import socket
import threading
import queue
import worker as wrk
import concurrent.futures

class Master:
    def __init__(self, address, port, num_workers):
        self.address = address
        self.port = port
        
        self.num_workers = num_workers
        self.jobs = queue.Queue()
        self.worker_pool = [wrk.Worker(id=i+1, jobs=self.jobs) for i in range(num_workers)]
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.socket.bind((self.address, self.port))
        self.socket.listen(1)
        print('Listening on {}:{}'.format(self.address, self.port))
        
        # iniciar hilo de escucha de clientes
        threading.Thread(target=self.listen_clients, daemon=True).start()

    def listen_clients(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.num_workers) as executor:
            while True:
                client_socket, client_address = self.socket.accept()
                print('Accepted connection from {}:{}'.format(client_address[0], client_address[1]))

                # recibir url del cliente
                url_data = client_socket.recv(1024)
                url = url_data.decode()
                print('Received URL:', url)

                # agregar trabajo a la cola de trabajos
                future = executor.submit(self.jobs.put, {'url': url, 'client_socket': client_socket})
    
    def stop(self):
        for worker in self.worker_pool:
            worker.stop()
        self.socket.close()

if __name__ == '__main__':
    master = Master('localhost', 5000, 2)
    for worker in master.worker_pool:
        worker.start()
    master.start()
    master.stop()

