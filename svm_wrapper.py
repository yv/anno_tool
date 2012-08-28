import os.path
import tempfile
import numpy
import sys
from mltk import Factory
from itertools import izip
from xvalidate_common import shrink_to



default_flags=['-w','3','-c','0.01','-l','1']
def set_flags(new_flags):
    global default_flags
    default_flags=new_flags


def read_weights(fname,fc=None):
    f=file(fname)
    ws=[]
    l=f.readline().strip()
    assert l.startswith('SVM-light Version V6')
    # kernel type - allow only linear
    l=f.readline().strip()
    assert l.startswith('0 ')
    # ignore degree, -g, -s, -r
    l=f.readline().strip()
    l=f.readline().strip()
    l=f.readline().strip()
    l=f.readline().strip()
    # ignore -u
    l=f.readline().strip()
    # highest feature index
    l=f.readline().strip().split()[0]
    if fc is not None:
        # SVMlight adds two?!
        assert int(l)<=len(fc.dict)+2,(l,len(fc.dict))
        n_features=len(fc.dict)
    else:
        n_features=int(l)
    # number of training documents
    l=f.readline().strip().split()[0]
    # number of support vectors plus 1 -- this should be 2
    l=f.readline().strip().split()[0]
    assert l=='2',l
    # threshold b
    l=f.readline().strip().split()[0]
    b=float(l)
    l=f.readline().strip().split()
    assert l[0]=='1'
    x=numpy.zeros([n_features],'float64')
    for i in xrange(1,len(l)):
        if l[i]=='#':
            break
        k_s,val_s=l[i].split(':')
        x[int(k_s)-1]=float(val_s)
    return b,x

class LinearClassifier:
    def __init__(self, w, bias=0.0):
        self.w=w
        self.bias=bias
    def classify(self, vec):
        return vec.dotFull(self.w)-self.bias


class SVMPerfLearner(Factory):
    def __init__(self,basedir=None,prefix=None,**kwargs):
        Factory.__init__(self, **kwargs)
        if basedir is None:
            self.basedir=tempfile.mkdtemp(prefix='svm')
            self.want_cleanup=2
        else:
            self.basedir=basedir
            self.want_cleanup=1
        if prefix is not None:
            self.prefix=prefix
        else:
            self.prefix=''
    def train(self):
        args=([self.svmlearn]+self.flags+
              [self.fname_by_pat('datafile'),
               self.fname_by_pat('classifier')])
        retval=os.spawnv(os.P_WAIT,self.svmlearn,args)
        assert retval==0, (args,retval)
    def write_data(self):
        f=self.open_by_pat('datafile','w')
        for (lbl,d) in self.data:
            if lbl:
                lab='+1'
            else:
                lab='-1'
            f.write(lab)
            d.write_pairs(f)
            f.write('\n')
        f.close()
    def load_classifier(self):
        if hasattr(self,'data'):
            self.write_data()
            self.train()
        else:
            # read auxiliary stuff for fc?
            pass
        bias,w=read_weights(self.fname_by_pat('classifier'))
        return LinearClassifier(w,bias)

svm_dir='/home/yannickv/sources/svm_perf/'
svmlearn=svm_dir+'svm_perf_learn'
svmperf=SVMPerfLearner(flags=['-w','3','-c','0.01','-l','1'],
                       svmlearn=svmlearn,
                       datafile_pattern='train.data',
                       classifier_pattern='model.data')

def train_greedy(vectors, labels, prototype, d=1):
    labelset=set()
    labels0=[[shrink_to(lbl,d) for lbl in lab] for lab in labels]
    for labs in labels0:
        for lab in labs:
            labelset.add(lab)
    all_labels=sorted(labelset)
    if len(all_labels)==1:
        return ([(all_labels[0],None)],None)
    assert d<10
    vecs=[]
    cont={}
    for label in all_labels:
        print label,d
        sub_cl_vec=[]
        sub_cl_lab=[]
        data_train=[]
        n_pos=0
        n_neg=0
        for vec,lab0,lab in izip(vectors,labels0,labels):
            if label in lab0:
                n_pos+=1 
                data_train.append((True,vec))
                sub_cl_vec.append(vec)
                sub_cl_lab.append([lb for lb in lab if lb.startswith(label)])
            else:
                n_neg+=1
                data_train.append((False,vec))
        if n_neg==0:
            print >>sys.stderr, "No negative examples for %s. Are we done?"%(label,)
            return ([(label,None)],None)
        learner=prototype.bind(label=label,depth=d,data=data_train)
        w_classify=learner.get('classifier')
        vecs.append((label,w_classify))
        cont[label]=train_greedy(sub_cl_vec,sub_cl_lab,prototype,d+1)
    return (vecs,cont)

def classify_greedy_mlab(stuff,vec_cl, num_labels=2):
    vecs,cont=stuff
    result=[]
    for label,vec in vecs:
        score=vec.classify(vec_cl)
        result.append((score,label))
    result.sort(reverse=True)
    rels=[]
    for i,res in enumerate(result):
        if i>0 and res[0]<0:
            break
        if i>=num_labels:
            break
        rel=classify_greedy(cont[res[1]],vec_cl)
        rels.append(rel)
    return rels

def classify_greedy(stuff,vec_cl, num_labels=2):
    vecs,cont=stuff
    if len(vecs)==1:
        return vecs[0][0]
    result=[]
    for label,vec in vecs:
        score=vec.classify(vec_cl)
        result.append((score,label))
    result.sort(reverse=True)
    return classify_greedy(cont[result[0][1]],vec_cl)

