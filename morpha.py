import sys
from itertools import izip
import subprocess

morpha_path='/export/local/yannick/space/compile/RASP/morph/morpha.x86_64_linux'
morpha_verbstem='/export/local/yannick/space/compile/RASP/morph/verbstem.list'

class MorphaProcess:
    def __init__(self):
        self.proc=subprocess.Popen([morpha_path,'-f',morpha_verbstem],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    def __call__(self,input):
        self.proc.stdin.write(input)
        self.proc.stdin.write('\n')
        result=self.proc.stdout.readline().strip()
        return result

my_morpha=MorphaProcess()

def lemmatize(t):
    m_input=[]
    for n in t.terminals:
        m_input.append('%s_%s'%(n.word,n.cat))
    result=my_morpha(' '.join(m_input)).split()
    for n,lem in izip(t.terminals,result):
        n.lemma=lem