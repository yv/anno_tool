#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
import sys
from itertools import izip
from pytree import export
import codecs

__all__ = ['terminal_tag', 'phrase_tag']

"""
Regeln:
nur pos/nur neg: wird vererbt
ADJ/NN: gerechten+ Krieg- => # / verschollene- Schätze+ => + / verdiente+ Strafe- => # / herzhaftem+ Biss => -
NN+/PP-: Chemotherapie+ [viraler Infektionen]- => + / Rechtfertigung+ [für Schandtaten]- => -
NN~/PP-: Ablehnung~ [aller Nichtsektenmitglieder+] => -
NN-/PP+: unter dem Deckmantel- [des Kampfes gegen den Terror]+ => - / Wegfall- [... in der Altenhilfe+] => -
X~/X^/NN+: nicht~ unerheblicher% Strafe- => - / kein~ reiner^ Segen+ => + / nicht~ unerhebliche% Nachteile-
"""

sentiws_limit=0.1
sentiws_info={}
for l in codecs.open('/home/yannickv/sources/SentiWS/SentiWS_v1.8c_Positive.txt','r','UTF-8'):
    line=l.strip().split()
    lemma,pos=line[0].split('|')
    score=float(line[1])
    if abs(score)>sentiws_limit:
        sentiws_info[(lemma,pos[0])]='+'
for l in codecs.open('/home/yannickv/sources/SentiWS/SentiWS_v1.8c_Negative.txt','r','UTF-8'):
    line=l.strip().split()
    lemma,pos=line[0].split('|')
    score=float(line[1])
    if abs(score)>sentiws_limit:
        sentiws_info[(lemma,pos[0])]='-'

lexsent_info={}
for l in codecs.open('/home/yannickv/sources/GermanLexSentiment/germanlex.txt','r','UTF-8'):
    if l[0]=='%':
        continue
    line=l.strip().split()
    lemma=line[0]
    kind,score=line[1].split('=')
    postag=line[2][0].upper()
    if kind=='POS':
        tag='+'
    elif kind=='NEG':
        tag='-'
    elif kind=='SHI':
        tag='~'
    elif kind=='INT':
        fscore=float(score)
        if fscore>1:
            tag='^'
        else:
            tag='%'
    else:
        continue
    lexsent_info[(lemma,postag)]=tag

gpolarity_info={}
for l in codecs.open('/home/yannickv/sources/GermanPolarityClues-2012/GermanPolarityClues-Negative-Lemma-21042012.tsv','r','UTF-8'):
    line=l.strip().split()
    lemma=line[1]
    postag=line[2][0]
    gpolarity_info[(lemma,postag)]='-'
for l in codecs.open('/home/yannickv/sources/GermanPolarityClues-2012/GermanPolarityClues-Positive-Lemma-21042012.tsv','r','UTF-8'):
    line=l.strip().split()
    lemma=line[1]
    postag=line[2][0]
    gpolarity_info[(lemma,postag)]='+'

def terminal_tag(n):
    """ retrieves a sentiment tag for a terminal
    """
    lemma=n.lemma
    postag=n.cat
    if postag in ['ADJA','ADJD','NN'] or postag[:2]=='VV':
        if postag[0]=='V' and '#' in lemma:
            lemma=lemma.replace('#','')
        if isinstance(lemma,str):
            lemma=lemma.decode('ISO-8859-15')
        key=(lemma,postag[0])
        if key in lexsent_info:
            return ('GLex',lexsent_info[key])
        elif key in sentiws_info:
            return ('SentiWS',sentiws_info[key])
        #elif key in gpolarity_info:
        #    return ('GPol',gpolarity_info[key])
        return None
    else:
        return None

def phrase_tag(n):
    """ computes a sentiment tag for a complete phrase
    """
    if n.isTerminal():
        ttag=terminal_tag(n)
        if ttag is None:
            w_lc=n.word.lower()
            if w_lc in ['kaum','nicht','kein','keine','keiner','keinem','keines','wenig']:
                return ('neg','~')
            elif w_lc in ['sehr','ganz']:
                return ('lex','^')
        return terminal_tag(n)
    elif n.cat in ['R-SIMPX','SIMPX']:
        return None
    else:
        head_tag=None
        nonhead_tags=[]
        for n1 in n.children:
            tag=phrase_tag(n1)
            if tag is not None:
                if n1.edge_label=='HD':
                    head_tag=tag+(n1.cat,)
                else:
                    nonhead_tags.append(tag+(n1.cat,))
        if head_tag and nonhead_tags:
            polarities=set([x[1] for x in [head_tag]+nonhead_tags])
            if len(polarities)==2 and '~' in polarities:
                other_pol=[x for x in polarities if x!='~'][0]
                if other_pol in '+-':
                    return ('neg_rule','-+'['+-'.index(other_pol)])
            if len(polarities)==2 and '^' in polarities:
                other_pol=[x for x in polarities if x!='~'][0]
                if other_pol in '+-':
                    return ('intensifier_rule',other_pol)
            if len(polarities)>1:
                print n.to_penn(),head_tag,nonhead_tags
        elif len(nonhead_tags)>1:
            polarities=set([x[1] for x in nonhead_tags])
            if len(polarities)>1:
                print n.to_penn(),head_tag,nonhead_tags
        if head_tag is not None:
            return head_tag[:2]
        elif nonhead_tags:
            return nonhead_tags[0][:2]
        else:
            return None

def try_stuff(t):
    for n in t.terminals:
        tag=terminal_tag(n)
        if tag is not None:
            print "%-10s: %s -> %s"%(tag[0],n.lemma,tag[1])

def try_compositional(t):
    for node in t.topdown_enumeration():
        if (node.cat in ['NX','PX','ADJX'] and 
            node.edge_label not in ['HD','-','APP']):
            ptag=phrase_tag(node)
            if False: #ptag != None:
                print node.to_penn()
                print ptag
        elif node.cat in ['LK','VC']:
            ptag=phrase_tag(node)
            if False: #ptag is not None:
                print node.to_penn()
                print ptag

def test(sent_start=1, sent_end=300):
    from annodb.database import get_corpus
    db=get_corpus('R6PRE1')
    s=db.corpus.attribute('s','s')
    lemmas=db.corpus.attribute('lemma','p')
    for sent_no in xrange(sent_start,sent_end):
        t=export.from_json(db.get_parses(sent_no)['release'])
        sent_span=s[sent_no]
        for n,lemma in izip(t.terminals,lemmas[sent_span[0]:sent_span[1]+1]):
            n.lemma=lemma
        try_stuff(t)
        try_compositional(t)
