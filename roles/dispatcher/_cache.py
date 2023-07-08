import asyncio
from queue import Queue
import time
from typing import Any, List

from common.environment import *
from common.job import Job
from common.printing import *
from Pyro5.api import Daemon, Proxy, behavior, current_context, expose
from Pyro5.errors import CommunicationError, NamingError
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

@expose
@behavior(instance_mode="single")
class Cache(object):
    def __init__(self, daemon: Daemon):
        '''
        Constructor for the object, isn't called at start of the dispatcher node,
        instead the object is created when a node is needed of the Pyro object.
        '''
        self.daemon = daemon
        self.pending_set: set
        self.pending_queue: Queue
        self.url_cache: dict
    
    def ps_ismember(self, url: str) -> bool:
        return self.pending_set.__contains__(url)
    
    def ps_add(self, url: str):
        self.pending_set.add(url)
    
    def p_push(self, url: str):
        self.pending_queue.put(url)
    
    def uc_delete(self, url: str):
        self.url_cache.pop(url)
    
    def uc_get(self, url: str) -> (str | None):
        if self.url_cache.__contains__(url):
            return self.url_cache.get(url)
        return None
    
    def p_llen(self) -> int:
        return self.pending_queue._qsize()
    
    def p_lpop(self) -> str:
        return self.pending_queue.get()
    
    def ps_srem(self, url: str):
        self.pending_set.discard(url)
    
    def uc_set(self, url: str, body: str):
        self.url_cache[url] = body
    