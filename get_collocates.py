import sys
import simplejson as json
from cStringIO import StringIO
from dist_sim import sparsmat
from annodb.database import get_corpus
from CWB.CL import Corpus
from cqp_util import use_corpus, query_cqp, escape_cqp
from web_stuff import Response, render_template

def collocate_vector(corpus, word1, wsize=5, pos_re=None):
    il=sparsmat.VecD1()
    lemmas=corpus.attribute('lemma','p')
    sentences=corpus.attribute('s','s')
    pos_attr=corpus.attribute('pos','p')
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

dewac02_db=get_corpus('DEWAC02')
dewac02_corpus=dewac02_db.corpus
cqp=use_corpus('DEWAC02')

def collocates_page(request):
    return render_template('collocates.html')

def get_collocates(request):
    word1=request.args['word1']
    wsize=int(request.args.get('wsize',5))
    lemma_dict=dewac02_corpus.attribute('lemma','p').getDictionary()
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
                      '[lemma="%s"]'%(escape_cqp(word1),),
                      '[lemma="%s"]'%(escape_cqp(word2),),limit=20)
    snippets=[]
    sents=dewac02_db.sentences
    words=dewac02_db.words
    texts=dewac02_db.corpus.attribute('text_id','s')
    buf=StringIO()
    for start,end in results:
        buf.write('<div class="example">')
        text_id=texts.cpos2struc(start)
        url=texts[text_id][2]
        buf.write('<a href="%s">%s</a><br>\n'%(url,url))
        dewac02_db.display_spans([(start,start+1,"<b>","</b>"),
                                  (end,end+1,"<b>","</b>")],buf)
        buf.write('</div>\n')
    return Response(buf.getvalue().decode('ISO-8859-15'),mimetype='text/html')
        

if __name__=='__main__':
    corpus=Corpus(sys.argv[1])
    lemma_dict=corpus.attribute('lemma','p').getDictionary()
    word1=sys.argv[2]
    vec=collocate_vector(corpus,word1, pos_re='VV.*|N.|ADJ.')
    collocates=[]
    for (k_id,v) in vec:
        k=lemma_dict.get_word(k_id)
        collocates.append((k,v))
    collocates.sort(key=lambda x:-x[1])
    for k,v in collocates[:20]:
        print "%s\t%s"%(k,v)

    
