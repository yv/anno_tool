#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
import math
from itertools import izip
from collections import defaultdict
import pytree.export as export
import annodb.database as annodb
from dist_sim.fcomb import InfoNode, InfoTree
from annodb.schema import schemas
from pynlp.de import smor_pos, tueba_heads
from pytree import deps
import simplejson as json

import sys
from pynlp.de import pydeps
from gwn_old import germanet
from gwn_old import wordsenses
from gwn_old.semclass import semclass_for_node
from gwn_old.gwn_word_features import get_verb_features

from sem_features import classify_adverb, classify_px, get_productions

db=annodb.get_corpus('R6PRE1')
lemmas=db.corpus.attribute('lemma','p')

stupid_head_finder=deps.SimpleDepExtractor(tueba_heads.hr_table+[(None,[(None,'HD','r'),(None,'l')])],['$,','$.'])

def null_warning_handler(w,args):
    if w in ['nolabel','nohead']:
        return
    sys.stderr.write(deps.messages[w]%args)

deps.warning_handler=null_warning_handler

hier_map={}
def make_schema(entries,prefix):
    for x in entries:
        hier_map[x[0]]=prefix+x[0]
        make_schema(x[2],'%s%s.'%(prefix,x[0]))
make_schema(schemas['konn2'].schema,'')

def find_args(n):
    if n.cat=='KOUS':
        if n.parent.cat=='C':
            pp=n.parent.parent
            assert pp.cat in ['SIMPX','FKONJ']
            sub_cl=pp
            while pp.edge_label=='KONJ':
                pp=pp.parent
            if pp.parent:
                pp=pp.parent
                while pp.parent and pp.cat not in ['SIMPX','R-SIMPX','FKONJ']:
                    pp=pp.parent
                main_cl=pp
            else:
                main_cl=None
            return sub_cl,main_cl
        else:
            print "weird: %s"%(n,)
            return None,None
    elif n.cat=='KON':
        pp=n.parent
        seen_kon=False
        main_cl=None
        sub_cl=None
        for n1 in pp.children:
            if n1.cat in ['SIMPX','FKONJ']:
                if seen_kon:
                    sub_cl=n1
                else:
                    main_cl=n1
            if n1.cat=='KON':
                seen_kon=True
        if main_cl is not None and main_cl.cat=='FKONJ':
            main_cl=pp.parent
        return sub_cl,main_cl

def find_negation(n):
    result=[]
    gather_negation(n.children,result)
    return result

def gather_negation(nodes,result):
    for n in nodes:
        if n.cat=='PTKNEG':
            result.append(n)
        elif n.isTerminal() and n.word.startswith('kein'):
            result.append(n)
        elif n.isTerminal() and n.word == 'nichts':
            result.append(n)
        if n.cat in ['SIMPX','R-SIMPX'] and n.edge_label!='OS':
            pass
        elif n.cat=='FKOORD':
            for n1 in n.children:
                if n1.cat=='FKONJ':
                    gather_negation(n1.children,result)
                    break
        else:
            gather_negation(n.children,result)

def find_nomargs(n):
    result=[]
    gather_args(n.children,result)
    return result

def gather_args(nodes,result):
    for n in nodes:
        if n.cat in ['VF','MF']:
            for n1 in n.children:
                if n1.edge_label in ['ON','OA','OD','OG','OPP','FOPP','PRED']:
                    result.append((n1.edge_label,n1))
        elif n.cat=='FKOORD':
            for n1 in n.children:
                if n1.cat=='FKONJ':
                    gather_args(n1.children,result)
                    break

def gather_adjuncts(nodes,result,exclude):
    for n in nodes:
        if n.cat in ['VF','MF','NF']:
            for n1 in n.children:
                if n1 in exclude: continue
                if n1.cat in ['NX','NCX']:
                    if n1.edge_label=='MOD' and n.cat!='NF':
                        result['tmp'].append(n1)
                elif n1.cat=='PX':
                    result[classify_px(n1)].append(n1)
                elif n1.cat=='ADVX':
                    result[classify_adverb(n1)].append(n1)
        elif n.cat=='FKOORD':
            for n1 in n.children:
                if n1.cat=='FKONJ':
                    gather_adjuncts(n1.children,result,exclude)
                    break
