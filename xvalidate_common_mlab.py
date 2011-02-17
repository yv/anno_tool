from collections import defaultdict
from itertools import izip
from lxml import etree
import simplejson as json
import sys

from xvalidate_common import shrink_to

__doc__="""
This module contains common routines for the multi-label
classification scripts
"""

def add_options_mlab(oparse):
    oparse.add_option('-T', type='choice', dest='target_gen',
                      choices=['exact','set','single'],
                      default='set')
    oparse.add_option('-S', type='choice', dest='example_sel',
                      choices=['exact','set','overlap'],
                      default='set')
    oparse.add_option('-C', type='choice', dest='classification',
                      choices=['h', 'hc', 'f', 'fc', 'gc'],
                      default='fc')
    oparse.add_option('--filter_feature', dest='filter_feature')

def gen_examples_exact(label,labelset):
    labelT=tuple(label)
    positive=[labelT]
    negative=[]
    for k in labelset:
        if k!=labelT:
            negative.append(k)
    return (positive,negative)

def gen_examples_seq_set(label,labelset):
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

def gen_examples_overlap(label,labelset):
    labelT=tuple(label)
    positive=[labelT]
    all_positive=set(labelT)
    negative=[]
    for k in labelset:
        if not all_positive.intersection(k):
            negative.append(k)
    return (positive,negative)

def gen_examples_overlap_single(label,labelset):
    labelT=tuple(label)
    positive=[]
    all_positive=set(labelT)
    for k in all_positive:
        positive.append((k,))
    negative=[]
    for k in labelset:
        if not all_positive.intersection(k):
            negative.append(k)
    return (positive,negative)

def get_example_fn(opts):
    """
    given option values for example_sel and target_gen, get_example_fn
    returns two functions:
    * transform_target transforms target multilabels to the actual form
      that is used as a training example
    * gen_examples gives positive and negative label candidates for a
      given gold label and a set of potential labels
    """
    target_gen=opts.target_gen
    example_sel=opts.example_sel
    # transform_target transforms the labels for generation of the target labelset
    if target_gen=='exact':
        transform_target=lambda x: x
    elif target_gen=='set':
        transform_target=lambda x: sorted(x)
    elif target_gen=='single':
        if example_sel=='overlap':
            transform_target=lambda x:x
        else:
            transform_target=lambda x: x[:1]
    if example_sel=='exact' or (example_sel=='set' and target_gen in ['set','single']):
        gen_examples=gen_examples_exact
    elif example_sel=='set' and target_gen=='exact':
        gen_examples=gen_examples_seq_set
    elif example_sel=='overlap':
        if target_gen=='single':
            gen_examples=gen_examples_overlap_single
        else:
            gen_examples=gen_examples_overlap
    return (transform_target,gen_examples)

def gen_label_f(label,tgt):
    for k in label:
        tgt.append(k)

def gen_label_h(label,tgt):
    for k in label:
        parts=k.split('.')
        for i in xrange(1,len(parts)+1):
            tgt.append('.'.join(parts[:i]))

def gen_label_c(label,tgt):
    labelseq=[]
    for k in label:
        parts=k.split('.')
        labelseq.append(parts[0])
    tgt.append('RC=%s'%('+'.join(labelseq),))

def choose_most_frequent(src_map):
    dummy=-sys.maxint
    dst_map={}
    for k1,vals in src_map.iteritems():
        max_val=-sys.maxint
        best=None
        for k2,val in vals.iteritems():
            if val>max_val:
                best=k2
                max_val=val
        dst_map[k1]=best
    return dst_map

class LabelGenerator:
    """
    handles the generation of possible or positive/negative labels
    according to the given options
    """
    def get_filter(self,data):
        """extracts the split_feature value"""
        feat=self.split_feature
        filt=[]
        for k in data:
            if k.startswith(feat):
                filt.append(k)
        if not filt:
            filt=[None]
        return filt
    def get_labelset(self,data):
        """returns a set of plausible labels (based on split_feature)"""
        if self.split_feature:
            my_ls=set()
            for k in get_filter(filter_feature,data):
                my_ls.update(ls_dict[k])
            return sorted(my_ls)
        else:
            return self.ls_dict[None]
    def gen_label(self, label):
        a=[]
        for f in self.gen_label_fns:
            f(label,a)
        return a
    def restored_label(self,label):
        restore_map=self.restore_map
        if restore_map is None:
            return label
        else:
            return restore_map[tuple(label)]
    def __init__(self,opts,all_data):
        filter_feature=opts.filter_feature
        self.split_feature=filter_feature
        transform_target, example_gen = get_example_fn(opts)
        self.transform_fn=transform_target
        self.example_fn=example_gen
        ls_dict=defaultdict(set)
        want_restore=False
        if opts.target_gen in ['single','set']:
            want_restore=True
            restore_map=defaultdict(lambda: defaultdict(int))
        # generate set of labels that we would want to choose from
        if opts.target_gen=='single' and opts.example_sel=='overlap':
            for bin_nr, data, label in all_data:
                if filter_feature:
                    filt=[ls_dict[k] for k in get_filter(filter_feature,data)]
                else:
                    filt=[ls_dict[None]]
                for x in label:
                    for ls1 in filt:
                        ls1.add((x,))
                    restore_map[(x,)][tuple(label)]+=1
        else:
            for bin_nr, data, label in all_data:
                if filter_feature:
                    filt=[ls_dict[k] for k in get_filter(filter_feature,data)]
                else:
                    filt=[ls_dict[None]]
                lbl=tuple(transform_target(label))
                for ls1 in filt:
                    ls1.add(lbl)
                if want_restore:
                    restore_map[lbl][tuple(label)]+=1
        if want_restore:
            self.restore_map=choose_most_frequent(restore_map)
        else:
            self.restore_map=None
        ## vvv why would this be needed?
        ## ls_dict[None]=sorted(ls_dict[None])
        self.ls_dict=ls_dict
        # set up generator for label parts
        gen_label_fns=[]
        classification=opts.classification
        if classification[0]=='f':
            gen_label_fns.append(gen_label_f)
        elif classification[0]=='h':
            gen_label_fns.append(gen_label_h)
        if 'c' in classification:
            gen_label_fns.append(gen_label_c)
        self.gen_label_fns=gen_label_fns
    def gen_examples(self,label,data):
        return self.example_fn(self.transform_fn(label),self.get_labelset(data))



