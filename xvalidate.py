import sys
sys.path.append('/home/yannickv/proj/pytree')
from itertools import imap
from multiprocessing import Pool

import json
import numpy
from getopt import getopt
from dist_sim.fcomb import FCombo
import me_opt_new as me_opt

is_multiclass=False
predictions_fname=None

n_processors=1
reassign_folds=False
current_fold=0

opts,args=getopt(sys.argv[1:],'p:P:R')
for k,v in opts:
    if k=='-p':
        predictions_fname=v
    elif k=='-P':
        n_processors=int(v)
    elif k=='-R':
        reassign_folds=True

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

data_bins=[[] for unused_ in xrange(n_bins)]

fc=FCombo(2,bias_item='**BIAS**')
#fc=FCombo(2)

def mkdata(feats):
    lst=[]
    for f in feats:
        if isinstance(f,basestring):
            lst.append((f,1.0))
        else:
            lst.append(f)
    return lst

def make_fold_classifier(fold_no):
    fold_train=[]
    for (i,exs) in enumerate(data_bins):
        if i!=fold_no:
            fold_train += data_bins[i]
    x=numpy.zeros(len(fc.dict),'d')
    iflag,n_iter,x,d1=me_opt.run_lbfgs(x,me_opt.sparse_unary_func,(fold_train,))
    return x

for l in file(args[0]):
    bin_nr,data,label,unused_span=json.loads(l)
    if reassign_folds:
        bin_nr=current_fold
        current_fold=(current_fold+1)%n_bins
    vec=fc(mkdata(data))
    data_bins[bin_nr].append((vec,label))
fc.dict.growing=False

classifiers=make_mapper()(make_fold_classifier,xrange(n_bins))
cleanup()

current_fold=0
if predictions_fname is not None:
    f_predict=file(predictions_fname,'w')
stats=[0.0,0.0,0.0,0.0]
for l in file(args[0]):
    bin_nr,data,label,unused_span=json.loads(l)
    if reassign_folds:
        bin_nr=current_fold
        current_fold=(current_fold+1)%n_bins
    result=(fc(mkdata(data)).dotFull(classifiers[bin_nr]) > 0)
    if predictions_fname is not None:
        print >>f_predict,result
    stats[result+2*label]+=1.0
print >>sys.stderr, stats
prec=stats[3]/(stats[3]+stats[1])
recl=stats[3]/(stats[3]+stats[2])
acc=(stats[3]+stats[0])/sum(stats)
print >>sys.stderr, "Prec=%.3f Recl=%.3f F=%.3f"%(prec,recl,2*prec*recl/(prec+recl))
print >>sys.stderr, "Accuracy=%.3f"%(acc,)
