import sys
sys.path.append('/home/yannickv/proj/pytree')

import json
from pytree import export, deps
from graph_search import dijkstra_search
from annodb import database
from getopt import getopt
from array import array
from dist_sim.fcomb import FCombo
from ml_utils import mkdata
from java_jcc import make_sd
import morpha
import numpy
import traceback
import re
import sys
import me_opt_new as me_opt

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

def pivot_features(n0,n1,n2,feat):
    lst_up_1=[]
    lst_up_2=[]
    n=n1
    while n:
        lst_up_1.append(n)
        n=n.parent
    n=n2
    while n:
        lst_up_2.append(n)
        n=n.parent
    set_1=set(lst_up_1)
    set_2=set(lst_up_2)
    n=n0
    set_up_0=set()
    while n and n not in set_1 and n not in set_2:
        set_up_0.add(n)
        n=n.parent
    pos1=-1
    pos2=-1
    pos0=-1
    for i,n_chld in enumerate(n.children):
        if n_chld in set_up_0:
            pos0=i
        if n_chld in set_1:
            pos1=i
        if n_chld in set_2:
            pos2=i
    syms=[n.cat]+[n_chld.cat for n_chld in n.children]
    syms[pos0+1]+='*C'
    syms[pos1+1]+='*1'
    syms[pos2+1]+='*2'
    feat.append('pvA='+'-'.join(syms))
    if pos1==-1:
        feat.append('pv1=P')
    else:
        if pos1<pos0:
            feat.append('pv1=L')
        else:
            feat.append('pv1=R')
    if pos2==-1:
        feat.append('pv2=P')
    else:
        if pos2<pos0:
            feat.append('pv2=L')
        else:
            feat.append('pv2=R')

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
    last_tree=None
    def __init__(self,**kw):
        self.__dict__.update(kw)
    def set_from_anno(self,anno):
        spans=anno['conn_parts']
        self.spans=spans
        ws=[tuple([w.lower() for w in words[span[0]:span[1]]]) for span in spans]
        self.ws=ws
        if len(ws)==1 and ws[0][-1] in normalize_connector:
            ws=((ws[0][-1],),)
            spans=[[spans[-1][1]-1,spans[-1][1]]]
        self.sent_no=sents.cpos2struc(spans[-1][0])
        s_start,s_end=sents[self.sent_no][:2]
        argspan1=anno['arg1']
        while left_ignore_re.match(words[argspan1[0]]):
            argspan1[0]+=1
        while right_ignore_re.match(words[argspan1[1]-1]):
            argspan1[1]-=1
        argspan1[0]-=s_start
        argspan1[1]-=s_start
        self.argspan1=argspan1
        argspan2=anno['arg2']
        while left_ignore_re.match(words[argspan2[0]]):
            argspan2[0]+=1
        while right_ignore_re.match(words[argspan2[1]-1]):
            argspan2[1]-=1
        argspan2[0]-=s_start
        argspan2[1]-=s_start
        self.argspan2=argspan2
        if ConnInfo.last_tree is not None and ConnInfo.last_tree.sent_no==self.sent_no:
            print "Reused s%s"%(self.sent_no)
            t=self.last_tree
        else:
            t_json=ptb.get_parses(self.sent_no)['release']
            t=export.from_json(t_json)
            make_sd(t)
            morpha.lemmatize(t)
            t.sent_no=self.sent_no
            ConnInfo.last_tree=t
        self.t=t
        if spans[0][0]-s_start>=len(t.terminals) or spans[0][0]-s_start<0:
            self.kind='multi-sentence'
            self.t=None
            return
        self.n_conn_start=t.terminals[spans[0][0]-s_start]
        self.n_conn_end=t.terminals[spans[-1][1]-s_start-1]
        if argspan1[0]<0:
            self.kind='anaphoric'
            self.n1=None
        elif argspan1[1]>=len(t.terminals):
            self.kind='cataphoric'
            self.n1=None
        else:
            try:
                if t.terminals[argspan1[0]].word=='that' and t.terminals[argspan1[0]].cat=='IN':
                        argspan1[0]+=1
                        while left_ignore_re.match(t.terminals[argspan1[0]].word):
                            argspan1[0]+=1
            except IndexError:
                print argspan1, t.terminals
                raise
            self.n1=find_node_simple(t,argspan1[0],argspan1[1]-argspan1[0])
        self.n2=find_node_simple(t,argspan2[0],argspan2[1]-argspan2[0])


def pruned_candlist(n_start,paths):
    cands=[]
    gather_candidates_up(n_start,[],paths,cands)
    if not cands:
        try:
            parent_full=n_start.parent.to_full([])
        except KeyError:
            parent_full=n_start.parent
        try:
            possible_keys=paths[0][n_start.cat][0].keys()
        except KeyError:
            possible_keys=None
        print >>sys.stderr, "No cands for %s (parent=%s, feasible=%s)"%(n_start.to_full([]),parent_full,possible_keys)
        return []
    max_score=max([x[3] for x in cands])
    return [x for x in cands if x[3]>=0.1*max_score]

