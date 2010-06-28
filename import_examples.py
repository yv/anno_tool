#!/usr/bin/python
# -*- encoding: iso-8859-15 -*-
import sys
import pytree.tree as tree
import pytree.export as export
from mmax_tools import write_basedata, write_markables, \
     words_fname, write_dotmmax

MAX_LEN=10
conns=['nachdem','während','seitdem','sobald']
coref_sets={}
examples={}
for c in conns:
    examples[c]=[]

# print >>sys.stderr,"reading coref sets...",
# for l in file('/home/yannick/corpora/tueba-convert/tueba-sets.txt'):
#     line=l.strip().split()
#     sid,node_id=line[0].split(':')
#     coref_sets[(sid,node_id)]=line[1]
# print >>sys.stderr,"done."

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
                if new_start<new_end:
                    markables.append(('unit',None,{'tag':'main'},
                                      pos+new_start,pos+new_end))
                else:
                    print >>sys.stderr, "Cannot tag main: %s"%(pp.to_penn(),)
        pos+=len(t.terminals)
        write_basedata(words_fname('mmax',docid),tokens)
        write_markables('mmax',docid,markables)
        write_dotmmax('mmax',docid)

def write_html(entries,docid):
    f=file(docid+'.html','w')
    print >>f, """<html>
<head><title>%s</title></head>
<body>
<table>
"""
    for t,t_old,n in entries:
        print >>f, "<tr bgcolor=\"#eeeeee\"><td><b>s%s</b><i>"%(t.sent_no)
        for n1 in t_old.terminals:
            print >>f, n1.word
        print >>f, "</i>"
        for i in xrange(len(t.terminals)):
            if i==n.start:
                print >>f,"<b>"
            print >>f, t.terminals[i].word
            if i+1==n.end:
                print >>f,"</b>"
        print >>f,"</td></tr>"
        print >>f,"<tr><td>Rel:</td></tr"
    print >>f,"""</table>
</body>
</html>
"""
    f.close()

packet_num=0
t_last=None
for t in export.read_trees(file('/home/yannickv/tmp/r6pre1/r6-komplett-morph.export')):
    sent_wanted=False
    for n in t.terminals:
        if (n.word.lower() in conns and
            n.cat in ['KOUS','KON']):
            c=n.word.lower()
            examples[c].append((t,t_last,n))
            if len(examples[c])==MAX_LEN:
                write_mmax(examples[c],'%d_%s'%(packet_num,c.replace('ä','ae')))
                write_html(examples[c],'%d_%s'%(packet_num,c.replace('ä','ae')))
                examples[c]=[]
                packet_num +=1
    t_last=t
for c in examples:
    if examples[c]:
        write_mmax(examples[c],'%d_%s_x'%(packet_num,c.replace('ä','ae')))
        write_html(examples[c],'%d_%s_x'%(packet_num,c.replace('ä','ae')))
        packet_num +=1
        
