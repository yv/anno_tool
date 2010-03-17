import sys
from collections import defaultdict

completely_ignore_attributes=set(['span','id','mmax_level','word'])



class Distribution(defaultdict):
    """represents a distribution that can be added,
    or divided by a scalar. abs(d) gives the L1 metric
    for the distribution"""
    def __init__(self):
        defaultdict.__init__(self,lambda:0)
    def __add__(self,other):
        a=Distribution()
        for k in self:
            a[k]+=self[k]
        for k in other:
            a[k]+=other[k]
        return a
    def __div__(self,val):
        a=Distribution()
        val=float(val)
        for k in self:
            a[k]=self[k]/val
        return a
    def __abs__(self):
        return sum(map(abs,self.itervalues()))

def marginal(dist,pos):
    """computes a marginal distribution from
    one that has tuples as keys"""
    new_dist=Distribution()
    for k in dist.iterkeys():
        new_dist[k[pos]]+=dist[k]
    return new_dist



def m2context(markable,doc):
    """returns the sentence that encloses
    some interesting markable and the previous one"""
    sents=doc.read_markables('sentence')
    sents.sort(key=lambda x:x[3])
    last_ctx=ctx=markable[3:5]
    for sent in sents:
        if sent[3]<=markable[3] and sent[4]>=markable[4]:
            ctx=last_ctx
        last_ctx=sent[3:5]
    return (' '.join(doc.tokens[ctx[0]:ctx[1]]))
            

def m2s(markable,doc):
    sents=doc.read_markables('sentence')
    ctx=markable[3:5]
    for sent in sents:
        if sent[3]<=markable[3] and sent[4]>=markable[4]:
            ctx=sent[3:5]
    return (' '.join(doc.tokens[ctx[0]:markable[3]])+
                     "["+' '.join(doc.tokens[markable[3]:markable[4]])+"]"+
            ' '.join(doc.tokens[markable[4]:ctx[1]]))

def sentencelink(markable,doc):
    sents=doc.read_markables('sentence')
    ctx=markable[3:5]
    sentid=None
    for sent in sents:
        if sent[3]<=markable[3] and sent[4]>=markable[4]:
            try:
                sentid=sent[2]['orderid']
            except KeyError:
                pass
            try:
                sentid=sent[2]['orderID']
            except KeyError:
                pass
            if not sentid:
                print sent[2]
    if sentid is not None:
        return '<a href="http://tintoretto.sfb.uni-tuebingen.de/pycwb/sentence/%s">s%s</a>'%(sentid,sentid)
    return '(no sent)'

def extract_attributes(attrs1,attrs2,key,rel_mapping={}):
    val1=attrs1.get(key,'unmarked')
    val2=attrs2.get(key,'unmarked')
    if key in rel_mapping:
        rmap=rel_mapping[key]
        val1=rmap.get(val1,val1)
        val2=rmap.get(val2,val2)
    return val1,val2


def markable_join(docs,level='konn'):
    """groups markables from different documents by span"""
    mss=[doc.read_markables(level) for doc in docs]
    result=[]
    for ms in mss:
        ms.sort(key=lambda x:x[3:5])
    idxs=[0 for ms in mss]
    len_sum=sum([len(ms) for ms in mss])
    while sum(idxs)<len_sum:
        wanted=min([ms[idx][3:5] for (idx,ms) in zip(idxs,mss)
                    if idx<len(ms)])
        actual=[]
        for i in xrange(len(idxs)):
            k=idxs[i]
            ms=mss[i]
            all_i=[]
            while k<len(ms) and ms[k][3:5]==wanted:
                all_i.append(ms[k])
                k+=1
            idxs[i]=k
            actual.append(all_i)
        result.append(actual)
    return result

def report_attributes(part,names,out=sys.stdout,
                      ignore=completely_ignore_attributes):
    attrs=set()
    pairs=[(name,ms[0][2]) for (name,ms) in zip(names,part) if ms]
    for n,m in pairs:
        attrs.update(m.keys())
    attrs.difference_update(ignore)
    for k in sorted(attrs):
        print >>out, "<tr><td><b>%s</b></td><td>"%(k,)
        seen_vals=set()
        for n1,m1 in pairs:
            if k not in m1:
                continue
            val=m1[k]
            if val in seen_vals: continue
            out.write("%s ("%(val,))
            first=True
            for n2,m2 in pairs:
                if m2.get(k,None)==val:
                    if not first:
                        out.write(", ")
                    first=False
                    out.write(n2)
            print >>out, ")"
            seen_vals.add(val)
        print >>out, "</td></tr>"
                

def display_markable(part,names,doc,out=sys.stdout):
    m=None
    for ms in part:
        if ms: m=ms[0]
    print >>out, '<div class="srctext">'
    print >>out, "%s<br>"%(m2context(m,doc),)
    print >>out, "%s%s"%(sentencelink(m,doc),m2s(m,doc))
    print >>out, "</div>"
    print >>out, "<table>"
    report_attributes(part,names,out)
    print >>out, "</table>"