## PTB sections (start)
##  0 ->       0
## 10 ->  441305
## 20 ->  956696
## 22 -> 1004073
## 23 -> 1044112
## 24 -> 1140913
## train on sec 00-09, test on 10-21
train_criteria={'level':'pdtb','reltype':'Explicit','span':{'$lt':441305}}
test_criteria={'level':'pdtb','reltype':'Explicit','span':{'$gte':441305,'$lt':1004073}}


## tiny train and test set for debugging
##train_criteria={'level':'pdtb','reltype':'Explicit','span':{'$lt':4000}}
##test_criteria={'level':'pdtb','reltype':'Explicit','span':{'$gte':4000,'$lt':8000}}

def sd_neighbours(n):
    result=[]
    for rel,n_to in n.sd_gov:
        result.append((1,n_to,'+'+rel))
    for rel,n_from in n.sd_dep:
        result.append((1,n_from,'-'+rel))
    return result

def make_deppath(node1,node2):
    try:
        if node1.isTerminal():
            head1=node1
        else:
            head1=node1.head
        if node2.isTerminal():
            head2=node2
        else:
            head2=node2.head
    except AttributeError:
        return None
    return dijkstra_search([head1],[head2],sd_neighbours)


# Step 1: gather paths
for anno in annos.find(train_criteria):
    ci=ConnInfo()
    try:
        ci.set_from_anno(anno)
    except:
        traceback.print_exc()
        break
    if ci.t is None:
        continue
    if ci.n1 is not None:
        path1=make_path(ci.n_conn_start,ci.n1)
        enter_path(path1[0],path1[1],all_paths_arg1)
        dpath=make_deppath(ci.n_conn_start,ci.n1)
        if dpath:
            print "N1:",make_deppath(ci.n_conn_start,ci.n1)
        else:
            try:
                print "No N1:",ci.n_conn_start,ci.n1,ci.n_conn_start.head.sd_gov,ci.n1.head.sd_gov
            except AttributeError:
                print "No N1 (no head):",ci.n_conn_start,ci.n1
    print "N2:",make_deppath(ci.n_conn_end,ci.n2)
    path2=make_path(ci.n_conn_end,ci.n2)
    enter_path(path2[0],path2[1],all_paths_arg2)

def anaphoric_features(ci,feats):
    feats.append("C"+'+'.join(['_'.join(ws) for ws in ci.ws]))
    feats.append("W1"+ci.n_conn_start.word)
    feats.append("P1"+ci.n_conn_start.cat)
    terms=ci.t.terminals
    feats.append("PA"+''.join([n.cat for span in ci.spans for n in ci.t.terminals[span[0]:span[1]]]))

def arg2only_features(ci,c,feats):
    feats.append("C"+'+'.join(['_'.join(ws) for ws in ci.ws]))
    feats.append("W1"+ci.n_conn_start.word)
    feats.append("P1"+ci.n_conn_start.cat)
    n2=c[2]
    path2=make_path(ci.n_conn_end,n2)
    feats.append("p2%s+%s"%('-'.join(path2[0]),'-'.join(path2[1])))
    dpath2=make_deppath(ci.n_conn_end,n2)
    if dpath2 is not None:
        feats.append("d2%s"%(''.join(dpath2[3])))
    else:
        feats.append("d2-")

def both_features(ci,c1,c2,feats):
    feats.append("C"+'+'.join(['_'.join(ws) for ws in ci.ws]))
    feats.append("W1"+ci.n_conn_start.word)
    feats.append("P1"+ci.n_conn_start.cat)
    n1=c1[2]
    n2=c2[2]
    path1=make_path(ci.n_conn_start,n1)
    feats.append("p2%s+%s"%('-'.join(path1[0]),'-'.join(path1[1])))
    path2=make_path(ci.n_conn_end,n2)
    feats.append("p2%s+%s"%('-'.join(path2[0]),'-'.join(path2[1])))
    pivot_features(ci.n_conn_end,n1,n2,feats)
    dpath1=make_deppath(ci.n_conn_start,n1)
    if dpath1 is not None:
        print dpath1
        feats.append("d1%s"%(''.join(dpath1[3])))
    else:
        feats.append("d1-")
    dpath2=make_deppath(ci.n_conn_end,n2)
    if dpath2 is not None:
        feats.append("d2%s"%(''.join(dpath2[3])))
    else:
        feats.append("d2-")

