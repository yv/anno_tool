import sys
import CWB.CL as cwb
import pymongo
from anno_config import *
import hashlib
import fshp

couch_ignore_attributes=set(['_id','_rev','type',
                             'span','corpus','annotator','level',
                             'word'])

srv=pymongo.Connection.paired(('192.168.1.1',27017),
                              ('192.168.1.2',27017))
#srv=pymongo.Connection('192.168.1.2')

def get_database():
    return srv['annoDB']

def create_user(username,passwd):
    hashed_pw=fshp.crypt(passwd)
    users=get_database().users
    user=users.find_one({'_id':username})
    if not user:
        user={'_id':username}
    user['hashed_pw']=hashed_pw
    users.save(user)

def login_user(username,passwd):
    users=get_database().users
    user=users.find_one({'_id':username})
    if not user:
        return None
    passwd=passwd.encode('ISO-8859-15')
    if fshp.check(passwd,user['hashed_pw']):
        return user
    return None

class Annotation(object):
    def __init__(self,doc):
        self._doc=doc
    def get_id(self):
        return self._doc.find_one({'_id':_id})
    def get(self,key,default=None):
        return self._doc.get(key,default)
    def keys(self):
        return self._doc.keys()
    def __iter__(self):
        return iter(self._doc)
    def __getitem__(self,key):
        return self._doc[key]
    def __setitem__(self,key,val):
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
    def retrieve_annotations(self,annotator):
        result=[]
        for span in self._doc['spans']:
            a=self._db.get_annotation(annotator,
                                self.level,
                                span)
            result.append(a)
        return result
    def save(self):
        print self._doc
        self._db.db.tasks.save(self._doc)

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
        self.db=get_database()[corpus_name]
    def get_tasks(self):
        result=[]
        for doc in self.db.tasks.find().toArray():
            result.append(Task(doc,self))
        return result
    def get_task(self,taskname):
        doc=self.db.tasks.find_one({'_id':taskname})
        if doc is not None:
            return Task(doc,self)
        else:
            return None
    def get_parses(self, sent_no):
        doc=self.db.parses.find_one({'_id':sent_no})
        if doc is None:
            print >>sys.stderr,"Not found: %s"%(repr(sent_no),)
            doc={'_id':sent_no}
        return doc
    def save_parses(self, doc):
        self.db.parses.save(doc)
    def create_task(self,name,level):
        _id='task_'+name
        a=self.db.tasks.find_one({'_id':_id})
        if a:
            assert a['level']==level,a
            assert a['corpus']==self.corpus_name
            if not hasattr(a,'type'):
                a['type']='task'
        else:
            a=dict(_id='task_'+name,
                   type='task',
                   corpus=self.corpus_name,
                   spans=[],
                   level=level)
        return Task(a,self)
    def get_tasks(self, name=None):
        all=self.db.tasks.find({})
        if name is not None:
            all = [Task(t,self) for t in all 
                   if t.get('annotators',None) is None
                   or name in t['annotators']]
        else:
            all = [Task(t,self) for t in all]
        return all
    def get_annotation(self,annotator, level, span):
        k=anno_key(annotator,level,self.corpus_name,span)
        result=self.db.annotation.find_one({'_id':k})
        if result is None:
            doc=dict(_id=k,
                     type='anno',
                     level=level,
                     annotator=annotator,
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
                out.write('<a href="/pycwb/sentence/%s">s%s</a> '%(sent0_orig+1,sent0_orig+1))
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
        for doc in docs:
            self.db.annotation.save(doc)
    def get_discourse(self,disc_id,user=None):
        result=self.db.discourse.find_one({'_id':disc_id,
                                           '_user':user})
        if result is None:
            words=self.words
            sents=self.sentences
            texts=self.corpus.attribute("text_id",'s')
            t_start,t_end,t_attrs=texts[disc_id]
            tokens=[w.decode('ISO-8859-15') for w in words[t_start:t_end+1]]
            sent=sents.cpos2struc(t_start)
            sent_end=sents.cpos2struc(t_end)
            sentences=[]
            for k in xrange(sent,sent_end+1):
                s_start,s_end,s_attr=sents[k]
                sentences.append(s_start-t_start)
            edus=sentences[:]
            indent=[0]*len(edus)
            result={'_id':disc_id,
                    '_user':user,
                    'tokens':tokens,
                    'sentences':sentences,
                    'edus':edus,
                    'indent':indent}
        return result
    def save_discourse(self,doc):
        self.db.discourse.save(doc)
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

def create_task_anno(username,task,populate=None):
    db=AnnoDB()
    task=db.get_task(task)
    if task is None:
        raise KeyError
    annos=[]
    for span in task.spans:
        m=db.get_annotation(username,task.level,span)
        if populate:
            populate(m)
        annos.append(m)
    db.save_annotations(annos)

def add_annotator(taskname, username):
    db=AnnoDB()
    task=db.get_task(taskname)
    if task is None:
        raise KeyError(taskname)
    user0=task.annotators[0]
    if task is None:
        raise KeyError
    annos=[]
    for span in task.spans:
        m=db.get_annotation(username,task.level,span)
        if 'word' not in m:
            m2=db.get_annotation(user0,task.level,span)
            for k in ['word']:
                m[k]=m2[k]
        annos.append(m)
    if username not in task.annotators:
        task.annotators.append(username)
        task.save()
    db.save_annotations(annos)

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
