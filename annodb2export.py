# -*- coding: iso-8859-1 -*-
import sys
import re
import optparse
from pytree import export
from annodb.database import get_corpus

__usage__='''
anodb2export.py release.export RELEASE_CQP

merges connective and WSD annotation into a Negra Export file
'''

oparse=optparse.OptionParser(usage=__usage__)
oparse.add_option('-W','--no-wsd', dest="want_wsd",
                 help='leave out LU attributes from output',
                  action='store_false', default=True)

want_wsd=True

task_names=(['task_waehrend%s_new'%(k,) for k in xrange(1,11)]+
    ['task_nachdem%s_new'%(k,) for k in xrange(1,8)]+
    ['task_bevor_%s'%(k,) for k in xrange(1,3)]+
    ['task_als_r6_%s'%(k,) for k in xrange(3,6)]+
    ['task_alsA_new','task_aberA_new','task_aber_R6_1','task_aber_R6_2',
     'task_bevor_new','task_bevor_1','task_bevor_2','task_bevor_3','task_seitdem_1','task_sobald_1',
     'task_und_r6_1','task_und_r6_2','task_und_r6_3','task_und_r6_4','task_und_r6_5','task_und_r6_6'])

annotators=['melike','anna','stefanie','sabrina','yannick']

discourse_user='nadine'
#discourse_user='*gold*'

rel_map={
    'evaluative':'antithesis',
    'epistemic_cause':'evidence'
    }

def get_rel(info,which):
    k=getattr(info,which,None)
    if k in rel_map:
        k=rel_map[k]
    if k in ['NULL','##','None','']:
        k=None
    if isinstance(k,unicode):
        k=k.encode('ISO-8859-15')
    return k

quoted_comment_re=re.compile(r'(?:^|\s+)[a-z]+:.*')
comment_by_string={
    'beides':None,
    'unentscheidbar':'unbestimmbar',
    'idiomatisch':'idiomatisch',
    'ergibt keinen Sinn':'unbestimmbar',
    'Fremdwort':'Fremdwort',
    'Eigenname':'Eigenname',
    u'übertragen':'uebertragen',
    u'Funktionsverbgefüge':'Funktionsverbgefuege',
    'keine Lesart passt':'unbestimmbar',
    'veraltete Lesart':'unbestimmbar'
}
def munge_lu_comment(comment):
    '''
    Verena (18.07.2013): anders als vereinbart und am 10.06 herumgeschrieben:
    Format soll ein Teil des Kommentarfelds mit in die Export-Datei integriert werden.
    
    Teil der Email:
- beides --> kann raus
- unentscheidbar --> Kommentar: "unentscheidbar"
- idiomatisch --> Kommentar: "idiomatisch"
- idiomatisch? --> gibts nicht
- ergibt keinen Sinn --> Kommentar: "unsinnig"
- Fremdwort --> Kommentar: "Fremdwort"
- Eigenname --> Kommentar: "Eigenname"
- übertragen --> Kommentar: "uebertragen"
- Funktionsverbgefüge -->  Kommentar: "Funktionsverbgefuege" (mit Kathrin besprechen, ob zu lang)
- keine Lesart passt --> ggf mit "unisinnig" vereinheitlichen

- ### falsches Lemma --> s. unten
  [19.07.2013 Verena am Telefon: sollen als ### eingefügt werden, werden manuell überprüft]

ist jeder Goldstandardkommentar in der Liste möglicher Kommentare drin, wenn nicht: Fehler werfen


Vor jedem Release muss überprüft werden,
ob jedes Wortvorkommen, das annotiert wurde, auch das korrekte Lemma/POS hat und umgekehrt

    Verena (19.07.2013, per Telefon): anders als besprochen soll bei "veraltete Lesart" und
    anderen der Kommentar "unbestimmbar" benutzt werden.

    Zusätzlich zu dem, was wir besprochen haben, soll bei "Eigenname" und "Fremdwort" ein LU-Eintrag
    automatisch entfernt werden, wenn das entsprechende POS-Tag (NE, FM) vorliegt.
    '''
    cm=comment.split('\n')[0].strip()
    cm=quoted_comment_re.sub('',cm)
    if cm=='':
        return None
    else:
        if cm[:3] == '###':
            return '###'
        elif cm=='***':
            return None
        try:
            tag=comment_by_string[cm]
            return tag
        except KeyError:
            print >>sys.stderr, "ERROR: unknown comment string '%s'"%(cm,)
            return None