def find_adjuncts(n,exclude=[]):
    result=defaultdict(list)
    gather_adjuncts(n.children,result,exclude)
    return result

def add_hypernyms(synsets,result):
    for syn in synsets:
        hyper=syn.getHypernyms()
        if not hyper:
            result.append(syn.getWords()[0].word)
        else:
            add_hypernyms(hyper,result)

def get_verbs(n):
    fin_verbs=[]
    nfin_verbs=[]
    gather_verbs(n.children,fin_verbs,nfin_verbs)
    flags=set()
    if not fin_verbs:
        for n1 in n.children:
            if n1.cat=='FKOORD':
                print "looking for finite verb in FKOORD..."
                for n2 in n1.children:
                    if n2.cat=='FKONJ':
                        gather_verbs(n2.children,fin_verbs,[])
                        if fin_verbs: break
    if not fin_verbs:
        if nfin_verbs:
            main_v=nfin_verbs[0]
            all_v=nfin_verbs[1:]
            flags.add('nonfin')
        else:
            main_v=n.head
            all_v=[]
            flags.add('null')
    else:
        main_v=fin_verbs[0]
        all_v=nfin_verbs
        if len(main_v.morph)==4:
            flags.add('tense=%s'%(main_v.morph[3]))
            flags.add('mood=%s'%(main_v.morph[2]))
        else:
            print >>sys.stderr, "strange morph: %s for %s"%(main_v.morph,main_v)
    print main_v,all_v
    pred=main_v.lemma
    for n in all_v:
        if n.cat.endswith('PP'):
            if pred=='werden':
                flags.add('passive:dyn')
                pred=n.lemma
            elif pred=='haben':
                flags.add('perfect')
                pred=n.lemma
            elif pred=='sein':
                lem=n.lemma
                if (lem not in smor_pos.info_map or
                    'perfect:sein' in smor_pos.info_map[lem]):
                    flags.add('perfect')
                else:
                    flags.add('passive:stat')
                pred=n.lemma
            elif pred=='bleiben':
                flags.add('passive:stat')
                # bleiben markieren
                pred=n.lemma
        elif n.cat.endswith('INF'):
            if pred=='werden':
                flags.add('future')
                pred=n.lemma
            elif pred in ['wollen','sollen','müssen','können']:
                flags.add('mod:'+pred)
                pred=n.lemma
        elif n.cat=='PTKVZ' and '#' not in pred:
            pred='%s#%s'%(n.word,pred)
    return (pred,flags)

def extend_v(lst,nodes):
    for n in nodes:
        if n.isTerminal() and n.cat[0]=='V':
            lst.append(n)
        elif n.cat[0]!='V':
            continue
        else:
            for n1 in n.children:
                if n1.edge_label=='KONJ':
                    if n1.isTerminal():
                        lst.append(n1)
                    else:
                        extend_v(lst,n1.children)
                    break
    print lst,nodes

def gather_verbs_fin(chlds,fin_v):
    for n1 in chlds:
        if (n1.cat[:2] in ['VV','VA','VM'] and
            n1.cat[2:] in ['FIN','IMP']):
            fin_v.append(n1)
        elif n1.cat=='VXFIN':
            gather_verbs_fin(n1.children,fin_v)
            if n1.edge_label=='KONJ':
                break
        elif n1.cat in ['TRUNC','KON']:
            continue
        else:
            assert False,n1
def gather_verbs_nfin(chlds,nfin_v):
    for n1 in chlds:
        if n1.isTerminal():
            if n1.cat[0]=='V':
                nfin_v.append(n1)
        elif n1.cat=='VXINF':
            gather_verbs_nfin(n1.children,nfin_v)
            if n1.edge_label=='KONJ':
                break
        else:
            assert False, n1
