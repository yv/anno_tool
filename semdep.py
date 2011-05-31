#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
import sys
import malt_wrapper
from CWB.CL import Corpus, IDList
from pynlp.de import smor_pos
from graph_search import dijkstra_search
from gzip import GzipFile
from codecs import latin_1_decode
import simplejson as json
import malt_wrapper
import promise

class DependencyCorpus(object):
    def __init__(self, corpus, lemma_column='tb_lemma',
                 pos_column='rf_pos',morph_column='rf_morph'):
        self.corpus=corpus
        self.words=corpus.attribute('word','p')
        self.postags=corpus.attribute(pos_column,'p')
        self.morphs=corpus.attribute(morph_column,'p')
        self.lemmas=corpus.attribute(lemma_column,'p')
        self.sentences=corpus.attribute('s','s')
        self.attach=corpus.attribute('attach','p')
        self.deprel=corpus.attribute('deprel','p')
    def __len__(self):
        return len(self.sentences)
    def __getitem__(self,idx):
        words=self.words
        postags=self.postags
        lemmas=self.lemmas
        attach=self.attach
        deprel=self.deprel
        morphs=self.morphs
        s_start,s_end=self.sentences[idx][:2]
        result=[]
        for i,posn in enumerate(xrange(s_start,s_end+1)):
            a=attach[posn]
            if a=='ROOT':
                parent_id=0
            else:
                parent_id=i+1+int(a)
            result.append([str(i+1),words[posn],lemmas[posn],
                           malt_wrapper.get_cpos(postags[posn]),
                           postags[posn], morphs[posn],
                           str(parent_id),deprel[posn]])
        return result
    def get_graph(self,idx):
        sent=self[idx]
        t=malt_wrapper.sent2tree(sent)
        for i,n in enumerate(t.terminals):
            n.start=i
        make_semrels(t)
        return t

def get_collocate_sents(corpus,
                        src_lemmas, tgt_lemmas,
                        src_pos=None, tgt_pos=None,
                        lemma_column='tb_lemma',
                        pos_column='rf_pos'):
    lemmas=corpus.attribute(lemma_column,'p')
    postags=corpus.attribute(pos_column,'p')
    sentences=corpus.attribute('s','s')
    src_ids=lemmas.find_list(src_lemmas)
    if src_pos is not None:
        src_ids &= postags.find_list(src_pos)
    src_sents=sentences.map_idlist(src_ids)
    tgt_ids=lemmas.find_list(tgt_lemmas)
    if tgt_pos is not None:
        tgt_ids &= postags.find_list(tgt_pos)
    tgt_sents=sentences.map_idlist(tgt_ids)
    return src_sents & tgt_sents

def collapse_aux(t):
    # 1. collapse aux
    has_aux=set()
    for i,n in enumerate(t.terminals):
        if n.syn_label=='AUX' and n.syn_parent:
            has_aux.add(n.syn_parent.start)
    for i,n in enumerate(t.terminals):
        if n.cat[0]=='V' and n.syn_label=='AUX' and n.start not in has_aux:
            aux_parents=[]
            flags=set()
            last=n
            n1=n.syn_parent
            while n1:
                n1_lemma=n1.lemma
                n1.new_label='aux'
                if last.cat.endswith('PP'):
                    if n1_lemma=='werden':
                        n.flags.add('passive:dyn')
                        n1.new_label='auxpass'
                    elif n1_lemma=='haben':
                        n.flags.add('perfect')
                    elif n1_lemma=='sein':
                        lem=last.lemma
                        if (last.lemma not in smor_pos.info_map or
                            'perfect:sein' in smor_pos.info_map[lem]):
                            flags.add('perfect')
                        else:
                            flags.add('passive:stat')
                            n1.new_label='auxpass'
                    elif n1_lemma=='bleiben':
                        n.flags.add('passive:stat')
                        n1.new_label='auxpass'
                elif last.cat.endswith('INF'):
                    n1_lemma=n1.lemma
                    if n1_lemma=='werden':
                        n.flags.add('future')
                    elif n1_lemma in ['wollen','sollen','müssen','können']:
                        n.flags.add('mod:'+n1_lemma)
                aux_parents.append(n1)
                if n1.syn_label!='AUX':
                    break
                last=n1
                n1=n1.syn_parent
            n.syn_parent=n1.syn_parent
            n.syn_label=n1.syn_label
            for n2 in aux_parents:
                n2.syn_label=n2.new_label
                n2.syn_parent=n
    for i,n in enumerate(t.terminals):
        if n.syn_parent and n.syn_parent.syn_label in ['aux','auxpass']:
            n.syn_parent=n.syn_parent.syn_parent

