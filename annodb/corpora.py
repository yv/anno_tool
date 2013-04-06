from app_configuration import get_config_var

allowed_corpora_nologin=get_config_var('pycwb.corpora.nologin')
allowed_corpora=allowed_corpora_nologin+get_config_var('pycwb.corpora.login')
allowed_corpora_admin=allowed_corpora+get_config_var('pycwb.corpora.admin')

tueba_url_pattern=get_config_var('pycwb.urls.tueba')+'/19%s/%s/%s/art%03d.htm'

def compute_url_tueba(text_id,unused_corpus):
    year=text_id[1:3]
    month=text_id[3:5]
    day=text_id[5:7]
    artno=int(text_id[8:])
    return tueba_url_pattern%(year,month,day,artno)

parser_ordering_de=['release','tueba']

corpus_sattr={}
corpus_d_sattr={}
corpus_urls={}
parse_order={}
for corp_name in allowed_corpora_admin:
    corpus_urls[corp_name]=compute_url_tueba
    parse_order[corp_name]=parser_ordering_de
