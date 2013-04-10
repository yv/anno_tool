import sys
import numpy
import cPickle
import os.path
from app_configuration import get_config_var
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import  sessionmaker, relationship
from sqlalchemy.sql import and_, or_, not_
from sqlalchemy.sql.expression import func
from sqlalchemy import Table, Column, Integer, String, Unicode, \
     Boolean, MetaData,\
     ForeignKey, create_engine

HAS_HYPERNYM=0
IS_RELATED_TO=1
HAS_HOLONYM=2
HAS_MERONYM=3
ENTAILS=4
CAUSES=5
HAS_COMPONENT_MERONYM=6
HAS_MEMBER_MERONYM=7
HAS_PORTION_MERONYM=8
HAS_SUBSTANCE_MERONYM=9

LEXREL_HAS_ANTONYM=0
LEXREL_HAS_PERTAINYM=1
LEXREL_ARG2=2
LEXREL_ARG1=3
LEXREL_HAS_PARTICIPLE=4

WCAT_ADJ=0
WCAT_NOMEN=1
WCAT_VERB=2

def to_latin1(s):
    if isinstance(s,unicode):
        return s.encode('ISO-8859-15')
    else:
        return s

Base = declarative_base()

class WordClass(Base):
    __tablename__='word_class_table'
    id=Column(Integer, primary_key=True)
    word_class=Column(String)
    def __str__(self):
        return self.word_class
    def __repr__(self):
        return 'germanet.WordClass(%d,%s)'%(self.id, self.word_class)

class WordCategory(Base):
    __tablename__='word_category_table'
    id=Column(Integer, primary_key=True)
    word_category=Column(String)
    def __str__(self):
        return self.word_category
    def __repr__(self):
        return 'germanet.WordCategory(%d,%s)'%(self.id, self.word_category)

class Synset(Base):
    __tablename__='synset_table'
    id=Column(Integer, primary_key=True)
    word_class_id=Column(Integer, ForeignKey('word_class_table.id'))
    word_class=relationship(WordClass)
    word_category_id=Column(Integer, ForeignKey('word_category_table.id'))
    word_category=relationship(WordCategory)
    paraphrase=Column(Unicode)
    comment=Column(Unicode)
    def __repr__(self):
        return 'germanet.Synset(%d)'%(self.id)
    def explain(self):
        return '%s: %s'%(self.id,
                         ' '.join(self.getWords()))
    def getWords(self):
        return [lu.wstr() for lu in self.lexunit]
    def getHypernyms(self):
        return [rel.to_synset for rel in self.from_rel
                if rel.rel_type_id==HAS_HYPERNYM]
    def getHyponyms(self):
        return [rel.from_synset for rel in self.to_rel
                if rel.rel_type_id==HAS_HYPERNYM]
    def print_hypernym_tree(self, indent=0):
        print ' '*indent + self.explain()
        for s in self.getHypernyms():
            s.print_hypernym_tree(indent+2)
    def print_hyponym_tree(self, indent=0, limit_depth=None, limit_breadth=None):
        print ' '*indent + self.explain()
        hypo=self.getHyponyms()
        wanted=True
        if limit_depth is not None:
            wanted=(limit_depth>0)
            new_depth_limit=limit_depth-1
        else:
            new_depth_limit=None
        if limit_breadth is not None and len(hypo)>limit_breadth:
            wanted=False
        if wanted:
            for s in self.getHyponyms():
                s.print_hyponym_tree(indent+2, new_depth_limit, limit_breadth)
        else:
            print ' '*(indent+2) + '...'
    def synset_depth(self):
        if hasattr(self,'cached_depth'):
            return self.cached_depth
        depth=None
        for syn in self.getHypernyms():
            d=syn.synset_depth()+1
            if depth is None or d<depth:
                depth=d
        if depth is None:
            depth=0
        self.cached_depth=depth
        return depth

class LexicalUnit(Base):
    __tablename__='lex_unit_table'
    id=Column(Integer, primary_key=True)
    synset_id=Column(Integer, ForeignKey('synset_table.id'))
    synset=relationship(Synset,backref='lexunit')
    orth_form=Column(Unicode)
    source=Column(String)
    named_entity=Column(Boolean)
    artificial=Column(Boolean)
    style_marking=Column(Boolean)
    old_orth_form=Column(String)
    old_orth_var=Column(Unicode)
    orth_var=Column(Unicode)
    comment=Column(Unicode)
    def __repr__(self):
        return 'germanet.LexicalUnit(%d)'%(self.id)
    def wstr(self):
        a=''
        if self.artificial: a+='?'
        if self.named_entity: a+='+'
        if self.style_marking: a+='#'
        a+=to_latin1(self.orth_form)
        return a

class ConRelType(Base):
    __tablename__='con_rel_type_table'
    id=Column(Integer, primary_key=True)
    name=Column(String)
    direction=Column(String)
    inverse=Column(String)
    transitive=Column(Boolean)
    inverse_pwn_key=Column(String)
    pwn_key=Column(String)
    def __repr__(self):
        return 'germanet.ConRelType(%d, %s)'%(self.id, self.name)

class ConRel(Base):
    __tablename__='con_rel_table'
    id=Column(Integer, primary_key=True)
    rel_type_id=Column(Integer, ForeignKey('con_rel_type_table.id'))
    rel_type=relationship(ConRelType)
    from_synset_id=Column(Integer, ForeignKey('synset_table.id'))
    from_synset=relationship(Synset, primaryjoin=(from_synset_id==Synset.id),
                             backref='from_rel', order_by=id)
    to_synset_id=Column(Integer, ForeignKey('synset_table.id'))
    to_synset=relationship(Synset, primaryjoin=(to_synset_id==Synset.id),
                           backref='to_rel', order_by=id)
    def __repr__(self):
        return 'germanet.ConRel(%s, %s, %s)'%(self.rel_type.name,
                                              self.from_synset_id,
                                              self.to_synset_id)

class GWN_DB(object):
    def __init__(self, dburl, data_dir=None):
        self.synsetsByWord={}
        engine=create_engine(dburl)
        self.session_factory=sessionmaker(bind=engine)
        self.session=self.session_factory()
        self.hypernym_graph=None
    def synsets_for_word(self, word):
        if not isinstance(word, unicode):
            word=word.decode('ISO-8859-15')
        if self.synsetsByWord.has_key(word):
            return self.synsetsByWord[word]
        session=self.session
        result=[session.query(Synset).get(id)
                for id in session.query(LexicalUnit.synset_id)
                    .filter(LexicalUnit.orth_form==word)]
        self.synsetsByWord[word]=result
        return result
    def synset_by_id(self, id):
        return self.session.query(Synset).get(id)
    def get_hypernym_graph(self):
        if self.hypernym_graph is None:
            self.hypernym_graph=HypernymGraph(self)
        return self.hypernym_graph
    def get_max_synset_id(self):
        result=self.session.execute('SELECT max(id) FROM synset_table')
        (max_synsetId,)=result.fetchone()
        return max_synsetId


dbs={}
db_urls={}
data_dirs={}
for k,v in get_config_var('germanet').iteritems():
    db_urls[k]=v['db_server']

def get_database(name):
    if name not in dbs:
        dbs[name]=GWN_DB(db_urls[name])
    return dbs[name]


                     
