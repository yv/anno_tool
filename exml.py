#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
import sys
import re
from topsort import topsort
from pytree import tree, export
from alphabet import CPPAlphabet, PythonAlphabet
from ordereddict import OrderedDict
from collections import defaultdict
from itertools import izip, islice
from xml.sax.saxutils import quoteattr,escape
from sqlalchemy import Table, Column, MetaData, \
    Integer, String, Enum, ForeignKey

__doc__="""
konvertiert eine Datei im Negra-Export-Format (Version 3 oder 4)
ins ExportXMLv2-Format.
Koreferenzannotation (als Kommentar mit 'R=') und Lemmas (als Kommentar
mit 'LM=' oder in der Lemmaspalte) werden zu passenden Attributen und/oder
Relationen umgewandelt.

Aufruf:
python exml.py tueba_datei.export > tueba_datei_exml.xml
"""

__version__="2011-12-11"
__author__= "Yannick Versley / Univ. Tuebingen"

def create_id(prefix,alphabet):
    n0=len(alphabet)
    n=n0
    while alphabet['%s%d'%(prefix,n)]<n0:
        n+=1
    return '%s%d'%(prefix,n)

class TextAttribute:
    def __init__(self,name,prop_name=None,default_val=None):
        self.name=name
        if prop_name is None:
            self.prop_name=name
        else:
            self.prop_name=prop_name
        self.default_val=default_val
    def map_attr(self,val,doc):
        if val==self.default_val:
            return None
        return val
    def get_updown(self,obj,doc,result):
        pass
    def describe_schema(self,f):
        open_tag(f,'text-attr',[('name',self.name)],indent=2)
        f.write('/>\n')
    def describe_column(self):
        return Column(self.name, String)

class EnumAttribute(TextAttribute):
    def __init__(self,name,**kw):
        TextAttribute.__init__(self,name,**kw)
        self.alphabet=PythonAlphabet()
        self.descriptions={}
    def add_item(self,name,description=None):
        self.alphabet[name]
        if description is not None:
           self.descriptions[name]=description
    def describe_schema(self,f):
        open_tag(f,'enum-attr',[('name',self.name)],indent=2)
        f.write('>\n')
        for val in self.alphabet.words:
            atts=[('name',val)]
            if val in self.descriptions:
                atts.append(('description',self.descriptions[val]))
            open_tag(f,'val',atts,indent=3)
            f.write('/>\n')
        f.write('  </enum-attr>\n')
    def describe_column(self):
        return Column(self.name, Enum(self.alphabet.words))
        
class RefAttribute:
    def __init__(self,name,prop_name=None,restriction=None,
                 restrict_target=None):
        self.name=name
        if prop_name is None:
            self.prop_name=self.name
        else:
            self.prop_name=prop_name
        if restriction is None or restriction=='none':
            self.restriction=None
        else:
            self.restriction=intern(restriction)
        self.restrict_target=restrict_target
    def map_attr(self,val,doc):
        return doc.get_obj_id(val)
    def get_updown(self,obj,doc,result):
        if self.restriction is 'down':
            other_obj=getattr(obj,self.prop_name)
            if other_obj is not None:
                result.append((doc.get_obj_id(obj),
                               doc.get_obj_id(other_obj)))
        elif self.restriction is 'up':
            other_obj=getattr(obj,self.prop_name)
            if other_obj is not None:
                result.append((doc.get_obj_id(other_obj),
                               doc.get_obj_id(obj)))
    def describe_schema(self,f):
        open_tag(f,'node-ref',[('name',self.name)],indent=2)
        f.write('/>\n')
    def describe_column(self):
        restrict_target=self.restrict_target
        if restrict_target is not None and len(restrict_target)==1:
            foreign_name=restrict_target[0]
            return Column(self.name, Integer,
                          ForeignKey('%s.%s_id'%(foreign_name,foreign_name)))
        return Column(self.name, Integer)
            