def count_common(lbl,lblS):
    common=0
    for k in lbl:
        for k2 in lblS:
            if k2.startswith(k):
                common+=1
                break
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

def extract_fm_stats(lbl,lblS,stats):
    foundS=set()
    for k in lbl:
        found=False
        for k2 in lblS:
            if k2.startswith(k):
                stats[k2][0]+=1
                foundS.add(k2)
                found=True
                break
        if not found:
            stats[k][1]+=1
    for k2 in lblS:
        if k2 not in foundS:
            stats[k2][2]+=1

def make_stats_multi(all_data, system_labels_a,
                     opts):
    max_depth=opts.max_depth
    predictions_fname=opts.predictions_fname
    stats_fname=opts.stats_fname
    system_labels=list(system_labels_a)
    node_root=etree.Element('eval-data')
    if opts.subsample is not None:
        etree.SubElement(node_root,'param',program='xvalidate',
                         name='subsample',value=str(opts.subsample))
    if opts.assigned_tag is not None:
        etree.SubElement(node_root,'param',program='--',
                         name='tag',value=assigned_tag)
    num_examples=len(all_data)
    for d in xrange(1,max_depth+1):
        node_depth=etree.SubElement(node_root,'group',name='depth=%d'%(d,))
        single_vals=defaultdict(float)
        fm_vals=defaultdict(lambda: [0,0,0])
        for ((bin_nr,data,label),sys_label) in izip(all_data,system_labels):
            labelC=[shrink_to(x,d) for x in label]
            sys_labelC=[shrink_to(x,d) for x in sys_label]
            extract_stats(labelC,sys_labelC,single_vals)
            extract_fm_stats(labelC,sys_labelC,fm_vals)
        for k in sorted(single_vals.iterkeys()):
            etree.SubElement(node_depth,'singleVal',name=k,score=str(single_vals[k]/num_examples))
        for k,v in sorted(fm_vals.iteritems()):
            etree.SubElement(node_depth,'relCount',name=k,
                             tp=str(v[0]),
                             fn=str(v[1]),
                             fp=str(v[2]))
    if predictions_fname is not None:
        f=file(predictions_fname,'w')
        for sys_label in system_labels:
            print >>f, json.dumps(sys_label)
        f.close()
    if stats_fname is not None:
        f=file(stats_fname,'w')
        f.write(etree.tostring(node_root,pretty_print=True,standalone=True))
        f.close()
    return node_root

def gather_stats(node,ctx,result):
    if node.tag=='eval-data':
        pass
    elif node.tag=='group':
        ctx+=node.get('name')+'/'
    elif node.tag=='singleVal':
        result[ctx+node.get('name')]=float(node.get('score'))
    elif node.tag=='relCount':
        tp=int(node.get('tp'))
        fp=int(node.get('fp'))
        fn=int(node.get('fn'))
        if tp==0:
            p=r=f=0
        else:
            p=float(tp)/(tp+fp)
            r=float(tp)/(tp+fn)
            f=2*p*r/(p+r)
        result[ctx+node.get('name')]=f
    for n in node:
        gather_stats(n,ctx,result)

def print_stats(node,indent=0):
    indentS=' '*indent
    if node.tag=='eval-data':
        pass
    elif node.tag=='group':
        print '%sGROUP: %s'%(indentS,node.get('name'))
    elif node.tag=='singleVal':
        print '%-40s %.3f'%(indentS+node.get('name'),float(node.get('score')))
    elif node.tag=='relCount':
        tp=int(node.get('tp'))
        fp=int(node.get('fp'))
        fn=int(node.get('fn'))
        if tp==0:
            p=r=f=0
        else:
            p=float(tp)/(tp+fp)
            r=float(tp)/(tp+fn)
            f=2*p*r/(p+r)
        print '%-40s Prec %.3f (%d/%d)\tRecl %.3f (%d/%d)\tF1=%.3f'%(indentS+node.get('name'),
                                                                   p,tp,tp+fp,r,tp,tp+fn,f)
    for n in node:
        print_stats(n,indent+1)
