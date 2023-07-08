import os
import socket
import time
from math import log2
from typing import Tuple

import requests
from common.environment import *
from common.printing import *
from common.setup import *

from Pyro5.errors import CommunicationError
from roles.dispatcher import Dispatcher, get_dispatcher, check_is_there

WORKERNAME = f"Worker_{os.getpid()}@{socket.gethostname()}"

WAIT_INCREMENT = 1
WAIT_REDUCTION = 1


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
    except KeyboardInterrupt:
        exit(0)

    return (sta, res)


def start(timeout=5):
    # Beauty printing. To details go to common.printing
    print('-- [c_beauty]XSCRAP[/c_beauty] WORKER --', justify='center')
    print(f'\nInitializing {WORKERNAME}.\n')

    wait_time = 1

    dispatcher = get_dispatcher()

    status = CONSOLE.status("Waiting for job...", spinner='line')
    status.start()

    while True:
        try:
            # In this case the worker just works with one url
            job = dispatcher.get_work(WORKERNAME)[0]
        except ValueError as e:
            time.sleep(log2(wait_time)/WAIT_REDUCTION)
            wait_time += WAIT_INCREMENT
        except CommunicationError:
            status.stop()
            dispatcher = get_dispatcher()
            status.start()
            wait_time = 1
        else:
            wait_time = 1
            old_status = status.renderable.text
            status.renderable.text = "Working..."
            log(f"Job assigned. Fetching HTML: {job}.")
            code, text = labor(job, timeout=timeout)
            log(f"Fetch {job} gives [c_beauty]{code}[/c_beauty] code")
            if code == 200:
                print(f'URL successfully fetched.\n', style='c_good')
            elif code//100 == 2:
                print(
                    f'URL result in {code} status code.\n', style='c_good')
            elif code == EARLY_ERROR_STATUS_CODE:
                print(
                    f'Was not possible to access the URL.\n',
                    style='c_fail')
            else:
                print(
                    f'URL fetching failed with status code {code}.\n',
                    style='c_fail')
            log(f"Saving result.")

            if not check_is_there():
                status.stop()
                dispatcher = get_dispatcher()
                status.start()

            dispatcher.put_result(WORKERNAME,job, text, code)
            log(f"Result saved.")
            status.renderable.text = old_status
