import sys
import simplejson as json
import codecs
from itertools import izip, islice
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
              #'adja_nnsg_1',
              'nnpl_oder_nnpl_0',
              'nnpl_und_nnpl_0',
              'nnpl_oder_nnpl_1',
              'nnpl_und_nnpl_1',
              'ATTR2', 'OBJA0', 'SUBJ0',
              'GMOD0', 'GMOD2']#,
              #'PP_in:P0','PP_in:P2']
nn_alph=CPPUniAlphabet()
nn_alph.fromfile(file('/gluster/nufa/yannick/TUEPP_vocab_N.txt'))

matrices=None
alphabets=None
sim_kernel=None

def get_matrices():
    global matrices
    global alphabets
    global sim_kernel
    if matrices is None:
        matrices={}
        alphabets={}
        for fname in matrix_names:
            f_in=file('/gluster/nufa/yannick/matrices/N/%s.dat'%(fname,))
            counts=sparsmat.mmapCSR(f_in)
            matrices[fname]=counts.transform_ll()
            alph=CPPUniAlphabet()
            alph.fromfile(file('/gluster/nufa/yannick/matrices/N/%s.alph'%(fname,)))
            alphabets[fname]=alph
        kernels=[JSDKernel(matrices[x]) for x in matrix_names]
        sim_kernel=KPolynomial(kernels, make_poly_single(len(kernels)))
    return matrices

def get_sim_kernel():
    if matrices is None:
        get_matrices()
    return sim_kernel

def make_poly_single(n):
    result=[]
    for i in xrange(n):
        lst=[0]*n
        lst[i]=1
        lst.append(1.0/n)
        result.append(tuple(lst))
    return result

def make_poly_cross(n):
    result=[]
    for i in xrange(n):
        for j in xrange(n):
            lst=[0]*n
            lst[i]=1
            lst[j]=1
            lst.append(1.0/(n*n))
            result.append(tuple(lst))
    for i in xrange(n):
        lst=[0]*n
        lst[i]=1
        lst.append(1.0/n)
        result.append(tuple(lst))
    return result
    

sim_cache={}

def get_sketch_data(word):
    w_idx=nn_alph[word]
    parts={}
    for (mat_name,matrix) in get_matrices().iteritems():
        result=[]
        row=matrix[w_idx]
        alphF=alphabets[mat_name]
        for k0,v in row:
            k=alphF.get_sym_unicode(k0)
            result.append((k,v))
        result.sort(key=lambda x:x[1],reverse=True)
        parts[mat_name]=result
    return parts

def get_common_features(idx1, idx2):
    result=[]
    for (mat_name, matrix) in get_matrices().iteritems():
        row=matrix[idx1].min_vals(matrix[idx2])
        alphF=alphabets[mat_name]
        for k0,v in row:
            k=alphF.get_sym_unicode(k0)
            result.append(('%s:%s'%(mat_name,k),v))
    result.sort(key=lambda x:x[1], reverse=True)
    return result

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
    #for k2 in xrange(len(nn_alph)):
    kern=get_sim_kernel().kernel
    for k2 in xrange(7000):
        if k1==k2: continue
        val=kern(k1,k2)
        cands.append((val,k2))
    cands.sort(reverse=True)
    cands1=cands[:250]
    sim_cache[word1]=[(nn_alph.get_sym(k),val) for (val,k) in cands1]
    if cutoff is not None:
        cands=cands[:cutoff]
    return [(nn_alph.get_sym(k),val) for (val,k) in cands]

def all_neighbours(word1,cutoff=10,max_hops=1,result=None):
    if result==None:
        result=defaultdict(lambda:-1)
        result[word1]=max_hops
    for w2,val in similar_words(word1,cutoff):
        if result[w2]<max_hops:
            result[w2]=max_hops
            if max_hops>0:
                #print >>sys.stderr, w2, max_hops
                all_neighbours(w2,cutoff,max_hops-1,result)
    return result

def get_neighbours_simple(word1, sim_cutoff=0.10):
    return [word1]+[w2 for (w2,val) in similar_words(word1) if val>=sim_cutoff]

def get_neighbours_2(word1, cutoff=10):
    cands=similar_words(word1)
    return (cands[cutoff][1], [word1]+[w2 for (w2,val) in cands[:cutoff]])

