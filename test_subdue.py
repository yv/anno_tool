import sys
import os
import optparse
from collections import defaultdict
from alphabet import PythonAlphabet, CPPUniAlphabet
from dist_sim.fcomb import FCombo, FeatureList, Multipart
from xvalidate_common import *
from xvalidate_common_mlab import *
import simplejson as json
import vflib

oparse=optparse.OptionParser()
oparse.add_option('-N', dest='N', type='int',
                  help='maximum feature edges',
                  default=None)
oparse.add_option('-M', dest='M', type='int',
                  help='minimum non-feature edges',
                  default=0)
oparse.add_option('--main', dest='main_features', action='store_true',
                  help='use main feature list')
add_options_common(oparse)
add_options_mlab(oparse)

def make_string(s):
    return unicode(s).encode('UTF-8').replace('"','')

def print_data_subdue(all_data):
    offset=1
    for bin_nr, data, label in all_data:
        for x in data.trees:
            (lst,new_offset)=x.as_subdue(offset)
            print "XP"
            for line in lst:
                print '\t'.join([make_string(s) for s in line])
            print

def print_data_gboost(all_data, fprefix, counter=None):
    alph=CPPUniAlphabet(want_utf8=True)
    offset=0
    f_data=file(fprefix+'.txt','w')
    tree_id=0
    for bin_nr, data, label in all_data:
        tree_id +=1
        for i,x in enumerate(data.trees):
            (lst,new_offset)=x.as_subdue(offset)
            if counter is not None:
                counter.count_graph(lst)
            print >>f_data, "t # %s_%s"%(tree_id,i)
            for line in lst:
                if line[-1] is None:
                    lbl=alph['None']
                else:
                    lbl=alph[line[-1]]
                line2=list(line[:-1])+[lbl]
                print >>f_data,'\t'.join([str(s) for s in line2])
    f_data.close()
    f_alph=file(fprefix+'.alph','w')
    alph.tofile_utf8(f_alph)
    f_alph.close()
    return alph

def create_random_data(fprefix):
    alph=CPPUniAlphabet(want_utf8=True)
    offset=0
    f_data=file(fprefix+'.txt','w')
    for tree_id in xrange(100):
        lst=random_graph()
        print >>f_data, "t # %s"%(tree_id,)
        for line in lst:
            if line[-1] is None:
                lbl=alph['None']
            else:
                lbl=alph[line[-1]]
            line2=list(line[:-1])+[lbl]
            print >>f_data,'\t'.join([str(s) for s in line2])
    f_data.close()
    f_alph=file(fprefix+'.alph','w')
    alph.tofile_utf8(f_alph)
    f_alph.close()
    return alph

class VFGraph:
    def __init__(self, tuples):
        g=vflib.ARGEdit()
        for tup in tuples:
            if tup[0]=='v':
                g.InsertNode(tup[2])
        for tup in tuples:
            if tup[0]=='e':
                lbl=str(tup[3])
                g.InsertEdge(tup[1],tup[2],lbl)
        self.g=g
    def __contains__(self, graph):
        #print '%s in %s'%(self.g, graph.g)
        if not hasattr(graph,'matcher'):
            graph.matcher=vflib.GraphMatcher(graph.g)
        return graph.matcher.matchVF2Mono(self.g,-1)

def random_graph(num_nodes=10, num_feat=4, edge_prob=0.3):
    node_ids=[]
    tuples=[]
    edges=[]
    for i in xrange(num_nodes):
        k=len(tuples)
        node_ids.append(k)
        tuples.append(('v',k,random.choice(['A','B','C'])))
        if node_ids:
            for j in node_ids:
                if random.random()<edge_prob:
                    edges.append(('e',j,k,'e'))
                fval=0
                for fnum in xrange(random.randint(1,num_feat+1)):
                    fval+=random.randint(1,4)
                    tuples.append(('v',k+fnum+1,'feat%d'%(fval)))
                    edges.append(('e',k,k+fnum+1,'_f'))
    return tuples+edges

