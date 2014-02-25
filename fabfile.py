import os
import sys
import json
import re
import yaml

from fabric.api import *

SETTINGS_DIR = "settings/deploy/inventory/group_vars/"

def vagrant():
    env.host_type = "remote"
    env.port = "2222"
    env.hosts = ["192.168.0.113"]
    env.user = "vagrant"
    _get_conf("vagrant")


def staging():
    env.host_type = "remote"
    env.port = "22"
    env.hosts = ["dealfu.dfvops.com"]
    env.user = "root"
    _get_conf("staging")


def production():
    raise NotImplemented


def full_deploy(branch_deploy="master"):
    """
    Prepares the remote machine for deployment
    """
    #run the ansible here
    pass



def update_deploy(branch_deploy="develop"):
    """
    Updates the system if have any changes they are reflected
    """
    #call here only the appropriate ansibal tasks
    pass


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




#For internal usage do not call those
def _resolve_var(s, conf):
    """
    Resolves a variable against the given dict
    @param s: in the form of ${x.y}
    @param conf: in the form of dict
    """
    pass



def _get_conf(name):
    """
    Loads the configuration from settings directory
    """
    #import first the settings
    cur_dir = os.getcwd()
    settings_path = os.path.join(cur_dir,
                                 SETTINGS_DIR)

    settings_file = os.path.join(settings_path,
                                 ".".join([name, "yml"]))

    if os.path.exists(settings_file):
        raise Exception("invalid settings supplied")



    conf = yaml.load(open(settings_file, "r"))
    env.deploy_dir = conf["project"]["root"]
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


