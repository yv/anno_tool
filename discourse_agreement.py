import re
from collections import defaultdict
from annodb.database import get_corpus
from StringIO import StringIO

class ComparedItem:
    def __init__(self, common, only1, only2, n_total=0, n_boring=0, positionKey=None):
        """sets of items that are common, only marked by annotator1, only by annotator2,
        number of total items that could be tagged, number of trivial agreements"""
        self.common=common
        self.only1=only1
        self.only2=only2
        self.n_total=n_total
        self.n_boring=n_boring
        self.positionKey=positionKey
    def f_measure(self):
        """f-measure over all interesting items"""
        n_common=len(self.common)
        n_only1=len(self.only1)
        n_only2=len(self.only2)
        if n_common==0:
            return 0.0
        else:
            return 2*n_common/float(2*n_common+n_only1+n_only2)
    def kappa_w(self):
        """kappa value assuming possible EDU boundaries for all words in the text"""
        n_common=len(self.common)+self.n_boring
        n_only1=len(self.only1)
        n_only2=len(self.only2)
        n_neg=self.n_total-n_common-n_only1-n_only2
        acc=float(n_common+n_neg)/float(self.n_total)
        marginal1=float(n_common+n_only1)/self.n_total
        marginal2=float(n_common+n_only2)/self.n_total
        expected=marginal1*marginal2+(1.0-marginal1)*(1.0-marginal2)
        return (acc-expected)/(1.0-expected)
    def print_out(self):
        positionKey=self.positionKey
        print "Common:"
        for s in self.common:
            print '\t%s %s'%(positionKey[s[0]],s[1])
        print "Only 1:"
        for s in self.only1:
            print '\t%s %s'%(positionKey[s[0]],s[1])
        print "Only 2:"
        for s in self.only2:
            print '\t%s %s'%(positionKey[s[0]],s[1])
        print "F-val=%.3f"%(self.f_measure())
        print "K_w  =%.3f"%(self.kappa_w())

class ComparedRelations:
    def __init__(self, rel_map, edumap1, edumap2):
        only1=[]
        only2=[]
        common=[]
        differing=[]
        for k,v in sorted(rel_map.iteritems()):
            if not v[0]:
                only2.append((k,v[1]))
            elif not v[1]:
                only1.append((k,v[0]))
            elif v[0]==v[1]:
                common.append((k,v[0]))
            else:
                differing.append((k,v))
        self.common=common
        self.differing=differing
        self.only1=only1
        self.only2=only2
        self.edumap1=edumap1
        self.edumap2=edumap2
    def name_for_range(self, r):
        try:
            return self.edumap1.unparse_range(r)
        except KeyError:
            return '%s#'%(self.edumap2.unparse_range(r),)
    def name_for_args(self, args):
        return '%s > %s'%(self.name_for_range(args[0]),
                          self.name_for_range(args[1]))
    def print_out(self):
        print "Common:"
        for r,rels in self.common:
            print '\t%-20s %s'%(self.name_for_args(r),','.join(rels))
        print "Different:"
        for r,rels in self.differing:
            print '\t%-20s %-25s %-25s'%(self.name_for_args(r),','.join(rels[0]),','.join(rels[1]))
        print "Only 1:"
        for r,rels in self.only1:
            print '\t%-20s %s'%(self.name_for_args(r),','.join(rels))
        print "Only 2:"
        for r,rels in self.only2:
            print '\t%-20s %s'%(self.name_for_args(r),','.join(rels))
    def add_to_stats(self,stats):
        for r,rels in self.common:
            stats.marginals1[','.join(rels)]+=1
            stats.marginals2[','.join(rels)]+=1
            stats.agreed[','.join(rels)]+=1
        for r,rels in self.differing:
            stats.marginals1[','.join(rels[0])]+=1
            stats.marginals2[','.join(rels[0])]+=1
            stats.disagreed[','.join(rels[0])]+=1
            stats.disagreed[','.join(rels[1])]+=1
            stats.disagreed_as['%s/%s'%(','.join(rels[0]),','.join(rels[1]))]+=1
        for r,rels in self.only1:
            stats.marginals1[','.join(rels)]+=1
            stats.unaligned[','.join(rels)]+=1
        for r,rels in self.only2:
            stats.marginals2[','.join(rels)]+=1
            stats.unaligned[','.join(rels)]+=1

