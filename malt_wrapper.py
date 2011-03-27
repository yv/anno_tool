import sys
import re
import os.path
import simplejson
from time import sleep
from os import kill
from signal import SIGINT
from shutil import rmtree
from CWB.CL import Corpus
from pytree import tree
from tempfile import NamedTemporaryFile, mkdtemp
from subprocess import Popen, PIPE, STDOUT, call
from pynlp.de.smor_pos import normalize_card
from itertools import izip

RFTAGGER_HOME='/home/yannickv/yannickv/compile/RFTagger'
TREETAGGER_HOME='/usr/local/TreeTagger'
MALT_HOME='/home/yannickv/sources/malt-1.4.1'

rftagger_cmd=[os.path.join(RFTAGGER_HOME,'bin/rft-annotate'),'-s',
              os.path.join(RFTAGGER_HOME,'lib/german-pc-32bit.par')]
treetagger_cmd=[os.path.join(TREETAGGER_HOME,'bin/tree-tagger'),
                '-token','-lemma',
                os.path.join(TREETAGGER_HOME,'models/german-par-linux-3.2.bin')]

tag_descr={}
val_map={'cas':{'acc':'a','gen':'g','dat':'d','nom':'n'}}

nn_morph_re=re.compile(r'cas=([a-z\*])\|num=([a-z]+|\*)\|gend=([a-z]+|\*)')
pper_morph_re=re.compile(r'per=([123])\|cas=([a-z\*])\|num=([a-z]+|\*)\|gend=([a-z]+|\*)')
vvfin_morph_re=re.compile(r'per=([123])\|num=([a-z]+)\|temp=([a-z]+)\|mood=([a-z]+)')
nn_like=set(['ART','NN','NE','ADJA','PDAT','PIAT','PIS','PDS',
             'PPOSAT','PRELS','PRELAT','APPRART'])
def sent2tree(sent):
    terminals=[]
    my_nn_like=nn_like
    for line in sent:
        postag=line[4]
        if postag=='PROAV':
            postag='PROP'
        tok=tree.TerminalNode(postag,line[1])
        if postag in my_nn_like:
            m=nn_morph_re.match(line[5])
            if m:
                tok.morph=''.join([m.group(1),m.group(2)[0],m.group(3)[0]])
            else:
                tok.morph='***'
        elif postag=='VVFIN':
            m=vvfin_morph_re.match(line[5])
            if m:
                tok.morph='%s%s%s%s'%(m.group(1),m.group(2)[0],m.group(4)[0],
                                      m.group(3)[-1])
            else:
                tok.morph='****'
        elif postag=='PPER':
            m=pper_morph_re.match(line[5])
            if m:
                tok.morph=''.join([m.group(2),m.group(3)[0],m.group(4)[0],m.group(1)])
        elif postag=='APPR':
            tok.morph=line[5][-1]
        else:
            tok.morph='--'
        tok.lemma=line[2]
        terminals.append(tok)
    for i,line in enumerate(sent):
        attach=int(line[6])
        tok=terminals[i]
        tok.syn_label=line[7]
        if attach==0:
            tok.syn_parent=None
        else:
            tok.syn_parent=terminals[attach-1]
    t=tree.Tree()
    t.terminals=terminals
    t.roots=terminals[:]
    return t

for l in file(os.path.join(RFTAGGER_HOME,'tagmap.txt')):
    line=l.strip().split()
    key=tuple(line[0].split('.'))
    tag=line[1]
    if len(line)>2:
        morph=tuple(line[2].split('|'))
    else:
        morph=()
    tag_descr[key]=(tag,morph)


def interpret_tags(tags):
    """creates a POS,morph combination out of the RFTagger tag"""
    for i in xrange(1,len(tags)+1):
        k=tuple(tags[:i])
        if k in tag_descr:
            val=tag_descr[k]
            return (val[0],make_morph(val[1],tags[i:]))
    print "cannot find:%s"%(tags,)
    return tags[0],'_'

def make_morph(tags,vals):
    """creates a morph attribute from the RFTagger tags"""
    alltags=[]
    for tag,val in izip(tags,vals):
        if tag=='*':
            continue
        if val[0]=='*':
            val='*'
        val=val.lower()
        if tag in val_map:
            val=val_map[tag].get(val,val)
        alltags.append('%s=%s'%(tag,val))
    if not alltags:
        return '_'
    else:
        return '|'.join(alltags)


