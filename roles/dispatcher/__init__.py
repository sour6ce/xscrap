from common.environment import *
from common.printing import *
from common.setup import *
from Pyro5.api import serve, Daemon

from .__dispatcher import *

def start():
    # Beauty printing. To details go to common.printing
    print('-- [c_beauty]XSCRAP[/c_beauty] DISPATCHER --', justify='center')
    print('\nInitializing dispatcher.\n')
    # Main Daemon
    daemon = Daemon(host=resolve_host(), port=resolve_hostport())
    URI = daemon.register(Dispatcher(daemon), objectId='xscrap.dispatcher')

    print(f"URI:{URI}\n")

    daemon.requestLoop()
