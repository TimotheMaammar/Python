# =============================================================================
#  TEMPLATE SHELLCODE - kernel32.dll + Sortie propre
# =============================================================================
#
#  Le plus petit shellcode complet et autonome :
#    1. Il retrouve l'adresse de base de kernel32.dll en parcourant le PEB
#    2. Il resout l'adresse de TerminateProcess par hachage (Export Directory)
#    3. Il appelle TerminateProcess -> le processus se termine proprement
#
#  Null-free et position-independent.
#  Il peut aussi tourner sans WinDbg.
# 
#  Lancement :  .\python.exe .\kernel32_clean_exit.py (Python x86 32-bit)
#
#  La ligne "[!] Pas termine" placee apres l'execution ne doit jamais s'afficher (TerminateProcess tue le processus).
# 
# Le hachage permet de gagner de la place, d'éviter de manipuler des strings, d'éviter les changements de longueur, et d'être plus discret. 
# =============================================================================

from keystone import *
import ctypes
import sys


# -----------------------------------------------------------------------------
#  Fonction de hachage "ROR13"
# -----------------------------------------------------------------------------
#  On replie un nom de fonction (chaine de longueur variable) en une valeur
#  fixe de 4 octets. Le shellcode comparera cette valeur au hash qu'il calcule
#  lui-meme sur chaque nom exporte par la DLL.
def ror32(value, count):
    # Rotation de 'value' de 'count' bits vers la droite, sur 32 bits
    value &= 0xFFFFFFFF
    return ((value >> count) | (value << (32 - count))) & 0xFFFFFFFF


def custom_hash(name: str) -> int:
    accumulateur = 0
    for index, caractere in enumerate(name):
        accumulateur = (accumulateur + ord(caractere)) & 0xFFFFFFFF
        if index < len(name) - 1:           # Pas de rotation apres le dernier caractere
            accumulateur = ror32(accumulateur, 0x0D)   # 0x0D = 13
    return accumulateur


# -----------------------------------------------------------------------------
#  Garde-fou : un hash null-free est obligatoire ici (on le pousse sur la pile).
#  Si un hash contenait un octet 0x00, le "push <hash>" reintroduirait un null.
# -----------------------------------------------------------------------------
def verifier_hash(name: str) -> int:
    h = custom_hash(name)
    if 0 in h.to_bytes(4, "little"):
        print(f"[!] {name} : le hash {h:#010x} contient un octet NULL "
              f"-> il casserait la propriete null-free !")
    return h

# Hash de la fonction utilisee par ce template. Pour ajouter une fonction au
# bloc resolve_symbols, ajouter ici son hash et la ligne d'affichage associee.
TERMINATEPROCESS_HASH = verifier_hash("TerminateProcess")   # Vaut 0x78b5b983

print(f"[*] Hash TerminateProcess = {TERMINATEPROCESS_HASH:#010x}")


