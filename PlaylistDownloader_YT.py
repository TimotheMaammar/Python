# 08/01/2022
# Script permettant de télécharger d'un coup tout une playlist Youtube au lieu de passer par des sites web foireux.
# Tous les cas ne sont pas gérés.
# 720p maximum parce que je n'ai pas besoin de plus.

import os
from pytube import YouTube, Playlist

################################################################################

dossier = input("Entrez le chemin où les vidéos seront téléchargées : \n")
while not os.path.exists(dossier):
    print("Dossier introuvable ou inaccessible.")
    dossier = input("Entrez le chemin où les vidéos seront téléchargées : \n")
   
################################################################################

pl_link = input("Entrez l'URL de la playlist Youtube : \n ")
video_links = Playlist(pl_link).video_urls
while len(video_links) == 0:
    print("Playlist introuvable ou inaccessible.")
    pl_link = input("Entrez l'URL de la playlist Youtube : \n ")
    video_links = Playlist(pl_link).video_urls
    
################################################################################

i = 0
for link in video_links:
    i += 1
    video = YouTube(link)

    if video.streams.get_by_itag("22") is not None: # 720p avec audio
        data = video.streams.get_by_itag("22")
    elif video.streams.get_by_itag("18") is not None: # 360p avec audio
        data = video.streams.get_by_itag("18")
    elif video.streams.get_by_itag("17") is not None: # 144p avec audio
        data = video.streams.get_by_itag("17")
    else:
        print("Aucun format pertinent n'a été trouvé")
        print("Passage à la vidéo suivante")
        continue

    print("Vidéo n°" + str(i))
    print("Titre : " + video.title)
    print("Début du téléchargement")
    data.download(dossier)
    print("Fin du téléchargement")
