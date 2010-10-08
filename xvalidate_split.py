import sys
sys.path.append('/home/yannickv/proj/pytree')

from itertools import izip,imap
from collections import defaultdict
from multiprocessing import Pool
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

n_bins=10

n_rare=100000
n_rare_c=100000

opts,args=getopt(sys.argv[1:],'C:P:p:w:d:s:N:l')
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
    elif k=='-N':
        n_rare=int(v)

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

data_bins=[[] for unused_ in xrange(n_bins)]


all_data, labelset=load_data(args[0])
print labelset.words

fc=FCombo(2)

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

def get_conn(data):
    for k in data:
        if k.startswith('CS='):
            return k
    return None

class Counts(defaultdict):
    def __init__(self,tp=int):
        defaultdict.__init__(self,tp)
    def __add__(self, other):
        a=Counts()
        a.update(self)
        for k,v in other.iteritems():
            a[k]+=v
    def __iadd__(self,other):
        for k,v in other.iteritems():
            self[k]+=v
        return self

class Sets(defaultdict):
    def __init__(self,tp=set):
        defaultdict.__init__(self,tp)
    def update(self,other):
        for k,v in other.iteritems():
            self[k].update(v)

# compute the training frequencies and label set for each fold
conn_freqs0=[Counts() for unused_ in xrange(n_bins)]
conn_labels0=[Sets() for unused_ in xrange(n_bins)]
for bin_nr,data,label in all_data:
    conn=get_conn(data)
    conn_freqs0[bin_nr][conn]+=1
    conn_labels0[bin_nr][conn].update(label)
conn_freqs=[Counts() for unused_ in xrange(n_bins)]
conn_labels=[Sets() for unused_ in xrange(n_bins)]
training_data=[{None:[]} for unused_ in xrange(n_bins)]
for i in xrange(n_bins):
    for j in xrange(n_bins):
        if i!=j:
            conn_freqs[i]+=conn_freqs0[j]
            conn_labels[i].update(conn_labels0[j])
    for k,v in conn_freqs[i].iteritems():
        if v<n_rare:
            del conn_labels[i][k]
        if v>=n_rare_c:
            training_data[i][k]=[]
print conn_labels[0]

for bin_nr,data,label in all_data:
    correct_all=[[] for unused_ in xrange(n_bins)]
    incorrect_all=[[] for unused_ in xrange(n_bins)]
    conn=get_conn(data)
    ## label  == list of gold labels
    ## label1 == proposed label
    ## clabels == series of labels for proposed
    for label1,clabel in izip(labelset.words,labelparts):
        seen=False
        wanted=False
        for lbl in label:
            if lbl==label1:
                wanted=True
                seen=True
                break
            elif label1.startswith(lbl):
                seen=True
        vec=None
        for i in xrange(n_bins):
            if i==bin_nr: continue
            if conn not in conn_labels[i] or label1 in conn_labels[i][conn]:
                if vec is None:
                    vec=fc(mkdata(data),labels=clabel)
                if wanted:
                    correct_all[i].append(vec)
                elif not seen:
                    incorrect_all[i].append(vec)
    for i,correct,incorrect in izip(xrange(n_bins),correct_all,incorrect_all):
        if i==bin_nr:
            assert len(correct)==0
            assert len(incorrect)==0
            continue
        if correct and incorrect:
            data=training_data[i]
            if conn in data:
                data[conn].append((correct,incorrect))
            else:
                data[None].append((correct,incorrect))
            ##data_bins[i].append((correct,incorrect))
fc.dict.growing=False

def make_fold_classifier(fold_no):
    all_cls={}
    for k,fold_train in training_data[fold_no].iteritems():
        print >>sys.stderr, k, len(fold_train)
        if len(fold_train)>0:
            x=me_opt.train_me_sparse(fold_train,fc.dict)
            all_cls[k]=x
    return all_cls

def classify(dat):
    bin_nr,data,label=dat
    conn=get_conn(data)
    check_all=(conn not in conn_labels[bin_nr])
    if not check_all:
        wanted_labels=conn_labels[bin_nr][conn]
    best=None
    best_score=-1000
    if conn in classifiers[bin_nr]:
        cls=classifiers[bin_nr][conn]
    else:
        cls=classifiers[bin_nr][None]
    for label1,clabel in izip(labelset.words,labelparts):
        if check_all or label1 in wanted_labels:
            score=fc(mkdata(data),labels=clabel).dotFull(cls)
            if score > best_score:
                best=label1
                best_score=score
    return best

classifiers=make_mapper()(make_fold_classifier,xrange(n_bins))
cleanup()

#if weights_fname is not None:
#    print_weights(weights_fname,fc,classifiers)

stats=make_stats(all_data,
                 make_mapper(True)(classify,all_data),
                 labelset, lenient,
                 predictions_fname,
                 stats_fname)
if max_depth is None:
    max_depth=max([len(lbl.split('.')) for lbl in labelset.words])
for d in xrange(1,max_depth+1):
    print_eval(stats,labelset,d)
