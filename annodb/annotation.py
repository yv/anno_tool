# PyCWB annotation tool (c) 2009-2013 Yannick Versley / Univ. Tuebingen
# released under the Apache license, version 2.0
#
# displaying, retrieving and saving annotations via HTTP requests 
#
import re
from itertools import izip
import simplejson as json
import yaml
import os.path
import sys
from cStringIO import StringIO

from annodb.schema import schemas
from annodb.database import *
from webapp_admin import *

from werkzeug.exceptions import NotFound, Forbidden

def is_ready(anno):
    if anno.get('level','konn')=='mod':
        scheme=mod_scheme
    else:
        scheme=konn_scheme
    if anno.get('comment',None) is not None:
        return False
    for key,values in scheme:
        if anno.get(key,None) is None:
            return False
    return True

def annotate(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    if task is None:
        return NotFound("no such task")
    if task.level == 'konn2':
        return annotate2(request,taskname)
    elif task.level == 'wsd':
        return annotate_wsd(request, taskname)
    else:
        return annotate1(request,taskname)
    

def annotate1(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    schema=schemas[task.level]
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        return redirect('/pycwb/login')
    mode=request.args.get('mode','wanted')
    annotations=task.retrieve_annotations(user)
    out=StringIO()
    out_js=StringIO()
    if mode=='wanted':
        print >>out, '<div><a href="?mode=all&force_corpus=%s">show all</a></div>'%(db.corpus_name,)
    for anno in annotations:
        if mode!='wanted' or not is_ready(anno):
            schema.make_widgets(anno,db,out,out_js)
    print >>out, '<div><a href="/pycwb/mark_ready/%s?force_corpus=%s">als fertig markieren</a></div>'%(taskname,db.corpus_name)
    response=render_template('annodummy.html',task=task,
                             corpus_name=db.corpus_name,
                             js_code=out_js.getvalue().decode('ISO-8859-15'),
                             output=out.getvalue().decode('ISO-8859-15'))
    request.set_corpus_cookie(response)
    return response

def mark_ready(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    if task is None:
        return NotFound("no such task")
    schema=schemas[task.level]
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        return redirect('/pycwb/login')
    if user not in task.annotators:
        return NotFound("no such task")
    if task.get_status(user) is None:
        task.set_status(user,'ready')
        task.save()
    return redirect('/pycwb')

def annotate2(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        return redirect('/pycwb/login')
    annotations=task.retrieve_annotations(user)
    scheme=schemas[task.level]
    jscode=StringIO()
    out=None
    jscode.write('examples=[]\n;')
    jscode.write('schema=%s\n;'%(json.dumps(scheme.schema)))
    for anno in annotations:
        scheme.make_widgets(anno,db,out,jscode)
    return render_template('annodummy2.html',
                           task=taskname,
                           corpus_name=db.corpus_name,
                           jscode=jscode.getvalue())

def annotate_wsd(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        return redirect('/pycwb/login')
    annotations=task.retrieve_annotations(user)
    scheme=schemas[task.level]
    jscode=StringIO()
    out=None
    jscode.write('examples=[]\n;')
    for anno in annotations:
        scheme.make_widgets(anno,db,out,jscode)
    return render_template('annodummy_wsd.html',
                           task=taskname,
                           corpus_name=db.corpus_name,
                           jscode=jscode.getvalue())

def adjudicate(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    schema=schemas[task.level]
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        return redirect('/pycwb/login')
    mode=request.args.get('mode','wanted')
    annotations=task.retrieve_annotations(user)
    out=StringIO()
    out_js=StringIO()
    ms=annotation_join(db,task)
    names=task.annotators
    if not names:
        return Response('Liste der Annotatoren ist leer.')
    level=task.level
    for part in ms:
        span=part[0].span
        anno_a=db.get_annotation(user,level,span)
        print >>out, '<div class="srctext">'
        db.display_span(span,1,0,out)
        print >>out, "</div>"
        print >>out, "<table>"
        for k in schema.get_slots():
            print >>out, "<tr><td><b>%s</b></td><td width=\"400\">"%(k,)
            seen_vals=set()
            for anno in part:
                try:
                    seen_vals.add(anno[k])
                except KeyError:
                    pass
            prefix=anno_a._id+'-'+k
            for v in seen_vals:
                if v==anno_a.get(k,None):
                    cls="chosen"
                else:
                    cls="choose"
                names_ch=','.join([name for (anno,name) in zip(part,names)
                                   if anno.get(k,None)==v])
                out.write('<a class="%s" onclick="chosen_txt(\'%s\',\'%s\');" id="%s_%s">%s</a> (%s)\n'%(cls,prefix,v,prefix,v,v,names_ch))
            out.write('</td><td><input id="txt:%s" onkeyup="after_blur_2(\'%s\')" value="%s"></td></tr>'%(prefix,prefix,anno_a.get(k,'')))
        print >>out,"</table>"
        comments=[]
        for anno,name in zip(part,names):
            if 'comment' in anno and anno['comment']:
                comments.append('<i>%s:</i>%s'%(name,escape(anno['comment']).replace('\n','<br>')))
        if comments:
            print >>out,"<b>comments:</b><br>"
            print >>out,(u'<br>'.join(comments)).encode('ISO-8859-15','xmlcharrefreplace')
    return render_template('annodummy.html',task=task,
                           js_code=out_js.getvalue().decode('ISO-8859-15'),
                           corpus_name=db.corpus_name,
                           output=out.getvalue().decode('ISO-8859-15'))

ignore_attributes_download=['span','type','corpus','annotator']
def download_anno(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    fmt=request.args.get('fmt','yaml')
    schema=schemas[task.level]
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        return redirect('/pycwb/login')
    out_js=StringIO()
    ms=annotation_join(db,task)
    names=task.annotators
    if not names:
        return Response('Liste der Annotatoren ist leer.')
    level=task.level
    json_parts=[]
    for part in ms:
        part_repr={}
        span=part[0].span
        part_repr['_span']=span
        part_repr['_corpus']=part[0].corpus
        part_repr['_sent_no']=db.sentences.cpos2struc(span[0])+1
        out=StringIO()
        db.display_span(span,1,0,out)
        part_repr['_html']=out.getvalue().decode('ISO-8859-15')
        part_repr['_annotators']=names
        for anno,name in zip(part,names):
            part_repr[name]=dict(((k,anno[k]) for k in anno if k not in ignore_attributes_download))
        json_parts.append(part_repr)
    if fmt=='yaml':
        return Response(yaml.safe_dump_all(json_parts, allow_unicode=True),mimetype='text/yaml')
    else:
        return Response(json.dumps(json_parts),mimetype='text/javascript')

hier_map={}
def make_schema(entries,prefix):
    for x in entries:
        hier_map[x[0]]=prefix+x[0]
        make_schema(x[2],'%s%s.'%(prefix,x[0]))
make_schema(schemas['konn2'].schema,'')

def agreement(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    level=task.level
    schema=schemas[task.level]
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        return redirect('/pycwb/login')
    mode=request.args.get('mode','wanted')
    annotations=task.retrieve_annotations(user)
    ms=annotation_join(db,task)
    columns=task.annotators
    predictions=[[] for col in columns]
    snippets=[]
    def deepen_tag(tag):
        return hier_map.get(tag,tag)
    def get_label(anno):
        lbl=[deepen_tag(anno.get('rel1','NULL'))]
        if 'rel2' in anno and anno['rel2']!='NULL':
            lbl.append(deepen_tag(anno['rel2']))
        return lbl
    for part in ms:
        span=part[0].span
        anno_a=db.get_annotation(user,level,span)
        if '##' in anno_a.get('comment',''):
            continue
        out=StringIO()
        print >>out, '<div class="srctext">'
        db.display_span(span,1,0,out)
        print >>out, "</div>"
        snippets.append(out.getvalue().decode('ISO-8859-15'))
        for (anno,labels) in izip(part,predictions):
            labels.append(get_label(anno))
    out_js=StringIO()
    print >>out_js, "columns=%s;"%(json.dumps(columns),)
    print >>out_js, "snippets=%s;"%(json.dumps(snippets),)
    print >>out_js, "predictions=%s;"%(json.dumps(predictions),)
    return render_template('agreement.html',task=task,
                           js_code=out_js.getvalue().decode('ISO-8859-15'),
                           corpus_name=db.corpus_name)

class ForAll(object):
    __slots__=['f']
    def __init__(self,f):
        self.f=f
    def __call__(self,x):
        f=self.f
        for val in x:
            if not f(val):
                return False
        return True
class ForAny(object):
    __slots__=['f']
    def __init__(self,f):
        self.f=f
    def __call__(self,x):
        f=self.f
        for val in x:
            result=f(val)
            if result:
                return result
        return False
class Disagree(object):
    __slots__=['f']
    def __init__(self,f):
        self.f=f
    def __call__(self,x):
        f=self.f
        vals=set()
        for val in x:
            result=f(val)
            vals.add(result)
        return (len(vals)>1)


symbols={}
konn2_mapping=schemas['konn2'].taxon_mapping

immutable_attributes=set(['_id','annotator','span','corpus','level'])
def save_attributes(request):
    db=request.corpus
    annotation=db.db.annotation
    if request.user is None:
        raise Forbidden
    if request.method=='POST':
        stuff=json.load(request.stream)
        print >>sys.stderr, stuff
        try:
            for k,v in stuff.iteritems():
                anno_key,attr=k.split('-',1)
                if attr in immutable_attributes:
                    print >>sys.stderr,"%s ignored (immutable)"%(attr,)
                    continue
                anno=annotation.find_one({'_id':anno_key})
                if anno is None:
                    print >>sys.stderr, "(not found):%s"%(anno_key,)
                if request.user!=anno['annotator']:
                    raise Forbidden("not yours")
                anno[attr]=v
                annotation.save(anno)
        except ValueError:
            raise NotFound("no such attribute")
        except HTTPException,e:
            print >>sys.stderr, e
            raise
        else:
            return Response('Ok')
    else:
        raise NotFound("only POST allowed")
