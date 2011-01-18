#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
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
import pydeps

adverb_classes={}
# nicht: erst, gerade (Fokusinteraktion)
# nicht: zugleich (parallel)
for k in '''anfangs bald beizeiten früh
nun jetzt gerade derzeit inzwischen soeben
gestern vorgestern neulich bisher bislang früher damals kürzlich letztens seinerzeit
morgen übermorgen seither später nachher demnächst'''.split():
    adverb_classes[k]='tmp'
for k in '''daher darum deshalb deswegen'''.split():
    adverb_classes[k]='causal'
for k in '''auch ebenfalls ebenso gleichfalls'''.split():
    adverb_classes[k]='focus-koord-incl'
for k in '''nur bloß lediglich allein ausschließlich einzig'''.split():
    adverb_classes[k]='focus-restr-excl'
for k in '''erst schon bereits noch'''.split():
    adverb_classes[k]='focus-tmp'
for k in '''zweifellos zweifelsohne fraglos tatsächlich
sicher bestimmt gewiß vermutlich wahrscheinlich
angeblich vorgeblich
leider'''.split():
    adverb_classes[k]='comment'

def classify_adverb(n):
    lem=n.head.lemma
    if lem in adverb_classes:
        return adverb_classes[lem]
    if lem.endswith('weise'):
        return 'comment'
    return None

def classify_px(n):
    if n.children[0].edge_label=='APP' and n.children[0].cat=='PX':
        n=n.children[0]
    lem=n.head.lemma
    if n.children[-1].cat not in ['NX','NCX']:
        return None
    case=n.head.morph[0]
    lem2=n.children[-1].head.lemma
    cls_lem2=set()
    for syn in germanet.synsets_for_word(lem2):
        cls_lem2.update(germanet.classify_synset(syn))
    if lem=='wegen':
        return 'causal'
    elif lem=='trotz':
        return 'concessive'
    if case=='d':
        if lem=='in' and 'zeiteinheit' in cls_lem2:
            return 'tmp'
        elif lem=='an' and 'tag' in cls_lem2:
            return 'tmp'
        elif lem=='nach' and 'information' in cls_lem2:
            return 'source'
        elif lem=='nach' and 'ereignis' in cls_lem2:
            return 'tmp'
        elif lem=='vor':
            if 'ereignis' in cls_lem2:
                # vor dem Unfall
                return 'tmp'
            if 'zeiteinheit' in cls_lem2:
                # vor zwei Wochen, vor dem 1. Mai
                return 'tmp'
        elif lem in ['während','seit']:
            return 'tmp'

db=annodb.get_corpus('R6PRE1')
lemmas=db.corpus.attribute('lemma','p')

stupid_head_finder=deps.SimpleDepExtractor(tueba_heads.hr_table+[(None,[(None,'HD','r'),(None,'l')])],['$,','$.'])

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


wanted_features=['csubj','mod','lex']

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
    if neg_sub:
        feats.append('NS+')
    else:
        feats.append('NS-')
    neg_main=find_negation(main_cl)
    print "neg[main]:",neg_main
    if neg_main:
        feats.append('NM+')
    else:
        feats.append('NM-')
    print "args[sub]:"
    (p,flags)=get_verbs(sub_cl)
    if 'lex' in wanted_features:
        feats.append('LS'+p)
    for k in flags:
        feats.append('TFS'+k)
    print p,flags
    print get_verb_features(p)
    nomargs_sub=find_nomargs(sub_cl)
    for k,v in nomargs_sub:
        print "  %s: %s"%(k,v.to_penn())
    if 'mod' in wanted_features:
        print "args[main]:"
    (p,flags)=get_verbs(main_cl)
    if 'lex' in wanted_features:
        feats.append('LM'+p)
    for k in flags:
        feats.append('TFM'+k)
    print p,flags
    print get_verb_features(p)
    nomargs_main=find_nomargs(main_cl)
    for k,v in nomargs_main:
        print "  %s: %s"%(k,v.to_penn())
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
    if len(t.terminals)>main_end and t.terminals[main_end].cat=='$.':
        feats.append('PUNC'+t.terminals[main_end].word)
    return feats

def process_spans(spans,annotator):
    for span in spans:
        sent_no=db.sentences.cpos2struc(span[0])
        sent_span=db.sentences[sent_no]
        t=export.from_json(db.get_parses(sent_no)['release'])
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
        target=get_target(anno)
        print target
        #print "anno: rel1=%s rel2=%s"%(anno.rel1,anno._doc.get('rel2','NULL'))
        print feats
        #print anno._doc
        print >>f_out, json.dumps([0,map(grok_encoding,feats),target,[span[0],span[1]-1]])

tasks=[db.get_task('task_nachdem%d_new'%(n,)) for n in xrange(1,7)]
print tasks
spans=sorted(set([tuple(span) for task in tasks for span in task.spans]))
f_out=file('nachdem_1-6.json','w')
process_spans(spans,'melike')
f_out.close()

tasks2=[db.get_task('task_waehrend%d_new'%(n,)) for n in xrange(1,3)]
print tasks
spans=sorted(set([tuple(span) for task in tasks2 for span in task.spans]))
f_out=file('waehrend_1-2.json','w')
process_spans(spans,'stefanie')
f_out.close()

# tasks2=[db.get_task('task_aberA_new')]
# print tasks2
# spans=sorted(set([tuple(span) for task in tasks2 for span in task.spans]))

# f_out=file('aberA.json','w')
# process_spans(spans,'sabrina')
# f_out.close()
