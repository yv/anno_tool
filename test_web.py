import sys
import os.path
from cStringIO import StringIO
from web_stuff import render_template, redirect
from mongoDB.annodb import AnnoDB
import pytree.export as export
import pytree.csstree as csstree

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
  t_start,t_end,t_attrs=texts.find_pos(end-1)
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
                         next_sent='/pycwb/sentence/%d'%(sno+2,))


def find_sent(request):
    #web.header('Content-Type','text/html;charset=UTF-8')
  sno=request.args.get('sent_no') or request.form.get('sent_no')
  if sno:
    return render_sentence(request,sno)
  else:
    return redirect('/pycwb')
