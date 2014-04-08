Dealfu Project 
======================

Dealfu project consists of two parts :

- Scrapping part : Generally done via Scrapy and some background processes. It is documented it __scrapping_deals.md__ document

- Web API part : That is the part that is showing the scrapped deals (read-only). It is described in __web_api.md__ document.


### Used Databases

In project we use 2 different databases :

- ElasticSearch : It is used for keeping the scrapped deals information. It seemed convenient to use it
as data store and avoid managing a primary data store for just keeping the data. The insertion part is
done on scrapping part of the project and querying part resides on Web Api.

- Redis : It is used in lots of places during scrapping process.
	* Caching the geo encoding data
	* Addresses to be fetched are put on a queue on Redis
	* Celery uses Redis for its backend messaging
	* We use Redis during groupon retry phase


### Deployment 

Deployment part is described in __deployment.md__ document.