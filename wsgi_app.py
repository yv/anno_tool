import os
import sys
import os.path

BASEDIR=os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASEDIR)

if 'PYNLP' not in os.environ:
      os.environ['PYNLP']='/export/common/yannick/pynlp'

import annodb.annotation as annotation
import test_web
import web_stuff
import discourse
import sense_edit

urls=[('/login',web_stuff.login_form),
      ('/logout',web_stuff.do_logout),
      ('/',web_stuff.index),
      ('/sentence/([0-9]+)',test_web.render_sentence),
      ('/annotate/([a-zA-Z0-9_]+)',annotation.annotate),
      ('/annotate2/([a-zA-Z0-9_]+)',annotation.annotate2),
      ('/mark_ready/([a-zA-Z0-9_]+)',annotation.mark_ready),
      ('/adjudicate/([a-zA-Z0-9_]+)',annotation.adjudicate),
      ('/download_anno/([a-zA-Z0-9_]+)',annotation.download_anno),
      ('/agreement/([a-zA-Z0-9_]+)',annotation.agreement),
      ('/saveAttributes',annotation.save_attributes),
      ('/discourse_list',discourse_edit.list_discourse),
      ('/discourse_rels',discourse_edit.discourse_rels),
      ('/discourse_rels_gold',discourse_edit.gold_discourse_rels),
      ('/discourse/([0-9]+)',discourse_edit.render_discourse),
      ('/printDiscourse/([0-9]+)',discourse_edit.render_discourse_printable),
      ('/saveDiscourse/([0-9]+)',discourse_edit.save_discourse),
      ('/archiveDiscourse/([0-9]+)',discourse_edit.archive_discourse),
      ('/compareDiscourse/([0-9]+)',discourse_edit.compare_discourse),
      ('/find_sent',test_web.find_sent),
      ('/find_word',test_web.find_word),
      ('/get_words',test_web.get_words),
      ('/tasks',web_stuff.tasks),
      ('/saveTask/([a-zA-Z0-9_]+)',web_stuff.save_task),
      ('/get_users',web_stuff.get_users),
      ('/stunden',web_stuff.stunden),
      ('/senses',sense_edit.senseEditor),
      ('/sensesJson',sense_edit.sensesJson),
      ('/sensesJson/([a-zA-Z0-9_#]+)',sense_edit.sensesJsonSingle),
      ('/wsd_tasks/([a-zA-Z0-9_#]+)',sense_edit.sense_tasks)
      ]

mymap=web_stuff.MyMap(urls)

application=mymap