def read_gboost(fprefix, N=None, M=0, alph=None, suffix='_out'):
    if alph is None:
        alph=CPPUniAlphabet(want_utf8=True)
        f_alph=file(fprefix+'.alph')
        alph.fromfile_utf8(f_alph)
        f_alph.close()
    f_patterns=file('%s%s.txt'%(fprefix,suffix))
    k=0
    num_feat=0
    num_nonfeat=0
    sym_feat=alph['_f']
    tuples=[]
    for l in f_patterns:
        line=l.strip().split()
        if not line: continue
        if line[0]=='t':
            if tuples:
                k+=1
                if (N is None or num_feat<=N) and num_nonfeat >= M:
                    yield (k,tuples)
                tuples=[]
                num_feat=0
        elif line[0]=='v':
            tuples.append(('v',int(line[1]),alph.get_sym_unicode(int(line[2]))))
        elif line[0]=='e':
            edge_sym=int(line[3])
            if edge_sym == sym_feat:
                num_feat+=1
            else:
                num_nonfeat+=1
            tuples.append(('e',int(line[1]),int(line[2]),alph.get_sym(edge_sym)))
    if tuples:
        k+=1
        if (N is None or num_feat<=N) and num_nonfeat >= M:
            yield k, tuples

def tuples2json(tuples):
    node_ids=PythonAlphabet()
    node_labels={}
    node_features=defaultdict(list)
    node_edges=defaultdict(list)
    feature_nodes=set()
    # record node labels
    for tup in tuples:
        if tup[0]=='v':
            node_labels[tup[1]]=tup[2]
    # record features, compile set of feature nodes
    # record edges
    for tup in tuples:
        if tup[0]=='e':
            if tup[3]=='_f':
                node_features[tup[1]].append(node_labels[tup[2]])
                feature_nodes.add(tup[1])
            else:
                node_ids[tup[1]]
                lbl=tup[3]
                if lbl is None or lbl=='None':
                    lbl=''
                node_edges[tup[1]].append((node_ids[tup[2]],tup[3]))
    # compile json data structure
    nodes=[]
    for i,n_id in enumerate(node_ids):
        nodes.append([node_labels[n_id], node_features[n_id], node_edges[n_id]])
    return nodes

def graphs_from_gboost(fprefix, N=None, M=0, alph=None, suffix='_out'):
    graphs=[]
    graph_nums=[]
    for k,tuples in read_gboost(fprefix, N, M, alph,suffix):
        graphs.append(VFGraph(tuples))
        graph_nums.append(k)
    return graphs, graph_nums

def occurring_labels(tuples):
    lbls=set()
    for tup in tuples:
        if tup[0]=='v':
            lbls.add(tup[-1])
    return lbls

class GraphGrinder:
    def __init__(self):
        self.counts=defaultdict(int)
        self.patterns=defaultdict(list)
    def count_graph(self,tuples):
        cs=self.counts
        for lbl in occurring_labels(tuples):
            cs[lbl]+=1
    def graph_key(self,tuples):
        cs=self.counts
        best_count=1e9
        best_label=None
        for lbl in occurring_labels(tuples):
            c=cs[lbl]
            if c<best_count or (c==best_count and lbl<best_label):
                best_count=c
                best_label=lbl
        return best_label
    def add_subgraph(self,k,tuples):
        key=self.graph_key(tuples)
        self.patterns[key].append((k,VFGraph(tuples)))
    def from_gboost(self, fprefix, N, M, alph=None, suffix='_out'):
     for k,tuples in read_gboost(fprefix, N, M, alph,suffix):
         self.add_subgraph(k,tuples)
    def encode_graph(self, tuples):
        ks=[]
        keys=occurring_labels(tuples)
        g=VFGraph(tuples)
        for key in keys:
            for k,g1 in self.patterns[key]:
                if g1 in g:
                    ks.append(k)
        return sorted(ks)

def graph_to_features(graphs, graph, graph_nums):
    feats=[]
    for i,g in enumerate(graphs):
        if g in graph:
            feats.append(graph_nums[i])
    return feats

def encode_obj(obj):
    if hasattr(obj,'as_json'):
        return obj.as_json()
    raise TypeError(repr(o)+ " is not JSON serializable")

