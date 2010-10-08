import sys
sys.path.append('/home/yannickv/proj/pytree')

from itertools import izip,imap
from multiprocessing import Pool
import json
import numpy
from getopt import getopt
from dist_sim.fcomb import FCombo
from alphabet import PythonAlphabet
#import me_opt2 as me_opt
#import sgd_opt as me_opt
import me_opt_new as me_opt

from xvalidate_common import *
     

predictions_fname=None
weights_fname=None
stats_fname=None
lenient=False
max_depth=None
n_processors=1
classification='hier'

n_rare=10

opts,args=getopt(sys.argv[1:],'C:P:p:w:d:s:l')
for k,v in opts:
    if k=='-p':
        predictions_fname=v
    elif k=='-w':
        weights_fname=v
    elif k=='-d':
        max_depth=int(v)
    elif k=='-l':
        lenient=True
    elif k=='-s':
        stats_fname=v
    elif k=='-P':
        n_processors=int(v)
    elif k=='-C':
        assert v in ['hier','flat']
        classification_scheme=v

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

n_bins=10


all_data=[]

all_data,labelset=load_data(args[0],max_depth)

print labelset.words

labelparts=[]
if classification=='hier':
    for label in labelset.words:
        parts=label.split('.')
        clabel=[]
        for i in xrange(1,len(parts)+1):
            clabel.append('.'.join(parts[:i]))
        labelparts.append(clabel)
elif classification=='flat':
    for label in labelset.words:
        labelparts.append([label])
    

data_bins=[[] for unused_ in xrange(n_bins)]
fc=FCombo(2)
for bin_nr,data,label in all_data:
    correct=[]
    incorrect=[]
    for label1,clabel in izip(labelset.words,labelparts):
        vec=fc(mkdata(data),labels=clabel)
        seen=False
        for lbl in label:
            if lbl==label1:
                correct.append(vec)
                seen=True
            elif label1.startswith(lbl):
                seen=True
        if not seen:
            incorrect.append(vec)
    assert correct,label
    assert incorrect,label
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
    for label1,clabel in izip(labelset.words,labelparts):
        score=fc(mkdata(data),labels=clabel).dotFull(classifiers[bin_nr])
        if score > best_score:
            best=label1
            best_score=score
    return best

stats=make_stats(all_data,
                 make_mapper(True)(classify,all_data),
                 labelset, lenient,
                 predictions_fname, stats_fname)
if max_depth is None:
    max_depth=max([len(lbl.split('.')) for lbl in labelset.words])
for d in xrange(1,max_depth+1):
    print_eval(stats,labelset,d)
