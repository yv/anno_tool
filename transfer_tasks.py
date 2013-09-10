import sys
from annodb.database import get_corpus, anno_key
from mercurial.bdiff import blocks
from itertools import izip
import optparse
import numpy

def make_offsets(ws1, ws2):
    offsets_map={}
    blk=blocks('\n'.join(ws1),'\n'.join(ws2))
    for i1,i2,j1,j2 in blk:
        if i2>i1:
            for i,j in izip(xrange(i1,i2),xrange(j1,j2)):
                offsets_map[i]=j
    return offsets_map

span_parts={'ne':['span_parts']}

class AnnoMapper:
    def __init__(self,corpus1,corpus2):
        self.db1=corpus1
        self.db2=corpus2
        ws1=list(self.db1.words)
        ws2=list(self.db2.words)
        self.offset_map=make_offsets(ws1,ws2)
        print >>sys.stderr, "%d tokens (of %d/%d) aligned"%(len(self.offset_map),
                                                            len(ws1), len(ws2))
    def remap_annotation(self, anno):
        span=anno['span']
        span_new=(self.offset_map[span[0]], self.offset_map[span[1]])
        level=anno['level']
        id_new=anno_key(anno['annotator'], level,
                        self.db2.corpus_name, span_new)
        anno['_id']=id_new
        anno['span']=span_new
        if level in span_parts:
            for k in span_parts[level]:
                if k in anno:
                    parts_mapped=[]
                    for frm, to in anno[k]:
                        parts_mapped.append((self.offset_map[frm], self.offset_map[to]))
                    anno[k]=parts_mapped
    def copy_tasks(self, task_names, force=False):
        wanted_spans=set()
        wanted_levels=set()
        for task_name in task_names:
            task=self.db1.db.tasks.find_one({'_id':task_name})
            assert task
            new_spans=[]
            for frm, to in task['spans']:
                try:
                    new_spans.append((self.offset_map[frm], self.offset_map[to]))
                except KeyError:
                    print "task %s: cannot map %d-%d"%(task_name,frm,to)
            wanted_spans.update((tuple(spn) for spn in task['spans']))
            task['spans']=new_spans
            task['corpus']=self.db2.corpus_name
            task2=self.db2.db.tasks.find_one({'_id':task['_id']})
            if not task2:
                self.db2.db.tasks.save(task)
            elif task2['spans']==task['spans']:
                if task2['corpus']!=args[1]:
                    task2['corpus']=args[1]
                    self.db2.db.tasks.save(task2)
                continue
            else:
                print 'duplicate task: %s'%(task_name,)
        for anno in self.db1.db.annotation.find():
            span=anno['span']
            if tuple(span) not in wanted_spans:
                continue
            try:
                self.remap_annotation(anno)
            except KeyError:
                pass
            anno2=self.db2.db.annotation.find_one({'_id':anno['_id']})
            if force or anno2 is None:
                self.db2.db.annotation.save(anno)

oparse=optparse.OptionParser()
oparse.add_option('-f','--force',dest="force", default=False,
                  action='store_true',
                  help="overwrite existing annotations")
oparse.add_option('-l','--list',dest="list", default=False,
                  action='store_true',
                  help="list annotations, don't do anything")

if __name__=='__main__':
    opts,args=oparse.parse_args()
    print opts, args
    db1=get_corpus(args[0])
    db2=get_corpus(args[1])
    if len(args)>=3:
        task_re=args[2]
    else:
        task_re=None
    all_names=[]
    if task_re is None:
        all_names=[x['_id'] for x in db1.db.tasks.find()]
    else:
        all_names=[x['_id'] for x in db1.db.tasks.find({'_id':{'$regex':task_re}})]
    if opts.list:
        print >>sys.stderr, "Affected tasks: (RE=%s, n=%s)"%(task_re,len(all_names))
        for x in sorted(all_names):
            print x
    else:
        print >>sys.stderr, "Create offsets map..."
        mapper=AnnoMapper(db1,db2)
        print >>sys.stderr, "Copying all tasks (RE=%s, n=%s)"%(task_re,len(all_names))
        mapper.copy_tasks(all_names,opts.force)
