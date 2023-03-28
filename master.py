import socket
import worker

class Master:
    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)        
    
    def receive_data(self, client_socket, client_address):
        url_data = client_socket.recv(1024)
        url = url_data.decode()
        print('Received URL:', url)
        html = worker.get_html(url)
        client_socket.sendall(html.encode())
