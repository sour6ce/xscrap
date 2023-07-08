from queue import Queue
from common.environment import *
from common.printing import *
from Pyro5.api import Daemon, behavior, expose
from sortedcontainers import SortedSet

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

    def is_pending(self, url: str) -> bool:
        return self.pending_set.__contains__(url)

    def insert_to_pending_set(self, url: str):
        self.pending_set.add(url)

    def push_to_pending_queue(self, url: str):
        self.pending_queue.put(url)

    def remove_from_cache(self, url: str):
        if self.url_cache.__contains__(url):
            self.url_cache.pop(url)

    def cached_response(self, url: str) -> (str | None):
        if self.url_cache.__contains__(url):
            return self.url_cache.get(url)
        return None

    def pending_size(self) -> int:
        return self.pending_queue._qsize()

    def retrieve_from_pending_queue(self) -> str:
        return self.pending_queue.get()

    def remove_from_pending_set(self, url: str):
        if self.pending_set.__contains__(url):
            self.pending_set.discard(url)

    def update_cache(self, url: str, body: str):
        self.url_cache[url] = body

    def try_push_to_pending_queue(self, url: str):
        if self.is_pending(url):
            return
        if self.pending_size() >= resolve_pending_queue_maxsize():
            log(f"Pending queue full, job {url} not queued.")
            raise ValueError("Pending queue full")
        self.insert_to_pending_set(url)
        self.push_to_pending_queue(url)

    def yield_pending_url(self) -> str:
        try:
            url = self.retrieve_from_pending_queue()
        except:
            log(f"Not enough jobs available for a request.")
            raise ValueError("Not enough jobs in queue")
        self.remove_from_pending_set(url)
        return url
