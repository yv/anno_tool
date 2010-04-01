#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
from itertools import izip
import pytree.export as export
import mongoDB.annodb as annodb
import pynlp.de.smor_pos as smor_pos

db=annodb.AnnoDB()
lemmas=db.corpus.attribute('lemma','p')
task=db.get_task('waehrend2')

def find_args(n):
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
        main_v=nfin_verbs[0]
        all_v=nfin_verbs[1:]
        flags.add('nonfin')
    else:
        main_v=fin_verbs[0]
        all_v=nfin_verbs
        flags.add('tense=%s'%(main_v.morph[3]))
        flags.add('mood=%s'%(main_v.morph[2]))
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

def gather_verbs(nodes,fin_v,nfin_v):
    for n in nodes:
        if n.cat in ['LK','VC']:
            for n1 in n.children:
                if n1.cat=='VXFIN':
                    fin_v.extend(n1.children)
                elif n1.cat=='VXINF':
                    nfin_v.extend(n1.children)
                elif n1.cat=='PTKVZ':
                    nfin_v.append(n1)
                else:
                    print "unclear:",n1.cat
        elif n.cat=='FKOORD':
            for n1 in n.children:
                if n1.cat=='FKONJ':
                    gather_verbs(n1.children,fin_v,nfin_v)
                    break

for span in task.spans:
    sent_no=db.sentences.cpos2struc(span[0])
    sent_span=db.sentences[sent_no]
    t=export.from_json(db.get_parses(sent_no)['release'])
    for n,lemma in izip(t.terminals,lemmas[sent_span[0]:sent_span[1]+1]):
        n.lemma=lemma
    offset=span[0]-sent_span[0]
    n=t.terminals[offset]
    anno=db.get_annotation('anna','konn',span)
    print "--- s%s"%(sent_no+1,)
    sub_cl,main_cl=find_args(n)
    print "SUB: ",sub_cl.to_penn()
    print "MAIN:",main_cl.to_penn()
    print "field:",sub_cl.parent.cat
    print "neg[sub]: ",find_negation(sub_cl)
    print "neg[main]:",find_negation(main_cl)
    print "args[sub]:"
    print get_verbs(sub_cl)
    for k,v in find_nomargs(sub_cl):
        print "  %s: %s"%(k,v.to_penn())
    print "args[main]:"
    print get_verbs(main_cl)
    for k,v in find_nomargs(main_cl):
        print "  %s: %s"%(k,v.to_penn())    
    print "anno: temporal=%s contrastive=%s"%(anno.temporal,anno.contrastive)

