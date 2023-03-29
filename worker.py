import requests
import threading
import time
import queue

class Worker(threading.Thread):
    def __init__(self, id, jobs):
        threading.Thread.__init__(self)
        self.id = id
        self.jobs = jobs
        self.stop_request = threading.Event()

    def run(self):
        while not self.stop_request.is_set():
            try:
                job = self.jobs.get(timeout=1)
            except queue.Empty:
                continue
            url = job['url']
            client_socket = job['client_socket']
            html = fetch_html(url)
            client_socket.sendall(html.encode())
            client_socket.close()
            self.jobs.task_done()
    
    def stop(self):
        self.stop_request.set()
    
def fetch_html(url):
    response = requests.get(url)
    return response.text
