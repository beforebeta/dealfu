BOT_NAME = 'dealfu_groupon'

SPIDER_MODULES = ['dealfu_groupon.spiders']
NEWSPIDER_MODULE = 'dealfu_groupon.spiders'

ITEM_PIPELINES = {
    "dealfu_groupon.pipelines.genespipe.BaseEsPipe":200,
    "dealfu_groupon.pipelines.espipe.EsPipeLine":300,
    "dealfu_groupon.pipelines.catpipe.CatPipeLine":400
}


#DISABLE THE WEB AND TELNET FOR NOW
WEBSERVICE_ENABLED = False
TELNETCONSOLE_ENABLED = False

# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'dealfu_groupon (+http://www.yourdomain.com)'
DOWNLOAD_DELAY = 0.25    # 250? ms of delay

#ES index information
ES_INDEX = "dealfu"
ES_INDEX_TYPE_DEALS = "deal"
ES_INDEX_TYPE_CATEGORY = "category"

#ES_SETTINGS
ES_SERVER = "127.0.0.1"
ES_PORT = "9200"

#REDIS QUEUE PARAMETERS
REDIS_HOST = "127.0.0.1"

REDIS_DEFAULT_QUEUE = "default"
REDIS_PORT = 6379
REDIS_RETRY_PREFIX = "scrapy:retry:%s"
REDIS_RETRY_COUNT = 4
REDIS_RETRY_DELAY = 5*60 #seconds to wait after we start retrying
REDIS_RETRY_STATUS_READY = "READY"
REDIS_RETRY_STATUS_FINISHED = "FINISHED"
REDIS_RETRY_STATUS_FAILED = "FAILED"

#REDIS GEO SETTINGS
REDIS_GEO_CACHE_KEY = "scrapy:geo:cache:%s" #pattern for cached values so far !
REDIS_GEO_POLL_LIST = "scrapy:geo:queue" # alist with items to pull
REDIS_GEO_REQUEST_LOG = "scrapy:geo:requests"

#GOOGLE GEOCODING SETTINGS
GOOGLE_GEO_API_KEY = "fake"
GOOGLE_GEO_API_ENDPOINT = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_GEO_REQUESTS_PER_DAY = 2500
GOOGLE_GEO_REQUESTS_PERIOD = 24*60*60
GOOGLE_GEO_DEFAULT_DELAY = GOOGLE_GEO_REQUESTS_PERIOD / GOOGLE_GEO_REQUESTS_PER_DAY
