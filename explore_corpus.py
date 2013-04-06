from annodb import schema
from cStringIO import StringIO
from werkzeug.utils import escape
from werkzeug.exceptions import NotFound, Forbidden, HTTPException
import json
import sys
import re
from collections import defaultdict
from webapp_admin import render_template, render_template_nocache, \
     redirect, Response, ADMINS
from annodb.corpora import allowed_corpora_nologin, corpus_sattr, corpus_d_sattr, corpus_urls

def escape_uni(s):
    return escape(s).encode('ISO-8859-1','xmlcharrefreplace')

def render_sentence(request,sent_no):
    db=request.corpus
    tueba_corpus=db.corpus
    sno=int(sent_no)-1
    words=db.words
    sents=db.sentences
    texts=tueba_corpus.attribute(corpus_sattr.get(db.corpus_name,'text_id'),'s')
    texts_d=tueba_corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
    max_sent=len(sents)
    start,end=sents[sno][:2]
    tokens=[]
    for i in xrange(start,end+1):
        tokens.append(words[i].decode('ISO-8859-1'))
    t_id=texts.cpos2struc(end-1)
    t_id_d=texts_d.cpos2struc(end-1)
    unused_start,unused_end,t_attrs=texts[t_id]
    if db.corpus_name in corpus_urls:
        text_url=corpus_urls[db.corpus_name](t_attrs,db.corpus_name)
    else:
        text_url='#'
    parses=db.get_parses(sno)
    alignments=db.get_alignments(sno)
    trees_out=StringIO()
    parses_html=''
    response=render_template('sentence.tmpl',
                             sent_id=sno+1,
                             sent_text=' '.join(tokens),
                             parses_html=parses_html,
                             text_id=t_attrs, text_url=text_url,
                             prev_sent='/pycwb/sentence/%d'%(sno,),
                             next_sent='/pycwb/sentence/%d'%(sno+2,),
                             disc_id=t_id_d,
                             corpus_name=request.corpus.corpus_name,
                             has_gold=False)
    request.set_corpus_cookie(response)
    return response

def render_search(request,word):
    db=request.corpus
    tueba_corpus=db.corpus
    print >>sys.stderr, repr(tueba_corpus)
    words=tueba_corpus.attribute("word","p")
    sents=tueba_corpus.attribute("s",'s')
    matches=[]
    try:
        idlist=words.find(word)
        message='%d Treffer.'%(len(idlist),)
        for k in idlist:
            sno=sents.cpos2struc(k)
            tokens=[]
            start,end=sents[sno][:2]
            for i in xrange(start,end+1):
                w=words[i].decode('ISO-8859-1')
                if i==k:
                    tokens.append(u'<b>%s</b>'%(escape(w),))
                else:
                    tokens.append(escape(w))
            matches.append((sno+1, ' '.join(tokens)))
    except KeyError:
        message='Nichts gefunden.'
    return render_template('matches.tmpl',
                           word=escape(word.decode('ISO-8859-15')),
                           matches=matches,
                           message=message)


def find_sent(request):
    #web.header('Content-Type','text/html;charset=UTF-8')
    sno=request.args.get('sent_no') or request.form.get('sent_no')
    if sno:
        return render_sentence(request,sno)
    else:
        return redirect('/pycwb')

def find_word(request):
    word=request.args.get('w') or request.form.get('w')
    if word:
        return render_search(request,word.encode('ISO-8859-15'))
    else:
        return redirect('/pycwb')

def get_words(request):
    word = request.args.get('term')
    if not word or len(word) < 2:
        return Response('')
    else:
        word = word.encode('ISO-8859-15').replace('.', '\\.')
    db = request.corpus
    ws = db.words
    wdict = db.words.getDictionary()
    result = [[w.decode('ISO-8859-15'), ws.frequency(w)] for w in wdict.expand_pattern(word + '.*')]
    result.sort(key=lambda x:-x[1])
    return Response(json.dumps(result[:10]), mimetype='text/javascript')

