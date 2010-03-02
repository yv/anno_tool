import sys
from collections import defaultdict
from mmax_tools import *

if 'null' in sys.argv[2:4]:
    rel_mapping={
        'other_rel':{'unmarked':'no_other'}
        }
else:
    rel_mapping={}

want_html=False

ignore_attributes=set(['comment','span','other_rel','id','mmax_level'])

class Distribution(defaultdict):
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
    new_dist=Distribution()
    for k in dist.iterkeys():
        new_dist[k[pos]]+=dist[k]
    return new_dist

def m2context(markable,doc):
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

def extract_attributes(attrs1,attrs2,key):
    val1=attrs1.get(key,'unmarked')
    val2=attrs2.get(key,'unmarked')
    if key in rel_mapping:
        rmap=rel_mapping[key]
        val1=rmap.get(val1,val1)
        val2=rmap.get(val2,val2)
    return val1,val2

def report_attributes(key,val1,val2):
    if want_html:
        print '<div class="difference">'
    print (u"%s: %s - %s"%(key,val1,val2)).encode('ISO-8859-1')
    if want_html:
        print '</div>'

def diff_markables(ms1,ms2,doc):
    ms1.sort(key=lambda x:x[3:5])
    ms2.sort(key=lambda x:x[3:5])
    idx1=0
    idx2=0
    strict=0
    lenient=0
    att_dist=defaultdict(Distribution)
    while idx1<len(ms1) and idx2<len(ms2):
        m1=ms1[idx1]
        m2=ms2[idx2]
        if m1[3:5]<m2[3:5]:
            print "only ann1: %s"%(m2s(ms1,doc),)
            idx1+=1
            continue
        elif m1[3:5]>m2[3:5]:
            print "only ann2: %s"%(m2s(ms2,doc),)
            idx2+=1
            continue
        attrs1=m1[2]
        attrs2=m2[2]
        have_m=False
        all_keys=set(attrs1.keys())
        all_keys.update(attrs2.keys())
        for key in sorted(all_keys):
            if key in ignore_attributes:
                continue
            val1,val2=extract_attributes(attrs1,attrs2,key)
            att_dist[key][(val1,val2)]+=1
            if val1!=val2:
                if not have_m:
                    have_m=True
                    if want_html:
                        print '<div class="srctext">'
                        print m2context(m1,doc),"<br>"
                    print "[%d]%s: "%(idx1,m2s(m1,doc),)
                    if want_html:
                        print '</div>'
        if have_m:
            for key in sorted(all_keys.intersection(ignore_attributes)):
                val1,val2=extract_attributes(attrs1,attrs2,key)
                if val1!=val2:
                    report_attributes(key,val1,val2)
        lenient+=1
        if not have_m:
            strict+=1
        idx1+=1
        idx2+=1
    all1=len(ms1)
    all2=len(ms2)
    return att_dist

def display_result(docid,result):
    print docid
    for r,dist_raw in result.iteritems():
        dist=dist_raw/abs(dist_raw)
        marg1=marginal(dist,0)
        marg2=marginal(dist,1)
        perc_agree=sum([w for ((a,b),w) in dist.iteritems()
                        if a==b])
        expected_agree=0
        for k in marg1.iterkeys():
            expected_agree+=marg1[k]*marg2[k]
        if expected_agree<1.0:
            kappa=(perc_agree-expected_agree)/(1-expected_agree)
            print "*** %s"%(r,)
            print "Percent  agreement: %.3f"%(perc_agree,)
            print "Expected agreement: %.3f"%(expected_agree,)
            print "Cohen's kappa: %.3f"%(kappa,)

def summarize_results(results):
    a=defaultdict(Distribution)
    for r in results:
        for k,v in r.iteritems():
            a[k]+=v
    return a

annodir='/gluster/common/annotation/'
empty_dir='/home/yannickv/proj/konnektor/mmax/'
annodirs={'anna':annodir+'annotation-Anna',
          'sabrina':annodir+'annotation-Sabrina',
          'holger':annodir+'annotation-Holger',
          'steffi':annodir+'annotation-steffi',
          'null':empty_dir}

anno_sets={'waehrend1':['0_waehrend','2_waehrend','3_waehrend','4_waehrend'],
           'nachdem1':['1_nachdem','5_nachdem','8_nachdem','11_nachdem'],
           'waehrend2':['6_waehrend','7_waehrend','9_waehrend','10_waehrend'],
           'nachdem2':['14_nachdem','16_nachdem','18_nachdem','23_nachdem']}

if __name__=='__main__':
    dir1=annodirs[sys.argv[1]]
    dir2=annodirs[sys.argv[2]]
    results=[]
    if want_html:
        print """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN"
        "http://www.w3.org/TR/html4/strict.dtd">
        <html><head><title>Annotation diff</title>
        <style type="text/css">
        .srctext { font-size: 12pt; line-height: 150%;
           font-family:Helvetica,Arial,sans-serif;
           font-style: italic;
           border-top: solid thin black;
           margin-top: 20pt;
           margin-bottom: 12pt;  }
        .difference { font-size: 11pt; }
        .file_id { font-weight: bold; font-size: 14pt;
        margin-top: 20pt; }
        </style>
        </head>
        <body>"""
    for docid in anno_sets[sys.argv[3]]:
        if want_html:
            print '<div class="file_id">%s</div>'%(docid)
        doc1=MMAXDiscourse(dir1,docid)
        doc2=MMAXDiscourse(dir2,docid)
        assert(doc1.tokens == doc2.tokens)
        ms1=doc1.read_markables('konn')
        ms2=doc2.read_markables('konn')
        partial=diff_markables(ms1,ms2,doc1)
        results.append(partial)
        display_result(docid,partial)
    summary=summarize_results(results)
    display_result('TOTAL',summary)
    if want_html:
        print """</body></html>"""
