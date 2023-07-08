import asyncio
from subprocess import Popen
import sys
import queue
import time
from typing import Any, Dict, List

from datetime import datetime, timedelta

import redis
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
PENDING_KEY = 'pending'
CACHE_KEY_PREFIX = 'cache'
PENDING_SET_KEY = 'pending_set'

def build_cache_key(url, prefix=CACHE_KEY_PREFIX):
    return f'{prefix}:{url}'

@expose
@behavior(instance_mode="single")
class Dispatcher(object):
    def __init__(self, daemon: Daemon):
        '''
        Constructor for the object, isn't called at start of the dispatcher node,
        instead the object is created when a node is needed of the Pyro object.

        Here he checks for the first time if the redis server is up.
        '''
        self.daemon = daemon
        
        self.__spawning=False
        
        self.worker_timestamps:Dict[str,datetime] = {}
        self.spawned_workers:Dict[str,Popen] = {}
        self.worker_timeout = timedelta(seconds=resolve_workertiemout())
        
        self.check_redis()
        print(
            "Dispatched initialized for first time successfully.\n\n",
            style="c_good")

    def check_redis(self):
        '''Check if there is connection to the redis server.'''
        print("Checking connection to redis server.\n")
        print(f"URL:{resolve_redis()}\n")
        connection_attempts = resolve_mbb_retries()
        connection_sleep = resolve_mbb_time()

        # Checking if dispatcher is up
        retries_count = 0
        # Note that when connection_attempts is set to 0, it tries to connect indefinitely
        while connection_attempts == 0 or retries_count < connection_attempts:
            try:
                self.r_server = redis.from_url(
                    resolve_redis(),
                    decode_responses=True)
                if not self.r_server.ping():
                    raise redis.exceptions.ConnectionError(
                        "Connection to redis server failed.")
                print(f"Connected to redis server.\n", style="c_good")
                return
            except redis.exceptions.ConnectionError as e:
                error('Redis server not reachable.\n')
                time.sleep(connection_sleep)
        back = resolve_backup_redis()
        if back is None:
            error(
                f'Did not manage to connect to redis server after {connection_attempts} tries. Exiting the application.\n')
            self.daemon.shutdown()
            exit(1)
        else:
            error(
                f'Did not manage to connect to redis server after {connection_attempts} tries. Trying to connect to backup dispatcher.\n')
            try:
                print(f"URL:{resolve_backup_redis()}\n")
                self.r_server = redis.from_url(back, decode_responses=True)
                if not self.r_server.ping():
                    raise redis.exceptions.ConnectionError(
                        "Connection to backup redis server failed.")
                print(f"Connected to backup redis server.\n", style="c_good")
                return
            except redis.exceptions.ConnectionError as e:
                error(f"Backup redis server unreachable.\n")
                self.daemon.shutdown()
                exit(1)

    def _send_pending(self, url: List[str]):
        '''
        Sends a bunch of urls to pending to fetch. This forces them to be fetched no matter
        if there is already a result stored in cache.
        '''
        if len(url) == 0:
            return
        # Lock forces to allow only this method to change values in that key
        for urlx in url:
            try:
                with self.r_server.lock(PENDING_SET_KEY+"_lock_", thread_local=False):
                    if self.r_server.sismember(PENDING_SET_KEY, urlx):
                        return
                    self.r_server.sadd(PENDING_SET_KEY, urlx)
            except redis.exceptions.ConnectionError:
                error('Redis server unavaliable.\n')
                self.check_redis()
            try:
                with self.r_server.lock(PENDING_KEY+"_lock_", thread_local=False):
                    self.r_server.rpush(PENDING_KEY, urlx)
            except redis.exceptions.ConnectionError:
                error('Redis server unavaliable.\n')
                self.check_redis()

    def _clear_cache_single(self, url: str):
        '''Delete the cache result for a given url.'''
        url_key = build_cache_key(url)
        try:
            with self.r_server.lock(url_key+"_lock_", thread_local=False):
                self.r_server.delete(url_key)
        except redis.exceptions.ConnectionError:
            error('Redis server unavaliable.\n')
            self.check_redis()

    def clear_cache(self, urls: List[str]):
        '''Delete the cache result for a list of urls.'''
        _ = [self._clear_cache_single(url) for url in urls]

    #Function added
    def _update_worker_timestamp(self, worker_id):
        self.worker_timestamps[worker_id] = datetime.now()
    
    #Function added
    def _check_workers(self):
        now = datetime.now()
        dead_workers = [worker for worker, timestamp in self.worker_timestamps.items() if now - timestamp > self.worker_timeout]

        for worker in dead_workers:
            del self.worker_timestamps[worker]

        if len(self.worker_timestamps) < resolve_worker_amount():
            error("Poor worker count.\n")
            self._spawn_new_workers(resolve_worker_amount() - len(self.worker_timestamps))
            
        if len(self.worker_timestamps) > resolve_worker_amount()*2:
            excessive_count=(len(self.worker_timestamps)-resolve_worker_amount())
            
            for _ in range(max(len(self.spawned_workers),excessive_count)):
                worker_id,process=self.spawned_workers.popitem()
                process.kill()
                
                log(f"Despawned worker: {worker_id}")
    
    #Function added
    def _spawn_new_workers(self, num_workers):
        if not self.__spawning:
            self.__spawning=True
            log("Spawning new workers...")
            for _ in range(num_workers):
                c_env=os.environ
                c_env.update({'DISPATCHER_PORT':str(resolve_hostport())})
                p = Popen([sys.executable,os.path.abspath(sys.argv[0]),"worker"], env=c_env)
                
                new_worker_name=f"Worker_{p.pid}@{socket.gethostname()}"
                self.worker_timestamps[new_worker_name]=datetime.now()
                
                self.spawned_workers[new_worker_name]=p
                log(f"Spawned worker: {new_worker_name}")
            self.__spawning=False
                
    def _retrieve_cache_single(self, url: str) -> dict | None:
        '''Retrieve result stored for a given url. If there's no cache for that url return None.'''
        result = None
        try:
            result = self.r_server.get(build_cache_key(url))
        except redis.exceptions.ConnectionError:
            error('Redis server unavaliable\n')
            self.check_redis()
            result = self.r_server.get(build_cache_key(url))
        return result if result is None else eval(result)

    def _retrieve_cache(self, urls: List[str]) -> List[dict | None]:
        '''Retrieve results stored for all given urls. If there's no cache for an url return None.'''
        return [self._retrieve_cache_single(url) for url in urls]

    def put_work(self, urls: List[str]):
        self._check_workers()
        
        sep = "\n\t"
        log(f'Arrived batch job: \n[\n\t{sep.join(urls)}\n]')

        # Sadly independent but not parallel
        self.clear_cache(urls)
        self._send_pending(urls)

    def get_work(self, worker_id, count: int = 1) -> List[str]:
        self._update_worker_timestamp(worker_id)
        log(f'Request for a job.')

        len= None

        try:
            len = self.r_server.llen(PENDING_KEY)
        except redis.exceptions.ConnectionError:
            error('Redis server unavaliable\n')
            self.check_redis()
            len = self.r_server.llen(PENDING_KEY)

        if len < count:
            log(f"Not enough jobs available for a request.")
            raise ValueError("Not enough jobs in queue")

        url: str = ''

        try:
            with self.r_server.lock(PENDING_KEY+"_lock_", thread_local=False):
                url = self.r_server.lpop(PENDING_KEY)
        except redis.exceptions.ConnectionError:
            error('Redis server unavaliable\n')
            self.check_redis()
            with self.r_server.lock(PENDING_KEY+"_lock_", thread_local=False):
                url = self.r_server.lpop(PENDING_KEY)

        if isinstance(url, str):
            try:
                with self.r_server.lock(PENDING_SET_KEY+"_lock_", thread_local=False):
                    self.r_server.srem(PENDING_SET_KEY, url)
            except redis.exceptions.ConnectionError:
                error('Redis server unavaliable\n')
                self.check_redis()
                with self.r_server.lock(PENDING_SET_KEY+"_lock_", thread_local=False):
                    self.r_server.srem(PENDING_SET_KEY, url)
        else:
            for urlx in url:
                try:
                    with self.r_server.lock(PENDING_SET_KEY+"_lock_", thread_local=False):
                        self.r_server.srem(PENDING_SET_KEY, urlx)
                except redis.exceptions.ConnectionError:
                    error('Redis server unavaliable\n')
                    self.check_redis()
                    with self.r_server.lock(PENDING_SET_KEY+"_lock_", thread_local=False):
                        self.r_server.srem(PENDING_SET_KEY, urlx)

        log(f'Job given: {url}.')

        return [url] if isinstance(url, str) else url

    def put_result(self, worker_id, url: str, body: str, status_code: int = 200):
        self._update_worker_timestamp(worker_id)
        log(f'Arrived result for job: {url} with status {status_code}')
        try:
            self.r_server.set(
                build_cache_key(url),
                repr({'body': body, 'status': status_code}))
        except redis.exceptions.ConnectionError:
            error('Redis server unavaliable\n')
            self.check_redis()
            self.r_server.set(
                build_cache_key(url),
                repr({'body': body, 'status': status_code}))

    def get_result(self, urls: List[str]) -> List[dict | None]:
        sep = "\n\t"
        log(f'Request for results on: \n[\n\t{sep.join(urls)}\n]')
        r = (self._retrieve_cache(urls))

        pending_urls = [
            url for res, url in zip(r, urls)
            if res is None or res['status'] != 200]

        if len(pending_urls) > 0:
            (self.put_work(pending_urls))

        return r

    def get_result_single(self, url: str) -> dict | None:
        return self.get_result([url])[0]

    def pending_size(self):
        try:
            return self.r_server.llen(PENDING_KEY)
        except redis.exceptions.ConnectionError:
            error('Redis server unavaliable\n')
            self.check_redis()
            return self.r_server.llen(PENDING_KEY)

    def cache_size(self):
        try:
            return self.r_server.dbsize() - 1
        except redis.exceptions.ConnectionError:
            error('Redis server unavaliable\n')
            self.check_redis()
            return self.r_server.dbsize() - 1

    def get_backup(self):
        return (resolve_backup_dispatcher(), resolve_backup_dispatcher_port())


