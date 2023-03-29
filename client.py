import socket

class Client:
    def __init__(self, address, port):
        self.address = address #master address
        self.port = port #master port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self):
        self.socket.connect((self.address, self.port))

    # This method is used to send data to the "master". Here, the data is encoded into bytes before being sent.
    def send_data(self, url):
        self.socket.sendall(url.encode())

    # This method is used to receive data from the "master". 
    # The method continues to receive data in blocks of 1024 bytes until there is no more data to receive.
    def receive_data(self):
        html = b""
        while True:
            received = self.socket.recv(1024)
            if received:
                html += received
            else:
                break
        return html.decode()

    def close(self):
        self.socket.close()

if __name__ == '__main__':
    client = Client('localhost', 5000)
    client.connect()

    data = 'https://www.google.com/'
    client.send_data(data)
    response = client.receive_data()

    print('Received:', response)

    client.close()

