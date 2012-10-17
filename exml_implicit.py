#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
import re
import sys
import exml
from exml import Text, Edu, EduRange, Topic, edu_re, topic_s
from itertools import izip
from collections import defaultdict
from ordereddict import OrderedDict
from pytree import tree
from annodb import database
from annodb.corpora import corpus_sattr, corpus_d_sattr, corpus_urls

__doc__="""
lädt SDRT-Annotation aus der Annotationsdatenbank und
konvertiert die Daten ins ExportXMLv2-Format.

Aufruf:
python exml_implicit.py Annotator > datei_exml.xml
"""

__version__="2011-03-03"
__author__="Yannick Versley / Univ. Tuebingen"


class DiscRel(exml.GenericMarkable):
    def __init__(self,label,target,marking=None):
        self.label=label
        self.marking=marking
        self.target=target

class DiscRelEdges(object):
    def __init__(self,name):
        self.name=name
        self.attributes=[exml.EnumAttribute('relation'),
                         exml.EnumAttribute('marking'),
                         exml.RefAttribute('arg2')]
    def get_edges(self,obj,doc):
        edges=[]
        if hasattr(obj,'rels') and obj.rels is not None:
            for rel in obj.rels:
                edges.append((rel.label,rel.marking,rel.target))
        return edges
    def get_updown(self,obj,doc,result):
        pass

comment_re=re.compile("//.*$");
span_re="(?:"+edu_re+"(?:-"+edu_re+")?|"+topic_s+")"
relation_re=re.compile("(\\w+(?:[- ]\\w+)*|\\?)\\s*\\(\\s*("+span_re+")\\s*,\\s*("+span_re+")\\s*\\)\\s*(%[^/]*)?\\s*")


def make_implicit_doc():
    text_schema=exml.MarkableSchema('text',Text)
    text_schema.attributes=[exml.TextAttribute('origin')]
    s_schema=exml.MarkableSchema('sentence',tree.Tree)
    s_schema.locality='text'
    discrel_edge=DiscRelEdges('discRel')
    topic_schema=exml.MarkableSchema('topic',Topic)
    topic_schema.attributes=[exml.TextAttribute('description')]
    topic_schema.locality='text'
    topic_schema.edges=[discrel_edge]
    edu_range_schema=exml.MarkableSchema('edu-range',EduRange)
    edu_range_schema.locality='text'
    edu_range_schema.edges=[discrel_edge]
    edu_schema=exml.MarkableSchema('edu',Edu)
    edu_schema.locality='sentence'
    edu_schema.edges=[discrel_edge]
    t_schema=exml.TerminalSchema('word',tree.TerminalNode)
    t_schema.attributes=[exml.TextAttribute('form',prop_name='word'),
                         exml.EnumAttribute('pos',prop_name='cat'),
                         exml.EnumAttribute('morph',prop_name='morph'),
                         exml.EnumAttribute('lemma',prop_name='lemma'),
                         exml.RefAttribute('dephead',prop_name='syn_parent'),
                         exml.EnumAttribute('deprel',prop_name='syn_label')]
    return exml.Document(t_schema,[text_schema,s_schema,
                                   edu_schema,topic_schema,edu_range_schema])                

def parse_relations(relations,text,ctx):
    relations_unparsed=text.unparsed_rels
    relations_parsed=defaultdict(list)
    for l in relations.split('\n'):
        l_orig=l.strip()
        l=l_orig
        l=comment_re.sub('',l)
        m=relation_re.match(l)
        if not m:
            relations_unparsed.append(l_orig)
        else:
            rel_label=m.group(1)
            try:
                rel_arg1=text.get_segment(m.group(2),ctx)
                rel_arg2=text.get_segment(m.group(3),ctx)
                rel_marking=m.group(4)
                if rel_marking is not None:
                    rel_marking=rel_marking.lstrip('%').strip()
                    rel_marking=rel_marking.encode('ISO-8859-15')
            except KeyError:
                relations_unparsed.append(l_orig)
            else:
                rel_arg1.rels.append(DiscRel(rel_label,rel_arg2,marking=rel_marking))

class DBReader:
    def __init__(self,ctx,db):
        self.ctx=ctx
        self.texts=db.corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
        self.sentences=db.corpus.attribute("s",'s')
        self.words=db.words
        self.postags=db.corpus.attribute("pos",'p')
    def addRange(self,start,end):
        ctx=self.ctx
        ctx_start=len(ctx.words)

def check_words(words_c,words_db):
    idx=0
    while True:
        if idx==len(words_c):
            if idx==len(words_db):
                return True
            else:
                print >>sys.stderr, "Remaining bits [1]:",words_db[idx:]
                return False
        elif idx==len(words_db):
            print >>sys.stderr, "Remaining bits [2]:",words_c[idx:]
            return False
        w_c=words_c[idx]
        w_db=words_db[idx]
        if not isinstance(w_c,unicode):
            w_c=w_c.decode('ISO-8859-15')
        if not isinstance(w_db,unicode):
            w_db=w_db.decode('ISO-8859-15')
        if w_c!=w_db:
            return False
        idx+=1

