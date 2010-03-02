try:
    import xml.etree.cElementTree as etree
except ImportError:
    import cElementTree as etree
from xml.sax.saxutils import quoteattr,escape
import sys
import os.path
import glob

def maybe_int(s):
    try:
        return int(s)
    except ValueError:
        return s

def words_fname(annodir,docid):
    return os.path.join(annodir,'Basedata','%s_words.xml'%(docid,))

def markable_fname(annodir,docid,levelname):
    return os.path.join(annodir,'markables','%s_%s_level.xml'%(docid,levelname))

def export_fname(annodir,docid):
    return os.path.join(annodir,'parsing','%s.exp'%(docid,))

def read_basedata(fname):
    tokens=[]
    token_ids={}
    ids=[]
    doc=etree.parse(fname)
    for elem in doc.findall('word'):
        token=elem.text.encode('ISO-8859-1')
        tok_id=elem.attrib['id']
        token_ids[tok_id]=len(tokens)
        ids.append(tok_id)
        tokens.append(token)
    return (tokens,token_ids,ids)

def write_basedata(fname,tokens):
    f=file(fname,'w')
    f.write('''<?xml version="1.0" encoding="ISO-8859-1"?>
<!DOCTYPE words SYSTEM "words.dtd">
<words>
''')
    for i,w in enumerate(tokens):
        print >>f,'  <word id="word_%d">%s</word>'%(i+1,escape(w))
    print >>f,"</words>"
    f.close()

def make_span(a,b,ids,ids2=None):
    """creates an MMAX2 span description given two
    points (0-based indices *between* tokens),
    optionally giving ids for starting and ending
    word positions - ids[N] is the word position that
    starts at position N, ids2[N] is the word position
    that ends at position N)."""
    if a>=b:
        raise ValueError('invalid span (%d,%d)'%(a,b))
    if ids2 is None and ids is not None:
        # assume ids advance normally
        ids2=[None]+ids
    if ids is None:
        a1=a+1
        if (a1==b):
            return 'word_%d'%(a1,)
        else:
            return 'word_%d..word_%d'%(a1,b)
    else:
        start_id=ids[a]
        end_id=ids2[b]
        if (start_id==end_id):
            return start_id
        else:
            return '%s..%s'%(start_id,end_id)
    

def write_dotmmax(dirname,base):
    f=file(os.path.join(dirname,'%s.mmax'%(base,)),'w')
    f.write('''<?xml version="1.0"?>
<mmax_project>
<turns></turns>
<words>%s_words.xml</words>
<gestures></gestures>
<keyactions></keyactions>
<views>
<stylesheet>muc_style.xsl</stylesheet>
</views>
</mmax_project>
'''%(base,))
    f.close()

def write_markables(dirname,basename,aa,ids=None,ids2=None,
                    encoding='ISO-8859-1'):
    # TODO: catch more exception and copy back backup files
    # if an error occurs (i.e., make sure there is *always*
    # a valid XML file in the end)
    fs={}
    cur_id=1
    raised=None
    if ids2 is None and ids is not None:
        # do this here so make_span doesn't have to do it each time
        ids2=[None]+ids
    for alvl,m_id,attrs,start_pos,end_pos in aa:
        if m_id is None:
            m_id=cur_id
            cur_id+=1
        if alvl in fs:
            f=fs[alvl]
        else:
            new_fname=os.path.join(dirname,'markables/%s_%s_level.xml'%(basename,alvl))
            if os.path.exists(new_fname):
                bak_fname=os.path.join(dirname,'markables/%s_%s_level.xml.bak'%(basename,alvl))
                os.rename(new_fname,bak_fname)
            f=file(new_fname,'w')
            f.write('''<?xml version="1.0" encoding="%s"?>
<!DOCTYPE markables SYSTEM "markables.dtd">
<markables xmlns="www.eml.org/NameSpaces/%s">
'''%(encoding,alvl))
            fs[alvl]=f
        m_id=maybe_int(m_id)
        if type(m_id)==int:
            m_id='markable_%d'%(m_id,)
        try:
            f.write('<markable id="%s" span="%s" mmax_level="%s"'%(
                m_id,make_span(start_pos,end_pos,ids,ids2),alvl))
        except ValueError,e:
            raised=e
            raised.args=tuple(list(raised.args)+[(alvl,m_id,attrs)])
            continue
        # write attributes
        for k,v in sorted(attrs.items()):
            if k in ['id','mmax_level','span']:
                continue
            if type(v)==tuple:
                assert len(v)==2
                f.write(' %s="%s"'%(k,make_span(v[0],v[1],ids,ids2)))
            elif issubclass(type(v),basestring):
                if type(v)==unicode:
                    f.write(' %s=%s'%(k,quoteattr(v).encode(encoding)))
                else:
                    f.write(' %s=%s'%(k,quoteattr(v)))
            else:
                f.write(' %s=%s'%(k,quoteattr(str(v))))
        f.write('/>\n')
    for alvl,f in fs.items():
        f.write('</markables>\n')
        f.close()
    if raised is not None:
        raise raised

