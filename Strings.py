# 01/07/2024
# Script permettant de télécharger un ensemble de fichiers à partir d'une liste de liens puis d'effectuer un "strings" dessus.
# Résultats stockés dans le même dossier au format TXT.

import os
import requests
import subprocess
import platform

url_file = 'urls.txt'
download_directory = 'downloaded_files'
os.makedirs(download_directory, exist_ok=True)

def read_urls_from_file(file_path):
    with open(file_path, 'r') as file:
        urls = file.read().splitlines()
    return urls


def download_file(url, directory):
    local_filename = os.path.join(directory, os.path.basename(url))
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_filename, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): 
                f.write(chunk)
    return local_filename


def run_strings(file_path):
    if platform.system() == 'Windows':
        result = subprocess.run(['strings.exe', file_path], capture_output=True, text=True)
    else:
        result = subprocess.run(['strings', file_path], capture_output=True, text=True)
    return result.stdout


urls = read_urls_from_file(url_file)


for url in urls:
    try:
        print(f'Téléchargement de {url}')
        file_path = download_file(url, download_directory)
        print(f'Fichier téléchargé: {file_path}')
        
        print(f'Exécution de strings sur {file_path}')
        strings_output = run_strings(file_path)
        
        strings_output_path = f"{file_path}_strings.txt"
        with open(strings_output_path, 'w') as f:
            f.write(strings_output)
        print(f'Résultats enregistrés dans: {strings_output_path}')
        
    except Exception as e:
        print(f'Erreur lors du traitement de {url}: {e}')

print('Traitement terminé.')
