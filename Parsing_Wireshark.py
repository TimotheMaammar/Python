# Script servant à parser un fichier .pcap contenant des trames OSPF
# Affichage de tous les champs
# Récupération des champs "Auth Data" dans un tableau

import pyshark

path = './fichier.pcapng'
hashes = []

def parsing(file_path):

    cap = pyshark.FileCapture(file_path)
    for packet in cap:
        try:
            if 'OSPF' in packet:
                ospf_packet = packet['OSPF']
                field_names = packet.ospf._all_fields
                hashes.append(field_names['ospf.v2.lls.auth_data'])
                # Le résultat est un dictionnaire très simple à parcourir
                for field_name in field_names:
                    print(field_name + " => " + field_names[field_name])
        except Exception as e:
            print(f"Erreur lors de la capture : {e}")


parsing(path)


print()
print("Hashes : ")
for hash in hashes: 
    print(str(hash).replace(":",""))
