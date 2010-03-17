import sys
import CWB.CL as cwb
import couchdb.client
from anno_config import *
import hashlib

couch_ignore_attributes=set(['_id','_rev','type',
                             'span','corpus','annotator','level',
                             'word'])

def get_database():
    srv=couchdb.client.Server('http://192.168.1.1:5984')
    srv.resource.http.add_credentials('yannick','okiru')
    return srv['annotation']

class Annotation(object):
    def __init__(self,doc):
        self._doc=doc
    def get_id(self):
        return self._doc['_id']
    def get(self,key,default=None):
        return self._doc.get(key,default)
    def keys(self):
        return self._doc.keys()
    def __iter__(self):
        return iter(self._doc)
    def __getitem__(self,key):
        return self._doc[key]
    def __setitem__(self,key):
        self._doc[key]=val
    def __getattr__(self,key):
        return self._doc[key]
    def __setattr__(self,key,val):
        if key.startswith('_'):
            self.__dict__[key]=val
        else:
            self._doc[key]=val

class Task(object):
    def __init__(self,doc,db):
        self._doc=doc
        self._db=db
    def __getattr__(self,key):
        return self._doc[key]
    def __setattr__(self,key,val):
        if key.startswith('_'):
            self.__dict__[key]=val
        else:
            self._doc[key]=val
    def retrieve_annotations(annotator):
        result=[]
        for span in self.get_spans():
            a=get_annotation(db,
                             annotator,
                             self.level,
                             self.corpus,
                             span)
            result.append(a)
    def save(self):
        print self._doc
        self._db[self._id]=self._doc

def anno_key(ann,lvl,corpus,span):
    s='%s|%s|%s|%d|%d'%(ann,lvl,corpus,span[0],span[1])
    m=hashlib.md5()
    m.update(s)
    return 'anno_'+m.hexdigest()[:8]

def report_attributes_simple(part,names,out=sys.stdout,
                             ignore=couch_ignore_attributes):
    attrs=set()
    pairs=zip(names,part)
    for n,m in pairs:
        attrs.update(m.keys())
    attrs.difference_update(ignore)
    for k in sorted(attrs):
        print >>out, "<tr><td><b>%s</b></td><td>"%(k,)
        seen_vals=set()
        for n1,m1 in pairs:
            if k not in m1:
                continue
            val=m1[k]
            if val in seen_vals: continue
            out.write("%s ("%(val,))
            first=True
            for n2,m2 in pairs:
                if m2.get(k,None)==val:
                    if not first:
                        out.write(", ")
                    first=False
                    out.write(n2)
            print >>out, ")"
            seen_vals.add(val)
        print >>out, "</td></tr>"

class AnnoDB(object):
    def __init__(self,corpus_name='TUEBA4'):
        self.corpus=cwb.Corpus(corpus_name)
        self.sentences=self.corpus.attribute('s','s')
        self.words=self.corpus.attribute('word','p')
        self.corpus_name=corpus_name
        self.db=get_database()
    def get_tasks(self):
        map_fun='''function(doc) {
          if (doc.type == 'task' &&
              doc.corpus == '%s')
            emit(doc._id,null)
        }'''%(self.corpus_name,)
        result=[]
        for doc in self.db.query(map_fun):
            result.append(Task(doc,self.db))
        return result
    def create_task(self,name,level):
        _id='task_'+name
        a=self.db.get(_id)
        if a:
            assert a['level']==level
            assert a['corpus']==self.corpus_name
            if not hasattr(a,'type'):
                a['type']='task'
        else:
            a=dict(_id='task_'+name,
                   type='task',
                   corpus=self.corpus_name,
                   spans=[],
                   level=level)
        return Task(a,self.db)
    def get_annotation(self,annotator, level, span):
        k=anno_key(annotator,level,self.corpus_name,span)
        result=self.db.get(k)
        if result is None:
            doc=couchdb.client.Document(_id=k,
                                        type='anno',
                                        level=level,
                                        annotator=annotator,
                                        corpus=self.corpus_name,
                                        span=span)
            return Annotation(doc)
        else:
            result['level']=level
            result['annotator']=annotator
            result['corpus']=self.corpus_name
            return Annotation(result)
    def display_span(self,span,sent_before,sent_after,
                     out=sys.stdout):
        sent0=self.sentences.cpos2struc(span[0])
        sent0_orig=sent0
        sent1=self.sentences.cpos2struc(span[1]-1)
        if sent0>=sent_before:
            sent0-=sent_before
        else:
            sent0=0
        sent1+=sent_after
        first=True
        for k in xrange(sent0,sent1+1):
            sent_span=self.sentences[k]
            if not first:
                out.write('<br>\n')
            if k==sent0_orig:
                out.write('<a href="http://tintoretto.sfb.uni-tuebingen.de/pycwb/sentence/%s">s%s</a> '%(sent0_orig+1,sent0_orig+1))
            first=False
            for off in xrange(sent_span[0],sent_span[1]+1):
                if off==span[0]:
                    out.write('<b>')
                out.write(self.words[off])
                if off==span[1]-1:
                    out.write('</b>')
                out.write(' ')

        
    def display_annotation(self,parts,names,out):
        span=parts[0].span
        print >>out, '<div class="srctext">'
        self.display_span(span,1,0,out)
        print >>out, "</div>"
        print >>out, "<table>"
        report_attributes_simple(parts,names,out)
        print >>out, "</table>"
    def save_annotations(self,annos):
        docs=[anno._doc for anno in annos]
        self.db.update(docs)
    def docspan2span(self,markable,doc):
        sents=doc.read_markables('sentence')
        ctx=markable[3:5]
        ctx_sent=None
        sentid=None
        for sent in sents:
            if sent[3]<=markable[3] and sent[4]>=markable[4]:
                try:
                    sentid=int(sent[2]['orderid'])
                    ctx_sent=sent
                except KeyError:
                    pass
                try:
                    sentid=int(sent[2]['orderID'])
                    ctx_sent=sent
                except KeyError:
                    pass
                if not sentid:
                    print sent[2]
        assert sentid is not None
        sent_span=self.sentences[sentid-1]
        corpus_span=(sent_span[0]+ctx[0]-ctx_sent[3],
                     sent_span[0]+ctx[1]-ctx_sent[3])
        assert self.words[corpus_span[0]]==doc.tokens[ctx[0]],(doc.tokens[ctx_sent[3]:ctx_sent[4]],self.words[sent_span[0]:sent_span[1]])
        return corpus_span

def annotation_join(db,task):
    result=[]
    level=task.level
    for span in task.spans:
        row=[]
        for anno in task.annotators:
            m=db.get_annotation(anno,level,span)
            assert m.get('annotator')==anno,(m._doc,anno)
            row.append(m)
        result.append(row)
    return result
