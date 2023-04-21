import os
from common.job import Job
from Pyro5.api import Proxy, register_dict_to_class
import socket
import requests
from roles.dispatcher import Dispatcher

# Registered how to cast from dict to class
register_dict_to_class(
    f'{Job.__module__}.{Job.__name__}', Job.from_dict)


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
    dispatcher: Dispatcher = Proxy("PYRONAME:xscrap.dispatcher")
    while True:
        try:
            job = dispatcher.get_work()
        except ValueError:
            pass
        else:
            process(job, timeout=timeout)
            dispatcher.put_result(job)
