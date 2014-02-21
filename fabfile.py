import os
import sys
import json
import time


from fabric.api import *

SETTINGS_DIR = "settings"
PROJECT_DIR = "scrapers/dealfu_groupon/"
PROJECT_NAME = "dealfu"

def devel():
    _get_conf("devel")

def staging():
    _get_conf("staging")


def production():
    _get_conf("production")



def full_deploy(branch_deploy="master"):
    """
    Prepares the remote machine for deployment
    """
    with hide('running', 'stdout', 'stderr'):
        with settings(warn_only=True):
            res = _execute("virtualenv -h").failed
    
    if res:
        #then you should install it fistly
        _execute("sudo apt-get -y install python-virtualenv")

    #at that stage we have virtualenv now go further and create a venv
    clean_deploy()

    _execute("sudo mkdir -p %s"%env.conf.DEPLOY_DIR)
    _execute("sudo chown -R %s %s"%(env.user, env.conf.DEPLOY_DIR))
    
    
    #we will need git before go further
    _execute("sudo apt-get -y install git")
    _execute("sudo apt-get -y install python-dev")

    #needed for lxml
    _execute("sudo apt-get -y install libxml2-dev libxslt-dev")

    #some base packages neede
    _execute("sudo apt-get -y install software-properties-common")
    _execute("sudo apt-get -y install python-software-properties")


    #install ES for db access
    _execute("sudo add-apt-repository ppa:webupd8team/java")
    _execute("sudo apt-get update")
    #_execute("sudo apt-get -y install oracle-java7-installer") run manually
    _execute("java -version")

    _install_es()


    with _cdir(env.conf.DEPLOY_DIR):
        #now create the virtualenv
        _execute("virtualenv --no-site-packages venv")
        #now clone the code into that directory
        _execute("git clone %s sjimporter"%(env.conf.GIT_ADDR))


def install_es():
    deb_add = "deb http://packages.elasticsearch.org/elasticsearch/0.90/debian stable main"
    _execute("echo '%s' | sudo tee -a /etc/apt/sources.list"%deb_add)
    _execute("sudo apt-get update")
    _execute("sudo apt-get -y --force-yes install elasticsearch")
    _execute("sudo service elasticsearch start")
    time.sleep(2)
    #test if it works
    _execute("sudo apt-get install curl")
    _execute("curl -X GET 'http://localhost:9200'")



def update_deploy(branch_deploy="develop"):
    """
    Updates the system if have any changes they are reflected
    """
    with _cdir(os.path.join(env.conf.DEPLOY_DIR, "sjimporter")):
        _execute("git pull origin %s"%branch_deploy)

        #the next step is to run requirements.txt
        _virtualenv("pip install -r requirements.txt")



def clean_deploy():
    """
    Cleans the previous system
    """
    #stop the processes
    _execute("if [ -d %s ]; then sudo rm -rf %s; fi"%(env.deploy_dir, env.deploy_dir))
    


def status_system():
    pass

def start_system():
    """
    Starts the remote system, before that one you should have
    run prep_deploy function
    """
    pass

def stop_system():
    """
    Stops the started system
    """
    pass



import elasticsearch
from elasticsearch.client import IndicesClient

def _get_es():
    """
    Internal util for es
    """
    es_host = env.conf.ES_SERVER
    es_port = env.conf.ES_PORT

    d = {
        "host":es_host,
        "port":es_port
    }

    return elasticsearch.Elasticsearch(hosts=[d])


def es_index_create(index):
    """
    Creates an index on ES server
    """

    es = IndicesClient(_get_es())
    print es.create(index=index)


def es_index_delete(index):
    """
    Deletes the index
    """
    es = IndicesClient(_get_es())
    print es.delete(index=index)


def es_list_mapping(index, mtype):
    """
    Lists mappings from specififed type and indexes
    """
    pass



def es_create_mapping(index):
    """
    Creates a mapping for specified type from resources file
    """
    resource_file = os.path.join(env.conf.DEPLOY_DIR,
                                 PROJECT_DIR,
                                 "resources/mappings.json")

    mapping_str = open(resource_file, "r").read()
    mappings = json.loads(mapping_str)

    #print json.dumps(mp, indent=4, sort_keys=True)
    es = IndicesClient(_get_es())

    for k,v in mappings.iteritems():
        print es.put_mapping(index, k, {k:mappings[k]})





def es_drop_mapping(index, mtype):
    """
    Drops mapping for specified mtype
    """
    pass


def insert_fixture(fixture):
    """
    Inserts some data into ES for testing
    """
    pass






#For internal usage do not call those
def _get_conf(name):
    """
    Loads the configuration from settings directory
    """
    #import first the settings
    cur_dir = os.getcwd()
    sys.path.append(cur_dir)

    __import__("%s"%SETTINGS_DIR, globals(), locals(), [], -1)
    conf = __import__("%s.%s"%(SETTINGS_DIR, name), globals(), locals(), [], -1)
    conf = getattr(conf, name)
    env.host_type = conf.HOST_TYPE
    env.port = conf.PORT
    env.hosts = conf.HOSTS
    env.user = conf.SSH_USER
    env.deploy_dir = conf.DEPLOY_DIR
    env.conf = conf
    env.env_type = name


def _execute(*args, **kwargs):
    """
    That will run the 'local' or 'run'
    method according to the env.hos_type
    that gives us opportunity to write the same code
    for local and remote machines. Innternal method
    do not use for public usage.
    """
    if env.host_type == "local":
        return local(*args, **kwargs)
    else:
        return run(*args, **kwargs)


def _cdir(*args, **kwargs):
    """
    The same version like one above but with
    cdir behaviour 
    """
    if env.host_type == "local":
        return lcd(*args, **kwargs)
    else:
        return cd(*args, **kwargs)


def _virtualenv(command):
    activate = "source %s"%(os.path.join(env.deploy_dir, "venv", "bin", "activate"))
    _execute(activate + '&&' + command)


