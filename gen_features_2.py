import json
from pytree import export
from annodb import database
from getopt import getopt
from java_jcc import make_sd
import re
import sys
import morpha

SIMPLE=True
want_norel=False
only_arg1=False
only_arg2=False

thatcompl_verbs=set()
for l in file('/export/local/yannick/verbnet-3.1/thatcompl.txt'):
    thatcompl_verbs.add(l.strip())

def find_node(t,off,l):
    try:
        n=t.terminals[off]
    except IndexError:
        return t.terminals[-1]
    #print >>sys.stderr,[n.word for n in t.terminals]
    #print >>sys.stderr,n,off,n.start
    while n.parent and n.end<off+l:
        n=n.parent
    while n.parent and len(n.parent.children)==1:
        n=n.parent
    return n

def find_node_simple(t,off,l):
    for n in t.terminals:
        if n.start>=off:
            break
    while n.parent and n.end<off+l:
        n=n.parent
    return n

trace_re=re.compile('([=-][0-9]+)+$')
def rm_trace(cat):
    if SIMPLE:
        if '-' in cat:
            cat=cat[:cat.index('-')]
        if '=' in cat:
            cat=cat[:cat.index('=')]
        return cat
    else:
        cat=trace_re.sub('',cat)
        return cat

def conn_str(conn,fs):
    fs.append('CS='+'+'.join(['_'.join(ws) for ws in conn]))

def find_vp(node):
    for n in node.children:
        if n.cat.startswith('VP'):
            return True
    return False

def find_trace(node):
    for n in node.children:
        if n.start==n.end:
            return True
    return False

def syn_features(node,fs):
    fs.append('sS'+rm_trace(node.cat))
    if node.parent is None:
        fs.append('sP-')
    else:
        fs.append('sP'+rm_trace(node.parent.cat))
        chlds=node.parent.children
        chld_idx=chlds.index(node)
        assert chlds[chld_idx] is node
        if chld_idx==0:
            fs.append('sL-')
        else:
            fs.append('sL'+rm_trace(chlds[chld_idx-1].cat))
        try:
            rsib=chlds[chld_idx+1]
            fs.append('sR'+rm_trace(chlds[chld_idx+1].cat))
            fs.append('rsVP'+'-+'[find_vp(rsib)])
            if not SIMPLE:
                fs.append('rsTr'+'-+'[find_trace(rsib)])
        except IndexError:
            fs.append('sR-')

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

def mood_features(node,fs,what):
    """extracts mood features.
    0 = only name of extraction pattern
    1 = only verb pos
    2 = only modal/negative presence or absence
    4 = modal words
    3 = vpos+modal, 5 = vpos+mword
    8 = Miltsakaki 4-tuple as one feature
    9 = as four distinct features 
    """
    args=get_arguments(node)
    if args:
        arg1,arg2,syn_tp=args
        fs.append('mp'+syn_tp)
        if arg1 and not only_arg2:
            if what in [8,9]:
                v_result=['']*3
                find_verb(arg1,v_result)
                if what==8:
                    fs.append('mV1'+'.'.join(v_result))
                else:
                    for i,vres in enumerate(v_result):
                        fs.append('mV1%d=%s'%(i,vres))
            elif 0<=what<8:
                if what&1==1:
                    vb=find_verb_2(arg1)
                    if vb:
                        fs.append('mV1'+vb.cat)
                    else:
                        fs.append('mV1-')
                if what&6!=0:
                    md=[]
                    find_modals(arg1,md,(what&4==4))
                    if md:
                        for m in md:
                            fs.append('mM1'+m)
                    else:
                        fs.append('mM1-')
        if arg2 and not only_arg1:
            if what in [8,9]:
                v_result=['']*3
                find_verb(arg2,v_result)
                if what==8:
                    fs.append('mV2'+'.'.join(v_result))
                else:
                    for i,vres in enumerate(v_result):
                        fs.append('mV2%d=%s'%(i,vres))
            elif 0<=what<8:
                if what&1==1:
                    vb=find_verb_2(arg2)
                    if vb:
                        fs.append('mV2'+vb.cat)
                    else:
                        fs.append('mV2-')
                if what&6!=0:
                    md=[]
                    find_modals(arg2,md,(what&4==4))
                    if md:
                        for m in md:
                            fs.append('mM2'+m)
                    else:
                        fs.append('mM2-')
    else:
        if node.parent:
            #print >>sys.stderr, "No args identified: %s"%(node.parent.to_full([]))
            pass

