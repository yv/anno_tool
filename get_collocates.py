import sys
import simplejson as json
import codecs
from collections import defaultdict
from cStringIO import StringIO
from dist_sim import sparsmat
from annodb.database import get_corpus
from annodb.corpora import corpus_urls
from CWB.CL import Corpus
from cqp_util import use_corpus, query_cqp, escape_cqp
from web_stuff import Response, render_template
import malt_wrapper
from dist_sim import sparsmat
from alphabet import CPPUniAlphabet
from dist_sim.semkernel import JSDKernel, PolynomialKernel, KPolynomial
import semdep

matrix_names=['adja_nnpl_1',
              'adja_nnsg_1',
              'nnpl_oder_nnpl_0',
              'nnpl_und_nnpl_0',
              'nnpl_oder_nnpl_1',
              'nnpl_und_nnpl_1',
              'ATTR2', 'OBJA0', 'SUBJ0',
              'GMOD0', 'GMOD2',
              'PP_in:P0','PP_in:P2']
nn_alph=CPPUniAlphabet()
nn_alph.fromfile(file('/gluster/nufa/yannick/TUEPP_vocab_N.txt'))

matrices={}
alphabets={}
for fname in matrix_names:
    f_in=file('/gluster/nufa/yannick/matrices/N/%s.dat'%(fname,))
    counts=sparsmat.mmapCSR(f_in)
    matrices[fname]=counts.transform_ll()
    alph=CPPUniAlphabet()
    alph.fromfile(file('/gluster/nufa/yannick/matrices/N/%s.alph'%(fname,)))
    alphabets[fname]=alph

def make_poly_single(n):
    result=[]
    for i in xrange(n):
        lst=[0]*n
        lst[i]=1
        lst.append(1.0/n)
        result.append(tuple(lst))
    return result

kernels=[JSDKernel(matrices['ATTR2']),
         JSDKernel(matrices['OBJA0']),
         JSDKernel(matrices['SUBJ0']),
         JSDKernel(matrices['GMOD0']),
         JSDKernel(matrices['adja_nnpl_1']),
         PolynomialKernel(matrices['nnpl_oder_nnpl_0'],c=0.1,d=2,normalize=True),
         PolynomialKernel(matrices['nnpl_oder_nnpl_1'],c=0.1,d=2,normalize=True),
         PolynomialKernel(matrices['nnpl_und_nnpl_0'],c=0.1,d=2,normalize=True),
         PolynomialKernel(matrices['nnpl_und_nnpl_1'],c=0.1,d=2,normalize=True)]
sim_kernel=KPolynomial(kernels, make_poly_single(len(kernels)))
sim_cache={}

def get_sketch_data(word):
    w_idx=nn_alph[word]
    parts={}
    for (mat_name,matrix) in matrices.iteritems():
        result=[]
        row=matrix[w_idx]
        alphF=alphabets[mat_name]
        for k0,v in row:
            k=alphF.get_sym_unicode(k0)
            result.append((k,v))
        result.sort(key=lambda x:x[1],reverse=True)
        parts[mat_name]=result
    return parts

def sketch_page(request):
    return render_template('sketch.html', matrix_names=json.dumps(matrix_names))

def get_sketch(request):
    word1=request.args['word1'].encode('ISO-8859-15')
    result=get_sketch_data(word1)
    return Response(json.dumps(result),mimetype='text/javascript')

def get_similar(request):
    word1=request.args['word1'].encode('ISO-8859-15')
    result=[]
    for word2,val in similar_words(word1,20):
        result.append([word2.decode('ISO-8859-15')]+get_kernel_values(word1,word2))
    return Response(json.dumps(result),mimetype='text/javascript')

def collocate_vector(corpus, word1, wsize=5, pos_re=None):
    il=sparsmat.VecD1()
    lemmas=corpus.attribute('tb_lemma','p')
    sentences=corpus.attribute('s','s')
    pos_attr=corpus.attribute('rf_pos','p')
    global_count=0.0
    if pos_re is None:
        pos_set=None
    else:
        pos_set=pos_attr.getDictionary().get_matching(pos_re)
    for pos in lemmas.find(word1):
        s_id=sentences.cpos2struc(pos)
        s_start,s_end=sentences[s_id][:2]
        off1=wsize-pos+1
        for i in xrange(max(s_start,pos-wsize),pos):
            if pos_set is None or pos_attr.cpos2id(i) in pos_set:
                w=off1+i
                il.add_count(lemmas.cpos2id(i),w)
                global_count+=w
        off2=wsize+pos+1
        for i in xrange(pos+1,min(s_end+1,pos+wsize+1)):
            if pos_set is None or pos_attr.cpos2id(i) in pos_set:
                w=off2-i
                il.add_count(lemmas.cpos2id(i),w)
                global_count+=w
    vec=il.to_sparse()
    vec/=global_count
    return vec

corpus_name='TUEPP'
dewac02_db=get_corpus(corpus_name)
dewac02_corpus=dewac02_db.corpus
dewac02_dep=semdep.DependencyCorpus(dewac02_corpus)
cqp=use_corpus(corpus_name)
if corpus_name in corpus_urls:
    url_transform=corpus_urls[corpus_name]
    def get_url(text_id):
        return url_transform(text_id,corpus_name)
else:
    def get_url(url):
        return url

def collocates_page(request):
    return render_template('collocates.html', corpus_name=corpus_name)

