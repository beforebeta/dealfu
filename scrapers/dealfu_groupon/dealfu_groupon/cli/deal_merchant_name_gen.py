import traceback

import cli.app

from dealfu_groupon.utils import get_default_logger, get_es, save_deal_item, es_get_batch, \
    get_in, from_url_to_name

from scrapy.utils.project import get_project_settings

logger = get_default_logger("dealfu_groupon.cli.deal_merchant_name_gen")


@cli.app.CommandLineApp
def deal_merchant_generator(app):
    """
    That function simply gets the merchants that don't have
    merchant name and generates one for them
    """
    settings = get_project_settings()

    query = {
        "from": 0,
        "size":100,
        "query":
        {"filtered":
            {"query": {
                "match_all": {}
            },
            "filter": {
                 "bool": {
                     "must": [
                        {"term": {
                           "enabled": False
                        }},
                        {
                            "missing": {
                               "field": "merchant.name"
                            }
                        },
                        {
                            "exists": {
                            "field": "merchant.url"
                            }
                        }
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

            try:
                url = get_in(item, "merchant", "url")
                if not url:
                    logger.warn("Skipping item : {} no merchant.url".format(item_id))
                    continue

                name = from_url_to_name(url)
                if not name:
                    continue


                logger.info("Setting name to : {} from {} of {}".format(name,
                                                                        url,
                                                                        item_id))

                item["merchant"]["name"] = name
                save_deal_item(settings, item_id,
                               item, es_conn=es, update=True)

            except Exception,ex:
                logger.error("Error when generating merchant name for ".format(item_id,
                                                                           traceback.format_exc()))
                continue


        #now that batch is processed get a new one
        from_page += per_page
        results = es_get_batch(settings, es, from_page, per_page, query=query)
        logger.info("Getting next batch : {}".format(from_page))

    logger.info("Finished merchant name generator !!!")

    return True


if __name__ == "__main__":
    deal_merchant_generator.run()