pxs_re=re.compile('^P(?:POS|I|D|REL|W)S')
def get_cpos(pos):
    if pos.endswith('AT') or pos=='ART':
        return 'ART'
    elif pxs_re.match(pos) or pos in ['PPER','PRF']:
        return 'PRO'
    elif pos in ['ADV','ADJD']:
        return 'ADV'
    elif pos.startswith('APP') or pos=='PROAV':
        return 'PREP'
    elif pos[0] in 'NV':
        return pos[0]
    else:
        return pos

def mkconll(rftags,lemmalines):
    result=[]
    for sent,sent2 in izip(rftags,lemmalines):
        token_id=0
        result_sent=[]
        for line,line2 in izip(sent,sent2):
            assert line[0]==line2[0]
            assert line[1]==line2[1]
            token_id+=1
            token=line[0]
            pos=line[1]
            morph=line[2]
            lemma=line2[2]
            if lemma=='@card@':
                lemma=normalize_card(token)
            elif lemma=='<unknown>':
                lemma=token
            result_sent.append([str(token_id),token,lemma,
                                get_cpos(pos),pos,morph])
        result.append(result_sent)
    return result

def read_table(f):
    result=[]
    sent=[]
    for l in f:
        if l.strip()=='':
            if sent!=[]:
                result.append(sent)
            sent=[]
        else:
            sent.append(l.strip().split('\t'))
    if sent!=[]:
        result.append(sent)
    return result

def read_table_iter(f):
    sent=[]
    for l in f:
        if l.strip()=='':
            if sent!=[]:
                yield sent
            sent=[]
        else:
            sent.append(l.strip().split('\t'))
    if sent!=[]:
        yield sent

def read_tt_table(f,tab):
    result=[]
    for sent in tab:
        sent_out=[]
        for line in sent:
            line2=f.readline().strip().split('\t')
            assert line[0]==line2[0]
            sent_out.append(line2)
        result.append(sent_out)
    return result

def write_table(f,sents):
    for sent in sents:
        for l in sent:
            print >>f, '\t'.join(l)
        print >>f
    f.flush()

def map_rftags(lines):
    result=[]
    for line in lines:
        word=line[0]
        tags=line[1].split('.')
        (tag,morph)=interpret_tags(tags)
        result.append([word,tag,morph])
    return result

class TimeoutError(Exception):
    def __init__(self,value):
        self.value=value
    def __repr__(self):
        return repr(self.value)

def call_with_timeout(args,timeout):
    p=Popen(args,close_fds=True)
    waited=0
    while waited<=timeout:
        ret=p.poll()
        if ret is not None:
            return ret
        sleep(10)
        waited+=10
    os.kill(p.pid,SIGINT)
    raise TimeoutError('%s has not finished after %d seconds'%(args[0],waited))
        

def run_malt(fname_in, fname_out, timeout=1800):
    old_dir=os.getcwd()
    os.chdir(MALT_HOME)
    try:
        call_with_timeout(['java','-Xmx4G',
                           '-jar','malt.jar','-c','tiger_conf',
                           '-i',fname_in,'-o',fname_out,
                           '-ic','ISO8859-15'],
                          timeout)
    finally:
        os.chdir(old_dir)

def gold2auto(f_in,f_out):
    conll_orig=read_table(f_in)
    conll_preproc=get_auto_columns(([x[1] for x in sent] for sent in conll_orig))
    result=[]
    for sent_orig,sent_preproc in izip(conll_orig,conll_preproc):
        result.append([x[:2]+y[2:6]+x[6:]
                       for (x,y) in izip(sent_orig,sent_preproc)])
    write_table(f_out,result)

def get_auto_columns(sentences):
    # 1. dump to tokens file
    f_tokens=NamedTemporaryFile(prefix='tokens')
    for sent in sentences:
        for word in sent:
            print >>f_tokens,word
        print >>f_tokens
    f_tokens.flush()
    # 2. run RFTagger and get result
    rftag_proc=Popen(rftagger_cmd+[f_tokens.name],stdout=PIPE)
    rftag_result=read_table(rftag_proc.stdout)
    del f_tokens
    # 3. create input for TreeTagger lemmatization
    rftags=map(map_rftags,rftag_result)
    f_tokenpos=NamedTemporaryFile(prefix='rfpos')
    write_table(f_tokenpos,
                ([x[:2] for x in sent] for sent in rftags))
    tt_proc=Popen(treetagger_cmd+[f_tokenpos.name],stdout=PIPE)
    lemmalines=read_tt_table(tt_proc.stdout,rftags)
    conll_lines=mkconll(rftags,lemmalines)
    return conll_lines

