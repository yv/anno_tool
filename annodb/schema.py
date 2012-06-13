import sys
import re
import simplejson as json
import os.path
from annodb.database import get_database
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

class SenseDict(dict):
    def __init__(self,coll):
        self.collection=coll
    def __missing__(self,k):
        sense_entry=self.collection.find_one({'_id':k})
        if sense_entry is None:
            return [[-1,'unknown']]
        else:
            senses=sense_entry['senses']
            self[k]=senses
            return senses

class WSDSchema:
    def __init__(self, coll):
        self.collection=coll
        self.senses_by_lemma_id={}
    def make_widgets(self, anno, db, out, out_js):
        sense_dict=SenseDict(self.collection)
        s_out=StringIO()
        db.display_span(anno['span'],1,0,s_out)
        munged_anno=dict(anno)
        munged_anno['senses']=sense_dict[munged_anno['lemma_id']]
        munged_anno['text']=s_out.getvalue().decode('ISO-8859-15')
        print >>out_js,'examples.push(%s);'%(json.dumps(munged_anno),)
    def make_display(self,anno,db,out,out_js):
        make_display_simple(self.get_slots(),anno,db,out)
    def get_state(self,anno):
        has_comment=(anno.get('comment',None) is not None)
        empty=False
        if anno.get('sense',None) is None:
            empty=True
        if empty and not has_comment:
            return 0
        else:
            if has_comment:
                return 2
            else:
                return 3
    def get_slots(self):
        return ['sense']
schemas['wsd']=WSDSchema(get_database().senses)


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
                      ['9380_Sitzmoebel','99979_Bankgebaeude','34523_Geldinstitut']),
                     ('beispiel',
                      ['37431_Modell','39958_Fallbeispiel']),
                     ('druck',
                      ['16697_Kunstdruck','19273_Erfolgsdruck','28808_Beruehrung','59957_Luftdruck']),
                     ('fall',
                      ['23788_Niedergang','24365_Sturz','39956_Angelegenheit','44524_Kasus']),
                     ('form',
                      ['16893_Gefaess','18450_Art_und_Weise','21726_Gestalt','36188_Fitness','39217_Verhalten']),
                     ('geschichte',
                        ['23683_Entstehungsgeschichte_Verlauf','23751_Angelegenheit_Affaere',
                         '38543_Geschichtswissenschaft','39843_Story_Erfolgsgeschichte',
                         '44685_Erzaehlung','72201_Vergangenheit','100299_Unterrichtsfach']),
                     ('kopf',
                      ['16537_Anfangsteil_Musikstueck','35602_Koerperteil','44537_Silbenteil',
                       '46252_Laengeneinheit_einen_Kopf_groesser','56718_Leiter',
                       '67435_Bauteil_Zylinderkopf']),
                     ('sache',
                      ['37501_Angelegenheit', '72129_Gegenstand']),
                     ('sinn',
                      ['22861_Verstaendnis_Geschaeftssinn','37541_Bedeutung','37542_Hoersinn']),
                     ('welt',
                      ['31539_Menschheit','31557_soziale_Gruppe_Fachwelt','61417_Bereich_Amateurbereich',
                       '62439_Weltall','62477_Erde']),
                     ('mann',
                      ['46875_Ehemann','47313_Geschlecht']),
                     ('mal',
                      ['18255_Kennzeichen','72540_Vorkommen']),
                     ('hoehe',
                      ['18516_Stufe','21856_Dimension']),
                     ('ag',
                      ['32301_Aktiengesellschaft','33158_Arbeitsgemeinschaft']),
                     ('ausschuss',
                      ['14661_Abfallprodukt','34327_Kommission']),
                     ('stuhl',
                      ['9375_Sitzmoebel','35999_Exkrement']),
                     ('frau',
                      ['44349_Anrede','46870_Ehefrau','47327_Geschlecht']),
                     ('partei',
                      ['31128_soziale_Gruppe','31854_politische_Gruppe','94900_juristisch']),
                     ('dienst',
                      ['27317_Arbeit','30119_Dienstleistung','34681_Dienstleistungsunternehmen']),
                     ('freundin',
                      ['47010_Partnerin','47058_Mitmensch','56198_Anhaengerin']),
                     ('ueberraschung',
                      ['21510_Geschenk','22545_Verblueffung','23763_Vorfall']),
                     ('gewinn',
                      ['20859_Ertrag','23382_Sieg','30967_Bereicherung']),
                     ('wahl',
                      ['19043_Alternative','27755_Auswahl','27789_Urnengang','100115_Abstimmung']),
                     ('stunde',
                      ['41020_Unterricht','72492_Zeitpunkt_Todesstunde','72772_60_Minuten','72818_Sprechstunde']),
                     ('sender',
                      ['34612_Sendeanstalt','45442_Sendeanlage','45443_Fernsehkanal','54633_Absender']),
                     ('karte',
                      ['15002_Fahrkarte','15339_Visitenkarte','16740_Plan','102274_Datentraeger_Telefonkarte']),
                     ('abfall',
                      ['68035_Muell','90738_Losloesung','90739_Druckabfall','99728_Hang']),
                     ('teilnahme',
                      ['19593_Interesse','22352_Anteilnahme','26219_Beteiligung','26234_Besuch']),
                     ('art',
                      ['18440_Konstruktionsweise','19447_Naturell','37010_Sorte','37028_Spezies','39574_Verhaltensweise']),
                     ('haus',
                      ['13245_Gebaeude','33219_Dynastie','40326_Sternzeichen','101788_Lokal_Treff','101789_Gesamtheit']),
                     ('ruhe',
                      ['19752_Gelassenheit','19896_Stille','22658_Beschaulichkeit','26490_Untaetigkeit','72953_Musse']),
                     ('anschlag',
                      ['28620_Attentat','40588_Aushang','99880_Schlagen_z.B._Ball','99881_Waffe_im_Anschlag','100240_Taste']),
                     ('kette',
                      ['8730_Fessel','14584_Schmuck','14702_Ankerkette','31278_Reihe_Folge','31290_Handelskette']),
                     ('abgabe',
                      ['21124_Steuer','21333_Abtretung','21419_Verkauf_Boerse','60109_Emission','89302_Schuss_Ball']),
                     ('land',
                      ['20826_Grundbesitz','59104_Boden','62542_Festland','62604_Provinz','64021_Staat','64026_Bundesland']),
                     ('programm',
                      ['11223_Computer','25098_Sendung','27849_Stundenplan_Lehrplan','45445_Sender',
                       '67149_Aktionsplan_Atomprogramm','73228_Zeitplan_Veranstaltungsprogramm']),
                     ('runde',
                      ['103235_Ausflug','24894_Sport','27805_Allgemein_Tarifrunde','31999_Gruppe','45552_Bier','61256_Strecke']),
                     ('spur',
                      ['13043_Fahrbahn','16568_Blutspur','38260_keine_Spur_verstehen','40167_Kriminalistik',
                       '46497_kleine_Menge_Hauch','61291_Fahrlinie_Fahrrinne']),
                     ('bestimmung',
                      ['23780_Schicksal','27762_Beauftragung','37913_Bewertung','38761_Ermittlung','42387_Festlegung','57356_Verwendungszweck'])]:
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
