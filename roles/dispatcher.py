import queue
from Pyro5.api import expose, behavior, serve, register_dict_to_class
from common.job import Job


# Registered how to cast from dict to class
register_dict_to_class(
    f'{Job.__module__}.{Job.__name__}', Job.from_dict)


@expose
@behavior(instance_mode="single")
class Dispatcher(object):
    def __init__(self):
        # TODO: Must be change for a Message Broker for better performance
        self.jobsqueue = queue.Queue()
        self.resultqueue = queue.Queue()

    def put_work(self, item):
        self.jobsqueue.put(item)

    def get_work(self, timeout=5) -> Job:
        try:
            return self.jobsqueue.get(block=True, timeout=timeout)
        except queue.Empty:
            raise ValueError("no jobs in queue")

    def put_result(self, item) -> None:
        self.resultqueue.put(item)

    def get_result(self, timeout=5) -> Job:
        try:
            return self.resultqueue.get(block=True, timeout=timeout)
        except queue.Empty:
            raise ValueError("no result avaible")

    def work_queue_size(self):
        return self.jobsqueue.qsize()

    def result_queue_size(self):
        return self.resultqueue.qsize()


def start():
    # Main Daemon
    serve({
        Dispatcher: "xscrap.dispatcher"
    })
