import re
import sys
import datetime
from collections import defaultdict
from werkzeug import Response, redirect, escape
from web_stuff import render_template, Forbidden, ADMINS
import simplejson as json
from semdep import filters
from annodb.database import login_user, get_corpus, \
     default_database, get_database, get_times, add_time
from annodb.corpora import allowed_corpora_nologin, allowed_corpora


def senseEditor(request):
    db=request.corpus
    return render_template('senses.html',
                           corpus_name=db.corpus_name)

def writeToDB():
    db_senses=get_database().senses
    for doc in senseInfo:
        db_senses.save(doc)

def make_sense(wanted_lemma,pos,senses=None):
    w=wanted_lemma.lower()
    w=w.replace(u'\u00e4','ae')
    w=w.replace(u'\u00f6','oe')
    w=w.replace(u'\u00fc','ue')
    w=w.replace(u'\u00df','ss')
    if senses is None:
        senses=[]
    return {'_id':'%s_%s'%(w,pos),
            'lemma':wanted_lemma,
            'pos':pos,
            'senses':senses}

def sensesJson(request):
    db_senses=get_database().senses
    if 'create' in request.args:
        wanted_lemma=request.args['create']
        user=request.user
        if not user or user not in ADMINS:
            raise Forbidden('not an admin')
        info=list(db_senses.find({'lemma':request.args['create']}))
        if len(info)==0:
            from gwn_db import germanet
            gwn=germanet.get_database('gwn6')
            synsets=gwn.synsets_for_word(wanted_lemma)
            objs=defaultdict(list)
            for synset in synsets:
                pos_cat=str(synset.word_category)[0].upper()
                lu_ids=[lu.id for lu in synset.lexunit if lu.orth_form==wanted_lemma or lu.orth_var==wanted_lemma]
                if lu_ids:
                    lu_id=lu_ids[0]
                else:
                    lu_id='?'
                other_lus=[lu.orth_form for lu in synset.lexunit if lu.orth_form!=wanted_lemma and lu.orth_var!=wanted_lemma]
                if other_lus:
                    lu_descr='_'.join(other_lus)
                else:
                    lu_descr=str(synset.word_class)
                objs[pos_cat].append([lu_id,lu_descr])
            info=[]
            for k,v in objs.iteritems():
                info.append(make_sense(wanted_lemma,k,v))
            if len(info)==0:
                if wanted_lemma[0].isupper():
                    info.append(make_sense(wanted_lemma,'N'))
                else:
                    info.append(make_sense(wanted_lemma,'V'))
                    info.append(make_sense(wanted_lemma,'A'))
                    info.append(make_sense(wanted_lemma,'R'))
        return Response(json.dumps(info),mimetype="text/javascript")
    else:
        info=list(db_senses.find({}))
        return Response(json.dumps(info),mimetype="text/javascript")

def sensesJsonSingle(request,senseId):
    user=request.user
    if not user:
        raise Forbidden('not an admin')
    if request.method=='PUT':
        if user not in ADMINS:
            raise Forbidden('not an admin')
        stuff=json.load(request.stream)
        db_senses=get_database().senses
        info=db_senses.find_one({'_id':senseId})
        if info is None:
            info={}
            for k in ['_id','pos','lemma']:
                info[k]=stuff[k]
        for k,v in stuff.iteritems():
            if k not in ['_id','pos','need_save']:
                info[k]=v
        db_senses.save(info)
        return Response(json.dumps(info),mimetype="text/javascript")

PACKET_SIZE=50

def query_tasks(corpus_db,wanted_lemma,lemma_id=None,wanted_pos=None):
    lemma_attr=corpus_db.corpus.attribute('lemma','p')
    pos_attr=corpus_db.corpus.attribute('pos','p')
    if lemma_id is None:
        lemma_id=make_sense(wanted_lemma,wanted_pos)
    try:
        all_matches=lemma_attr.find(wanted_lemma)
    except KeyError:
        return ([],[])
    if wanted_pos is not None:
        all_matches &= pos_attr.find_list(filters[wanted_pos])
    old_tasks=[task for task in corpus_db.get_tasks() if task.level=='wsd' and task._doc.get('lemma_id',None)==lemma_id]
    old_spans=set([span[0] for task in old_tasks for span in task.spans])
    new_spans=sorted(set(all_matches)-old_spans)
    current_no=0
    new_tasks=[]
    for i in xrange((len(new_spans)+PACKET_SIZE-1)/PACKET_SIZE):
        while corpus_db.get_task('task_%s_%s'%(lemma_id,current_no)):
            current_no+=1
        task=corpus_db.create_task('%s_%s'%(lemma_id,current_no),'wsd')
        task.spans=[(x,x+1) for x in new_spans[i*PACKET_SIZE:(i+1)*PACKET_SIZE]]
        task.lemma_id=lemma_id
        task.annotators=[]
        new_tasks.append(task)
    return (old_tasks, new_tasks)

def create_new_task(task):
    annos=task.retrieve_annotations('*default*')
    for anno in annos:
        anno.lemma_id=task.lemma_id
    task._db.save_annotations(annos)

def sense_tasks(request,senseId):
    user=request.user
    if not user or user not in ADMINS:
        raise Forbidden('not an admin')
    sense=get_database().senses.find_one({'_id':senseId})
    print >>sys.stderr, sense
    (old_tasks,new_tasks)=query_tasks(request.corpus,sense['lemma'],sense['_id'],sense.get('pos','N'))
    if request.method=='GET':
        # retrieve task statistics
        info={'num_existing':len(old_tasks), 'num_remaining':len(new_tasks)}
        return Response(json.dumps(info),mimetype="text/javascript")
    elif request.method=='POST':
        stuff=json.load(request.stream)
        print >>sys.stderr, stuff
        if stuff['method']=='existing':
            for task in old_tasks:
                task.set_annotators(sorted(set(task._doc.get('annotators',[])).union(stuff['annotators'])))
            info={'num_existing':len(old_tasks), 'num_remaining':len(new_tasks)}
            return Response(json.dumps(info),mimetype="text/javascript")
        elif stuff['method']=='remaining':
            for task in new_tasks:
                create_new_task(task)
                task.set_annotators(sorted(set(task._doc.get('annotators',[])).union(stuff['annotators'])))
                task.save()
            info={'num_existing':len(old_tasks)+len(new_tasks),
                  'num_remaining':0}
            return Response(json.dumps(info),mimetype="text/javascript")
    print >>sys.stderr, 'huh?'
            
        