import cli.app
from dealfu_groupon.background.geocode import submit_geo_request
from dealfu_groupon.utils import get_es, es_get_batch, get_default_logger, needs_geo_fetch, needs_address_geo_fetch
from scrapy.utils.project import get_project_settings

logger = get_default_logger("dealfu_groupon.cli.deal_checker")


@cli.app.CommandLineApp
def submit_geo_request_addresses(app):
    """
    That application will get the addresses
    that don't have geo location info and submit
    them to be collected
    """
    settings = get_project_settings()

    query = {   "from": 0,
        "size":100,
        "query":
        {
            "filtered":
                {"query": {
                    "match_all": {}
                },
            "filter": {
                 "bool": {
                     "must": [
                        {"term": {
                           "enabled": False
                        }},
                        {"exists": {
                            "field": "merchant.addresses.address"
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

            if not needs_geo_fetch(item, item_id=item_id, logger=logger):
                #logger.warn("The item {} have blanks in address but is not sent for geofetch".format(item_id))
                continue

            for addr in item.get("addresses", []):
                if needs_address_geo_fetch(addr):
                    logger.debug("Submit geo {} for addr : {}".format(item_id, addr))
                    submit_geo_request.delay(settings, item_id)

        #now that batch is processed get a new one
        from_page += per_page
        results = es_get_batch(settings, es, from_page, per_page, query=query)
        logger.info("Getting next batch : {}".format(from_page))


    logger.info("Finished deal enabler !!!")


if __name__ == "__main__":
    submit_geo_request_addresses.run()

