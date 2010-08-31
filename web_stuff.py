#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
templates, authentication and stuff


based on:
    Cookie Based Auth
    ~~~~~~~~~~~~~~~~~

    This is a very simple application that uses a secure cookie to do the
    user authentification.

    :copyright: Copyright 2009 by the Werkzeug Team, see AUTHORS for more details.
    :license: BSD, see LICENSE for more details.
"""
import os.path
import re
import datetime
from werkzeug import Request, Response, cached_property, redirect, escape
from werkzeug.exceptions import HTTPException, MethodNotAllowed, \
    NotImplemented, NotFound, Forbidden
from werkzeug.contrib.securecookie import SecureCookie
from jinja2 import Environment, FileSystemLoader
import json
from annodb.database import login_user, get_corpus, \
     default_database, get_database
from annodb.corpora import allowed_corpora_nologin, allowed_corpora

TEMPLATE_PATH=os.path.join(os.path.dirname(__file__),'templates')
#mylookup=TemplateLookup(directories=[TEMPLATE_PATH])
mylookup=Environment(loader=FileSystemLoader(TEMPLATE_PATH,encoding='ISO-8859-15'))

def render_template(template, **context):
    return Response(mylookup.get_template(template).render(**context),
                    mimetype='text/html')

def render_template_nocache(template, **context):
    return Response(mylookup.get_template(template).render(**context),
                    mimetype='text/html',
                    headers=[('Pragma','no-store, no-cache'),
                             ('Cache-control','no-store, no-cache, must-revalidate')])

# don't use this key but a different one; you could just use
# os.unrandom(20) to get something random.  Changing this key
# invalidates all sessions at once.
SECRET_KEY = 'H\xda}\xa3k0\x0c\xdc\x0bY\na\x08}\n\x1f\x13\xc5\x9f\xf1'

# the cookie name for the session
COOKIE_NAME = 'session'
ADMINS=['yannick','anna','stefanie']

class AppRequest(Request):
    """A request with a secure cookie session."""

    def logout(self):
        """Log the user out."""
        self.session.pop('username', None)

    def login(self, username):
        """Log the user in."""
        self.session['username'] = username
        self.session['real_user'] = username

    def become(self, username):
        if (self.session['real_user']==username or
            self.session['real_user'] in ADMINS):
            self.session['username']=username
        else:
            raise ValueError

    @property
    def logged_in(self):
        """Is the user logged in?"""
        return self.user is not None

    @property
    def user(self):
        """The user that is logged in."""
        return self.session.get('username')

    @property
    def corpus(self):
        data=self.cookies.get('corpus')
        if not data or data not in allowed_corpora:
            data=default_database
        return get_corpus(data)

    @cached_property
    def session(self):
        data = self.cookies.get(COOKIE_NAME)
        if not data:
            return SecureCookie(secret_key=SECRET_KEY)
        return SecureCookie.unserialize(data, SECRET_KEY)

def login_form(request):
    error = ''
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if password and login_user(username,password):
            request.login(username)
            if request.form.get('become'):
                request.become(request.form.get('become'))
            response=redirect('/pycwb/')
            request.session.save_cookie(response)
            return response
        error = '<p>Invalid credentials'
    if request.args.get('become'):
        become_text='<input type="hidden" name="become" value="%s">'%(request.args.get('become'),)
    else:
        become_text=''
    return Response('''
    <html><head>
        <title>Login</title></head><body><h1>Login</h1>
        <p>Not logged in.
        %s
        <form action="/pycwb/login" method="post">
          <p>
            <input type="text" name="username" size=20>
            <input type="password" name="password", size=20>
            %s
            <input type="submit" value="Login">
        </form>''' % (error, become_text), mimetype='text/html')

def do_logout(request):
    request.logout()
    response=redirect('/pycwb/')
    request.session.save_cookie(response)
    return response

def index(request):
    def by_id(x):
        return x._id
    corpus_name=request.cookies.get('corpus')
    try:
        corpus_name=request.args['corpus']
    except KeyError:
        pass
    if not corpus_name or corpus_name not in allowed_corpora:
        corpus_name=default_database
    db=get_corpus(corpus_name)
    if not request.user:
        tasks=sorted(db.get_tasks(), key=by_id)
        corpora=allowed_corpora_nologin
    else:
        tasks=sorted(db.get_tasks(request.user), key=by_id)
        corpora=allowed_corpora
    response=render_template('index.html',user=request.user,
                             tasks=tasks, tasks0=tasks,
                             corpus_name=corpus_name,
                             corpora=corpora)
    expire_date=datetime.datetime.now()+datetime.timedelta(30)
    response.set_cookie('corpus',corpus_name,
                        expires=expire_date)
    return response

def tasks(request):
    db=request.corpus
    tasks=db.get_tasks()
    return render_template('tasks.html',
                           tasks=tasks,
                           corpus=db.corpus_name)

def save_task(request,task_id):
    user=request.user
    if not user or user not in ADMINS or request.method!='POST':
        raise Forbidden('not an admin')
    db=request.corpus
    task=db.get_task(task_id)
    data=filter(None,request.stream.read().split(','))
    task.set_annotators(data)
    task.save()
    return Response('Ok')

def get_users(request):
    q=request.args['q']
    result=[]
    for user in get_database().users.find({}):
        if q and (q not in user.get('name','') and
                  q not in user['_id']):
            continue
        u={'id':user['_id']}
        if 'name' in user:
            u['name']=user['name']
        else:
            u['name']=user['_id']
        result.append(u)
    return Response(json.dumps(result),mimetype="text/javascript")

class MyMap(object):
    def __init__(self,urls):
        mapping=[]
        for s,fun in urls:
            mapping.append((re.compile('^%s$'%(s,)),fun))
        self.mapping=mapping
    def __call__(self,environ,start_response):
        try:
            req=AppRequest(environ)
            for regex, fun in self.mapping:
                match=regex.match(req.path)
                if match is not None:
                    resp=fun(req,*match.groups())
                    break
            else:
                raise NotFound()
        except HTTPException, e:
            resp=e
        return resp(environ,start_response)
