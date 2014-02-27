from twisted.internet import reactor

from scrapy.crawler import Crawler
from scrapy import log, signals
from scrapy.utils.project import get_project_settings

from dealfu_groupon.spiders.groupon import GrouponSpider

def retry_document(doc_id, doc_url):
    """
    This task will generally enqueue the given url
    and document _id again to be scrapped on scrapy
    """
    spider = GrouponSpider(only_one_deal=True,
                           pipeline=["dealfu_groupon.pipelines.retrypipe.RetryPipeLine"],
                           one_url=doc_url,
                           doc_id=doc_id)

    settings = get_project_settings()
    crawler = Crawler(settings)
    crawler.signals.connect(reactor.stop, signal=signals.spider_closed)
    crawler.configure()
    crawler.crawl(spider)
    crawler.start()
    log.start(logstdout=False)
    reactor.run() # the script will block here until the spider_closed signal was sent
    return "FINISHED !"
