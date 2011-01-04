import sys
sys.path.append('/home/yannickv/proj/pytree')

from itertools import izip,imap
from collections import defaultdict
from multiprocessing import Pool
import json
import numpy
from getopt import getopt
from dist_sim.fcomb import FCombo
from alphabet import PythonAlphabet
#import me_opt2 as me_opt
#import sgd_opt as me_opt
import me_opt_new as me_opt

from lxml import etree

from xvalidate_common import *
     

predictions_fname=None
weights_fname=None
stats_fname=None
max_depth=3
n_processors=1
# target_gen: exact/set/single
target_gen='set'
# example_sel: exact/set/overlap
example_sel='set'
# labeling: h/hc/f/fc/gc
classification='fc'
reassign_folds=True

opts,args=getopt(sys.argv[1:],'p:w:P:Rd:T:S:C:')
for k,v in opts:
    if k=='-p':
        predictions_fname=v
    elif k=='-w':
        weights_fname=v
    elif k=='-P':
        n_processors=int(v)
    elif k=='-R':
        reassign_folds=True
    elif k=='-d':
        max_depth=int(v)
    elif k=='T':
        assert v in ['exact','set','single']
        target_gen=v
    elif k=='S':
        assert v in ['exact','set','overlap']
        example_sel=v
    elif k=='C':
        assert v in ['h','hc','f','fc','gc']
        classification=v

if n_processors==1:
    def cleanup():
        pass
    def make_mapper(want_iter=False):
        if want_iter:
            return imap
        else:
            return map
else:
    def make_mapper(want_iter=False):
        global cleanup
        p=Pool(n_processors)
        def my_cleanup():
            p.close()
        cleanup=my_cleanup
        if want_iter:
            def my_map(f,xs):
                return p.imap(f,xs,100)
            return my_map
            #return lambda f,xs: p.imap(f,xs,100)
        else:
            return p.map


all_data,labelset0=load_data(args[0],max_depth,reassign_folds)

if target_gen=='exact':
    transform_target=lambda x: x
elif target_gen=='set':
    transform_target=lambda x: sorted(x)
elif target_gen=='single':
    if example_sel=='overlap':
        transform_target=lambda x:x
    else:
        transform_target=lambda x: x[:1]

# generate set of labels that we would want to choose from
ls=set()
if target_gen=='single' and example_set=='overlap':
    for bin_nr, data, label in all_data:
        for x in label:
            ls.add((x,))
else:
    for bin_nr, data, label in all_data:
        ls.add(tuple(transform_target(label)))
labelset=sorted(ls)

def gen_examples_exact(label):
    labelT=tuple(label)
    positive=[labelT]
    negative=[]
    for k in labelset:
        if k!=labelT:
            negative.append(k)
    return (positive,negative)

def gen_examples_seq_set(label):
    # permuted sequence => neutral
    labelT=tuple(label)
    positive=[labelT]
    all_positive=[labelT]
    negative=[]
    if len(label)>1:
        labelT2=tuple([label[0],label[1]])
        if labelT2 in labelset:
            all_positive.append(labelT2)
    else:
        labelT2=None
    for k in labelset:
        if k not in all_positive:
            negative.append(k)
    return (positive,negative)

def gen_examples_overlap(label):
    labelT=tuple(label)
    positive=[labelT]
    all_positive=set(labelT)
    negative=[]
    for k in labelset:
        if not all_positive.intersect(k):
            negative.append(k)
    return (positive,negative)

def gen_examples_overlap_single(label):
    labelT=tuple(label)
    positive=[]
    all_positive=set(labelT)
    for k in all_positive:
        positive.append((k,))
    negative=[]
    for k in labelset:
        if not all_positive.intersect(k):
            negative.append(k)
    return (positive,negative)

# transform_target transforms the labels for generation of the target labelset
# transform_label transforms the labels for generation of positive/negative examples
if example_sel=='exact' or (example_sel=='set' and target_gen in ['set','single']):
    gen_examples=gen_examples_exact
elif example_sel=='set' and target_gen=='exact':
    gen_examples=gen_examples_seq_set
elif example_sel=='overlap':
    if target_gen=='single':
        gen_examples=gen_examples_overlap_single
    else:
        gen_examples=gen_examples_overlap

