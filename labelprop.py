import simplejson as json
import optparse
import codecs
from alphabet import PythonAlphabet
from xvalidate_common import *
from xvalidate_common_mlab import *
from dist_sim.semkernel import JSDKernel, PolynomialKernel
from dist_sim.sparsmat import CSRMatrixD, VecD2
from dist_sim.fcomb import FCombo
import numpy

def run_labelprop(graph, ys, loss, opts):
    """
    Input: weighted graph (co-occurrence matrix),
    partial labeling in ys (-1=unlabeled, otherwise class)
    loss matrix
    Output:
    complete labeling
    """
    eta=opts.eta
    k_max=opts.k_max
    n=len(ys)
    print loss.shape
    m=loss.shape[0]
    print "Label Propagation with n=%d m=%d"%(n,m)
    old_dist=numpy.zeros([n,m],'d')
    new_dist=numpy.zeros([n,m],'d')
    lab=numpy.zeros(n,'?')
    for i,y in enumerate(ys):
        if y>=0:
            lab[i]=True
            old_dist[i,y]=1.0
            new_dist[i,y]=1.0
        else:
            old_dist[i,:]=(1.0/m)
    marginals_lab=old_dist[lab,:].sum(0)
    marginals_lab[marginals_lab==0]=1.0
    maxdiff=None
    for k in xrange(k_max):
        print >>sys.stderr, "\rIteration %d/%d eta=%.2f maxdiff=%s"%(k+1,k_max,eta,maxdiff),
        if eta==0.0:
            loss_factors=0.0+(loss==0)
        elif eta<0.0:
            maxloss=loss.max()
            loss_factors=((maxloss-loss)/maxloss)**(-eta)
        else:
            loss_factors=numpy.exp(-eta*loss)
            #eta *= eta_step
        for i,y in enumerate(ys):
            if y==-1:
                ndist=new_dist[i]
                ndist[:]=0.0
                edges=graph[i]
                if edges:
                    for (j,val) in edges:
                        ndist+=val*numpy.dot(old_dist[j],loss_factors)
                    tot=ndist.sum()
                    if tot>0.0:
                        ndist/=tot
                    else:
                        print >>sys.stderr, "node %d has no neighbours with indegree %d?"%(i,len(graph[i]))
                        print >>sys.stderr, ndist
                        print >>sys.stderr, graph[i]
                        for (j,val) in edges:
                            print >>sys.stderr, old_dist[j]
                        sys.exit(1)
        # re-normalize by label counts
        if opts.renorm!=0.0:
            marginals_ratio=(new_dist.sum(0)/marginals_lab)**opts.renorm
            #print marginals_lab
            #print new_dist.sum(0)
            #print marginals_ratio
            for i,y in enumerate(ys):
                if y==-1:
                    new_dist[i]/=marginals_ratio
            # normalize (2)
            for i,y in enumerate(ys):
                if y==-1:
                    ndist /= ndist.sum()
        maxdiff=numpy.abs(new_dist-old_dist).max()
        if maxdiff<1e-5:
            break
        if numpy.isnan(numpy.sum(new_dist)):
            for i,y in enumerate(ys):
                ndist=new_dist[i]
                if numpy.isnan(numpy.sum(ndist)):
                    print >>sys.stderr, "node %d has a NaN?"%(i,)
                    print >>sys.stderr, ndist
                    print >>sys.stderr, marginals_lab
            sys.exit(1)
        (new_dist,old_dist)=(old_dist,new_dist)
    ys_new=[]
    print >>sys.stderr, "done. (maxdiff=%s)"%(maxdiff,)
    for i,y in enumerate(ys):
        if y==-1:
            ys_new.append(old_dist[i].argmax())
        else:
            ys_new.append(y)
    return ys_new


def norm_set(x):
    return tuple(sorted(x))

def load_data(fname_labeled, fname_unlabeled, normalize_func=norm_set):
    alph=PythonAlphabet()
    labeled={}
    xs=[]
    ys_gold=[]
    all_ys=[[] for i in xrange(n_bins)]
    line_no=0
    for l in file(fname_labeled):
        try:
            bin_unused, data, label, span = json.loads(l, object_hook=object_hook)
        except ValueError:
            print >>sys.stderr, l
            raise
        span=tuple(span)
        xs.append(data)
        bin_nr=line_no%n_bins
        y=alph[normalize_func(label)]
        ys_gold.append(y)
        for i in xrange(n_bins):
            if i==bin_nr:
                all_ys[i].append(-1)
            else:
                all_ys[i].append(y)
        assert span not in labeled
        labeled[span]=len(xs)-1
        line_no+=1
    for l in file(fname_unlabeled):
        try:
            bin_unused, data, label, span = json.loads(l, object_hook=object_hook)
        except ValueError:
            print >>sys.stderr, l
            raise
        span=tuple(span)
        if span not in labeled:
            xs.append(data)
            for i in xrange(n_bins):
                all_ys[i].append(-1)
            labeled[span]=len(xs)-1
    return xs, ys_gold, all_ys, alph, labeled

