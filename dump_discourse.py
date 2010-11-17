from annodb import get_corpus
from test_web import parse_relations

db=get_corpus('TUEBA4')
discourses=[111]
annotator1='anna'

for t_id in discourses:
  doc1=db.get_discourse(t_id,annotator1)
  tokens=doc['tokens']
  edus=doc['edus']
  (topic_rels,relations_unparsed)=parse_relations(doc.get('relations',''))
  print topic_rels