def collapse_kon(t):
    has_kon=set()
    for i,n in enumerate(t.terminals):
        if (n.syn_label=='KON' and n.syn_parent is not None or
            n.syn_label=='CJ' and n.syn_parent.cat=='KON'):
            has_kon.add(n.syn_parent.start)
    for i,n in enumerate(t.terminals):
        if (n.start not in has_kon and (n.syn_label=='KON' or
                                        n.syn_label=='CJ' and n.syn_parent.cat=='KON')):
            conjuncts=[]
            coord=None
            coord_label='conj'
            n1=n
            while n1:
                if n1.cat=='KON':
                    coord=n1
                    coord_label='conj_'+n1.word.lower()
                else:
                    conjuncts.append(n1)
                if n1.syn_label=='KON' or (n1.syn_label=='CJ' and n1.syn_parent.cat=='KON'):
                    n1=n1.syn_parent
                else:
                    break
            for n1 in conjuncts[:-1]:
                n1.syn_label=coord_label
                n1.syn_parent=conjuncts[-1]
            if coord is not None and coord.syn_parent is not None:
                coord.syn_label='cc'

def get_preposition(node):
    lem=node.lemma
    parent_new=node.syn_parent
    node.flags.add('hide')
    # if lem has a locative/essive ambiguity, add case
    # use bis-zu
    if lem in ['in','nach','an']:
        lbl='prep_%s_%s'%(lem,node.morph)
    if lem=='von' and parent_new and parent_new.cat=='APPR':
        return get_preposition(parent_new)
    else:
        lbl='prep_%s'%(lem,)
    return lbl,parent_new

def collapse_pn(t):
    # TODO: auf Video oder auf sonst einem Medium (APPR-conj_xx->
    for i,n in enumerate(t.terminals):
        if n.syn_label=='PN':
            lbl,parent_new=get_preposition(n.syn_parent)
            n.syn_label=lbl
            n.syn_parent=parent_new

def relabel_subj(t):
    for n in t.terminals:
        if n.syn_label=='SUBJ' and n.syn_parent:
            lbl='nsubj'
            if n.syn_parent.flags.intersection(['passive:dyn','passive:stat']):
                lbl='nsubjpass'
            n.syn_label=lbl
        if n.syn_label=='prep_von' and n.syn_parent and 'passive:dyn' in n.syn_parent.flags:
            n.syn_label='agent'

other_mapping={'ATTR':'amod','DET':'det',
               'OBJA':'dobj',
               'ADV':'adv','KONJ':'mark',
               'ZEIT':'tmod'}
def relabel_others(t):
    for n in t.terminals:
        lab=n.syn_label
        if lab in other_mapping:
            n.syn_label=other_mapping[lab]

def fill_sd_gov(t):
    for n in t.terminals:
        if 'hide' in n.flags:
            continue
        n.sd_gov=[]
        n.sd_dep=[]
        if n.syn_parent:
            n.sd_gov.append((n.syn_label,n.syn_parent))
    for n in t.terminals:
        if 'hide' in n.flags:
            continue
        if n.syn_parent:
            if 'hide' in n.syn_parent.flags:
                print >>sys.stderr, "dependent of hidden: %s -> %s"%(n,n.syn_parent)
            else:
                n.syn_parent.sd_dep.append((n.syn_label,n))
            