def get_collocates(request):
    word1=request.args['word1'].encode('ISO-8859-15')
    wsize=int(request.args.get('wsize',5))
    lemma_dict=dewac02_corpus.attribute('tb_lemma','p').getDictionary()
    vec=collocate_vector(dewac02_corpus, word1, wsize, "VV.*|N.|ADJ.")
    collocates=[]
    for (k_id,v) in vec:
        k=lemma_dict.get_word(k_id)
        collocates.append((k,v))
    collocates.sort(key=lambda x:-x[1])
    result=[]
    for k,v in collocates[:60]:
        result.append({'tag':k.decode('ISO-8859-15'),'count':v})
    return Response(json.dumps(result),mimetype='text/javascript')

def get_assoc(cqp,pat1,pat2,max_dist=None,limit=None):
    if limit is None:
        f=list
    else:
        f=lambda x: x[:limit]
    if max_dist is None:
        results=f(query_cqp(cqp,
                          '%s []* %s within 1 s'%(pat1,pat2)))
        results+=f(query_cqp(cqp,
                             '%s []* %s within 1 s'%(pat2,pat1)))
    else:
        results=f(query_cqp(cqp,
                            '%s []{0,%d} %s within 1 s'%(pat1,max_dist,pat2)))
        results+=f(query_cqp(cqp,
                             '%s []{0,%d} %s within 1 s'%(pat2,max_dist,pat1)))
    return results

def collocate_examples(request):
    word1=request.args['word1'].encode('ISO-8859-15')
    word2=request.args['word2'].encode('ISO-8859-15')
    results=get_assoc(cqp,
                      '[tb_lemma="%s"]'%(escape_cqp(word1),),
                      '[tb_lemma="%s"]'%(escape_cqp(word2),),limit=20)
    snippets=[]
    sents=dewac02_db.sentences
    words=dewac02_db.words
    texts=dewac02_db.corpus.attribute('text_id','s')
    buf=StringIO()
    for start,end in results:
        buf.write('<div class="example">')
        text_id=texts.cpos2struc(start)
        sent_no=sents.cpos2struc(start)
        s_start, s_end=sents[sent_no][:2]
        w1_idx=start-s_start
        w2_idx=end-s_start
        url=texts[text_id][2]
        buf.write('<a onclick="loadGraph(%d,%d,%d)">[graph]</a> <a href="%s">%s</a><br>\n'%(
            sent_no, w1_idx, w2_idx,
            get_url(url),url))
        dewac02_db.display_spans([(start,start+1,"<b>","</b>"),
                                  (end,end+1,"<b>","</b>")],buf)
        buf.write('</div>\n')
    return Response(buf.getvalue().decode('ISO-8859-15'),mimetype='text/html')

def similar_words(word1,cutoff=250):
    if cutoff<=250 and word1 in sim_cache:
        return sim_cache[word1][:cutoff]
    k1=nn_alph[word1]
    cands=[]
    for k2 in xrange(len(nn_alph)):
        if k1==k2: continue
        val=sim_kernel.kernel(k1,k2)
        cands.append((val,k2))
    cands.sort(reverse=True)
    cands1=cands[:250]
    sim_cache[word1]=[(nn_alph.get_sym(k),val) for (val,k) in cands1]
    if cutoff is not None:
        cands=cands[:cutoff]
    return [(nn_alph.get_sym(k),val) for (val,k) in cands]

def get_kernel_values(word1,word2):
    i1=nn_alph[word1]
    i2=nn_alph[word2]
    result=[]
    for kern in sim_kernel.kernels:
        result.append(kern.kernel(i1,i2))
    return result

def sentence_graph(request):
    sent_no=int(request.args['sent_id'])
    sent=dewac02_dep[sent_no]
    t=malt_wrapper.sent2tree(sent)
    for i,n in enumerate(t.terminals):
        n.start=i
    semdep.make_semrels(t)
    return Response(json.dumps(semdep.dep2json(t)),mimetype='text/javascript')

def dump_word_graphs(word, fname):
    f_out=codecs.open(fname,'w','UTF-8')
    sentences=dewac02_db.sentences
    lemma_posns=dewac02_corpus.attribute('tb_lemma','p').find(word)
    for pos in lemma_posns:
        sent_no=sentences.cpos2struc(pos)
        t=dewac02_dep.get_graph(sent_no)
        print >>f_out, json.dumps(semdep.dep2json(t))
    f_out.close()

def dump_all():
    for word in ['nehmen','Markt','Eis','handeln','Bann']:
        print word
        dump_word_graphs(word,
                         '/home/yannickv/sources/projects/GraphMining/examples/%s_graphs.json'%(word,))

def dump_paths(word1,word2):
    lemmas=dewac02_db.corpus.attribute('tb_lemma','p')
    sents=dewac02_db.sentences
    results=get_assoc(cqp,
                      '[tb_lemma="%s"]'%(escape_cqp(word1),),
                      '[tb_lemma="%s"]'%(escape_cqp(word2),))
    counts=defaultdict(int)
    for start,end in results:
        sent_no=sents.cpos2struc(start)
        s_start, s_end=sents[sent_no][:2]
        if lemmas[start]==word1:
            idx1=start-s_start
            idx2=end-s_start
        else:
            idx1=end-s_start
            idx2=start-s_start
        t=dewac02_dep.get_graph(sent_no)
        path=semdep.get_path(t,idx1,idx2)
        if path:
            counts['_'.join(path[3])]+=1
    return counts

if __name__=='__main__':
    corpus=Corpus(sys.argv[1])
    lemma_dict=corpus.attribute('tb_lemma','p').getDictionary()
    for l in file(sys.argv[2]):
        word1=l.strip().split()[0]
        vec=collocate_vector(corpus, word1, pos_re='VV.*|N.|ADJ.')
        collocates=[]
        for (k_id,v) in vec:
            k=lemma_dict.get_word(k_id)
            collocates.append((k,v))
        collocates.sort(key=lambda x:-x[1])
        for k,v in collocates[:20]:
            print "%s\t%s\t%s"%(word1,k,v)
