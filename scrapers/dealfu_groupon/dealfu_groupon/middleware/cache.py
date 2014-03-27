"""
Simple module that will cache pages for offline access
"""
import os
from time import time
import cPickle as pickle
import base64

from w3lib.http import headers_raw_to_dict, headers_dict_to_raw

from scrapy.utils.project import data_path
from scrapy.http import Headers
from scrapy.responsetypes import responsetypes


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


class DealFilesystemCacheStorage(object):

    def __init__(self, settings):
        self.cachedir = data_path(settings['HTTPCACHE_DIR'])

    def open_spider(self, spider):
        pass

    def close_spider(self, spider):
        pass

    def retrieve_response(self, spider, request):
        """Return response if present in cache, or None otherwise."""
        metadata = self._read_meta(spider, request)
        if metadata is None:
            return  # not cached
        rpath = self._get_request_path(spider, request)
        with open(os.path.join(rpath, 'response_body'), 'rb') as f:
            body = f.read()
        with open(os.path.join(rpath, 'response_headers'), 'rb') as f:
            rawheaders = f.read()
        url = metadata.get('response_url')
        status = metadata['status']
        headers = Headers(headers_raw_to_dict(rawheaders))
        respcls = responsetypes.from_args(headers=headers, url=url)
        response = respcls(url=url, headers=headers, status=status, body=body)
        return response

    def store_response(self, spider, request, response):
        """Store the given response in the cache."""
        rpath = self._get_request_path(spider, request)
        if not os.path.exists(rpath):
            os.makedirs(rpath)
        metadata = {
            'url': request.url,
            'method': request.method,
            'status': response.status,
            'response_url': response.url,
            'timestamp': time(),
        }
        with open(os.path.join(rpath, 'meta'), 'wb') as f:
            f.write(repr(metadata))
        with open(os.path.join(rpath, 'pickled_meta'), 'wb') as f:
            pickle.dump(metadata, f, protocol=2)
        with open(os.path.join(rpath, 'response_headers'), 'wb') as f:
            f.write(headers_dict_to_raw(response.headers))
        with open(os.path.join(rpath, 'response_body'), 'wb') as f:
            f.write(response.body)
        with open(os.path.join(rpath, 'request_headers'), 'wb') as f:
            f.write(headers_dict_to_raw(request.headers))
        with open(os.path.join(rpath, 'request_body'), 'wb') as f:
            f.write(request.body)

    def _get_request_path(self, spider, request):
        key = base64.urlsafe_b64encode(request.url)
        return os.path.join(self.cachedir, spider.name, key[0:2], key)

    def _read_meta(self, spider, request):
        rpath = self._get_request_path(spider, request)
        metapath = os.path.join(rpath, 'pickled_meta')
        if not os.path.exists(metapath):
            return  # not found

        with open(metapath, 'rb') as f:
            return pickle.load(f)