class RelationStatistics:
    def __init__(self):
        self.marginals1=defaultdict(int)
        self.marginals2=defaultdict(int)
        self.agreed=defaultdict(int)
        self.disagreed=defaultdict(int)
        self.disagreed_as=defaultdict(int)
        self.unaligned=defaultdict(int)
    def print_out(self):
        print "*** Aggregate relations ***"
        sum_all=0
        print "Common:"
        for k,v in sorted(self.agreed.iteritems(),key=lambda x:-x[1]):
            sum_all+=2*v
            f_val=2.0*v/(self.marginals1[k]+self.marginals2[k])
            print "\t%-25s %3d   F=%.3f"%(k,v,f_val)
        print "Disagreed:"
        for k,v in sorted(self.disagreed.iteritems(),key=lambda x:-x[1]):
            sum_all+=v
            print "\t%-25s %3d"%(k,v)
        print "Frequent Disagreements:"
        for k,v in sorted(self.disagreed_as.iteritems(),key=lambda x:-x[1]):
            if v>1:
                print "\t%-40s %3d"%(k,v)
        print "Frequently Unaligned:"
        for k,v in sorted(self.unaligned.iteritems(),key=lambda x:-x[1]):
            sum_all+=v
            if v>1:
                print "\t%-25s %3d"%(k,v)

def make_rels(rels):
    if rels is None or len(rels)==0:
        return ''
    elif len(rels)==1:
        return rels[0].encode('ISO-8859-1','xmlcharrefreplace')
    else:
        return '<br>'+'<br>'.join(rels).encode('ISO-8859-1','xmlcharrefreplace')

def render_document_html(doc, rels={}, markers=[], replacement_topics=None):
    sentences=doc['sentences']
    edus=doc['edus']
    nonedu=doc.get('nonedu',{})
    uedus=doc.get('uedus',{})
    tokens=doc['tokens']
    indent=doc['indent']
    if replacement_topics is None:
        topics=doc.get('topics',[])
    else:
        topics=replacement_topics
    out=StringIO()
    next_sent=0
    next_edu=0
    next_topic=0
    next_marker=0
    sub_edu=0
    INDENT_STEP=20
    in_div=False
    rel=''
    for i,tok in enumerate(tokens):
        if next_topic<len(topics) and topics[next_topic][0]==i:
            if in_div:
                out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
                in_div=False
            rel=make_rels(rels.get('T%d'%(next_topic,),None))
            out.write('<div class="topic"><span class="edu-label">T%d</span>\n'%(next_topic,))
            out.write(topics[next_topic][1].encode('ISO-8859-1'))
            out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
            next_topic +=1
        if next_edu<len(edus) and edus[next_edu]==i:
            if in_div:
                out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
                in_div=False
            next_edu+=1
            sub_edu+=1
            if next_sent<len(sentences) and sentences[next_sent]==i:
                sub_edu=0
                next_sent+=1
            rel=make_rels(rels.get('%d.%d'%(next_sent,sub_edu),None))
            if nonedu.get(unicode(i),None):
                cls='nonedu'
            elif uedus.get(unicode(i),None):
                cls='uedu'
            else:
                cls='edu'
            out.write('<div class="%s" style="margin-left:%dpx"><span class="edu-label">%d.%d</span>'%(cls,indent[next_edu-1]*INDENT_STEP,next_sent,sub_edu))
            in_div=True
        if next_marker<len(markers) and markers[next_marker][0]==i:
            m=markers[next_marker]
            out.write('<span class="marker%s">%s</span>'%(m[1],m[2]))
            next_marker+=1
        out.write('%s '%(tok.encode('ISO-8859-1'),))
    if in_div:
        out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
    return out.getvalue()


