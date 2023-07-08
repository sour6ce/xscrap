import asyncio
import queue
import time
from typing import Any, List

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
        self.cache = Proxy(resolve_cache_server())
        uri = self.cache._pyroUri
        # Good
        print(
            f'Successfully connected to cache server in {uri.host}:{uri.port}\n',
            style='c_good')
        print(
            "Dispatched initialized for first time successfully.\n\n",
            style="c_good")

    def _send_pending(self, url: List[str]):
        '''
        Sends a bunch of urls to pending to fetch. This forces them to be fetched no matter
        if there is already a result stored in cache.
        '''
        if len(url) == 0:
            return
        # Lock forces to allow only this method to change values in that key
        for urlx in url:
            if self.cache.ps_ismember(urlx):
                return
            self.cache.ps_add(urlx)
            self.cache.p_push(urlx)

    def _clear_cache_single(self, url: str):
        '''Delete the cache result for a given url.'''
        self.cache.uc_delete(build_cache_key(url))

    def clear_cache(self, urls: List[str]):
        '''Delete the cache result for a list of urls.'''
        _ = [self._clear_cache_single(url) for url in urls]

    def _retrieve_cache_single(self, url: str) -> dict | None:
        '''Retrieve result stored for a given url. If there's no cache for that url return None.'''
        result = None
        try:
            result = self.cache.uc_get(build_cache_key(url))
        except:
            result = None
        return result if result is None else eval(result)

    def _retrieve_cache(self, urls: List[str]) -> List[dict | None]:
        '''Retrieve results stored for all given urls. If there's no cache for an url return None.'''
        return [self._retrieve_cache_single(url) for url in urls]

    def put_work(self, urls: List[str]):
        sep = "\n\t"
        log(f'Arrived batch job: \n[\n\t{sep.join(urls)}\n]')

        # Sadly independent but not parallel
        self.clear_cache(urls)
        self._send_pending(urls)

    def get_work(self, count: int = 1) -> List[str]:
        log(f'Request for a job.')

        url: str = ''
        try:
            url = self.cache.p_lpop()
        except:
            log(f"Not enough jobs available for a request.")
            raise ValueError("Not enough jobs in queue")
        self.cache.ps_srem(url)
        log(f'Job given: {url}.')
        return url

    def put_result(self, url: str, body: str, status_code: int = 200):
        log(f'Arrived result for job: {url} with status {status_code}')
        self.cache.uc_set(
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
        return self.cache.p_llen()

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
