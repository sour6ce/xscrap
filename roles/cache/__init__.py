from common.environment import *
from common.printing import *
from common.setup import *
from Pyro5.api import serve, Daemon

from .__cache import *


def start():
    # Beauty printing. To details go to common.printing
    print('-- [c_beauty]XSCRAP[/c_beauty] CACHE SERVER --', justify='center')
    print('\nInitializing cache server.\n')
    # Main Daemon
    daemon = Daemon(host=resolve_cache_host(), port=resolve_cache_port())
    URI = daemon.register(Cache(daemon), objectId='xscrap.cache')

    print(f"URI:{URI}\n")

    daemon.requestLoop()