def parseMalt(sentences):
    # 1. dump to tokens file
    f_tokens=NamedTemporaryFile(prefix='tokens')
    for sent in sentences:
        for word in sent:
            print >>f_tokens,word.replace('\x0c','_')
        print >>f_tokens
    f_tokens.flush()
    # 2. run RFTagger and get result
    try:
        rftag_proc=Popen(rftagger_cmd+[f_tokens.name],stdout=PIPE)
        rftag_result=read_table(rftag_proc.stdout)
    except:
        f_tokens.delete=False
        raise
    else:
        del f_tokens
    # 3. create input for TreeTagger lemmatization
    rftags=map(map_rftags,rftag_result)
    f_tokenpos=NamedTemporaryFile(prefix='rfpos')
    try:
        write_table(f_tokenpos,
                    ([x[:2] for x in sent] for sent in rftags))
        tt_proc=Popen(treetagger_cmd+[f_tokenpos.name],stdout=PIPE)
        lemmalines=read_tt_table(tt_proc.stdout,rftags)
    except:
        f_tokenpos.delete=False
        raise
    # 4. write conll_in file
    conll_dir=mkdtemp('malt')
    conll_lines=mkconll(rftags,lemmalines)
    f_conll=file(os.path.join(conll_dir,'conll_in.conll'),'w')
    write_table(f_conll,conll_lines)
    f_conll.flush()
    run_malt(f_conll.name,os.path.join(conll_dir,'conll_out.conll'))
    iconv_proc=Popen(['iconv','-f','UTF-8','-t','ISO-8859-15',
                      os.path.join(conll_dir,'conll_out.conll')],
                     stdout=PIPE)
    parsed_malt=read_table(iconv_proc.stdout)
    rmtree(conll_dir)
    return parsed_malt
    
CHUNK_SIZE=20000
def test(corpus_name,sent_nos):
    sents=[]
    corp=Corpus(corpus_name)
    words=corp.attribute('word','p')
    sentences=corp.attribute('s','s')
    result=[]
    for i in sent_nos:
        assert i<len(sentences),(i,len(sentences))
        s_start,s_end=sentences[i][:2]
        sents.append(words[s_start:s_end+1])
        if len(sents)>=CHUNK_SIZE:
            result+=parseMalt(sents)
            sents=[]
    if sents:
        result+=parseMalt(sents)
    return result

def parse_all(corpus_name,start_sent=0):
    if start_sent==0:
        f_out=file('/export/local/yannick/malt_all_%s.conll'%(corpus_name,),'w')
    else:
        f_out=file('/export/local/yannick/malt_all_%s-%s.conll'%(corpus_name,start_sent),'w') 
    sents=[]
    corp=Corpus(corpus_name)
    words=corp.attribute('word','p')
    sentences=corp.attribute('s','s')
    for i in xrange(start_sent,len(sentences)):
        assert i<len(sentences),(i,len(sentences))
        s_start,s_end=sentences[i][:2]
        sents.append(words[s_start:s_end+1])
        if len(sents)>=CHUNK_SIZE:
            print >>sys.stderr, "%s-%s"%(i-len(sents)+1,i)
            result=parseMalt(sents)
            write_table(f_out,result)
            sents=[]
    if sents:
        result=parseMalt(sents)
        write_table(f_out,result)
    f_out.close()

def malt2cqp(corpus_name):
    try:
        f_in=file('/export/local/yannick/malt_all_%s-all.conll'%(corpus_name))
    except IOError:
        f_in=file('/export/local/yannick/malt_all_%s.conll'%(corpus_name))
    corp=Corpus(corpus_name)
    words=corp.attribute('word','p')
    sentences=corp.attribute('s','s')
    for i,sent in enumerate(read_table_iter(f_in)):
        s_start,s_end=sentences[i][:2]
        assert (s_end-s_start+1)==len(sent), (i,f_in.tell(),
                                              words[s_start:s_end+1],
                                              [x[1] for x in sent])
        for j,line in enumerate(sent):
            if line[6]=='0':
                attach='ROOT'
            else:
                attach='%+d'%(int(line[6])-j-1)
            print '\t'.join([line[4],line[5],line[7],attach])
        

if __name__=='__main__':
    if sys.argv[1]=='wanted':
        wanted=simplejson.load(file('parses_wanted.json'))
        for k,v in wanted.iteritems():
            print >>sys.stderr, k, len(v)
            tabs=test(k,v)
            write_table(file('/export/local/yannick/malt_parses_%s.conll'%(k,),'w'),tabs)
    elif sys.argv[1]=='all':
        parse_all(sys.argv[2])
    elif sys.argv[1]=='cqp':
        malt2cqp(sys.argv[2])
