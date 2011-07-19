import sys
from CWB.CL import Corpus
from itertools import izip, islice
from collections import defaultdict
from alphabet import PythonAlphabet, CPPUniAlphabet
from trie_alph import DBAlphabet
from dist_sim import sparsmat
import numpy
from array import array
from gzip import GzipFile
from cStringIO import StringIO
import simplejson as json
import codecs
import fileinput
import cPickle
import os.path
from semdep import get_collocate_sents, DependencyCorpus, lemma_for, \
     dep2paths_sat, filters

min_count=5
min_typecount=5
large_prime=200000033

def PathReader(f, max_len=None):
    line_no=0
    try:
        for l in f:
            path=json.loads(l)
            if max_len is not None:
                if len(path[2])>max_len:
                    continue
            yield path
            line_no+=1
            if (line_no%10000)==0:
                print >>sys.stderr, "\r%d"%(line_no,),
        print >>sys.stderr, "\r%d"%(line_no,)
    except IOError as msg:
        print >>sys.stderr, "IOError:", msg
        raise StopIteration

def CorpusReader(corpus, w1, w2, pos1, pos2,
                 max_len=None, max_sent=None):
    sent_ids=get_collocate_sents(corpus, w1, w2, pos1, pos2)
    print >>sys.stderr, "%d matching sentences."%(len(sent_ids),)
    dep_corpus=DependencyCorpus(corpus)
    for i in sent_ids:
        if max_sent is not None and i>max_sent:
            break
        t=dep_corpus.get_graph(i)
        src_nodes=[j for (j,n) in enumerate(t.terminals)
                   if n.cat in pos1 and corpus.to_unicode(n.lemma) in w1]
        tgt_nodes=[j for (j,n) in enumerate(t.terminals)
                   if n.cat in pos2 and corpus.to_unicode(n.lemma) in w2]
        paths=dep2paths_sat(t, src_nodes, tgt_nodes)
        #print >>sys.stderr, "found %d paths in sentence %d"%(len(paths),i)
        for path in paths:
            if max_len is None or len(path[2])<=max_len:
                yield path

# TBD: need to externalize hashcounts for actual reuse
#      is this really reuse, or something non-helpful?
#      (=> possibility of creating different data)
def TemporaryStorage(r, pair_alph, fname, min_count=5, reuse=False):
    hashcounts=numpy.zeros(large_prime,'i')
    line_no=0
    n_written=0
    if not (reuse and os.path.exists(fname)):
        f_out=file(fname,'w')
        for path in r:
          if len(path[2])>4:
              continue
          w1,w2 = path2words(path)
          try:
              words=u'%s_%s'%(w1,w2)
              pair_alph[words]
          except KeyError:
              continue
          key=path2rel(path)
          rel_idx=hash(key)%large_prime
          hashcounts[rel_idx]+=1
          print >>f_out, json.dumps(path)
          n_written+=1
          if (n_written%10000)==0:
              print >>sys.stderr, "\r%d written"%(n_written,)
        f_out.close()
    f_in=file(fname)
    n_read=0
    n_yielded=0
    for l in f_in:
        path=json.loads(l)
        key=path2rel(path)
        rel_idx=hash(key)%large_prime
        n_read+=1
        if hashcounts[rel_idx]>=min_count:
            yield path
            n_yielded+=1
            if (n_yielded%10000)==0:
                print >>sys.stderr, "\r%d written, %d read, %d found"%(n_written, n_read, n_yielded)
    print >>sys.stderr

def path2words(path):
    word1=path[0]
    word2=path[1]
    if '|' in word1:
        word1=word1[:word1.index('|')]
    if '|' in word2:
        word2=word2[:word2.index('|')]
    return (word1,word2)

def extract_wordpairs(f,f_out):
    w1_alph=PythonAlphabet()
    w2_alph=PythonAlphabet()
    counts=sparsmat.LargeVecI2()
    max_size=1000000
    for path in PathReader(f, max_len=4):
        word1,word2=path2words(path)
        w1_idx=w1_alph[word1]
        w2_idx=w2_alph[word2]
        counts.add_count(w1_idx,w2_idx)
    for w1_idx, w2_idx, count in counts:
        if count>=min_count:
            word1=w1_alph.get_sym(w1_idx)
            word2=w2_alph.get_sym(w2_idx)
            print >>f_out, u"%d\t%s\t%s"%(count,word1,word2)

all_dewac=['DEWAC01','DEWAC02','DEWAC03','DEWAC05','DEWAC06',
          'DEWAC10','DEWAC14','DEWAC15','DEWAC16','DEWAC17']
