import os
import socket
from typing import Tuple

import requests
from common.environment import *
from common.job import Job
from common.printing import *
from common.setup import *
from Pyro5.api import Proxy, register_dict_to_class
from Pyro5.errors import CommunicationError, NamingError
from roles.dispatcher import Dispatcher

WORKERNAME = f"Worker_{os.getpid()}@{socket.gethostname()}"


# Function that actually do the job, should be slow
def labor(url: str, timeout: int) -> Tuple[int, str]:
    # The result is a tuple of status code and body
    # NOTE: setup.EARLY_ERROR_STATUS_CODE has an special status code used
    # and is reserved to request that didn't reach the site
    res: str = None
    sta: int = None

    # The data for this job is the url of the page to scrap
    try:
        _res = requests.get(url, timeout=timeout)
        sta = _res.status_code
        res = _res.text
    except Exception as e:
        sta = 580
        res = str(e)

    return (sta, res)


def start(timeout=3):
    # Beauty printing. To details go to common.printing
    print('-- [c_beauty]XSCRAP[/c_beauty] WORKER --', justify='center')
    print(f'\nInitializing {WORKERNAME}.\n')

    dispatcher: Dispatcher

    # Checking if dispatcher is up
    with CONSOLE.status("Checking connection with dispatcher...", spinner='line') as status:
        log(
            f"Searching for dispatcher at {resolve_dispatcher()}:{resolve_dispatcher_port()}")
        dispatcher = Proxy(
            f'PYRO:xscrap.dispatcher@{resolve_dispatcher()}:{resolve_dispatcher_port()}')
        try:
            dispatcher._pyroBind()
            uri = dispatcher._pyroUri
            # Good
            print(
                f'Successfully connected to dispatcher in {uri.host}:{uri.port}\n',
                style='c_good')
        # If dispatcher is down
        except CommunicationError as e:
            status.stop()
            error('Dispatcher not reachable. Shuting down worker.\n')
            exit(1)
        # If name server is down
        except NamingError as e:
            status.stop()
            error('Name Server not reachable. Shuting down worker.\n')
            exit(1)

    status = CONSOLE.status("Waiting for job...", spinner='line')
    status.start()

    while True:
        try:
            # In this case the worker just works with one url
            job = dispatcher.get_work()[0]
        except ValueError:
            pass
        else:
            old_status = status.renderable.text
            status.renderable.text = "Working..."
            log(f"Job assigned. Fetching HTML: {job}.")
            code, text = labor(job, timeout=timeout)
            log(f"Fetch {job} gives [c_beauty]{code}[/c_beauty] code")
            if code == 200:
                print(f'URL successfully fetched.\n', style='c_good')
            elif code//100 == 2:
                print(f'URL result in {code} status code.\n', style='c_good')
            elif code == EARLY_ERROR_STATUS_CODE:
                print(f'Was not possible to access the URL.\n', style='c_fail')
            else:
                print(
                    f'URL fetching failed with status code {code}.\n',
                    style='c_fail')
            log(f"Saving result.")
            dispatcher.put_result(job, text, code)
            log(f"Result saved.")
            status.renderable.text = old_status
