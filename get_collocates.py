import sys
import simplejson as json
import codecs
from collections import defaultdict
from cStringIO import StringIO
from dist_sim import sparsmat
from annodb.database import get_corpus
from CWB.CL import Corpus
from cqp_util import use_corpus, query_cqp, escape_cqp
from web_stuff import Response, render_template
import malt_wrapper
import semdep

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
            url,url))
        dewac02_db.display_spans([(start,start+1,"<b>","</b>"),
                                  (end,end+1,"<b>","</b>")],buf)
        buf.write('</div>\n')
    return Response(buf.getvalue().decode('ISO-8859-15'),mimetype='text/html')
        
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
