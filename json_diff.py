import sys
import json
import optparse
from lxml.etree import XML, tostring
from itertools import izip
from cStringIO import StringIO
from annodb import database
from xvalidate_common import load_data_spans, make_spans, add_options_common
from dist_sim.fcomb import FCombo, make_multilabel, dump_example
from json2dot import get_graph_svg

oparse=optparse.OptionParser()
add_options_common(oparse)
oparse.add_option('--corpus',dest='corpus_name')
oparse.add_option('--attributes',dest='want_attributes',
                  action='store_true')

html_header='''
<html>
<head>
<title>json_diff</title>
<style type="text/css">
.only1 { color:#cc0033; }
.only2 { color:#009900; }
.example {
	   border-top: solid thin black;
	   margin-top: 20pt;
	   margin-bottom: 12pt;  }
}
</style>
</head>
<body>
'''

html_footer='''
</body>
'''

def print_diffs(lst,out):
    result=[]
    for op,f,v in lst:
        if op==' ':
            pass
        else:
            if op=='-':
                cls='only1'
            else:
                cls='only2'
            result.append('<span class="%s">%s</span>'%(cls,f))
    print >>out, '<div class="flist">'
    print >>out,(' '.join(result)).encode('ISO-8859-15')
    print >>out,'</div>'

def compare_data(all_data1,all_data2,opts,f):
    f.write(html_header)
    if opts.corpus_name is not None:
        db=database.get_corpus(opts.corpus_name)
    else:
        db=None
    for (bin1,data1,label1,span),(bin2,data2,label2,span2) in izip(all_data1,all_data2):
        assert label1==label2
        diffs_m=data1.diff_with(data2)
        if diffs_m is not None:
            print >>f,'<div class="example">'
            if db is not None:
                out=StringIO()
                sent_no=db.sentences.cpos2struc(span[0])+1
                print >>out,'<a href="http://localhost:5000/pycwb/sentence/%d?force_corpus=%s">s%d</a>'%(
                    sent_no,opts.corpus_name,sent_no)
                spans=make_spans(span)
                db.display_spans(spans,out)
                print >>f, out.getvalue()
            if 'parts' in diffs_m:
                for diffs_part in diffs_m['parts']:
                    print_diffs(diffs_part,f)
            for g1,g2 in diffs_m.get('trees',[]):
                print >>f,'<div>'
                g=g1.as_json()
                val=get_graph_svg(g['nodes'],'gr0')
                svg_xml=tostring(XML(val),xml_declaration=False)
                print >>f,svg_xml
                g=g2.as_json()
                val=get_graph_svg(g['nodes'],'gr0')
                svg_xml=tostring(XML(val),xml_declaration=False)
                print >>f,svg_xml
                print >>f,'</div>'
            print >>f,'</div>'
    f.write(html_footer)

if __name__=='__main__':
    opts,args=oparse.parse_args(sys.argv[1:])
    all_data_1,labelset_1=load_data_spans(args[0],opts)
    all_data_2,labelset_2=load_data_spans(args[1],opts)
    compare_data(all_data_1,all_data_2,opts,sys.stdout)
