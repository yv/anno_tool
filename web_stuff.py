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
from werkzeug import Request, Response, cached_property, redirect, escape
from werkzeug.exceptions import HTTPException, MethodNotAllowed, \
    NotImplemented, NotFound
from werkzeug.contrib.securecookie import SecureCookie
from jinja2 import Environment, FileSystemLoader
from mongoDB.annodb import login_user, AnnoDB
from anno_config import anno_sets

db=AnnoDB()

TEMPLATE_PATH=os.path.join(os.path.dirname(__file__),'templates')
#mylookup=TemplateLookup(directories=[TEMPLATE_PATH])
mylookup=Environment(loader=FileSystemLoader(TEMPLATE_PATH,encoding='ISO-8859-15'))

def render_template(template, **context):
    return Response(mylookup.get_template(template).render(**context),
                    mimetype='text/html')

# don't use this key but a different one; you could just use
# os.unrandom(20) to get something random.  Changing this key
# invalidates all sessions at once.
SECRET_KEY = 'H\xda}\xa3k0\x0c\xdc\x0bY\na\x08}\n\x1f\x13\xc5\x9f\xf1'

# the cookie name for the session
COOKIE_NAME = 'session'

class AppRequest(Request):
    """A request with a secure cookie session."""

    def logout(self):
        """Log the user out."""
        self.session.pop('username', None)

    def login(self, username):
        """Log the user in."""
        self.session['username'] = username

    @property
    def logged_in(self):
        """Is the user logged in?"""
        return self.user is not None

    @property
    def user(self):
        """The user that is logged in."""
        return self.session.get('username')

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
            response=redirect('/pycwb/')
            request.session.save_cookie(response)
            return response
        error = '<p>Invalid credentials'
    return Response('''
        <title>Login</title><h1>Login</h1>
        <p>Not logged in.
        %s
        <form action="/pycwb/login" method="post">
          <p>
            <input type="text" name="username" size=20>
            <input type="password" name="password", size=20>
            <input type="submit" value="Login">
        </form>''' % error, mimetype='text/html')

def do_logout(request):
    request.logout()
    response=redirect('/pycwb/')
    request.session.save_cookie(response)
    return response

def index(request):
    if not request.user:
        tasks=[t._id for t in db.get_tasks()]
    else:
        tasks=[t._id for t in db.get_tasks(request.user)]
    return render_template('index.html',user=request.user,
                           tasks=tasks, tasks0=anno_sets)


@AppRequest.application
def application(request):
    if request.args.get('do') == 'logout':
        request.logout()
        response = redirect('.')
    elif request.logged_in:
        response = index(request)
    else:
        response = login_form(request)
    request.session.save_cookie(response)
    return response

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
                    

if __name__ == '__main__':
    run_simple('localhost', 4000, application)
