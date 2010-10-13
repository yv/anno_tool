from annodb import schema
from cStringIO import StringIO
from web_stuff import render_template, render_template_nocache, \
     redirect, Response, ADMINS
from werkzeug.utils import escape
from werkzeug.exceptions import NotFound, Forbidden, HTTPException
import json
import pytree.csstree as csstree
import pytree.export as export
import sys
import re
from collections import defaultdict
from annodb.corpora import corpus_sattr, corpus_d_sattr, corpus_urls

def escape_uni(s):
    return escape(s).encode('ISO-8859-1','xmlcharrefreplace')

def write_alignment(align,out):
    words1=align['words1']
    words2=align['words2']
    alignment=set([(x[1],x[0]) for x in align['alignment']])
    print >>out,'<table>'
    print >>out,'<tr><td></td>'
    for w in words1:
        print >>out,'<td>%s</td>'%(escape_uni(w))
    print >>out,'</tr>'
    for i,w2 in enumerate(words2):
        print >>out,'<tr><td>%s</td>'%(escape_uni(w2))
        for j,w in enumerate(words1):
            if (i,j) in alignment:
                print >>out,'<td bgcolor="#0033aa">x</td>'
            else:
                print >>out,'<td>.</td>'
        print >>out,'</tr>'
    print >>out,'</table>'
        

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
    names_parses=sorted([k for k in parses.iterkeys() if k!='_id'])
    names_alignments=sorted([k for k in alignments.iterkeys() if k!='_id'])
    annotations=db.find_annotations([start,end],'*gold*')
    if names_parses or names_alignments or annotations:
        print >>trees_out,'<div id="parses-tabs">'
        print >>trees_out,'<ul>'
        for k in names_parses:
            print >>trees_out,'<li><a href="#parses-%s">%s (parse)</a></li>'%(k,k)
        for k in names_alignments:
            print >>trees_out,'<li><a href="#alignments-%s">%s (align)</a></li>'%(k,k)
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
        for k in names_alignments:
            v=alignments[k]
            print >>trees_out,'<div id="alignments-%s">'%(k,)
            write_alignment(v,trees_out)
            print >>trees_out,'</div>'
        for k in names: 
            print >>trees_out,'<div id="level-tabs-%s">'%(k,)
            trees_out.write(''.join(levels[k].getvalue()))
            print >>trees_out,"</div>"
        print >>trees_out,'</div>'
        parses_html=trees_out.getvalue().decode('ISO-8859-15')
    else:
        parses_html=''
    response=render_template('sentence.tmpl',
                           sent_id=sno+1,
                           sent_text=' '.join(tokens),
                           parses_html=parses_html,
                           text_id=t_attrs, text_url=text_url,
                           prev_sent='/pycwb/sentence/%d'%(sno,),
                           next_sent='/pycwb/sentence/%d'%(sno+2,),
                           disc_id=t_id_d)
    request.set_corpus_cookie(response)
    return response


def render_discourse(request,disc_no):
    db=request.corpus
    corpus=db.corpus
    t_id=int(disc_no)
    doc=db.get_discourse(t_id,request.user)
    texts=corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
    sents=corpus.attribute("s",'s')
    start,end,text_attrs=texts[t_id]
    sent_id=sents.cpos2struc(start)
    response=render_template_nocache('discourse.html',
                                     corpus_name=json.dumps(request.corpus.corpus_name),
                                     disc_id=disc_no,
                                     sent_id=sent_id,
                                     sentences=json.dumps(doc['sentences']),
                                     edus=json.dumps(doc['edus']),
                                     tokens=json.dumps(doc['tokens']),
                                     indent=json.dumps(doc['indent']),
                                     relations=json.dumps(doc.get('relations','')),
                                     nonedu=json.dumps(doc.get('nonedu',{})),
                                     topics=json.dumps(doc.get('topics',[])))
    request.set_corpus_cookie(response)
    return response

edu_re="[0-9]+(?:\\.[0-9]+)?"
topic_s="T[0-9]+"
topic_re=re.compile(topic_s)
span_re="(?:"+edu_re+"(?:-"+edu_re+")?|"+topic_s+")"
relation_re=re.compile("(\\w+(?:[- ]\\w+)*|\\?)\\s*\\(\\s*("+span_re+")\\s*,\\s*("+span_re+")\\s*\\)\\s*")
comment_re=re.compile("//.*$");

