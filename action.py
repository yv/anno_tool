import os
from werkzeug import script, DispatcherMiddleware, redirect, \
    DebuggedApplication

from mongoDB.annodb import create_user, create_task_anno
import mongoDB.anno_query as anno_query
import web_stuff
import test_web
from web_stuff import AppRequest, render_template

urls=[('/login',web_stuff.login_form),
      ('/',web_stuff.index),
      ('/sentence/([0-9]+)',test_web.render_sentence),
      ('/annotate/([a-z0-9_]+)',anno_query.annotate),
      ('/annotate2/([a-z0-9_]+)',anno_query.annotate2),
      ('/saveAttributes',anno_query.save_attributes),
      ('/find_sent',test_web.find_sent),
      ('/annoquery',anno_query.display_annoquery)]

mymap=web_stuff.MyMap(urls)

application=mymap

@AppRequest.application
def redirect_to_pycwb(request):
    return redirect('/pycwb/')

def make_app():
    return DispatcherMiddleware(redirect_to_pycwb, {
            '/pycwb': mymap})

def make_debugged():
    return DebuggedApplication(make_app())

static_dirs={
    '/static':os.path.join(os.path.dirname(__file__),'static')
}

action_runserver = script.make_runserver(make_app,static_files=static_dirs)

action_rundebugging = script.make_runserver(make_debugged,static_files=static_dirs)

def action_adduser(username='user',passwd='glargfix'):
    create_user(username,passwd)

def action_createtask(username='yannick',task='all1'):
    create_task_anno(username, task)

script.run()
