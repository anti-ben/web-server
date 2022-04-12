# coding: utf-8

import socket

print('Client!!!')
HOST = 'localhost'
PORT = 3001
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # create TCP socket obj
s.connect((HOST, PORT))  # connect the addr
s.sendall(b'Hello from client!')
data = s.recv(1024)
s.close()
print('receive ', repr(data))