def gather_verbs(nodes,fin_v,nfin_v):
    for n in nodes:
        if n.cat in ['LK','VC']:
            for n1 in n.children:
                if n1.cat=='VXFIN':
                    gather_verbs_fin(n1.children,fin_v)
                elif n1.cat=='VXINF':
                    gather_verbs_nfin(n1.children,nfin_v)
                elif n1.cat=='PTKVZ':
                    nfin_v.append(n1)
                else:
                    print "unclear:",n1.cat
        elif n.cat=='FKOORD':
            for n1 in n.children:
                if n1.cat=='FKONJ':
                    gather_verbs(n1.children,fin_v,nfin_v)
                    break


def get_target(anno):
    rel1=anno.rel1
    tgt=[hier_map[rel1]]
    if 'rel2' in anno._doc and anno.rel2!='NULL':
        tgt.append(hier_map[anno.rel2])
    return tgt

def grok_encoding(s):
    if isinstance(s,str):
        return s.decode('ISO-8859-15')
    else:
        return unicode(s)

def compatible_pronoun(n1,n2):
    if n1.head.cat!='PPER':
        return False
    if n2.head.cat=='PPER':
        return n1.head.morph[1:]==n2.head.morph[1:]
    if n1.head.morph[3]!='3':
        return False
    if n1.head.morph[1:3]!=n2.head.morph[1:3]:
        return False
    for n in n2.children:
        if n.cat=='PPOSAT':
            return False
    return True


def get_features(t, sub_cl, main_cl):
    feats=[]
    sub_parent=sub_cl.parent
    # if sub_parent.cat=='ADVX' and sub_parent.parent:
    #     #feats.append('modADV')
    #     cls=classify_adverb(sub_parent)
    #     #if cls:
    #     #    feats.append('modADV='+cls)
    #     #feats.append('modADV='+sub_parent.head.lemma)
    if (sub_parent.cat in ['ADVX','PX','NX'] and
        sub_parent.parent and
        sub_parent.parent.cat in ['VF','MF','NF']):
        sub_parent=sub_parent.parent
    print "field:",sub_parent.cat
    if 'nobaseline' not in wanted_features:
        feats.append('fd'+sub_parent.cat)
    neg_sub=find_negation(sub_cl)
    print "neg[sub]: ",neg_sub
    if 'neg' in wanted_features:
        if neg_sub:
            feats.append('NS+')
        else:
            feats.append('NS-')
    neg_main=find_negation(main_cl)
    print "neg[main]:",neg_main
    if 'neg' in wanted_features:
        if neg_main:
            feats.append('NM+')
        else:
            feats.append('NM-')
    (p,flags)=get_verbs(sub_cl)
    if 'lex' in wanted_features:
        feats.append('LS'+p)
    if 'assoc' in wanted_features and p in assoc_features:
        for k in assoc_features[p]:
            feats.append('AS'+k)
    if 'tmp' in wanted_features:
        for k in flags:
            feats.append('TFS'+k)
    print p,flags
    print get_verb_features(p)
    print "args[sub]:"
    nomargs_sub=find_nomargs(sub_cl)
    for k,v in nomargs_sub:
        print "  %s: %s[%s]"%(k,v.to_penn(), semclass_for_node(v))
    (p,flags)=get_verbs(main_cl)
    if 'lex' in wanted_features:
        feats.append('LM'+p)
    if 'assoc' in wanted_features and p in assoc_features:
        for k in assoc_features[p]:
            feats.append('AM'+k)
    if 'tmp' in wanted_features:
        for k in flags:
            feats.append('TFM'+k)
    print p,flags
    print get_verb_features(p)
    print "args[main]:"
    nomargs_main=find_nomargs(main_cl)
    for k,v in nomargs_main:
        print "  %s: %s[%s]"%(k,v.to_penn(),semclass_for_node(v))
    if 'mod' in wanted_features:
        mod_main=find_adjuncts(main_cl,[sub_cl])
        mod_sub=find_adjuncts(sub_cl)
        for (mod,modS) in [(mod_main,'M'),(mod_sub,'S')]:
            for k in ['tmp','causal','concessive','focus-koord-incl','comment']:
                if k in mod:
                    val='+'
                else:
                    val='-'
                feats.append('mod%s%s%s'%(modS,k,val))
        if mod_main:
            print "mod[main]"
            for k in mod_main:
                for v in mod_main[k]:
                    print " %s: %s"%(k,v.to_penn())
        if mod_sub:
            print "mod[sub]"
            for k in mod_sub:
                for v in mod_sub[k]:
                    print " %s: %s"%(k,v.to_penn())
    if 'csubj' in wanted_features:
        subj_main=[x[1] for x in nomargs_main if x[0]=='ON']
        subj_sub=[x[1] for x in nomargs_sub if x[0]=='ON']
        if len(subj_main)==1 and len(subj_sub)==1:
            if compatible_pronoun(subj_main[0],subj_sub[0]):
                feats.append('cpM+')
            else:
                feats.append('cpM-')
            if compatible_pronoun(subj_sub[0],subj_main[0]):
                feats.append('cpS+')
            else:
                feats.append('cpS-')
    main_end=main_cl.end
    if 'punc' in wanted_features:
        if len(t.terminals)>main_end and t.terminals[main_end].cat=='$.':
            feats.append('PUNC'+t.terminals[main_end].word)
    return feats