class ComparisonResult:
    def __init__(self, doc):
        self.edu_compare=None
        self.topic_compare=None
        self.rels_compare=None
        self.tokens=doc['tokens']
        self.sentences=doc['sentences']
        self.edu_list=None
    def print_out(self):
        print "*** EDUs ***"
        if self.edu_list is not None:
            print_edus(self.edu_list, self.tokens)
        if self.edu_compare is not None:
            self.edu_compare.print_out()
        if self.topic_compare is not None:
            print "*** Topics ***"
            self.topic_compare.print_out()
        if self.rels_compare is not None:
            print "*** Relations ***"
            self.rels_compare.print_out()
    def add_to_stats(self,stats):
        self.rels_compare.add_to_stats(stats)
    def render_html(self, name1, name2, doc):
        tokens=self.tokens
        sentences=self.sentences
        nonedu=doc.get('nonedu',{})
        uedu=doc.get('uedus',{})
        next_sent=0
        next_edu=0
        next_topic=0
        sub_edu=0
        out=StringIO()
        rel=''
        in_div=False
        for i,tok in enumerate(tokens):
            if next_topic<len(topics) and topics[next_topic][0]==i:
                if in_div:
                    out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
                    in_div=False
                # rel=make_rels(topic_rels.get('T%d'%(next_topic,),None))
                out.write('<div class="topic"><span class="edu-label">T%d</span>\n'%(next_topic,))
                out.write(topics[next_topic][1].encode('ISO-8859-1'))
                out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
                next_topic +=1
            if next_edu<len(edus) and edus[next_edu]==i:
                if in_div:
                    out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
                    in_div=False
                next_edu+=1
                sub_edu+=1
                if next_sent<len(sentences) and sentences[next_sent]==i:
                    sub_edu=0
                    next_sent+=1
                # rel=make_rels(topic_rels.get('%d.%d'%(next_sent,sub_edu),None))
                if nonedu.get(unicode(i),None):
                    cls='nonedu'
                elif uedus.get(unicode(i),None):
                    cls='uedu'
                else:
                    cls='edu'
                out.write('<div class="%s"><span class="edu-label">%d.%d</span>'%(cls,next_sent,sub_edu))
                in_div=True
            out.write('%s '%(tok.encode('ISO-8859-15'),))
        if in_div:
            out.write('<span class="edu-rel">%s</span></div>\n'%(rel,))
        return out.getvalue().decode('ISO-8859-15')
        

def compare_edus(doc1,doc2,prefix=''):
    tokens=doc1['tokens']
    sentences=doc1['sentences']
    sent_gold=sentences[:]
    sent_gold.append(len(tokens))
    exclude=set(sent_gold)
    edus1=doc1['edus']
    edus2=doc2['edus']
    interesting1=set(edus1).difference(exclude)
    interesting2=set(edus2).difference(exclude)
    common=interesting1.intersection(interesting2)
    edu_only1=interesting1.difference(interesting2)
    edu_only2=interesting2.difference(interesting1)
    sent_idx=0
    s_common=[]
    s_only1=[]
    s_only2=[]
    positionKey={}
    for n in sorted(interesting1.union(interesting2)):
        while sent_gold[sent_idx]<n:
            sent_idx+=1
        positionKey[n]='[%s%d]'%(prefix,sent_idx)
        s=(n,"%s | %s"%(' '.join(tokens[n-2:n]),' '.join(tokens[n:n+2])))
        if n in common:
            s_common.append(s)
        elif n in edu_only1:
            s_only1.append(s)
        else:
            s_only2.append(s)
    return ComparedItem(s_common,s_only1,s_only2,len(tokens),len(sentences),positionKey=positionKey)

def compare_topics(doc1, doc2, prefix=''):
    diffs_topic=[]
    try:
        topics1=dict([x for x in doc1['topics']])
        topics2=dict([x for x in doc2['topics']])
    except KeyError:
        return None
    sentences=doc1['sentences']
    tokens=doc1['tokens']
    sent_gold=sentences[:]
    sent_gold.append(len(tokens))
    s_common=[]
    s_only1=[]
    s_only2=[]
    positionKey={}
    sent_idx=0
    for start,topic_str in doc1['topics']:
        while sent_gold[sent_idx]<start:
            sent_idx+=1
        positionKey[start]='[%s]'%(sent_idx,)
        if start not in topics2:
            s_only1.append((start, topic_str))
        else:
            s_common.append((start,'%s / %s'%(topic_str, topics2[start])))
    sent_idx=0
    for start,topic_str in doc2['topics']:
        if start not in topics1:
            while sent_gold[sent_idx]<start:
                sent_idx+=1
            positionKey[start]='[%s]'%(sent_idx,)
            s_only2.append((start, topic_str))
    return ComparedItem(s_common, s_only1, s_only2, len(sentences), positionKey=positionKey)

class RootMapping:
    """maps spans to their root words"""
    def __init__(self, db, t_id):
        self.db=db
        (start,end)=db.get_texts_attribute()[t_id][:2]
        self.pos=db.corpus.attribute('pos','p')[start:end+1]
        self.attach=db.corpus.attribute('attach','p')[start:end+1]
    def root_for_token(self, initial_idx, start, end, seen=None):
        idx=initial_idx
        while True:
            tok_pos=self.pos[idx]
            if tok_pos in ['$(','$,','$.']:
                return None
            tok_attach=self.attach[idx]
            if tok_attach=='ROOT':
                return idx
            new_idx=idx+int(tok_attach)
            if new_idx<start or new_idx >=end:
                return idx
            if seen is not None:
                seen.add(idx)
            idx=new_idx
    def roots_for_span(self, start, end):
        seen=set()
        roots=set()
        for idx in xrange(start,end):
            r_idx=self.root_for_token(idx, start, end, seen)
            if r_idx is not None:
                roots.add(r_idx)
        return roots

