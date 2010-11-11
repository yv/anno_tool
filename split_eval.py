import sys
import re
import simplejson as json
import numpy
from collections import defaultdict
from alphabet import PythonAlphabet
from getopt import getopt
from xvalidate_common import print_eval, get_accuracy

max_depth=3
min_freq=0
lenient=True
compare_fname=None
sort_key='freq'


def shrink_to(lbl,d):
    parts=lbl.split('.')
    if len(parts)>d:
        lbl='.'.join(parts[:d])
    return lbl

opts,args=getopt(sys.argv[1:],'d:F:C:s:')
for k,v in opts:
    if k=='-F':
        min_freq=int(v)
    elif k=='-C':
        compare_fname=v
    elif k=='-d':
        max_depth=int(v)
    elif k=='-s':
        sort_key=v

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
        new_label_2.append(lbl)
    all_data.append((bin_nr,data,new_label_2))
labelset.growing=False

N=len(labelset)
if max_depth is None:
    max_depth=max([len(lbl.split('.')) for lbl in labelset.words])

def get_stats(fname,feature_re):
    stats=defaultdict(lambda: numpy.zeros([N,N],'d'))
    f_cls=file(fname)
    for bin_nr,data,label in all_data:
        best=f_cls.readline().strip()
        if max_depth is not None:
            best=shrink_to(best,max_depth)
        matching_features=[x for x in data if feature_re.match(x)]
        if not matching_features:
            matching_features=[None]
        new_label=[]
        for lbl in label:
            if max_depth is not None:
                lbl=shrink_to(lbl,max_depth)
            new_label.append(lbl)
        label=new_label
        if best in label:
            lbl=best
        elif lenient and len(label)==1 and best.startswith(label[0]):
            lbl=best
        else:
            lbl=label[0]
        for k in matching_features:
            stats[k][labelset[best],labelset[lbl]]+=1.0
    return stats

wanted_features=re.compile(args[2])
stats=get_stats(args[1],wanted_features)
if compare_fname is not None:
    stats2=get_stats(compare_fname,wanted_features)

lblsort=stats.keys()
if sort_key=='freq':
    lblsort.sort(key=lambda k: stats[k].sum())
elif sort_key=='acc1':
    lblsort.sort(key=lambda k: get_accuracy(stats[k],labelset,max_depth))
elif sort_key=='acc2':    
    lblsort.sort(key=lambda k: get_accuracy(stats2[k],labelset,max_depth))
elif sort_key=='diff':
    lblsort.sort(key=lambda k: get_accuracy(stats2[k],labelset,max_depth)-get_accuracy(stats[k],labelset,max_depth))
elif sort_key=='key':
    lblsort.sort()
else:
    print >>sys.stderr,"Unknown sort key %s"%(sort_key,)
    sys.exit(1)
for k in lblsort:
    freq=stats[k].sum()
    if freq>=min_freq:
        acc=get_accuracy(stats[k],labelset,max_depth)
        if compare_fname:
            acc2=get_accuracy(stats2[k],labelset,max_depth)
            print "%-24s %4d\t%.3f\t%.3f\t%+.3f"%(k,stats[k].sum(),acc,acc2,acc2-acc)
        else:
            print "%-24s %4d\t%.3f"%(k,stats[k].sum(),acc)
