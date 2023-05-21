from common.environment import *
from common.printing import *
from common.setup import *
from Pyro5.api import serve

from .__dispatcher import *


def start():
    # Beauty printing. To details go to common.printing
    print('-- [c_beauty]XSCRAP[/c_beauty] DISPATCHER --', justify='center')
    print('\nInitializing dispatcher.\n')
    global status
    status = CONSOLE.status("Routing jobs...", spinner='line')
    status.start()
    # Main Daemon
    serve({
        Dispatcher: "xscrap.dispatcher"
    }, host=resolve_host(), port=resolve_hostport(), use_ns=False)