def gen_label_f(label,tgt):
    for k in label:
        parts=k.split('.')
        for i in xrange(1,len(parts)+1):
            tgt.append('.'.join(parts[:i]))

def gen_label_h(label,tgt):
    for k in label:
        tgt.append(k)

def gen_label_c(label,tgt):
    labelseq=[]
    for k in label:
        parts=k.split('.')
        labelseq.append(parts[0])
    tgt.append('RC=%s'%('^'.join(labelseq),))

gen_label_fns=[]
if classification[0]=='f':
    gen_label_fns.append(gen_label_f)
elif classification[0]=='h':
    gen_label_fns.append(gen_label_h)
if 'c' in classification:
    gen_label_fns.append(gen_label_c)

def gen_label(label):
    a=[]
    for f in gen_label_fns:
        f(label,a)
    return a

print >>sys.stderr, "preparing feature vectors..."

data_bins=[[] for unused_ in xrange(n_bins)]
fc=FCombo(2)
for bin_nr,data,label in all_data:
    wanted,unwanted=gen_examples(transform_target(label))
    assert wanted,label
    assert unwanted,label
    correct=[]
    incorrect=[]
    for lbl in wanted:
        vec=fc(mkdata(data),labels=gen_label(lbl))
        correct.append(vec)
    for lbl in unwanted:
        vec=fc(mkdata(data),labels=gen_label(lbl))
        incorrect.append(vec)
    data_bins[bin_nr].append((correct,incorrect))
fc.dict.growing=False

def make_fold_classifier(fold_no):
    fold_train=[]
    for (i,exs) in enumerate(data_bins):
        if i!=fold_no:
            fold_train += data_bins[i]
    x=me_opt.train_me_sparse(fold_train,fc.dict)
    return x

classifiers=make_mapper()(make_fold_classifier,xrange(n_bins))
cleanup()

if weights_fname is not None:
    print_weights(weights_fname,fc,classifiers)

def classify(dat):
    bin_nr,data,label=dat
    best=None
    best_score=-1000
    for label in labelset:
        score=fc(mkdata(data),labels=gen_label(label)).dotFull(classifiers[bin_nr])
        if score > best_score:
            best=label
            best_score=score
    return best

def count_common(lbl,lblS):
    common=0
    for k in lbl:
        for k2 in lblS:
            if k2.startswith(k):
                common+=1
                break
    print lbl,lblS,common
    return common

def extract_stats(lbl,lblS,stats):
    cc=count_common(lbl,lblS)
    len_s=len(lblS)
    len_g=len(lbl)
    stats['dice']+=2.0*count_common(lbl,lblS)/(len(lbl)+len(lblS))
    if cc==len(lblS):
        stats['subset']+=1.0
        if cc==len(lbl):
            stats['equal']+=1.0
            val_exact=1.0
            for k_g, k_s in izip(lbl,lblS):
                if not k_s.startswith(k_g):
                    val_exact=0.0
                    break
            stats['exact']+=val_exact
    if lblS[0].startswith(lbl[0]):
        stats['first']+=1.0

def make_stats_multi(all_data, system_labels_a, max_depth,
                     predictions_fname,
                     stats_fname):
    system_labels=list(system_labels_a)
    node_root=etree.Element('eval-data')
    num_examples=len(all_data)
    for d in xrange(1,max_depth+1):
        node_depth=etree.SubElement(node_root,'group',name='depth=%d'%(d,))
        single_vals=defaultdict(float)
        for ((bin_nr,data,label),sys_label) in izip(all_data,system_labels):
            labelC=[shrink_to(x,d) for x in label]
            sys_labelC=[shrink_to(x,d) for x in sys_label]
            extract_stats(labelC,sys_labelC,single_vals)
        print single_vals
        for k in sorted(single_vals.iterkeys()):
            etree.SubElement(node_depth,'singleVal',name=k,score=str(single_vals[k]/num_examples))
    if stats_fname is not None:
        f=file(stats_fname,'w')
        f.write(etree.tostring(stats,pretty_print=True,standalone=True))
        f.close()
    return node_root

def print_eval_multi(stats):
    print etree.tostring(stats,pretty_print=True)

stats=make_stats_multi(all_data,
                       make_mapper(True)(classify,all_data),
                       max_depth,
                       predictions_fname, stats_fname)
print_eval_multi(stats)
