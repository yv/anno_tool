#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
import sys
import simplejson as json
import exml
import exml_merged
import get_features
import optparse
from pytree.tree import Tree
from dist_sim.fcomb import InfoNode, InfoTree
from collections import defaultdict
from exml import ExportCorpusReader, make_syntax_doc, EnumAttribute, TextAttribute, \
     Topic, EduRange, Edu
from sem_features import get_productions
import sentiment

wanted_features=['csubj','mod','lex','tmp','neg','punc','lexrel','wordpairsA','productionsA','istatusG','puncG']

disc_map=get_features.make_hier_schema(file('disc_schema.txt'))
for x in ['Speechact','Cause','Enable','Epistemic']:
    disc_map['Explanation-'+x]=disc_map['Explanation-'+x.lower()]
    disc_map['Result-'+x]=disc_map['Result-'+x.lower()]
disc_map['RestatementC']=disc_map['Restatement']
disc_map['CommentaryC']=disc_map['Commentary']
disc_map['ContinuationQ']=disc_map['Continuation']
disc_map['InstanceV']=disc_map['Instance']
disc_map['ParallelV']=disc_map['Parallel']
disc_map['Result-Spreechact']=disc_map['Result-speechact']

def get_unmarked_relations(doc,edu):
    by_target=defaultdict(list)
    for rel in edu.rels:
        if rel.marking:
            marking=rel.marking.split('|')
        else:
            marking='???'
        by_target[rel.target.xml_id].append([disc_map[rel.label],marking,edu,rel.target])
    return [[[x[0] for x in xs]]+xs[0][1:] for xs in by_target.itervalues()]

def span2nodes(doc,span):
    start,end0=span
    result=[]
    end=end0
    while end>start+1 and doc.w_objs[end-1].cat in ['$(','$.','$,']:
        print >>sys.stderr, "Cut: %s"%(doc.w_objs[end-1])
        end-=1
    while start<end:
        n0=doc.w_objs[start]
        if n0.cat in ['KON','$(','$.','$,']:
            start+=1
            continue
        n=parent=n0.parent
        while parent and parent.span[0]>=start and parent.span[1]<=end:
            n=parent
            parent=parent.parent
        if parent and n.span[1]<end and n.cat in ['VF','LK','MF'] and parent.cat in ['SIMPX','R-SIMPX','FKONJ']:
            n=parent
        elif n.cat in ['VF','NF'] and len(n.children)==1:
            n=n.children[0]
        result.append(n)
        start=n.span[1]
    return result

def extract_bigrams(prefix,attr,terms,want_unigram=True):
    if want_unigram:
        result=[prefix+getattr(n,attr) for n in terms]
    else:
        result=[]
    if not terms:
        return result
    last_w=getattr(terms[0],attr)
    for i in xrange(1,len(terms)):
        next_w=getattr(terms[i],attr)
        result.append('%s%s_%s'%(prefix,last_w,next_w))
        last_w=next_w
    return result

ignore_pos=['NN','NE','VVFIN','VVINF','VVIZU','VVPP']

def ling_features(terminals,nodes,exclude,prefix):
    result=[]
    neg_nodes=[]; get_features.gather_negation(terminals, neg_nodes)
    if neg_nodes:
        result.append('%s_N+'%(prefix,))
    else:
        result.append('%s_N-'%(prefix,))
    # adjunct types
    adj=defaultdict(list)
    get_features.gather_adjuncts(nodes,adj,exclude)
    for x in adj:
        result.append('%s_adj_%s'%(prefix,x))
    # heads
    for n in nodes:
        if n.cat in ['SIMPX','R-SIMPX','FKOORD','FKONJ']:
            (p,flags)=get_features.get_verbs(n)
            result.append('%sL%s'%(prefix,p))
            for k in flags:
                result.append('%sTF%s'%(prefix,k))
    # sentiment tags
    sent_tags=set()
    for n in terminals:
        tag=sentiment.terminal_tag(n)
        if tag is not None:
            sent_tags.add(tag[1])
    if '+' in sent_tags:
        if '-' in sent_tags:
            pol_tag='AMB'
        else:
            pol_tag='POS'
    elif '-' in sent_tags:
        pol_tag='NEG'
    else:
        pol_tag='NIL'
    if neg_nodes or '~' in sent_tags:
        pol_tag+='-NEG'
    result.append('%spol%s'%(prefix,pol_tag))
    return result