def process_edus(doc,root_map=None):
    """
    parses the edu ranges in a document and returns
    tuples of the form (edu_id, start, end, roots)
    """
    tokens=doc['tokens']
    sentences=doc['sentences']
    sent_gold=sentences[:]
    sent_gold.append(len(tokens))
    edus=doc['edus']
    nonedu=doc.get('nonedu',{})
    edu_list=[]
    def output_edu():
        if old_edu!=None and unicode(old_start) not in nonedu:
            if root_map is None:
                root_idxs=None
            else:
                root_idxs=root_map.roots_for_span(old_start,start)
            edu_list.append((old_edu,old_start,start,root_idxs))
    sent_idx=0
    sub_idx=0
    old_edu=None
    for start in edus:
        output_edu()
        if start>=sent_gold[sent_idx+1]:
            sent_idx+=1
            sub_idx=0
            assert sent_gold[sent_idx]==start, (sent_gold,start,edus)
        else:
            sub_idx+=1
        old_edu='%s.%s'%(sent_idx+1,sub_idx)
        old_start=start
    start=len(tokens)
    output_edu()
    return edu_list

def print_edus(edu_list, tokens):
    for edu_id, start, end, roots in edu_list:
        lst=[]
        for i in xrange(start,end):
            if i in roots:
                lst.append('[%s]'%(tokens[i],))
            else:
                lst.append(tokens[i])
        print edu_id, ' '.join(lst)

edu_re="[0-9]+(?:\\.[0-9]+)?"
topic_s="T[0-9]+"
topic_re=re.compile(topic_s)
span_re="(?:"+edu_re+"(?:-"+edu_re+")?|"+topic_s+")"
relation_re=re.compile("(\\w+(?:[- ]\\w+)*|\\?)\\s*\\(\\s*("+span_re+")\\s*,\\s*("+span_re+")\\s*\\)\\s*(%[^/]*)?\\s*")
comment_re=re.compile("//.*$");
def parse_relations(relations,edu_map):
    """
    turns the relations string into a list of tuples
    of the form (rel_name, arg1, arg2, marking)
    plus a list of unmarked relations
    """
    relations_unparsed=[]
    relations_parsed=[]
    for l in relations.split('\n'):
        l_orig=l.strip()
        l=l_orig
        l=comment_re.sub('',l)
        m=relation_re.match(l)
        if not m:
            relations_unparsed.append(l_orig)
        else:
            rel_label=m.group(1)
            try:
                rel_arg1=edu_map.parse_range(m.group(2))
                rel_arg2=edu_map.parse_range(m.group(3))
                rel_marking=m.group(4)
                if rel_marking is not None:
                    rel_marking=rel_marking.lstrip('%')
            except KeyError:
                relations_unparsed.append(l_orig)
            else:
                relations_parsed.append((rel_label,rel_arg1,rel_arg2,rel_marking))
    return relations_parsed, relations_unparsed

class EduMap:
    def __init__(self, edu_list):
        by_id={}
        by_minroot={}
        by_maxroot={}
        for edu_id, start, end, roots in edu_list:
            by_id[edu_id]=(start,end,roots)
            by_minroot[min(roots)]=edu_id
            by_maxroot[max(roots)]=edu_id
        self.by_id=by_id
        self.by_minroot=by_minroot
        self.by_maxroot=by_maxroot
    def parse_range(self,r_str):
        endpoints=r_str.split('-')
        start_edu=endpoints[0]
        if '.' not in start_edu:
            start_edu+='.0'
        if len(endpoints)==1:
            end_edu=start_edu
        else:
            end_edu=endpoints[-1]
            if '.' not in end_edu:
                end_edu+='.0'
        return (min(self.by_id[start_edu][2]),
                max(self.by_id[end_edu][2]))
    def unparse_range(self,(start,end)):
        start_edu=self.by_minroot[start]
        end_edu=self.by_maxroot[end]
        if start_edu==end_edu:
            return start_edu
        else:
            return '%s-%s'%(start_edu,end_edu)

