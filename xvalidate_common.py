import sys
import numpy
import json
from alphabet import PythonAlphabet
from itertools import izip

__all__=['mkdata','shrink_to','load_data','make_stats',
         'print_weights','print_eval']

def mkdata(feats):
    lst=[]
    for f in feats:
        if isinstance(f,basestring):
            lst.append((f,1.0))
        else:
            lst.append(f)
    return lst

def shrink_to(lbl,d):
    parts=lbl.split('.')
    if len(parts)>d:
        lbl='.'.join(parts[:d])
    return lbl

def load_data(fname, max_depth=None):
    all_data=[]
    labelset=PythonAlphabet()
    for l in file(fname):
        bin_nr,data,label,unused_span=json.loads(l)
        new_label=[]
        for lbl in label:
            if max_depth is not None:
                lbl=shrink_to(lbl,max_depth)
            labelset[lbl]
            new_label.append(lbl)
        all_data.append((bin_nr,data,new_label))
    labelset.growing=False
    return all_data, labelset


def make_stats(data,classifications,
               labelset,
               lenient=True,
               predictions_fname=None,
               stats_fname=None):
    N=len(labelset)
    stats=numpy.zeros([N,N],'d')
    if predictions_fname is not None:
        f_predict=file(predictions_fname,'w')
    for (bin_nr,data,label),best in izip(data,classifications):
        if predictions_fname is not None:
            print >>f_predict,best
        if best in label:
            lbl=best
            #if lbl!=label[0]:
            #    print "Choosing %s for %s"%(lbl,label[0])
        elif lenient and len(label)==1 and best.startswith(label[0]):
            lbl=best
        else:
            lbl=label[0]
        stats[labelset[best],labelset[lbl]]+=1.0
    if predictions_fname is not None:
        f_predict.close()
    if stats_fname is not None:
        import cPickle
        f_stats=file(stats_fname,'w')
        cPickle.dump([labelset,stats],f_stats,-1)
        f_stats.close()
    return stats

def print_weights(fname,fc,classifiers,epsilon=1e-4):
    f_weights=file(fname,'w')
    all_feats=[]
    for feat,ws in izip(fc.dict.words,izip(*classifiers)):
        aws=numpy.array(ws)
        if numpy.abs(aws).max()>epsilon:
            all_feats.append((feat,aws.mean(),aws.std()))
    all_feats.sort(key=lambda x:-abs(x[1]))
    for x in all_feats:
        print >>f_weights,"%-16s %.3f %.3f"%(x[0],x[1],x[2])
    f_weights.close()


def print_eval(stats,labelset,d):
    print >>sys.stderr, "*** for d=%d ***"%(d,)
    labels_d=numpy.array([shrink_to(lbl,d) for lbl in labelset.words])
    #print >>sys.stderr, labels_d
    all_correct=0.0
    for label1 in sorted(set(labels_d)):
        correct=(labels_d==label1)
        TP=stats[correct][:,correct].sum()
        all_correct+=TP
        SP=stats[correct,:].sum()
        GP=stats[:,correct].sum()
        prec=TP/max(1.0,SP)
        recl=TP/max(1.0,GP)
        if SP>0 or GP>0:
            print >>sys.stderr, "%-16s Prec=%.3f(%d/%d) Recl=%.3f(%d/%d) F=%.3f"%(label1,
                                                                                  prec,TP,SP,
                                                                                  recl,TP,GP,
                                                                                  2*prec*recl/(prec+recl))
    acc=all_correct/stats.sum()
    print >>sys.stderr, "Accuracy=%.3f(%d/%d)"%(acc,all_correct,stats.sum())

def get_accuracy(stats,labelset,d):
    labels_d=numpy.array([shrink_to(lbl,d) for lbl in labelset.words])
    all_correct=0.0
    for label1 in sorted(set(labels_d)):
        correct=(labels_d==label1)
        TP=stats[correct][:,correct].sum()
        all_correct+=TP
    acc=all_correct/stats.sum()
    return acc