class IDRefAttribute:
    def __init__(self,name,prop_name=None,restriction=None,
                 restrict_target=None):
        self.name=name
        if prop_name is None:
            self.prop_name=self.name
        else:
            self.prop_name=prop_name
        if restriction is None or restriction=='none':
            self.restriction=None
        else:
            self.restriction=intern(restriction)
        self.restrict_target=restrict_target
    def map_attr(self,val,doc):
        return val
    def get_updown(self,obj,doc,result):
        if self.restriction is 'down':
            other=getattr(obj,self.prop_name)
            if other_obj is not None:
                result.append((doc.get_obj_id(obj),
                               other))
        elif self.restriction is 'up':
            other=getattr(obj,self.prop_name)
            if other is not None:
                result.append((other,
                               doc.get_obj_id(obj)))
    def describe_schema(self,f):
        open_tag(f,'node-ref',[('name',self.name)],indent=2)
        f.write('/>\n')
    def describe_column(self):
        restrict_target=self.restrict_target
        if restrict_target is not None and len(restrict_target)==1:
            foreign_name=restrict_target[0]
            return Column(self.name, Integer,
                          ForeignKey('%s.%s_id'%(foreign_name,foreign_name)))
        return Column(self.name, Integer)

class MarkableSchema:
    def __init__(self,name,cls=None):
        self.name=name
        self.attributes=[]
        self.edges=[]
        self.cls=cls
        self.locality=None
    def serialize_object(self, obj, doc):
        oid=doc.get_obj_id(obj)
        span=obj.span
        attr_d=OrderedDict()
        attr_d['xml:id']=oid
        for att in self.attributes:
            if hasattr(obj,att.prop_name):
                v=getattr(obj,att.prop_name)
                if v is not None:
                    v_txt=att.map_attr(v,doc)
                    if v_txt is not None:
                        attr_d[att.name]=v_txt
        edges=[]
        for edge_schema in self.edges:
            edgelist=edge_schema.get_edges(obj,doc)
            for edgevals in edgelist:
                attr_e=OrderedDict()
                for (att,val) in izip(edge_schema.attributes,edgevals):
                    if val is not None:
                        attr_e[att.name]=att.map_attr(val,doc)
                edges.append((edge_schema.name,attr_e))
        return (span,self.name,attr_d,edges)
    def get_updown(self,obj,doc,result):
        for att in self.attributes:
            att.get_updown(obj,doc,result)
        for edge in self.edges:
            edge.get_updown(obj,doc,result)
    def describe_schema(self,f,edges):
        attrs=[('name',self.name)]
        if self.locality is not None:
            attrs.append(('locality',self.locality))
        open_tag(f,'node',attrs,1)
        f.write('>\n')
        for att in self.attributes:
            att.describe_schema(f)
        f.write(' </node>\n')
        for edge_schema in self.edges:
            if edge_schema.name not in edges:
                edges[edge_schema.name]=[edge_schema,[self.name]]
            else:
                edges[edge_schema.name][1].append(self.name)
    def describe_table(self, metadata):
        cols=[Column(self.name+'_id', Integer, primary_key=True),
              Column('start', Integer),
              Column('end',Integer)]
        for attr in self.attributes:
            cols.append(attr.describe_column())
        return Table(self.name, metadata, *cols)
    def attribute_by_name(self,name):
        for att in self.attributes:
            if att.name==name:
                return att
        return KeyError(name)

class SecondaryEdges:
    def __init__(self,name):
        self.name=name
        self.alphabet=PythonAlphabet()
        self.attributes=[EnumAttribute('cat'),
                         RefAttribute('parent')]
        self.descriptions={}
    def get_edges(self,obj,doc):
        edges=[]
        if hasattr(obj,'secedge') and obj.secedge is not None:
            for secedge in obj.secedge:
                edges.append([secedge[0],secedge[1]])
        return edges
    def get_updown(self,obj,doc,result):
        pass
    def add_item(self,name,description=None):
        self.alphabet[name]
        if description is not None:
           self.descriptions[name]=description 

def open_tag(f,name,items,indent=0):
    f.write(' '*indent)
    f.write('<%s'%(name,))
    for k,v in items:
        if v is None:
            continue
        f.write(' %s=%s'%(k,quoteattr(v)))


