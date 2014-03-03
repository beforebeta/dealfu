# Scrapy settings for dealfu_groupon project
#
# For simplicity, this file contains only the most important settings by
# default. All the other settings are documented here:
#
#     http://doc.scrapy.org/en/latest/topics/settings.html
#

BOT_NAME = 'dealfu_groupon'

SPIDER_MODULES = ['dealfu_groupon.spiders']
NEWSPIDER_MODULE = 'dealfu_groupon.spiders'

ITEM_PIPELINES = {
    "dealfu_groupon.pipelines.espipe.EsPipeLine":300,
    "dealfu_groupon.pipelines.catpipe.CatPipeLine":400,
    "dealfu_groupon.pipelines.retrypipe.RetryPipeLine":500
}


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'dealfu_groupon (+http://www.yourdomain.com)'
DOWNLOAD_DELAY = 0.25    # 250? ms of delay

#ES_SETTINGS
ES_SERVER = "192.168.0.113"
ES_PORT = "9200"

#ES index information
ES_INDEX = "dealfu"
ES_INDEX_TYPE_DEALS = "deal"
ES_INDEX_TYPE_CATEGORY = "category"

#REDIS QUEUE PARAMETERS
REDIS_DEFAULT_QUEUE = "default"
REDIS_HOST = "192.168.0.113"
REDIS_PORT = 6379
REDIS_RETRY_PREFIX = "scrapy:retry:%s"
REDIS_RETRY_COUNT = 4
REDIS_RETRY_DELAY = 20 #seconds to wait after we start retrying
REDIS_RETRY_STATUS_READY = "READY"
REDIS_RETRY_STATUS_FINISHED = "FINISHED"
REDIS_RETRY_STATUS_FAILED = "FAILED"
