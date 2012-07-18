import re
from itertools import izip
from pynlp.mmax_tools import *
import simplejson as json
import os.path
import sys

BASEDIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASEDIR)
from schema import schemas
from annodb.database import *
from web_stuff import *
from cStringIO import StringIO
from querygrammar import FunctorOp, Accessor, TaxonAccessor, \
    Constant, parser, make_query

from werkzeug.exceptions import NotFound, Forbidden
            
def run_query(q, which_set,db):
    yield """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
"http://www.w3.org/TR/html4/strict.dtd">
<html><head><title>Annotation diff</title>
<style type="text/css">
  .srctext { font-size: 12pt; line-height: 150%;
     font-family:Helvetica,Arial,sans-serif;
     font-style: italic;
     border-top: solid thin black;
     margin-top: 20pt;
     margin-bottom: 12pt;  }
  .difference { font-size: 11pt; }
  .file_id { font-weight: bold; font-size: 14pt;
  margin-top: 20pt; }
  </style>
</head>
<body>"""
    task=db.get_task(which_set)
    ms=annotation_join(db,task)
    names=task.annotators
    out=StringIO()
    for part in ms:
        if q(part):
            db.display_annotation(part,names,out)
    yield out.getvalue()
    yield "</body></html>"

myglobals={'__builtins__':None,'None':None}
#for k in 'ForAny ForAll Disagree contrastive temporal causal other_rel'.split():
#    myglobals[k]=globals()[k]

query_ok_re=re.compile(r"^(\'[a-z]+\'|==|\!=|[\(\)\&\| ]|ForAll|ForAny|contrastive|temporal|causal)+$")
def display_annoquery(request):
    db=request.corpus
    if request.method=='POST':
        form=request.form
        qs=form['q'].strip().replace('\n','')
        qset=form.get('wset','all1')
        #m=query_ok_re.match(qs)
        m=True
        if m:
            try:
                q=make_query("ForAny(rel1 in Comparison)",symbols)    
            except SyntaxError,e :
                return render_template('annoquery.html',
                                       errmsg='Syntax error:%s<br>%s'%(e,e.text),
                                       query=form['q'],
                                       tasks=anno_sets)
            except TypeError,e :
                return render_template('annoquery.html',
                                       errmsg='Type error:%s'%(e,),
                                       query=form['q'],
                                       tasks=anno_sets)
            else:
                result=' '.join(run_query(q,qset,db)).decode('ISO-8859-15')
                print >>sys.stderr, type(result)
                return Response(result, mimetype='text/html')
        else:
            return render_template('annoquery.html',
                                   errmsg='Your query is not valid',
                                   query=form['q'],
                                   tasks=anno_sets)
    return render_template('annoquery.html',
                           errmsg='',
                           query='',
                           tasks=anno_sets)


konn_scheme=[('temporal',['temporal','non_temporal']),
             ('causal',['causal','enable','non_causal']),
             ('contrastive',['kontraer','kontradiktorisch',
                             'parallel','no_contrast'])]

mod_scheme=[('class',['tmp','loc','sit','freq','dur',
                      'final','causal','concessive','cond','dir',
                      'instr','focus','source','manner',
                      'commentary','modalprt','intensifier'])]

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

def download_anno(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
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
        part_repr['_sent_no']=db.sentences.cpos2struc(span[0])+1
        out=StringIO()
        db.display_span(span,1,0,out)
        part_repr['_html']=out.getvalue().decode('ISO-8859-15')
        part_repr['_annotators']=names
        for anno,name in zip(part,names):
            part_repr[name]=dict(((k,anno[k]) for k in anno))
        json_parts.append(part_repr)
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
symbols['==']=FunctorOp(lambda x,y: x==y)
symbols['in']=FunctorOp(lambda x,y: x in y)
symbols['not in']=FunctorOp(lambda x,y: x not in y)
symbols['|']=FunctorOp(lambda x,y: x or y)
symbols['&']=FunctorOp(lambda x,y: x and y)
symbols['rel1']=TaxonAccessor('rel1',schemas['konn2'].taxon_mapping)
symbols['rel2']=TaxonAccessor('rel2',schemas['konn2'].taxon_mapping)
symbols['ForAll']=ForAll
symbols['ForAny']=ForAny
symbols['Disagree']=Disagree

#for k in ['temporal','causal','contrastive','other_rel']:
#    symbols[k]=Accessor(k)
for k,v in konn2_mapping.iteritems():
    symbols[k]=Constant(v)

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

if __name__=='__main__':
    q=make_query("ForAny(rel1 in Comparison)",symbols)    
    for s in run_query(q,'task_aber1_new'):
        sys.stdout.write(s)
