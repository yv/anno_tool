import os
from werkzeug import script, DispatcherMiddleware
from mongoDB.anno_query import application
from mongoDB.annodb import create_user
import web_stuff
import test_web
from web_stuff import AppRequest, render_template

urls=[('/login',web_stuff.login_form),
      ('/',web_stuff.index),
    ('/sentence/([0-9]+)',test_web.render_sentence),
    ('/find_sent',test_web.find_sent)]

mymap=web_stuff.MyMap(urls)

def make_app():
    return DispatcherMiddleware(application, {
            '/pycwb': mymap})

static_dirs={
    '/static':os.path.join(os.path.dirname(__file__),'static')
}

action_runserver = script.make_runserver(make_app,static_files=static_dirs)

def action_adduser(username='user',passwd='glargfix'):
    create_user(username,passwd)

script.run()
