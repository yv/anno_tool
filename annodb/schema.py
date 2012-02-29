import sys
import re
import simplejson as json
import os.path
from cStringIO import StringIO

BASEDIR=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASEDIR)

__doc__="""
a schema corresponds to one particular AnnoDB annotation
schema. It exposes the following methods:
- make_widgets(anno,out,out_js): creates HTML/JS code
  for creating appropriate editing widgets
- get_state(anno):
  returns 0 (blank) 1 (partial) 2 (full w/comment) 3 (full, no comment)
"""

schemas={}

def display_chooser(prefix,alternatives,chosen,out):
    for alt in alternatives:
        cls='choose'
        if alt==chosen:
            cls='chosen'
        out.write('''
[<a class="%s" onclick="chosen('%s','%s');" id="%s_%s">%s</a>]\n'''%(
                cls,prefix,alt,prefix,alt,alt))

def display_textbox(prefix,value,out):
    out.write('''
<textarea cols="80" id="%s" onkeyup="after_blur('%s')">'''%(
            prefix,prefix))
    if value is not None:
        out.write(value.encode('ISO-8859-15'))
    out.write('</textarea>')

def make_display_simple(slots,anno,db,out,spans=None):
    if spans is None:
        print >>out, '<div class="srctext" id="src:%s">'%(anno._id,)
        db.display_span(anno['span'],1,0,out)
        print >>out, '</div>'
    else:
        print >>out, '<div class="srctext" id="src:%s">'%(anno._id,)
        db.display_spans(spans,out)
        print >>out, '</div>'        
    out.write('<table>')
    for key in slots:
        out.write('<tr><td><b>')
        out.write(key)
        out.write(':</b></td><td>')
        out.write(anno.get(key,''))
        out.write('</td></tr>')
    val=anno.get('comment',None)
    if val is not None:
        out.write('<tr><td><b>comment:</b></td><td>%s</td></tr>')
    out.write('</table>')

class SimpleSchema:
    def __init__(self, schema_descr):
        self.descr=schema_descr
    def init_page(self,out,out_js):
        pass
    def make_widgets(self,anno,db,out,out_js):
        print >>out, '<div class="srctext" id="src:%s">'%(anno._id,)
        db.display_span(anno['span'],1,0,out)
        print >>out, '</div>'
        edited=False
        out.write('<table>')
        scheme=self.descr
        for key,values in scheme:
            out.write('<tr><td><b>')
            out.write(key)
            out.write(':</b></td><td>')
            val=anno.get(key,None)
            if val is not None:
                edited=True
                out_js.write('what_chosen["%s"]="%s";'%(anno._id+'-'+key,
                                                       val))
            display_chooser(anno._id+'-'+key,values,
                            val,out)
            out.write('</td></tr>')
        out.write('<tr><td><b>comment:</b></td><td>')
        val=anno.get('comment',None)
        if val is not None:
            edited=True
        display_textbox(anno._id+'-comment',
                        anno.get('comment',None),out)
        out.write('</td></tr></table>')
    def make_display(self,anno,db,out,out_js):
        make_display_simple(self.get_slots(),anno,db,out)
    def get_state(self,anno):
        scheme=self.descr
        has_comment=(anno.get('comment',None) is not None)
        empty=True
        full=True
        for key,unused_val in scheme:
            if anno.get(key,None) is None:
                full=False
            else:
                empty=False
        if empty and not has_comment:
            return 0
        elif full:
            if has_comment:
                return 2
            else:
                return 3
        else:
            return 1
    def get_slots(self):
        return [k for (k,unused_) in self.descr]
            

konn_scheme=[('temporal',['temporal','non_temporal']),
             ('causal',['causal','enable','non_causal']),
             ('contrastive',['kontraer','kontradiktorisch',
                             'parallel','no_contrast'])]

mod_scheme=[('class',['tmp','loc','sit','freq','dur',
                      'final','causal','concessive','cond','dir',
                      'instr','focus','source','manner',
                      'commentary','modalprt','intensifier'])]
ne_scheme=[('tag',['PER','ORG','LOC','GPE','OTHER'])]

schemas['konn']=SimpleSchema(konn_scheme)
schemas['mod']=SimpleSchema(mod_scheme)
schemas['ne']=SimpleSchema(ne_scheme)

