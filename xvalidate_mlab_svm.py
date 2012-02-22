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
from svm_wrapper import SVMLearner, train_greedy, classify_greedy_mlab, set_flags
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
oparse.set_defaults(reassign_folds=True,max_depth=3)

opts,args=oparse.parse_args(sys.argv[1:])

if opts.method=='F':
    set_flags(['-w','3','-c','0.01','-l','1'])
elif opts.method=='acc':
    set_flags(['-c','1'])

all_data,labelset0=load_data(args[0],opts)

(transform_target,gen_examples)=get_example_fn(opts)

label_gen=LabelGenerator(opts,all_data)

if opts.n_processors==1:
    def cleanup():
        pass
    def make_mapper(want_iter=False):
        if want_iter:
            return imap
        else:
            return map


print >>sys.stderr, "preparing training file..."

data_bins=[[] for i in xrange(n_bins)]
test_bins=[[] for i in xrange(n_bins)]

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
    vec=fc(data)
    for i in xrange(n_bins):
        if i!=bin_nr:
            data_bins[i].append((vec,label))
        else:
            test_bins[i].append((vec,label))
fc.dict.growing=False

print >>sys.stderr, "training models..."
classifiers=[]
for i,data_bin in enumerate(data_bins):
    labels=[x[1] for x in data_bin]
    examples=[x[0] for x in data_bin]
    basedir='/export/local/yannick/konn-cls/fold-%d'%(i,)
    cl_greedy=train_greedy(examples,labels,basedir,fc)
    classifiers.append(cl_greedy)

# for i,data_bin in enumerate(test_bins):
#     labels=[x[1] for x in data_bin]
#     examples=[x[0] for x in data_bin]
#     basedir='/export/local/yannick/konn-cls/fold-%d'%(i,)
#     convert_onevsall(examples,labels,basedir,'test_')

if opts.weights_fname is not None:
    print_weights(opts.weights_fname,fc,classifiers)

def classify(dat):
    bin_nr,data,label=dat
    best=classify_greedy_mlab(classifiers[bin_nr],fc(data))
    return best



stats=make_stats_multi(all_data,
                       make_mapper(True)(classify,all_data),
                       opts)
if left_out:
    print >>sys.stderr, "Subsampling: left out %d/%d examples"%(left_out,len(all_data))
print_stats(stats)
