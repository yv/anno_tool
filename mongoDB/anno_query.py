import re
from pynlp.mmax_tools import *
import simplejson as json
import os.path
import sys

BASEDIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASEDIR)
from anno_tools import *
from anno_config import *
from mongoDB.annodb import *
from web_stuff import *
from cStringIO import StringIO
from taxonomy_schema import load_schema, taxon_map
from querygrammar import FunctorOp, Accessor, TaxonAccessor, \
    Constant, parser, make_query

from werkzeug import run_simple, parse_form_data, escape
from werkzeug.exceptions import NotFound, Forbidden

class ForAll(object):
    """checks a condition on all markables in a query"""
    def __init__(self,a):
        self.a=a
    def __call__(self,mss):
        for ms in mss:
            if not self.a(ms):
                return False
        return True

class ForAny(object):
    """checks a condition on some markables in a query"""
    def __init__(self,a):
        self.a=to_query(a)
    def __call__(self,mss):
        for ms in mss:
            if ms==[]:
                continue
            if self.a(ms):
                return True
        return False

class Disagree(object):
    """checks a condition on some markables in a query"""
    def __init__(self,a):
        self.a=to_query(a)
    def __call__(self,mss):
        someTrue=False
        someFalse=False
        for ms in mss:
            if self.a(ms):
                someTrue=True
            else:
                someFalse=True
        return someTrue and someFalse
    
        
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

def display_chooser(prefix,alternatives,chosen,out):
    for alt in alternatives:
        cls='choose'
        if alt==chosen:
            cls='chosen'
        out.write('''
[<a class="%s" onclick="chosen('%s','%s');" id="%s_%s">%s</a>]\n'''%(
                cls,prefix,alt,prefix,alt,alt))

def display_textbox(prefix,value,out):
    out.write('''
<textarea cols="80" id="%s" onkeyup="after_blur('%s')">'''%(
            prefix,prefix))
    if value is not None:
        out.write(value)
    out.write('</textarea>')

konn_scheme=[('temporal',['temporal','non_temporal']),
             ('causal',['causal','enable','non_causal']),
             ('contrastive',['kontraer','kontradiktorisch',
                             'parallel','no_contrast'])]

mod_scheme=[('class',['tmp','loc','sit','freq','dur',
                      'final','causal','concessive','cond','dir',
                      'instr','focus','source','manner',
                      'commentary','modalprt','intensifier'])]
                     
def widgets_konn(anno,out,out_js=None):
    edited=False
    out.write('<table>')
    if anno.get('level','konn')=='mod':
        scheme=mod_scheme
    else:
        scheme=konn_scheme
    for key,values in scheme:
        out.write('<tr><td><b>')
        out.write(key)
        out.write(':</b></td><td>')
        val=anno.get(key,None)
        if val is not None:
            edited=True
        display_chooser(anno._id+':'+key,values,
                        val,out)
        out.write('</td></tr>')
    out.write('<tr><td><b>comment:</b></td><td>')
    val=anno.get('comment',None)
    if val is not None:
        edited=True
    display_textbox(anno._id+':comment',
                    anno.get('comment',None),out)
    out.write('</td></tr></table>')
    if out_js and edited:
        out_js.write('set_edited(%s)'%(anno._id))

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
        raise NotFound("no such task")
    user=request.user
    if user is None:
        redirect('/pycwb/login')
    mode=request.args.get('mode','wanted')
    annotations=task.retrieve_annotations(user)
    out=StringIO()
    if mode=='wanted':
        print >>out, '<div><a href="?mode=all">show all</a></div>'
    for anno in annotations:
        if mode!='wanted' or not is_ready(anno):
            print >>out, '<div class="srctext" id="src:%s">'%(anno._id,)
            db.display_span(anno['span'],1,0,out)
            print >>out, '</div>'
            widgets_konn(anno,out)
    return render_template('annodummy.html',task=task,
                           output=out.getvalue().decode('ISO-8859-15'))


konn2_schema=load_schema(file(os.path.join(BASEDIR,'konn2_schema.txt')))
konn2_mapping=taxon_map(konn2_schema)
def annotate2(request,taskname):
    db=request.corpus
    task=db.get_task(taskname)
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        redirect('/pycwb/login')
    annotations=task.retrieve_annotations(user)
    examples=[]
    for anno in annotations:
        out=StringIO()
        db.display_span(anno['span'],1,0,out)
        munged_anno=dict(anno)
        munged_anno['text']=out.getvalue().decode('ISO-8859-15')
        examples.append(munged_anno)
    jscode='examples=%s;\nschema=%s;'%(json.dumps(examples),
                                       json.dumps(konn2_schema))
    return render_template('annodummy2.html',
                           jscode=jscode)

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
symbols['==']=FunctorOp(lambda x,y: x==y)
symbols['in']=FunctorOp(lambda x,y: x in y)
symbols['not in']=FunctorOp(lambda x,y: x not in y)
symbols['|']=FunctorOp(lambda x,y: x or y)
symbols['&']=FunctorOp(lambda x,y: x and y)
symbols['rel1']=TaxonAccessor('rel1',konn2_mapping)
symbols['rel2']=TaxonAccessor('rel2',konn2_mapping)
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
                anno_key,attr=k.split(':')
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