def make_dewac_reader():
    return fileinput.FileInput(['/gluster/nufa/yannick/paths_sat_%s.json.gz'%(x,)
                                for x in all_dewac],
                               openhook=fileinput.hook_compressed)

def path2rel(path):
    lst=[]
    b_write=lst.append
    p2=path[2]
    for d,rel,lem in p2[:-1]:
        b_write(d)
        b_write(rel)
        b_write(':')
        b_write(lem)
        b_write(':')
    d,rel=p2[-1]
    b_write(d)
    b_write(rel)
    return u''.join(lst)
    
def prefilter_relfreq(f):
    hashcounts=numpy.zeros(large_prime,'i')
    line_no=0
    for path in PathReader(f):
        if len(path[2])>4:
            continue
        rel_idx=hash(path2rel(path))%large_prime
        hashcounts[rel_idx]+=1
    return hashcounts

sat_map={
    'der':'das',
    'die':'das',
    'der|die|das':'das',
    'eine':'ein',
    'ein|eine':'ein'
    }

def get_satellites(path):
    result=['.']
    for r,s in path[3]:
        result.append(u'^%s:%s'%(r,sat_map.get(s,s)))
    for r,s in path[4]:
        result.append(u'/%s:%s'%(r,sat_map.get(s,s)))
    return result

def prefilter_relfreq_sat(f,hc):
    hc2=numpy.zeros(large_prime,'i')
    try:
        for path in PathReader(f,4):
            key=path2rel(path)
            if hc[hash(key)%large_prime]>=min_count:
                sat=get_satellites(path)
                for s in sat:
                    k2=hash(key+s)%large_prime
                    hc2[k2]+=1
    except IOError as msg:
        print >>sys.stderr, "IOError:", msg
        pass
    return hc2

def extract_typecount(f,f_out,hc,hc2, want_db=None):
    if want_db:
        rel_alph=DBAlphabet('/gluster/nufa/yannick/dbalph_%s'%(want_db,))
    else:
        rel_alph=CPPUniAlphabet()
    w1_alph=PythonAlphabet()
    w2_alph=PythonAlphabet()
    counts=sparsmat.LargeVecI3()
    for path in PathReader(f,max_len=4):
        key=path2rel(path)
        if hc[hash(key)%large_prime]>=min_count:
            sat=get_satellites(path)
            word1,word2=path2words(path)
            w1_idx=w1_alph[word1]
            w2_idx=w2_alph[word2]
            for s in sat:
                k2_s=key+s
                if hc2[hash(k2_s)%large_prime]>=min_typecount:
                    rel_idx=rel_alph[key+s]
                    counts.add_count(rel_idx,w1_idx,w2_idx,1)
    print >>sys.stderr, "len(counts)=%d"%(counts.get_size(),)
    typecounts=counts.get_type_counts()
    for rel, count in izip(rel_alph, typecounts):
        if count>=min_typecount:
            print >>f_out, "%d\t%s"%(count,rel)

def create_plassoc(f, fname_out, min_freq=100):
    w1_alph=PythonAlphabet()
    w2_alph=PythonAlphabet()
    counts=sparsmat.LargeVecD2()
    counts_raw=sparsmat.LargeVecI2()
    for path in PathReader(f):
        word1,word2=path2words(path)
        w1_idx=w1_alph[word1]
        w2_idx=w2_alph[word2]
        counts.add_count(w1_idx,w2_idx,1/float(len(path)-1))
        counts_raw.add_count(w1_idx,w2_idx)
    counts_mat=counts_raw.to_csr()
    counts_mi=counts.to_csr().transform_mi()
    marginals_l=counts_mat.left_marginals()
    marginals_r=counts_mat.right_marginals()
    f_out=codecs.open(fname_out,'w','ISO-8859-15')
    for w1_idx,vec in enumerate(counts_mi):
        if marginals_l[w1_idx]>=min_freq:
            for w2_idx, val in vec:
                if marginals_r[w2_idx]>=min_freq:
                    word1=w1_alph.get_sym(w1_idx)
                    word2=w2_alph.get_sym(w2_idx)
                    print >>f_out, u"%f\t%s\t%s"%(val,word1,word2)
    f_out.close()