for name, senses in [('bank',
                      ['6399_Sitzmoebel','9650_Bankgebaeude','2545_Geldinstitut']),
                     ('beispiel',
                      ['27407_Modell','29263_Fallbeispiel']),
                     ('druck',
                      ['23044_Kunstdruck','13904_Erfolgsdruck','20952_Beruehrung','41003_Luftdruck']),
                     ('fall',
                      ['17117_Niedergang','17533_Sturz','29261_Angelegenheit','32328_Kasus']),
                     ('form',
                      ['12198_Gefaess','13288_Art_und_Weise','15612_Gestalt','26504_Fitness','28743_Verhalten']),
                     ('geschichte',
                        ['17036_Entstehungsgeschichte_Verlauf','17090_Angelegenheit_Affaere',
                         '27238_Geschichtswissenschaft','28172_Story_Erfolgsgeschichte',
                         '32441_Erzaehlung','51052_Vergangenheit','73395_Unterrichtsfach']),
                     ('kopf',
                      ['11972_Anfangsteil_Musikstueck','26042_Koerperteil','32339_Silbenteil',
                       '33613_Laengeneinheit_einen_Kopf_groesser','38648_Leiter',
                       '47085_Bauteil_Zylinderkopf']),
                     ('sache',
                      ['27464_Angelegenheit', '50999_Gegenstand']),
                     ('sinn',
                      ['16427_Verstaendnis_Geschaeftssinn','27485_Bedeutung','27486_Hoersinn']),
                     ('welt',
                      ['22902_Menschheit','22919_soziale_Gruppe_Fachwelt','42095_Bereich_Amateurbereich',
                       '42842_Weltall','42860_Erde'])]:
    schemas['wsd_'+name]=SimpleSchema([('tag',senses)])

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

class TaxonomySchema:
    def __init__(self, schema):
        self.schema=schema
        self.taxon_mapping=taxon_map(schema)
    def make_widgets(self, anno, db, out, out_js):
        s_out=StringIO()
        db.display_span(anno['span'],1,0,s_out)
        munged_anno=dict(anno)
        munged_anno['text']=s_out.getvalue().decode('ISO-8859-15')
        print >>out_js,'examples.push(%s);'%(json.dumps(munged_anno),)
    def make_display(self,anno,db,out,out_js):
        make_display_simple(self.get_slots(),anno,db,out)
    def get_state(self,anno):
        scheme=self.descr
        has_comment=(anno.get('comment',None) is not None)
        empty=False
        if anno.get('rel1',None) is None:
            empty=True
        if empty and not has_comment:
            return 0
        else:
            if has_comment:
                return 2
            else:
                return 3
    def get_slots(self):
        return ['rel1','rel2']

konn2_schema=load_schema(file(os.path.join(BASEDIR,'konn2_schema.txt')))
schemas['konn2']=TaxonomySchema(konn2_schema)

class PropbankSchema:
    def __init__(self):
        pass
    def make_widgets(self,anno,db,out,out_js):
        self.make_display(anno,db,out,out_js)
    def make_display(self,anno,db,out,out_js):
        spans=[]
        span=anno['span']
        spans.append((span[0],span[1],'<b>','</b>'))
        for k,v in anno['args'].iteritems():
            if v is None: continue
            for span0,span1 in v:
                spans.append((span0,span1,'[<sub>%s</sub>'%(k,),']'))
        make_display_simple(['sense','morph'],anno,db,out,spans)

schemas['propbank']=PropbankSchema()

class PDTBSchema:
    def __init__(self):
        pass
    def make_widgets(self,anno,db,out,out_js):
        self.make_display(anno,db,out,out_js)
    def make_display(self,anno,db,out,out_js):
        spans=[]
        reltype=anno['reltype']
        span=anno['span']
        if reltype in ['Explicit']:
            for span in anno['conn_parts']:
                spans.append((span[0],span[1],'<b>','</b>'))
        if reltype in ['Implicit','Explicit','AltLex']:
            attrs=['semtag','semtag2']
            if reltype=='Explicit':
                attrs.append('conn_head')
        else:
            attrs=['reltype']
        for k in ['arg1','arg2','relattr','arg1attr','arg2attr']:
            try:
                parts=anno[k+'_parts']
            except KeyError:
                pass
            else:
                for span in parts:
                    spans.append((span[0],span[1],
                                  '[<sub>%s</sub>'%(k,),
                                  '<sub>%s</sub>]'%(k,)))
        make_display_simple(attrs,anno,db,out,spans)
        
schemas['pdtb']=PDTBSchema()
