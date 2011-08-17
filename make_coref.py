import sys
import exml
import en_extract
import string
from collections import defaultdict
from annodb.database import get_corpus
from annodb.corpora import corpus_sattr, corpus_d_sattr
from pytree import tree
from alphabet import CPPAlphabet

def determine_set_ids(ana_links,alph):
    for k in ana_links.keys():
        determine_set_id(k,ana_links,set(),alph)

def determine_set_id(k,links,visited,alph):
    if k not in links:
        kk='set_%d'%(alph[k],)
        links[k]={'set_id':kk}
        return kk
    info=links[k]
    if 'set_id' in info:
        return info['set_id']
    if k in visited:
        kk='set_%d'%(alph[k],)
        info['set_id']=kk
        return kk
    visited.add(k)
    kk=determine_set_id(info['rel'][1][0],links,visited,alph)
    info['set_id']=kk
    return kk
    
def get_maximal_projection_0(n):
    if n.cat[-2:]=='AT':
        # PPOSAT, PRELAT
        return n
    while True:
        if not n.parent:
            return n
        if n.parent.cat not in ['NX','NCX','EN-ADD']:
            return n
        if n.parent.cat in ['NX','NCX'] and n.edge_label=='-':
            return n
        if n.edge_label=='KONJ':
            return n
        n=n.parent

def get_maximal_projection(n):
    n=get_maximal_projection_0(n)
    if n.cat=='EN-ADD' and len(n.children)==1 and n.children[0].cat in ['NX','NCX']:
        return n.children[0]
    if n.cat=='NX' and len(n.children)==2 and n.children[1].cat=='R-SIMPX':
        return n.children[0]
    return n

def get_entry(ana_links, node):
    n_id=node.xml_id
    if n_id in ana_links:
        return ana_links[n_id]
    else:
        entry={}
        ana_links[n_id]=entry
        return entry

def get_min(n):
    want_more=True
    while want_more:
        want_more=False
        if len(n.children)==1:
            n=n.children[0]
            want_more=True
        elif n.cat in ['NX','NCX']:
            for n1 in n.children:
                if n1.edge_label in ['HD','APP']:
                    n=n1
                    want_more=True
                    break
    return n

num_tr=string.maketrans('123456789','999999999')
def get_heads(n, result, is_pl=False):
    if hasattr(n,'en_info'):
        result.append(('NE',str(n.en_info)))
        return
    if n.isTerminal():
        if n.cat=='NN':
            hd=n.lemma
            if '|' in hd:
                hd=hd[:hd.index('|')]
            if '-' in hd:
                hd=hd[hd.rindex('-')+1:]
            hd=hd.translate(num_tr)
            if is_pl:
                letter='p'
            else:
                letter=n.morph[1]
            result.append(('NN',hd,letter))
        return
    if n.cat in ['NX','NCX']:
        for n1 in n.children:
            if n1.edge_label in ['HD','APP']:
                get_heads(n1,result,is_pl)
            elif n1.edge_label=='KONJ':
                get_heads(n1,result,True)
    elif n.cat in ['EN-ADD']:
        for n1 in n.children:
            get_heads(n1,result,is_pl)
        
def print_appos(hds, f_out):
    if len(hds)<2:
        return
    for hd1 in hds:
        if hd1[0]!='NN': continue
        for hd2 in hds:
            if hd2[0]!='NE': continue
            print >>f_out, "Name_Appos_%s\t%s\t%s"%(hd1[2],hd1[1],hd2[1])

def print_coref(hds, f_out):
    for hd1 in hds:
        if hd1[0]!='NN': continue
        for hd2 in hds:
            if hd2[0]=='NE':
                print >>f_out, "Name_Coref_%s\t%s\t%s"%(hd1[2],hd1[1],hd2[1])
            else:
                if hd1[2]==hd2[2] and hd1[1]!=hd2[1]:
                    print >>f_out, "Noun_Coref\t%s\t%s"%(hd1[1],hd2[1])

