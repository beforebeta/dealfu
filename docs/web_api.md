Dealfu Web API
=============================

Wep API is responsible for querying scrapped data via Scrapy and showing it via a RESTFUL Api to its clients. It is basically a Django Rest Framework project. The Web API is backward compatible with Sqoot
Rest Api and generally follows its structure. Currently it has 2 endpoints :


### List Deals Api at /api/deals/

Generally it lists the scrapped and enabled deals (those which are good enough to be shown) to user.
Currently supports following parameters :

- query : full text searching 
- online 
- category_slugs
- location
- radius
- order
- page
- per_page

For more information about listed parameters, Sqoot api can be referred to.


### Detail Deal Api at /api_deals/<deal_id>/

Gets info of the specified deal.

### Category List at /api/categories/

Lists the deal categories which were gathered during scrapping process.



Django Management Commands
==============================

In the project we have a few Django commands that are quite useful for a few database tasks.

- esmanage : inits the elastic search indexes with mappings file
- esdump : useful commad for exporting deals deals data into xls
