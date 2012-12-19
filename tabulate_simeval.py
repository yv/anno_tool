import sys
from lxml import etree
from xvalidate_common_mlab import gather_stats
from glob import glob

OUT_DIR="conn_experiments"

wanted_columns=[('by_freq/all_items','all'),
                ('by_freq/most_frequent','top 30'),
                ('by_freq/10-20','10-20'),
                ('by_freq/5-10','5-10'),
                ('by_freq/2-3','2-3'),
                ('by_freq/1-2','1-2')]

def load_and_print_stats(fname,f_out):
    stats=etree.parse(file(fname))
    result={}
    gather_stats(stats.getroot(),'',result)
    print result
    f_out.write(fname)
    for k,d in wanted_columns:
        f_out.write('\t')
        if k in result:
            f_out.write('%f'%(result[k],))
        else:
            f_out.write('--')
    f_out.write('\n')

f_out=file('all_simeval.txt','w')
f_out.write('(filename)')
for k,d in wanted_columns:
    f_out.write('\t')
    f_out.write(d)
f_out.write('\n')
for fname in sorted(glob('sim_eval_experiments/*.xml')):
    load_and_print_stats(fname,f_out)
f_out.close()
