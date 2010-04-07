import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mongoDB.annodb import *
from mmax_tools import *
from anno_config import *
from anno_tools import *


db=AnnoDB()

def map_attributes(old_attrs,doc):
    word=old_attrs['word']
    doc['word']=word
    rels=[]
    temporal=old_attrs.get('temporal',None)
    contrastive=old_attrs.get('contrastive',None)
    causal=old_attrs.get('causal')
    if word=='nachdem':
        if temporal=='temporal':
            rels.append('Temporal')
        if contrastive in ['kontraer','kontradiktorisch']:
            rels.append('contrast')
        elif contrastive=='parallel':
            rels.append('parallel')
        if causal=='enable':
            rels.append('enable')
        elif causal=='causal':
            rels.append('cause')
    else:
        if contrastive in ['kontraer','kontradiktorisch']:
            rels.append('contrast')
        elif contrastive=='parallel':
            rels.append('parallel')
        if causal=='enable':
            rels.append('enable')
        elif causal=='causal':
            rels.append('cause')
        if temporal=='temporal':
            rels.append('Temporal')
    if len(rels)>=1:
        doc['rel1']=rels[0]
        if len(rels)>=2:
            doc['rel2']=rels[1]
        elif 'rel2' in doc:
            del doc['rel2']
    elif 'rel1' in doc:
        del doc['rel1']
        
            
if len(sys.argv)>1:
    wanted=sys.argv[1:]
else:
    wanted=anno_sets.keys()

for taskname in wanted:
    task=db.create_task(taskname+'_new','konn2')
    task.annotators=['anna','sabrina','holger']
    all_spans=set()
    for annotator in task.annotators:
        annotations=[]
        for docid in anno_sets[taskname]:
            doc=MMAXDiscourse(annodirs[annotator],docid)
            ms=doc.read_markables('konn')
            for m in ms:
                span=db.docspan2span(m,doc)
                anno=db.get_annotation(annotator,'konn2',span)
                map_attributes(m[2],anno._doc)
                anno.span=span
                anno.level='konn2'
                annotations.append(anno)
                all_spans.add(span)
        db.save_annotations(annotations)
    task.spans=sorted(all_spans)
    task.save()
