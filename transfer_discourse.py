#!/usr/bin/python
# -*- coding: iso-8859-15 -*-
import sys
import regex
from itertools import izip
from mercurial.bdiff import blocks
from annodb.database import get_corpus

__doc__='''
Transfer discourse documents between different corpus
versions.
Differences in
 (a) the token sequence
and/or
 (b) the sentence segmentation
should be detected (and hopefully corrected)
'''

def make_offsets(ws1, ws2):
    offsets_map={}
    blk=blocks('\n'.join(ws1),'\n'.join(ws2))
    for i1,i2,j1,j2 in blk:
        if i2>i1:
            for i,j in izip(xrange(i1,i2),xrange(j1,j2)):
                offsets_map[i]=j
    return offsets_map

def likely_same(ws1, ws2):
    s1=set(ws1)
    s2=set(ws2)
    overlap=float(len(s1.intersection(s2)))/float(len(s1.union(s2)))
    return overlap>0.8

def to_unicode_seq(ws):
    out=[]
    for w in ws:
        if not isinstance(w, unicode):
            out.append(w.decode('ISO-8859-15'))
        else:
            out.append(w)
    return out

def to_string_seq(ws):
    out=[]
    for w in ws:
        if isinstance(w, unicode):
            out.append(w.encode('ISO-8859-15'))
        else:
            out.append(w)
    return out

def check_words(words_c,words_db):
    idx=0
    while True:
        if idx==len(words_c):
            if idx==len(words_db):
                return True
            else:
                print >>sys.stderr, "Remaining bits [1]:",words_db[idx:]
                return False
        elif idx==len(words_db):
            print >>sys.stderr, "Remaining bits [2]:",words_c[idx:]
            return False
        w_c=words_c[idx]
        w_db=words_db[idx]
        if w_c!=w_db:
            min_idx=max(0,idx-1)
            #print >>sys.stderr, "no match: %s vs %s"%(words_db[min_idx:idx+2],words_c[min_idx:idx+2])
            return False
        idx+=1

def matches_doc(db,doc,t_id):
    '''returns true iff the given doc should be at the given t_id'''
    tokens=to_unicode_seq(doc['tokens'])
    texts=db.corpus.attribute('text_id','s')
    start,end,text_id=texts[t_id]
    words=to_unicode_seq(db.words[start:end+1])
    if check_words(words,tokens):
        return (True,True)
    elif likely_same(words,tokens):
        #print >>sys.stderr, "likely the same."
        return (True,False)
    return (False,False)

def make_edunames(edus,sents):
    seen_sents=set()
    sent_no=0
    result=[]
    for i in sorted(edus):
        if i in sents:
            sent_no+=1
            sub_edu=0
            seen_sents.add(i)
        else:
            sub_edu+=1
        result.append(('%s.%s'%(sent_no,sub_edu),i))
    assert seen_sents==sents
    return result

def make_eduname_mapping(names_old, names_new):
    result={}
    idx=0
    for nm_old,posn in names_old:
        while names_new[idx][1]<posn:
            idx+=1
        assert names_new[idx][1]==posn
        result[nm_old]=names_new[idx][0]
    return result

parens_re=regex.compile('\\(.*\\)')
edu_re=regex.compile('T[0-9]+|[0-9]+(?:\.[0-9]+)?')
def map_relations(rels_s,eduname_map):
    def map_edu(m):
        s=m.group(0)
        if s[0]=='T':
            return s
        elif '.' in s:
            return eduname_map[s]
        else:
            s2=eduname_map[s+'.0']
            if s2.endswith('.0'):
                return s2[:-2]
            else:
                return s2
    def map_rel_part(m):
        return edu_re.sub(map_edu,m.group(0))
    rels_new=[]
    for rel in rels_s.split('\n'):
        rel2=parens_re.sub(map_rel_part,rel)
        rels_new.append(rel2)
    return '\n'.join(rels_new)

def make_indent(edus,indent_map):
    result=[]
    old_indent=0
    for edu in edus:
        if edu in indent_map:
            old_indent=indent_map[edu]
        result.append(old_indent)
    return result

