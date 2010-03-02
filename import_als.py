#!/usr/bin/python
# -*- encoding: iso-8859-15 -*-
import sys
import re
import pytree.tree as tree
import pytree.export as export
from mmax_tools import write_basedata, write_markables, \
     words_fname, write_dotmmax

MAX_LEN=10
conns=['als']
coref_sets={}
examples=[]
not_a_komp=set('munter bieder lokker inner voller makaber'.split())

print >>sys.stderr,"reading coref sets...",
for l in file('/home/yannick/corpora/tueba-convert/tueba-sets.txt'):
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
            #print sent_id,node.id,attrs
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

def write_html(entries,docid):
    f=file(docid+'.html','w')
    print >>f, """<html>
<head><title>%s</title></head>
<body>
<table>
"""%(docid,)
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

def find_finverb(node):
    if (node.isTerminal() and
        node.cat.startswith('V') and
        node.cat.endswith('FIN')):
        yield node
    for n in node.children:
        if n.cat in ['VF','MF','NF']:
            continue
        for n1 in find_finverb(n):
            yield n1

comparative_adja_re=re.compile('(.*er)e[rmns]?$')
comparative_adjd_re=re.compile('(?:.*er|mehr)$')
def check_als(t,node):
    # step 1: look for comparative
    for n in t.terminals[:node.start]:
        if n.cat=='ADJA':
            m=comparative_adja_re.match(n.word)
            if m and not m.group(1).lower() in not_a_komp:
                print "%s ADJA_komp: %s"%(t.sent_no, n.to_penn(),)
                return False
        if n.cat=='ADJD' and comparative_adjd_re.match(n.word):
            if n.word.lower() not in not_a_komp:
                print "%s ADJD_komp: %s"%(t.sent_no, n.to_penn(),)
                return False
    # step 2: look for konjunktiv full verb within SIMPX
    n1=node.parent
    while n1.cat not in ['SIMPX','R-SIMPX']:
        n1=n1.parent
        if n1 is None:
            break
    if n1:
        for n in find_finverb(n1):
             if n.morph[2]=='k':
                print "%s konjunktiv: %s"%(t.sent_no, n1.to_penn())
                return False
    return True

packet_num=0
t_last=None
for t in export.read_trees(file('/home/yannick/corpora/tueba4.export')):
    sent_wanted=False
    for n in t.terminals:
        if (n.word.lower()=='als' and
            n.cat=='KOUS' and
            check_als(t,n)):
            c=n.word.lower()
            examples.append((t,t_last,n))
            if len(examples)==MAX_LEN:
                write_mmax(examples,'als_%02d'%(packet_num,))
                write_html(examples,'als_%02d'%(packet_num,))
                examples=[]
                packet_num +=1
    t_last=t

if examples:
        write_mmax(examples,'als_%02dx'%(packet_num,))
        write_html(examples,'als_%02dx'%(packet_num,))
        packet_num +=1