def make_infotree(nodes1,nodes2,terminals2):
    ti=InfoTree()
    nodes=[]
    last_node=None
    for n in nodes1:
        if n.cat in ['SIMPX','R-SIMPX','FKONJ']:
            ni=get_features.make_simple_tree(n,nodes2,terminals2)
        else:
            kind,feats=get_features.munge_single_phrase(n)
            ni=InfoNode('FRAG',feats)
        if last_node is not None:
            last_node.add_edge(ni,'frag')
        nodes.append(ni)
        last_node=ni
    for ni in nodes:
        ti.add_node(ni,True)
    return ti.as_json()

def connection_features(terminals1, nodes1, terminals2, nodes2):
    last_nodes1=nodes1[-1]
    last_nodes1_parent=last_nodes1.parent
    if (last_nodes1_parent and last_nodes1_parent.cat=='VF' and
        last_nodes1_parent.parent in nodes2):
        return ['conVF']
    last_nodes2=nodes2[-1]
    last_nodes2_parent=last_nodes2.parent
    if (last_nodes2_parent and last_nodes2_parent.cat=='VF' and
        last_nodes2_parent.parent in nodes1):
        return ['conVFi']
    first_nodes2=nodes2[0]
    first_nodes2_parent=first_nodes2.parent
    if (first_nodes2_parent and first_nodes2_parent.cat=='NF' and
        first_nodes2_parent.parent in nodes1):
        return ['conNF']
    start1=terminals1[0].span[0]
    start2=terminals2[0].span[0]
    if terminals1[0].span[0] > terminals2[0].span[0]:
        return [x+'i' for x in connection_features(terminals2, nodes2, terminals1, nodes1)]
    end1=terminals1[-1].span[1]
    end2=terminals2[-1].span[1]
    print start1,end1,start2,end2
    if end1==start2:
        return ['conME']
    elif end1 < start2:
        return ['conBE']
    elif start1 < start2 and end2 < end1:
        return ['conDU']
    assert False

def extract_features(terminals1,terminals2,nodes1,nodes2):
    # linguistic features
    feat_bl=ling_features(terminals1,nodes1,nodes2,'1')
    feat_bl+=ling_features(terminals2,nodes2,nodes1,'2')
    get_features.lexrel_features_1(terminals1,terminals2, feat_bl)
    feat_bl+=connection_features(terminals1,nodes1,terminals2,nodes2)
    # Sporleder & Lascarides shallow bigrams
    feat_sl08=extract_bigrams('1w','word',terminals1)
    feat_sl08+=extract_bigrams('2w','word',terminals2)
    feat_sl08+=extract_bigrams('1l','lemma',terminals1)
    feat_sl08+=extract_bigrams('2l','lemma',terminals2)
    feat_sl08+=extract_bigrams('1v','lemma',[n for n in terminals1 if n.cat[0]=='V'])
    feat_sl08+=extract_bigrams('2v','lemma',[n for n in terminals2 if n.cat[0]=='V'])
    feat_sl08+=extract_bigrams('1c','cat',terminals1,False)
    feat_sl08+=extract_bigrams('2c','cat',terminals2,False)
    # Lin et al.'s word pairs / productions
    feat_wp=['wp_%s_%s'%(n1.word,n2.word)
             for n1 in terminals1
             if n1.cat not in ignore_pos
             for n2 in terminals2
             if n2.cat not in ignore_pos]
    feat_prod=[]
    lst1=[]
    lst2=[]
    for n in nodes1:
        get_productions(n,nodes2,lst1)
    for n in nodes2:
        get_productions(n,nodes1,lst2)
    prods1=set(lst1)
    prods2=set(lst2)
    for k in prods1:
        if k in prods2:
            feat_prod.append('prB%s'%(k,))
        else:
            feat_prod.append('prM%s'%(k,))
    for k in prods2:
        if k not in prods1:
            feat_prod.append('prS%s'%(k,))    
    features=[feat_bl,feat_sl08, feat_wp, feat_prod]
    return features

