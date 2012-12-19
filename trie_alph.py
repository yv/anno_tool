import codecs
import os.path
from kyotocabinet import DB

class DBAlphabet(object):
    __slots__=['fname','db','f','n','enc','encoding','growing']
    def __init__(self,fname,encoding='ISO-8859-15',load=True):
        self.fname=fname
        self.encoding=encoding
        self.db=DB()
        flags=DB.OWRITER|DB.OCREATE
        if not load:
            flags |= DB.OTRUNCATE
        self.db.open(fname+'.kch', flags)
        n=0
        if load:
            try:
                n=int(self.db.get('|n|'))
                self.f=file(fname+'.txt','a')
            except TypeError:
                self.f=file(fname+'.txt','w')
        else:
            self.f=file(fname+'.txt','w')
        self.n=n
        self.enc=codecs.getencoder(encoding)
        self.growing=True
    def __getitem__(self,key):
        if isinstance(key,unicode):
            key=self.enc(key)[0]
        val=self.db.get(key)
        if val is not None:
            return int(val)
        else:
            if not self.growing:
                raise KeyError
            n0=self.n
            self.db[key]=n0
            print >>self.f, key
            self.n=n0+1
            return n0
    def __iter__(self):
        return (l.rstrip('\n') for l in codecs.open(self.fname+'.txt','r',self.encoding))
    def __del__(self):
        self.db['|n|']=self.n

