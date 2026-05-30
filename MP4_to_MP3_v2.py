#!/usr/bin/env python3
# Script de conversion MP4 vers MP3
# Plus moderne et fiable que l'ancien avec moviepy

import os
import subprocess
import sys
from pathlib import Path

def convertir_mp4_en_mp3(dossier):
    """Convertit tous les MP4 d'un dossier en MP3"""
    
    # Vérifier que ffmpeg est installé
    try:
        subprocess.run(['C:\\Users\\timot\\Downloads\\ffmpeg-8.1.1-essentials_build\\ffmpeg-8.1.1-essentials_build\\bin\\ffmpeg.exe', '-version'], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("❌ ffmpeg n'est pas installé. Installe-le:")
        print("   Windows: choco install ffmpeg  (ou télécharge depuis ffmpeg.org)")
        print("   Linux: sudo apt install ffmpeg")
        print("   macOS: brew install ffmpeg")
        sys.exit(1)
    
    # Vérifier le dossier
    dossier = Path(dossier).resolve()
    if not dossier.exists():
        print(f"❌ Dossier introuvable: {dossier}")
        sys.exit(1)
    
    # Trouver tous les MP4
    fichiers_mp4 = list(dossier.glob('**/*.mp4'))
    
    if not fichiers_mp4:
        print(f"❌ Aucun fichier MP4 trouvé dans {dossier}")
        sys.exit(1)
    
    print(f"✅ {len(fichiers_mp4)} fichier(s) MP4 trouvé(s)\n")
    
    # Convertir chaque MP4
    reussi = 0
    echec = 0
    
    for i, video_path in enumerate(fichiers_mp4, 1):
        audio_path = video_path.with_suffix('.mp3')
        
        # Sauter si le MP3 existe déjà
        if audio_path.exists():
            print(f"[{i}/{len(fichiers_mp4)}] ⏭️  {video_path.name} (déjà converti)")
            continue
        
        print(f"[{i}/{len(fichiers_mp4)}] 🔄 {video_path.name}...", end=" ", flush=True)
        
        try:
            # Convertir avec ffmpeg
            subprocess.run(
                [
                    'C:\\Users\\timot\\Downloads\\ffmpeg-8.1.1-essentials_build\\ffmpeg-8.1.1-essentials_build\\bin\\ffmpeg.exe',
                    '-i', str(video_path),
                    '-q:a', '0',  # Meilleure qualité audio
                    '-map', 'a',  # Extraire que l'audio
                    '-y',  # Overwrite sans demander
                    str(audio_path)
                ],
                capture_output=True,
                check=True,
                timeout=3600  # Une heure de timeout par fichier
            )
            print("✅")
            reussi += 1
            
        except subprocess.TimeoutExpired:
            print("❌ (timeout)")
            echec += 1
        except subprocess.CalledProcessError as e:
            print(f"❌ (erreur ffmpeg)")
            echec += 1
        except Exception as e:
            print(f"❌ ({str(e)})")
            echec += 1
    
    # Résumé
    print(f"\n{'='*50}")
    print(f"✅ Réussi: {reussi}")
    print(f"❌ Échoué: {echec}")
    print(f"{'='*50}")

if __name__ == "__main__":
    dossier = input("Entrez le chemin du dossier contenant les MP4:\n> ").strip()
    
    if not dossier:
        dossier = "."
    
    convertir_mp4_en_mp3(dossier)