class DiscourseReader:
    """Liest Diskursannotation und erzeugt passende Markables"""
    def __init__(self,ctx,db):
        self.ctx=ctx
        self.texts=db.corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
        self.sentences=db.corpus.attribute("s",'s')
        self.words=db.words
        self.postags=db.corpus.attribute("pos",'p')
        self.morph=db.corpus.attribute("morph",'p')
        self.deprel=db.corpus.attribute("deprel","p")
        self.attach=db.corpus.attribute("attach","p")
        self.lemma=db.corpus.attribute("lemma","p")
        self.db=db
    def add_sentences(self,sentences,start,tokens):
        sent_id=self.sentences.cpos2struc(start)
        ctx=self.ctx
        ctx_start=len(ctx.words)
        end=start+len(tokens)
        terminals=[tree.TerminalNode(pos,w) for (w,pos) in izip(self.words[start:end],
                                                                self.postags[start:end])]
        assert check_words(self.words[start:end],tokens), (self.words[start:end][:3],tokens[:3])
        for i,n in enumerate(terminals):
            cpos=start+i
            n.syn_label=self.deprel[cpos]
            n.lemma=self.lemma[cpos]
            n.morph=self.morph[cpos]
            tok_attach=self.attach[cpos]
            if tok_attach!='ROOT':
                try:
                    n.syn_parent=terminals[i+int(tok_attach)]
                except IndexError,e:
                    print n.word,tok_attach,i,len(terminals)
                    print e
        for i in xrange(len(sentences)):
            t=tree.Tree()
            t.sent_no=sent_id+i
            start=sentences[i]
            try:
                end=sentences[i+1]
            except IndexError:
                end=len(tokens)
            corpus_start,corpus_end=self.sentences[sent_id+i][:2]
            t.terminals=terminals[start:end]
            t.span=(start+ctx_start,end+ctx_start)
            prefix='s%s'%(t.sent_no,)
            t.xml_id=prefix
            if end-start!=corpus_end-corpus_start+1:
                print >>sys.stderr, "Length mismatch: (%d vs %d)"%(end-start, corpus_end-corpus_start+1)
                print >>sys.stderr, start,end,tokens[start:end]
                print >>sys.stderr, corpus_start,corpus_end,self.words[corpus_start:corpus_end+1]
            for j in xrange(start,end):
                #print start,end,j,len(t.terminals)
                #t.terminals[j-start].xml_id='%s_%d'%(prefix,j-start+1)
                t.terminals[j-start].xml_id='t%s'%(corpus_start+j-start,)
                ctx.add_terminal(t.terminals[j-start])
            ctx.register_object(t)
    def addNext(self, doc):
        ctx=self.ctx
        ctx_start=len(ctx.words)
        t_id=int(doc['_docno'])
        start,end,text_id=self.texts[t_id]
        sentences=doc['sentences']
        edus=doc['edus']
        nonedu=doc.get('nonedu',{})
        tokens=doc['tokens']
        topics=doc.get('topics',[])
        self.add_sentences(sentences,start,tokens)
        #assert tokens==self.words[start:end+1], (tokens[:3],self.words[start:start+3])
        assert check_words(self.words[start:end+1], tokens), (t_id, self.words[start:start+3], tokens[:3])
        text_markable=Text(text_id,t_id)
        text_markable.xml_id='text_%s'%(t_id,)
        text_markable.span=(ctx_start,ctx_start+len(tokens))
        ctx.register_object(text_markable)
        for i in xrange(len(topics)):
            start=topics[i][0]
            try:
                end=topics[i+1][0]
            except IndexError:
                end=len(tokens)
            top=Topic(xml_id='topic_%s_%d'%(t_id,i))
            top.span=(start+ctx_start,end+ctx_start)
            top.description=topics[i][1].encode('ISO-8859-15')
            text_markable.topics['T%d'%(i,)]=top
            ctx.register_object(top)
        next_sent=0
        sub_edu=0
        for i in xrange(len(edus)):
            start=edus[i]
            try:
                end=edus[i+1]
            except IndexError:
                end=len(tokens)
            assert start<end
            if next_sent<len(sentences) and start==sentences[next_sent]:
                sub_edu=0
                next_sent+=1
            else:
                sub_edu+=1
            if nonedu.get(unicode(start),None):
                pass
            else:
                edu_markable=Edu()
                edu_markable.span=(start+ctx_start,end+ctx_start)
                edu_markable.xml_id='edu_%s_%d_%d'%(t_id,next_sent,sub_edu)
                text_markable.edus['%d.%d'%(next_sent,sub_edu)]=edu_markable
                edu_markable.edu_idx=len(text_markable.edu_list)
                text_markable.edu_list.append(edu_markable)
                ctx.register_object(edu_markable)
        parse_relations(doc['relations'],text_markable,ctx)
        

if __name__=='__main__':
    db=database.get_corpus('TUEBA4')
    text_ids=db.corpus.attribute(corpus_d_sattr.get(db.corpus_name,'text_id'),'s')
    if len(sys.argv)>1:
        annotator=sys.argv[1]
    else:
        annotator='*gold*'
    results=db.db.discourse.find({'_user':annotator})
    doc=make_implicit_doc()
    print '<?xml version="1.0" encoding="ISO-8859-15"?>'
    print '<exml-doc>'
    reader=DiscourseReader(doc,db)
    # do the actual conversion
    for r in results:
        try:
            docid=int(r['_docno'])
        except KeyError:
            pass
        else:
            reader.addNext(r)
    doc.describe_schema(sys.stdout)
    print '<body serialization="inline">'
    doc.write_inline_xml(sys.stdout)
    print '</body>'
    print '</exml-doc>'
