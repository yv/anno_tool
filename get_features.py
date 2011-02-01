#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
import math
from itertools import izip
from collections import defaultdict
import pytree.export as export
import annodb.database as annodb
from annodb.schema import schemas
from pynlp.de import smor_pos, tueba_heads
from pytree import deps
import simplejson as json

import sys
sys.path.append('/home/yannickv/proj/pytree')
import germanet
import wordsenses
import pydeps
from sem_features import classify_adverb, classify_px, semclass_for_node, get_productions

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

def get_verb_features(vlemma):
    vlemma=vlemma.replace('#','')
    synsets=germanet.synsets_for_word(vlemma)
    result=[]
    add_hypernyms(synsets,result)
    result2=set()
    for syn in synsets:
        result2.add(syn.lexGroup.name)
    return sorted(set(result)),sorted(result2)

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
        flags.add('tense=%s'%(main_v.morph[3]))
        flags.add('mood=%s'%(main_v.morph[2]))
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

def gather_verbs(nodes,fin_v,nfin_v):
    for n in nodes:
        if n.cat in ['LK','VC']:
            for n1 in n.children:
                if n1.cat=='VXFIN':
                    fin_v.extend(n1.children)
                elif n1.cat=='VXINF':
                    extend_v(nfin_v,n1.children)
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


#wanted_features=['csubj','mod','lex','tmp','neg','punc','lexrel','assoc']
wanted_features=['csubj','mod','lex','tmp','neg','punc','lexrel','assoc'] #,'wordpairs','productions']
#wanted_features=['wordpairs','productions']
#wanted_features=[]

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

def production_features(t,sub_cl,main_cl):
    result=[]
    lst_main=[]
    lst_sub=[]
    get_productions(main_cl,[sub_cl],lst_main)
    get_productions(sub_cl,[main_cl],lst_sub)
    set_main=set(lst_main)
    set_main.intersection_update(wanted_productions)
    set_sub=set(lst_sub)
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

def wordpair_features(t,sub_cl,main_cl):
    result=[]
    idx_main=set(xrange(main_cl.start,main_cl.end))
    idx_sub=set(xrange(sub_cl.start,sub_cl.end))
    idx_main.difference_update(idx_sub)
    #idx_sub.difference_update(idx_main)
    words_main=[t.terminals[i].lemma for i in sorted(idx_main)]
    words_sub=[t.terminals[i].lemma for i in sorted(idx_sub)]
    for k in ['%s_%s'%(x,y) for x in words_main for y in words_sub]:
        if k in wanted_pairs:
            result.append('WP'+k)
    print result
    return result

def retrieve_synsets(t,idxs):
    wanted_lemmas=[]
    for idx in idxs:
        n=t.terminals[idx]
        if n.cat in ['NN','NE','ADJA','ADJD','VVFIN','VVINF','VVIZU']:
            w=n.lemma.replace('#','')
            wc=n.cat[0].lower()
            if n.cat=='NN':
                synsets=wordsenses.analyse_nn_lemma(w.split('|'))
                synsets2=[syn for syn in synsets
                          if not syn.getWords()[0].eigenname]
                if synsets2:
                    synsets=synsets2
            else:
                synsets=[syn for syn in germanet.synsets_for_word(w)
                         if syn.lexGroup.wordclass[0]==wc]
            wanted_lemmas.append((n,synsets))
    return wanted_lemmas

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
        #idx_sub.difference_update(idx_main)
        words_main=[t.terminals[i].lemma for i in sorted(idx_main)]
        words_sub=[t.terminals[i].lemma for i in sorted(idx_sub)]
        wordpairs.add(['%s_%s'%(x,y) for x in words_main for y in words_sub])
    features_const=constituents.select()
    features_pairs=wordpairs.select()
    return features_const,features_pairs

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
        if 'productions' in wanted_features:
            feats+=production_features(t,sub_cl,main_cl)
        if 'wordpairs' in wanted_features:
            feats+=wordpair_features(t,sub_cl,main_cl)
        if 'lexrel' in wanted_features:
            lexrel_features(t, sub_cl, main_cl,feats)
        target=get_target(anno)
        print target
        #print "anno: rel1=%s rel2=%s"%(anno.rel1,anno._doc.get('rel2','NULL'))
        print feats
        #print anno._doc
        print >>f_out, json.dumps([0,map(grok_encoding,feats),target,[span[0],span[1]-1]])

if 'assoc' in wanted_features:
    assoc_features={}
    for l in file('word_assoc.txt'):
        line=l.strip().split()
        assoc_features[line[0]]=line[1:]

tasks=[db.get_task('task_nachdem%d_new'%(n,)) for n in xrange(1,7)]
print tasks
spans=sorted(set([tuple(span) for task in tasks for span in task.spans]))
if 'productions' in wanted_features or 'wordpairs' in wanted_features:
    wanted_productions,wanted_pairs=do_counting(spans)
    print wanted_productions
    print wanted_pairs
f_out=file('nachdem_1-6.json','w')
process_spans(spans,'melike')
f_out.close()

tasks2=[db.get_task('task_waehrend%d_new'%(n,)) for n in xrange(1,3)]
print tasks
spans=sorted(set([tuple(span) for task in tasks2 for span in task.spans]))
# TBD: update wanted_productions
f_out=file('waehrend_1-2.json','w')
process_spans(spans,'melike')
f_out.close()

# tasks2=[db.get_task('task_aberA_new')]
# print tasks2
# spans=sorted(set([tuple(span) for task in tasks2 for span in task.spans]))

# f_out=file('aberA.json','w')
# process_spans(spans,'sabrina')
# f_out.close()
