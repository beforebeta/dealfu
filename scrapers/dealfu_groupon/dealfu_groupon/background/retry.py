from dealfu_groupon.background.geocode import push_to_geo_queue
from dealfu_groupon.utils import needs_geo_fetch, is_item_in_geo_queue, needs_address_geo_fetch, get_redis
import requests
import traceback

from scrapy.exceptions import DropItem
from scrapy.http.response.html import HtmlResponse

from dealfu_groupon.background.celery import app
from dealfu_groupon.pipelines.retrypipe import RetryPipeLine


try:
    #sometimes fails inside the tests
    from celery.utils.log import get_task_logger
    logger = get_task_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)



@app.task
def retry_document(settings, redis_key, doc):
    """
    This task will generally enqueue the given url
    and document _id again to be scrapped on scrapy
    """
    #before we go further we may want to check if we should try ?
    from dealfu_groupon.spiders.groupon import GrouponSpider

    pipe = RetryPipeLine(settings, redis_key, doc["id"], logger)
    retry_dict = pipe.get_retry_dict()
    redis_conn = get_redis(settings)

    #first fetch the item from groupon
    resp = None
    try:
        result = requests.get(doc["untracked_url"])
        resp = HtmlResponse(url=doc["untracked_url"], body=result.content)
    except Exception,ex:
        logger.error("Error when fetching url : {}".format(traceback.format_exc()))
        return pipe.fail_or_retry(retry_dict, doc)

    spider = GrouponSpider()
    item = spider.parse_deal(resp)
    item["id"] = doc["id"]

    #try processing it
    try:
        result = pipe.process_item(item)
        if not result:
            #retry or finish
            return pipe.fail_or_retry(retry_dict, doc)
        else:
            # we are done we should
            # update the item here !
            pipe.update_item_finish(result, retry_dict)
            #check if it need a geo encoding
            #because sometimes the address info appears after retry
            #process and we should refetch the address
            add_if_to_geo_request(redis_conn,
                                  settings,
                                  result,
                                  item["id"],
                                  logger)
            return "FINISHED SUCCESS"
    except DropItem, ex:
        logger.error("Invalid item can not be retried : {}".format(traceback.format_exc()))
        pipe.mark_failed(retry_dict)
        return "FAILED"
    except Exception,ex:
        logger.error("There was some error when retrying {}: {}".format(
            doc["id"], traceback.format_exc()))
        return pipe.fail_or_retry(retry_dict, doc)


    return "FAILED NOWHERE !"


def add_if_to_geo_request(redis_conn, settings,item, item_id, logger):
    """
    Adds item into geo request queue if legitime to be gathered
    """
    if not needs_geo_fetch(item, item_id=item_id, logger=logger):
        return False

    #check here if it is the geo list for fetching, if yes no need
    #to resubmit it again
    redis_key = settings.get("REDIS_GEO_POLL_LIST")
    if is_item_in_geo_queue(redis_conn, redis_key, item_id):
        logger.info("Item already in geo queue no need for re-fetch")
        return False

    #submit to celery to be processed!
    for address in item.get("addresses", []):
        if needs_address_geo_fetch(address):
            push_to_geo_queue(redis_conn, redis_key, address, item_id)
            logger.info("Item submitted to be geo-fetched : {0} on retry queue".format(address))

    return True
