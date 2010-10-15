import json
from pytree import export
from annodb import database
from getopt import getopt
from array import array
import re
import sys

ptb=database.get_corpus('PTB')
annos=ptb.db.annotation
words=ptb.words
sents=ptb.sentences
text_id=ptb.corpus.attribute('text_id','s')

normalize_connector=set(['after','before','because','when','until','since','if'])

def new_paths():
    return ({},{},array('i',[0]))

all_paths_arg1=new_paths()
all_paths_arg2=new_paths()
def enter_path(up_cat,down_cat,node):
    for i,c in enumerate(up_cat):
        if c in node[0]:
            node=node[0][c]
        else:
            node_new=({},{},array('i',[0]))
            node[0][c]=node_new
            node=node_new
    for i,c in enumerate(down_cat):
        if c in node[1]:
            node=node[1][c]
        else:
            node_new=({},{},array('i',[0]))
            node[1][c]=node_new
            node=node_new
    node[2][0]+=1

def gather_candidates_up(syn_node,path,graph_node,cands):
    if syn_node is None or syn_node.cat not in graph_node[0]:
        return
    graph_node2=graph_node[0][syn_node.cat]
    path2=path+[syn_node.cat]
    gather_candidates_down(syn_node,path2,[],graph_node2,cands)
    gather_candidates_up(syn_node.parent,path2,graph_node2,cands)

def gather_candidates_down(syn_node,path_up,path,graph_node,cands):
    if graph_node[2][0]>0:
        cands.append((path_up,path,syn_node,graph_node[2][0]))
    for n in syn_node.children:
        cat2=n.cat
        if cat2 in graph_node[1]:
            gather_candidates_down(n,path_up,path+[cat2],graph_node[1][cat2],cands)

def find_node_simple(t,off,l):
    for n in t.terminals:
        if n.start>=off:
            break
    while n.parent and n.end<off+l:
        n=n.parent
    return n

trace_re=re.compile('([=-][0-9]+)+$')
def rm_trace(cat):
    if '-' in cat:
        cat=cat[:cat.index('-')]
    if '=' in cat:
        cat=cat[:cat.index('=')]
    return cat

def get_arguments(n):
    if n.cat=='IN' and n.parent and n.parent.cat.startswith('SBAR'):
        # complementizer
        arg1=n.parent
        arg2=arg1.parent
        if len(arg1.children)>=2 and arg1.children[1].cat=='S':
            arg1=arg1.children[1]
        while arg2 and arg2.cat in ['VP']:
            arg2=arg2.parent
        return (arg1,arg2,'in-sbar')
    elif (n.cat=='IN' and n.parent and n.parent.cat.startswith('PP') and
          is_s(n.parent.children[-1].cat)):
        n_par=n.parent; n_gp=n_par.parent
        arg1=n_par.children[-1]
        arg2=n_gp
        while arg2 and arg2.cat=='VP':
            arg2=arg2.parent
        return (arg1,arg2,'in-pp_s')
    elif n.cat=='CC' and n.parent and n.parent.cat.startswith('S'):
        # S coordination
        arg1=arg2=None
        n_seen=False
        for n1 in n.parent.children:
            if n1.cat.startswith('S'):
                if not n_seen and arg1 is None:
                    arg1=n1
                elif n_seen:
                    arg2=n1
            elif n1 is n:
                n_seen=True
        return (arg1,arg2,'cc-s')
    elif n.cat=='WRB' and n.parent and n.parent.cat.startswith('WHADVP'):
        n_par=n.parent
        n_gp=n_par.parent
        if n_gp and n_gp.cat.startswith('SBAR'):
            arg1=n_gp
            arg2=arg1.parent
            if len(arg1.children)>=2 and arg1.children[1].cat=='S':
                arg1=arg1.children[1]
            while arg2 and arg2.cat in ['VP']:
                arg2=arg2.parent
            return (arg1,arg2,'wrb-sbar')
    elif n.cat=='RB' and n.parent and n.parent.cat.startswith('ADVP'):
        n_par=n.parent; n_gp=n_par.parent
        if n_gp and n_gp.cat=='S' and n_gp.children[0] is n_par:
            # S-initial adverbial
            arg1=None
            arg2=n_gp
            return (arg1,arg2,'rb_top-s')
    elif n.cat.startswith('PP'):
        n_par=n.parent
        if n_par and n_par.cat=='S' and n_par.children[0] is n:
            # S-initial adverbial
            arg1=None
            arg2=n_par
            return (arg1,arg2,'pp_top-s')
    else:
        return None

def is_s(cat):
    return (cat=='S' or cat.startswith('S-'))

