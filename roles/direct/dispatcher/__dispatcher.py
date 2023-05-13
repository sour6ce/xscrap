
from Pyro5.api import expose, behavior
import queue
from common.job import Job
from common.printing import *
from rich.status import Status


status: Status = None


@expose
@behavior(instance_mode="single")
class Dispatcher(object):
    def __init__(self):
        # TODO: Must be change for a Message Broker for better performance
        self.jobsqueue: queue.Queue[Job] = queue.Queue()
        self.resultqueue: queue.Queue[Job] = queue.Queue()
        print(
            "Dispatched initialized for first time successfully.\n\n",
            style="c_good")

    def put_work(self, item: Job):
        log(f"Arrived new job: {item.data}.")
        self.jobsqueue.put(item)

    def get_work(self, timeout=5) -> Job:
        log(f'Request for a job.')
        old_status = status.renderable.text
        status.renderable.text = "Waiting for job queue..."
        try:
            j = self.jobsqueue.get(block=True, timeout=timeout)
            log(f'Job given: {j.data}.')
            status.renderable.text = old_status
            return j
        except queue.Empty:
            log(f"No jobs available for a request.")
            status.renderable.text = old_status
            raise ValueError("no jobs in queue")

    def put_result(self, item: Job) -> None:
        log(f'Arrived result for job: {item.data}')
        self.resultqueue.put(item)

    def get_result(self, timeout=5) -> Job:
        log(f'Request for a result.')
        old_status = status.renderable.text
        status.renderable.text = "Waiting for result queue..."
        try:
            j = self.resultqueue.get(block=True, timeout=timeout)
            log(f'Result given: {j.data}.')
            status.renderable.text = old_status
            return j
        except queue.Empty:
            log(f"No results avaiable for a request.")
            status.renderable.text = old_status
            raise ValueError("no result available")

    def work_queue_size(self):
        return self.jobsqueue.qsize()

    def result_queue_size(self):
        return self.resultqueue.qsize()