class ChildEdges:
    def __init__(self,name):
        self.name=name
    def put_edges(self,obj,doc,edges):
        for n in obj.children:
            attr_d=OrderedDict()
            attr_d['target']=get_obj_id(n)
            attr_d['label']=n.edge_label
            edges.append((self.name,attr_d))
    def get_updown(self,obj,doc,result):
        obj_id=doc.get_obj_id(obj)
        for n in obj.children:
            result.append((doc.get_obj_id(n),
                           obj_id))

class ReferenceEdges:
    def __init__(self,name):
        self.name=name
        self.attributes=[EnumAttribute('type'),
                         IDRefAttribute('target')]
    def get_edges(self,obj,doc):
        info=getattr(obj,'anaphora_info',None)
        if info is not None:
            tgt=None
            if info[0]!='expletive':
                tgt=' '.join(info[1])
            return [[info[0],tgt]]
        else:
            return []
    def get_updown(self,obj,doc,result):
        pass

class TerminalSchema:
    def __init__(self,name,cls):
        self.name=name
        self.attributes=[]
        self.edges=[]
        self.cls=cls
    def serialize_terminal(self,obj,doc):
        oid=doc.get_obj_id(obj)
        #span=obj.span
        attr_d=OrderedDict()
        attr_d['xml:id']=oid
        for att in self.attributes:
            if hasattr(obj,att.prop_name):
                v=getattr(obj,att.prop_name)
                if v is not None:
                    v_txt=att.map_attr(v,doc)
                    if v_txt is not None:
                        attr_d[att.name]=v_txt
        edges=[]
        for edge_schema in self.edges:
            edgelist=edge_schema.get_edges(obj,doc)
            for edgevals in edgelist:
                attr_e=OrderedDict()
                for (att,val) in izip(edge_schema.attributes,edgevals):
                    if val is not None:
                        attr_e[att.name]=att.map_attr(val,doc)
                edges.append((edge_schema.name,attr_e))
        return (self.name,attr_d,edges)
    def describe_schema(self,f,edges):
        open_tag(f,'tnode',[('name',self.name)],1)
        f.write('>\n')
        for att in self.attributes:
            att.describe_schema(f)
        f.write(' </tnode>\n')
        for edge_schema in self.edges:
            if edge_schema.name not in edges:
                edges[edge_schema.name]=[edge_schema,[self.name]]
            else:
                edges[edge_schema.name][1].append(self.name)
    def attribute_by_name(self,att_name):
        for att in self.attributes:
            if att.name==att_name:
                return att
        raise KeyError(att_name)
    def describe_table(self, metadata):
        cols=[Column(self.name+'_id', Integer, primary_key=True),
              Column('start', Integer)]
        for attr in self.attributes:
            cols.append(attr.describe_column())
        return Table(self.name, metadata, *cols)

