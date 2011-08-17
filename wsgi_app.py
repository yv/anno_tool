import os
import sys
import os.path

BASEDIR=os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASEDIR)

import annodb.anno_query as anno_query
import test_web
import web_stuff
import get_collocates

urls=[('/login',web_stuff.login_form),
      ('/logout',web_stuff.do_logout),
      ('/',web_stuff.index),
      ('/sentence/([0-9]+)',test_web.render_sentence),
      ('/discourse_list',test_web.list_discourse),
      ('/discourse_rels',test_web.discourse_rels),
      ('/discourse_rels_gold',test_web.gold_discourse_rels),
      ('/discourse/([0-9]+)',test_web.render_discourse),
      ('/printDiscourse/([0-9]+)',test_web.render_discourse_printable),
      ('/saveDiscourse/([0-9]+)',test_web.save_discourse),
      ('/archiveDiscourse/([0-9]+)',test_web.archive_discourse),
      ('/compareDiscourse/([0-9]+)',test_web.compare_discourse),
      ('/annotate/([a-zA-Z0-9_]+)',anno_query.annotate),
      ('/annotate2/([a-zA-Z0-9_]+)',anno_query.annotate2),
      ('/mark_ready/([a-zA-Z0-9_]+)',anno_query.mark_ready),
      ('/adjudicate/([a-zA-Z0-9_]+)',anno_query.adjudicate),
      ('/saveAttributes',anno_query.save_attributes),
      ('/find_sent',test_web.find_sent),
      ('/find_word',test_web.find_word),
      ('/get_words',test_web.get_words),
      ('/annoquery',anno_query.display_annoquery),
      ('/tasks',web_stuff.tasks),
      ('/saveTask/([a-zA-Z0-9_]+)',web_stuff.save_task),
      ('/get_users',web_stuff.get_users),
      ('/collocates',get_collocates.collocates_page),
      ('/get_collocates',get_collocates.get_collocates),
      ('/collocate_examples',get_collocates.collocate_examples),
      ('/sentence_graph',get_collocates.sentence_graph),
      ('/sketch',get_collocates.sketch_page),
      ('/get_sketch',get_collocates.get_sketch),
      ('/get_similar',get_collocates.get_similar),
      ('/stunden',web_stuff.stunden)]

mymap=web_stuff.MyMap(urls)

application=mymap
