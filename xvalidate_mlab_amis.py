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
from mltk.amis_wrapper import AMISLearner
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

(transform_target,gen_examples)=get_example_fn(opts)

label_gen=LabelGenerator(opts,all_data)

print >>sys.stderr, "preparing training file..."

learners=[AMISLearner('/export2/local/yannick/konn-cls/fold-%d'%(i,)) for i in xrange(n_bins)]
if opts.cutoff>1:
    for lrn in learners:
        lrn.count_threshold=opts.cutoff
streams=[x.open_events() for x in learners]

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
    wanted,unwanted=label_gen.gen_examples(label,data)
    assert wanted,label
    assert unwanted,label
    n1=make_multilabel(label_gen.gen_label(wanted[0]),
                       [label_gen.gen_label(lab) for lab in unwanted],
                       data,fc)
    buf.reset()
    buf.write('line_%s\n1\t'%(lineno,))
    dump_example(n1,buf,fc)
    buf.truncate()
    s=buf.getvalue()
    for i in xrange(n_bins):
        if i!=bin_nr:
            streams[i].write(s)
fc.dict.growing=False
for f in streams: f.close()


print >>sys.stderr, "training models..."

classifiers=[]
for i in xrange(n_bins):
    learners[i].run_learner()
    classifiers.append(learners[i].read_weights(fc))

if opts.weights_fname is not None:
    print_weights(opts.weights_fname,fc,classifiers)

def classify(dat):
    bin_nr,data,label=dat
    best=None
    best_score=-1000
    for label in label_gen.get_labelset(data):
        score=fc(data,labels=label_gen.gen_label(label)).dotFull(classifiers[bin_nr])
        if len(label)>1:
            score+=opts.bias_multi
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
