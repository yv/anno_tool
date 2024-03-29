# PyCWB annotation tool (c) 2009-2013 Yannick Versley / Univ. Tuebingen
# released under the Apache license, version 2.0
#
# This file implements discourse annotation functionality
#
import re
import simplejson as json

from werkzeug.utils import escape
from werkzeug.exceptions import NotFound, Forbidden, HTTPException

from webapp_admin import render_template, render_template_nocache, \
     redirect, Response, ADMINS
from annodb.corpora import corpus_sattr, corpus_d_sattr, corpus_urls

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
    coref=db.db.referential.find_one({'_id':t_id})
    discourse=db.db.discourse.find_one({'_id':'%s~*gold*'%(t_id,)})
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
    if coref is not None:
        names_coref=sorted([k for k in coref.iterkeys() if k!='_id'])
    else:
        names_coref=[]
    annotations=db.find_annotations([start,end],'*gold*')
    if names_parses or names_alignments or annotations:
        print >>trees_out,'<div id="parses-tabs">'
        print >>trees_out,'<ul class="nav nav-tabs">'
        for k in names_parses:
            print >>trees_out,'<li><a href="#parses-%s">%s (parse)</a></li>'%(k,k)
        for k in names_alignments:
            print >>trees_out,'<li><a href="#alignments-%s">%s (align)</a></li>'%(k,k)
        for k in names_coref:
            print >>trees_out,'<li><a href="#coref-%s">%s (coref)</a></li>'%(k,k)
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
        for k in names_coref:
            v=coref[k]
            print >>trees_out,'<div id="coref-%s">'%(k,)
            write_coref(db, v, trees_out, start,end+1)
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
                             disc_id=t_id_d,
                             corpus_name=request.corpus.corpus_name,
                             has_gold=(discourse is not None))
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
                                     uedus=json.dumps(doc.get('uedus',{})),
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
        
def render_discourse_printable(request,disc_no):
    db=request.corpus
    corpus=db.corpus
    t_id=int(disc_no)
    if not request.user:
        raise Forbidden("must be logged in")
    if request.user and 'who' in request.args and (request.user in ADMINS or request.args['who']=='*gold*'):
        who=request.args['who']
    else:
        who=request.user
    doc=db.get_discourse(t_id,who)
    topic_rels,relations_unparsed=parse_relations(doc.get('relations',''))
    # go through words, creating discourse
    out=StringIO()
    out.write('''<html><head><title>Discourse %d:%s</title>
    <meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-15" />
    <link rel="stylesheet" href="/static/discourseEdit.css" type="text/css">
    </head>
    <body>
    <h1>Discourse %d:%s</h1>
    '''%(t_id,who,t_id,who))
    out.write(render_document_html(doc, topic_rels))
    if relations_unparsed:
        out.write('<h2>unparsed relations:</h2>')
        out.write('<br>'.join(relations_unparsed).encode('ISO-8859-1'))
    out.write('</body>\n</html>\n')
    return Response([out.getvalue()],content_type='text/html; charset=ISO-8859-15')

def list_discourse(request):
    db=request.corpus
    words=db.words
    text_ids=db.corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
    docids=sorted(set([r['_docno'] for r in db.db.discourse.find({'_user':{'$in':[request.user,'*gold*']}}) if '_docno' in r]))
    doc_lst=[]
    for docid in docids:
        txt0=text_ids[docid]
        txt="%s: %s"%(txt0[2],' '.join(words[txt0[0]:txt0[0]+5]))
        if request.user in ADMINS:
            users=[doc['_user'] for doc in db.db.discourse.find({'_docno':docid})]
        else:
            users=[doc['_user'] for doc in db.db.discourse.find({'_docno':docid})
                   if (doc['_user'] in ['*gold*',request.user] or
                       request.user is not None and doc['_user'].startswith(request.user+'*'))]
        doc_lst.append((request.user,docid,txt.decode('ISO-8859-15'),users))
    return render_template('discourse_list.html',
                           corpus_name=db.corpus_name,
                           user=request.user,
                           results=doc_lst)

def isolate_relations(relations):
    different_relations=defaultdict(list)
    for l in relations.split('\n'):
        l_orig=l.strip()
        l=l_orig
        l=comment_re.sub('',l)
        m=relation_re.match(l)
        if m:
            rel_arg1=parse_arg(m.group(2))
            rel_label=m.group(1)
            different_relations[rel_label].append(rel_arg1)
    return different_relations

def gold_discourse_rels(request):
    db=request.corpus
    words=db.words
    text_ids=db.corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
    results=db.db.discourse.find({'_user':'*gold*'})
    docs={}
    sum_all=0
    rel_counts=defaultdict(int)
    rel_occurrences=defaultdict(list)
    for r in results:
        try:
            docid=int(r['_docno'])
        except KeyError:
            pass
        else:
            txt0=text_ids[docid]
            txt="%s: %s"%(txt0[2],' '.join(words[txt0[0]:txt0[0]+5]))
            txt=txt.decode('ISO-8859-15')
            rels=isolate_relations(r['relations'])
            for k in rels:
                sum_all+=len(rels[k])
                rel_counts[k]+=len(rels[k])
                rel_occurrences[k].append((docid,txt,rels[k]))
    result=[]
    for rel in sorted(rel_counts.keys(),key=lambda x:-rel_counts[x]):
        result.append((rel,rel_counts[rel],rel_occurrences[rel]))
    return render_template('discourse_rels.html',
                           corpus_name=db.corpus_name,
                           results=result,
                           sum_all=sum_all)

