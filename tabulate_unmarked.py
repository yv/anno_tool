import sys
from lxml import etree
from xvalidate_common_mlab import gather_stats
from glob import glob

OUT_DIR="conn_g_experiments"

# wanted_columns=[('depth=1/dice','dice'),
#                 ('depth=1/micro-F','mF'),
#                 ('depth=3/dice','dice3'),
#                 ('depth=3/micro-F','mF3'),
#                 ('depth=1/Contingency-P','ContP'),
#                 ('depth=1/Contingency-R','ContR'),
#                 ('depth=1/Contingency','ContF'),
#                 ('depth=1/Expansion-P','ExpnP'),
#                 ('depth=1/Expansion-R','ExpnR'),
#                 ('depth=1/Expansion','ExpnF'),
#                 ('depth=1/Temporal-P','TempP'),
#                 ('depth=1/Temporal-R','TempR'),
#                 ('depth=1/Temporal','TempF'),
#                 ('depth=1/Comparison-P','CompP'),
#                 ('depth=1/Comparison-R','CompR'),
#                 ('depth=1/Comparison','CompF'),
#                 ('depth=1/Reporting-P','ReptP'),
#                 ('depth=1/Reporting-R','ReptR'),
#                 ('depth=1/Reporting','ReptF')]

wanted_columns=[('depth=1/dice','dice'),
                ('depth=1/micro-F','mF'),
                ('depth=3/dice','dice3'),
                ('depth=3/micro-F','mF3'),
                ('depth=1/Contingency','ContF'),
                ('depth=1/Expansion','ExpnF'),
                ('depth=1/Temporal','TempF'),
                ('depth=1/Comparison','CompF'),
                ('depth=1/Reporting','ReptF')]

def load_and_print_stats(fname,f_out,ident=None):
    if ident is None:
        ident=fname
    stats=etree.parse(file(fname))
    result={}
    gather_stats(stats.getroot(),'',result)
    print result
    f_out.write(ident)
    for k,d in wanted_columns:
        f_out.write('\t')
        if k in result:
            f_out.write('%f'%(result[k],))
        else:
            f_out.write('--')
    f_out.write('\n')

OUT_DIR="unmarked_experiments"
def generate_filenames(prefix,suffix):
    for fname in sorted(glob('%s/*%s'%(prefix,suffix))):
        shortened_fname=fname
        if shortened_fname.startswith(prefix+'/'):
            shortened_fname=shortened_fname[len(prefix)+1:]
        if shortened_fname.endswith(suffix):
            shortened_fname=shortened_fname[:-len(suffix)]
        yield (shortened_fname,fname)

f_out=file('um_results.txt','w')
f_out.write('(filename)')
for k,d in wanted_columns:
    f_out.write('\t')
    f_out.write(d)
f_out.write('\n')
for shortened_fname,fname in generate_filenames('unmarked_experiments','_um_stats_svm.xml'):
    load_and_print_stats(fname,f_out,shortened_fname)
f_out.close()
