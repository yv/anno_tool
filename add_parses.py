import sys
import pytree.export as export
import mongoDB.annodb as annodb
import getopt

corpus_name='TUEBA4'
parse_name='release'

opts,args=getopt.getopt(sys.argv[1:],'c:p:')
for k,v in opts:
    if k=='-c':
        corpus_name=v
    elif k=='-p':
        parse_name=v

db=annodb.AnnoDB(corpus_name)
f=file(args[0])

parses=db.db.parses
for t in export.read_trees(f):
    sent_no=int(t.sent_no)-1
    span=db.sentences[sent_no]
    words=db.words[span[0]:span[1]+1]
    words2=[n.word for n in t.terminals]
    assert words==words2, (words, words2)
    trees=parses.find_one({'_id':sent_no})
    if trees is None:
        trees={'_id':sent_no}
    trees[parse_name]=export.to_json(t)
    parses.save(trees)

