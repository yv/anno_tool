import sys
import re

__all__=['load_schema','Taxon','taxon_map']

def load_schema(f):
    stack=[]
    toplevel=[]
    for l in f:
        if l[0]=='%':
            continue
        line=l.strip().split()
        if not line:
            continue
        word=line[0].lstrip('+')
        indent=len(line[0])-len(word)
        entry=[word,dict([(x,True) for x in line[1:]]),[]]
        if indent==0:
            toplevel.append(entry)
            stack=[entry]
        else:
            while len(stack)>indent:
                stack.pop()
            stack[-1][2].append(entry)
            stack.append(entry)
    return toplevel

class Taxon(object):
    def __init__(self,name):
        self.name=name
        self.subsumed=set([name])
    def add_subsumed(self,others):
        self.subsumed.update(others)
    def __contains__(self,other):
        if hasattr(other,'name'):
            return other.name in self.subsumed
        else:
            return other in self.subsumed
    def __repr__(self):
        return 'Taxon(%s)'%(self.name,)

def add_taxons(entry,taxons,taxons_by_name):
    t=Taxon(entry[0])
    for entry1 in entry[2]:
        subtaxons=[]
        t1=add_taxons(entry1,subtaxons,taxons_by_name)
        taxons.extend(subtaxons)
        t.add_subsumed(t1.subsumed)
    taxons.append(t)
    taxons_by_name[t.name]=t
    return t

def taxon_map(schema):
    all_taxons=[]
    taxons_by_name={}
    for entry in schema:
        add_taxons(entry,all_taxons,taxons_by_name)
    return taxons_by_name

if __name__=='__main__':
    print load_schema(file('konn2_schema.txt'))
