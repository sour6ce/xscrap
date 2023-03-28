import socket
import worker

class Master:
    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def start(self):
        self.socket.bind((self.address, self.port))
        self.socket.listen(1)
        print('Listening on {}:{}'.format(self.address, self.port))
        while True:
            client_socket, client_address = self.socket.accept()
            print('Accepted connection from {}:{}'.format(client_address[0], client_address[1]))
            url_data = client_socket.recv(1024)
            url = url_data.decode()
            print('Received URL:', url)
            html = worker.get_html(url)
            client_socket.sendall(html.encode())
            client_socket.close()

if __name__ == '__main__':
    master = Master('localhost', 5000)
    master.start()
