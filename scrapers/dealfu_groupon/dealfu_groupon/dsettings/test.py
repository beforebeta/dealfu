from dealfu_groupon.dsettings.base import *

#ES_SETTINGS
ES_SERVER = "192.168.0.113"
ES_PORT = "9200"

#ES index information
ES_INDEX = "test_dealfu"
ES_INDEX_TYPE_DEALS = "deal"
ES_INDEX_TYPE_CATEGORY = "category"

#REDIS QUEUE PARAMETERS
REDIS_DEFAULT_DB = 1
REDIS_DEFAULT_QUEUE = "default_test"
REDIS_HOST = "192.168.0.113"

#GOOGLE GEOCODING SETTINGS
GOOGLE_GEO_API_KEY = "fake_test"