def read_markables(dirname,basename,lvl,token_ids):
    doc=etree.parse(markable_fname(dirname,basename,lvl))
    tag=doc.getroot().tag
    if '}' in tag:
        ns=tag[:tag.index('}')+1]
    else:
        ns=''
    result=[]
    for elem in doc.findall(ns+'markable'):
        spans=[x.split('..')
               for x in elem.attrib['span'].split(',')]
        start_pos=token_ids[spans[0][0]]
        end_pos=token_ids[spans[-1][-1]]+1
        result.append((lvl,elem.attrib['id'],
                       elem.attrib,
                       start_pos,end_pos))
    return result

def read_token_markables(dirname,basename,lvl,tokens,token_ids):
    """reads a token-based annotation level and returns an array
    of attribute dictionaries"""
    doc=etree.parse(markable_fname(dirname,basename,lvl))
    all_attrs=[None]*len(tokens)
    tag=doc.getroot().tag
    if '}' in tag:
        ns=tag[:tag.index('}')+1]
    else:
        ns=''
    result=[]
    for elem in doc.findall(ns+'markable'):
        start_pos=token_ids[elem.attrib['span']]
        all_attrs[start_pos]=elem.attrib
    return all_attrs


def links2sets(aa,link_attr='COREF',set_attr='coref_set',
               anno_level='coref'):
    """goes through a list of annotations, computes the
    equivalence sets built by the given links and adds
    these as the 'coref_set' attribute"""
    sets={}
    elements={}
    next_set_id=0
    for alvl,m_id,attrs,start_pos,end_pos in aa:
        if alvl!=anno_level or link_attr not in attrs:
            continue
        link=(maybe_int(m_id),maybe_int(attrs[link_attr]))
        ks=[sets[mid] for mid in link if mid in sets]
        if len(ks)==0:
            set_id="set_%d"%(next_set_id,)
            elements[set_id]=[]
            next_set_id+=1
        elif len(ks)==1:
            set_id=ks[0]
        else:
            a=[]
            set_id=ks[0]
            for set2 in ks:
                elm=elements[set2]
                elements[set2]=[]
                a.extend(elm)
                for e in elm:
                    sets[e]=set_id
            elements[set_id]=a
        for e in link:
            old_setid=sets.get(e,'')
            sets[e]=set_id
            if old_setid!=set_id:
                elements[set_id].append(e)
    for anno in aa:
        if anno[0]!=anno_level or anno[1] not in sets:
            continue
        anno[2][set_attr]=sets[anno[1]]

class MMAXDiscourse:
    def __init__(self, basedir, docid):
        self.basedir=basedir
        self.docid=docid
        (self.tokens,self.tok_ids,self.ids)=read_basedata(words_fname(basedir,docid))
    def read_markables(self,level):
        return read_markables(self.basedir,self.docid,level,self.tok_ids)
    def write_markables(self,markables):
        write_markables(self.basedir,self.docid,markables,self.ids)
    def make_span(self,pos1,pos2):
        return make_span(pos1,pos2,self.ids)
    def all_levels(self):
        fnames=glob.glob(markable_fname(self.basedir,self.docid,'*'))
        n1=len(self.docid)+1
        return [os.path.basename(name)[n1:-10] for name in fnames]
    def retokenize(self,tokens_new):
        """imposes a new tokenization on an MMAX file (to correct
        tokenization errors)"""
        #TODO: use a list of (level,attribute) pairs to also
        # correct word_ids values such as min_ids in coref
        if self.tokens==tokens_new:
            print >>sys.stderr,"retokenize: nothing to do for %s"%(self.docid,)
            return
        print >>sys.stderr,"***RETOKENIZE: %s ***"%(self.docid,)
        all_markables=[]
        for level in self.all_levels():
            all_markables.extend(self.read_markables(level))
        mapping=compute_mapping(self.tokens,tokens_new)
        (mapped_ids,mapped_ids2)=mapping2ids(mapping)
        write_markables(self.basedir,self.docid,all_markables,
                        mapped_ids,mapped_ids2)
        write_basedata(words_fname(self.basedir,self.docid),tokens_new)
        self.tokens=tokens_new
        new_ids=['word_%d'%(i+1) for i in xrange(len(tokens_new))]
        tok_ids={}
        for i,n in enumerate(new_ids):
            tok_ids[n]=i
        self.ids=new_ids
        self.tok_ids=tok_ids

