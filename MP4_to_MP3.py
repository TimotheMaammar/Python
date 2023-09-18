# 18/09/2023
# Script permettant de convertir d'un coup tout un dossier de vidéos .mp4 en fichiers audio .mp3
# Tous les cas ne sont pas gérés.
# Beaucoup plus fiable que les sites et notamment pour les gros fichiers.

import os
from moviepy.editor import *

################################################################################
dossier = input("Entrez le chemin où se trouvent les vidéos : \n")
while not os.path.exists(dossier):
    print("Dossier introuvable ou inaccessible.")
    dossier = input("Entrez le chemin où se trouvent les vidéos : \n")
################################################################################


################################################################################
videos = []
for (repertoire, sousRepertoire, fichier) in os.walk(dossier):
	videos.extend(fichier)
################################################################################


################################################################################
for video in videos:
	if str(video).endswith('.mp4'):
		print(video)
		v = VideoFileClip(dossier + "\\" + video)
		nouveau_nom = str(video).replace('.mp4','.mp3')
		print(nouveau_nom)
		v.audio.write_audiofile(dossier + "\\" + nouveau_nom)
################################################################################
