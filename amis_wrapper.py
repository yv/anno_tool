import os.path
import tempfile
import numpy

format_template="""DATA_FORMAT	%(data_format)s
MODEL_FILE	%(basedir)s/all.in
EVENT_FILE	%(basedir)s/all.event
OUTPUT_FILE	%(basedir)s/all.model
LOG_FILE	%(basedir)s/all.log
NUM_ITERATIONS	%(num_iterations)s
REPORT_INTERVAL	1
MAP_SIGMA	10
BC_LOWER	20
BC_UPPER	20
FEATURE_TYPE	real
FEATURE_WEIGHT_TYPE	lambda
PARAMETER_TYPE	lambda
ESTIMATION_ALGORITHM	%(estimation_algorithm)s
FILTER_INACTIVE_FEATURES	true
"""

treelexer_path='/home/yannickv/proj/pytree-package/amis_tools/treelexer'
amis_path='/usr/local/bin/amis'

def read_weights(fc,fname):
    f=file(fname)
    ws=[]
    for l in f:
        line=l.strip().split()
        fno=fc.unescaped(line[0])
        ws.append((fno,float(line[1])))
    fc.dict.growing=False
    x=numpy.zeros([len(fc.dict)],'float64')
    for i,v in ws:
        x[i]=v
    return x

class AMISLearner:
    def __init__(self,basedir=None):
        if basedir is None:
            self.basedir=tempfile.mkdtemp(prefix='amis')
            self.want_cleanup=True
        else:
            self.basedir=basedir
            self.want_cleanup=False
        self.num_iterations=70
        self.conf_written=False
        self.data_format='AmisTree'
        self.estimation_algorithm='BFGSMAP'
        self.count_threshold=2
    def write_conf(self):
        fname=os.path.join(self.basedir,'amis.conf')
        f=file(fname,'w')
        try:
            f.write(format_template%{'basedir':self.basedir,
                                     'num_iterations':self.num_iterations,
                                     'estimation_algorithm':self.estimation_algorithm,
                                     'data_format':self.data_format})
            self.conf_written=True
        finally:
            f.close()
    def open_events(self):
        fname=os.path.join(self.basedir,'all.event0')
        self.infile_written=False
        f=file(fname,'w')
        return f
    def create_in_file(self):
        args=[treelexer_path,
              '-t',str(self.count_threshold),
              '-l',os.path.join(self.basedir,'all.in'),
              '-o',os.path.join(self.basedir,'all.event')]
        if os.access(os.path.join(self.basedir,'all.model'),os.R_OK):
            args += ['-i',os.path.join(self.basedir,'all.model')]
        args+=[os.path.join(self.basedir,'all.event0')]
        retval=os.spawnv(os.P_WAIT,treelexer_path,args)
        assert retval==0, (args,retval)
        self.infile_written=True
    def run_learner(self):
        if not self.conf_written:
            self.write_conf()
        if not self.infile_written:
            self.create_in_file()
        retval=os.spawnv(os.P_WAIT,amis_path,[amis_path,os.path.join(self.basedir,'amis.conf')])
        assert retval==0, (args,retval)
    def read_weights(self,alph):
        return read_weights(alph, os.path.join(self.basedir,'all.model'))

