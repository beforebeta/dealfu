import cli.app

from dealfu_groupon.utils import get_default_logger, get_es, should_item_be_enabled, save_deal_item
from scrapy.utils.project import get_project_settings

logger = get_default_logger("dealfu_groupon.cli.deal_checker")


@cli.app.CommandLineApp
def deal_enabler(app):
    """
    Checks all deals and enables those which are ok
    """
    settings = get_project_settings()

    #query to get all of the disabled

    per_page = 100
    es = get_es(settings)
    from_page = 0

    results = _es_get_batch(settings, es, from_page, per_page)


    while results:
        for r in results:
            item = r["_source"]
            item_id = r["_id"]

            if should_item_be_enabled(item):
                logger.debug("Enabled item : {}".format(item_id))

                item["enabled"] = True
                save_deal_item(settings, item_id,
                               item, es_conn=es, update=True)

        #now that batch is processed get a new one
        from_page += per_page
        results = _es_get_batch(settings, es, from_page, per_page)
        logger.info("Getting next batch : {}".format(from_page))

    logger.info("Finished deal enabler !!!")

    return True


def _es_get_batch(settings, es, from_pg, per_page):
    """
    Gets a batch
    """
    query = {
        "from": 0,
        "size":100,
        "query": {
            "filtered": {"query": {"match_all": {}
            },
         "filter": {
             "bool": {
                 "must": [
                    {"term": {
                       "enabled": False
                    }}
                 ]
             }
         }
    }}}

    query["from"] = from_pg
    query["size"] = per_page

    result = es.search(index=settings["ES_INDEX"],
                       doc_type=settings["ES_INDEX_TYPE_DEALS"],
                       body=query)

    total = result["hits"]["total"]
    if total == 0:
        return []

    return result["hits"]["hits"]


if __name__ == "__main__":
    deal_enabler.run()