# =============================================================================
#  LE SHELLCODE (assembleur x86 32 bits)
# =============================================================================
#  Rappel important sur Keystone : dans la chaine assembleur, le caractere ';'
#  est un SEPARATEUR d'instructions, pas un debut de commentaire. On documente
#  donc avec des commentaires Python '#' a l'exterieur des chaines, une
#  instruction par ligne terminee par '\n'.
# =============================================================================
CODE = (
    # -------------------------------------------------------------------------
    #  Prologue
    # -------------------------------------------------------------------------
    "start:\n"
    "int3\n"                         # Breakpoint WinDbg (decommenter pour lancer sans interruption)
    "mov ebp, esp\n"                 # EBP = point de reference fixe pour ranger nos valeurs
                                     #   (adresses resolues, variables locales)
    "add esp, 0xfffffdf0\n"          # Reserve un espace de travail sous la pile.
                                     #   0xfffffdf0 = -0x210 : on ADDITIONNE une valeur
                                     #   negative au lieu de "sub esp, 0x210" qui, lui,
                                     #   contiendrait des octets 0x00 (interdits ici).

    # -------------------------------------------------------------------------
    #  find_kernel32 : retrouve l'adresse de base de kernel32.dll via le PEB
    # -------------------------------------------------------------------------
    #  Chemin parcouru :
    #    FS:[0x30] -> PEB
    #    PEB+0x0C  -> _PEB_LDR_DATA
    #    Ldr+0x1C  -> InInitializationOrderModuleList (liste des modules charges)
    #  Puis on parcourt la liste chainee jusqu'a tomber sur kernel32.dll.
    "find_kernel32:\n"
    "xor ecx, ecx\n"                 # ECX = 0 (sert d'offset, puis de comparateur)
    "mov esi, fs:[ecx+0x30]\n"       # ESI = adresse du PEB (le registre FS pointe sur le TEB)
    "mov esi, [esi+0x0C]\n"          # ESI = PEB->Ldr (_PEB_LDR_DATA)
    "mov esi, [esi+0x1C]\n"          # ESI = premiere entree de InInitializationOrderModuleList
    "next_module:\n"
    "mov ebx, [esi+0x08]\n"          # EBX = adresse de base du module courant (champ DllBase)
    "mov edi, [esi+0x20]\n"          # EDI = nom du module courant (chaine UNICODE)
    "mov esi, [esi]\n"               # ESI = entree suivante de la liste (champ Flink)
    "cmp [edi+0x18], cx\n"           # Le 13e caractere du nom est-il nul ?
                                     #   "kernel32.dll" fait 12 caracteres ; en UNICODE
                                     #   chaque caractere occupe 2 octets, donc le caractere
                                     #   d'indice 12 (le 13e) commence a l'offset 12*2 = 0x18.
                                     #   S'il est nul, le nom fait exactement 12 caracteres.
    "jne next_module\n"              # Sinon, on passe au module suivant
                                     #   (kernel32 est l'un des premiers initialises, donc
                                     #    le premier module de 12 caracteres rencontre)

    # -------------------------------------------------------------------------
    #  Recuperation de l'adresse de find_function SANS "call" vers l'avant
    # -------------------------------------------------------------------------
    #  Un "call" vers une etiquette situee plus loin produit un decalage positif
    #  du genre E8 xx 00 00 00 -> avec des octets 0x00. Pour l'eviter, on recupere
    #  l'adresse de find_function par la sequence :
    #    saut court vers l'avant -> call vers l'arriere (decalage negatif, donc
    #    des octets 0xFF, sans null) -> pop de l'adresse de retour empilee.
    "find_function_shorten:\n"
    "jmp find_function_shorten_bnc\n"     # Saut court vers l'avant (octets EB xx)
    "find_function_ret:\n"
    "pop esi\n"                           # ESI = adresse de retour = adresse de find_function
    "mov [ebp+0x04], esi\n"               # On memorise cette adresse pour les appels indirects
    "jmp resolve_symbols\n"               # On saute a la partie utile du shellcode
    "find_function_shorten_bnc:\n"
    "call find_function_ret\n"            # Call vers l'arriere (decalage negatif, sans null) :
                                          #   il empile l'adresse de l'instruction suivante,
                                          #   c'est-a-dire celle de find_function juste en dessous.

    # -------------------------------------------------------------------------
    #  find_function : resout un symbole par hash dans l'Export Directory Table
    # -------------------------------------------------------------------------
    #  Entree  : EBX = base de la DLL ; le hash recherche est sur la pile.
    #  Sortie  : EAX = adresse virtuelle (VMA) de la fonction trouvee.
    #  Comme le hash est pousse AVANT le call et que pushad empile 8 registres
    #  (0x20 octets) plus l'adresse de retour (0x04), le hash se retrouve a
    #  l'emplacement [esp+0x24] a l'interieur de la fonction.
    "find_function:\n"
    "pushad\n"                            # Sauvegarde des 8 registres generaux
    "mov eax, [ebx+0x3C]\n"               # EAX = decalage vers l'entete PE (champ e_lfanew)
    "mov edi, [ebx+eax+0x78]\n"           # EDI = adresse relative (RVA) de l'Export Directory Table
    "add edi, ebx\n"                      # EDI = adresse virtuelle de l'Export Directory Table
    "mov ecx, [edi+0x18]\n"               # ECX = NumberOfNames (nombre de noms exportes = compteur)
    "mov eax, [edi+0x20]\n"               # EAX = RVA du tableau AddressOfNames
    "add eax, ebx\n"                      # EAX = adresse virtuelle de AddressOfNames
    "mov [ebp-4], eax\n"                  # On memorise cette adresse (variable locale temporaire)
    "find_function_loop:\n"
    "jecxz find_function_finished\n"      # Si le compteur atteint 0 : nom non trouve, on sort
    "dec ecx\n"                           # On decremente le compteur (= index courant)
    "mov eax, [ebp-4]\n"                  # EAX = adresse du tableau AddressOfNames
    "mov esi, [eax+ecx*4]\n"              # ESI = RVA du nom d'indice ECX (chaque entree = 4 octets)
    "add esi, ebx\n"                      # ESI = adresse virtuelle de ce nom (chaine ASCII)
    "compute_hash:\n"
    "xor eax, eax\n"                      # EAX = 0
    "cdq\n"                               # EDX = 0 (accumulateur du hash ; cdq met EDX a 0 ici)
    "cld\n"                               # Sens de lecture des chaines vers l'avant (DF = 0)
    "compute_hash_again:\n"
    "lodsb\n"                             # AL = octet courant pointe par ESI, puis ESI avance
    "test al, al\n"                       # Est-on sur le terminateur nul de la chaine ?
    "jz compute_hash_finished\n"          # Oui : le hash du nom est complet
    "ror edx, 0x0D\n"                     # Rotation de l'accumulateur de 13 bits vers la droite
    "add edx, eax\n"                      # On ajoute l'octet courant a l'accumulateur
    "jmp compute_hash_again\n"            # Caractere suivant
    "compute_hash_finished:\n"
    "find_function_compare:\n"
    "cmp edx, [esp+0x24]\n"               # Le hash calcule est-il egal au hash recherche ?
    "jnz find_function_loop\n"            # Non : on essaie le nom suivant
    # --- A partir d'ici, on a trouve le bon nom a l'indice ECX ---
    "mov edx, [edi+0x24]\n"               # EDX = RVA du tableau AddressOfNameOrdinals
    "add edx, ebx\n"                      # EDX = adresse virtuelle de ce tableau
    "mov cx, [edx+ecx*2]\n"               # CX = ordinal correspondant (chaque entree = 2 octets)
    "mov edx, [edi+0x1C]\n"               # EDX = RVA du tableau AddressOfFunctions
    "add edx, ebx\n"                      # EDX = adresse virtuelle de ce tableau
    "mov eax, [edx+ecx*4]\n"              # EAX = RVA de la fonction (indexee par l'ordinal)
    "add eax, ebx\n"                      # EAX = adresse virtuelle de la fonction
    "mov [esp+0x1C], eax\n"               # On ecrase la copie de EAX sauvegardee par pushad,
                                          #   pour que popad restitue cette adresse dans EAX
    "find_function_finished:\n"
    "popad\n"                             # Restauration des registres (EAX = adresse trouvee)
    "ret\n"

    # -------------------------------------------------------------------------
    #  Partie utile : resoudre TerminateProcess puis l'appeler
    # -------------------------------------------------------------------------
    #  C'est ICI qu'on ajoute les fonctions (un bloc de resolution + un bloc
    #  d'appel par fonction), en gardant TerminateProcess en dernier.
    "resolve_symbols:\n"
    f"push {TERMINATEPROCESS_HASH:#x}\n"  # On pousse le hash recherche sur la pile
    "call dword ptr [ebp+0x04]\n"         # Appel indirect de find_function -> EAX = TerminateProcess
    # --- Appel : TerminateProcess(hProcess = -1, uExitCode = 0) ---
    #  Convention __stdcall : les arguments sont pousses dans l'ordre INVERSE.
    "xor ecx, ecx\n"                      # ECX = 0
    "push ecx\n"                          # Argument 2 : uExitCode = 0 (code de sortie)
    "push 0xffffffff\n"                   # Argument 1 : hProcess = -1 (pseudo-handle du processus courant)
                                         
    "call eax\n"                          # Appel de TerminateProcess : on ne revient jamais
)