def make_semrels(t):
    # 0. unattach punct, add flags field
    for n in t.terminals:
        n.flags=set()
        if n.syn_label=='-PUNCT-' or n.cat in ['$.','$,','$(']:
            n.syn_label='-'
            n.syn_parent=None
            n.flags.add('hide')
        if n.cat in ['PTKZU','PTKVZ']:
            n.flags.add('hide')
        if n.syn_parent is None and n.syn_label not in ['ROOT','-']:
            print >>sys.stderr, "Renaming root label: %s/%s/%s"%(n.word,n.cat,n.syn_label)
            n.syn_label='ROOT'
    collapse_aux(t)
    collapse_kon(t)
    collapse_pn(t)
    relabel_subj(t)
    relabel_others(t)
    fill_sd_gov(t)

def output_triples(t):
    for n in t.terminals:
        if 'hide' in n.flags or n.cat in ['$.','$,','$(']:
            continue
        for lab,dep in n.sd_dep:
            print '%s(%s-%s,%s-%s)'%(lab,n.lemma,n.start+1,
                                     dep.lemma,dep.start+1)
                                     

def get_path(t,idx1,idx2,limit=None):
    def neighbours(idx):
        n0=t.terminals[idx]
        if 'hide' in n0.flags:
            return
        for rel,n in n0.sd_dep:
            if 'hide' not in n.flags:
                yield (1,n.start,'-'+rel)
        for rel,n in n0.sd_gov:
            if 'hide' not in n.flags:
                yield (1,n.start,'+'+rel)
    return dijkstra_search([idx1],[idx2],neighbours,limit)

lemma_map={
    'der':'das',
    'die':'das',
    'der|die|das':'das',
    'eine':'ein',
    'ein|eine':'ein',
    }

@promise.pure()
@promise.sensible()
def lemma_for(n):
    s=n.lemma
    if isinstance(s,str):
        s=latin_1_decode(n.lemma)[0]
    s=lemma_map.get(s,s)
    if '|' in s:
        return s[:s.index('|')]
    else:
        return s

def dep2json(t):
    nodes=[]
    edges=[]
    for n in t.terminals:
        n_id='w%d'%(n.start+1,)
        if 'hide' in n.flags or n.cat in ['$.','$,','$(']:
            continue
        nodes.append([n_id,lemma_for(n),n.cat])
        for lab, dep in n.sd_dep:
            edges.append([n_id,'w%d'%(dep.start+1),lab.decode('ISO-8859-15')])
    return {'nodes':nodes,'edges':edges}

def dep2paths(t,target,feature,result=None):
    if result==None:
        result=[]
    nodes=t.terminals
    for idx_start in target:
        dep2paths2(nodes,idx_start,feature,
                   [lemma_for(nodes[idx_start])],
                   set(),result)
    return result

def dep2paths2(nodes,idx,feature,path,seen,result):
    n=nodes[idx]
    if 'hide' in n.flags:
        return
    for lab, dep in n.sd_dep:
        idx2=dep.start
        if idx2 not in seen:
            path.append(('-',lab.decode('ISO-8859-15'),
                         lemma_for(dep)))
            seen.add(idx)
            if idx2 in feature:
                result.append(path[:])
            dep2paths2(nodes,idx2,feature,path,seen,result)
            seen.remove(idx)
            path.pop()
    for lab, dep in n.sd_gov:
        idx2=dep.start
        if idx2 not in seen:
            path.append(('+',lab.decode('ISO-8859-15'),
                         lemma_for(dep)))
            seen.add(idx)
            if idx2 in feature:
                result.append(path[:])
            dep2paths2(nodes,idx2,feature,path,seen,result)
            seen.remove(idx)
            path.pop()

def get_sat(n,seen):
    result=[]
    try:
        for lab, dep in n.sd_dep:
            idx2=dep.start
            if idx2 not in seen:
                result.append((lab.decode('ISO-8859-15'),
                               lemma_for(dep)))
    except AttributeError as x:
        print >>sys.stderr, "Att: %s (%s)"%(x,n)
    return result

def dep2paths_sat(t,target,feature,result=None):
    if result==None:
        result=[]
    nodes=t.terminals
    for idx_start in target:
        n=nodes[idx_start]
        dep2paths_sat2(nodes,idx_start,feature,
                   [n],
                   set([idx_start]),result)
    return result

