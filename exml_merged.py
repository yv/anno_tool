import sys
from annodb.database import get_corpus
import exml
from exml import ExportCorpusReader, make_syntax_doc, EnumAttribute, TextAttribute, \
     Topic, EduRange, Edu
from exml_implicit import DiscRelEdges, parse_relations

task_names=(['task_waehrend%s_new'%(k,) for k in xrange(1,11)]+
    ['task_nachdem%s_new'%(k,) for k in xrange(1,8)]+
    ['task_bevor_%s'%(k,) for k in xrange(1,3)]+
    ['task_als_r6_%s'%(k,) for k in xrange(3,6)]+
    ['task_alsA_new','task_aberA_new','task_aber_R6_1','task_aber_R6_2',
     'task_bevor_new','task_bevor_1','task_bevor_2','task_bevor_3','task_seitdem_1','task_sobald_1',
     'task_und_r6_1','task_und_r6_2','task_und_r6_3','task_und_r6_4','task_und_r6_5','task_und_r6_6'])

annotators=['melike','anna','stefanie','sabrina','yannick']

discourse_user='nadine'
#discourse_user='*gold*'

rel_map={
    'evaluative':'antithesis',
    'epistemic_cause':'evidence'
    }

def get_rel(info,which):
    k=info.get(which,None)
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
            konn=info.get('word',obj.lemma.decode('ISO-8859-15')).encode('ISO-8859-15')
            rel1=get_rel(info,'rel1')
            rel2=get_rel(info,'rel2')
            return [[konn,rel1,rel2]]
        else:
            return []
    def get_updown(self,obj,doc,result):
        pass


class MergedCorpusReader(ExportCorpusReader):
    def __init__(self, doc, export_fname, corpus_name):
        ExportCorpusReader.__init__(self,doc,export_fname)
        db=get_corpus(corpus_name)
        self.db=db
        self.sentences=db.corpus.attribute("s",'s')
        self.words=db.words
        self.deprel=db.corpus.attribute("deprel","p")
        self.attach=db.corpus.attribute("attach","p")
        self.discourse=db.db.discourse
        tasks=[self.db.get_task(x) for x in task_names]
        self.spans=sorted(set([tuple(span) for task in tasks if task is not None for span in task.spans]))
        print >>sys.stderr, "%d spans found"%(len(self.spans),)
        self.span_idx=0
    def addNext(self):
        old_start=len(self.doc.words)
        new_stop=ExportCorpusReader.addNext(self)
        new_start=len(self.doc.words)
        while self.span_idx<len(self.spans) and self.spans[self.span_idx][0]<new_stop:
            span=self.spans[self.span_idx]
            #print "MCR span:",span
            assert self.db.words[span[0]]==self.doc.words[span[0]],(span[0],self.db.words[span[0]],self.doc.words[span[0]])
            for a_name in annotators:
                anno=self.db.get_annotation(a_name,'konn2',span)
                if anno is not None and 'rel1' in anno or 'comment' in anno:
                    break
            if 'rel1' not in anno or anno.rel1=='NULL':
                self.span_idx+=1
                continue
            #print "MCR anno:",anno.keys()
            self.doc.w_objs[span[0]].konn_rel=anno
            self.span_idx+=1
        for i in xrange(old_start,new_start):
            n=self.doc.w_objs[i]
            n.syn_label=self.deprel[i]
            tok_attach=self.attach[i]
            if tok_attach!='ROOT':
                try:
                    n.syn_parent=self.doc.w_objs[i+int(tok_attach)]
                except IndexError,e:
                    print >>sys.stderr, n.word, tok_attach, i
        
        return new_stop
    def on_text(self, text_markable):
        t_id=text_markable.doc_no
        disc=list(self.discourse.find({'_user':discourse_user,'_docno':int(text_markable.doc_no)}))
        if not disc:
            return
        print >>sys.stderr, "found discourse:", text_markable.doc_no
        ctx=self.doc
        ctx_start=text_markable.span[0]
        ctx_len=text_markable.span[-1]-text_markable.span[0]
        doc=disc[0]
        sentences=doc['sentences']
        edus=doc['edus']
        nonedu=doc.get('nonedu',{})
        tokens=doc['tokens']
        topics=doc.get('topics',[])
        for i in xrange(len(topics)):
            start=topics[i][0]
            try:
                end=topics[i+1][0]
            except IndexError:
                end=ctx_len
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



def make_konn_doc():
    doc=make_syntax_doc()
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
    doc.add_schemas([edu_schema,topic_schema,edu_range_schema])
    doc.t_schema.edges.append(ConnectiveEdges('connective'))
    doc.t_schema.attributes+=[exml.RefAttribute('dephead',prop_name='syn_parent'),
                              exml.EnumAttribute('deprel',prop_name='syn_label')]

    return doc

def main(export_fname, corpus_name):
    doc=make_konn_doc()
    reader=MergedCorpusReader(doc,export_fname,corpus_name)
    print '<?xml version="1.0" encoding="ISO-8859-15"?>'
    print '<exml-doc>'
    doc.describe_schema(sys.stdout)
    # do the actual conversion
    print '<body serialization="inline">'
    last_stop=len(doc.words)
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

if __name__=='__main__':
    main(sys.argv[1],sys.argv[2])