def extract_trees(nodes1,nodes2,terminals1,terminals2):
    get_features.mark_nodes(nodes1,nodes2)
    result=[make_infotree(nodes1,nodes2,terminals2),
            make_infotree(nodes2,nodes1,terminals1)]
    get_features.unmark_nodes(nodes1,nodes2)
    return result

def do_stuff(doc,last_stop,new_stop):
    for t in doc.get_objects_by_class(Tree,last_stop,new_stop):
        get_features.stupid_head_finder(t)
    result=[]
    for n in doc.w_objs[last_stop:new_stop]:
        if hasattr(n,'konn_rel'):
            anno=n.konn_rel
            if 'rel1' not in anno or anno.rel1 in ['NULL','##','']: continue
            sub_cl,main_cl=get_features.find_args(n)
            if sub_cl is None or main_cl is None:
                continue
            print >>sys.stderr, n.lemma, get_features.get_target(n.konn_rel)
            idxs1=set(xrange(sub_cl.span[0],sub_cl.span[1]))
            idxs2=set(xrange(main_cl.span[0],main_cl.span[1]))
            idxs2.difference_update(idxs1)
            terminals1=[doc.w_objs[i] for i in sorted(idxs1)]
            terminals2=[doc.w_objs[i] for i in sorted(idxs2)]
            print >>sys.stderr, "SUB: ",' '.join([x.word for x in terminals1])
            print >>sys.stderr, "MAIN:",' '.join([x.word for x in terminals2])
            spans=n.span+[['arg1']+sub_cl.span,['arg2']+main_cl.span]
            result.append(['konn',n.lemma,get_features.get_target(n.konn_rel),
                           extract_features(terminals1,terminals2,[sub_cl],[main_cl]),
                           extract_trees([sub_cl],[main_cl],terminals1,terminals2),
                           spans])
    disc_rels=[]
    for edu in doc.get_objects_by_class(Edu,last_stop,new_stop):
        disc_rels+=get_unmarked_relations(doc,edu)
    for edu_range in doc.get_objects_by_class(EduRange, last_stop, new_stop):
        disc_rels+=get_unmarked_relations(doc,edu_range)
    for rel in disc_rels:
        label,marking,arg1,arg2=rel
        print >>sys.stderr, marking, label
        idxs1=set(xrange(arg1.span[0],arg1.span[1]))
        idxs2=set(xrange(arg2.span[0],arg2.span[1]))
        if idxs1.issubset(idxs2):
            idxs2.difference_update(idxs1)
        elif idxs2.issubset(idxs1):
            idxs1.difference_update(idxs2)
        terminals1=[doc.w_objs[i] for i in sorted(idxs1)]
        terminals2=[doc.w_objs[i] for i in sorted(idxs2)]
        print >>sys.stderr, "ARG1:",' '.join([n.word for n in terminals1])
        nodes1=span2nodes(doc,arg1.span)
        for node in nodes1:
            print >>sys.stderr, node.to_penn()
        print >>sys.stderr, "ARG2:",' '.join([n.word for n in terminals2])
        nodes2=span2nodes(doc,arg2.span)
        for node in nodes2:
            print >>sys.stderr, node.to_penn()
        spans=[min(arg1.span[0],arg2.span[0]),max(arg1.span[1],arg2.span[1]),
               ['arg1']+list(arg1.span),
               ['arg2']+list(arg2.span)]
        if marking[0]=='-':
            stuff=[label,
                   extract_features(terminals1,terminals2,nodes1,nodes2),
                   extract_trees(nodes1,nodes2,terminals1,terminals2),
                   spans]
            if len(marking)==1:
                result.append(['drel','-']+stuff)
            result.append(['drel','x']+stuff)
    return result

