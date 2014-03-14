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


