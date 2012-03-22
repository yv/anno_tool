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
import random
import me_opt_new as me_opt

from lxml import etree

from xvalidate_common import *
from xvalidate_common_mlab import *

oparse=optparse.OptionParser()
add_options_common(oparse)
add_options_mlab(oparse)
oparse.add_option('--method', type='choice', dest='method',
                      choices=['random','frequent'],
                      default='random')

oparse.set_defaults(reassign_folds=True,max_depth=3)

opts,args=oparse.parse_args(sys.argv[1:])

all_data,labelset0=load_data(args[0],opts)


left_out=0
rnd_gen=random.Random(opts.seed)
#fc=FCombo(2,bias_item='__bias__')

if opts.method=='random':
    classifications=[x[2] for x in all_data]
    rnd_gen.shuffle(classifications)
elif opts.method=='frequent':
    counts=defaultdict(int)
    counts_set=defaultdict(int)
    for x in all_data:
        counts[tuple(x[2])]+=1
    total=0.0
    for k,v in counts.iteritems():
        counts_set[tuple(sorted(k))]+=v
        total+=v
    all_counts=sorted((('+'.join(x[0]),x[1]/total) for x in counts.iteritems()),
                      key=lambda x:-x[1])
    print "Most frequent (exact):"
    for k,v in all_counts:
        print "%-40s %.3f"%(k,v)
    all_counts=sorted((('+'.join(x[0]),x[1]/total) for x in counts_set.iteritems()),
                      key=lambda x:-x[1])
    print "Most frequent (set):"
    for k,v in all_counts:
        print "%-40s %.3f"%(k,v)
    best=None
    best_count=-1
    for k in counts:
        if counts[k]>best_count:
            best=k
            best_count=counts[k]
    classifications=[list(best)]*len(all_data)

stats=make_stats_multi(all_data,
                       classifications,
                       opts)
print_stats(stats)
