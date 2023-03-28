import client as cl
import master as mt

if __name__ == '__main__':
    master = mt.Master('localhost', 8000)
    client = cl.Client('localhost', 8000)
    master.socket.bind((master.address, master.port))
    master.socket.listen(1)
    print('Listening on {}:{}'.format(master.address, master.port))
    client.connect()
    while True:
        client_socket, client_address = master.socket.accept()
        print('Accepted connection from {}:{}'.format(client_address[0], client_address[1]))
        data = input('URL: ')
        client.send_data(data)
        master.receive_data(client_socket,client_address)
        response = client.receive_data()
        print(response)
        client_socket.close()
    