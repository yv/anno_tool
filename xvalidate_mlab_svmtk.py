import sys
import os
import shutil
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
from svmtk_wrapper import svmtk, train_greedy, classify_greedy_mlab
import random

from lxml import etree

from xvalidate_common import *
from xvalidate_common_mlab import *

oparse=optparse.OptionParser()
add_options_common(oparse)
add_options_mlab(oparse)
oparse.add_option('--maxlabels',dest='max_labels',
                  type='int', default=2)
oparse.add_option('--method', dest='method', default='poly',
                  type='choice', choices=['linear','poly','rbf','rbf2','rbf3','tree','st','pt'])
oparse.add_option('--subdir',action="store_true",dest="want_subdir")
oparse.set_defaults(reassign_folds=True,max_depth=3)

opts,args=oparse.parse_args(sys.argv[1:])

if opts.want_subdir:
    subdir='/export2/local/yannick/konn-cls/%s/'%(os.getpid(),)
    os.mkdir(subdir)
    for i in xrange(10):
        os.mkdir('%sfold-%d'%(subdir,i))
else:
    subdir='/export2/local/yannick/konn-cls/'
    
my_svmtk=svmtk.bind(datafile_pattern=subdir+'fold-%(fold)d/%(label)s_d%(depth)d_train.data',
                    classifier_pattern=subdir+'fold-%(fold)d/%(label)s_d%(depth)d_train.model')

if opts.method=='poly':
    my_svmtk=my_svmtk.bind(flags=['-t', '1','-d',str(opts.degree),'-c','1','-m','800'])
elif opts.method=='linear':
    my_svmtk=my_svmtk.bind(flags=['-t', '0','-c','1','-m','800'])
elif opts.method=='rbf':
    my_svmtk=my_svmtk.bind(flags=['-t', '2','-m','800'])
elif opts.method=='rbf2':
    my_svmtk=my_svmtk.bind(flags=['-t', '2','-g','0.1','-m','800'])
elif opts.method=='rbf3':
    my_svmtk=my_svmtk.bind(flags=['-t', '2','-c','10','-m','800'])
elif opts.method=='tree':
    my_svmtk=my_svmtk.bind(flags=['-t', '5','-S','1','-F','1','-d',str(opts.degree),'-C','+','-N','1', '-m','800'])
elif opts.method=='st':
    my_svmtk=my_svmtk.bind(flags=['-t', '5','-S','0','-F','1','-d',str(opts.degree),'-C','+','-N','1', '-m','800'])
elif opts.method=='pt':
    my_svmtk=my_svmtk.bind(flags=['-t', '5','-S','2','-M','0.7','-N','0','-F','1','-d',str(opts.degree),'-C','+', '-m','800'])
else:
    print >>sys.stderr, "No method selected?"

all_data,labelset0=load_data(args[0],opts)

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
        p=Pool(opts.n_processors)
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

print >>sys.stderr, "preparing training file..."

data_bins=[[] for i in xrange(n_bins)]
test_bins=[[] for i in xrange(n_bins)]

left_out=0
rnd_gen=random.Random(opts.seed)
#fc=FCombo(2,bias_item='__bias__')
#fc=FCombo(opts.degree)
fc=FCombo(1)
fc.codec=codecs.lookup('ISO-8859-15')
lineno=0
buf=StringIO()
for bin_nr,data,label in all_data:
    lineno+=1
    if rnd_gen.random()>=opts.subsample:
        left_out+=1
        continue
    buf.truncate(0)
    fc.to_svmltk(data,buf)
    vec=buf.getvalue()
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
    cl_greedy=train_greedy(examples,labels,my_svmtk.bind(fold=i))
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
    buf=StringIO()
    buf.write('0 ')
    fc.to_svmltk(data,buf)
    vec=buf.getvalue()
    #print vec
    best=classify_greedy_mlab(classifiers[bin_nr],vec,opts.max_labels)
    return best



stats=make_stats_multi(all_data,
                       make_mapper(True)(classify,all_data),
                       opts)
if left_out:
    print >>sys.stderr, "Subsampling: left out %d/%d examples"%(left_out,len(all_data))
print_stats(stats)

if opts.want_subdir:
    shutil.rmtree(subdir)
