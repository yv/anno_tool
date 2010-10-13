allowed_corpora_nologin=['TUEBA4','R6PRE1','EUROPARL_EN','EUROPARL_DE']
allowed_corpora=allowed_corpora_nologin+['PTB']

def compute_url_tueba(text_id,unused_corpus):
    year=text_id[1:3]
    month=text_id[3:5]
    day=text_id[5:7]
    artno=int(text_id[8:])
    return 'http://tintoretto.sfb.uni-tuebingen.de/taz/19%s/%s/%s/art%03d.htm'%(year,month,day,artno)

def compute_url_europarl(text_id,corpus_name):
    year=text_id[-15:-13]
    month=text_id[-12:-10]
    day=text_id[-9:-7]
    return 'http://www.europarl.europa.eu/sides/getDoc.do?pubRef=-//EP//TEXT+CRE+20%s%s%s+ITEMS+DOC+XML+V0//%s'%(year,month,day,corpus_name[-2:])

corpus_sattr={'EUROPARL_EN':'file_name',
              'EUROPARL_DE':'file_name'}
corpus_d_sattr={'EUROPARL_EN':'SPEAKER_NAME',
                'EUROPARL_DE':'SPEAKER_NAME'}
corpus_urls={'TUEBA4':compute_url_tueba,
             'R6PRE1':compute_url_tueba,
             'EUROPARL_EN':compute_url_europarl,
             'EUROPARL_DE':compute_url_europarl}
