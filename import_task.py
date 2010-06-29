import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from annodb.database import *
from mmax_tools import *
from anno_config import *
from anno_tools import *

corpus="R6PRE1"

db=AnnoDB(corpus)

def map_attributes(old_attrs,doc):
    word=old_attrs['word']
    doc['word']=word
    if 'comment' in old_attrs:
        doc['comment']=old_attrs['comment']
    rels=[]
    temporal=old_attrs.get('temporal',None)
    contrastive=old_attrs.get('contrastive',None)
    causal=old_attrs.get('causal')
    other_rel=old_attrs.get('other_rel')
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
    if other_rel=='concession':
        rels.append('Concession')
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
    print taskname
    task=db.create_task(taskname+'_new','konn2')
    #task.annotators=['anna','sabrina','holger']
    if task.get('annotators',None) is None:
        task.annotators=[]
    all_spans=set()
    for annotator in ['*default*']:
        annotations=[]
        for docid in anno_sets[taskname]:
            doc=MMAXDiscourse(annodirs['null'],docid)
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