def colorize(idxs,edge_thr,a=0.9,b=0.0):
    k_vals={}
    neighbours=defaultdict(set)
    kern=get_sim_kernel().kernel
    for i1,idx1 in enumerate(idxs):
        for i2,idx2 in islice(enumerate(idxs),i1+1,None):
            val=kern(idx1,idx2)
            k_vals[(i1,i2)]=val
            if val>edge_thr:
                neighbours[i1].add(i2)
                neighbours[i2].add(i1)
    # helper functions for finding the initial committees
    def score_centrality(i):
        """figure of merit for choosing one node as cluster seed"""
        result=0.0
        for i1 in neighbours[i]:
            for i2 in neighbours[i]:
                if i2>i1:
                    result+=k_vals[(i1,i2)]
            if i<i1:
                result+=k_vals[(i,i1)]
            else:
                result+=k_vals[(i1,i)]
        return result
    def most_central():
        best_idx=None
        best_val=0.0
        for i in neighbours.iterkeys():
            val=score_centrality(i)
            if val>best_val:
                best_val=val
                best_idx=i
        return best_idx
    def get_cluster(i):
        scores=[(k_vals[(i,j)],j) for j in neighbours if i<j]
        scores+=[(k_vals[(j,i)],j) for j in neighbours if j<i]
        scores.sort(reverse=True)
        threshold=scores[0][0]*a+b
        return [i]+[j for (val,j) in scores if val>=threshold]
    def remove_neighbours(newclust):
        for i in newclust:
            del neighbours[i]
        for i in neighbours.keys():
            ns=neighbours[i]
            ns.difference_update(newclust)
            if len(ns)<1:
                del neighbours[i]
    clusters=[]
    centroids=[]
    while neighbours:
        i_new=most_central()
        assert i_new is not None, neighbours
        clust=get_cluster(i_new)
        clusters.append(clust)
        centroids.append(i_new)
        remove_neighbours(clust)
    # helper functions for creating the actual coloring
    def score_cluster(i,clust):
        if i in clust:
            return 1.0
        result=0.0
        for j in clust:
            if i<j:
                result+=k_vals[(i,j)]
            else:
                result+=k_vals[(j,i)]
        return result/len(clust)
    def best_cluster(i):
        best_k=-1
        best_val=0.0
        for (k,clust) in enumerate(clusters):
            val=score_cluster(i,clust)
            if val>best_val:
                best_k=k
                best_val=val
        return best_k
    #print >>sys.stderr, clusters
    return ([best_cluster(i) for i in xrange(len(idxs))],centroids)
                 

def make_similarity_graph(words,sim_cutoff=0.10):
    nodes=[]
    edges=[]
    idxs=[]
    for w in words:
        idxs.append(nn_alph[w])
        nodes.append({'name':w.decode('ISO-8859-15'),'common':[],'want_label':False})
    idx0=idxs[0]
    for (i,idx) in islice(enumerate(idxs),1,None):
        nodes[i]['common']=[x[0] for x in get_common_features(idx0, idx)[:3]]
    (clusters0,centroids0)=colorize(idxs[1:],sim_cutoff,0.6,0.3*sim_cutoff)
    clusters=[1]+[(k+2) for k in clusters0]
    nodes[0]['want_label']=True
    for (n,c) in izip(nodes,clusters):
        n['group']=c
    for i in centroids0:
          nodes[i+1]['want_label']=True
    kern=get_sim_kernel().kernel
    for i1,idx1 in enumerate(idxs):
        for i2,idx2 in enumerate(idxs):
            if idx1>idx2:
                val=kern(idx1,idx2)
                if val>sim_cutoff:
                    edges.append({'source':i1,'target':i2,
                                  'value':val})
    return {'nodes':nodes,'edges':edges}

def get_neighbour_graph(request):
    word1=request.args['word1'].encode('ISO-8859-15')
    cutoff=int(request.args.get('cutoff',10))
    (sim_cutoff,all_words)=get_neighbours_2(word1, cutoff)
    result=make_similarity_graph(all_words,sim_cutoff=sim_cutoff)
    return Response(json.dumps(result),mimetype='text/javascript')

def get_kernel_values(word1,word2):
    i1=nn_alph[word1]
    i2=nn_alph[word2]
    result=[]
    for kern in get_sim_kernel().kernels:
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

def eval_invr(syns, invr_scores):
    score=0.0
    for k in syns:
        score += invr_scores.get(k,0.0)
    return score

if __name__=='__main__':
    if sys.argv[1]=='collocates':
        corpus=Corpus(sys.argv[2])
        lemma_dict=corpus.attribute('tb_lemma','p').getDictionary()
        for l in file(sys.argv[3]):
            word1=l.strip().split()[0]
            vec=collocate_vector(corpus, word1, pos_re='VV.*|N.|ADJ.')
            collocates=[]
            for (k_id,v) in vec:
                k=lemma_dict.get_word(k_id)
                collocates.append((k,v))
            collocates.sort(key=lambda x:-x[1])
            for k,v in collocates[:20]:
                print "%s\t%s\t%s"%(word1,k,v)
    elif sys.argv[1]=='eval':
        for l in file(sys.argv[2]):
            line=l.strip().split('\t')
            word1=line[0]
            invr_scores={}
            for i,(w2,val) in enumerate(similar_words(word1)):
                invr_scores[w2]=1.0/(1.0+i)
            for i in xrange(6,len(line)):
                line[i]=str(eval_invr(line[i].split(','),invr_scores))
            print '\t'.join(line)
