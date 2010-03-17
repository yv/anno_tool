import re
from pynlp.mmax_tools import *
from anno_tools import *
from anno_config import *
from annodb import *
from cStringIO import StringIO

from werkzeug import run_simple, parse_form_data, escape

db=AnnoDB()

class QueryBase(object):
    isQuery=True
    def __eq__(self,other):
        return QueryBinOp(self,to_query(other),lambda x,y: x==y)
    def __ne__(self,other):
        return QueryBinOp(self,to_query(other),lambda x,y: x!=y)
    def __and__(self,other):
        return QueryBinOp(self,to_query(other),lambda x,y: x and y)
    def __or__(self,other):
        return QueryBinOp(self,to_query(other),lambda x,y: x or y)
    def __rand__(self,other):
        return QueryBinOp(self,to_query(other),lambda x,y: x and y)
    def __ror__(self,other):
        return QueryBinOp(self,to_query(other),lambda x,y: x or y)
    def __invert__(self):
        return lambda x: not self(x)

class QueryBinOp(QueryBase):
    __slots__=['a','b','f']
    def __init__(self,a,b,f):
        self.a=a
        self.b=b
        self.f=f
    def __call__(self,x):
        return self.f(self.a(x),self.b(x))

class QueryMonOp(QueryBase):
    __slots__=['a','f']
    def __init__(self,a,f):
        self.a=a
        self.f=f
    def __call__(self,x):
        return self.f(self.a(x))

class QueryConstant(QueryBase):
    __slots__=['a']
    def __init__(self,a):
        self.a=a
    def __call__(self,x):
        return self.a

class ForAll(QueryBase):
    """checks a condition on all markables in a query"""
    def __init__(self,a):
        self.a=a
    def __call__(self,mss):
        for ms in mss:
            if not self.a(ms):
                return False
        return True

class ForAny(QueryBase):
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

class Disagree(QueryBase):
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

temporal=MarkableAttribute('temporal')
causal=MarkableAttribute('causal')
contrastive=MarkableAttribute('contrastive')
other_rel=MarkableAttribute('other_rel')

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
    task=Task(db.db['task_'+which_set],db)
    ms=annotation_join(db,task)
    names=task.annotators
    out=StringIO()
    for part in ms:
        if q(part):
            db.display_annotation(part,names,out)
    yield out.getvalue()
    yield "</body></html>"

def display_form(environ,start_response):
    options='\n'.join(['<option value="%s">%s'%(k,k) for k in anno_sets.keys()])
    result='''
<html><head><title>Query Form</title></head>
<body>
<form action="/annoquery" method="post">
<textarea cols="80" rows="4" name="q">
ForAll(contrastive=='kontraer') & Disagree(temporal=='temporal')
</textarea><br>
<select name="wset">
%s
</select><br>
<input type="submit">
</form>
</body>
</html>'''%(options,)
    start_response('200 OK',[('Content-type','text/html; charset=iso-8859-1')])
    return [result]

myglobals={'__builtins__':None}
for k in 'ForAny ForAll Disagree contrastive temporal causal other_rel'.split():
    myglobals[k]=globals()[k]

query_ok_re=re.compile(r"^(\'[a-z]+\'|==|\!=|[\(\)\&\| ]|ForAll|ForAny|contrastive|temporal|causal)+$")
def display_annoquery(environ,start_response):
    if environ['REQUEST_METHOD']=='POST':
        form=parse_form_data(environ)[1]
        qs=form['q'].strip().replace('\n','')
        qset=form.get('wset','all1')
        #m=query_ok_re.match(qs)
        m=True
        if m:
            try:
                q=eval(qs,myglobals)
            except SyntaxError,e :
                start_response('200 OK',[('Content-type','text/html; charset=iso-8859-1')])
                return ['''<html><head><title>not valid</title></head>
<body>
<h1>Syntax Error</h1>
%s<br>
%s
</body>'''%(e,e.text)]
            else:
                start_response('200 OK',[('Content-type','text/html; charset=iso-8859-1')])
                return run_query(q,qset)
        else:
            start_response('200 OK',[('Content-type','text/html; charset=iso-8859-1')])
            return ['''<html><head><title>not valid</title></head>
<body>
<h1>Your query is not valid</h1>
</body>''']
    return display_form(environ,start_response)

def test_web():    
    run_simple('localhost',8091,display_annoquery)

application=display_annoquery

if __name__=='__main__':
    q=ForAll(contrastive=='kontraer') & (ForAny(temporal=='temporal') & ForAny(temporal!='temporal'))
    for s in run_query(q):
        sys.stdout.write(s)
