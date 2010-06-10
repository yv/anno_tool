import sys
import os.path
from cStringIO import StringIO
from web_stuff import render_template, redirect
from mongoDB.annodb import AnnoDB
import pytree.export as export
import pytree.csstree as csstree
from werkzeug import escape
import json

db=AnnoDB()
tueba_corpus=db.corpus

def compute_url(text_id):
  year=text_id[1:3]
  month=text_id[3:5]
  day=text_id[5:7]
  artno=int(text_id[8:])
  return 'http://tintoretto/taz/19%s/%s/%s/art%03d.htm'%(year,month,day,artno)

def render_sentence(request,sent_no):
  sno=int(sent_no)-1
  words=tueba_corpus.attribute("word",'p')
  sents=tueba_corpus.attribute("s",'s')
  texts=tueba_corpus.attribute("text_id",'s')
  max_sent=len(sents)
  start,end,sent_attrs=sents[sno]
  tokens=[]
  for i in xrange(start,end+1):
      tokens.append(words[i].decode('ISO-8859-1'))
  t_id=texts.cpos2struc(end-1)
  t_start,t_end,t_attrs=texts[t_id]
  text_url=compute_url(t_attrs)
  trees_out=StringIO()
  parses=db.get_parses(sno)
  for k,v in parses.iteritems():
    if k=='_id':
      continue
    trees_out.write('<b>%s</b> <a href="javascript:$(\'tree:%s\').toggle()">[show]</a><br/>\n'%(k,k))
    t=export.from_json(v)
    csstree.write_html(t,trees_out,_id='tree:'+k,_style_display='none')
  return render_template('sentence.tmpl',
                         sent_id=sno+1,
                         sent_text=' '.join(tokens),
                         parses_html=trees_out.getvalue().decode('ISO-8859-15'),
                         text_id=t_attrs, text_url=text_url,
                         prev_sent='/pycwb/sentence/%d'%(sno,),
                         next_sent='/pycwb/sentence/%d'%(sno+2,),
                         disc_id=t_id)


def render_discourse(request,disc_no):
  words=tueba_corpus.attribute("word",'p')
  sents=tueba_corpus.attribute("s",'s')
  texts=tueba_corpus.attribute("text_id",'s')
  t_id=int(disc_no)
  t_start,t_end,t_attrs=texts[t_id]
  tokens=[w.decode('ISO-8859-15') for w in words[t_start:t_end+1]]
  sent=sents.cpos2struc(t_start)
  sent_end=sents.cpos2struc(t_end)
  sentences=[]
  for k in xrange(sent,sent_end+1):
    s_start,s_end,s_attr=sents[k]
    sentences.append(s_start-t_start)
  edus=sentences[:]
  indent=[0]*len(edus)
  return render_template('discourse.html',
                         sentences=json.dumps(sentences),
                         edus=json.dumps(edus),
                         tokens=json.dumps(tokens),
                         indent=json.dumps(indent))

def render_search(request,word):
  words=tueba_corpus.attribute("word","p")
  sents=tueba_corpus.attribute("s",'s')
  matches=[]
  try:
    idlist=words.find(word)
    message='%d Treffer.'%(len(idlist),)
    for k in idlist:
      sno=sents.cpos2struc(k)
      tokens=[]
      start,end,sent_attrs=sents[sno]
      for i in xrange(start,end+1):
        w=words[i].decode('ISO-8859-1')
        if i==k:
          tokens.append(u'<b>%s</b>'%(escape(w),))
        else:
          tokens.append(escape(w))
      matches.append((sno+1, ' '.join(tokens)))
  except KeyError:
    message='Nichts gefunden.'
  return render_template('matches.tmpl',
                         word=escape(word.decode('ISO-8859-15')),
                         matches=matches,
                         message=message)


def find_sent(request):
    #web.header('Content-Type','text/html;charset=UTF-8')
  sno=request.args.get('sent_no') or request.form.get('sent_no')
  if sno:
    return render_sentence(request,sno)
  else:
    return redirect('/pycwb')

def find_word(request):
  word=request.args.get('w') or request.form.get('w')
  if word:
    return render_search(request,word.encode('ISO-8859-15'))
  else:
    return redirect('/pycwb')
