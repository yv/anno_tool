#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
import sys
from itertools import izip
from pytree import export
import codecs

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

def try_stuff(t):
    for n in t.terminals:
        tag=terminal_tag(n)
        if tag is not None:
            print "%-10s: %s -> %s"%(tag[0],n.lemma,tag[1])

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