def do_lex(node,fs):
    args=get_arguments(node)
    if args:
        try:
            a1_lemma=args[0].head.lemma
            fs.append('SH1='+a1_lemma)
        except AttributeError:
            pass
        try:
            a2_lemma=args[1].head.lemma
            fs.append('SH2='+a2_lemma)
        except AttributeError:
            pass

def as_features(node):
    args=get_arguments(node)
    if args and args[2] in ['in-sbar','in-pp_s']:
        arg2=args[1]
        try:
            a2_lemma=arg2.head.lemma
        except AttributeError:
            pass
        else:
            print >>sys.stderr, arg2.head.lemma, arg2.head.lemma in thatcompl_verbs
            if arg2.head.lemma in thatcompl_verbs:
                a2_args=sorted(['%s_%s'%(n.cat,rel) for (rel,n) in arg2.head.sd_dep])
                fs.append('asT+')
                fs.append('asTa'+'-'.join(a2_args))
                for a2 in a2_args:
                    fs.append('asT1'+a2)
            else:
                fs.append('asT-')
        

if __name__=='__main__':
    use_conn=False
    use_syn=False
    use_mood=None
    use_as=True
    use_lex=False
    multiclass=False
    opts,args=getopt(sys.argv[1:], 'csSM:mr12L')
    #print >>sys.stderr, args
    db=database.get_corpus(args[0])
    for k,v in opts:
        if k=='-c': use_conn=True
        elif k=='-s':
            use_syn=True
            SIMPLE=False
        elif k=='-S':
            use_syn=True
            SIMPLE=True
        elif k=='-m': multiclass=True
        elif k=='-r':
            multiclass=True
            want_norel=True
        elif k=='-1': only_arg1=True
        elif k=='-2': only_arg2=True
        elif k=='-M':
            use_mood=int(v)
        elif k=='-L':
            use_lex=True
    for l in file(args[1]):
        file_name,sent_no,offset,length,span,conn,cls = json.loads(l)
        if multiclass:
            if cls is None:
                if want_norel:
                    cls='NoRel'
                else:
                    continue
            target=cls
        else:
            target=(cls is not None)
        if args[0]=='PTB':
            sent_no=db.sentences.cpos2struc(span[0])
        doc=db.get_parses(sent_no)
        #print >>sys.stderr, conn, file_name, sent_no
        try:
            t=export.from_json(doc['release'])
        except KeyError:
            try:
                t=export.from_json(doc['pcfgla'])
            except KeyError:
                print >>sys.stderr, "Cannot find sentence %d. Arrgh!"%(sent_no,)
                continue
        fs=[]
        node=None
        node1=None
        if use_conn: conn_str(conn,fs)
        if use_syn:
            node=find_node(t,offset,length)
            syn_features(node,fs)
        if use_mood is not None:
            node1=find_node_simple(t,offset,length)
            mood_features(node1,fs,use_mood)
        if use_as and conn==[['as']]:
            make_sd(t)
            morpha.lemmatize(t)
            if node1==None:
                node1=find_node_simple(t,offset,length)
            as_features(node1)
        if use_lex:
            make_sd(t)
            morpha.lemmatize(t)
            if node1==None:
                node1=find_node_simple(t,offset,length)
            do_lex(node1,fs)
        print json.dumps([0,fs,target,span])