def transform_graphs(fname, gs, gn, main_features=False):
    num_lines=0
    for l in file(fname):
        obj=json.loads(l, object_hook=object_hook)
        data=obj[1]
        num_lines+=1
        sys.stderr.write("\r%d"%(num_lines,))
        graph_feats=defaultdict(str)
        for i,g0 in enumerate(data.trees):
            (g1,offset)=g0.as_subdue(0)
            g=VFGraph(g1)
            for feat in graph_to_features(gs,g,gn):
                graph_feats[feat]+=str(i+1)
        flst=[]
        for k,v in sorted(graph_feats.iteritems()):
            flst.append('graph%s_%s'%(k,v))
        if main_features:
            data.parts[0]=FeatureList(list(data.parts[0])+flst)
        else:
            data.parts.append(FeatureList(flst))
        data.trees=[]
        print json.dumps(obj, default=encode_obj)
    sys.stderr.write('\n')

def transform_graphs_2(fname, grinder, main_features=False):
    num_lines=0
    for l in file(fname):
        obj=json.loads(l, object_hook=object_hook)
        data=obj[1]
        num_lines+=1
        sys.stderr.write("\r%d"%(num_lines,))
        graph_feats=defaultdict(str)
        for i,g0 in enumerate(data.trees):
            (g1,offset)=g0.as_subdue(0)
            for feat in grinder.encode_graph(g1):
                graph_feats[feat]+=str(i+1)
        flst=[]
        for k,v in sorted(graph_feats.iteritems()):
            flst.append('graph%s_%s'%(k,v))
        if main_features:
            data.parts[0]=FeatureList(list(data.parts[0])+flst)
        else:
            data.parts.append(FeatureList(flst))
        data.trees=[]
        print json.dumps(obj, default=encode_obj)
    sys.stderr.write('\n')

gspan_exe='/home/yannickv/sources/sam2010v1.2/bin/gSpanCORK'

def test_gspan(fprefix,N=3,M=0):
    alph=CPPUniAlphabet(want_utf8=True)
    f_alph=file(fprefix+'.alph')
    alph.fromfile_utf8(f_alph)
    f_alph.close()
    gs0=[x for (xnum,x) in read_gboost(fprefix,None,0,alph,'')]
    print >>sys.stderr, "%d input graphs"%(len(gs0),)
    os.system('%s -F %d -G %d -m 5 -L 7 < %s > %s'%(gspan_exe,alph['_f'],N,
                                                    fprefix+'.txt',fprefix+'_out.txt'))
    gs1,gn1=graphs_from_gboost(fprefix,N,M,alph)
    os.system('%s -m 5 -L 7 < %s > %s'%(gspan_exe,
                                        fprefix+'.txt',fprefix+'_out.txt'))
    gs2,gn2=graphs_from_gboost(fprefix,N,M,alph)
    assert len(gs1)==len(gs2)
    print >>sys.stderr, "length check passed: %d"%(len(gs1),)
    print >>sys.stderr, "graph numbers compared: %d vs %d"%(gn1[-1], gn2[-1])
    for tuples in gs0:
        g=VFGraph(tuples)
        feats1=graph_to_features(gs1,g,gn1)
        feats2=graph_to_features(gs2,g,gn2)
        assert len(feats1)==len(feats2), (tuples, feats1, feats)

if __name__=='__main__':
    opts, args = oparse.parse_args(sys.argv[1:])
    all_data, labelset0=load_data(args[0],opts)
    if len(args)>1:
        grinder=GraphGrinder()
        alph=print_data_gboost(all_data,args[1],grinder)
        # run gspanCORK
        sys.stderr.write('%s -F %d -G %d -m 5 -L 7 < %s > %s\n'%(gspan_exe,alph['_f'],opts.N,
                                                                args[1]+'.txt',args[1]+'_out.txt'))
        os.system('%s -F %d -G %d -m 5 -L 7 < %s > %s'%(gspan_exe,alph['_f'],opts.N,
                                                        args[1]+'.txt',args[1]+'_out.txt'))
        #os.system('%s -m 5 -L 10 < %s > %s'%(gspan_exe, args[1]+'.txt',args[1]+'_out.txt'))
        # read in subgraphs and replace graphs in data by more feature columns
        grinder.from_gboost(args[1],opts.N,opts.M,alph)
        transform_graphs_2(args[0],grinder,opts.main_features)
        # OLD WAY
        #gs,gn=graphs_from_gboost(args[1],opts.N,opts.M, alph)
        #transform_graphs(args[0],gs,gn,opts.main_features)

    else:
        print_data_subdue(all_data)
            