class Document:
    def __init__(self,t_schema,schemas):
        self.t_schema=t_schema
        self.schemas=schemas
        self.schema_by_class={}
        self.object_by_id={}
        #self.basedata=BaseData()
        self.words=[]
        self.w_objs=[]
        self.word_attr='word'
        self.markables_by_start=defaultdict(list)
        self.node_objs=defaultdict(list)
        self.word_ids=CPPAlphabet()
        if t_schema.cls is not None:
            self.schema_by_class[t_schema.cls]=t_schema
        for schema in schemas:
            if schema.cls is not None:
                self.schema_by_class[schema.cls]=schema
    def get_obj_id(self,obj):
        if hasattr(obj,'xml_id'):
            return obj.xml_id
        else:
            mlevel=self.mlevel_for_class(type(obj))
            if mlevel is not None:
                n=mlevel.name
            else:
                n='x'
            k='%s_%s'%(n,id(obj))
            obj.xml_id=k
            #obj_by_id[k]=obj
            return k
    def add_terminal(self,w_obj):
        val=self.word_ids[self.get_obj_id(w_obj)]
        assert val==len(self.words),(val,w_obj.xml_id,len(self.words),self.words[val-2:val+2],self.words[-2:])
        self.words.append(getattr(w_obj,self.word_attr))
        self.w_objs.append(w_obj)
    def mlevel_for_class(self,cls):
        try:
            return self.schema_by_class[cls]
        except KeyError:
            for k in cls.__bases__:
                result=self.mlevel_for_class(k)
                if result is not None:
                    return result
        return None
    def reorder_updown(self,objs):
        # 1. extract up/down graph
        # TODO: add precedence for "locality"-type things
        edges=[]
        objs_dict={}
        result=[]
        objs_by_level={}
        edges_len=0
        for (ml,obj) in objs:
            objs_by_level[ml.name]=self.get_obj_id(obj)
        for (ml,obj) in objs:
            obj_id=self.get_obj_id(obj)
            ml.get_updown(obj,self,edges)
            objs_dict[obj_id]=(ml,obj)
            if ml.locality in objs_by_level:
                edges.append((objs_by_level[ml.locality],obj_id))
        # 2. topological sort (of keys)
        for k in topsort(edges):
            if k in objs_dict:
                result.append(objs_dict[k])
                del objs_dict[k]
        result+=objs_dict.values()
        return result
    def register_object(self,obj):
        mlevel=self.mlevel_for_class(type(obj))
        if mlevel is None:
            print self.schema_by_class
            raise ValueError("No markable level for %s (type %s)"%(obj,type(obj)))
        self.markables_by_start[obj.span[0]].append((mlevel,obj))
    def make_span(self,span):
        wids=self.word_ids
        parts=[]
        for start,end in zip(span[::2],span[1::2]):
            if end==start+1:
                parts.append(wids.get_sym(start))
            else:
                parts.append('%s..%s'%(wids.get_sym(start),
                                       wids.get_sym(end-1)))
        return ','.join(parts)
    def get_objects_by_class(self,cls,start=0,end=None):
        if end is None:
            end=len(self.words)
        objs_by_start=self.markables_by_start
        result=[]
        for i in xrange(start,end):
            for (mlevel,obj) in objs_by_start[i]:
                if isinstance(obj,cls):
                    result.append(obj)
        return result
    def write_inline_xml(self,f,start=0,end=None):
        """inline XML serialization"""
        objs_by_start=self.markables_by_start
        if end is None:
            end=len(self.words)
        stack=[]
        for i,n in izip(xrange(start,end),islice(self.w_objs,start,end)):
            # close all tags that must be closed here
            while stack and i==stack[-1][1]:
                f.write(' '*(len(stack)-1))
                f.write('</%s>\n'%(stack[-1][0],))
                stack.pop()
            assert (not stack or stack[-1][1]>i),(i,stack)
            #find all markables starting here
            o_here=objs_by_start[i]
            o_here.sort(key=lambda (mlevel,obj):-obj.span[-1])
            j=0
            last_o=len(o_here)-1
            m_here=[]
            while j<last_o:
                end_here=o_here[j][1].span[-1]
                if end_here==o_here[j+1][1].span[-1]:
                    # perform sort by endpoint and topological
                    # sort for coextensive up/down relationships
                    j1=j+1
                    while j1<=last_o and end_here==o_here[j1][1].span[-1]:
                        j1+=1
                    for mlevel,obj in self.reorder_updown(o_here[j:j1]):
                        m_here.append(mlevel.serialize_object(obj,self))
                    j=j1
                else:
                    mlevel,obj=o_here[j]
                    m_here.append(mlevel.serialize_object(obj,self))
                    j+=1
            while j<len(o_here):
                (mlevel,obj)=o_here[j]
                m_here.append(mlevel.serialize_object(obj,self))
                j+=1
            for m in m_here:
                need_span=False
                endpoint=m[0][-1]
                if len(m[0])>2:
                    need_span=True
                    if stack and m[0][-1]>stack[-1][1]:
                        endpoint=stack[-1][1]
                elif stack and m[0][-1]>stack[-1][1]:
                    need_span=True
                    endpoint=stack[-1][1]
                if need_span:
                    m[2]['span']=self.make_span(m[0])
                open_tag(f,m[1],m[2].iteritems(),len(stack))
                f.write('>\n')
                for e in m[3]:
                    open_tag(f,e[0],e[1].iteritems(),len(stack)+1)
                    f.write('/>\n')
                stack.append((m[1],endpoint))
            t_desc=self.t_schema.serialize_terminal(n,self)
            open_tag(f,t_desc[0],t_desc[1].iteritems(),len(stack))
            if t_desc[2]:
                f.write('>\n')
                for e in t_desc[2]:
                    open_tag(f,e[0],e[1].iteritems(),len(stack)+1)
                    f.write('/>\n')
                f.write(' '*(len(stack)))
                f.write('</%s>\n'%(t_desc[0],))
            else:
                f.write('/>\n')
        # finally, close everything else
        while stack:
            x=stack.pop()
            f.write(' '*(len(stack)-1))
            f.write('</%s>\n'%(x[0],))
    def write_graph_xml(self,f):
        """graph XML serialization"""
        assert False
    def clear_markables(self, start=0, end=None):
        if end is None:
            end=len(self.words)
        mbs=self.markables_by_start
        for i in xrange(start,end):
            if i in mbs:
                del mbs[i]
            self.w_objs[i]=None
    def describe_schema(self,f):
        edge_descrs={}
        f.write("<schema>\n")
        self.t_schema.describe_schema(f,edge_descrs)
        for schema in self.schemas:
            schema.describe_schema(f,edge_descrs)
        for (name,(schema,parents)) in edge_descrs.iteritems():
            open_tag(f,"edge", [('name',name),('parent','|'.join(parents))])
            f.write('>\n')
            for att in schema.attributes:
                att.describe_schema(f)
            f.write('</edge>\n')
        f.write("</schema>\n")
    def make_metadata(self):
        meta=MetaData()
        self.t_schema.describe_table(meta)
        for schema in self.schemas:
            schema.describe_table(meta)
        return meta