def parse_arg(arg):
    if topic_re.match(arg):
        return arg
    else:
        arg=arg.split('-')[0]
        if '.' not in arg:
            arg+='.0'
        return arg

def parse_relations(relations):
    relations_unparsed=[]
    relations_parsed=defaultdict(list)
    for l in relations.split('\n'):
        l_orig=l.strip()
        l=l_orig
        l=comment_re.sub('',l)
        m=relation_re.match(l)
        if not m:
            relations_unparsed.append(l_orig)
        else:
            rel_label=m.group(1)
            rel_arg1=parse_arg(m.group(2))
            rel_arg2=parse_arg(m.group(3))
            relations_parsed[rel_arg1].append(l_orig)
    return relations_parsed,relations_unparsed
        
def make_rels(rels):
    if rels is None or len(rels)==0:
        return ''
    elif len(rels)==1:
        return rels[0].encode('ISO-8859-1','xmlcharrefreplace')
    else:
        return '<br>'+'<br>'.join(rels).encode('ISO-8859-1','xmlcharrefreplace')
def render_discourse_printable(request,disc_no):
    db=request.corpus
    corpus=db.corpus
    t_id=int(disc_no)
    if not request.user:
        raise Forbidden("must be logged in")
    if request.user and request.user in ADMINS and 'who' in request.args:
        who=request.args['who']
    else:
        who=request.user
    doc=db.get_discourse(t_id,who)
    texts=corpus.attribute("text_id",'s')
    sents=corpus.attribute("s",'s')
    start,end,text_attrs=texts[t_id]
    sent_id=sents.cpos2struc(start)
    sentences=doc['sentences']
    edus=doc['edus']
    nonedu=doc.get('nonedu',{})
    tokens=doc['tokens']
    indent=doc['indent']
    topic_rels,relations_unparsed=parse_relations(doc.get('relations',''))
    topics=doc.get('topics',[])
    # go through words, creating discourse
    out=StringIO()
    out.write('''<html><head><title>Discourse %d:%s</title>
    <meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-15" />
    <link rel="stylesheet" href="/static/discourseEdit.css" type="text/css">
    </head>
    <body>
    <h1>Discourse %d:%s</h1>
    '''%(t_id,who,t_id,who))
    next_sent=0
    next_edu=0
    next_topic=0
    sub_edu=0
    INDENT_STEP=20
    in_div=False
    rel=''
    for i,tok in enumerate(tokens):
        if next_topic<len(topics) and topics[next_topic][0]==i:
            if in_div:
                out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
                in_div=False
            rel=make_rels(topic_rels.get('T%d'%(next_topic,),None))
            out.write('<div class="topic"><span class="edu-label">T%d</span>\n'%(next_topic,))
            out.write(topics[next_topic][1].encode('ISO-8859-1'))
            out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
            next_topic +=1
        if next_edu<len(edus) and edus[next_edu]==i:
            if in_div:
                out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
                in_div=False
            next_edu+=1
            sub_edu+=1
            if next_sent<len(sentences) and sentences[next_sent]==i:
                sub_edu=0
                next_sent+=1
            rel=make_rels(topic_rels.get('%d.%d'%(next_sent,sub_edu),None))
            if nonedu.get(unicode(i),None):
                cls='nonedu'
            else:
                cls='edu'
            out.write('<div class="%s" style="margin-left:%dpx"><span class="edu-label">%d.%d</span>'%(cls,indent[next_edu-1]*INDENT_STEP,next_sent,sub_edu))
            in_div=True
        out.write('%s '%(tok.encode('ISO-8859-1'),))
    if in_div:
        out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
    if relations_unparsed:
        out.write('<h2>unparsed relations:</h2>')
        out.write('<br>'.join(relations_unparsed).encode('ISO-8859-1'))
    out.write('</body>\n</html>\n')
    return Response([out.getvalue()],content_type='text/html; charset=ISO-8859-15')

def list_discourse(request):
    db=request.corpus
    words=db.words
    text_ids=db.corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
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
            if request.user in ADMINS:
                users=[doc['_user'] for doc in db.db.discourse.find({'_docno':docid})]
            else:
                users=[]
            doc_lst.append((request.user,r['_docno'],txt.decode('ISO-8859-15'),users))
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