quotes=["''",'"']
def plausible_cont(tok1,tok2):
    if tok1==tok2:
        return True
    elif tok1.startswith(tok2):
        return True
    elif tok2.startswith(tok1):
        return True
    return False
def compute_mapping(tokens1,tokens2):
    """mostly O(n) computation of a mapping between two tokenizations
    of the same text"""
    idx1=0
    idx2=0
    result=[]
    while idx1<len(tokens1):
        if tokens1[idx1]==tokens2[idx2]:
            result.append(None)
            idx1+=1
            idx2+=1
        elif (tokens1[idx1] in quotes and
              tokens2[idx2] in quotes and
              (idx1+1==len(tokens1) and
               idx2+1==len(tokens2) or
               idx1+1<len(tokens1) and
               idx2+1<len(tokens2) and
               plausible_cont(tokens[idx1+1],tokens[idx2+1]))):
            result.append(('var',))
            idx1+=1
            idx2+=1
        elif ((idx1+1==len(tokens1) and
               idx2+2==len(tokens2) or
               idx1+1<len(tokens1) and
               idx2+2<len(tokens2) and
               plausible_cont(tokens1[idx1+1],tokens2[idx2+2])) and
              tokens1[idx1]==tokens2[idx2]+tokens2[idx2+1]):
            result.append(('split',[tokens2[idx2],tokens2[idx2+1]]))
            idx1+=1
            idx2+=2
        elif ((idx1+2==len(tokens1) and
               idx2+1==len(tokens2) or
               idx1+2<len(tokens1) and
               idx2+1<len(tokens2) and
               plausible_cont(tokens1[idx1+2],tokens2[idx2+1])) and
              tokens1[idx1]+tokens1[idx1+1]==tokens2[idx2]):
            result.append(('join',1,2))
            result.append(('join',2,2))
            idx1+=2
            idx2+=1
        else:
            raise ValueError("Cannot compute mapping between %s... and %s..."%(tokens1[idx1:idx1+3],tokens2[idx2:idx2+3]))
    return result

def mapping2ids(mapping):
    """computes a mapping so that spans for the pre-mapping
    tokens can be converted to spans for the post-mapping
    tokenization, assuming that the word positions are
    numbered word1...wordN, as write_basedata would do it."""
    ids=[]
    ids2=[]
    word_num=0
    word_id=None
    for x in mapping:
        if x is None or x[0]=='var':
            ids2.append(word_id)
            word_num+=1
            word_id='word_%d'%(word_num,)
            ids.append(word_id)
        elif x[0]=='split':
            ids2.append(word_id)
            word_num+=1
            word_id='word_%d'%(word_num,)
            ids.append(word_id)
            word_id='word_%d'%(word_num,)
            word_num+=len(x[1])-1
        elif x[0]=='join':
            if x[1]==1:
                ids2.append(word_id)
                word_num+=1
                word_id='word_%d'%(word_num,)
                ids.append(word_id)
            else:
                ids.append(word_id)
                ids2.append(word_id)
        else:
            raise ValueError("Cannot interpret mapping type %s"%(x,))
    ids2.append(word_id)
    assert len(ids)==len(mapping)
    assert len(ids2)==len(mapping)+1
    return (ids,ids2)

def get_docid(fname):
    fname=os.path.basename(fname)
    if '.' in fname:
        fname=fname[:fname.rindex('.')]
    return fname

def all_docs(dirname):
    docs=[get_docid(fname) for fname in glob.glob(os.path.join(dirname,'*.mmax'))]
    return docs