def assign_node_ids(n,prefix,sent_start=0):
    n.span=[n.start+sent_start,n.end+sent_start]
    if hasattr(n,'xml_id'):
        pass
    elif hasattr(n,'id'):
        n.xml_id='%s_%s'%(prefix,n.id)
    for n1 in n.children:
        assign_node_ids(n1,prefix,sent_start)

class GenericMarkable(object):
    def __init__(self, **kw):
        self.__dict__.update(kw)
    
class Text(GenericMarkable):
    pass

class NamedEntity(object):
    def __init__(self,kind,**kw):
        self.kind=kind
        self.__dict__.update(kw)

def make_syntax_doc():
    text_schema=MarkableSchema('text',Text)
    text_schema.attributes=[TextAttribute('origin')]
    s_schema=MarkableSchema('sentence',tree.Tree)
    s_schema.locality='text'
    nt_schema=MarkableSchema('node',tree.NontermNode)
    nt_schema.locality='sentence'
    secedge_edge=SecondaryEdges('secEdge')
    relation_edge=ReferenceEdges('relation')
    func_attr=EnumAttribute('func',prop_name='edge_label')
    nt_schema.attributes=[EnumAttribute('cat'),
                          func_attr,
                          RefAttribute('parent',restriction='up',
                                       restrict_target=['node']),
                          TextAttribute('comment')]
    nt_schema.edges=[secedge_edge,
                     relation_edge]
    ne_schema=MarkableSchema('ne',NamedEntity)
    ne_schema.locality='sentence'
    ne_schema.attributes=[EnumAttribute('type',prop_name='kind')]
    ne_schema.attributes[0].add_item('PER','Person')
    ne_schema.attributes[0].add_item('ORG','Organisation')
    ne_schema.attributes[0].add_item('GPE','Gebietskörperschaft')
    ne_schema.attributes[0].add_item('LOC','Ort')
    ne_schema.attributes[0].add_item('OTH','andere Eigennamen')
    t_schema=TerminalSchema('word',tree.TerminalNode)
    t_schema.attributes=[TextAttribute('form',prop_name='word'),
                         EnumAttribute('pos',prop_name='cat'),
                         EnumAttribute('morph',default_val='--'),
                         TextAttribute('lemma',default_val='--'),
                         func_attr,
                         RefAttribute('parent',restriction='up',
                                      restrict_target=['node']),
                         TextAttribute('comment')]
    t_schema.edges=[secedge_edge,
                    relation_edge]
    return Document(t_schema,[s_schema,nt_schema,text_schema,ne_schema])

