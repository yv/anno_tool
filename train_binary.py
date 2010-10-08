import sys
import cPickle
sys.path.append('/home/yannickv/proj/pytree')
import json
import numpy
from getopt import getopt
from dist_sim.fcomb import FCombo
from ml_utils import *
import me_opt_new as me_opt

model_fname=None
current_fold=0

opts,args=getopt(sys.argv[1:],'m:')
for k,v in opts:
    if k=='-m':
        model_fname=v

train_data=[]

fc=FCombo(2,bias_item='**BIAS**')
#fc=FCombo(2)

def make_classifier():
    fold_train=train_data
    x=numpy.zeros(len(fc.dict),'d')
    iflag,n_iter,x,d1=me_opt.run_lbfgs(x,me_opt.sparse_unary_func,(fold_train,))
    return x

for l in file(args[0]):
    bin_nr,data,label,unused_span=json.loads(l)
    vec=fc(mkdata(data))
    train_data.append((vec,label))
fc.dict.growing=False

classifier=make_classifier()

f_cl=file(model_fname,'w')
cPickle.dump(BinaryClassifier(fc,classifier),f_cl,-1)
f_cl.close()
