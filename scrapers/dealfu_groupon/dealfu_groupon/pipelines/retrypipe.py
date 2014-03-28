import datetime
import traceback
import logging

#for page that require JS
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException

from elasticsearch.exceptions import TransportError
from scrapy.exceptions import DropItem

from redis import Redis

from dealfu_groupon.utils import get_es, merge_dict_items, needs_retry, clean_float_values, save_deal_item, \
    needs_price_retry


class RetryPipeLine(object):
    """
    Retry pipeline checks for specific item if current
    parsed version is better than the one in database
    if not it re-schedules it again to be checked later
    """

    def __init__(self, settings, retry_key, item_id,logger):
        """
        Init the pipeline
        """
        self.settings = settings
        self.es = get_es(self.settings)
        self.redis_conn = Redis(host=self.settings.get("REDIS_HOST"),
                                port=self.settings.get("REDIS_PORT"))
        self.logger = logger
        self.item_id = item_id
        self.retry_key = retry_key


    def exists(self):
        if not self.redis_conn.exists(self.retry_key):
            return False

        return True

    def get_retry_dict(self):
        """
        fetch the retry dict
        """
        retry_dict = self.redis_conn.hgetall(self.retry_key)
        return retry_dict

    def get_item(self):
        """
        Returns back a fresh copy of the item
        """
        try:
            result = self.es.get(index=self.settings.get("ES_INDEX"),
                        doc_type=self.settings.get("ES_INDEX_TYPE_DEALS"),
                        id=self.item_id)['_source']

            return result

        except TransportError,ex:
            raise DropItem("Non existing item : %s "%self.item_id)


    def process_item(self, item):
        """
        Retry specified the specified item if there is a DropItem then
        means it failed, so don't try again, otherwise if returns
        False that means we should give it try, otherwise it is finished
        """
        self.logger.info("RETRY ITEM : %s "%item["id"])
        #self.logger.info("RETRY_DETAIL : %s"%json.dumps(dict(item)))

        if not self.exists():
            raise DropItem("Non existing key, supplied (deleted ?) {}".format(self.retry_key))


        result = self.get_item() #that is a fresh copy of item
        merged_item = merge_dict_items(result, item) #merge them

        if not needs_retry(merged_item):
            #mark item as finished so the other end can finish that
            return merged_item
        else:
            #decrase the retry count so other part can know if it failed
            if self._needs_selenium_fetch(merged_item):
                price_info = _get_price_info_selenium(item["untracked_url"],
                                                      settings=self.settings)
                if price_info:
                    merged_item = merge_dict_items(merged_item, price_info)
                    if not needs_retry(merged_item):
                        return merged_item

        return False


    def update_item_finish(self, item, retry_dict):
        """
        Save the item and mark it finished
        """
        save_deal_item(self.settings,
                       self.item_id,
                       item,
                       es_conn=self.es)

        return self.set_item_finished(retry_dict)

    def set_item_finished(self, retry_dict):
        """
        Marks the item as finished aka SUCCESSFUL
        """
        retry_dict["status"] = self.settings.get("REDIS_RETRY_STATUS_FINISHED")
        self.redis_conn.hmset(self.retry_key, retry_dict)
        return True


    def _needs_selenium_fetch(self, item):
        """
        Checks if supplied item needs to be fetched via selenium
        """
        return needs_price_retry(item)


    def decrease_retry_count(self, retry_dict):
        """
        Decreases the retry count
        """
        retry_count = int(retry_dict["retry_count"])
        retry_count -= 1

        if retry_count <= 0:
            retry_dict["status"] = self.settings.get("REDIS_RETRY_STATUS_FAILED")

        retry_dict["retry_count"] = retry_count
        #set the final structure
        self.redis_conn.hmset(self.retry_key, retry_dict)

        return retry_count


    def mark_failed(self, retry_dict):
        """
        Mark item as failed
        """
        retry_dict["status"] = self.settings.get("REDIS_RETRY_STATUS_FAILED")
        self.redis_conn.hmset(self.retry_key, retry_dict)
        return True


    def fail_or_retry(self, retry_dict, doc):
        from dealfu_groupon.background.retry import retry_document

        rcount = self.decrease_retry_count(retry_dict)
        if rcount == 0:
            if  retry_dict["status"] == self.settings["REDIS_RETRY_STATUS_FAILED"]:
                return "FAILED"
            if  retry_dict["status"] == self.settings["REDIS_RETRY_STATUS_FINISHED"]:
                return "SUCCESS"

        #apply it again
        eta = datetime.datetime.utcnow() + datetime.timedelta(seconds=self.settings.get("REDIS_RETRY_DELAY"))
        retry_document.apply_async(args=[self.settings,
                                         self.retry_key,
                                         doc],
                               eta=eta)

        return "RETRY AGAIN %d"%rcount



def _get_price_info_selenium(url, settings=None, logger=None):
    """
    CAUTION that will block the whole process !!!
    But it is ok since that is a background process!
    """

    if not logger:
        logger = logging.getLogger()

    d = {}
    d["commission"] = 0

    phantom_port = settings.get("PHANTMOJS_PORT", 10002)if settings else 10002

    driver = webdriver.PhantomJS(port=phantom_port)
    try:
        driver.get(url)
    except Exception,ex:
        logger.error("Error when getting page with Phantom : {}".format(traceback.format_exc()))
        driver.quit()
        return d


    try:
        price_el = driver.find_element_by_xpath('//div[@id="purchase-cluster"]//div[@class="from-minimum"]')
        val_el = driver.find_element_by_xpath('//div[@id="purchase-cluster"]//div[@class="market-minimum"]')

        price_txt = price_el.text
        val_txt = val_el.text

        d["price"] = clean_float_values(price_txt, "$", ",")
        d["value"] = clean_float_values(val_txt, "$", ",")

        if not d["value"] or not d["price"]:
            return d

        d["discount_amount"] = d["value"] - d["price"]

        discount_percentage = d["discount_amount"] / d["value"]
        discount_percentage = float("%.2f"%discount_percentage)
        d["discount_percentage"] = discount_percentage


    except NoSuchElementException, ex:
        logger.error("Error when parisng page with Phantom : {}".format(traceback.format_exc()))
    finally:
        driver.quit()

    return d
