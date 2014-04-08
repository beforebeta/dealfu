Deployment of Dealfu Project
===============================

Deployment is really important task when you have lots of moving parts, like we have in Dealfu project.
As a deployment tool we use __Ansible__ . In order to use currently written ansible scripts the one is not supposed to understand it, but when someone needs to add new stuff to it, reading its documentation will be very helpful. Ansible has that notion of putting your tasks in playbooks. That document will explain some of most important playbooks used in the project.

Initial Deployment 
----------------------------

To initialize the system for the first usage (installing servers, packages and etc), the following command can be run :

	ansible-playbook -i deploy/inventory/staging deploy/playbook/site.yml

The command above contains other playbooks which will be explained :

- appservers.yml : 	Contains setting up uwsgi and Django Rest Api and also has tasks that update the code repo
- cacheservers.yml : Sets up the Redis server on specified target
- dbservers.yml : Sets up the elasticsearch server
- loabbalancers.yml : Sets up the nginx web server which is in front of the uwsgi and Web Api


Deploying Scrapping Scripts
--------------------------------

Because project has lots of moving small parts (scrappers, background tasks, command line tasks) we use supervisord in the project. Therefore all tasks can be started/stopped inside supervisorctl tool. All of the deployment configurations for those parts are in __scrapbook.yml__ playbook file. For example to deploy current configuration :

	ansible-playbook -i deploy/inventory/staging deploy/playbook/scrapbook.yml

That command will install supervisord if not installed and will install config files that manage specific tasks.



Some useful Playbooks
-----------------------------

In project we have a few useful playbooks that we use from time to time 


##### Updating the code repo 

To update the code repo we use the following command : 

	ansible-playbook -i deploy/inventory/staging deploy/playbook/appservers.yml --tags repo


##### Initialize the ElastiSearch indexes 

To reset the current db and initialize with new mapping data we use : 

	ansible-playbook -i deploy/inventory/staging deploy/playbook/esmanage.yml


##### Upgrade Elastic Search Mapping

Sometimes we need to add a new field to ES, but changing the mapping needs to reset the whole database.
Loosing all that data is not very wise, when we have 70 000 deals in database. Therefore we have a playbook that backs up the old data, upgrades mapping and restores it back.

	ansible-playbook -i deploy/inventory/staging deploy/playbook/esupdatemap.yml



Setting Up Development Environment
-------------------------------

The easiest way of setting up development environment i found is to have a partial set up on a vagrant machine with the help of Vagrant (or some other virtual solution) and having the code on your local environment.