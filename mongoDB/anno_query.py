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
from taxonomy_schema import load_schema
from querygrammar import FunctorOp, Accessor, interpret_query

from werkzeug import run_simple, parse_form_data, escape
from werkzeug.exceptions import NotFound, Forbidden

db=AnnoDB()

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
    
        
class MarkableAttribute(QueryBase):
    def __init__(self,name):
        self.name=name
        self.isQuery=True
    def __call__(self,markable):
        val=markable.get(self.name,None)
        return val

def to_query(x):
    if hasattr(x,'isQuery'):
        return x
    else:
        return QueryConstant(x)


symbol_dict={}
for k in ['temporal','causal','contrastive','other_rel']:
    symbol_dict[k]=Accessor(k)
symbol_dict['==']=FunctorOp(lambda a,b: a==b)

def run_query(q, which_set='all1'):
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
    task=Task(db.db.tasks.find_one({'_id':'task_'+which_set}),db)
    ms=annotation_join(db,task)
    names=task.annotators
    out=StringIO()
    for part in ms:
        if q(part):
            db.display_annotation(part,names,out)
    yield out.getvalue()
    yield "</body></html>"

myglobals={'__builtins__':None,'None':None}
for k in 'ForAny ForAll Disagree contrastive temporal causal other_rel'.split():
    myglobals[k]=globals()[k]

query_ok_re=re.compile(r"^(\'[a-z]+\'|==|\!=|[\(\)\&\| ]|ForAll|ForAny|contrastive|temporal|causal)+$")
def display_annoquery(request):
    if request.method=='POST':
        form=request.form
        qs=form['q'].strip().replace('\n','')
        qset=form.get('wset','all1')
        #m=query_ok_re.match(qs)
        m=True
        if m:
            try:
                q=eval(qs,myglobals)
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
                result=' '.join(run_query(q,qset)).decode('ISO-8859-15')
                print type(result)
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
def widgets_konn(anno,out,out_js=None):
    edited=False
    out.write('<table>')
    for key,values in konn_scheme:
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

def annotate(request,taskname):
    task=db.get_task(taskname)
    if task is None:
        raise NotFound("no such task")
    user=request.user
    if user is None:
        redirect('/pycwb/login')
    annotations=task.retrieve_annotations(user)
    out=StringIO()
    for anno in annotations:
        print >>out, '<div class="srctext" id="src:%s">'%(anno._id,)
        db.display_span(anno['span'],1,0,out)
        print >>out, '</div>'
        widgets_konn(anno,out)
    return render_template('annodummy.html',task=task,
                           output=out.getvalue().decode('ISO-8859-15'))


konn2_schema=load_schema(file(os.path.join(BASEDIR,'konn2_schema.txt')))
def annotate2(request,taskname):
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

immutable_attributes=set(['_id','annotator','span','corpus','level'])
def save_attributes(request):
    annotation=db.db.annotation
    if request.user is None:
        raise Forbidden
    if request.method=='POST':
        stuff=json.load(request.stream)
        print stuff
        try:
            for k,v in stuff.iteritems():
                anno_key,attr=k.split(':')
                if attr in immutable_attributes:
                    print >>sys.stderr,"%s ignored (immutable)"%(attr,)
                    continue
                print anno_key,attr
                anno=annotation.find_one({'_id':anno_key})
                if anno is None:
                    print "(not found):%s"%(anno_key,)
                if request.user!=anno['annotator']:
                    raise Forbidden("not yours")
                anno[attr]=v
                annotation.save(anno)
        except ValueError:
            raise NotFound("no such attribute")
        except HTTPException,e:
            print e
            raise
        else:
            return Response('Ok')
    else:
        raise NotFound("only POST allowed")

if __name__=='__main__':
    q=ForAll(contrastive=='kontraer') & (ForAny(temporal=='temporal') & ForAny(temporal!='temporal'))
    for s in run_query(q):
        sys.stdout.write(s)
