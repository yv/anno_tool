import os
import os.path
import yaml

BASEDIR=os.path.dirname(os.path.abspath(__file__))

yml_config={}
for fname in [os.path.join(BASEDIR,'config.yml'),
              '/etc/pynlp.yml']:
    if os.path.exists(fname):
        yml_config=yaml.load(file(fname))
        break

def get_config_var(path, env=None):
    if env is None:
        env={}
    result=yml_config
    prefix=''
    for e in path.split('.'):
        if e[0]=='$':
            try:
                result=result[env[e[1:]]]
                prefix+=env[e[1:]]+'.'
            except KeyError,err:
                try:
                    result=result[':default']
                    prefix+=':default.'
                except KeyError:
                    raise KeyError('%s/:default[%s]'%(prefix,e))
        else:
            try:
                result=result[e]
            except KeyError:
                raise KeyError('%s/%s'%(prefix,e))
            prefix+=e+'.'
    return result

