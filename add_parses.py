import sys
import pytree.export as export
import mongoDB.annodb as annodb

db=annodb.AnnoDB()
f=file(sys.argv[1])
parse_name='release'

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

