import os
import sys
import os.path

BASEDIR=os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASEDIR)

import mongoDB.anno_query as anno_query
import test_web
import web_stuff

urls=[('/login',web_stuff.login_form),
      ('/logout',web_stuff.do_logout),
      ('/',web_stuff.index),
      ('/sentence/([0-9]+)',test_web.render_sentence),
      ('/annotate/([a-z0-9_]+)',anno_query.annotate),
      ('/annotate2/([a-z0-9_]+)',anno_query.annotate2),
      ('/saveAttributes',anno_query.save_attributes),
      ('/find_sent',test_web.find_sent),
      ('/annoquery',anno_query.display_annoquery)]

mymap=web_stuff.MyMap(urls)

application=mymap
