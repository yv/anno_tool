import sys
sys.path.append('/home/yannickv/proj/pytree')

import codecs
from itertools import izip,imap
from collections import defaultdict
from multiprocessing import Pool
from cStringIO import StringIO
import json
import numpy
from getopt import getopt
import optparse
from dist_sim.fcomb import FCombo, make_multilabel, dump_example
from alphabet import PythonAlphabet
from svm_wrapper import svmperf, train_greedy, classify_greedy_mlab, set_flags
#import me_opt2 as me_opt
#import sgd_opt as me_opt
import random
import me_opt_new as me_opt

from lxml import etree

from xvalidate_common import *
from xvalidate_common_mlab import *

oparse=optparse.OptionParser()
add_options_common(oparse)
add_options_mlab(oparse)
oparse.add_option('--method',dest='method',
                  choices=['F','acc'],
                  default='F')
oparse.add_option('--maxlabels',dest='max_labels',
                  type='int', default=2)
oparse.add_option('--featsel',dest='feat_sel',
                  type='int', default=0)
oparse.add_option('--featsize',dest='feat_size')
oparse.set_defaults(reassign_folds=True,max_depth=3)

opts,args=oparse.parse_args(sys.argv[1:])

my_svmperf=svmperf.bind(datafile_pattern='/export2/local/yannick/konn-cls/fold-%(fold)d/%(label)s_d%(depth)d_train.data',
                        classifier_pattern='/export2/local/yannick/konn-cls/fold-%(fold)d/%(label)s_d%(depth)d_train.model')
if opts.method=='F':
    my_svmperf=my_svmperf.bind(flags=['-w','3','-c','0.01','-l','1'])
elif opts.method=='acc':
    my_svmperf=my_svmperf.bind(flags=['-c','1'])

all_data,labelset0=load_data(args[0],opts)

if opts.n_processors==1:
    def cleanup():
        pass
    def make_mapper(want_iter=False):
        if want_iter:
            return imap
        else:
            return map


print >>sys.stderr, "preparing training file..."

data0_bins=[[] for i in xrange(n_bins)]
test0_bins=[[] for i in xrange(n_bins)]
data_bins=[[] for i in xrange(n_bins)]
test_bins=[[] for i in xrange(n_bins)]

def chi2(n_ab,n_a,n_b,N):
    if n_a==0 or n_a==N:
        return 0.0
    if n_b==0 or n_b==N:
        return 0.0
    obs=[n_ab,n_a-n_ab,n_b-n_ab,N+n_ab-n_a-n_b]
    p_a=float(n_a)/N
    p_b=float(n_b)/N
    ext=[p_a*n_b,(1.0-p_b)*n_a,(1.0-p_a)*n_b,(1.0-p_a)*(N-n_b)]
    x2=sum(((o-e)**2/e for (o,e) in izip(obs,ext)))
    return x2

left_out=0
rnd_gen=random.Random(opts.seed)
#fc=FCombo(2,bias_item='__bias__')
fc=FCombo(opts.degree)
fc.codec=codecs.lookup('ISO-8859-15')
lineno=0
buf=StringIO()
for bin_nr,data,label in all_data:
    lineno+=1
    if rnd_gen.random()>=opts.subsample:
        left_out+=1
        continue
    if opts.feat_sel:
        vec0=fc.munge_uni(data)
    else:
        vec0=fc(data)
    for i in xrange(n_bins):
        if i!=bin_nr:
            data0_bins[i].append((vec0,label))
        else:
            test0_bins[i].append((vec0,label))
if opts.feat_sel:
    if opts.feat_size is not None:
        feat_sizes=[int(x) for x in opts.feat_size.split(',')]
    else:
        feat_sizes=[0,500]
    # Feature Selection & Creation of actual feature vectors
    for i in xrange(n_bins):
        print >>sys.stderr, "Feature selection for fold %d"%(i,)
        label_vecs, feature_vecs_a=example_vectors(data0_bins[i])
        N=len(data0_bins[i])
        mask=[None]
        for j,feature_vecs in enumerate(feature_vecs_a):
            all_vals=numpy.zeros(len(fc.dict))
            for (k,fvec) in enumerate(feature_vecs):
                best_val=0.0
                fvec_len=len(fvec)
                if fvec_len==0: continue
                for lbl_vec in label_vecs:
                    lbl_len=len(lbl_vec)
                    val=chi2(fvec.count_intersection(lbl_vec),fvec_len,lbl_len,N)
                    if val>best_val:
                        best_val=val
                all_vals[k]=best_val
            ordering=numpy.argsort(all_vals)
            for k in ordering[-3:]:
                print "Feature %s value %f"%(fc.dict.get_sym(k),all_vals[k])
            if j<len(feat_sizes):
                n_max=feat_sizes[j]
            if n_max>0:
                if len(ordering)>n_max:
                    print "cutoff[%d] = %f"%(j,all_vals[ordering[-n_max]])
                    mask.append((all_vals >= all_vals[ordering[-n_max]]))
                else:
                    mask.append(None)
        data_bins[i]=[(fc.munge_vec(vec0,mask),label) for (vec0,label) in data0_bins[i]]
        test_bins[i]=[(fc.munge_vec(vec0,mask),label) for (vec0,label) in test0_bins[i]]
else:
    data_bins=data0_bins
    test_bins=test0_bins
fc.dict.growing=False

print >>sys.stderr, "training models..."
classifiers=[]
for i,data_bin in enumerate(data_bins):
    labels=[x[1] for x in data_bin]
    examples=[x[0] for x in data_bin]
    basedir='/export2/local/yannick/konn-cls/fold-%d'%(i,)
    cl_greedy=train_greedy(examples,labels,my_svmperf.bind(fold=i))
    classifiers.append(cl_greedy)

# for i,data_bin in enumerate(test_bins):
#     labels=[x[1] for x in data_bin]
#     examples=[x[0] for x in data_bin]
#     basedir='/export2/local/yannick/konn-cls/fold-%d'%(i,)
#     convert_onevsall(examples,labels,basedir,'test_')

if opts.weights_fname is not None:
    print_weights(opts.weights_fname,fc,classifiers)

def classify(dat):
    bin_nr,data,label=dat
    best=classify_greedy_mlab(classifiers[bin_nr],fc(data),opts.max_labels)
    return best



stats=make_stats_multi(all_data,
                       make_mapper(True)(classify,all_data),
                       opts)
if left_out:
    print >>sys.stderr, "Subsampling: left out %d/%d examples"%(left_out,len(all_data))
print_stats(stats)