def transfer_doc(db,doc,t_id):
    tokens=to_string_seq(doc['tokens'])
    orig_sentence_offsets=doc['sentences']
    texts=db.corpus.attribute('text_id','s')
    sentences=db.sentences
    start,end,text_id=texts[t_id]
    # compute sentence offsets in new corpus
    sent0=sentences.cpos2struc(start)
    sentN=sentences.cpos2struc(end)
    new_sentence_offsets=set([sentences[i][0]-start for i in xrange(sent0,sentN+1)])
    words=to_string_seq(db.words[start:end+1])
    offset_map=make_offsets(tokens,words)
    # use mapping to compare old and new sentence offsets
    mapped_orig_sentence_offsets=set([offset_map[i] for i in orig_sentence_offsets])
    mapped_orig_edu_offsets=set([offset_map[i] for i in doc['edus']])
    indent_map=dict([(offset_map[i],indent) for (i,indent) in izip(doc['edus'],doc['indent'])])
    added_sentences=new_sentence_offsets.difference(mapped_orig_sentence_offsets)
    print "added sentences:", sorted(added_sentences)
    missing_sentences=(mapped_orig_sentence_offsets.difference(new_sentence_offsets))
    assert not missing_sentences, missing_sentences
    nonedu_new=dict((str(offset_map[int(x)]),1) for x in doc['nonedu'])
    uedus_new=dict((str(offset_map[int(x)]),1) for x in doc.get('uedus',{}))
    topics_new=[[offset_map[posn],topic_str] for (posn,topic_str) in doc['topics']]
    all_edus=mapped_orig_edu_offsets.union(added_sentences)
    # account for added sentences by adding them as nonedus
    for i in added_sentences:
        nonedu_new[str(i)]=1
    # compute edu name mapping for 
    edunames_old=make_edunames(mapped_orig_edu_offsets,mapped_orig_sentence_offsets)
    edunames_new=make_edunames(all_edus,new_sentence_offsets)
    eduname_mapping=make_eduname_mapping(edunames_old,edunames_new)
    print eduname_mapping
    doc_new={
        '_docno':t_id,
        '_user':doc['_user'],
        'tokens':to_unicode_seq(words),
        'sentences':sorted(new_sentence_offsets),
        'edus':sorted(all_edus),
        'indent':make_indent(sorted(all_edus),indent_map),
        'topics':topics_new,
        'nonedu':nonedu_new,
        'uedus':uedus_new,
        'relations':map_relations(doc['relations'],eduname_mapping)
        }
    #print doc
    #print doc_new
    return doc_new

def check_doc(db, doc):
    t_id=int(doc['_docno'])
    similar,same = matches_doc(db,doc,t_id)
    if similar:
        if same:
            #print "doc %s matches exactly. Yay."%(doc['_id'],)
            db.db.discourse.save(doc)
        else:
            print "doc %s matches approximately. half-Yay."%(doc['_id'],)
            doc2=transfer_doc(db,doc,t_id)
            doc2['_id']=doc['_id']
            print doc2
            db.db.discourse.save(doc2)
        return None
    else:
        old_id=doc['_id']
        print "doc %s does not match text %s"%(old_id,t_id)
        for offset in [-1,1,-2,2,-3,3]:
            similar,same=matches_doc(db,doc,t_id+offset)
            if similar:
                print "is really %s"%(t_id+offset,)
                (part1,annotator)=old_id.split('~')
                print 'id => %s~%s'%(t_id+offset,annotator)
                #db.db.discourse.remove({'_id':old_id})
                doc['_docno']=t_id+offset
                doc['_id']='%s~%s'%(t_id+offset,annotator)
                #db.db.discourse.save(doc)
                break

if __name__=='__main__':
    db=get_corpus(sys.argv[1])
    db2=get_corpus(sys.argv[2])
    for doc in list(db.db.discourse.find()):
        try:
            check_doc(db2,doc)
        except KeyError,e:
            print e
            # we could actually delete these?
            pass
