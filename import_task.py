from annodb import *
from mmax_tools import *
from anno_config import *
from anno_tools import *

import httplib2

#httplib2.debuglevel=2

db=AnnoDB()


if len(sys.argv)>1:
    wanted=sys.argv[1:]
else:
    wanted=anno_sets.keys()

for taskname in wanted:
    task=db.create_task(taskname,'konn')
    task.annotators=['anna','sabrina','holger']
    all_spans=set()
    for annotator in task.annotators:
        annotations=[]
        for docid in anno_sets[taskname]:
            doc=MMAXDiscourse(annodirs[annotator],docid)
            ms=doc.read_markables('konn')
            for m in ms:
                span=db.docspan2span(m,doc)
                anno=db.get_annotation(annotator,'konn',span)
                for k,v in m[2].iteritems():
                    if k not in completely_ignore_attributes:
                        anno._doc[k]=v
                anno.span=span
                annotations.append(anno)
                all_spans.add(span)
        db.save_annotations(annotations)
    task.spans=sorted(all_spans)
    task.save()
