import cli.app

from dealfu_groupon.utils import get_default_logger, get_es, should_item_be_enabled, save_deal_item, es_get_batch
from scrapy.utils.project import get_project_settings

logger = get_default_logger("dealfu_groupon.cli.deal_checker")


@cli.app.CommandLineApp
def deal_enabler(app):
    """
    Checks all deals and enables those which are ok
    """
    settings = get_project_settings()

    #query to get all of the disabled
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

    per_page = 100
    es = get_es(settings)
    from_page = 0

    results = es_get_batch(settings, es, from_page, per_page, query=query)


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
        results = es_get_batch(settings, es, from_page, per_page, query=query)
        logger.info("Getting next batch : {}".format(from_page))

    logger.info("Finished deal enabler !!!")

    return True



if __name__ == "__main__":
    deal_enabler.run()