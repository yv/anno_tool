import sys
import cPickle
sys.path.append('/home/yannickv/proj/pytree')

from itertools import imap
from collections import defaultdict
from multiprocessing import Pool
import json
import numpy
import array
from getopt import getopt
from dist_sim.fcomb import FCombo
from alphabet import PythonAlphabet
from ml_utils import *
#import me_opt2 as me_opt
#import sgd_opt as me_opt
import me_opt_new as me_opt

predictions_fname=None
weights_fname=None
stats_fname=None
lenient=False
max_depth=None

opts,args=getopt(sys.argv[1:],'d:m:')
for k,v in opts:
    if k=='-d':
        max_depth=int(v)
    elif k=='-m':
        model_fname=v


train_data=[]

def shrink_to(lbl,d):
    parts=lbl.split('.')
    if len(parts)>d:
        lbl='.'.join(parts[:d])
    return lbl

labelset=PythonAlphabet()
all_data=[]
for l in file(args[0]):
    bin_nr,data,label,unused_span=json.loads(l)
    new_label=[]
    new_label_2=[]
    for lbl in label:
        if max_depth is not None:
            lbl=shrink_to(lbl,max_depth)
        labelset[lbl]
        new_label.append(lbl.split('.'))
        new_label_2.append(lbl)
    all_data.append((bin_nr,data,new_label_2))
    train_data.append((new_label,mkdata(data)))
labelset.growing=False

def make_classifier():
    cls=make_greedy_classifier(train_data)
    return cls

def make_greedy_classifier(fold_train):
    labelset=set()
    fc_here=FCombo(2)
    for suffixes,ex in fold_train:
        for suffix in suffixes:
            if suffix:
                labelset.add(suffix[0])
            else:
                labelset.add('')
    if labelset==set(['']):
        return (labelset,None,None,None)
    train_here=[]
    next_level=defaultdict(list)
    wanted_suffixes=set()
    for suffixes,ex in fold_train:
        # which are the positive example(s)?
        wanted_suffixes.clear()
        for suffix in suffixes:
            if suffix:
                wanted_suffixes.add(suffix[0])
            else:
                wanted_suffixes.add('')
        ## stick relevant sub-classifications in next_level
        for suffix0 in wanted_suffixes:
            if wanted_suffixes=='':
                continue
            next_suffixes=[]
            for suffix in suffixes:
                if len(suffix)>1 and suffix[0]==suffix0:
                    next_suffixes.append(suffix[1:])
            if next_suffixes:
                next_level[suffix0].append((next_suffixes,ex))
        ## make actual training example
        correct=[]
        incorrect=[]
        for lbl1 in labelset:
            vec=fc_here(ex,labels=[lbl1])
            if lbl1 in wanted_suffixes:
                correct.append(vec)
            else:
                incorrect.append(vec)
        if correct and incorrect:
            train_here.append((correct,incorrect))
    print len(train_here), labelset
    if train_here:
        x=me_opt.train_me_sparse(train_here,fc_here.dict)
        del train_here
        alph_new,x_new=reduce_classifier(fc_here.dict,x)
        alph_new.growing=False
        fc_here.set_dict(alph_new)
        del x
        fc_here.dict.growing=False
        #x_new=x
    else:
        fc_here=x_new=None
    sub_classifiers=dict()
    for k,v in next_level.iteritems():
        sub_classifiers[k]=make_greedy_classifier(v)
    return (labelset,fc_here,x_new,sub_classifiers)

classifier=make_classifier()

f_cl=file(model_fname,'w')
cPickle.dump(GreedyClassifier(classifier),f_cl,-1)
f_cl.close()