def make_noderef(x):
    sentid,nodeid=x.split(':')
    try:
        nid=int(nodeid)
    except ValueError:
        return 's%s_%s'%(sentid,nodeid)
    else:
        if nid<500:
            nid+=1
        return 's%s_%d'%(sentid,nid)

def comments_to_relations(t):
    for n in t.terminals+t.node_table.values():
        cm=getattr(n,'comment',None)
        if cm is not None and 'R=' in cm:
            attrs=export.comment2attrs(cm)
            ana_info=attrs['R']
            if '.' in ana_info:
                rel,tgt=ana_info.split('.')
                targets=[make_noderef(x) for x in tgt.split(',')]
            else:
                rel=ana_info
                targets=None
            n.anaphora_info=(rel,targets)
            del attrs['R']
            if attrs:
                n.comment=export.attrs2comment(attrs)
            else:
                n.comment=None

def lemmas_from_comments(t):
    for n in t.terminals:
        cm=getattr(n,'comment',None)
        if cm is not None and 'LM=' in cm:
            attrs=export.comment2attrs(cm)
            n.lemma=attrs['LM']
            del attrs['LM']
            if attrs:
                n.comment=export.attrs2comment(attrs)
            else:
                n.comment=None
def make_parts(xs,offset=0):
    spans=[]
    current=None
    for x in xs:
        if current:
            if current[1]==x:
                current[1]=x+1
            else:
                spans.append(current[0]+offset)
                spans.append(current[1]+offset)
                current=[x,x+1]
        else:
            current=[x,x+1]
    if current:
        spans.append(current[0]+offset)
        spans.append(current[1]+offset)
    return spans

def remove_ne_holes(nodes,spanset,is_head):
    for n in nodes:
        n_head = (is_head and n.edge_label=='HD')
        if '-NE' in n.edge_label:
            spanset.difference_update(xrange(n.start,n.end))
        if '=' in n.cat and not n_head:
            continue
        if not n.isTerminal():
            remove_ne_holes(n.children,spanset,n_head)

def nodes_to_ne(t):
    all_nes=[]
    # extract NE information
    for n in t.topdown_enumeration():
        if '=' in n.cat:
            idx=n.cat.index('=')
            kind=n.cat[idx+1:]
            ne_span=set(xrange(n.start,n.end))
            remove_ne_holes(n.children,ne_span,True)
            for n_punct in t.terminals:
                if (n_punct.cat in ['$(','$,','$.'] and
                    n_punct.start in ne_span and
                    (n_punct.start-1 not in ne_span or
                     n_punct.start+1 not in ne_span)):
                    ne_span.discard(n_punct.start)
            all_nes.append((kind,make_parts(sorted(ne_span))))
    t.all_nes=all_nes
    # remove all NE stuff from labels and edges
    for n in t.topdown_enumeration():
        if '=' in n.cat:
            idx=n.cat.index('=')
            n.cat=n.cat[:idx]
        if n.edge_label=='-NE':
            n.edge_label='-'
        
def add_tree_to_doc(t,ctx):
    sent_start=len(ctx.words)
    comments_to_relations(t)
    lemmas_from_comments(t)
    nodes_to_ne(t)
    if hasattr(t,'sent_no'):
        prefix='s%s'%(t.sent_no,)
        t.xml_id=prefix
        for i,n in enumerate(t.terminals):
            n.xml_id='%s_%d'%(prefix,i+1)
        for n in t.roots:
            assign_node_ids(n,prefix,sent_start)
    if hasattr(t,'all_nes'):
        last_num=defaultdict(int)
        suffixes=['','a','b','c','d']
        for kind, local_span in t.all_nes:
            ne=NamedEntity(kind)
            ne.span=[k+sent_start for k in local_span]
            ne_start=ne.span[0]
            suff=suffixes[last_num[ne_start]]
            last_num[ne_start]+=1
            ne.xml_id='ne_%s%s'%(ne_start,suff)
            ctx.register_object(ne)
    for n in t.terminals:
        ctx.add_terminal(n)
    t.span=[sent_start,sent_start+len(t.terminals)]
    ctx.register_object(t)
    for n in t.node_table.values():
        ctx.register_object(n)