# NOTE: Not Daemon Code from here


def check_is_there():
    try:
        dispatcher = Proxy(
            f'PYRO:xscrap.dispatcher@{resolve_dispatcher()}:{resolve_dispatcher_port()}')
        dispatcher._pyroBind()
        return True
    except:
        return False


__stored_backup = (None, None)


def get_dispatcher():
    connection_attempts = resolve_mbb_retries()
    connection_sleep = resolve_mbb_time()

    global __stored_backup

    dispatcher: Dispatcher
    # Checking if dispatcher is up
    retries_count = 0
    # Note that when connection_attempts is set to 0, it tries to connect indefinitely
    while True:
        try:
            while connection_attempts == 0 or retries_count < connection_attempts:
                try:
                    log(
                        f"Searching for dispatcher at {resolve_dispatcher()}:{resolve_dispatcher_port()}")
                    dispatcher = Proxy(
                        f'PYRO:xscrap.dispatcher@{resolve_dispatcher()}:{resolve_dispatcher_port()}')
                    retries_count += 1
                    dispatcher._pyroBind()
                    uri = dispatcher._pyroUri
                    # Good
                    print(
                        f'Successfully connected to dispatcher in {uri.host}:{uri.port}\n',
                        style='c_good')
                # Ctrl-C signal and alike
                except KeyboardInterrupt:
                    exit(0)
                except Exception as e:
                    # If dispatcher is down
                    if isinstance(e, CommunicationError):
                        error('Dispatcher not reachable.\n')
                        time.sleep(connection_sleep)
                    # If name server is down
                    elif isinstance(e, NameError):
                        error('Name Server not reachable.\n')
                    else:
                        raise e
                else:
                    __stored_backup = dispatcher.get_backup()
                    return dispatcher
            if not any(__stored_backup):
                __stored_backup = (
                    resolve_backup_dispatcher(),
                    resolve_backup_dispatcher_port()
                )
            if not any(__stored_backup):
                error(
                    f'Did not manage to connect to dispatcher after {connection_attempts} tries. Exiting the application.\n')
                exit(1)
            else:
                error(
                    f'Did not manage to connect to dispatcher after {connection_attempts} tries. Trying to connect to backup dispatcher.\n')
                try:
                    log(
                        f"Searching for backup dispatcher at {__stored_backup[0]}:{__stored_backup[1]}")
                    dispatcher = Proxy(
                        f'PYRO:xscrap.dispatcher@{__stored_backup[0]}:{__stored_backup[1]}')
                    retries_count += 1
                    dispatcher._pyroBind()
                    uri = dispatcher._pyroUri
                    # Good
                    print(
                        f'Successfully connected to backup dispatcher in {uri.host}:{uri.port}\n',
                        style='c_good')
                # Ctrl-C signal and alike
                except KeyboardInterrupt:
                    exit(0)
                except CommunicationError as e:
                    error('Backup dispatcher not reachable.\n')
                    exit(1)
                else:
                    __stored_backup = dispatcher.get_backup()
                    return dispatcher
        except CommunicationError:
            time.sleep(connection_sleep)
            continue
    return None