class JSONOutput:
    def __init__(self,opts=None):
        self.files={}
        if opts is None:
            self.opts=object()
            self.opts.fprefix=''
        else:
            self.opts=opts
    def add_explicit(self, conn, fname=None):
        if fname is None:
            fname=conn
        self.files[conn]=file('%s%s_exml.json'%(opts.fprefix,fname),'w')
    def add_implicit(self, conn, fname=None):
        if fname is None:
            fname=conn
        self.files[conn]=file('%s%s_exml.json'%(opts.fprefix,fname),'w')
    def handle_stuff(self, stuff):
        for kind, marker, label, features, trees, span in stuff:
            if marker in self.files:
                f=self.files[marker]
                print >>f, json.dumps([0,{'_type':'multipart','parts':features,
                                          'trees': trees},
                                       label,span],encoding='ISO-8859-15')
    def close(self):
        for f in self.files.itervalues():
            f.close()
        self.files=None
                                      

def main(export_fname, corpus_name,opts):
    handler=JSONOutput(opts)
    handler.add_explicit('während','waehrend')
    handler.add_explicit('nachdem')
    handler.add_explicit('als')
    handler.add_implicit('-','unmarked')
    handler.add_implicit('x','unmarked_all')
    get_features.wanted_features=wanted_features
    get_features.do_initialization(wanted_features,corpus_name)
    doc=exml_merged.make_konn_doc()
    reader=exml_merged.MergedCorpusReader(doc,export_fname,corpus_name)
    last_stop=len(doc.words)
    while True:
        try:
            new_stop=reader.addNext()
            if (new_stop!=last_stop):
                stuff=do_stuff(doc,last_stop,new_stop)
                handler.handle_stuff(stuff)
                doc.clear_markables(last_stop,new_stop)
                last_stop=new_stop
        except StopIteration:
            break
    stuff=do_stuff(doc,last_stop,len(doc.w_objs))
    handler.handle_stuff(stuff)
    handler.close()

def do_nadine(export_fname='/gluster/nufa/public/tuebadz-7.0-mit-NE-format4-mit-anaphern.export',
              corpus_name='R7FINAL'):
    doc=exml_merged.make_konn_doc()
    reader=exml_merged.MergedCorpusReader(doc,export_fname,corpus_name)
    last_stop=len(doc.words)
    examples=[]
    while True:
        try:
            disc_rels=[]
            new_stop=reader.addNext()
            if (new_stop!=last_stop):
                for edu in doc.get_objects_by_class(Edu,last_stop,new_stop):
                    disc_rels+=get_unmarked_relations(doc,edu)
                for edu_range in doc.get_objects_by_class(EduRange, last_stop, new_stop):
                    disc_rels+=get_unmarked_relations(doc,edu)
                doc.clear_markables(last_stop,new_stop)
                last_stop=new_stop
            for rel in disc_rels:
                examples.append(('|'.join(rel[1]),'+'.join(rel[0]),
                                 ' '.join(doc.words[rel[2].span[0]:rel[2].span[1]]),
                                 ' '.join(doc.words[rel[3].span[0]:rel[3].span[1]])))
        except StopIteration:
            break
    examples.sort()
    output=file('nadine_out.txt','w')
    for line in examples:
        print >>output,'\t'.join(line)
    output.close()

def test_span2nodes(doc,start,end):
    doc.ensure_span(start,end)
    for node in span2nodes(doc,[start,end]):
        print node.to_penn()

oparse=optparse.OptionParser()
oparse.add_option('--fprefix',dest='fprefix',
                  default='')
oparse.add_option('--features',dest='features')
if __name__=='__main__':
    opts,args=oparse.parse_args(sys.argv[1:])
    if opts.features is not None:
        feat_lst=opts.features.split(',')
        if 'defaults' in feat_lst:
            feat_lst+=wanted_features
        wanted_features=feat_lst
    if len(args)>=2:
        main(args[0], args[1],opts)
    else:
        exp_fname='/gluster/nufa/public/tuebadz-7.0-mit-NE-format4-mit-anaphern.export'
        corpus_name='R7FINAL'
        main(exp_fname,corpus_name,opts)
