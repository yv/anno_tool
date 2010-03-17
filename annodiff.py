import sys
from mmax_tools import *
from anno_tools import *
from anno_config import *
from getopt import getopt


want_html=False

opts,args=getopt(sys.argv[1:],'',['html'])

for k,v in opts:
    if k=='--html':
        want_html=True
    else:
        print "Unknown option: %s"%(k,)

if 'null' in args[1:3]:
    rel_mapping={
        'other_rel':{'unmarked':'no_other'},
        'causal':{'enable':'result'}
        }
    want_agree=False
else:
    rel_mapping={
         'other_rel':{'unmarked':'no_other'},
         'causal':{'enable':'causal'},
         'contrastive':{'kontradiktorisch':'kontraer','parallel':'kontraer'}
         }
    want_agree=True


completely_ignore_attributes=set(['span','id','mmax_level','word'])
ignore_attributes=set(['comment']).union(completely_ignore_attributes)

def report_attributes(key,val1,val2):
    if want_html:
        print '<div class="difference">'
    if val2=='unmarked' and args[1]=='null':
        print (u"%s: %s"%(key,val1)).encode('ISO-8859-1')
    else:
        print (u"%s: %s - %s"%(key,val1,val2)).encode('ISO-8859-1')
    if want_html:
        print '</div>'

def gen_all(attrs):
    result=[]
    for key in ['temporal','contrastive','causal']:
        val=attrs.get(key,'unmarked')
        try:
            rmap=rel_mapping[key]
        except KeyError:
            pass
        else:
            val=rmap.get(val,val)
        result.append(val)
    return '-'.join(result)

def diff_markables(join_result,doc):
    strict=0
    lenient=0
    att_dist=defaultdict(Distribution)
    pos=0
    for ms1,ms2 in join_result:
        pos+=len(ms1)
        if not ms1:
            m2=ms2[0]
            print "only ann1: %s"%(m2s(ms1,doc),)
            continue
        elif not ms2:
            m1=msq[0]
            print "only ann2: %s"%(m2s(ms2,doc),)
            continue
        attrs1=ms1[0][2]
        attrs2=ms2[0][2]
        have_m=False
        all_keys=set(attrs1.keys())
        all_keys.update(attrs2.keys())
        for key in sorted(all_keys):
            if key in ignore_attributes:
                continue
            val1,val2=extract_attributes(attrs1,attrs2,key,rel_mapping)
            att_dist[key][(val1,val2)]+=1
            if val1!=val2:
                if not have_m:
                    have_m=True
                    if want_html:
                        print '<div class="srctext">'
                        print "<b>[%d]</b> %s<br>"%(pos,m2context(ms1[0],doc))
                    else:
                        print "[%d]"%(pos,),
                    print "%s: "%(m2s(ms1[0],doc),)
                    if want_html:
                        print '</div>'
                report_attributes(key,val1,val2)
        allatt1=gen_all(attrs1)
        allatt2=gen_all(attrs2)
        att_dist['all_att'][(allatt1,allatt2)]+=1
        if have_m:
            for key in sorted(all_keys.intersection(ignore_attributes)):
                if key in completely_ignore_attributes:
                    continue
                val1,val2=extract_attributes(attrs1,attrs2,key)
                if val1!=val2:
                    report_attributes(key,val1,val2)
        lenient+=1
        if not have_m:
            strict+=1
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
        print "Marginals:"
        marg1_raw=marginal(dist_raw,0)
        marg2_raw=marginal(dist_raw,1)
        all_keys=set(marg1.iterkeys()).union(marg2.iterkeys())
        for k,v in sorted(marg1.iteritems(),key=lambda x:-x[1]):
            if v>0:
                f_val=2*dist[(k,k)]/(marg1[k]+marg2[k])
            else:
                f_val=0
            if len(k)<16:
                print "%16s: %4d (%5.1f%%) %4d (%5.1f%%) F=%4.3f"%(k,
                                                                   marg1_raw[k],
                                                                   marg1[k]*100,
                                                                   marg2_raw[k],
                                                                   marg2[k]*100,
                                                                   f_val)
            else:
                print "%40s: %4d (%5.1f%%) %4d (%5.1f%%) F=%4.3f"%(k,
                                                                   marg1_raw[k],
                                                                   marg1[k]*100,
                                                                   marg2_raw[k],
                                                                   marg2[k]*100,
                                                                   f_val)

def summarize_results(results):
    a=defaultdict(Distribution)
    for r in results:
        for k,v in r.iteritems():
            a[k]+=v
    return a


if __name__=='__main__':
    dir1=annodirs[args[0]]
    dir2=annodirs[args[1]]
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
    for docid in anno_sets[args[2]]:
        if want_html:
            print '<div class="file_id">%s</div>'%(docid)
        doc1=MMAXDiscourse(dir1,docid)
        doc2=MMAXDiscourse(dir2,docid)
        assert(doc1.tokens == doc2.tokens)
        mss=markable_join([doc1,doc2])
        partial=diff_markables(mss,doc1)
        results.append(partial)
        #if want_agree:
        #    display_result(docid,partial)
    summary=summarize_results(results)
    if want_agree:
        display_result('TOTAL',summary)
    if want_html:
        print """</body></html>"""
