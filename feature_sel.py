import sys
from collections import defaultdict
from itertools import izip
import numpy
from dist_sim import sparsmat

__doc__='''
This module does feature selection and more exotic
functionality in addition to fcombs feature combination
mechanism.

The feature selection works by first creating a sparse
vector representation of the data (without combination),
then calculating statistics and (for each part vector)
creating a mask of used features.
'''

def example_vectors(data):
    '''
    creates per-feature and per-label vectors
    that describe which examples contain them.
    '''
    label_dict=defaultdict(sparsmat.VecD1)
    vecs_a=[[] for i in xrange(len(data[0][0]))]
    for i,(vec0_a, label) in enumerate(data):
        for vec0,vecs in izip(vec0_a, vecs_a):
            vecs.append(vec0)
        for lbl in label:
            label_dict[lbl].add_count(i,1)
    by_feature=[sparsmat.CSRMatrixD().fromVectors(vecs).transpose() for vecs in vecs_a]
    by_label=[x.to_sparse() for x in label_dict.values()]
    return by_label, by_feature


def feat_chi2(n_ab,n_a,n_b,N):
    '''
    Pearsons X2 statistic
    '''
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

def feat_pmi(n_ab,n_a,n_b,N):
    '''
    Pointwise mutual information criterion
    '''
    if n_a==0:
        return 0.0
    if n_b==0:
        return 0.0
    quot=(n_ab*float(N))/(float(n_a)*float(n_b))
    if quot<1.0:
        return 0.0
    return numpy.log(quot)

def feat_f1(n_ab,n_a,n_b,N):
    if n_a==0:
        return 0.0
    if n_b==0:
        return 0.0
    f_ab=float(n_ab)
    prec=f_ab/n_a
    recl=f_ab/n_b
    if prec==0: return 0.0
    return 2*prec*recl/(prec+recl)

def feat_f18(n_ab,n_a,n_b,N):
    if n_a==0:
        return 0.0
    if n_b==0:
        return 0.0
    f_ab=float(n_ab)
    prec=f_ab/n_a
    recl=f_ab/n_b
    if prec==0: return 0.0
    return 1.125*prec*recl/(0.125*prec+recl)

def feat_f8(n_ab,n_a,n_b,N):
    if n_a==0:
        return 0.0
    if n_b==0:
        return 0.0
    f_ab=float(n_ab)
    prec=f_ab/n_a
    recl=f_ab/n_b
    if prec==0: return 0.0
    return 9*prec*recl/(8.0*prec+recl)

def feat_unsup(n_ab,n_a,n_b,N):
    '''
    unsupervised feature selection based on p_a only
    '''
    if n_a<5 or n_a==N:
        return 0.0
    p_a=float(n_a)/N
    return p_a*(1.0-p_a)

def do_fs_comb(data,fc,feat_sizes,feat_sel_method=feat_chi2):
    '''
    Computes a (feature selection and combination) transform based on labeled data.
    :param data: pairs of feature vectors (as list of sparse vectors) and labelings
    :param fc: a feature combinator (which provides the feature dictionary)
    :param feat_sizes: the feature set sizes for each part, 0 (all features) or -1 (no features)
    :param feat_sel_method: the statistic to use for feature selection
    '''
    n_max=0
    label_vecs, feature_vecs_a=example_vectors(data)
    N=len(data)
    mask=[]
    for j,feature_vecs in enumerate(feature_vecs_a):
        if j<len(feat_sizes):
            n_max=feat_sizes[j]
        if n_max>0:
            all_vals=numpy.zeros(len(fc.dict_aux))
            for (k,fvec) in enumerate(feature_vecs):
                best_val=0.0
                fvec_len=len(fvec)
                if fvec_len<2: continue
                for lbl_vec in label_vecs:
                    lbl_len=len(lbl_vec)
                    val=feat_sel_method(fvec.count_intersection(lbl_vec),fvec_len,lbl_len,N)
                    if val>best_val:
                        best_val=val
                all_vals[k]=best_val
            ordering=numpy.argsort(all_vals)
            for k in ordering[-3:]:
                print >>sys.stderr, "Feature %s value %f"%(fc.dict_aux.get_sym(k),
                                                               all_vals[k])
            if len(ordering)>n_max:
                print >>sys.stderr,"cutoff[%d] = %f"%(j,all_vals[ordering[-n_max]])
                mask.append((all_vals >= all_vals[ordering[-n_max]]))
            else:
                mask.append(None)
        elif n_max==0:
            print >>sys.stderr, "Use all features[%d]"%(j,)
            mask.append(None)
        elif n_max==-1:
            print >>sys.stderr, "Use no features[%d]"%(j,)
            mask.append(numpy.zeros(len(fc.dict_aux),'?'))
    def munge_fn(vec0):
        return fc.munge_vec(vec0,mask)
    return munge_fn

