"""
When you just need to test something without saving that
is the pipe you should use !
"""

from dealfu_groupon.utils import check_spider_pipeline


class EmptyPipe(object):

    @check_spider_pipeline
    def process_item(self, item, spider):
        return item