def production_features(t,sub_cl,main_cl, do_filter=True):
    result=[]
    lst_main=[]
    lst_sub=[]
    get_productions(main_cl,[sub_cl],lst_main)
    get_productions(sub_cl,[main_cl],lst_sub)
    set_main=set(lst_main)
    if do_filter:
        set_main.intersection_update(wanted_productions)
    set_sub=set(lst_sub)
    if do_filter:
        set_sub.intersection_update(wanted_productions)
    for k in set_main:
        if k in set_sub:
            result.append('prB%s'%(k,))
        else:
            result.append('prM%s'%(k,))
    for k in set_sub:
        if k not in set_main:
            result.append('prS%s'%(k,))
    return result

ignore_pos=['NN','NE','VVFIN','VVINF','VVIZU','VVPP']
#ignore_pos=[]

#TODO: only include a given wordpair once?
def wordpair_features(t,sub_cl,main_cl,conn, do_filter=True):
    result=[]
    idx_main=set(xrange(main_cl.start,main_cl.end))
    idx_sub=set(xrange(sub_cl.start,sub_cl.end))
    idx_main.difference_update(idx_sub)
    #idx_sub.discard(conn)
    #idx_sub.difference_update(idx_main)
    words_main=[t.terminals[i].lemma for i in sorted(idx_main)
                if t.terminals[i].cat not in ignore_pos]
    words_sub=[t.terminals[i].lemma for i in sorted(idx_sub)
               if t.terminals[i].cat not in ignore_pos]
    wps=['%s_%s'%(x,y) for x in words_main for y in words_sub]
    #wps.intersection_update(wanted_pairs)
    if do_filter:
        for k in wps:
            if k in wanted_pairs:
                result.append('WP'+k)
        print result
    else:
        for k in wps:
            result.append('WP'+k)
    return result

def retrieve_synsets(t,idxs):
    wanted_lemmas=[]
    for idx in idxs:
        n=t.terminals[idx]
        if n.cat in ['NN','NE','ADJA','ADJD','VVFIN','VVINF','VVIZU']:
            synsets=wordsenses.synsets_for_lemma(n.lemma,n.cat)
            wanted_lemmas.append((n,synsets))
    return wanted_lemmas

def expanded_synsets_for_lemma(lemma,pos):
    synsets=wordsenses.synsets_for_lemma(lemma,pos)
    if not synsets:
        return []
    depths=[wordsenses.synset_depth(syn) for syn in synsets]
    max_depth=max(depths)
    min_depth=min(depths)
    if pos=='NN':
        limit=max(3,min_depth-2)
    else:
        limit=max(0,min_depth-2)
    hyp_map={}
    for syn,d in izip(synsets,depths):
        wordsenses.gather_hyperonyms(syn.synsetId,hyp_map,0,d-limit)
    return hyp_map.keys()

