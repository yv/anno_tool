#!/usr/bin/python
# -*- encoding: iso-8859-15 -*-
import sys
import pytree.tree as tree
import pytree.export as export
from mmax_tools import write_basedata, write_markables, \
     words_fname, write_dotmmax

MAX_LEN=10
conns=['als','nachdem','bevor','während']
sents='7626 7387 9122 10704 10864 23738 1200'.split()
coref_sets={}
examples={}

print >>sys.stderr,"reading coref sets...",
for l in file('/mnt/stick/tueba-convert/tueba-sets.txt'):
    line=l.strip().split()
    sid,node_id=line[0].split(':')
    coref_sets[(sid,node_id)]=line[1]
print >>sys.stderr,"done."

def add_phrases(node,pos0,markables,sent_id):
    if node.cat=='NX' and not (node.edge_label=='APP' or
                               node.edge_label=='HD' and
                               node.parent.cat!='PX'):
        attrs={}
        if (sent_id,node.id) in coref_sets:
            attrs['coref_set']=coref_sets[(sent_id,node.id)]
            print sent_id,node.id,attrs
        markables.append(('phrase',None,attrs,pos0+node.start,pos0+node.end))
    elif node.cat[:2]=='VV':
        # also mark full verbs
        markables.append(('phrase',None,{},pos0+node.start,pos0+node.end))        
    for n in node.children:
        add_phrases(n,pos0,markables,sent_id)
def write_mmax(entries,docid):
    tokens=[]
    markables=[]
    pos=0
    t_last=None
    for t,t_old,n in entries:
        if not t_last or (t_last.sent_no!=t.sent_no and
            t_old and t_old.sent_no!=t_last.sent_no):
            markables.append(('sentence',None,
                              {'orderID':t_old.sent_no,'tag':'context'},
                              pos,pos+len(t_old.terminals)))
            tokens.extend([n1.word for n1 in t_old.terminals])
            pos+=len(t_old.terminals)
        markables.append(('sentence',None,
                          {'orderID':t.sent_no,'tag':'annotate'},
                          pos,pos+len(t.terminals)))
        # TODO: mark coref, KOUS element, ...
        for i,n1 in enumerate(t.terminals):
            markables.append(('pos',None,{'tag':n1.cat},
                              pos+i,pos+i+1))
            tokens.append(n1.word)
        for n1 in t.roots:
            add_phrases(n1,pos,markables,t.sent_no)
        markables.append(('konn',None,{'word':n.word},
                          pos+n.start,pos+n.end))
        if n.parent.cat=='C':
            pp=n.parent.parent
            assert pp.cat in ['SIMPX','FKONJ']
            markables.append(('unit',None,{'tag':'sub'},
                              pos+pp.start,pos+pp.end))
            old_start=pp.start
            old_end=pp.end
            while pp.edge_label=='KONJ':
                pp=pp.parent
            if pp.parent:
                pp=pp.parent
                while pp.parent and pp.cat not in ['SIMPX','R-SIMPX','FKONJ']:
                    pp=pp.parent
                new_start=pp.start
                new_end=pp.end
                if new_start==old_start:
                    new_start=old_end
                elif new_end==old_end:
                    new_end=old_start
                markables.append(('unit',None,{'tag':'main'},
                              pos+new_start,pos+new_end))
        pos+=len(t.terminals)
        write_basedata(words_fname('mmax',docid),tokens)
        write_markables('mmax',docid,markables)
        write_dotmmax('mmax',docid)

packet_num=0
t_last=None
for t in export.read_trees(file('/home/yannick/tueba4.export')):
    sent_wanted=False
    for n in t.terminals:
        if (n.word.lower() in ['als','nachdem','bevor','während'] and
            n.cat=='KOUS'):
            c=n.word.lower()
            if t.sent_no in sents:
                examples[t.sent_no]=(t,t_last,n)
    t_last=t
all_examples=[]
print sents
for sent_no in sents:
    all_examples.append(examples[sent_no])
write_mmax(all_examples,'beispiele')
    
