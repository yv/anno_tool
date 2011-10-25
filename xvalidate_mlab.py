import sys
sys.path.append('/home/yannickv/proj/pytree')

from itertools import izip,imap
from collections import defaultdict
from multiprocessing import Pool
import json
import numpy
import optparse
import random
from dist_sim.fcomb import FCombo
from alphabet import PythonAlphabet
#import me_opt2 as me_opt
#import sgd_opt as me_opt
#import me_opt_new as me_opt
from dist_sim import sgd

from lxml import etree

from xvalidate_common import *
from xvalidate_common_mlab import *
     
oparse=optparse.OptionParser()
add_options_common(oparse)
add_options_mlab(oparse)
oparse.set_defaults(reassign_folds=True,max_depth=3)

opts,args=oparse.parse_args(sys.argv[1:])

if opts.n_processors==1:
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


all_data,labelset0=load_data(args[0],opts)

#transform_target,gen_examples = get_example_fn(example_sel,target_gen)


label_gen=LabelGenerator(opts,all_data)

print >>sys.stderr, "preparing feature vectors..."

level_weights=[1.0,1.0,1.0]
def multilevel_dice(lab,lab2):
    """loss function that is based on dice scores at multiple levels"""
    total=0.0
    Z=0.0
    for d in xrange(1,4):
        short=set([shrink_to(x,d) for x in lab])
        short2=set([shrink_to(x,d) for x in lab2])
        total+=level_weights[d-1]*2.0*len(short.intersection
                                          (short2))/(len(short)+len(short2))
        Z+=level_weights[d-1]
    return 1.0-total/Z

left_out=0
data_bins=[[] for unused_ in xrange(n_bins)]
fc=FCombo(opts.degree)
for bin_nr,data,label in all_data:
    if random.random() >= opts.subsample:
        left_out+=1
        continue
    wanted,unwanted=label_gen.gen_examples(label,data)
    assert wanted,label
    if not unwanted:
        continue
    correct=[]
    incorrect=[]
    loss_vals=[]
    for lbl in wanted:
        vec=fc(data,labels=label_gen.gen_label(lbl))
        correct.append(vec)
    for lbl in unwanted:
        vec=fc(data,labels=label_gen.gen_label(lbl))
        incorrect.append(vec)
        loss_vals.append(3.0*multilevel_dice(label,lbl))
    data_bins[bin_nr].append((correct,incorrect,loss_vals))
fc.dict.growing=False

def make_fold_classifier(fold_no):
    fold_train=[]
    for (i,exs) in enumerate(data_bins):
        if i!=fold_no:
            fold_train += data_bins[i]
    p=sgd.make_problem(fold_train, 'ranking_hinge', fc)
    p.C=10.0
    x=sgd.run_optimize(p, 'sgd')
    #x=me_opt.train_me_sparse(fold_train,fc.dict)
    return x

classifiers=make_mapper()(make_fold_classifier,xrange(n_bins))
cleanup()

if opts.weights_fname is not None:
    print_weights(opts.weights_fname,fc,classifiers)

def classify(dat):
    bin_nr,data,label=dat
    best=None
    best_score=-1000
    for label in label_gen.get_labelset(data):
        score=fc(data,labels=label_gen.gen_label(label)).dotFull(classifiers[bin_nr])
        if score > best_score:
            best=label
            best_score=score
    return label_gen.restored_label(best)

stats=make_stats_multi(all_data,
                       make_mapper(True)(classify,all_data),
                       opts)
if left_out:
    print >>sys.stderr, "Subsampling: left out %d/%d examples"%(left_out,len(all_data))
print_stats(stats)
