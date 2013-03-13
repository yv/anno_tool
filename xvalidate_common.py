import sys
import numpy
import json
import codecs
from dist_sim.fcomb import Multipart
from alphabet import PythonAlphabet
from itertools import izip

__all__=['shrink_to','load_data','load_ranking_data',
         'load_data_spans','load_aux','make_stats',
         'print_weights','print_weights_2','print_eval','n_bins',
         'add_options_common',
         'object_hook','PrettyFloat']

class PrettyFloat(float):
    def __repr__(self):
        return '%.3f'%(self,)

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
    oparse.add_option('--train-model', dest='train_model', default=None)

def shrink_to(lbl,d):
    parts=lbl.split('.')
    if len(parts)>d:
        lbl='.'.join(parts[:d])
    return lbl

n_bins=10

def object_hook(o):
    if '_type' in o:
        tp=o['_type']
        if tp=='multipart':
            obj=Multipart(o['parts'])
            if 'trees' in o:
                for d in o['trees']:
                    obj.add_tree(d)
            return obj
    return o

def load_data(fname, opts):
    reassign_folds=getattr(opts,'reassign_folds',True)
    max_depth=opts.max_depth
    all_data=[]
    line_no=0
    labelset=PythonAlphabet()
    for l in file(fname):
        bin_nr,data,label,unused_span=json.loads(l, object_hook=object_hook)
        if reassign_folds:
            bin_nr=line_no%n_bins
        new_label=[]
        if label in [None, True, False]:
            new_label=label
        else:
            for lbl in label:
                if max_depth is not None:
                    lbl=shrink_to(lbl,max_depth)
                labelset[lbl]
                new_label.append(lbl)
        all_data.append((bin_nr,data,new_label))
        line_no+=1
    labelset.growing=False
    return all_data, labelset

def load_ranking_data(fname, opts):
    reassign_folds=getattr(opts,'reassign_folds',True)
    max_depth=opts.max_depth
    all_data=[]
    line_no=0
    for l in file(fname):
        bin_nr,data,unused_span=json.loads(l, object_hook=object_hook)
        if reassign_folds:
            bin_nr=line_no%n_bins
        all_data.append((bin_nr,data,None))
        line_no+=1
    return all_data

def load_data_spans(fname, opts):
    reassign_folds=getattr(opts,'reassign_folds',True)
    max_depth=opts.max_depth
    all_data=[]
    line_no=0
    labelset=PythonAlphabet()
    for l in file(fname):
        bin_nr,data,label,span=json.loads(l, object_hook=object_hook)
        if reassign_folds:
            bin_nr=line_no%n_bins
        new_label=[]
        if label in [None, True, False]:
            new_label=label
        else:
            for lbl in label:
                if max_depth is not None:
                    lbl=shrink_to(lbl,max_depth)
                labelset[lbl]
                new_label.append(lbl)
        all_data.append((bin_nr,data,new_label,span))
        line_no+=1
    labelset.growing=False
    return all_data, labelset

def make_spans(span):
    spans=[(span[0],span[1]+1,"<b>","</b>")]
    for name,start,end in span[2:]:
        spans.append((start,end,"[<sub>%s</sub>"%(name,),"<sub>%s</sub>]"%(name,)))
    return spans

def load_aux(fname):
    all_labels=[]
    for l in file(fname):
        bin_nr,data,label,auxlabel=json.loads(l, object_hook=object_hook)
        all_labels.append(auxlabel)
    return all_labels


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
    for feat,ws in izip(fc.dict,izip(*classifiers)):
        aws=numpy.array(ws)
        if numpy.abs(aws).max()>epsilon:
            all_feats.append((feat,aws.mean(),aws.std()))
    all_feats.sort(key=lambda x:-abs(x[1]))
    for x in all_feats:
        print >>f_weights,"%-16s %.3f %.3f"%(x[0],x[1],x[2])
    f_weights.close()

def print_weights_2(fname,wmaps):
    f_weights=codecs.open(fname,'w','ISO-8859-15')
    all_feat_names=set()
    for wmap in wmaps:
        all_feat_names.update(wmap.iterkeys())
    all_feats=[]
    for feat in all_feat_names:
        aws=numpy.array([wmap.get(feat,0.0) for wmap in wmaps])
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
