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

