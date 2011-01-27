import sys
import numpy
import json
import codecs
from alphabet import PythonAlphabet
from itertools import izip

__all__=['mkdata','shrink_to','load_data','make_stats',
         'print_weights','print_eval','n_bins','add_options_common']

def add_options_common(oparse):
    oparse.add_option('-w', dest='weights_fname')
    oparse.add_option('-p', dest='predictions_fname', help='File for predictions')
    oparse.add_option('-s', dest='stats_fname', help='File for evaluation statistics')
    oparse.add_option('-R', action='store_true',
                      dest='reassign_folds')
    oparse.add_option('-d', action='store', type='int',
                      dest='max_depth')
    oparse.add_option('-P', type='int',
                      dest='n_processors',default=1)
    oparse.add_option('--subsample', action='store', type='float',
                      dest='subsample', default=1.0)
    oparse.add_option('--tag',dest='assigned_tag')
    oparse.add_option('--rand-seed',dest='seed',default=None)
    oparse.add_option('--cutoff',dest='cutoff', type='int',
                      default=1)
    oparse.add_option('--degree',dest='degree', type='int',
                      default=2, help='feature expansion degree')

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

n_bins=10

def load_data(fname, opts):
    reassign_folds=opts.reassign_folds
    max_depth=opts.max_depth
    all_data=[]
    line_no=0
    labelset=PythonAlphabet()
    for l in file(fname):
        bin_nr,data,label,unused_span=json.loads(l)
        if reassign_folds:
            bin_nr=line_no%n_bins
        new_label=[]
        for lbl in label:
            if max_depth is not None:
                lbl=shrink_to(lbl,max_depth)
            labelset[lbl]
            new_label.append(lbl)
        all_data.append((bin_nr,data,new_label))
        line_no+=1
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
    f_weights=codecs.open(fname,'w','ISO-8859-15')
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
