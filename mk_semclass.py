import sys
from itertools import izip
from collections import defaultdict
from alphabet import CPPUniAlphabet
from dist_sim import sparsmat
import optparse
import simplejson as json

sys.path.append('/home/yannickv/proj/pytree')
import wordsenses
import germanet

matrix_names=['adja_nnpl_1',
              'adja_nnsg_1',
              'nnpl_oder_nnpl_0',
              'nnpl_und_nnpl_0',
              'nnpl_oder_nnpl_1',
              'nnpl_und_nnpl_1',
              'ATTR2', 'OBJA0', 'SUBJ0']
              #'dewiki_esa']
              #'GMOD0', 'GMOD2',
              #'PP_in:P0','PP_in:P2']
          
nn_alph=CPPUniAlphabet()
nn_alph.fromfile(file('/gluster/nufa/yannick/TUEPP_vocab_N.txt'))

matrices={}
alphabets={}
clusters={}
for fname in matrix_names:
    f_in=file('/gluster/nufa/yannick/matrices/N/%s.dat'%(fname,))
    counts=sparsmat.mmapCSR(f_in)
    matrices[fname]=counts.transform_mi_discount()
    alph=CPPUniAlphabet()
    alph.fromfile(file('/gluster/nufa/yannick/matrices/N/%s.alph'%(fname,)))
    alphabets[fname]=alph

taxon_map={}
parts=[]
for l in file('taxon_schema.txt'):
    k=0
    while l[k]=='+': k+=1
    parts=parts[:k]
    relname=l[k:].strip()
    parts.append(relname)
    taxon_map[relname]='.'.join(parts)

def make_features(word,opts):
    result0=[]
    result=[result0]
    if opts.gwn_type=='hyper':
        result0+=gwn_features2(word,opts)
    elif opts.gwn_type=='beginners':
        result0+=gwn_features(word, False)
    elif opts.gwn_type=='beginners2':
        result0+=gwn_features(word, True)
    result0+=cluster_features(word)
    if opts.dist_type!='none':
        result += matrix_features(word,opts)
    return {'_type':'multipart','parts':result}

def cluster_features(word):
    result=[]
    word_u=word.decode('ISO-8859-15')
    for cl, vals in clusters.iteritems():
        if word_u not in vals:
            result.append('cl_%s_NULL'%(cl,))
        else:
            entry=vals[word_u]
            if isinstance(entry,basestring) or isinstance(entry,int):
                result.append('cl_%s_%s'%(cl,vals[word_u]))
            else:
                for k in entry:
                    result.append('cl_%s_%s'%(cl,k))                    
    return result

def gwn_features(word, no_xxx=True):
    result=[]
    synsets=germanet.synsets_for_word(word)
    # if word.endswith('In'):
    #     word2=word[:-2]+'in'
    #     result.append('binnenI')
    #     synsets += germanet.synsets_for_word(word2)
    if not synsets:
        result.append('noGWN')
        return result
    # version A: interesting beginners
    features=set()
    for syn in synsets:
        features.update(germanet.classify_synset(syn))
    result=['GWN_%s'%(feat,) for feat in features]
    if no_xxx:
        for feat in ['person','gruppe','ort','artefakt','tier','ereignis']:
            if feat not in features:
                result.append('GWN_no_%s'%(feat,))
    return result

gwn_feat_names={}
def gwn_feature_name(synset):
    synId=synset.synsetId
    if synId in gwn_feat_names:
        return gwn_feat_names[synId]
    else:
        val='GWN_%s_%s'%(synId,sorted(synset.getWords())[0].word)
        gwn_feat_names[synId]=val
        return val

def gwn_features2(word,opts):
    synsets=germanet.synsets_for_word(word)
    if not synsets and opts.want_supervised:
        return ['noGWN']
    hyper=set()
    for syn in synsets:
        for syn2 in syn.ancestors():
            hyper.add(gwn_feature_name(syn2))
    return list(hyper)

def matrix_features(word,opts):
    def discretize(basename,val,thresholds,result):
        last_tr=0.0
        for i,next_tr in enumerate(thresholds):
            if val>next_tr:
                result.append([basename+chr(65+i),1.0])
            else:
                ival=((val-last_tr)/(next_tr-last_tr))
                result.append([basename+chr(65+i),ival])
                break
            last_tr=next_tr
    try:
        idx=nn_alph[word]
    except KeyError:
        print >>sys.stderr, "Not in list:",word
        return []
    else:
        parts=[]
        for (mat_name,matrix) in matrices.iteritems():
            result=[]
            row=matrix[idx]
            alphF=alphabets[mat_name]
            for k0,v in row:
                k=alphF.get_sym_unicode(k0)
                if opts.dist_type=='simple':
                    result.append(['%s_%s'%(mat_name,k),v])
                if opts.dist_type=='sc':
                    if v>0.5:
                        discretize('%s_%s'%(mat_name,k),v,[2.0,5.0],result)
                else:
                    if '1' in opts.dist_type and v>1.0:
                        result.append('%s_%sA'%(mat_name,k))
                    if '5' in opts.dist_type and v>5.0:
                        result.append('%s_%sB'%(mat_name,k))
            parts.append(result)
        return parts

oparse=optparse.OptionParser()
oparse.add_option('-D', type='choice', dest='dist_type',
                  choices=['none','simple','sc','nosc1','nosc5','nosc15'],
                  default='nosc15')
oparse.add_option('-G', type='choice', dest='gwn_type',
                  choices=['none','beginners','beginners2','hyper'],
                  default='hyper')
oparse.add_option('-C', action='append', dest='clusters')
oparse.add_option('-u', action='store_false', dest='want_supervised')
oparse.set_defaults(clusters=[],want_supervised=True)
opts,args=oparse.parse_args(sys.argv[1:])
for cl in opts.clusters:
    clusters[cl]=json.load(file('/export/local/yannick/clusterings/%s_clusters.json'%(cl,)))
for l in file(args[0]):
    line=l.strip().split()
    if len(line)>1:
        labels=[taxon_map[x] for x in line[1].split('*')]
    else:
        labels=None
    print json.dumps([0,make_features(line[0],opts),labels,line[0].decode('ISO-8859-15')])
