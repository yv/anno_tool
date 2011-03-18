import PyCQP_interface

def use_corpus(corpus_name):
    cqp=PyCQP_interface.CQP(bin='/usr/local/bin/cqp',options='-c')
    cqp.Exec(corpus_name+";")
    cqp.maxProcCycles=10.0
    return cqp

def escape_cqp(s):
    s=s.replace('\\','\\\\')
    s=s.replace('[','\\[')
    s=s.replace('.','\\.')
    s=s.replace('"','\\"')
    return s

BLK_SIZE=20000
result_no=0

class CQPResult:
    def __init__(self,cqp,result_name):
        self.cqp=cqp
        self.rsize=int(cqp.Exec("size %s;"%(result_name,)))
        self.results=[]
        self.result_name=result_name
    def __len__(self):
        return self.rsize
    def __getitem__(self,k):
        if type(k)==slice:
            stop=min(self.rsize,k.stop)
            if k.step is None:
                step=1
            else:
                step=k.step
            return [self[kk] for kk in xrange(k.start,stop,step)]
        if k<0 or k>=self.rsize:
            raise IndexError(k)
        results=self.results
        while len(results)<=k:
            matches=self.cqp.Dump(subcorpus=self.result_name,
                                  first=len(results),
                                  last=min(self.rsize-1,len(results)+BLK_SIZE))
            for span in matches:
                results.append((int(span[0]),int(span[1])))
        return results[k]
    def __del__(self):
        self.cqp.Exec("discard %s ;"%(self.result_name,))

def query_cqp(cqp,query):
    global result_no
    #cqp.Exec(corpus_name+";")
    result_no+=1
    cqp.Query('Result%d = %s;'%(result_no,query))
    return CQPResult(cqp,'Result%d'%(result_no,))
    