def lexrel_features(t, sub_cl, main_cl,feats):
    idx_main=set(xrange(main_cl.start,main_cl.end))
    idx_sub=set(xrange(sub_cl.start,sub_cl.end))
    idx_main.difference_update(idx_sub)
    lemmas_s=retrieve_synsets(t,idx_sub)
    lemmas_m=retrieve_synsets(t,idx_main)
    hyp_map={}
    for n_s,synsets_s in lemmas_s:
        for n_m,synsets_m in lemmas_m:
            # gwn_path=wordsenses.relate_senses(synsets_s,
            #                                   synsets_m)
            # if gwn_path:
            #     print 'GWN', n_s.lemma, n_m.lemma, gwn_path
            lcs,dist=wordsenses.lcs_path(synsets_s,synsets_m)
            if lcs is not None:
                lcs_depth=wordsenses.synset_depth(lcs)
                print "GWN-LCS",n_s,n_m,lcs.explain(), dist, lcs_depth
                # if lcs in synsets_s:
                #     if lcs in synsets_m:
                #         feats.append('lcs_synonym')
                #     else:
                #         feats.append('lcs_hyperS')
                #         #feats.append('lcs_hyperS_%d'%(lcs.synsetId,))
                # elif lcs in synsets_m:
                #         feats.append('lcs_hyperM')
                #         #feats.append('lcs_hyperM_%d'%(lcs.synsetId,))                      
                #feats.append('lcs_exact_%d'%(lcs.synsetId,))
                if lcs.lexGroup.wordclass[0]!='n':
                    wordsenses.gather_hyperonyms(lcs.synsetId,hyp_map,0,2)
                elif lcs_depth>2:
                    wordsenses.gather_hyperonyms(lcs.synsetId,hyp_map,0,min(2,lcs_depth-3))
    for k in hyp_map:
        feats.append('lcs_super_%d'%(k,))

class FeatureCounter:
    def __init__(self):
        self.counts=defaultdict(int)
        self.total=0
    def add(self,lst):
        all_productions=set(lst)
        for k in all_productions:
            self.counts[k]+=1
        self.total+=1
    def by_entropy(self,x):
        if x[1]==self.total: return 0
        p=float(x[1])/self.total
        return -p*math.log(p)*(1.0-p)*math.log(1-p)
    def select(self,key=None,N=500,min_count=5):
        if key==None:
            key=self.by_entropy
        counts=sorted(self.counts.iteritems(),key=key)
        print "Cutoff at %s (with min_count=%d)"%(counts[N],min_count)
        return set([x[0] for x in counts[:N] if x[1]>=min_count])

def do_counting(spans):
    constituents=FeatureCounter()
    wordpairs=FeatureCounter()
    for span in spans:
        sent_no=db.sentences.cpos2struc(span[0])
        sent_span=db.sentences[sent_no]
        offset=span[0]-sent_span[0]
        t=export.from_json(db.get_parses(sent_no)['release'])
        for n in t.topdown_enumeration():
            if n.cat=='NCX': n.cat='NX'
        for n,lemma in izip(t.terminals,lemmas[sent_span[0]:sent_span[1]+1]):
            n.lemma=lemma
        stupid_head_finder(t)
        all_productions=set()
        n=t.terminals[offset]
        sub_cl,main_cl=find_args(n)
        if not main_cl: continue
        if not sub_cl: continue
        lst=[]
        get_productions(main_cl,[sub_cl],lst)
        get_productions(sub_cl,[main_cl],lst)
        constituents.add(lst)
        idx_main=set(xrange(main_cl.start,main_cl.end))
        idx_sub=set(xrange(sub_cl.start,sub_cl.end))
        idx_main.difference_update(idx_sub)
        #idx_sub.discard(offset)
        #idx_sub.difference_update(idx_main)
        words_main=[t.terminals[i].lemma for i in sorted(idx_main)
                    if t.terminals[i].cat not in ignore_pos]
        words_sub=[t.terminals[i].lemma for i in sorted(idx_sub)
                   if t.terminals[i].cat not in ignore_pos]
        wordpairs.add(['%s_%s'%(x,y) for x in words_main for y in words_sub])
    features_const=constituents.select()
    features_pairs=wordpairs.select()
    return features_const,features_pairs

buckets=[3,5,10,15,20]
def discretize(n):
    if n<buckets[0]:
        return n
    for b in buckets[1:]:
        if n<=b:
            return b
    return buckets[-1]+1