bot_re=re.compile('^#BOT ([A-Z]+)')
class ExportCorpusReader:
    """CorpusReader implementation for reading Negra-Export files"""
    def __init__(self, doc, fname):
        self.doc=doc
        t_schema=doc.t_schema
        nt_schema=doc.schemas[1]
        tables={
            'WORDTAG':t_schema.attribute_by_name('pos'),
            'MORPHTAG':t_schema.attribute_by_name('morph'),
            'NODETAG':nt_schema.attribute_by_name('cat'),
            'EDGETAG':nt_schema.attribute_by_name('func'),
            'SECEDGETAG':nt_schema.edges[0].attributes[0]
        }
        reftypes=nt_schema.edges[1].attributes[0]
        reftypes.add_item('anaphoric','Anaphorisches Pronomen')
        reftypes.add_item('cataphoric','Kataphorisches Pronomen')
        reftypes.add_item('coreferential','Diskurs-altes nicht-Pronomen')
        self.origins={}
        where=None
        self.fmt=3
        self.f=file(fname)
        while True:
            old_pos=self.f.tell()
            l=self.f.readline()
            if l.strip()=='#FORMAT 4':
                self.fmt=4
            m=bot_re.match(l)
            if m:
                where=m.group(1)
            elif l.startswith('#EOT'):
                where=None
            elif where and where in tables:
                line=l.strip().split(None,2)
                if len(line)<3:
                    comment=''
                else:
                    comment=line[2]
                tables[where].add_item(line[1],comment)
            elif where=='ORIGIN':
                line=l.strip().split(None,2)
                self.origins[line[0]]=line[1]
            if l.startswith('#BOS'):
                self.f.seek(old_pos)
                break
        self.doc_no=None
        self.origin_markable=None
    def addNext(self):
        """
        Reads in the next unit of the document.
        Returns the last token offset for which all
        markables are guaranteed to be read.
        """
        while True:
            l=self.f.readline()
            if l=='':
                raise StopIteration()
            m=export.bos_pattern.match(l)
            if m:
                sent_no=m.group(1)
                doc_no=m.group(2)
                t=export.read_sentence(self.f,self.fmt)
                t.sent_no=sent_no
                t.doc_no=doc_no
                t.comment=m.group(3)
                if t.comment:
                    t.comment=t.comment.lstrip()
                self.do_add(t)
                return self.last_stop
    def do_add(self,t):
        if self.doc_no==t.doc_no:
            self.origin_markable.span[-1]+=len(t.terminals)
        else:
            self.last_stop=len(self.doc.words)
            origin_markable=Text(origin=self.origins.get(t.doc_no))
            origin_markable.span=[len(self.doc.words),
                                  len(self.doc.words)+len(t.terminals)]
            origin_markable.xml_id='text_%s'%(t.doc_no,)
            self.doc.register_object(origin_markable)
            self.origin_markable=origin_markable
            self.doc_no=t.doc_no
        t.determine_tokenspan_all()
        add_tree_to_doc(t,self.doc)
 
if __name__=='__main__':
    doc=make_syntax_doc()
    if len(sys.argv)<=1:
        print >>sys.stderr, __doc__
        sys.exit(1)
    fname=sys.argv[1]
    reader=ExportCorpusReader(doc,fname)
    print '<?xml version="1.0" encoding="ISO-8859-15"?>'
    print '<exml-doc>'
    doc.describe_schema(sys.stdout)
    # do the actual conversion
    print '<body serialization="inline">'
    last_stop=len(doc.words)
    while True:
        try:
            new_stop=reader.addNext()
            if (new_stop!=last_stop):
                doc.write_inline_xml(sys.stdout,last_stop,new_stop)
                doc.clear_markables(last_stop,new_stop)
                last_stop=new_stop
        except StopIteration:
            break
    doc.write_inline_xml(sys.stdout,last_stop)
    print '</body>'
    print '</exml-doc>'
