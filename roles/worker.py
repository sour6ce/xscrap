import os
import socket

import requests
from common.environment import *
from common.job import Job
from common.printing import *
from common.setup import *
from Pyro5.api import Proxy, register_dict_to_class
from Pyro5.errors import CommunicationError, NamingError
from roles.dispatcher import Dispatcher

WORKERNAME = f"Worker_{os.getpid()}@{socket.gethostname()}"


def labor(data, timeout: int) -> str | int:  # Function that actually do the job, should be slow
    # The result is the body of the page or a number if the request end in an error
    res = None

    # The data for this job is the url of the page to scrap
    try:
        res = requests.get(data, timeout=timeout)
        res = res.text if (res.status_code // 100) == 2 else res.status_code
    except Exception as e:
        res = 0

    return res


# Function that process the job calling the labor and storing the result
def process(job: Job, timeout):
    job.result = labor(job.data, timeout)
    job.processedBy = WORKERNAME


def start(timeout=10):
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
            job = dispatcher.get_work()
        except ValueError:
            pass
        else:
            old_status = status.renderable.text
            status.renderable.text = "Working..."
            log(f"Job assigned. Fetching HTML: {job.data}.")
            process(job, timeout=timeout)
            log(f"Fetch {job.data} gives {job.result if isinstance(job.result,int) else 'an HTML.'}")
            if isinstance(job.result, str):
                print(f'HTML successfully fetched: {job.data}.', style='c_good')
            if isinstance(job.result, int):
                print(
                    f'HTML fetching failed: {job.data}. Error:{job.result}',
                    style='c_fail')
            log(f"Saving result.")
            dispatcher.put_result(job)
            log(f"Result saved.")
            status.renderable.text = old_status