have_form_re=re.compile('(?:has|have|had)$',re.I)
be_pres_re=re.compile('(?:am|is|are)$',re.I)
be_past_re=re.compile('(?:was|were)$',re.I)
def find_verb(n,result):
    if n.cat.startswith('VB'):
        if have_form_re.match(n.word):
            result[0]=n.word.lower()
        elif be_pres_re.match(n.word):
            result[1]='pres'
        elif be_past_re.match(n.word):
            result[1]='past'
        elif n.word.lower()=='been':
            result[1]='been'
        else:
            if n.cat in ['VBP','VBZ']:
                result[2]='pres'
            elif n.cat=='VBD':
                result[2]='past'
            elif n.cat=='VBN':
                result[2]='ppast'
            elif n.cat=='VBG':
                result[2]='ppres'
        return n
    if n.isTerminal():
        return None
    for chld in n.children:
        cc=chld.cat
        if is_s(cc) or cc.startswith('V'):
            find_verb(chld,result)

def find_verb_2(n):
    if n.cat.startswith('VB'):
        return n
    if n.isTerminal():
        return None
    for chld in n.children:
        cc=chld.cat
        if is_s(cc) or cc.startswith('V'):
            vb=find_verb_2(chld)
            if vb:
                return vb

def make_path(n1,n2):
    n=n1
    lst_up=[]
    lst_down=[]
    while n:
        lst_up.append(n)
        n=n.parent
    seen=set(lst_up)
    n=n2
    while n and n not in seen:
        lst_down.append(n)
        n=n.parent
    if n in seen:
        lst_up=lst_up[:lst_up.index(n)+1]
    lst_down.reverse()
    return ([n.cat for n in lst_up],[n.cat for n in lst_down])

def find_modals(n,md,want_word):
    for chld in n.children:
        if chld.isTerminal():
            if chld.word in ["n't","not"]:
                md.append('not')
            elif chld.cat=='MD':
                if want_word:
                    md.append(chld.word)
                else:
                    md.append('+')
        elif is_s(chld.cat) or chld.cat.startswith('V'):
            find_modals(chld,md,want_word)

left_ignore_re=re.compile('(?:[,:]|``)$')
right_ignore_re=re.compile("(?:[,:]|'')$")

class ConnInfo(object):
    def __init__(self,**kw):
        self.__dict__.update(kw)
    def set_from_anno(self,anno):
        spans=anno['conn_parts']
        self.spans=spans
        self.ws=[tuple([w.lower() for w in words[span[0]:span[1]]]) for span in spans]
        if len(ws)==1 and ws[0][-1] in normalize_connector:
            ws=((ws[0][-1],),)
            spans=[[spans[-1][1]-1,spans[-1][1]]]
        self.sent_no=sents.cpos2struc(spans[-1][0])
        s_start,s_end=sents[self.sent_no][:2]
        argspan1=anno['arg1']
        while left_ignore_re.match(words[argspan1[0]]):
            argspan1[0]+=1
        while right_ignore_re.match(words[argspan1[1]]):
            argspan1[1]-=1
        argspan1[0]-=s_start
        argspan1[1]-=s_start
        self.argspan1=argspan1
        argspan2=anno['arg2']
        while left_ignore_re.match(words[argspan2[0]]):
            argspan2[0]+=1
        while right_ignore_re.match(words[argspan2[1]]):
            argspan2[1]-=1
        argspan2[0]-=s_start
        argspan2[1]-=s_start
        self.argspan2=argspan2
        t_json=ptb.get_parses(sent_no)['release']
        self.t=export.from_json(t_json)
        if spans[0][0]-s_start>=len(t.terminals) or spans[0][0]-s_start<0:
            return
        self.n_conn_start=t.terminals[spans[0][0]-s_start]
        self.n_conn_end=t.terminals[spans[-1][1]-s_start-1]
        if argspan1[0]<0:
            self.n1=None
        else:
            self.n1=find_node_simple(t,argspan1[0],argspan1[1]-argspan1[0])
        self.n2=find_node_simple(t,argspan2[0],argspan2[1]-argspan2[0])
        
            

