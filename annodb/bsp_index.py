import json
import numpy
import cPickle
import os.path
import glob

class BSPLeaf(object):
    """represents an indexed part of a parsed corpus"""
    def __init__(self,prefix,sent_range=None):
        self.prefix=prefix
        self.sno_part=None
        self.offset_part=None
        if sent_range is not None:
            self.sent_range=sent_range
            self.sno_part=None
            self.offset_part=None
        else:
            self.load_parts()
            self.sent_range=(self.sno_part[0],self.sno_part[-1])
    def __getinitargs__(self):
        return (self.prefix,self.sent_range)
    def load_parts(self):
        fname_sno=self.prefix+'.sno.bin'
        fname_offset=self.prefix+'.offset.bin'
        self.sno_part=numpy.memmap(fname_sno,'uint32','r')
        self.offset_part=numpy.memmap(fname_offset,'uint32','r')
    def unload_parts(self):
        self.sno_part=None
        self.offset_part=None
    def get_parses(self,sno,dict_result):
        if sno<self.sent_range[0]:
            return
        elif sno>self.sent_range[1]:
            return
        if self.sno_part is None:
            self.load_parts()
        idx=self.sno_part.searchsorted(sno)
        if self.sno_part[idx]==sno:
            offset=self.offset_part[idx]
            f=file(self.prefix+'.json')
            f.seek(offset)
            parses=json.loads(f.readline())
            f.close()
            for k in parses:
                if k=='_id': continue
                dict_result[k]=parses[k]

def get_parses_all(sno,leaves,dict_result):
    for leaf in leaves:
        leaf.get_parses(sno,dict_result)

class BSPInner(object):
    def __init__(self,split,overlap,left=None,right=None):
        self.split=split
        self.overlap=overlap
        self.left=left
        self.right=right
    def get_parses(self,sno,dict_result):
        get_parses_all(sno,self.overlap,dict_result)
        if sno<self.split:
            if self.left is not None:
                self.left.get_parses(sno,dict_result)
        else:
            if self.right is not None:
                self.right.get_parses(sno,dict_result)


def make_bsp_tree(leaves,overlap0=None):
    left_border=min([n.sent_range[0] for n in leaves])
    right_border=max([n.sent_range[1] for n in leaves])
    midpoint=(left_border+right_border)//2
    left_leaves=[]
    right_leaves=[]
    overlap_leaves=[]
    for leaf in leaves:
        if leaf.sent_range[1]<midpoint:
            left_leaves.append(leaf)
        elif leaf.sent_range[0]>=midpoint:
            right_leaves.append(leaf)
        else:
            overlap_leaves.append(leaf)
    if overlap0 is not None:
        for leaf in overlap0:
            if leaf.sent_range[1]<midpoint:
                left_leaves.append(leaf)
            elif leaf.sent_range[0]>=midpoint:
                right_leaves.append(leaf)
            else:
                overlap_leaves.append(leaf)
    if right_leaves and left_leaves:
        overlap1=overlap_leaves
        overlap2=[]
    else:
        overlap1=None
        overlap2=overlap_leaves
    if right_leaves:
        n_right=make_bsp_tree(right_leaves,overlap1)
    else:
        n_right=None
    if left_leaves:
        n_left=make_bsp_tree(left_leaves,overlap1)
    else:
        n_left=None
    return BSPInner(midpoint,overlap2,n_left,n_right)

def txt2bin(fname):
    assert fname.endswith('-idx.txt') or fname.endswith('.idx.txt')
    basename=fname[:-8]
    all=[]
    
    for l in file(fname):
        if l.startswith('id fuzz:'): continue
        line=l.strip().split()
        all.append((int(line[1]),int(line[0])))
    all.sort()
    all_a=numpy.array(all,'uint32')
    all_a[:,0].tofile(basename+'.sno.bin')
    all_a[:,1].tofile(basename+'.offset.bin')

def load_directory(dirname,force_recreate=False):
    parse_idx_fname=os.path.join(dirname,'parse_idx.pik')
    if os.path.exists(parse_idx_fname) and not force_recreate:
        parse_idx=cPickle.load(file(parse_idx_fname))
    else:
        all_parses=glob.glob(os.path.join(dirname,'*.json'))
        leaves=[]
        for fname in all_parses:
            base_fname=fname[:-5]
            idx_fname=base_fname+'.idx.txt'
            sno_fname=base_fname+'.sno.bin'
            if not os.path.exists(sno_fname):
                txt2bin(idx_fname)
            leaves.append(BSPLeaf(base_fname))
        parse_idx=make_bsp_tree(leaves)
        cPickle.dump(parse_idx, file(os.path.join(dirname,'parse_idx.pik'),'w'), protocol=-1)
    return parse_idx
            
        