def extract_semlinks(fname, corpus_db, f_out):
    doc=exml.make_syntax_doc()
    reader=exml.ExportCorpusReader(doc,fname)
    alph=CPPAlphabet()
    db_texts=corpus_db.corpus.attribute(corpus_d_sattr.get(corpus_db.corpus_name,
                                                        'text_id'),
                                     's')
    old_stop=0
    txt_no=0
    ref_db=corpus_db.db.referential
    while True:
        try:
            new_stop=reader.addNext()
        except StopIteration:
            break
        texts=doc.get_objects_by_class(exml.Text, old_stop,new_stop)
        ana_links={}
        for txt in texts:
            print txt.origin
            trees=doc.get_objects_by_class(tree.Tree,txt.span[0],txt.span[-1])
            for t in trees:
                for n in t.topdown_enumeration():
                    info=getattr(n,'anaphora_info',None)
                    if info is not None:
                        if info[0] in ['anaphoric','cataphoric','coreferential','bound']:
                            get_entry(ana_links,n)['rel']=info
                #print ' '.join([n.word for n in t.terminals])
            determine_set_ids(ana_links,alph)
            # add NE info
            for t in trees:
                all_spans=[en_extract.add_ne_db(t, ne_range, t.span[0], corpus_db)
                           for ne_range in en_extract.extract_ne_old(t)]
                sent_start=t.span[0]
                for headword, span, semtag, span_parts in all_spans:
                    n=en_extract.get_node_ver1(t, span[0]-sent_start, span[-1]-sent_start)
                    n.en_info=semtag
                    entry=get_entry(ana_links,get_maximal_projection(n))
                    entry['en_cls']=semtag
                    entry['min_ids']=span
            chain_heads=defaultdict(set)
            for t in trees:
                for n in t.topdown_enumeration():
                    n_id=n.xml_id
                    if n_id in ana_links:
                        entry=ana_links[n_id]
                        hds=[]
                        get_heads(n,hds)
                        print_appos(hds, f_out)
                        if 'set_id' in entry:
                            ch=chain_heads[entry['set_id']]
                            ch.update(hds)
            for k,vs in chain_heads.iteritems():
                print_coref(vs, f_out)
        doc.clear_markables(old_stop,new_stop)
        old_stop=new_stop

def main(fname, corpus_db):
    doc=exml.make_syntax_doc()
    reader=exml.ExportCorpusReader(doc,fname)
    alph=CPPAlphabet()
    db_texts=corpus_db.corpus.attribute(corpus_d_sattr.get(corpus_db.corpus_name,
                                                        'text_id'),
                                     's')
    old_stop=0
    txt_no=0
    ref_db=corpus_db.db.referential
    while True:
        try:
            new_stop=reader.addNext()
        except StopIteration:
            break
        texts=doc.get_objects_by_class(exml.Text, old_stop,new_stop)
        ana_links={}
        for txt in texts:
            print txt.origin
            trees=doc.get_objects_by_class(tree.Tree,txt.span[0],txt.span[-1])
            for t in trees:
                for n in t.topdown_enumeration():
                    info=getattr(n,'anaphora_info',None)
                    if info is not None:
                        if info[0] in ['anaphoric','cataphoric','coreferential','bound']:
                            get_entry(ana_links,n)['rel']=info
                #print ' '.join([n.word for n in t.terminals])
            determine_set_ids(ana_links,alph)
            # add NE info
            for t in trees:
                all_spans=[en_extract.add_ne_db(t, ne_range, t.span[0], corpus_db)
                           for ne_range in en_extract.extract_ne_old(t)]
                sent_start=t.span[0]
                for headword, span, semtag, span_parts in all_spans:
                    n=en_extract.get_node_ver1(t, span[0]-sent_start, span[-1]-sent_start)
                    entry=get_entry(ana_links,get_maximal_projection(n))
                    entry['en_cls']=semtag
                    entry['min_ids']=span
            for t in trees:
                for n in t.topdown_enumeration():
                    n_id=n.xml_id
                    if n_id in ana_links:
                        entry=ana_links[n_id]
                        entry['span']=n.span
                        if 'min_ids' not in entry:
                            entry['min_ids']=get_min(n).span
            db_span=db_texts[txt_no][:2]
            assert db_span==(txt.span[0],txt.span[-1]-1), (db_span, txt.span)
            refs=ref_db.find_one({'_id':txt_no})
            if refs is None:
                refs={'_id':txt_no}
            refs['release']=ana_links
            ref_db.save(refs)
            txt_no+=1
        doc.clear_markables(old_stop,new_stop)
        old_stop=new_stop

if __name__=='__main__':
    main(sys.argv[1], get_corpus(sys.argv[2]))
        
        