def dep2paths_sat2(nodes,idx,feature,path,seen,result):
    n=nodes[idx]
    if 'hide' in n.flags or len(seen)>4:
        return
    for lab, dep in n.sd_dep:
        idx2=dep.start
        if idx2 not in seen:
            path.append(('-',lab.decode('ISO-8859-15'),
                         lemma_for(dep)))
            seen.add(idx)
            if idx2 in feature:
                result.append([lemma_for(path[0]),
                               lemma_for(dep),
                               path[1:-1]+[path[-1][:2]],
                               get_sat(path[0],seen),
                               get_sat(dep,seen)])
            dep2paths_sat2(nodes,idx2,feature,path,seen,result)
            seen.remove(idx)
            path.pop()
    for lab, dep in n.sd_gov:
        idx2=dep.start
        if idx2 not in seen:
            path.append(('+',lab.decode('ISO-8859-15'),
                         lemma_for(dep)))
            seen.add(idx)
            if idx2 in feature:
                result.append([lemma_for(path[0]),
                               lemma_for(dep),
                               path[1:-1]+[path[-1][:2]],
                               get_sat(path[0],seen),
                               get_sat(dep,seen)])
            dep2paths_sat2(nodes,idx2,feature,path,seen,result)
            seen.remove(idx)
            path.pop()

filters={
    'N':set(['NN']),
    'A':set(['ADJA','ADJD']),
    'V':set(['VVFIN','VVINF','VVPP','VVIZU'])
}

def dep2paths_all(corpus, kind='NN'):
    dc=DependencyCorpus(Corpus(corpus))
    if kind=='NN':
        suffix=''
    else:
        suffix='_'+kind
    filt_tgt=filters[kind[0]]
    filt_feat=filters[kind[1]]
    f_out=GzipFile('/gluster/nufa/yannick/paths_%s%s.json.gz'%(corpus,suffix),'w')
    for i in xrange(len(dc)):
        result=[]
        t=dc.get_graph(i)
        target=set([j for (j,n) in enumerate(t.terminals)
                    if n.cat in filt_tgt])
        feature=set([j for (j,n) in enumerate(t.terminals)
                     if n.cat in filt_feat])
        dep2paths(t,target,feature,result)
        #print '#',' '.join([n.word for n in t.terminals])
        for path in result:
            print >>f_out, json.dumps(path)
        if i%1000==0:
            print >>sys.stderr,"\r%s"%(i,)
    f_out.close()

def dep2paths_sat_all(corpus, kind='NN'):
    dc=DependencyCorpus(Corpus(corpus))
    if kind=='NN':
        suffix=''
    else:
        suffix='_'+kind
    filt_tgt=filters[kind[0]]
    filt_feat=filters[kind[1]]
    f_out=GzipFile('/gluster/nufa/yannick/paths_sat_%s%s.json.gz'%(corpus,suffix),'w')
    for i in xrange(len(dc)):
        result=[]
        t=dc.get_graph(i)
        target=set([j for (j,n) in enumerate(t.terminals)
                    if n.cat in filt_tgt])
        feature=set([j for (j,n) in enumerate(t.terminals)
                     if n.cat in filt_feat])
        dep2paths_sat(t,target,feature,result)
        #print '#',' '.join([n.word for n in t.terminals])
        for path in result:
            print >>f_out, json.dumps(path)
        if i%1000==0:
            print >>sys.stderr,"\r%s"%(i,)
    f_out.close()

if __name__=='__main__':
    #for sent in malt_wrapper.read_table_iter(file(sys.argv[1])):
    cmd=sys.argv[1]
    if cmd=='triples':
        for sent in DependencyCorpus(Corpus(sys.argv[2])):
            t=malt_wrapper.sent2tree(sent)
            for i,n in enumerate(t.terminals):
                n.start=i
            make_semrels(t)
            print '#',' '.join((n.word for n in t.terminals))
            output_triples(t)
            print
    elif cmd=='paths':
        if len(sys.argv)>3:
            kind=sys.argv[3]
        else:
            kind='NN'
        dep2paths_all(sys.argv[2],kind)
    elif cmd=='paths_sat':
        if len(sys.argv)>3:
            kind=sys.argv[3]
        else:
            kind='NN'
        dep2paths_sat_all(sys.argv[2],kind)