# Step 2: determine path candidates and train classifier/rankers
fc_anaphoric=FCombo(2,bias_item='**BIAS**')
data_anaphoric=[]
fc_arg2only=FCombo(2)
data_arg2only=[]
fc_both=FCombo(2)
data_both=[]
for anno in annos.find(train_criteria):
    ci=ConnInfo()
    try:
        ci.set_from_anno(anno)
    except:
        traceback.print_exc()
        break
    if ci.t is None:
        continue
    t=ci.t
    morpha.lemmatize(t)
    cands2=pruned_candlist(ci.n_conn_end,all_paths_arg2)
    if ci.n1 is None:
        anaphoric_val=False
        ## create arg2only examples
        good=[]
        bad=[]
        for c in cands2:
            feat=[]
            arg2only_features(ci,c,feat)
            fval=fc_arg2only(mkdata(feat))
            if ci.n2==c[2]:
                good.append(fval)
            else:
                bad.append(fval)
        if good and bad:
            data_arg2only.append([good,bad])
    else:
        anaphoric_val=True
        ## create _both examples
        n1=ci.n1
        cands1=pruned_candlist(ci.n_conn_start,all_paths_arg1)
        good=[]
        bad=[]
        for c1 in cands1:
            for c2 in cands2:
                ## create arg_both examples
                feat=[]
                both_features(ci,c1,c2,feat)
                fval=fc_both(mkdata(feat))
                if ci.n1==c1[2] and ci.n2==c2[2]:
                    good.append(fval)
                else:
                    bad.append(fval)
        if good and bad:
            data_both.append([good,bad])
    feat=[]
    anaphoric_features(ci,feat)
    data_anaphoric.append((fc_anaphoric(mkdata(feat)),anaphoric_val))

## Step 2b: create classifiers/rankers
fc_arg2only.dict.growing=False
fc_both.dict.growing=False
fc_anaphoric.dict.growing=False
weights_arg2only=me_opt.train_me_sparse(data_arg2only,fc_arg2only.dict)
weights_both=me_opt.train_me_sparse(data_both,fc_both.dict)
x=numpy.zeros(len(fc_anaphoric.dict),'d')
iflag,n_iter,x,d1=me_opt.run_lbfgs(x,me_opt.sparse_unary_func,(data_anaphoric,))
weights_anaphoric=x

## Step 3: evaluate everything
arg1_total=0
arg1_exact=0
arg1_head=0

arg2_total=0
arg2_exact=0
arg2_head=0

anaphoric_eval=numpy.zeros([2,2])

for anno in annos.find(test_criteria):
    ci=ConnInfo()
    try:
        ci.set_from_anno(anno)
    except:
        traceback.print_exc()
        break
    if ci.t is None:
        continue
    t=ci.t
    cands2=pruned_candlist(ci.n_conn_end,all_paths_arg2)
    if ci.n1 is None:
        anaphoric_val=False
        ## create arg2only examples
        best=None
        best_score=-1000
        for c in cands2:
            feat=[]
            arg2only_features(ci,c,feat)
            fval=fc_arg2only(mkdata(feat))
            score=fval.dotFull(weights_arg2only)
            if score>best_score:
                best=c
                best_score=score
        arg2_total+=1
        if best!=None and ci.n2==best[2]:
            arg2_exact+=1
        if best!=None and ci.n2.head==best[2].head:
            arg2_head+=1
    else:
        anaphoric_val=True
        ## create _both examples
        n1=ci.n1
        cands1=pruned_candlist(ci.n_conn_start,all_paths_arg1)
        best=(None,None)
        best_score=-1000
        for c1 in cands1:
            for c2 in cands2:
                ## create arg_both examples
                feat=[]
                both_features(ci,c1,c2,feat)
                fval=fc_both(mkdata(feat))
                score=fval.dotFull(weights_both)
                if score>best_score:
                    best=(c1,c2)
                    best_score=score
        best1,best2=best
        arg1_total+=1
        if best1!=None:
            if ci.n1==best1[2]:
                arg1_exact+=1
            if ci.n1.head==best1[2].head:
                arg1_head+=1
            else:
                print ' '.join([n.word for n in ci.t.terminals]),ci.ws
                print "wrong Arg1: %s"%(best1[2].to_full([]))
                print "wanted: %s"%(ci.n1.to_full([]))
        arg2_total+=1
        if best2!=None:
            if ci.n2==best2[2]:
                arg2_exact+=1
            if ci.n2.head==best2[2].head:
                arg2_head+=1
    feat=[]
    anaphoric_features(ci,feat)
    anaphoric_decision=(fc_anaphoric(mkdata(feat)).dotFull(weights_anaphoric)>0)
    anaphoric_eval[anaphoric_val][anaphoric_decision]+=1

print "Arg1(exact): %d/%d=%.3f"%(arg1_exact,arg1_total,float(arg1_exact)/arg1_total)
print "Arg1(head):  %d/%d=%.3f"%(arg1_head,arg1_total,float(arg1_head)/arg1_total)
print "Arg2(exact): %d/%d=%.3f"%(arg2_exact,arg2_total,float(arg2_exact)/arg2_total)
print "Arg2(head):  %d/%d=%.3f"%(arg2_head,arg2_total,float(arg2_head)/arg2_total)
prec=float(anaphoric_eval[1,1])/anaphoric_eval[:,1].sum()
recl=float(anaphoric_eval[1,1])/anaphoric_eval[1,:].sum()
f1=2*prec*recl/(prec+recl)
print "anaphoric: P=%d/%d=%.3f R=%d/%d=%.3f F1=%.3f"%(anaphoric_eval[1,1],anaphoric_eval[:,1].sum(),prec,
                                                 anaphoric_eval[1,1],anaphoric_eval[1,:].sum(),recl,
                                                 f1)
