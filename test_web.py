from annodb import schema
from cStringIO import StringIO
from web_stuff import render_template, redirect, Response
from werkzeug.utils import escape
from werkzeug.exceptions import NotFound, Forbidden, HTTPException
import json
import pytree.csstree as csstree
import pytree.export as export
import sys
from collections import defaultdict

def compute_url(text_id):
    if text_id.startswith('wsj'):
        return '#'
    year=text_id[1:3]
    month=text_id[3:5]
    day=text_id[5:7]
    artno=int(text_id[8:])
    return 'http://tintoretto.sfb.uni-tuebingen.de/taz/19%s/%s/%s/art%03d.htm'%(year,month,day,artno)

def render_sentence(request,sent_no):
    db=request.corpus
    tueba_corpus=db.corpus
    sno=int(sent_no)-1
    words=tueba_corpus.attribute("word",'p')
    sents=tueba_corpus.attribute("s",'s')
    texts=tueba_corpus.attribute("text_id",'s')
    max_sent=len(sents)
    start,end,sent_attrs=sents[sno]
    tokens=[]
    for i in xrange(start,end+1):
        tokens.append(words[i].decode('ISO-8859-1'))
    t_id=texts.cpos2struc(end-1)
    unused_start,unused_end,t_attrs=texts[t_id]
    text_url=compute_url(t_attrs)
    parses=db.get_parses(sno)
    trees_out=StringIO()
    names_parses=sorted([k for k in parses.iterkeys() if k!='_id'])
    annotations=db.find_annotations([start,end],'*gold*')
    if names_parses or annotations:
        print >>trees_out,'<div id="parses-tabs">'
        print >>trees_out,'<ul>'
        for k in names_parses:
            print >>trees_out,'<li><a href="#parses-%s">%s (parse)</a></li>'%(k,k)
        levels=defaultdict(StringIO)
        for anno in annotations:
            level=anno['level']
            schema.schemas[level].make_display(anno,db,levels[level],None)
        names=sorted(levels.iterkeys())
        for k in names:
            print >>trees_out,'<li><a href="#level-tabs-%s">%s</a></li>'%(k,k)
        print >>trees_out,'</ul>'
        for k in names_parses:
            v=parses[k]
            print >>trees_out,'<div id="parses-%s">'%(k,)
            #trees_out.write('<b>%s</b> <a href="javascript:$(\'tree:%s\').toggle()">[show]</a><br/>\n'%(k,k))
            t=export.from_json(v)
            csstree.write_html(t,trees_out,_id='tree-'+k)
            print >>trees_out,'</div>'
        for k in names: 
            print >>trees_out,'<div id="level-tabs-%s">'%(k,)
            trees_out.write(''.join(levels[k].getvalue()))
            print >>trees_out,"</div>"
        print >>trees_out,'</div>'
        parses_html=trees_out.getvalue().decode('ISO-8859-15')
    else:
        parses_html=''
    return render_template('sentence.tmpl',
                           sent_id=sno+1,
                           sent_text=' '.join(tokens),
                           parses_html=parses_html,
                           text_id=t_attrs, text_url=text_url,
                           prev_sent='/pycwb/sentence/%d'%(sno,),
                           next_sent='/pycwb/sentence/%d'%(sno+2,),
                           disc_id=t_id)


def render_discourse(request,disc_no):
    db=request.corpus
    corpus=db.corpus
    t_id=int(disc_no)
    doc=db.get_discourse(t_id,request.user)
    texts=corpus.attribute("text_id",'s')
    sents=corpus.attribute("s",'s')
    start,end,text_attrs=texts[t_id]
    sent_id=sents.cpos2struc(start)
    return render_template('discourse.html',
                           disc_id=disc_no,
                           sent_id=sent_id,
                           sentences=json.dumps(doc['sentences']),
                           edus=json.dumps(doc['edus']),
                           tokens=json.dumps(doc['tokens']),
                           indent=json.dumps(doc['indent']),
                           relations=json.dumps(doc.get('relations','')),
                           topics=json.dumps(doc.get('topics',[])))

def list_discourse(request):
    db=request.corpus
    words=db.words
    text_ids=db.corpus.attribute('text_id','s')
    results=db.db.discourse.find({'_user':request.user})
    doc_lst=[]
    for r in results:
        try:
            docid=int(r['_docno'])
        except KeyError:
            pass
        else:
            txt0=text_ids[docid]
            txt="%s: %s"%(txt0[2],' '.join(words[txt0[0]:txt0[0]+5]))
            doc_lst.append((request.user,r['_docno'],txt.decode('ISO-8859-15')))
    return render_template('discourse_list.html',
                           results=doc_lst)

def save_discourse(request,disc_no):
    db=request.corpus
    t_id=int(disc_no)
    if not request.user:
        raise Forbidden('must be logged in')
    doc=db.get_discourse(t_id,request.user)
    if request.method=='POST':
        stuff=json.load(request.stream)
        try:
            for k,v in stuff.iteritems():
                if k[0]=='_': continue
                doc[k]=v
        except HTTPException,e:
            print >>sys.stderr, e
            raise
        else:
            db.save_discourse(doc)
            return Response('Ok')
    else:
        raise NotFound("Only POST allowed")


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
            start,end,sent_attrs=sents[sno]
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

