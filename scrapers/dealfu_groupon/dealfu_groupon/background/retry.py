from twisted.internet import reactor

from scrapy.crawler import Crawler
from scrapy import log, signals
from scrapy.utils.project import get_project_settings


def retry_document(settings, redis_key, doc):
    """
    This task will generally enqueue the given url
    and document _id again to be scrapped on scrapy
    """
    #before we go further we may want to check if we should try ?
    from dealfu_groupon.spiders.groupon import GrouponSpider

    spider = GrouponSpider(only_one_deal=True,
                           pipeline=["dealfu_groupon.pipelines.retrypipe.RetryPipeLine"],
                           one_url=doc.get("untracked_url"),
                           doc_id=doc.get("id"))

    settings = get_project_settings()
    crawler = Crawler(settings)
    crawler.signals.connect(reactor.stop, signal=signals.spider_closed)
    crawler.configure()
    crawler.crawl(spider)
    crawler.start()
    log.start(logstdout=False)
    reactor.run() # the script will block here until the spider_closed signal was sent

    #check the status on redis
    #and if the items is retried successfully
    #then don't reschedule it again !

    return "FINISHED !"
