import os
from werkzeug import script, DispatcherMiddleware, redirect, \
    DebuggedApplication
from annodb.database import create_user, create_task_anno, add_annotator
from web_stuff import AppRequest, render_template
from wsgi_app import application


@AppRequest.application
def redirect_to_pycwb(request):
    return redirect('/pycwb/')

def make_app():
    return DispatcherMiddleware(redirect_to_pycwb, {
            '/pycwb': application})

def make_debugged():
    return DebuggedApplication(make_app())

static_dirs={
    '/static':os.path.join(os.path.dirname(__file__),'static')
}

action_runserver = script.make_runserver(make_app,static_files=static_dirs)

action_rundebugging = script.make_runserver(make_debugged,static_files=static_dirs)

def action_add_user(username='user',passwd='glargfix'):
    create_user(username,passwd)

def action_add_annotator(taskname='task1', username='yannick'):
    add_annotator(taskname,username)

def action_createtask(username='yannick',task='all1'):
    create_task_anno(username, task)

script.run()