pos_groups={'$,':'c','ADJA':'a','NN':'n',
            'VVFIN':'v','VVPP':'v','VVINF':'v',
            'VVIZU':'v'}
def arg_lengths(t,sub_cl,main_cl,conn):
    result=[]
    idx_main=set(xrange(main_cl.start,main_cl.end))
    idx_sub=set(xrange(sub_cl.start,sub_cl.end))
    idx_main.difference_update(idx_sub)
    idx_sub.discard(conn)
    result.append('alTM%d'%(discretize(len(idx_main,))))
    result.append('alTS%d'%(discretize(len(idx_sub,))))
    group_counts=defaultdict(int)
    for i in idx_main:
        t_cat=t.terminals[i].cat
        if t_cat in pos_groups:
            group_counts[pos_groups[t_cat]]+=1
    for k in group_counts:
        result.append('al%sM%d'%(k,discretize(group_counts[k])))
    group_counts=defaultdict(int)
    for i in idx_sub:
        t_cat=t.terminals[i].cat
        if t_cat in pos_groups:
            group_counts[pos_groups[t_cat]]+=1
    for k in group_counts:
        result.append('al%sS%d'%(k,discretize(group_counts[k])))
    return result

def make_simple_tree(main_cl, sub_cl):
    (pred,flags)=get_verbs(main_cl)
    feats=list(flags)+['lm:'+pred]
    feats+=['hyp%d'%(k,) for k in expanded_synsets_for_lemma(pred,'VVINF')]
    ni1=InfoNode(main_cl.cat,feats)
    for n2 in main_cl.children:
        if n2.cat in ['VF','MF','NF']:
            for n3 in n2.children:
                if n3 is sub_cl:
                    ni2=InfoNode('SUB_CL',['fd:'+n2.cat])
                    ni1.add_edge(ni2)
                    continue
                if n3.edge_label.endswith('-MOD'):
                    continue
                feats=['fd:'+n2.cat,'cat:'+n3.cat]
                kind='MOD'
                if n3.edge_label in ['ON','OA','OD','OG','OPP','FOPP','PRED']:
                    kind='ARG'
                    feats.append('gf:'+n3.edge_label)
                if n3.cat=='PX':
                    cls=classify_px(n3)
                    if cls is not None:
                        feats.append('cls:'+cls)
                elif n3.cat=='ADVX':
                    cls=classify_adverb(n3)
                    if cls is not None:
                        feats.append('cls:'+cls)
                elif n3.cat=='NX':
                    sc=semclass_for_node(n3)
                    if sc is not None:
                        feats.append('sem:%s'%(sc,))
                if hasattr(n3,'head'):
                    feats.append('lm:'+n3.head.lemma)
                    if n3.cat=='PX':
                        if len(n3.children)>1 and n3.children[1].cat=='NX':
                            feats.append('arg:'+n3.children[1].head.lemma)
                    if n3.head.cat=='NN':
                        feats+=['hyp%d'%(k,) for k in expanded_synsets_for_lemma(pred,'VVINF')]
                ni2=InfoNode(kind,feats)
                ni1.add_edge(ni2)
    return ni1

def node2tree(n):
    ti=InfoTree()
    ti.add_node(n,True)
    return ti.as_json()

