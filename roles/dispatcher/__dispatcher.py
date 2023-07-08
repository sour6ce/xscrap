import asyncio
from subprocess import DEVNULL, Popen
import sys
import queue
import time
from typing import Any, Dict, List

from datetime import datetime, timedelta

from common.environment import *
from common.job import Job
from common.printing import *
from Pyro5.api import Daemon, Proxy, behavior, current_context, expose
from Pyro5.errors import CommunicationError, NamingError
from typing_extensions import overload
from roles.cache.__cache import Cache

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
        self.__spawning_cache=False
        
        self.worker_timestamps:Dict[str,datetime] = {}
        self.spawned_workers:Dict[str,Popen] = {}
        self.worker_timeout = timedelta(seconds=resolve_workertiemout())
        
        # Good
        print(
            f'Successfully connected to cache server in {resolve_cache_host()}:{resolve_cache_port()}\n',
            style='c_good')
        print(
            "Dispatched initialized for first time successfully.\n\n",
            style="c_good")

    def cache_is_there(self):
        try:
            cache = Proxy(resolve_cache_server())
            cache._pyroBind()
            return True
        except:
            return False
    
    def ensure_cache(self):
        while not self.cache_is_there():
            if not self.__spawning_cache:
                log("Cache node missing.")
                self.__spawning_cache=True
                log("Spawning local cache...")
                os.environ['CACHE_SERVER_HOST']=resolve_host()
                os.environ['CACHE_SERVER_PORT']=str(resolve_cache_port())
                
                try:
                    _ = Popen([sys.executable,os.path.abspath(sys.argv[0]),"cache"], 
                            stdout=DEVNULL, stdin=DEVNULL, stderr=DEVNULL)
                except Exception as e:
                    error("Local cache can't be spawned. Reason:")
                    print(e)
                    print('\n')
                else:
                    log(f"Spawned cache at: {resolve_cache_server()}")
                    self.__spawning_cache=False
            
            time.sleep(4)
                 

    def _send_pending(self, url: List[str]):
        '''
        Sends a bunch of urls to pending to fetch. This forces them to be fetched no matter
        if there is already a result stored in cache.
        '''
        if len(url) == 0:
            return
        # Lock forces to allow only this method to change values in that key
        for urlx in url:
            self.ensure_cache()
            with Proxy(resolve_cache_server()) as cache:
                if cache.ps_ismember(urlx):
                    return
                cache.ps_add(urlx)
                cache.p_push(urlx)

    def _clear_cache_single(self, url: str):
        '''Delete the cache result for a given url.'''
        self.ensure_cache()
        with Proxy(resolve_cache_server()) as cache:
            cache.uc_delete(build_cache_key(url))

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
                p = Popen([sys.executable,os.path.abspath(sys.argv[0]),"worker"], env=c_env, 
                          stdout=DEVNULL, stdin=DEVNULL, stderr=DEVNULL)
                
                new_worker_name=f"Worker_{p.pid}@{socket.gethostname()}"
                self.worker_timestamps[new_worker_name]=datetime.now()
                
                self.spawned_workers[new_worker_name]=p
                log(f"Spawned worker: {new_worker_name}")
            self.__spawning=False
                
    def _retrieve_cache_single(self, url: str) -> dict | None:
        '''Retrieve result stored for a given url. If there's no cache for that url return None.'''
        result = None
        self.ensure_cache()
        try:
            with Proxy(resolve_cache_server()) as cache:
                result = cache.uc_get(build_cache_key(url))
        except:
            result = None
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

        url: str = ''
        self.ensure_cache()
        with Proxy(resolve_cache_server()) as cache:
            try:
                url = cache.p_lpop()
            except:
                log(f"Not enough jobs available for a request.")
                raise ValueError("Not enough jobs in queue")
            cache.ps_srem(url)
        log(f'Job given: {url}.')
        return [url]

    def put_result(self, worker_id, url: str, body: str, status_code: int = 200):
        self._update_worker_timestamp(worker_id)
        log(f'Arrived result for job: {url} with status {status_code}')
        
        self.ensure_cache()
        with Proxy(resolve_cache_server()) as cache:
            cache.uc_set(build_cache_key(url),
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
        self.ensure_cache()
        with Proxy(resolve_cache_server()) as cache:
            return cache.p_llen()

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
                    f'Did not manage to connect to dispatcher after {connection_attempts} tries.\n')
                raise Exception("XSCRAP:Orphan:f'Did not manage to connect to dispatcher after {connection_attempts} tries")
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
                    raise Exception("XSCRAP:Orphan:Backup dispatcher not reachable")
                else:
                    __stored_backup = dispatcher.get_backup()
                    return dispatcher
        except CommunicationError:
            time.sleep(connection_sleep)
            continue
    return None
