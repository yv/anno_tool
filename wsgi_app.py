import os
import sys
import os.path

BASEDIR=os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASEDIR)

import annodb.anno_query as anno_query
import test_web
import web_stuff

urls=[('/login',web_stuff.login_form),
      ('/logout',web_stuff.do_logout),
      ('/',web_stuff.index),
      ('/sentence/([0-9]+)',test_web.render_sentence),
      ('/discourse_list',test_web.list_discourse),
      ('/discourse/([0-9]+)',test_web.render_discourse),
      ('/saveDiscourse/([0-9]+)',test_web.save_discourse),
      ('/annotate/([a-zA-Z0-9_]+)',anno_query.annotate),
      ('/annotate2/([a-zA-Z0-9_]+)',anno_query.annotate2),
      ('/adjudicate/([a-zA-Z0-9_]+)',anno_query.adjudicate),
      ('/saveAttributes',anno_query.save_attributes),
      ('/find_sent',test_web.find_sent),
      ('/find_word',test_web.find_word),
      ('/annoquery',anno_query.display_annoquery),
      ('/tasks',web_stuff.tasks),
      ('/saveTask/([a-zA-Z0-9_]+)',web_stuff.save_task),
      ('/get_users',web_stuff.get_users)]

mymap=web_stuff.MyMap(urls)

application=mymap