def discourse_rels(request):
    db=request.corpus
    words=db.words
    text_ids=db.corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
    results=db.db.discourse.find({'_user':request.user})
    docs={}
    rel_counts=defaultdict(int)
    rel_occurrences=defaultdict(list)
    sum_all=0
    for r in results:
        try:
            docid=int(r['_docno'])
        except KeyError:
            pass
        else:
            txt0=text_ids[docid]
            txt="%s: %s"%(txt0[2],' '.join(words[txt0[0]:txt0[0]+5]))
            txt=txt.decode('ISO-8859-15')
            rels=isolate_relations(r['relations'])
            for k in rels:
                sum_all+=len(rels[k])
                rel_counts[k]+=len(rels[k])
                rel_occurrences[k].append((docid,txt,rels[k]))
    result=[]
    for rel in sorted(rel_counts.keys(),key=lambda x:-rel_counts[x]):
        result.append((rel,rel_counts[rel],rel_occurrences[rel]))
    return render_template('discourse_rels.html',
                           corpus_name=db.corpus_name,
                           results=result,
                           sum_all=sum_all)


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

allowed_suffix_re=re.compile('[a-zA-Z0-9_-]+')
def archive_discourse(request,disc_no):
    db=request.corpus
    t_id=int(disc_no)
    if not request.user:
        raise Forbidden('must be logged in')
    doc=db.get_discourse(t_id,request.user)
    if request.method=='POST':
        stuff=json.load(request.stream)
        if 'newsuffix' in stuff and allowed_suffix_re.match(stuff['newsuffix']):
            newsuffix=stuff['newsuffix']
            new_user='%s*%s'%(request.user,newsuffix)
            doc['_id']='%s~%s'%(disc_no,new_user)
            doc['_user']=new_user
            db.save_discourse(doc)
            return Response(json.dumps(doc))
        else:
            raise NotFound('Invalid Suffix')
    else:
        raise NotFound('Only POST allowed')

def compare_discourse(request,disc_no):
    db=request.corpus
    t_id=int(disc_no)
    if ('user1' not in request.args and
        'user2' not in request.args):
        user1=request.user
        user2='*gold*'
    else:
        if ('user1' not in request.args or
            'user2' not in request.args):
            return NotFound('need user1, user2')
        user1=request.args['user1']
        user2=request.args['user2']
    doc1=db.get_discourse(t_id,user1)
    doc2=db.get_discourse(t_id,user2)
    tokens=doc1['tokens']
    sentences=doc1['sentences']
    sent_gold=sentences[:]
    sent_gold.append(len(tokens))
    exclude=set(sent_gold)
    edus1=doc1['edus']
    edus2=doc2['edus']
    interesting1=set(edus1).difference(exclude)
    interesting2=set(edus2).difference(exclude)
    common=interesting1.intersection(interesting2)
    edu_only1=interesting1.difference(interesting2)
    edu_only2=interesting2.difference(interesting1)
    edus=sorted(common.union(sent_gold))
    diffs_seg=[]
    markers=[]
    sent_idx=0
    for n in sorted(edu_only1.union(edu_only2)):
        while sent_gold[sent_idx]<n:
            sent_idx+=1
        if n in edu_only1:
            diagnosis="Nur %s"%(user1,)
            markers.append((n,'1','edu'))
        else:
            diagnosis="Nur %s"%(user2,)
            markers.append((n,'2','edu'))
        diffs_seg.append((diagnosis,"[%d] %s | %s"%(sent_idx,
                                               ' '.join(tokens[n-2:n]),' '.join(tokens[n:n+2]))))
    n_common=len(common)
    n_only1=len(edu_only1)
    n_only2=len(edu_only2)
    #for i,(start,end) in enumerate(zip(sent_gold[:-1],sent_gold[1:])):
    #    sentences.append((i+1,tokens[start:end]))
    if n_common==0:
        f_val_seg=0
    else:
        f_val_seg=2*n_common/(len(interesting1)+len(interesting2))
    diffs_topic=[]
    topics1=dict([x for x in doc1.get('topics',[])])
    topics2=dict([x for x in doc2.get('topics',[])])
    #print >>sys.stderr, topics2
    topics=[]
    sent_idx=0
    for start,topic_str in sorted(topics1.iteritems()):
        if start not in topics2:
            while sent_gold[sent_idx]<start:
                sent_idx+=1
            diffs_topic.append(("Nur %s"%(user1,),"[%s] %s"%(sent_idx, topic_str)))
            topics.append((start,'<span class="marker1">[%s]</span> %s'%(user1, topic_str)))
        else:
            topics.append((start,'%s / %s'%(topic_str, topics2[start])))
    for start,topic_str in sorted(topics2.iteritems()):
        if start not in topics1:
            while sent_gold[sent_idx]<start:
                sent_idx+=1
            diffs_topic.append(("Nur %s"%(user2,),"[%s] %s"%(sent_idx, topic_str)))
            topics.append((start,'<span class="marker2">[%s]</span> %s'%(user2, topic_str)))
    topics.sort()
    users=[doc['_user'] for doc in db.db.discourse.find({'_docno':t_id})]
    comp_result=make_comparison(db, t_id, user1, user2)
    rels=comp_result.rels_compare.make_display_rels()
    # render common view of discourse
    display=render_document_html(doc, rels, markers, replacement_topics=topics)
    return render_template('discourse_diff.html',
                           display=display.decode('ISO-8859-15'),
                           all_users=users,
                           docid=t_id, user1=user1, user2=user2,
                           sentences=sentences,
                           f_val_seg=f_val_seg, diffs_seg=diffs_seg,
                           diffs_topic=diffs_topic)

