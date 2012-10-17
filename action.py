import os
from werkzeug import script, DispatcherMiddleware, redirect, \
    DebuggedApplication
from annodb.database import create_user, add_annotator, get_corpus
from web_stuff import AppRequest, render_template
from test_web import archive_user
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

def action_archive_user(username='user'):
    archive_user(username)

def action_add_annotator(dbname='xxx', taskname='task1', username='yannick'):
    add_annotator(dbname, taskname, username)

def action_remove_task(dbname='xxx', taskname='task1'):
    get_corpus(dbname).remove_task(taskname)

def action_list_empty_tasks(dbname='xxx'):
    for task in get_corpus(dbname).get_tasks():
        if not task.annotators:
            print task._id,
    print

script.run()
