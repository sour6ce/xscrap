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

@expose
@behavior(instance_mode="single")
class Cache(object):
    def __init__(self, daemon: Daemon):
        '''
        Constructor for the object, isn't called at start of the dispatcher node,
        instead the object is created when a node is needed of the Pyro object.
        '''
        self.daemon = daemon
        self.pending_set: set = set()
        self.pending_queue: Queue = Queue()
        self.url_cache: dict = dict()
    
    def ps_ismember(self, url: str) -> bool:
        return self.pending_set.__contains__(url)
    
    def ps_add(self, url: str):
        self.pending_set.add(url)
    
    def p_push(self, url: str):
        self.pending_queue.put(url)
    
    def uc_delete(self, url: str):
        if self.url_cache.__contains__(url):
            self.url_cache.pop(url)
    
    def uc_get(self, url: str) -> (str | None):
        if self.url_cache.__contains__(url):
            return self.url_cache.get(url)
        return None
    
    def p_llen(self) -> int:
        return self.pending_queue._qsize()
    
    def p_lpop(self) -> str:
        return self.pending_queue.get(False)
    
    def ps_srem(self, url: str):
        if self.pending_set.__contains__(url):
            self.pending_set.discard(url)
    
    def uc_set(self, url: str, body: str):
        self.url_cache[url] = body
    