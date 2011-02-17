import os.path
import tempfile
import numpy
from itertools import izip
from xvalidate_common import shrink_to

svm_dir='/home/yannickv/sources/svm_perf/'
svmlearn=svm_dir+'svm_perf_learn'

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

class SVMLearner:
    def __init__(self,basedir=None,prefix=None):
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
        self.flags=['-w','3','-c','0.01','-l','1']
    def open_events(self):
        fname=os.path.join(self.basedir,self.prefix+'train.data')
        f=file(fname,'w')
        return f
    def train(self):
        retval=os.spawnv(os.P_WAIT,svmlearn,[svmlearn]+self.flags+
                         [os.path.join(self.basedir,self.prefix+'train.data'),
                          os.path.join(self.basedir,self.prefix+'train.model')])
        assert retval==0, (args,retval)
    def read_weights(self,fc=None):
        return read_weights(os.path.join(self.basedir,self.prefix+'train.model'),fc)

def classify_greedy_mlab(stuff,vec_cl):
    vecs,cont=stuff
    result=[]
    for label,bias,vec in vecs:
        score=vec_cl.dotFull(vec)-bias
        result.append((score,label))
    result.sort(reverse=True)
    if len(result)>=2 and result[1][0]>0:
        rel1=classify_greedy(cont[result[0][1]],vec_cl)
        rel2=classify_greedy(cont[result[1][1]],vec_cl)
        return [rel1,rel2]
    else:
        rel1=classify_greedy(cont[result[0][1]],vec_cl)
        return [rel1]

def classify_greedy(stuff,vec_cl):
    vecs,cont=stuff
    if len(vecs)==1:
        return vecs[0][0]
    result=[]
    for label,bias,vec in vecs:
        score=vec_cl.dotFull(vec)-bias
        result.append((score,label))
    result.sort(reverse=True)
    return classify_greedy(cont[result[0][1]],vec_cl)

def train_greedy(vectors, labels, basedir=None, fc=None, d=1):
    labelset=set()
    labels0=[[shrink_to(lbl,d) for lbl in lab] for lab in labels]
    for labs in labels0:
        for lab in labs:
            labelset.add(lab)
    all_labels=sorted(labelset)
    if len(all_labels)==1:
        return ([(all_labels[0],None,None)],None)
    vecs=[]
    cont={}
    for label in all_labels:
        print label,d
        learner=SVMLearner(basedir=basedir,prefix='%s_d%s_'%(label,d))
        f=learner.open_events()
        sub_cl_vec=[]
        sub_cl_lab=[]
        for vec,lab0,lab in izip(vectors,labels0,labels):
            if label in lab0:
                f.write('+1')
                sub_cl_vec.append(vec)
                sub_cl_lab.append([lb for lb in lab if lb.startswith(label)])
            else:
                f.write('-1')
            vec.write_pairs(f)
            f.write('\n')
        f.close()
        learner.train()
        bias,w_classify=learner.read_weights(fc)
        vecs.append((label,bias,w_classify))
        cont[label]=train_greedy(sub_cl_vec,sub_cl_lab,basedir,fc,d+1)
    return (vecs,cont)

def convert_onevsall(vectors,labels,basedir=None,prefix=''):
    labelset=set()
    for labs in labels:
        for lab in labs:
            labelset.add(lab)
    all_labels=sorted(labelset)
    all_learners=[SVMLearner(basedir=basedir, prefix=prefix+label+'_') for label in all_labels]
    for label,learner in izip(all_labels,all_learners):
        f=learner.open_events()
        for vec,lab in izip(vectors,labels):
            if label in lab:
                f.write('+1')
            else:
                f.write('-1')
            vec.write_pairs(f)
            f.write('\n')
        f.close()
    return all_learners
