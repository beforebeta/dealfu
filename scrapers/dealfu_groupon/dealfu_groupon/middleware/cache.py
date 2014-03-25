"""
Simple module that will cache pages for offline access
"""

class CacheDealPolicy(object):

    def __init__(self, settings):
        self.ignore_http_codes = [int(x) for x in settings.getlist('HTTPCACHE_IGNORE_HTTP_CODES')]

    def should_cache_request(self, request):
        return request.meta.get("cache_me") is True


    def should_cache_response(self, response, request):
        return request.meta.get("cache_me") is True and response.status not in self.ignore_http_codes

    def is_cached_response_fresh(self, response, request):
        return True

    def is_cached_response_valid(self, cachedresponse, response, request):
        return True