level_weights=[1.0,1.0,1.0]
def multilevel_dice(lab,lab2):
    """loss function that is based on dice scores at multiple levels"""
    total=0.0
    Z=0.0
    for d in xrange(1,4):
        short=set([shrink_to(x,d) for x in lab])
        short2=set([shrink_to(x,d) for x in lab2])
        total+=level_weights[d-1]*2.0*len(short.intersection
                                          (short2))/(len(short)+len(short2))
        Z+=level_weights[d-1]
    return 1.0-total/Z

def run_xval(graph, loss, all_ys, opts):
    all_output=[]
    output_ys=[]
    for k in xrange(len(all_ys)):
        output=run_labelprop(graph, all_ys[k], loss, opts)
        all_output.append(output)
    for i in xrange(len(all_ys[0])):
        output_ys.append(all_output[i%n_bins][i])
    return output_ys

def make_graph(xs, opts, alph):
    n=len(xs)
    n_neighbours=opts.neighbours
    mat=CSRMatrixD()
    mat.fromVectors(xs)
    ker=PolynomialKernel(mat)
    graph0=VecD2()
    for file_spec in opts.graph_file:
        if ':' in file_spec:
            fname,w_str=file_spec.split(':')
            w=float(w_str)
        else:
            fname=file_spec
            w=1.0
        n_links=0
        for l in codecs.open(fname,'r','ISO-8859-15'):
            line=l.strip().split()
            try:
                i=alph[line[0]]
                j=alph[line[1]]
                n_links+=1
                if len(line)>2:
                    val=float(line[2])*w
                else:
                    val=w
                graph0.add_count(i,j,val)
                graph0.add_count(j,i,val)
            except KeyError:
                pass
        print >>sys.stderr, "%s: %d links added"%(fname, n_links)
    print >>sys.stderr, "Create graph"
    for i in xrange(n):
        cands=[]
        for j in xrange(n):
            if i!=j:
                val=ker.kernel(i,j)
                cands.append((val,j))
        cands.sort(reverse=True)
        if cands[0][0]==0.0:
            print >>sys.stderr, "No neighbours: %d"%(i,)
        else:
            cands=cands[:n_neighbours]
            for val,j in cands:
                graph0.add_count(i,j,val)
                graph0.add_count(j,i,val)
        print >>sys.stderr, "\r\t%d/%d"%(i,len(xs)),
    graph=graph0.to_csr()
    print >>sys.stderr
    return graph

oparse=optparse.OptionParser()
add_options_common(oparse)
add_options_mlab(oparse)
oparse.add_option('--eta', action='store', type='float',
                      dest='eta', default=0.0)
oparse.add_option('--num_iter', action='store', type='int',
                      dest='k_max', default=60)
oparse.add_option('--neighbours', action='store', type='int',
                      dest='neighbours', default=10)
oparse.add_option('--renorm', action='store', type='float',
                      dest='renorm', default=0.5)
oparse.add_option('--graph', action='append', dest='graph_file')
oparse.set_defaults(reassign_folds=True,max_depth=3,graph_file=[])
opts,args=oparse.parse_args(sys.argv[1:])

fc=FCombo(opts.degree)
fc.codec=codecs.lookup('ISO-8859-15')

xs0, ys_gold, all_ys, alph, labeled=load_data(args[0],args[1])
n_labeled=len(ys_gold)
xs=[fc(x) for x in xs0]
graph=make_graph(xs,opts,labeled)
n=len(alph.words)
loss=numpy.zeros([n,n])
for i in xrange(n):
    for j in xrange(n):
        loss[i,j]=multilevel_dice(alph.words[i],alph.words[j])

output_ys=run_xval(graph, loss, all_ys, opts)
all_data=zip([0]*len(ys_gold),
              xs0,
              [alph.words[y] for y in ys_gold])
sys_labels=[alph.words[y] for y in output_ys[:len(ys_gold)]]

stats=make_stats_multi(all_data, sys_labels, opts)

print_stats(stats)
