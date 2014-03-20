"""
The general pipe that is base for all spiders
"""
from dealfu_groupon.utils import check_spider_pipeline


class BaseEsPipe(object):

    @check_spider_pipeline
    def process_item(self, item, spider):
        return item