def do_custom_comb(data,fc,feat_sizes):
    '''
    Computes a (feature selection and combination) transform based on labeled data.
    :param data: pairs of feature vectors (as list of sparse vectors) and labelings
    :param fc: a feature combinator (which provides the feature dictionary)
    :param feat_sizes: the feature set sizes for each part, 0 (all features) or -1 (no features)
    :param feat_sel_method: the statistic to use for feature selection
    '''
    n_max=0
    label_vecs, feature_vecs_a=example_vectors(data)
    N=len(data)
    mask=[]
    for j,feature_vecs in enumerate(feature_vecs_a):
        if j<len(feat_sizes):
            n_max=feat_sizes[j]
        if j==3:
            feat_sel_method=feat_f1
        else:
            feat_sel_method=feat_pmi
        if n_max>0:
            all_vals=numpy.zeros(len(fc.dict_aux))
            for (k,fvec) in enumerate(feature_vecs):
                best_val=0.0
                fvec_len=len(fvec)
                if fvec_len<2: continue
                for lbl_vec in label_vecs:
                    lbl_len=len(lbl_vec)
                    val=feat_sel_method(fvec.count_intersection(lbl_vec),fvec_len,lbl_len,N)
                    if val>best_val:
                        best_val=val
                all_vals[k]=best_val
            ordering=numpy.argsort(all_vals)
            for k in ordering[-3:]:
                print >>sys.stderr, "Feature %s value %f"%(fc.dict_aux.get_sym(k),
                                                               all_vals[k])
            if len(ordering)>n_max:
                print >>sys.stderr,"cutoff[%d] = %f"%(j,all_vals[ordering[-n_max]])
                mask.append((all_vals >= all_vals[ordering[-n_max]]))
            else:
                mask.append(None)
        elif n_max==0:
            print >>sys.stderr, "Use all features[%d]"%(j,)
            mask.append(None)
        elif n_max==-1:
            print >>sys.stderr, "Use no features[%d]"%(j,)
            mask.append(numpy.zeros(len(fc.dict_aux),'?'))
    def munge_fn(vec0):
        return fc.munge_vec_2(vec0,mask,[2,2,2,1,1])
    return munge_fn

def do_custom_comb_2(data,fc,feat_sizes,feat_sel_method=None):
    '''
    Computes a (feature selection and combination) transform based on labeled data.
    :param data: pairs of feature vectors (as list of sparse vectors) and labelings
    :param fc: a feature combinator (which provides the feature dictionary)
    :param feat_sizes: the feature set sizes for each part, 0 (all features) or -1 (no features)
    :param feat_sel_method: the statistic to use for feature selection
    '''
    if feat_sel_method is None:
        feat_sel_method=feat_f1
    n_max=0
    label_vecs, feature_vecs_a=example_vectors(data)
    N=len(data)
    mask=[]
    for j,feature_vecs in enumerate(feature_vecs_a):
        if j<len(feat_sizes):
            n_max=feat_sizes[j]
        if n_max>0:
            all_vals=numpy.zeros(len(fc.dict_aux))
            for (k,fvec) in enumerate(feature_vecs):
                best_val=0.0
                fvec_len=len(fvec)
                if fvec_len<2: continue
                for lbl_vec in label_vecs:
                    lbl_len=len(lbl_vec)
                    val=feat_sel_method(fvec.count_intersection(lbl_vec),fvec_len,lbl_len,N)
                    if val>best_val:
                        best_val=val
                all_vals[k]=best_val
            ordering=numpy.argsort(all_vals)
            for k in ordering[-3:]:
                print >>sys.stderr, "Feature %s value %f"%(fc.dict_aux.get_sym(k),
                                                               all_vals[k])
            if len(ordering)>n_max:
                print >>sys.stderr,"cutoff[%d] = %f"%(j,all_vals[ordering[-n_max]])
                mask.append((all_vals >= all_vals[ordering[-n_max]]))
            else:
                mask.append(None)
        elif n_max==0:
            print >>sys.stderr, "Use all features[%d]"%(j,)
            mask.append(None)
        elif n_max==-1:
            print >>sys.stderr, "Use no features[%d]"%(j,)
            mask.append(numpy.zeros(len(fc.dict_aux),'?'))
    def munge_fn(vec0):
        return fc.munge_vec_2(vec0,mask,[2,1,1,1,1])
    return munge_fn
