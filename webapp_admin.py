#!/usr/bin/env python
# -*- coding: iso-8859-15 -*-
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
import sys
import datetime
from cStringIO import StringIO
from werkzeug import Request, Response, cached_property, redirect, escape
from werkzeug.exceptions import HTTPException, MethodNotAllowed, \
    NotImplemented, NotFound, Forbidden
from werkzeug.contrib.securecookie import SecureCookie
from jinja2 import Environment, FileSystemLoader
import json
from annodb.database import login_user, get_corpus, \
     default_database, get_database, get_times, add_time
from annodb.corpora import allowed_corpora_nologin, allowed_corpora, allowed_corpora_admin

SENSIBLE_ENCODING='ISO-8859-15'

TEMPLATE_PATH=os.path.join(os.path.dirname(__file__),'templates')
#mylookup=TemplateLookup(directories=[TEMPLATE_PATH])
mylookup=Environment(loader=FileSystemLoader(TEMPLATE_PATH,encoding=SENSIBLE_ENCODING),
                     extensions=['jinja2.ext.do'])

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

ADMINS=['yannick','anna','nadine','janne', 'kathrin', 'heike', 'verena']

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
        if not data or data not in allowed_corpora_admin:
            data=default_database
        if 'force_corpus' in self.args:
            data2=self.args['force_corpus']
            if data2 in allowed_corpora and data!=data2:
                data=data2
        return get_corpus(data)

    @cached_property
    def session(self):
        data = self.cookies.get(COOKIE_NAME)
        if not data:
            return SecureCookie(secret_key=SECRET_KEY)
        return SecureCookie.unserialize(data, SECRET_KEY)
    
    def set_corpus_cookie(self,response):
        data=self.corpus.corpus_name
        if not data or data not in allowed_corpora:
            data=default_database
        expire_date=datetime.datetime.now()+datetime.timedelta(30)
        response.set_cookie('corpus',data,
                        expires=expire_date)

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
    if not corpus_name or corpus_name not in allowed_corpora_admin:
        corpus_name=default_database
    db=get_corpus(corpus_name)
    if not request.user:
        tasks=sorted(db.get_tasks(), key=by_id)
        corpora=allowed_corpora_nologin
        tasks_ready=[]
    else:
        user=request.user
        tasks=[]
        tasks_ready=[]
        for task in sorted(db.get_tasks(request.user), key=by_id):
            if task.get_status(user):
                tasks_ready.append(task)
            else:
                tasks.append(task)
        corpora=allowed_corpora
        if user in ADMINS:
            corpora=allowed_corpora_admin
    response=render_template('index.html',user=request.user,
                             tasks=tasks, tasks_ready=tasks_ready,
                             corpus_name=corpus_name,
                             corpora=corpora)
    expire_date=datetime.datetime.now()+datetime.timedelta(30)
    response.set_cookie('corpus',corpus_name,
                        expires=expire_date)
    return response

monate=['Januar','Februar','März','April','Mai','Juni',
        'Juli','August','September','Oktober','November','Dezember']
def parse_stunden(s):
    if ':' in s:
        hh,mm=s.split(':')
        hh_n=int(hh)
        return hh_n+numpy.sign(hh_n)*(int(mm)/60.0)
    return float(s.replace(',','.'))

def fmt_stunden(t):
    return '%d:%02d'%(t,int(t*60)%60)
    
def stunden(request):
    user=request.user
    if user is None:
        return redirect('/pycwb/')
    if request.method=='POST':
        when=request.form['when']
        what=request.form['what']
        hours=parse_stunden(request.form['hours'])
        add_time(user, when, what, hours)
    times=get_times(user)
    now=datetime.datetime.now()
    cur_month=now.strftime('%Y-%m')
    cur_val=now.year*12+now.month
    buf=StringIO()
    buf.write('<table class="table table-striped">\n')
    buf.write('<tr><th>Wann</th><th width="250">Was</th><th>Stunden</th></tr>\n')
    for month in sorted(times.iterkeys()):
        all_entries=times[month]
        sum_stunden=sum([x['hours'] for x in all_entries])
        try:
            monat_str=monate[int(month[5:])-1]
            monat_val=int(month[:4])*12+int(month[5:])
        except IndexError:
            monat_str="Invalid:"+month[5:]
            monat_val=-1
        display_str='%s %s'%(monat_str, month[:4].encode(SENSIBLE_ENCODING))
        buf.write('<tr class="header_row">\n')
        buf.write('<td><span class="icon-time">&nbsp;</span></td><td>%s</td><td>%2s</td>\n'%(display_str,fmt_stunden(sum_stunden)))
        buf.write('</tr>')
        if cur_val-monat_val<3:
            if request.args.get('order','default')=='entered':
                entries_list=all_entries
            else:
                entries_list=sorted(all_entries,key=lambda x:x['when'])
            for i, entry in enumerate(entries_list):
                entry_date=datetime.datetime.strptime(entry['when'],'%Y-%m-%d')
                if i%1:
                    fmt='odd_row'
                else:
                    fmt='even_row'
                when_str=entry_date.strftime('%d. (%A)')
                buf.write('<tr class="%s">\n'%(fmt,))
                buf.write('<td>%s</td><td>%s</td><td align="right">%s</td>\n'%(when_str, entry['what'].encode(SENSIBLE_ENCODING),
                                                                              fmt_stunden(entry['hours'])))
                buf.write('</tr>')
    buf.write('</table>')
    response=render_template('stunden.html',
                             user=request.user,
                             main_body=buf.getvalue().decode(SENSIBLE_ENCODING),
                             today_date=now.strftime('%F'))
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
