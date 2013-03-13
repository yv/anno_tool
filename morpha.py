import sys
from itertools import izip
import subprocess

rasp_path='/export/local/yannick/space/compile/RASP'
arch_type='x86_64_linux'
morpha_path=rasp_path+'/morph/morpha.'+arch_type
morphg_path=rasp_path+'/morph/morphg.'+arch_type
morpha_verbstem=rasp_path+'/morph/verbstem.list'

class MorphaProcess:
    def __init__(self):
        self.proc=subprocess.Popen([morpha_path,'-f',morpha_verbstem],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    def __call__(self,input):
        self.proc.stdin.write(input)
        self.proc.stdin.write('\n')
        result=self.proc.stdout.readline().strip()
        return result

class MorphgProcess:
    def __init__(self):
        self.proc=subprocess.Popen([morphg_path,'-f',morpha_verbstem],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    def __call__(self,input):
        self.proc.stdin.write(input)
        self.proc.stdin.write('\n')
        result=self.proc.stdout.readline().strip()
        return result

my_morpha=MorphaProcess()
my_morphg=MorphgProcess()
morphg_cache={}

def lemmatize(t):
    m_input=[]
    for n in t.terminals:
        m_input.append('%s_%s'%(n.word,n.cat))
    result=my_morpha(' '.join(m_input)).split()
    for n,lem in izip(t.terminals,result):
        n.lemma=lem

def lemmatize_single(word,pos):
    result=my_morpha('%s_%s'%(word,pos))
    return result

def unlemmatize(terminals):
    m_input=[]
    wanted=[]
    for n in terminals:
        wcat='%s_%s'%(n.word,n.cat)
        if '+' not in wcat:
            pass
        elif wcat in morphg_cache:
            n.word=morphg_cache[wcat]
        else:
            m_input.append(wcat)
            wanted.append(n)
    result=my_morphg(' '.join(m_input)).split()
    for n,form,wcat in izip(wanted,result,m_input):
        if wcat[0].isupper():
            form=form[0].upper()+form[1:]
        morphg_cache[wcat]=form
        n.word=form