ignore_lu_cats=set([
        ('NE','-1/Eigenname'),
        ('FM','-1/Fremdwort')])

class ConnectiveDecorator:
    def __init__(self, corpus_name):
        db=get_corpus(corpus_name)
        self.db=db
        self.sentences=db.corpus.attribute("s",'s')
        self.words=db.words
        try:
            self.lemmas=db.corpus.attribute('lemma','p')
        except KeyError:
            self.lemmas=None
        tasks=[self.db.get_task(x) for x in task_names]
        self.spans=sorted(set([tuple(span) for task in tasks if task is not None for span in task.spans]))
        print >>sys.stderr, "%d spans found"%(len(self.spans),)
        self.span_idx=0
        if want_wsd:
            self.wsd=sorted(self.db.db.annotation.find({'level':'wsd','annotator':'wsdgold'}),key=lambda x:x['span'][0])
            print >>sys.stderr, "%d WSD annotations found"%(len(self.wsd),)
        else:
            self.wsd=[]
        self.wsd_idx=0
        self.sent_start=0
    def decorate(self, t):
        words1=[n.word for n in t.terminals]
        new_stop=self.sent_start+len(words1)
        words2=[self.words[i] for i in xrange(self.sent_start, new_stop)]
        assert words1==words2, (words1,words2)
        while self.span_idx<len(self.spans) and self.spans[self.span_idx][0]<new_stop:
            span=self.spans[self.span_idx]
            for a_name in annotators:
                anno=self.db.get_annotation(a_name,'konn2',span)
                if anno is not None and 'rel1' in anno or 'comment' in anno:
                    break
            if 'rel1' not in anno or anno.rel1=='NULL':
                self.span_idx+=1
                continue
            # munge DC into terminal
            rel_str=get_rel(anno,'rel1')
            rel2=get_rel(anno,'rel2')
            if rel2:
                rel_str+='/'+rel2
            n=t.terminals[anno.span[0]-self.sent_start]
            attrs=export.comment2attrs(getattr(n,'comment',None))
            attrs['DC']=rel_str
            n.comment=export.attrs2comment(attrs)
            self.span_idx+=1
        while self.wsd_idx<len(self.wsd) and self.wsd[self.wsd_idx]['span'][0]<new_stop:
            info=self.wsd[self.wsd_idx]
            lu_hash=info['sense']
            lu='#'.join(sorted([x for x in lu_hash if lu_hash[x]]))
            if lu=='': lu='-1'
            if 'comment' in info and info['comment'] is not None:
                lu_comment=munge_lu_comment(info['comment'])
                if lu_comment:
                    lu+='/'+lu_comment
            n=t.terminals[info['span'][0]-self.sent_start]
            attrs=export.comment2attrs(getattr(n,'comment',None))
            if (n.cat, lu) not in ignore_lu_cats:
                attrs['LU']=str(lu)
            n.comment=export.attrs2comment(attrs)
            self.wsd_idx+=1
        self.sent_start=new_stop

def main(export_fname, corpus_name):
    decorator=ConnectiveDecorator(corpus_name)
    f_in=file(export_fname)
    f_out=sys.stdout
    l=f_in.readline()
    while l!='':
        if l.strip()=='#FORMAT 4':
            fmt=4
            f_out.write('#FORMAT %d\n'%(fmt,))
        elif l.strip()=='#FORMAT 3':
            fmt=3
            f_out.write('#FORMAT %d\n'%(fmt,))
        else:
            f_out.write(l)
            m=export.bos_pattern.match(l)
            if m:
                sent_no=m.group(1)
                t=export.read_sentence(f_in,fmt)
                decorator.decorate(t)
                export.write_sentence_tabs(t,f_out,fmt)
                f_out.write('#EOS %s\n'%(sent_no))
        l=f_in.readline()


if __name__=='__main__':
    (opts,args) = oparse.parse_args()
    want_wsd=opts.want_wsd
    main(args[0],args[1])
