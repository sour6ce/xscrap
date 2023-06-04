import asyncio
import queue
import time
from typing import Any, List

import redis
from common.environment import *
from common.job import Job
from common.printing import *
from Pyro5.api import behavior, expose, current_context
from typing_extensions import overload

###############################################################################
#                                                                             #
# There are two major data stored in redis server: Pending and Cache
# NOTE: Is possible in the future to separate this in two redis servers
#
# Pending is a list that works as a queue of URLs that needs to be worked
#
# Cache works as a result storage of all the URLs worked. While an url is at
# cache is assumed to be "worked" and can be returned to client.
#
# Due to nature of results it is recommended to use random key eviction in
# to help forcing a cached page to be fetched again sometimes.
#                                                                             #
###############################################################################
PENDING_KEY = 'pending'
CACHE_KEY_PREFIX = 'cache'


def build_cache_key(url, prefix=CACHE_KEY_PREFIX):
    return f'{prefix}:{url}'


@expose
@behavior(instance_mode="single")
class Dispatcher(object):
    def __init__(self):
        '''
        Constructor for the object, isn't called at start of the dispatcher node,
        instead the object is created when a node is needed of the Pyro object.

        Here he checks for the first time if the redis server is up.
        '''
        print("Checking connection to redis server\n")
        self.r_server = redis.from_url(resolve_redis(), decode_responses=True)
        self.check_redis()
        print(
            "Dispatched initialized for first time successfully.\n\n",
            style="c_good")

    def check_redis(self):
        '''Check if there is connection to the redis server.'''
        try:
            if not self.r_server.ping():
                raise redis.ConnectionError(
                    "Connection to redis server failed.")
        except Exception as e:
            print(
                f'Encounter ERROR: {e} Trying again in {10.0:.2f} seconds.')
            time.sleep(10.0)

    def _send_pending(self, *url: str):
        '''
        Sends a bunch of urls to pending to fetch. This forces them to be fetched no matter
        if there is already a result stored in cache.
        '''
        # Lock forces to allow only this method to change values in that key
        with self.r_server.lock(PENDING_KEY+"_lock_", thread_local=False):
            self.r_server.rpush(PENDING_KEY, *url)

    def _clear_cache_single(self, url: str):
        '''Delete the cache result for a given url.'''
        url_key = build_cache_key(url)

        with self.r_server.lock(url_key+"_lock_", thread_local=False):
            self.r_server.delete(url_key)

    def _clear_cache(self, urls: List[str]):
        '''Delete the cache result for a list of urls.'''
        _ = [self._clear_cache_single(url) for url in urls]

    def _retrieve_cache_single(self, url: str) -> dict | None:
        '''Retrieve result stored for a given url. If there's no cache for that url return None.'''
        result = self.r_server.get(build_cache_key(url))
        return result if result is None else eval(result)

    def _retrieve_cache(self, urls: List[str]) -> List[dict | None]:
        '''Retrieve results stored for all given urls. If there's no cache for an url return None.'''
        return [self._retrieve_cache_single(url) for url in urls]

    def put_work(self, urls: List[str]):
        sep = "\n\t"
        log(f'Arrived batch job: \n[\n\t{sep.join(urls)}\n]')

        # Sadly independent but not parallel
        self._send_pending(*urls)
        self._clear_cache(urls)

    def get_work(self, count: int = 1) -> List[str]:
        log(f'Request for a job.')

        if self.r_server.llen(PENDING_KEY) == 0:
            log(f"No jobs available for a request.")
            raise ValueError("No jobs in queue")
        if self.r_server.llen(PENDING_KEY) < count:
            log(f"Not enough jobs available for a request.")
            raise ValueError("Not enough jobs in queue")

        url: str = ''

        with self.r_server.lock(PENDING_KEY+"_lock_", thread_local=False):
            url = self.r_server.lpop(PENDING_KEY)

        log(f'Job given: {url}.')

        return [url] if isinstance(url, str) else url

    def put_result(self, url: str, body: str, status_code: int = 200):
        log(f'Arrived result for job: {url} with status {status_code}')
        self.r_server.set(
            build_cache_key(url),
            repr({'body': body, 'status': 200}))

    def get_result(self, urls: List[str]) -> List[dict | None]:
        sep = "\n\t"
        log(f'Request for results on: \n[\n\t{sep.join(urls)}\n]')
        r = (self._retrieve_cache(urls))

        pending_urls = [url for res, url in zip(r, urls) if res is None]

        (self.put_work(pending_urls))

        return r

    def pending_size(self):
        return self.r_server.llen(PENDING_KEY)

    def cache_size(self):
        return self.r_server.dbsize()-1