def gather_training_vectors(pair_alph,
                            rel_alph,
                            r, count_vec=None):
    if count_vec is None:
        count_vec=sparsmat.LargeVecI2()
    for path in r:
        sys.stderr.write('.')
        word1,word2=path2words(path)
        try:
            pair_idx=pair_alph[u'%s_%s'%(word1,word2)]
        except KeyError:
            print repr(u'%s_%s'%(word1,word2))
            continue
        rel=path2rel(path)
        try:
            rel_alph[rel+'.']
        except KeyError:
            continue
        else:
            for s in get_satellites(path):
                try:
                    rel_idx=rel_alph[rel+s]
                except KeyError:
                    continue
                count_vec.add_count(pair_idx,rel_idx,1)
    return count_vec

def write_binned_vectors(classifications,
                        count_mat, rel_alph, f_out):
    n_rels=len(rel_alph)
    marginals=numpy.zeros(n_rels)
    print len(classifications), len(count_mat)
    for cls, vec in izip(classifications,count_mat):
        f_out.write('%+d\t'%(cls,))
        parts=[]
        for k,freq in vec:
            k1=k+1
            marginals[k]+=1
            thr=1
            while thr<=freq and thr<=2048:
                parts.append(k1)
                thr *=2
                k1+=n_rels
        parts.sort()
        f_out.write(' '.join(['%d:1'%(k,) for k in parts]))
        f_out.write('\n')
    print marginals, marginals.sum()

def read_training_pairs(pairs_fname):
    cls=[]
    pair_alph=PythonAlphabet()
    w1=set()
    w2=set()
    for l in codecs.open(pairs_fname,'r','ISO-8859-15'):
        line=l.strip().split()
        cls.append(int(line[0]))
        pair_alph[u'%s_%s'%(line[1],line[2])]
        w1.add(line[1])
        w2.add(line[2])
    pair_alph.growing=False
    return cls, pair_alph, w1, w2

def make_data(pairs_fname, corpus_name, out_fname, pos_filter='NN'):
    cls, pair_alph, w1, w2=read_training_pairs(pairs_fname)
    r0=CorpusReader(Corpus(corpus_name), w1, w2,
                    filters[pos_filter[0]],
                    filters[pos_filter[1]])
    r=TemporaryStorage(r0, pair_alph, '/export/local/yannick/paths.tmp.json')
    rel_alph=CPPUniAlphabet()
    print >>sys.stderr, "get training vectors"
    count_vec=sparsmat.LargeVecI2()
    count_vec=gather_training_vectors(pair_alph, rel_alph, r, count_vec)
    rel_alph.growing=False
    print >>sys.stderr, "len(count_vec)=%d"%(count_vec.get_size(),)
    print >>sys.stderr, "remap for typecount>=5"
    wanted=(count_vec.get_type_counts(1)>=5)
    count_vec2=count_vec.remap(1,wanted)
    rel_alph2=rel_alph.remap(wanted)
    print >>sys.stderr, "%d items remain, len(count_vec2)=%d"%(len(rel_alph2),
                                                               count_vec2.get_size())
    print count_vec2.get_type_counts(1)
    count_mat=count_vec2.to_csr()
    print >>sys.stderr, "write binned"
    write_binned_vectors(cls, count_mat, rel_alph2, file(out_fname+'_vec.txt','w'))
    rel_alph2.tofile(file(out_fname+'_rels.txt','w'))

if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='pairfreq':
        extract_wordpairs(GzipFile(sys.argv[2]),
                          codecs.getwriter('ISO-8859-15')(sys.stdout))
    elif cmd=='pairfreq_all':
        extract_wordpairs(make_dewac_reader(),
                          codecs.getwriter('ISO-8859-15')(sys.stdout))
    elif cmd=='plassoc':
        create_plassoc(GzipFile(sys.argv[2]),sys.argv[3])
    elif cmd=='typecount':
        print >>sys.stderr, "Create relation filter"
        hc=prefilter_relfreq(GzipFile(sys.argv[2]))
        print >>sys.stderr, "Create rel+sat filter"
        hc2=prefilter_relfreq_sat(GzipFile(sys.argv[2]),hc)
        print >>sys.stderr, "Count rel+sat types"
        db_name=None
        if len(sys.argv)>3:
            db_name=sys.argv[3]
        extract_typecount(GzipFile(sys.argv[2]),
                          codecs.getwriter('ISO-8859-15')(sys.stdout),hc,hc2,db_name)
    elif cmd=='make_data':
        if len(sys.argv)>5:
            pos_filter=sys.argv[5]
        else:
            pos_filter='NN'
        make_data(sys.argv[2], sys.argv[3], sys.argv[4], pos_filter)