# Step 1: gather paths
for anno in annos.find({'level':'pdtb','reltype':'Explicit'}):
    ci=ConnInfo()
    try:
        ci.set_from_anno(anno)
    except:
        print "Unexpected error:", sys.exc_info()[0]
        continue
    spans=anno['conn_parts']
    ws=[tuple([w.lower() for w in words[span[0]:span[1]]]) for span in spans]
    if len(ws)==1 and ws[0][-1] in normalize_connector:
        ws=((ws[0][-1],),)
        spans=[[spans[-1][1]-1,spans[-1][1]]]
    sent_no=sents.cpos2struc(spans[-1][0])
    s_start,s_end=sents[sent_no][:2]
    argspan1=anno['arg1']
    while left_ignore_re.match(words[argspan1[0]]):
        argspan1[0]+=1
    while right_ignore_re.match(words[argspan1[1]]):
        argspan1[1]-=1
    argspan1[0]-=s_start
    argspan1[1]-=s_start
    argspan2=anno['arg2']
    while left_ignore_re.match(words[argspan2[0]]):
        argspan2[0]+=1
    while right_ignore_re.match(words[argspan2[1]]):
        argspan2[1]-=1
    argspan2[0]-=s_start
    argspan2[1]-=s_start
    try:
        t_json=ptb.get_parses(sent_no)['release']
    except KeyError:
        print "No parse for sentence %d"%(sent_no,)
    t=export.from_json(t_json)
    if spans[0][0]-s_start>=len(t.terminals) or spans[0][0]-s_start<0:
        print >>sys.stderr, "multi-sentence connective: %s"%(ws,)
        continue
    n_conn_start=t.terminals[spans[0][0]-s_start]
    n_conn_end=t.terminals[spans[-1][1]-s_start-1]
    #print words[s_start:s_end+1],ws,n_conn_start.to_full([]),n_conn_end.to_full([])
    if argspan1[0]<0:
        pass
        #print 'arg1=*anaphoric*'
    else:
        n1=find_node_simple(t,argspan1[0],argspan1[1]-argspan1[0])
        #print 'arg1',n1.to_full([])
        path1=make_path(n_conn_start,n1)
        #print path1
        enter_path(path1[0],path1[1],all_paths_arg1)
    n2=find_node_simple(t,argspan2[0],argspan2[1]-argspan2[0])
    #print 'arg2',n2.to_full([])
    path2=make_path(n_conn_end,n2)
    #print path2
    enter_path(path2[0],path2[1],all_paths_arg2)

# Step 2: determine path candidates
for anno in annos.find({'level':'pdtb','reltype':'Explicit'}):
    spans=anno['conn_parts']
    ws=[tuple([w.lower() for w in words[span[0]:span[1]]]) for span in spans]
    if len(ws)==1 and ws[0][-1] in normalize_connector:
        ws=((ws[0][-1],),)
        spans=[[spans[-1][1]-1,spans[-1][1]]]
    sent_no=sents.cpos2struc(spans[-1][0])
    s_start,s_end=sents[sent_no][:2]
    argspan1=anno['arg1']
    while left_ignore_re.match(words[argspan1[0]]):
        argspan1[0]+=1
    while right_ignore_re.match(words[argspan1[1]-1]):
        argspan1[1]-=1
    argspan1[0]-=s_start
    argspan1[1]-=s_start
    argspan2=anno['arg2']
    while left_ignore_re.match(words[argspan2[0]]):
        argspan2[0]+=1
    while right_ignore_re.match(words[argspan2[1]-1]):
        argspan2[1]-=1
    argspan2[0]-=s_start
    argspan2[1]-=s_start
    try:
        t_json=ptb.get_parses(sent_no)['release']
    except KeyError:
        print "No parse for sentence %d"%(sent_no,)
    t=export.from_json(t_json)
    if spans[0][0]-s_start>=len(t.terminals) or spans[0][0]-s_start<0:
        print >>sys.stderr, "multi-sentence connective: %s"%(ws,)
        continue
    n_conn_start=t.terminals[spans[0][0]-s_start]
    n_conn_end=t.terminals[spans[-1][1]-s_start-1]
    print words[s_start:s_end+1],ws,n_conn_start.to_full([]),n_conn_end.to_full([])
    if argspan1[0]<0:
        print 'arg1=*anaphoric*'
    else:
        n1=find_node_simple(t,argspan1[0],argspan1[1]-argspan1[0])
        print 'arg1',[n.word for n in t.terminals[argspan1[0]:argspan1[1]]],n1.to_full([])
        path1=make_path(n_conn_start,n1)
        print path1
        cands=[]
        gather_candidates_up(n_conn_start,[],all_paths_arg1,cands)
        max_score=max([x[3] for x in cands])
        cands=[x for x in cands if x[3]>=0.1*max_score]
        found=False
        for c in cands:
            print "cand[1]:",c
            if c[2]==n1:
                found=True
        if not found:
            print "** Arg1 not covered"
    n2=find_node_simple(t,argspan2[0],argspan2[1]-argspan2[0])
    print 'arg2',n2.to_full([])
    path2=make_path(n_conn_end,n2)
    print path2
    enter_path(path2[0],path2[1],all_paths_arg2)
