#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
import sys
import shelve
import exml_merged
import optparse
from annodb.database import get_corpus
from pytree.tree import Tree
from collections import defaultdict
from exml import Document, Text

def main(exp_fname,corpus_name,opts):
    exml_db=shelve.open('/export2/local/yannick/%s_db.db'%(corpus_name,),protocol=-1)
    doc=exml_merged.make_konn_doc()
    reader=exml_merged.MergedCorpusReader(doc,exp_fname,corpus_name)
    last_stop=len(doc.words)
    texts=[]
    text_no=0
    exml_db['_schema']=(doc.t_schema,doc.schemas,doc.schema_by_class)
    while True:
        try:
            disc_rels=[]
            new_stop=reader.addNext()
            if (new_stop!=last_stop):
                for txt in doc.get_objects_by_class(Text,last_stop,new_stop):
                    texts.append(txt.span[0])
                    w_objs=[]
                    markables=[]
                    for i in xrange(txt.span[0],txt.span[1]):
                        w_objs.append(doc.w_objs[i])
                        markables+=[markable for mlevel,markable in doc.markables_by_start[i]]
                    exml_db['d%d'%(text_no)]=(w_objs,markables)
                    text_no+=1
            doc.clear_markables(last_stop,new_stop)
            last_stop=new_stop
        except StopIteration:
            break
    if (last_stop!=len(doc.words)):
        for txt in doc.get_objects_by_class(Text,last_stop):
            texts.append(txt.span[0])
            w_objs=[]
            markables=[]
            for i in xrange(txt.span[0],txt.span[1]):
                w_objs.append(doc.w_objs[i])
                markables+=[markable for mlevel,markable in doc.markables_by_start[i]]
            exml_db['d%d'%(text_no)]=(w_objs,markables)
            text_no+=1
    exml_db['_texts']=texts
    exml_db['_words']=doc.words

class DBDocument(Document):
    '''
    uses an EXML representation with lazy-loading from a database
    '''
    def __init__(self, corpus_name):
        exml_db=shelve.open('/export2/local/yannick/%s_db.db'%(corpus_name,),protocol=-1)
        self.db=exml_db
        self.annodb=get_corpus(corpus_name)
        (t_schema, schemas, schema_by_class)=exml_db['_schema']
        Document.__init__(self, t_schema, schemas)
        self.words=exml_db['_words']
        self.w_objs=[None]*len(self.words)
        self._texts=exml_db['_texts']
    def ensure_loaded(self,doc_no):
        offset=self._texts[doc_no]
        if self.w_objs[offset] is not None:
            return
        w_objs,markables=self.db['d%d'%(doc_no,)]
        for i,w_obj in enumerate(w_objs):
            self.w_objs[offset+i]=w_obj
        for obj in markables:
            self.register_object(obj)
        return (offset,offset+len(w_objs))
    def ensure_span(self, start, end):
        low=0; high=len(self._texts)-1
        more=True
        while more:
            mid=(low+high)/2
            if self._texts[mid]<start and low<mid:
                low=mid
            elif self._texts[mid]>end and high>mid:
                high=mid
            else:
                more=False
        for i in xrange(low,high+1):
            self.ensure_loaded(i)
        return (low,high)
    def get_tree(self, sent_no):
        start,end=self.annodb.sentences[sent_no][:2]
        self.ensure_span(start,end)
        markables=self.markables_by_start[start]
        for schema,obj in markables:
            if isinstance(obj,Tree):
                return obj
        assert False, (sent_no, markables)

oparse=optparse.OptionParser()
if __name__=='__main__':
    opts,args=oparse.parse_args(sys.argv[1:])
    if len(args)>=2:
        main(args[0], args[1],opts)
    else:
        exp_fname='/gluster/nufa/public/tuebadz-7.0-mit-NE-format4-mit-anaphern.export'
        corpus_name='R7FINAL'
        main(exp_fname,corpus_name,opts)