class EduMapSpan:
    def __init__(self, edu_list):
        by_id={}
        by_minroot={}
        by_maxroot={}
        for edu_id, start, end, roots in edu_list:
            by_id[edu_id]=(start,end,roots)
            by_minroot[start]=edu_id
            by_maxroot[end]=edu_id
        self.by_id=by_id
        self.by_minroot=by_minroot
        self.by_maxroot=by_maxroot
    def parse_range(self,r_str):
        endpoints=r_str.split('-')
        start_edu=endpoints[0]
        if '.' not in start_edu:
            start_edu+='.0'
        if len(endpoints)==1:
            end_edu=start_edu
        else:
            end_edu=endpoints[-1]
            if '.' not in end_edu:
                end_edu+='.0'
        return (self.by_id[start_edu][0],
                self.by_id[end_edu][1])
    def unparse_range(self,(start,end)):
        start_edu=self.by_minroot[start]
        end_edu=self.by_maxroot[end]
        if start_edu==end_edu:
            return start_edu
        else:
            return '%s-%s'%(start_edu,end_edu)

def compare_relations(rels1, rels2):
    rel_map=defaultdict(lambda: ([],[],[],[]))
    for posn,(rel_label, arg1, arg2, marking) in enumerate(rels1):
        rel_map[(arg1,arg2)][0].append(rel_label)
        rel_map[(arg1,arg2)][2].append(posn)
    for posn,(rel_label, arg1, arg2, marking) in enumerate(rels2):
        rel_map[(arg1,arg2)][1].append(rel_label)
        rel_map[(arg1,arg2)][3].append(posn)
    return rel_map

def add_relation_comparison(db, t_id, doc1, doc2, result):
    """
    creates a relation mapping between the annotations
    of doc1 and doc2
    (first tries to match ranges via exact span, then
    via just the roots)
    """
    root_map=RootMapping(db,t_id)
    edu_list_1=process_edus(doc1,root_map)
    edu_list_2=process_edus(doc2,root_map)
    result.edu_list=edu_list_1
    edumap1a=EduMapSpan(edu_list_1)
    edumap2a=EduMapSpan(edu_list_2)
    edumap1b=EduMap(edu_list_1)
    edumap2b=EduMap(edu_list_2)
    parsed1a,unparsed1a=parse_relations(doc1['relations'], edumap1a)
    parsed2a,unparsed2a=parse_relations(doc2['relations'], edumap2a)
    rel_map_c={}
    rel_map_a=compare_relations(parsed1a,parsed2a)
    mapped_1=set()
    mapped_2=set()
    for k,v in rel_map_a.iteritems():
        if v[0] and v[1]:
            mapped_1.update(v[2])
            mapped_2.update(v[3])
            rel_map_c[(edumap1b.parse_range(edumap1a.unparse_range(k[0])),edumap1b.parse_range(edumap1a.unparse_range(k[1])))]=v
    parsed1b,unparsed1b=parse_relations(doc1['relations'], edumap1b)
    parsed2b,unparsed2b=parse_relations(doc2['relations'], edumap2b)
    parsed_more_1=[r for (i,r) in enumerate(parsed1b) if i not in mapped_1]
    parsed_more_2=[r for (i,r) in enumerate(parsed2b) if i not in mapped_2]
    rel_map_d=compare_relations(parsed_more_1,parsed_more_2)
    for k,v in rel_map_d.iteritems(): rel_map_c[k]=v
    result.rels_compare=ComparedRelations(rel_map_c,
                                          edumap1b,edumap2b)
    

def make_comparison(db, t_id, user1, user2, prefix=''):
    doc1=db.get_discourse(t_id,user1)
    doc2=db.get_discourse(t_id,user2)
    result=ComparisonResult(doc1)
    result.edu_compare=compare_edus(doc1,doc2,prefix)
    result.topic_compare=compare_topics(doc1,doc2,prefix)
    add_relation_comparison(db, t_id, doc1, doc2, result)
    return result

vorvergleich_docs=[
    [270,'janne','anna'],
    [271,'janne','anna'],
    [55,'anna2*old','sabrina2*old'],
    [69,'sabrina*Version1Sa','anna*Anna-Version1'],
    [143,'anna2*old','sabrina2*old'],
    [1471,'anna2*old','sabrina2*old']]

if __name__=='__main__':
    db=get_corpus('TUEBA4')
    stats=RelationStatistics()
    for t_id, user1, user2 in vorvergleich_docs:
        print "**** DOC: %s (%s/%s)****"%(t_id,user1,user2)
        result=make_comparison(db,t_id,user1,user2)
        result.add_to_stats(stats)
        result.print_out()
    stats.print_out()
