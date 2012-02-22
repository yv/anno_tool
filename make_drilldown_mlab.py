#!/usr/bin/python
# -*- coding: iso-8859-1 -*-
import sys
import re
import simplejson as json
import numpy
import codecs
from annodb import database
from jinja2 import Environment, FileSystemLoader
from cStringIO import StringIO
from collections import defaultdict
from alphabet import PythonAlphabet
from getopt import getopt
from xvalidate_common import shrink_to


__doc__="""
Erzeugt HTML-Dateien mit Daten für drilldown.js (Multilabel-Klassifikation)

Aufruf:
python make_drilldown_mlab.py -d CORPUS features.json results1.json [results2.json] > page.html

Options:
  -d CORPUS
  -m max_depth    : ignore taxonomy levels > max_depth
  -w weights_file : include weights
"""

max_depth=None

db_name=None
mylookup=Environment(loader=FileSystemLoader('./templates',encoding='ISO-8859-15'))
tmpl=mylookup.get_template('drilldown.html')
corpus_name=None
weights_fname=None

opts,args=getopt(sys.argv[1:],'m:d:w:')
for k,v in opts:
    if k=='-m':
        max_depth=int(v)
    elif k=='-d':
        corpus_name=v
    elif k=='-w':
        weights_fname=v

all_data=[]
spans=[]
for l in file(args[0]):
    bin_nr,data,label,unused_span=json.loads(l)
    if max_depth is not None:
        label=[shrink_to(lab,max_depth) for lab in label]
    all_data.append((bin_nr,data,label))

weights={}
if weights_fname is not None:
    for l in codecs.open(weights_fname,'r','ISO-8859-15'):
        line=l.strip().split()
        weights[line[0]]=float(line[1])

if corpus_name is not None:
    db=database.get_corpus(corpus_name)
    snippets=[]
    for l in file(args[0]):
        bin_nr,data,label,span=json.loads(l)
        out=StringIO()
        sent_no=db.sentences.cpos2struc(span[0])+1
        print >>out,'<a href="http://localhost:5000/pycwb/sentence/%d?force_corpus=%s">s%d</a>'%(
            sent_no,corpus_name,sent_no)
        db.display_spans([(span[0],span[1]+1,"<b>","</b>")],out)
        snippets.append(out.getvalue().decode('ISO-8859-15'))
else:
    snippets=None
    

def get_predictions(fname):
    f_cls=file(fname)
    result=[]
    for bin_nr,data,label in all_data:
        best=json.loads(f_cls.readline())
        if max_depth is not None:
            best=[shrink_to(lab,max_depth) for lab in best]
        result.append(best)
    return result

predictions={}
columns=[]
for fname in args[1:]:
    predictions[fname]=get_predictions(fname)
    columns.append(fname)
js_out=StringIO()

js_out.write('data=%s;\ncolumns=%s;\npredictions=%s\n'%(json.dumps(all_data),
                                                        json.dumps(columns),
                                                        json.dumps(predictions)))
js_out.write('snippets=%s;\n'%(json.dumps(snippets)))
js_out.write('weights=%s;\n'%(json.dumps(weights)))
js_out.write('type="mlab";')
print tmpl.render(jscode=js_out.getvalue())
