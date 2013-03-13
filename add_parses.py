import sys
import pytree.export as export
import annodb.database as annodb
import getopt
from pytree.exml import nodes_to_ne

corpus_name=None
parse_name='release'
sanitize=False

opts,args=getopt.getopt(sys.argv[1:],'c:p:s')
for k,v in opts:
    if k=='-c':
        corpus_name=v
    elif k=='-p':
        parse_name=v
    elif k=='-s':
        sanitize=True

if corpus_name is None:
    print >>sys.stderr, "Need to specify corpus_name"
    sys.exit(1)

db=annodb.AnnoDB(corpus_name)
f=file(args[0])

parses=db.db.parses
for t in export.read_trees(f):
    sent_no=int(t.sent_no)-1
    print >>sys.stderr, sent_no
    span=db.sentences[sent_no]
    words=db.words[span[0]:span[1]+1]
    words2=[n.word for n in t.terminals]
    assert words==words2, (words, words2)
    trees=parses.find_one({'_id':sent_no})
    if trees is None:
        trees={'_id':sent_no}
    if sanitize:
        nodes_to_ne(t)
    trees[parse_name]=export.to_json(t)
    parses.save(trees)