# =============================================================================
#  HARNESS PYTHON : assemble, alloue, copie et execute le shellcode
# =============================================================================

# On refuse de continuer si l'interpreteur n'est pas en 32 bits : le shellcode
# est ecrit pour de l'x86 32 bits (FS:[0x30], etc.).
if sys.maxsize > 2**32:
    print("[!] Lance ce script avec Python x86 (32-bit)")
    sys.exit(1)

# Assemblage : Keystone transforme le texte assembleur en octets machine.
ks = Ks(KS_ARCH_X86, KS_MODE_32)
encoding, count = ks.asm(CODE)
shellcode = bytes(encoding)

# Affichage du resultat de l'assemblage.
nulls = shellcode.count(0x00)
print(f"[*] {count} instructions assemblees")
print(f"[*] Shellcode ({len(shellcode)} bytes): {shellcode.hex()}")
print(f"[*] Null bytes: {nulls}")

# Acces a l'API Windows via ctypes.
kernel32 = ctypes.windll.kernel32
kernel32.GetModuleHandleA.restype = ctypes.c_void_p
kernel32.VirtualAlloc.restype = ctypes.c_void_p   # Le retour est un pointeur (sinon tronque)

# Verite Python : la vraie base de kernel32.dll dans ce processus. C'est la
# valeur que find_kernel32 doit retrouver et placer dans EBX. 
# Pour le verifier il suffit de comparer avec 'r @ebx' dans WinDbg.
base_k32 = kernel32.GetModuleHandleA(b"kernel32.dll")
print(f"[i] Base de kernel32.dll = 0x{base_k32:08x}  (valeur attendue dans EBX)")

# Allocation d'une page memoire executable et inscriptible :
#   0x3000 = MEM_COMMIT | MEM_RESERVE
#   0x40   = PAGE_EXECUTE_READWRITE
addr = kernel32.VirtualAlloc(None, len(shellcode), 0x3000, 0x40)
ctypes.memmove(addr, shellcode, len(shellcode))   # Copie des octets du shellcode dans la page
print(f"[*] Shellcode @ 0x{addr:08X}")

# Pause : laisse le temps d'attacher WinDbg a python.exe avant l'execution.
# Utile surtout si le "int3" dans CODE est decommente (sinon le shellcode
# s'execute et se termine immediatement). Pour un lancement standalone,
# appuyer simplement sur Entree.
input("[*] Attacher WinDbg maintenant puis appuyer sur Entree...")

# Transformation de l'adresse en pointeur de fonction (void func(void)) et appel.
# Rassemblement en une seule ligne
ctypes.CFUNCTYPE(None)(addr)()

# Si on arrive ici, c'est que TerminateProcess n'a pas fait son travail.
print("[!] Pas termine : TerminateProcess n'a PAS ete appele (probleme).")
