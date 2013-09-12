from pytree import tree
from pytree.exml import make_syntax_doc, TerminalSchema, \
     EnumAttribute, TextAttribute, RefAttribute, \
     Topic, EduRange, Edu, Text, \
     Document, GenericMarkable, MarkableSchema

__all__=['DiscRel', 'DiscRelEdges', 'ConnectiveEdges', 'make_konn_doc', 'make_implicit_doc']

rel_map={
    'evaluative':'antithesis',
    'epistemic_cause':'evidence'
    }

def get_rel(info,which):
    k=getattr(info,which,None)
    if k in rel_map:
        k=rel_map[k]
    if k=='NULL':
        k=None
    return k

class ConnectiveEdges:
    def __init__(self,name):
        self.name=name
        self.attributes=[TextAttribute('konn'),
                         EnumAttribute('rel1'),
                         EnumAttribute('rel2')]
        for att in [self.attributes[1], self.attributes[2]]:
            att.add_item('Temporal','temporal contiguity')
            att.add_item('cause','strong causal relation')
            att.add_item('enable','weak causal relation')
            att.add_item('evidence','argumentative reasoning')
            att.add_item('speech_act','circumstances for a speech act (causal)')
            att.add_item('Result','causal relation (underspecified)')
            att.add_item('Comparison','comparison relation (underspecified)')
            att.add_item('parallel','parallel')
            att.add_item('contrast','contrast')
            att.add_item('Condition','conditional')
            att.add_item('NonFactual','counterfactual bevor')
            att.add_item('Concession','concessive relation (underspecified)')
            att.add_item('contraexpectation','denial-of-expectation')
            att.add_item('antithesis','antithesis/Bewertungskontrast')
    def get_edges(self,obj,doc):
        info=getattr(obj,'konn_rel',None)
        if info is not None:
            konn=getattr(info,'word',obj.lemma.decode('ISO-8859-15')).encode('ISO-8859-15')
            rel1=get_rel(info,'rel1')
            rel2=get_rel(info,'rel2')
            return [[konn,rel1,rel2]]
        else:
            return []
    def get_updown(self,obj,doc,result):
        pass

class DiscRel(GenericMarkable):
    def __init__(self,label,target,marking=None):
        self.label=label
        self.marking=marking
        self.target=target

class DiscRelEdges(object):
    def __init__(self,name):
        self.name=name
        self.attributes=[EnumAttribute('relation'),
                         EnumAttribute('marking'),
                         RefAttribute('arg2')]
    def get_edges(self,obj,doc):
        edges=[]
        if hasattr(obj,'rels') and obj.rels is not None:
            for rel in obj.rels:
                edges.append((rel.label,rel.marking,rel.target))
        return edges
    def set_edges(self,obj,vals,doc):
        rels=[]
        for lbl,mark,tgt in vals:
            rels.append(DiscRel(lbl,tgt,mark))
        obj.rels=rels
    def get_updown(self,obj,doc,result):
        pass

def make_konn_doc():
    doc=make_syntax_doc()
    discrel_edge=DiscRelEdges('discRel')
    topic_schema=MarkableSchema('topic',Topic)
    topic_schema.attributes=[TextAttribute('description')]
    topic_schema.locality='text'
    topic_schema.edges=[discrel_edge]
    edu_range_schema=MarkableSchema('edu-range',EduRange)
    edu_range_schema.locality='text'
    edu_range_schema.edges=[discrel_edge]
    edu_schema=MarkableSchema('edu',Edu)
    edu_schema.locality='sentence'
    edu_schema.edges=[discrel_edge]
    doc.add_schemas([edu_schema,topic_schema,edu_range_schema])
    doc.t_schema.edges.append(ConnectiveEdges('connective'))
    doc.t_schema.attributes+=[RefAttribute('dephead',prop_name='syn_parent'),
                              EnumAttribute('deprel',prop_name='syn_label'),
                              TextAttribute('lexUnit',prop_name='lex_unit')]

    return doc

def make_implicit_doc():
    text_schema=MarkableSchema('text',Text)
    text_schema.attributes=[TextAttribute('origin')]
    s_schema=MarkableSchema('sentence',tree.Tree)
    s_schema.locality='text'
    discrel_edge=DiscRelEdges('discRel')
    topic_schema=MarkableSchema('topic',Topic)
    topic_schema.attributes=[TextAttribute('description')]
    topic_schema.locality='text'
    topic_schema.edges=[discrel_edge]
    edu_range_schema=MarkableSchema('edu-range',EduRange)
    edu_range_schema.locality='text'
    edu_range_schema.edges=[discrel_edge]
    edu_schema=MarkableSchema('edu',Edu)
    edu_schema.locality='sentence'
    edu_schema.edges=[discrel_edge]
    t_schema=TerminalSchema('word',tree.TerminalNode)
    t_schema.attributes=[TextAttribute('form',prop_name='word'),
                         EnumAttribute('pos',prop_name='cat'),
                         EnumAttribute('morph',prop_name='morph'),
                         EnumAttribute('lemma',prop_name='lemma'),
                         RefAttribute('dephead',prop_name='syn_parent'),
                         EnumAttribute('deprel',prop_name='syn_label')]
    return Document(t_schema,[text_schema,s_schema,
                                   edu_schema,topic_schema,edu_range_schema])                
