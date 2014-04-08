Scrapping Deals From Different Sources
=======================================

Dealfu project is using generally Scrapy framework for gathering deals from Deal Sites.
Scrapping parts consists of Spiders, Pipelines, Background Jobs, Command Line Applications
and Middleware parts.


Spiders
------------

In Scrapy the parts that are managing the scraping process are called spiders. Currently we have 2
spiders in our system for scrapping the __www.livingsocial.com__ and __www.groupon.com__ . For running
the groupon scrapper we use the following commands :

	scrapy crawl groupon

The command above will run the scrapper through new-york city (default) and will save
the deals into database (through a pipeline into Elasticsearch). There are other processes
that are run during scrapping phase but they will be explained later in more detail. 
To scrape the whole site you need to :

	crawl groupon -a division_path={{scrappers.resources}}divisions.json"

Where {{scrappers.resources}} is the place of the resources directory.
If you need to scrape certain amount of deals you can use the following command :

	scrapy crawl groupon -a num_of_deals=300


To run LivingSocial scrapper you can use (currently doesn't have any extra options like groupon):

	scrapy crawl livesocial


### Adding a new Scrapper

To add a new scrapper you need to create a file here {{project.root}}scrapers/dealfu_groupon/dealfu_groupon/spiders . Copying one of the current spiders, will be a good starting point. In general the
spiders are typical scrapy spiders (which can be read about in their documentation) with very small
differences we needed. A few points to be careful about :

- You need to add a pipeline variable to your spider which marks the pipelines it uses. If it is 
a general spider it can use _dealfu_groupon.pipelines.espipe.EsPipeLine_ or if it is not you can
use your custom pipeline in case of groupon it is : _dealfu_groupon.pipelines.grouponespipe.GrouponEsPipeLine_ 

- When a single deal is scraped you should return back a _DealfuItem_ (check current spider implementations)

Other parts are typical scrapy components used in most of scrapping projects.


Pipelines 
---------------------

Scrapy has that term called pipelines, which is responsible of handling the spiders' output. Currently in our project we have 2 pipelines responsible for dealing with scrapped deals. We have a general
pipeline called _BaseEsPipe_ which is good for most of the cases and also supplies hook places
for those that need more special behavior. General workflow of a scraped item in _BaseEsPipe_ :

- Item is checked if it is in database
- If in database we don't go further but we do a few checks like if it should be deleted, or if
it should be geo encoded (more about it later)
- If it is not in db it is saved
- It is send to a background process to be geo encoded if needed
- Also enabled if it is good enough (online deals sometimes are good enough without geo encoding)

Therefore when adding a new spider, you can reuse the _BaseEsPipe_ or extend it and hook into parts
that will be specific to your pipeline. For example _GrouponEsPipeLine_ is a specialized pipeline
which needs a little bit more than usual :

- We have some criteria when a mandatory field is missing that item is not processed further and it is dropped. However, it turns out that groupon sometimes sends partial data back when it is under load. Therefore we may need to retry those items later with a background process. _GrouponEsPipeLine_ hooks
into some places to make that possible (looking at source will clarify lots of things)


Background Jobs
-----------------------

We have a few background jobs in our project, which are responsible for handling the load that can not be done during the scrapping process. Because the Scrapy is single Threaded, everything that blocks
will hang the whole scrapping process. In current project most of the background processing is done via __Celery__ library. Some of the background processes will be explained in following sections and they are in {{project.root}}/dealfu_groupon/dealfu_groupon/background/ directory :


#### 1) Geo address submission task (geocode.py)

That task is called in scrapy pipelines when a merchant address is needed to be geo encoded. The general workflow is like :

- check if current address is in cache (we keep a Redis cache of already gathered addresses)
- if it is in cache save it in database and don't go further
- if no it is pushed into a Redis queue to be geo encoded later via other processes (which will be
explained later)


#### 2) Retry groupon deals (retry.py)

That task is specific to groupon and is responsible to retry some of the urls that were not able to
be gathered successfully during the scrapping process. What it does in general is to replay the scape processing for only specified urls. That part has a control for deals that need JS support to be 
gathered. Therefore we have some issues with Phantomjs (memory and cpu issues) and we decided to disable that part because we don't have much deals that are int that situation. Currently it is not disabled but needs to be disabled in future !!!


Command Line Applications
---------------------------

We have a few useful command line applications in the project tree but most important one is the part
that is geo (geopoll.py) encoding the merchant addresses. It is not a celery task, because celery is not very good at working with singleton long running processes. Currently we are using two remote geo
services for geo encoding the addresses :

- google free geo encode service
- datascience free geo service

Therefore the way you run the command line application differs according to geo service you want to use. If you want to use google service :

	python dealfu_groupon/cli/geopoll.py google

If want to use the other service :


	python dealfu_groupon/cli/geopoll.py datascience

The general workflow of fetching data is like :

- Listen on a Redis queue for incoming geo encoding requests
- When a new request comes fetch the address via the chosen geo service
- Cache the fetched address for future fetches
- Update and save the item which the geo address was requested for.
- Remove the entry from queue

In script there is a part which is checking for empty results. If google's service can not
find a given address, we give up, if data science can not find it we don't remove it from
queue so google's servce has a chance to fetch it again (Check _DataScienceToolkitGeoApi_ and _GoogleGeoApi_ source for more details).


Middlewares
---------------------------

In project we don't have any custom middlewares, but we hook into Scrapy's HTTP cache middleware.
We cache the scrapped deals on file system because, re-scrapping the whole site is taking too much time and also having that data on disk maybe useful in the future. In project we replace the Scrapy
caching policy with ours for more control of what needs to be cached or not (inspect the _CacheDealPolicy_ for more information). If someone needs to cache some of the requests, what needs to be done is (in spider) to pass meta {'cache':True} data into Request (look at Scrapy's docs) object.






