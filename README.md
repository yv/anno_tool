PyCWB
=====

This is an annotation tool for span-based annotation
of discourse connectives, discourse structure/discourse relations,
and word sense information. It uses the Open Corpus Workbench (CWB)
for storing and indexing corpus files, MongoDB for storing annotations,
and (optionally) PostgreSQL for interfacing with predefined inventories
of word senses such as GermaNet.


Installation
============
The application uses Python's WSGI interface for connecting to a web server.
Among all possible solutions, we will describe a solution using Apache, mod_wsgi,
and a local MongoDB installation.

Installing deb/ymp packages
---------------------------

The following should be available as existing packages (Ubuntu/SuSE):

 * python
 * libapache2-mod-wsgi / apache2-mod_wsgi
 * cython / python-Cython
 * python-pip
 * python virtualenv
 * mongodb (SuSE: see below)

mongodb on SuSE (unstable package)

    zypper addrepo http://download.opensuse.org/repositories/server:database/openSUSE_12.3/server:database.repo
    zypper refresh
    zypper install mongodb

Setting up Python packages
--------------------------
In a suitable directory, do:

    virtualenv anno_tool_env
    source anno_tool_env/bin/activate

    pip install -r /path/to/anno_tool/requirements.txt

You can test whether the installation works in general using

   python action.py rundebugging

This will run a test server on port 5000

Setting up mod_wsgi
-------------------

add the following to your apache2.conf:

    WSGIPythonHome /path/to/anno_tool_env
    WSGIScriptAlias /pycwb /path/to/anno_tool/wsgi_app.py
    Alias /static "/path/to/anno_tool/static"
    <Directory /path/to/anno_tool/static>
        AllowOverride None
        Order allow,deny
        Allow from all
    </Directory>

Configuration
=============

the file config.yml contains configuration directives for
the annotation tool.

 * pycwb.corpora.nologin: a list of corpora that are available for non-logged-in users
 * pycwb.corpora.login: a list of corpora that are only available to authenticated users
 * pycwb.corpora.admin: a list of corpora that only members of the admin group can see
 * pycwb.admins: a list of users that can create tasks etc.
 * pycwb.cwb_registry: the directory where the CWB registry files for corpora are searched (default: /usr/local/share/cwb/registry)

Creating users
--------------

Adding users, and changing users' passwords, can be done using the add_user action:

   python action.py add_user <username> <password>

Backing up and restoring data
=============================

The annotation tool uses one global user/password collection (annoDB.users),
and per-corpus collections for tasks, annotations, and discourse data
(annoDB.<CORPUS>.{tasks,annotation,discourse})

To make a backup from a database that has a corpus named R9PRE1, using
MongoDB's commands, you can use the following:

    mongodump -o data_backup -d annoDB -c users
    mongodump -o data_backup -d annoDB -c R9PRE1.tasks
    mongodump -o data_backup -d annoDB -c R9PRE1.annotation
    mongodump -o data_backup -d annoDB -c R9PRE1.discourse

You can restore all data by simply using

    mongorestore data_backup

If you use username/password authentication, you will need to add
"-u username -p password" to each command.