def process_spans(spans,annotator):
    for span in spans:
        sent_no=db.sentences.cpos2struc(span[0])
        sent_span=db.sentences[sent_no]
        t=export.from_json(db.get_parses(sent_no)['release'])
        for n in t.topdown_enumeration():
            if n.cat=='NCX': n.cat='NX'
        stupid_head_finder(t)
        for n,lemma in izip(t.terminals,lemmas[sent_span[0]:sent_span[1]+1]):
            n.lemma=lemma
        offset=span[0]-sent_span[0]
        n=t.terminals[offset]
        anno=db.get_annotation(annotator,'konn2',span)
        if 'rel1' not in anno or anno.rel1=='NULL': continue
        print "--- s%s"%(sent_no+1,)
        sub_cl,main_cl=find_args(n)
        if not main_cl: continue
        if not sub_cl: continue
        print "SUB: ",sub_cl.to_penn()
        print "MAIN:",main_cl.to_penn()
        #print "anno: temporal=%s contrastive=%s"%(anno.temporal,anno.contrastive)
        feats=get_features(t,sub_cl,main_cl)
        aux_lst=[]
        if 'productions' in wanted_features:
            feats+=production_features(t,sub_cl,main_cl)
        if 'productionsA' in wanted_features:
            aux_lst.append(production_features(t, sub_cl, main_cl, False))
        if 'wordpairs' in wanted_features:
            feats+=wordpair_features(t,sub_cl,main_cl,offset)
        if 'wordpairsA' in wanted_features:
            aux_lst.append(wordpair_features(t,sub_cl,main_cl,offset, False))
        if 'arglen' in wanted_features:
            feats+=arg_lengths(t, sub_cl, main_cl, offset)
        if 'lexrel' in wanted_features:
            lexrel_features(t, sub_cl, main_cl,feats)
        target=get_target(anno)
        print target
        #print "anno: rel1=%s rel2=%s"%(anno.rel1,anno._doc.get('rel2','NULL'))
        print feats
        #print anno._doc
        # print >>f_out, json.dumps([0,map(grok_encoding,feats),
        #                           target,[span[0],span[1]-1]],encoding='ISO-8859-15')
        print >>f_out, json.dumps([0,{'_type':'multipart','parts':[map(grok_encoding,feats)]+aux_lst,
                                      'trees':[node2tree(make_simple_tree(main_cl, sub_cl)),
                                               node2tree(make_simple_tree(sub_cl, None))]},
                                  target,[span[0],span[1]-1]],encoding='ISO-8859-15')

#wanted_features=['csubj','mod','lex','tmp','neg','punc','lexrel','assoc']
#wanted_features=['csubj','mod','lex','tmp','neg','punc','lexrel','assoc','wordpairs','productions']
#wanted_features=['csubj','mod','lex','tmp','neg','punc','lexrel','wordpairs','productions']
wanted_features=['csubj','mod','lex','tmp','neg','punc','lexrel','wordpairsA','productionsA']
#wanted_features=['nobaseline']
#wanted_features=['wordpairs','productions']
#wanted_features=[]

if len(sys.argv)>=2:
    wanted_features=sys.argv[1].split(',')

tasks_n=[db.get_task('task_nachdem%d_new'%(n,)) for n in xrange(1,7)]
tasks_w=[db.get_task('task_waehrend%d_new'%(n,)) for n in xrange(1,7)]
tasks_w2=[db.get_task('task_waehrend%d_new'%(n,)) for n in xrange(1,11)]
spans_n=sorted(set([tuple(span) for task in tasks_n for span in task.spans]))
spans_w=sorted(set([tuple(span) for task in tasks_w for span in task.spans]))
spans_w2=sorted(set([tuple(span) for task in tasks_w2 for span in task.spans]))

## 1. prepare necessary data (assoc, productions, wordpairs)
if 'assoc' in wanted_features:
    assoc_features={}
    for l in file('word_assoc.txt'):
        line=l.strip().split()
        assoc_features[line[0]]=line[1:]

if 'productions' in wanted_features or 'wordpairs' in wanted_features:
    #wanted_productions,wanted_pairs=do_counting(spans_n+spans_w2)
    wanted_productions,wanted_pairs=do_counting(spans_n+spans_w)
    print wanted_productions
    print wanted_pairs

if __name__=='__main__':
    ## 2. create data for nachdem and waehrend
    f_out=file('nachdem_1-6.json','w')
    process_spans(spans_n,'melike')
    f_out.close()

    # TBD: update wanted_productions
    f_out=file('waehrend_1-4.json','w')
    process_spans(spans_w,'melike')
    f_out.close()

    f_out=file('waehrend_1-10.json','w')
    process_spans(spans_w2,'melike')
    f_out.close()

    # tasks2=[db.get_task('task_aberA_new')]
    # print tasks2
    # spans=sorted(set([tuple(span) for task in tasks2 for span in task.spans]))

    # f_out=file('aberA.json','w')
    # process_spans(spans,'sabrina')
    # f_out.close()
