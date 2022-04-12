# coding: utf-8

import socket

# 1.socket
# 2.bind
# 3.listen
# 4.accept
# 5.receive
# 6.close

print('Server!!!')
HOST = ''
PORT = 3001
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # create TCP socket obj
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # release the port when restart
s.bind((HOST, PORT))  # bind the addr
s.listen(1)  # 1: maximum number of connections in waiting state when no request is processed
print('Listening: ', PORT)
while 1:
    conn, client_addr = s.accept()    # accept conn passive
    data = conn.recv(1024)  # data cache
    print('receive: ', repr(data))
    conn.sendall(b'Hi ' + data)
    conn.close()
