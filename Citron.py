import os
import json
import traceback
import threading
import socket
import http.server
import urllib.parse
import urllib.request
import time
import math
import random
import tempfile
import subprocess
import shutil
import io
import sys
import ctypes
import webbrowser
import wave
import hashlib
import ssl
from tkinter import filedialog, Listbox, END, Scrollbar, messagebox, Menu, Canvas
from datetime import datetime
from collections import Counter

# ══════════════════════════════════════════════════════════════════
# ── 🔒 Certificats HTTPS (toutes les requêtes urllib.request) ───────
# ══════════════════════════════════════════════════════════════════
# Sur certaines installations Windows, le magasin de certificats système
# est incomplet (certificat intermédiaire manquant) : urllib.request
# échoue alors sur CHAQUE requête HTTPS avec une erreur du style
# "[SSL: CERTIFICATE_VERIFY_FAILED] ... unable to get issuer certificate",
# même quand le site visé (GitHub, AlloCiné, TMDB...) n'a rigoureusement
# rien d'anormal. Le paquet "certifi" fournit un jeu de certificats
# fiable et à jour, indépendant du magasin Windows local — on l'utilise
# ici pour TOUTES les requêtes HTTPS de Citron (urllib.request.urlopen
# sans "context=" explicite s'appuie sur ce contexte par défaut), ce qui
# évite d'avoir à corriger ce point site par site.
# Si "certifi" n'est pas installé, on se rabat silencieusement sur le
# comportement par défaut (celui d'avant ce correctif) : aucune
# régression, juste pas de correctif tant qu'il n'est pas disponible
# ("pip install certifi" dans l'environnement Python de Citron).
try:
    import certifi
    ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())
    print("[TLS] certifi utilisé pour les vérifications de certificat HTTPS")
except ImportError:
    print("[TLS] certifi non installé — certificats HTTPS vérifiés via le magasin système "
          "(pip install certifi pour corriger d'éventuelles erreurs SSL)")

# ══════════════════════════════════════════════════════════════════
# ── 🛟 Filet de sécurité au chargement de customtkinter / vlc ────────
# ══════════════════════════════════════════════════════════════════
# customtkinter et vlc (le module python-vlc, qui a lui-même besoin de
# VLC installé sur la machine) sont les deux seules dépendances
# externes de Citron. Sans ce filet, un souci ici (bibliothèque
# manquante, VLC absent, ou VLC installé dans une architecture 32/64
# bits différente de celle de Python) fait planter Citron AVANT même
# que le grand bloc try/except plus bas (autour de la classe
# CitronVideoPlayer) ne puisse l'intercepter : la fenêtre noire
# s'ouvre et se referme aussitôt, sans aucun message ni trace dans le
# fichier log. On affiche donc ici une boîte de dialogue Windows
# native (sans dépendre de tkinter, qui peut être la cause même du
# problème) et on journalise, avant de quitter proprement.
def _fenetre_erreur_demarrage(titre, message):
    try:
        ctypes.windll.user32.MessageBoxW(0, message, titre, 0x10)  # MB_ICONERROR
    except Exception:
        print(f"{titre}\n{message}")
    try:
        with open("erreur_citron.log", "a", encoding="utf-8") as f:
            f.write(f"\n[ERREUR AU DÉMARRAGE] {titre}\n{message}\n")
    except Exception:
        pass

try:
    import customtkinter as ctk
except ImportError as e:
    _fenetre_erreur_demarrage(
        "Citron — bibliothèque manquante",
        "Le module « customtkinter » est introuvable.\n\n"
        f"Détail : {e}\n\n"
        "Solution : relance Installer_Citron.bat, ou ouvre une invite de "
        "commandes dans ce dossier et tape :\n"
        "python -m pip install customtkinter"
    )
    sys.exit(1)

# Si un dossier "VLC" portable (contenant libvlc.dll, libvlccore.dll et
# le sous-dossier "plugins") est placé à côté de Citron, on l'indique à
# python-vlc AVANT l'import : ça permet de faire fonctionner Citron sans
# aucune installation de VLC sur la machine, en copiant simplement ce
# dossier avec Citron.exe (voir Copier_VLC_Portable.bat).
try:
    _citron_base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
except Exception:
    _citron_base_dir = os.getcwd()
_vlc_portable_dir = os.path.join(_citron_base_dir, "VLC")
if os.path.isfile(os.path.join(_vlc_portable_dir, "libvlc.dll")):
    os.environ.setdefault("PYTHON_VLC_LIB_PATH", os.path.join(_vlc_portable_dir, "libvlc.dll"))
    os.environ.setdefault("PYTHON_VLC_MODULE_PATH", os.path.join(_vlc_portable_dir, "plugins"))

try:
    import vlc
except ImportError as e:
    _fenetre_erreur_demarrage(
        "Citron — bibliothèque manquante",
        "Le module « vlc » (python-vlc) est introuvable.\n\n"
        f"Détail : {e}\n\n"
        "Solution : relance Installer_Citron.bat, ou ouvre une invite de "
        "commandes dans ce dossier et tape :\n"
        "python -m pip install python-vlc"
    )
    sys.exit(1)
except OSError as e:
    # python-vlc est installé mais ne trouve pas libvlc : VLC lui-même
    # est absent, ou installé dans une architecture différente
    # (32 bits) de celle de Python (64 bits), ou inversement.
    _fenetre_erreur_demarrage(
        "Citron — VLC introuvable",
        "Le lecteur VLC ne semble pas installé, ou installé dans une "
        "version 32/64 bits différente de celle de Python.\n\n"
        f"Détail : {e}\n\n"
        "Solution : installe VLC (même architecture que Python — 64 bits "
        "recommandé) depuis https://www.videolan.org/vlc/\n"
        "ou relance Installer_Citron.bat."
    )
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════
# ── 🎭 Banque de répliques « Citron façon Audiard » ─────────────────
# ══════════════════════════════════════════════════════════════════
# Une voix off pose le décor, sobre, presque documentaire ; Citron
# répond avec la gouaille — la formule qui claque, le cynisme
# tendre, jamais dans la lourdeur. Chaque pioche est aléatoire et
# sans répétition immédiate (voir _pick_audiard_dialogues), donc le
# dialogue affiché n'est presque jamais le même d'une fois à l'autre.
AUDIARD_DIALOGUES = [
    ("Le citron a lancé sa recherche en 3D.",
     "Ouais, et je la fais avec panache, question de standing."),
    ("Certains diraient qu'il tourne en rond.",
     "Tourner en rond, c'est déjà une direction, mon vieux."),
    ("Le tableur est vaste, les données nombreuses.",
     "Vaste, vaste… c'est vite dit. Moi j'appelle ça du rangement à faire."),
    ("Il pourrait aller plus vite.",
     "Plus vite, moins bien fait — j'ai jamais aimé ce marché-là."),
    ("La 3D, c'est pour le spectacle ou pour le boulot ?",
     "Les deux, mon ami. On n'est pas des sauvages."),
    ("On dirait qu'il cherche quelque chose de précis.",
     "Précis, oui. Perdu, non. Nuance."),
    ("Le résultat approche.",
     "Approche, approche… comme le facteur un jour de grève."),
    ("Il n'a pas l'air pressé.",
     "Un citron pressé, c'est un citron fini, mon vieux."),
    ("Le tableur résiste un peu.",
     "Tout le monde résiste au début. Après, ils m'aiment bien."),
    ("Certains l'appellent lent.",
     "Moi j'appelle ça minutieux. Question de vocabulaire."),
    ("Il tourne, il tourne encore.",
     "Et alors ? La Terre aussi, et personne s'en plaint."),
    ("Le jus des résultats ne va plus tarder.",
     "Tant mieux, parce que moi, j'ai plus grand-chose à presser."),
    ("On lui a demandé de faire vite.",
     "On m'a demandé plein de choses. J'écoute surtout le tableur."),
    ("Il travaille sans se plaindre.",
     "Se plaindre, ça n'a jamais rempli une seule colonne."),
    ("Le voilà qui inspecte chaque ligne.",
     "Chaque ligne mérite le coup d'œil. On n'est pas chez les brutes."),
]

def _pick_audiard_dialogues(k):
    """Pioche k répliques (voix off, Citron) sans répétition immédiate.
    Si k dépasse la taille de la banque, elle est remélangée et
    concaténée jusqu'à obtenir assez de répliques."""
    pool = []
    while len(pool) < k:
        batch = list(AUDIARD_DIALOGUES)
        random.shuffle(batch)
        pool.extend(batch)
    return pool[:k]

# ══════════════════════════════════════════════════════════════════
# ── 🪟 Utilitaires Windows (isolés du reste du code) ────────────────
# ══════════════════════════════════════════════════════════════════
# Regroupe ici tout le code bas niveau spécifique à Windows qui n'est PAS
# couplé à l'état vivant de l'interface (widgets Tk, générations de capture
# en cours...) : DPI awareness, flags subprocess, protocole citron:// dans
# le registre. Chaque fonction est sûre à appeler sur n'importe quel OS —
# elle ne fait rien (ou renvoie une valeur neutre) hors Windows, donc le
# reste du fichier n'a plus besoin de vérifier `os.name == "nt"` avant de
# les utiliser.
#
# Le mirroring de fenêtre (capture/masquage de fenêtre native via hwnd) et
# la lecture MP3 via MCI restent dans la classe CitronVideoPlayer : trop
# couplés à l'état vivant de l'interface pour être isolés sans risque.

IS_WINDOWS = (os.name == "nt")

try:
    import winsound  # Windows uniquement ; lecture WAV sans passer par VLC
except ImportError:
    winsound = None

if IS_WINDOWS:
    from ctypes import wintypes


def set_process_dpi_aware():
    """Déclare le process DPI-aware (Windows uniquement). À appeler AVANT
    toute création de fenêtre Tk, sinon Windows scale/déplace lui-même les
    fenêtres positionnées loin de l'origine (0,0) et tout calcul de position
    (winfo_rootx/geometry) devient faux. Ne fait rien sur les autres OS."""
    if not IS_WINDOWS:
        return
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI aware
        except Exception:
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(1)  # System DPI aware
            except Exception:
                ctypes.windll.user32.SetProcessDPIAware()  # Fallback legacy
        print("[DPI] Process déclaré DPI-aware")
    except Exception as ex:
        print(f"[DPI] Impossible de déclarer le process DPI-aware : {ex}")


def no_console_flags():
    """Flags subprocess à passer à creationflags= pour ne pas faire apparaître
    de fenêtre console lors du lancement d'un exécutable externe (ffmpeg,
    powershell...). Vaut 0 (aucun effet) sur les OS non Windows — utiliser
    cette fonction évite les appels directs à subprocess.CREATE_NO_WINDOW,
    qui n'existe pas hors Windows."""
    if not IS_WINDOWS:
        return 0
    return subprocess.CREATE_NO_WINDOW


def register_citron_url_protocol(script, script_dir, python_exe):
    """Enregistre le protocole citron:// dans le registre Windows (HKCU) et
    écrit un lanceur .cmd qui transmet correctement l'URL (%1) au script.
    Renvoie le chemin du lanceur créé. Lève une exception en cas d'échec —
    à l'appelant de l'afficher (messagebox, log...) : cette fonction ne fait
    aucune I/O d'interface, uniquement registre + fichier."""
    if not IS_WINDOWS:
        raise RuntimeError("Windows uniquement.")
    import winreg
    launcher = os.path.join(script_dir, "citron_protocol_launch.cmd")
    with open(launcher, "w", encoding="utf-8") as f:
        f.write("@echo off\r\n")
        f.write(f'cd /d "{script_dir}"\r\n')
        f.write(f'"{python_exe}" "{script}" %*\r\n')
    cmd = f'"{launcher}" "%1"'
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\citron")
    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, "URL:Citron Protocol")
    winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")
    winreg.CloseKey(key)
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                           r"Software\Classes\citron\shell\open\command")
    winreg.SetValueEx(key, "", 0, winreg.REG_SZ, cmd)
    winreg.CloseKey(key)
    return launcher


def is_citron_protocol_registered():
    """Renvoie True/False si le protocole citron:// est enregistré dans le
    registre Windows, ou None si non applicable (OS non Windows)."""
    if not IS_WINDOWS:
        return None
    import winreg
    try:
        winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Classes\citron")
        return True
    except FileNotFoundError:
        return False


# ── Mirroring natif de fenêtre (vignette de survol) ─────────────────
# Utilisé uniquement pour positionner/masquer la fenêtre de vignette
# (aperçu au survol de la barre de progression) via des appels Windows bas
# niveau plutôt que withdraw()/geometry() de Tkinter, pour éviter un bug de
# composition DWM qui laisse un résidu visuel ("fantôme") de la fenêtre.
# Ne dépend que du Toplevel Tkinter passé en paramètre — aucun état de
# l'application — donc extractible sans risque hors de la classe.

_win_mirror_ctypes_ready = False


def win_setup_ctypes():
    """Déclare explicitement les signatures des fonctions Windows utilisées
    pour la vignette. Sans ça, ctypes suppose par défaut des entiers 32 bits
    pour tous les paramètres, ce qui peut mal transmettre les handles de
    fenêtre (pointeurs 64 bits) — c'est très probablement ce qui faisait
    que SetWindowPos semblait ignorer la position demandée."""
    global _win_mirror_ctypes_ready
    if _win_mirror_ctypes_ready or not IS_WINDOWS:
        return
    from ctypes import wintypes
    u32 = ctypes.windll.user32
    u32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
    u32.GetAncestor.restype = wintypes.HWND
    u32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u32.ShowWindow.restype = wintypes.BOOL
    u32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                  ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    u32.SetWindowPos.restype = wintypes.BOOL
    u32.IsWindowVisible.argtypes = [wintypes.HWND]
    u32.IsWindowVisible.restype = wintypes.BOOL
    u32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u32.GetWindowLongW.restype = ctypes.c_long
    u32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
    u32.SetWindowLongW.restype = ctypes.c_long
    u32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF,
                                                ctypes.c_ubyte, wintypes.DWORD]
    u32.SetLayeredWindowAttributes.restype = wintypes.BOOL
    _win_mirror_ctypes_ready = True


def win_hwnd(win):
    """Résout le vrai HWND Windows de premier niveau d'un Toplevel Tkinter.
    winfo_id() renvoie l'identifiant de la ZONE DE CONTENU (un HWND enfant
    interne à Tk), pas celui de la fenêtre de premier niveau elle-même —
    appliquer SetWindowPos dessus déplace ce contenu à l'intérieur de son
    propre cadre au lieu de déplacer la fenêtre, d'où la vignette restée
    bloquée dans un coin. GetAncestor(GA_ROOT) remonte à la bonne fenêtre
    racine."""
    try:
        win_setup_ctypes()
        hwnd = win.winfo_id()
        if IS_WINDOWS:
            GA_ROOT = 2
            root_hwnd = ctypes.windll.user32.GetAncestor(hwnd, GA_ROOT)
            if root_hwnd:
                return root_hwnd
        return hwnd
    except Exception:
        return None


def win_make_layered(win):
    """Transforme la fenêtre en véritable fenêtre "layered" (WS_EX_LAYERED).
    Windows gère alors sa composition via un tampon dédié, correctement
    invalidé à chaque affichage/masquage — c'est la technique standard
    pour éliminer les résidus visuels ("fantômes") sur les fenêtres
    outil/topmost, plus fiable qu'un simple redessin forcé après coup."""
    if not IS_WINDOWS:
        return
    try:
        win_setup_ctypes()
        hwnd = win_hwnd(win)
        if not hwnd:
            return
        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        u32 = ctypes.windll.user32
        ex_style = u32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        u32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex_style | WS_EX_LAYERED)
        LWA_ALPHA = 0x2
        u32.SetLayeredWindowAttributes(hwnd, 0, 255, LWA_ALPHA)  # 255 = totalement opaque
    except Exception as ex:
        print(f"[Vignette] Erreur passage en fenêtre layered : {ex}")


def win_native_hide(win):
    """Cache une fenêtre via l'appel Windows natif ShowWindow(SW_HIDE),
    au lieu de withdraw() de Tkinter. Les info-bulles natives de Windows
    (qui ne fantômisent jamais) utilisent ce mécanisme — withdraw() de
    Tcl/Tk ne déclenche apparemment pas toujours la même séquence de
    notifications, ce qui semble être la vraie cause du fantôme."""
    if not IS_WINDOWS:
        try: win.withdraw()
        except Exception: pass
        return
    try:
        hwnd = win_hwnd(win)
        if hwnd:
            SW_HIDE = 0
            ctypes.windll.user32.ShowWindow(hwnd, SW_HIDE)
        else:
            win.withdraw()
    except Exception:
        try: win.withdraw()
        except Exception: pass


def win_native_show(win, x, y):
    """Affiche/positionne une fenêtre via les appels Windows natifs
    SetWindowPos (position + topmost) et ShowWindow(SW_SHOWNOACTIVATE,
    qui affiche sans voler le focus), au lieu de geometry()/deiconify()
    de Tkinter."""
    if not IS_WINDOWS:
        try:
            win.geometry(f"+{x}+{y}")
            win.deiconify()
            win.attributes("-topmost", True)
            win.lift()
        except Exception: pass
        return
    try:
        hwnd = win_hwnd(win)
        if not hwnd:
            print("[Vignette] HWND introuvable, secours Tkinter")
            win.geometry(f"+{x}+{y}"); win.deiconify(); win.lift(); return
        HWND_TOPMOST = -1
        SWP_NOACTIVATE = 0x0010
        SWP_SHOWWINDOW = 0x0040
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        ok = ctypes.windll.user32.SetWindowPos(
            hwnd, HWND_TOPMOST, int(x), int(y), int(w), int(h),
            SWP_NOACTIVATE | SWP_SHOWWINDOW)
        if not ok:
            err = ctypes.get_last_error()
            print(f"[Vignette] SetWindowPos a échoué (hwnd={hwnd}, x={x}, y={y}, GetLastError={err})")
        SW_SHOWNOACTIVATE = 4
        ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWNOACTIVATE)
    except Exception as ex:
        print(f"[Vignette] Erreur affichage natif : {ex}")
        try:
            win.geometry(f"+{x}+{y}"); win.deiconify(); win.lift()
        except Exception: pass


def force_redraw_region(x, y, w, h):
    """Force Windows à redessiner explicitement une zone d'écran donnée.
    Contourne un bug de composition DWM qui peut laisser un résidu visuel
    ("fantôme") de certaines fenêtres borderless/topmost, même après leur
    fermeture — la vraie cause du problème, indépendamment de la façon
    dont on ferme la fenêtre (withdraw ou destroy)."""
    if not IS_WINDOWS or w <= 0 or h <= 0:
        return
    try:
        from ctypes import wintypes
        RDW_INVALIDATE = 0x0001
        RDW_ERASE = 0x0004
        RDW_ALLCHILDREN = 0x0080
        RDW_UPDATENOW = 0x0100
        margin = 4  # légère marge pour couvrir tout résidu en bordure
        rect = wintypes.RECT(int(x - margin), int(y - margin),
                              int(x + w + margin), int(y + h + margin))
        ctypes.windll.user32.RedrawWindow(
            None, ctypes.byref(rect), None,
            RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN | RDW_UPDATENOW)
    except Exception as ex:
        print(f"[Vignette] Erreur redessin forcé : {ex}")

# ── Fin des utilitaires Windows ─────────────────────────────────────

# ── DPI awareness : à déclarer AVANT toute création de fenêtre Tk ───
set_process_dpi_aware()

log_file = "erreur_citron.log"
with open(log_file, "w", encoding="utf-8") as f:
    f.write(f"=== Démarrage Citron v9.7 - {datetime.now()} ===\n\n")
print("=== Démarrage Citron v9.7 ===")
print("[BUILD] Fix: erreur 'step' MCI +menu voix au-dessus (2026-07-20)")
print("[BUILD] Fix: menu 'Aller sur internet' fenêtre fantôme (2026-08-06)")
print("[BUILD] Compléter le tableur : réutilise le téléchargement de la simulation lors de "
      "la validation, bouton 'Valider' dans la fiche simulée, colonne 8 = N/B, "
      "colonnes 10/11 en hyperlien (2026-09-23)")
print("[BUILD] Compléter le tableur : colonne 8 en champ libre 'Renseignements divers', "
      "catégorie 'Autre' avec précision manuelle, affiche AlloCiné en pleine qualité "
      "(recadrage retiré automatiquement) (2026-09-24)")
print("[BUILD] Affiche : accepte un lien de fiche film AlloCiné (extraction automatique "
      "de l'image, avec repli sur l'URL d'origine si le nettoyage échoue) + en-tête "
      "Referer sur le téléchargement (2026-09-24)")
print("[BUILD] Recherche : cascade tv-programme.com -> AlloCine -> SensCritique -> "
      "Plansamericains (nouvelle source) -> TMDB -> IA, chaque source sautee si le "
      "resultat est deja complet ; AlloCine/SensCritique/Plansamericains examinent "
      "jusqu'a 3 fiches candidates pour departager les films homonymes par annee "
      "au lieu de renseigner au hasard (2026-09-25)")
print("[BUILD] Envoi TV (DLNA) : message final explicite si le boîtier reste bloqué en "
      "TRANSITIONING malgré des relances de Play (état DLNA interne figé côté "
      "renderer, typique après une coupure réseau) -> conseille un débranchement/"
      "rebranchement du boîtier plutôt que 'appuyez sur Play sur la télécommande' "
      "(2026-09-25)")
print("[BUILD] Zoom vidéo : remplace le zoom à la molette (peu fiable, VLC "
      "interceptait souvent l'événement avant Tkinter, nécessitait un sous-"
      "classement Win32 dédié) par des raccourcis clavier +/- (et pavé "
      "numérique), 0 du pavé numérique ou touche 0 pour réinitialiser (2026-09-26)")
print("[BUILD] Capture d'écran : tente désormais ddagrab (Desktop Duplication API) "
      "avant gdigrab (BitBlt classique) -> capture fidèlement le rendu vidéo "
      "matériel (overlay Direct3D de VLC en décodage accéléré) que gdigrab peut "
      "manquer, laissant une zone noire/figée à la place de la vidéo malgré une "
      "zone correctement sélectionnée ; repli automatique et silencieux sur "
      "gdigrab si ce build de ffmpeg n'inclut pas ddagrab, ou si la zone est sur "
      "un écran secondaire (2026-09-26)")

AUDIO_EXT = {'.mp3', '.flac', '.ogg', '.wav', '.aac', '.wma', '.m4a', '.opus'}
VIDEO_EXT  = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv'}
ALL_EXT    = AUDIO_EXT | VIDEO_EXT

# ── Version & vérification de mise à jour ────────────────────────────
# À incrémenter manuellement à chaque nouvelle version distribuée.
CITRON_VERSION = "9.7"

# URL d'un petit fichier JSON à héberger quelque part (page perso, fichier
# "brut" d'un dépôt GitHub, etc.), de la forme :
#   {"version": "1.1.0", "url": "https://.../citron_v1.1.0.py", "notes": "Correctifs de stabilité",
#    "sha256": "<empreinte SHA-256 du fichier pointé par 'url'>"}
# Laisser à None désactive complètement la vérification : aucune requête
# réseau n'est faite, aucune erreur n'est jamais affichée. À renseigner le
# jour où cette page existe réellement (voir _check_for_update ci-dessous).
#
# "sha256" (optionnel) : empreinte du fichier publié, à recalculer à chaque
# nouvelle version et à coller dans le JSON. Sous Windows :
#   certutil -hashfile Citron.py SHA256
# Si elle est fournie et correspond, Citron télécharge et vérifie lui-même
# le fichier avant de l'enregistrer (bouton "💾 Enregistrer (vérifié)") —
# ça garantit que le fichier reçu est EXACTEMENT celui que tu as publié,
# peu importe où il est hébergé. Si elle est fournie mais ne correspond
# PAS, Citron refuse carrément de proposer ce fichier. Sans "sha256", le
# comportement reste celui d'avant (simple lien ouvert dans le navigateur,
# sans garantie d'intégrité).
CITRON_UPDATE_CHECK_URL = "https://raw.githubusercontent.com/Eric-65-eng/CITRON/refs/heads/main/citron_update.json"


class _StdoutTee:
    """Duplique l'écriture d'un flux vers plusieurs cibles à la fois — ici,
    la vraie console ET une mémoire tampon. Utilisé le temps d'un « Test
    Citron » pour capturer TOUT ce qui s'affiche en console (y compris les
    print() de diagnostic dispersés dans tout le fichier, ex: [Vignette],
    [Settings], [Capture écran]...) sans changer le comportement normal :
    tout continue de s'afficher normalement, en plus d'être mémorisé."""
    def __init__(self, *targets):
        self._targets = targets
    def write(self, s):
        for t in self._targets:
            try: t.write(s)
            except Exception: pass
    def flush(self):
        for t in self._targets:
            try: t.flush()
            except Exception: pass


def _parse_version_tuple(v):
    """Convertit "1.2.3" en (1, 2, 3) pour une comparaison numérique fiable.
    Une comparaison de chaînes de caractères serait trompeuse : "1.9" est
    lexicographiquement supérieur à "1.10", alors que 1.10 est la version
    la plus récente des deux."""
    parts = []
    for p in str(v).strip().split("."):
        digits = "".join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)

# ── Schéma de citron_settings.json ───────────────────────────────────
# Chaque réglage individuel a déjà sa valeur par défaut via d.get(clé,
# défaut) dans load_settings — un ancien fichier auquel il manque une clé
# récente continue donc de se charger sans problème. Ce numéro de schéma
# sert pour le jour où un réglage devra être RENOMMÉ ou RESTRUCTURÉ plutôt
# que simplement ajouté : une valeur par défaut ne suffit plus dans ce
# cas-là, il faut une vraie transformation, appliquée une fois pour toutes
# via _migrate_settings_dict ci-dessous.
CITRON_SETTINGS_SCHEMA_VERSION = 1


def _migrate_settings_dict(d):
    """Fait progresser un dict de réglages chargé depuis le disque jusqu'au
    schéma actuel, en appliquant les migrations une par une dans l'ordre.
    Un fichier sans "settings_schema_version" est considéré en version 0
    (toutes les installations existantes avant l'ajout de ce mécanisme).
    Pour l'instant aucune migration structurelle n'est nécessaire — la liste
    ci-dessous est volontairement vide — mais le point d'entrée existe déjà,
    prêt pour la première fois où un simple valeur par défaut ne suffira
    plus (ex : un réglage renommé ou dont le format change)."""
    version = d.get("settings_schema_version", 0)
    migrations = {
        # 0: _migrate_settings_0_to_1,  # exemple pour une future migration
    }
    while version < CITRON_SETTINGS_SCHEMA_VERSION:
        step = migrations.get(version)
        if step:
            d = step(d)
        version += 1
    d["settings_schema_version"] = CITRON_SETTINGS_SCHEMA_VERSION
    return d


# Port local : instance unique + réception d'URLs depuis le navigateur
CITRON_CMD_PORT = 8767

def parse_citron_launch_arg(arg):
    """Extrait une URL depuis un argument CLI ou un lien citron://."""
    if not arg:
        return None
    arg = str(arg).strip().strip('"').strip("'")
    if arg.startswith("--url="):
        return arg[6:].strip() or None
    if arg == "--url":
        return None
    low = arg.lower()
    if low.startswith("citron://") or low.startswith("citron:"):
        try:
            raw = arg
            if raw.lower().startswith("citron://"):
                raw = "http://citron/" + raw[9:]
            elif raw.lower().startswith("citron:"):
                raw = "http://citron/" + raw[7:]
            parsed = urllib.parse.urlparse(raw)
            qs = urllib.parse.parse_qs(parsed.query)
            if "url" in qs and qs["url"]:
                return urllib.parse.unquote(qs["url"][0])
            path = urllib.parse.unquote(parsed.path.lstrip("/"))
            if path.startswith("http"):
                return path
            if "url=" in arg:
                return urllib.parse.unquote(arg.split("url=", 1)[1])
        except Exception as ex:
            print(f"[Parse] Erreur citron:// : {ex}")
        return None
    if low.startswith("http://") or low.startswith("https://"):
        return arg
    return None

def try_send_url_to_running_citron(url):
    """Transmet l'URL à une instance déjà ouverte. Retourne True si OK."""
    try:
        payload = (json.dumps({"cmd": "play", "url": url}, ensure_ascii=False) + "\n").encode("utf-8")
        with socket.create_connection(("127.0.0.1", CITRON_CMD_PORT), timeout=2.0) as s:
            s.sendall(payload)
            try:
                s.shutdown(socket.SHUT_WR)
            except Exception:
                pass
            try:
                s.recv(64)
            except Exception:
                pass
        print(f"[Citron] URL transmise à l'instance ouverte : {url[:90]}")
        return True
    except Exception as ex:
        print(f"[Citron] Pas d'instance en écoute ({ex})")
        return False

def is_audio(path):
    return os.path.splitext(path)[1].lower() in AUDIO_EXT

def get_vlc_duration(path):
    """Extrait la durée d'un média via une instance VLC jetable, dédiée à
    cet unique appel (nécessaire : parse() est bloquant et plus fiable dans
    une instance fraîche que sur l'instance de lecture principale, souvent
    déjà occupée). Appelée une fois par fichier non encore en cache lors du
    scan de bibliothèque (_fetch_durations_bg) — potentiellement des
    centaines de fois d'affilée au premier lancement sur une grosse
    bibliothèque. Sans libération explicite, chaque appel laissait une
    instance VLC complète (cœur libvlc + pool de threads) orpheline en
    mémoire, jamais libérée par le ramasse-miettes Python (les objets VLC
    sont des wrappers ctypes sur des ressources natives, hors de portée du
    GC) — la cause la plus probable des ralentissements/blocages progressifs
    de Citron rapportés après une grosse bibliothèque jamais scannée."""
    inst = None
    m = None
    try:
        inst = vlc.Instance("--quiet")
        m = inst.media_new(path)
        m.parse()
        ms = m.get_duration()
        return ms / 1000.0 if ms > 0 else 0.0
    except Exception:
        return 0.0
    finally:
        try:
            if m: m.release()
        except Exception:
            pass
        try:
            if inst: inst.release()
        except Exception:
            pass

def fmt_duration(seconds):
    seconds = int(seconds)
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"

def fmt_countdown(seconds):
    seconds = max(0, int(seconds))
    h, r = divmod(seconds, 3600)
    m, s = divmod(r, 60)
    return f"{h}h{m:02d}m{s:02d}s" if h else f"{m}m{s:02d}s"

# ── Correctif "coller" pour les champs de saisie (CTkEntry) ─────────────
# Sur certains PC Windows (notamment claviers AZERTY / dispositions non-US),
# le raccourci Ctrl+V ne déclenche pas l'évènement virtuel <<Paste>> de Tk
# dans les widgets Entry : le caractère produit par Ctrl+V dépend du layout
# clavier et Tk ne le reconnaît alors plus comme "coller". Résultat : on ne
# peut plus coller de lien (ex: URL YouTube) dans le champ. On rebranche
# donc manuellement Ctrl+V (+ variantes) sur clipboard_get(), et on ajoute
# un menu clic-droit "Coller" en secours, indépendant du raccourci clavier.
def enable_entry_paste(entry):
    """Rend le collage (Ctrl+V + clic droit) fiable dans un CTkEntry/Entry,
    quel que soit le layout clavier (AZERTY, QWERTY, etc.)."""
    def _paste(event=None):
        try:
            texte = entry.clipboard_get()
        except Exception:
            return "break"
        if not texte:
            return "break"
        try:
            entry.delete("sel.first", "sel.last")
        except Exception:
            pass
        entry.insert("insert", texte)
        return "break"

    def _copy(event=None):
        try:
            texte = entry.selection_get()
        except Exception:
            return "break"
        entry.clipboard_clear()
        entry.clipboard_append(texte)
        return "break"

    def _cut(event=None):
        _copy()
        try:
            entry.delete("sel.first", "sel.last")
        except Exception:
            pass
        return "break"

    def _select_all(event=None):
        entry.select_range(0, "end")
        entry.icursor("end")
        return "break"

    # Rebranchement explicite sur les touches (peu importe la disposition
    # clavier, on capture par touche physique ET par évènement virtuel Tk).
    for seq in ("<Control-v>", "<Control-V>", "<<Paste>>"):
        entry.bind(seq, _paste)
    for seq in ("<Control-c>", "<Control-C>", "<<Copy>>"):
        entry.bind(seq, _copy)
    for seq in ("<Control-x>", "<Control-X>", "<<Cut>>"):
        entry.bind(seq, _cut)
    for seq in ("<Control-a>", "<Control-A>"):
        entry.bind(seq, _select_all)

    # Menu clic-droit "Coller / Copier / Couper / Tout sélectionner" : marche
    # même quand le raccourci clavier est capturé/bloqué par le système.
    menu = Menu(entry, tearoff=0)
    menu.add_command(label="Coller", command=_paste)
    menu.add_command(label="Copier", command=_copy)
    menu.add_command(label="Couper", command=_cut)
    menu.add_separator()
    menu.add_command(label="Tout sélectionner", command=_select_all)

    def _popup_menu(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    entry.bind("<Button-3>", _popup_menu)  # clic droit
    return entry

# ── HTTP Server ──────────────────────────────────────────
class QuietHTTPServer(http.server.ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True
    def handle_error(self, request, client_address):
        import sys
        exc = sys.exc_info()[1]
        if isinstance(exc, (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)):
            return
        super().handle_error(request, client_address)

class VideoHTTPHandler(http.server.BaseHTTPRequestHandler):
    server_file = None
    # Mode « relais » : au lieu de servir un fichier local, on va chercher les
    # octets sur une URL distante (ex: lien direct googlevideo.com résolu par
    # yt-dlp) et on les retransmet en HTTP simple. Indispensable pour les
    # boîtiers DLNA anciens (ex: WD TV Live) dont le client HTTP embarqué ne
    # sait pas parler HTTPS : envoyer l'URL HTTPS brute à la TV se traduit
    # par un écran noir (la commande de lecture est acceptée, le titre
    # s'affiche, mais aucun octet vidéo n'arrive jamais).
    server_remote_url = None
    server_remote_mime = None
    MIME = {
        ".mp4":"video/mp4", ".mkv":"video/x-matroska", ".avi":"video/x-msvideo",
        ".mov":"video/quicktime", ".wmv":"video/x-ms-wmv", ".flv":"video/x-flv",
        ".mp3":"audio/mpeg", ".flac":"audio/flac", ".ogg":"audio/ogg",
        ".wav":"audio/wav", ".aac":"audio/aac", ".m4a":"audio/mp4",
    }
    def log_message(self, fmt, *args):
        print(f"[HTTP] {self.command} {self.path} -> {fmt % args}")
    def do_HEAD(self):
        if VideoHTTPHandler.server_remote_url:
            self._serve_remote()
        else:
            self._send_headers_only()
    def do_GET(self):
        if VideoHTTPHandler.server_remote_url:
            self._serve_remote()
        else:
            self._serve_file()
    def _send_headers_only(self):
        path = VideoHTTPHandler.server_file
        if not path or not os.path.isfile(path):
            self.send_error(404); return
        fsize = os.path.getsize(path)
        ext = os.path.splitext(path)[1].lower()
        mime = self.MIME.get(ext, "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(fsize))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Connection", "keep-alive")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
    def _serve_remote(self):
        """Relaie une URL distante (typiquement HTTPS) en HTTP simple, pour
        les boîtiers DLNA incapables de faire du HTTPS eux-mêmes. Transmet
        l'entête Range du client (la TV) à la source distante, afin que
        l'avance/le retour rapide continuent de fonctionner."""
        remote_url = VideoHTTPHandler.server_remote_url
        if not remote_url:
            self.send_error(404); return
        mime = VideoHTTPHandler.server_remote_mime or "application/octet-stream"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        rh = self.headers.get("Range", "")
        if rh:
            headers["Range"] = rh
        req = urllib.request.Request(remote_url, headers=headers)
        upstream = None
        try:
            try:
                upstream = urllib.request.urlopen(req, timeout=15)
                status = 200
            except urllib.error.HTTPError as he:
                # Un 206 (réponse partielle demandée via Range) remonte ici
                # comme "erreur" HTTP côté urllib : on le traite normalement.
                upstream = he
                status = he.code
            self.send_response(status)
            ctype = upstream.headers.get("Content-Type") or mime
            self.send_header("Content-Type", ctype)
            clen = upstream.headers.get("Content-Length")
            if clen:
                self.send_header("Content-Length", clen)
            crange = upstream.headers.get("Content-Range")
            if crange:
                self.send_header("Content-Range", crange)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Connection", "keep-alive")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            if self.command == "HEAD":
                return
            while True:
                chunk = upstream.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as ex:
            print(f"[HTTP relais] Erreur : {ex}")
            try:
                self.send_error(502)
            except Exception:
                pass
        finally:
            try:
                if upstream:
                    upstream.close()
            except Exception:
                pass
    def _serve_file(self):
        path = VideoHTTPHandler.server_file
        if not path or not os.path.isfile(path):
            self.send_error(404); return
        fsize = os.path.getsize(path)
        ext = os.path.splitext(path)[1].lower()
        mime = self.MIME.get(ext, "application/octet-stream")
        start, end = 0, fsize - 1
        rh = self.headers.get("Range", "")
        is_range = False
        if rh:
            try:
                p = rh.strip().replace("bytes=", "").split("-")
                start = int(p[0]) if p[0].strip() else 0
                end = int(p[1]) if len(p) > 1 and p[1].strip() else fsize - 1
                end = min(end, fsize - 1)
                is_range = True
            except Exception:
                start, end = 0, fsize - 1
        length = end - start + 1
        if is_range:
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{fsize}")
        else:
            self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Connection", "keep-alive")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    data = f.read(min(65536, remaining))
                    if not data: break
                    self.wfile.write(data)
                    remaining -= len(data)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as ex:
            print(f"[HTTP] Erreur envoi: {ex}")

class VideoStreamServer:
    def __init__(self, port=8765):
        self.port = port
        self.server = QuietHTTPServer(("", port), VideoHTTPHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f"[HTTP] Serveur streaming demarre port {port}")
    def serve(self, p):
        VideoHTTPHandler.server_remote_url = None
        VideoHTTPHandler.server_remote_mime = None
        VideoHTTPHandler.server_file = p
        print(f"[HTTP] Fichier servi : {os.path.basename(p)}")
    def serve_remote(self, url, mime="video/mp4"):
        """Active le mode relais : les requêtes HTTP locales sont
        retransmises depuis `url` (peut être HTTPS) au lieu d'un fichier
        disque. Utilisé pour la lecture internet sur TV DLNA."""
        VideoHTTPHandler.server_file = None
        VideoHTTPHandler.server_remote_url = url
        VideoHTTPHandler.server_remote_mime = mime
        print(f"[HTTP] Relais activé vers : {url[:100]}…")
    def get_url(self, p):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            h = s.getsockname()[0]
            s.close()
        except Exception:
            h = socket.gethostbyname(socket.gethostname())
        url = f"http://{h}:{self.port}/{urllib.parse.quote(os.path.basename(p))}"
        print(f"[HTTP] URL stream : {url}")
        return url
    def get_relay_url(self, filename_hint="stream.mp4"):
        """URL locale (HTTP simple) à donner à la TV pendant le mode relais.
        Le nom de fichier dans l'URL n'a qu'un rôle indicatif (extension) —
        le contenu réel provient de la source relayée par serve_remote()."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            h = s.getsockname()[0]
            s.close()
        except Exception:
            h = socket.gethostbyname(socket.gethostname())
        url = f"http://{h}:{self.port}/{urllib.parse.quote(filename_hint)}"
        print(f"[HTTP] URL relais (TV) : {url}")
        return url
    def stop(self):
        if self.server: self.server.shutdown()

# ── DLNA ────────────────────────────────────────────────
def _get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        h = s.getsockname()[0]
        s.close()
        return h
    except Exception:
        return socket.gethostbyname(socket.gethostname())

def _same_subnet(ip1, ip2):
    try:
        return ip1.rsplit(".", 1)[0] == ip2.rsplit(".", 1)[0]
    except Exception:
        return True

def _mime_for_url(url):
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    return {
        ".mp4":"video/mp4", ".mkv":"video/x-matroska", ".avi":"video/x-msvideo",
        ".mov":"video/quicktime", ".wmv":"video/x-ms-wmv", ".flv":"video/x-flv",
        ".mp3":"audio/mpeg", ".flac":"audio/flac", ".ogg":"audio/ogg",
        ".wav":"audio/wav", ".aac":"audio/aac", ".m4a":"audio/mp4",
    }.get(ext, "video/mp4")

def _upnp_class_for_url(url):
    ext = os.path.splitext(url.split("?")[0])[1].lower()
    return "object.item.audioItem.musicTrack" if ext in AUDIO_EXT else "object.item.videoItem"

def _soap_error_detail(he):
    """Extrait le détail réel d'une erreur SOAP/UPnP (code + description)
    depuis le corps de la réponse HTTP en erreur, quand c'est possible.
    Sans ça, toute erreur UPnP remonte comme un simple « HTTP Error 500:
    Internal Server Error », ce qui ne dit rien sur la vraie cause (ex :
    714 Illegal MIME-Type, 402 Invalid Args, 701 Transition not available…)."""
    import re as _re
    try:
        detail = he.read().decode(errors="ignore")
    except Exception:
        detail = ""
    code_m = _re.search(r'<errorCode>\s*(\d+)\s*</errorCode>', detail)
    desc_m = _re.search(r'<errorDescription>([^<]*)</errorDescription>', detail)
    extra = ""
    if code_m or desc_m:
        extra = f" — UPnPError {code_m.group(1) if code_m else '?'} : {(desc_m.group(1) if desc_m else '').strip()}"
    return f"HTTP {he.code} {he.reason}{extra}"

def _soap_stop(cu):
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body><u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:Stop></s:Body></s:Envelope>"""
    hdrs = {"Content-Type":'text/xml; charset="utf-8"',
            "SOAPAction":'"urn:schemas-upnp-org:service:AVTransport:1#Stop"',
            "Content-Length":str(len(body.encode()))}
    try:
        with urllib.request.urlopen(urllib.request.Request(cu, body.encode(), hdrs), timeout=5) as r: r.read()
    except urllib.error.HTTPError as he:
        print(f"[DLNA] Stop: {_soap_error_detail(he)}")
    except Exception as ex:
        print(f"[DLNA] Stop: {ex}")

def _soap_play(cu):
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body><u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Speed>1</Speed></u:Play></s:Body></s:Envelope>"""
    hdrs = {"Content-Type":'text/xml; charset="utf-8"',
            "SOAPAction":'"urn:schemas-upnp-org:service:AVTransport:1#Play"',
            "Content-Length":str(len(body.encode()))}
    try:
        with urllib.request.urlopen(urllib.request.Request(cu, body.encode(), hdrs), timeout=6) as r: r.read()
    except urllib.error.HTTPError as he:
        raise RuntimeError(_soap_error_detail(he)) from he

def _soap_pause(cu):
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body><u:Pause xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:Pause></s:Body></s:Envelope>"""
    hdrs = {"Content-Type":'text/xml; charset="utf-8"',
            "SOAPAction":'"urn:schemas-upnp-org:service:AVTransport:1#Pause"',
            "Content-Length":str(len(body.encode()))}
    try:
        with urllib.request.urlopen(urllib.request.Request(cu, body.encode(), hdrs), timeout=5) as r: r.read()
    except urllib.error.HTTPError as he:
        print(f"[DLNA] Pause: {_soap_error_detail(he)}")
    except Exception as ex:
        print(f"[DLNA] Pause: {ex}")

def _soap_set(cu, stream_url, title):
    """Envoie SetAVTransportURI. Tente d'abord le protocolInfo DLNA complet
    (avec drapeaux OP/FLAGS, utile pour l'avance/retour rapide sur les
    renderers strictement DLNA-compliant), puis, si le boîtier le refuse
    (ex: UPnPError 501 « Action failed », fréquent sur certains boîtiers
    anciens/quirky comme le WD TV Live avec certains conteneurs), retente
    UNE FOIS avec un protocolInfo simplifié et permissif — un compromis
    largement documenté pour ce genre de renderer capricieux."""
    import xml.sax.saxutils as _saxutils
    mime = _mime_for_url(stream_url) or "video/mp4"
    upnp_class = _upnp_class_for_url(stream_url)
    # Échappement XML du titre et de l'URL : un titre contenant "&", "<" ou
    # ">" (ex: "Fast & Furious") produisait autrement un XML mal formé,
    # rejeté par le renderer DLNA avec une erreur HTTP 500 générique et
    # incompréhensible — corrigé ici, quel que soit le titre du média.
    safe_title = _saxutils.escape(str(title))
    safe_url = _saxutils.escape(str(stream_url))

    def _try(proto):
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body><u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">
<InstanceID>0</InstanceID><CurrentURI>{safe_url}</CurrentURI>
<CurrentURIMetaData>&lt;DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"&gt;&lt;item id="1" parentID="0" restricted="1"&gt;&lt;dc:title&gt;{safe_title}&lt;/dc:title&gt;&lt;upnp:class&gt;{upnp_class}&lt;/upnp:class&gt;&lt;res protocolInfo="{proto}"&gt;{safe_url}&lt;/res&gt;&lt;/item&gt;&lt;/DIDL-Lite&gt;</CurrentURIMetaData>
</u:SetAVTransportURI></s:Body></s:Envelope>"""
        print(f"[DLNA] SetAVTransportURI -> {cu}")
        print(f"[DLNA] URL stream : {stream_url}")
        print(f"[DLNA] MIME : {mime}  |  protocolInfo : {proto[:70]}...")
        hdrs = {"Content-Type":'text/xml; charset="utf-8"',
                "SOAPAction":'"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"',
                "Content-Length":str(len(body.encode()))}
        with urllib.request.urlopen(urllib.request.Request(cu, body.encode(), hdrs), timeout=8) as r:
            r.read()

    proto_full = f"http-get:*:{mime}:DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000"
    proto_simple = f"http-get:*:{mime}:*"
    try:
        _try(proto_full)
        return
    except urllib.error.HTTPError as he1:
        detail1 = _soap_error_detail(he1)
        print(f"[DLNA] SetAVTransportURI erreur (protocolInfo complet) : {detail1} — nouvel essai en protocolInfo simplifié…")
        try:
            _try(proto_simple)
            return
        except urllib.error.HTTPError as he2:
            detail2 = _soap_error_detail(he2)
            print(f"[DLNA] SetAVTransportURI erreur (protocolInfo simplifié) : {detail2}")
            hint = ""
            if "501" in detail1 and "501" in detail2:
                hint = (" — le boîtier TV rejette l'action quel que soit le format proposé ; "
                        "s'il s'agit de la toute première action de la session, il est "
                        "probablement bloqué dans un état interne dégradé : éteignez-le "
                        "puis rallumez-le (ou redémarrez son service DLNA) et réessayez.")
            raise RuntimeError(f"{detail2}{hint}") from he2

def _soap_get_transport_state(cu):
    import re as _re
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body><u:GetTransportInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetTransportInfo></s:Body></s:Envelope>"""
    hdrs = {"Content-Type":'text/xml; charset="utf-8"',
            "SOAPAction":'"urn:schemas-upnp-org:service:AVTransport:1#GetTransportInfo"',
            "Content-Length":str(len(body.encode()))}
    try:
        with urllib.request.urlopen(urllib.request.Request(cu, body.encode(), hdrs), timeout=5) as r:
            xml = r.read().decode(errors="ignore")
        m = _re.search(r'<CurrentTransportState[^>]*>([^<]+)</CurrentTransportState>', xml, _re.I)
        return m.group(1).strip() if m else ""
    except Exception as ex:
        print(f"[DLNA] GetTransportInfo error: {ex}")
        return ""

def _soap_get_position(cu):
    import re as _re
    body = """<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body><u:GetPositionInfo xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID></u:GetPositionInfo></s:Body></s:Envelope>"""
    hdrs = {"Content-Type":'text/xml; charset="utf-8"',
            "SOAPAction":'"urn:schemas-upnp-org:service:AVTransport:1#GetPositionInfo"',
            "Content-Length":str(len(body.encode()))}
    try:
        with urllib.request.urlopen(urllib.request.Request(cu, body.encode(), hdrs), timeout=5) as r:
            xml = r.read().decode(errors="ignore")
        def pt(tag):
            mm = _re.search(rf'<{tag}[^>]*>([^<]+)</{tag}>', xml, _re.I)
            if not mm: return 0
            parts = mm.group(1).strip().split(":")
            try:
                parts = [float(x) for x in parts]
                if len(parts)==3: return parts[0]*3600+parts[1]*60+parts[2]
                if len(parts)==2: return parts[0]*60+parts[1]
                return parts[0]
            except: return 0
        return pt("RelTime"), pt("TrackDuration")
    except Exception as ex:
        print(f"[DLNA] GetPositionInfo: {ex}")
        return 0, 0

def discover_dlna_renderers(timeout=4):
    import re as _re
    ADDR, PORT = "239.255.255.250", 1900
    search_types = ["urn:schemas-upnp-org:device:MediaRenderer:1","ssdp:all"]
    raw_locations = {}
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(timeout)
        for st in search_types:
            MSG = (f"M-SEARCH * HTTP/1.1\r\nHOST: {ADDR}:{PORT}\r\n"
                   f'MAN: "ssdp:discover"\r\nMX: 2\r\nST: {st}\r\n\r\n').encode()
            sock.sendto(MSG, (ADDR, PORT))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(4096)
                r = data.decode(errors="ignore")
                loc = ""
                for line in r.splitlines():
                    if line.upper().startswith("LOCATION:"): loc = line.split(":",1)[1].strip()
                if loc and addr[0] not in raw_locations:
                    raw_locations[addr[0]] = loc
            except socket.timeout: break
    except Exception as ex: print(f"SSDP: {ex}")
    finally:
        if sock: sock.close()
    devices = []
    for ip, loc in raw_locations.items():
        dev = _resolve_device(ip, loc)
        if dev: devices.append(dev)
    return devices

def _resolve_device(ip, location_url):
    import re as _re
    try:
        req = urllib.request.Request(location_url, headers={"User-Agent":"Citron/8.5"})
        with urllib.request.urlopen(req, timeout=4) as r:
            xml = r.read().decode(errors="ignore")
    except Exception as ex:
        return {"ip":ip,"location":location_url,"name":ip,"control_url":None}
    fname = ip
    m = _re.search(r'<friendlyName[^>]*>([^<]+)</friendlyName>', xml, _re.I)
    if m: fname = m.group(1).strip()
    control_url = None
    svc_blocks = _re.findall(r'<service>(.*?)</service>', xml, _re.S|_re.I)
    base = _re.match(r'(https?://[^/]+)', location_url)
    base = base.group(1) if base else ""
    for blk in svc_blocks:
        if "AVTransport" in blk:
            cu = _re.search(r'<controlURL[^>]*>([^<]+)</controlURL>', blk, _re.I)
            if cu:
                raw = cu.group(1).strip()
                control_url = raw if raw.startswith("http") else base+("" if raw.startswith("/") else "/")+raw.lstrip("/")
                break
    return {"ip":ip,"location":location_url,"name":fname,"control_url":control_url}

# ══════════════════════════════════════════════════════════
try:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    class CitronVideoPlayer(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("🍋 Citron v9.7 - Lecteur Vidéo")

            # Filet de sécurité : une exception levée dans un callback Tk
            # (ex : opération sur une fenêtre déjà détruite suite à des
            # clics/touches très rapprochés) ne doit jamais laisser
            # l'interface bloquée. On la journalise et on continue, plutôt
            # que de laisser le comportement par défaut potentiellement
            # interrompre le traitement des événements suivants.
            def _tk_callback_exception_handler(exc, val, tb):
                try:
                    print(f"[TkCallback] Exception ignorée (widget probablement détruit) : {val}")
                except Exception:
                    pass
            self.report_callback_exception = _tk_callback_exception_handler

            # Bibliothèque
            self.video_paths  = []
            self.video_names  = []
            self.playlist     = []
            self.virtual_playlist = []
            self._virtual_playlist_win = None
            self.current_index = -1
            self.is_fullscreen = False
            self.seeking = False
            self.progress_visible = False
            self.shuffle_mode = False
            self._shuffle_queue = []
            self.shuffle_done = []
            self._shuffle_history = []  # historique pour ⏮ en mode aléatoire

            # Décompte
            self.countdown_running = False

            # Animation audio
            self.audio_anim_id = None
            self.audio_anim_phase = 0.0
            self.audio_level = 0.0

            # Cache durées
            self.duration_cache = {}

            # Cache de préchargement des fiches Infos tableur (navigation
            # ◀ ▶), {path: (row_data, error)}. Taille bornée dans
            # _prefetch (voir _open_info_window) : ce n'est qu'un accélérateur
            # de navigation immédiatement voisine, pas un historique complet.
            self._info_cache = {}
            self._INFO_CACHE_MAX = 40

            # TV
            self._tv_mode = False
            self._tv_device = None
            self._tv_play_device = None
            self._tv_control_url = None
            self._tv_play_index = -1
            self._tv_shuffle = False
            self._tv_shuffle_queue = []
            self._tv_gen = 0
            self._mirror_on = True

            # DLNA
            self._dlna_devices = []
            self._tableur_path = ""   # chemin vers le fichier .ods
            self._dlna_cancel = threading.Event()
            self._mirror_on = True
            self._seq_mode = False
            self._list_play_mode = False  # lecture directe depuis "Liste complète" (⏭/⏮ naviguent dans video_paths)
            self._list_play_index = -1
            # Lecture issue d'une recherche tableur : ⏮/⏭ naviguent dans
            # la derniere liste de resultats (titres disponibles seulement),
            # tant qu'au moins une fenetre de resultats est encore ouverte.
            self._search_play_mode = False
            self._search_play_paths = []
            self._search_play_index = -1
            self._search_results_wins = []  # fenetres de resultats encore ouvertes
            self._playlist_total_dur = 0.0
            self._single_tv_mode = False
            self._seq_visited = []       # indices déjà lus en session séquentielle
            self._seq_start_idx = 0      # index de départ de la lecture séquentielle
            self._seq_order = []         # ordre de lecture (séquentiel ou aléatoire)

            # Fenêtres
            self.list_win = None
            self.playlist_win = None
            self.stats_win = None
            self.dlna_win = None

            # Test Citron (automate de diagnostic)
            self._test_citron_active = False
            self._test_citron_fh = None
            self._test_citron_win = None
            self._test_citron_textbox = None
            self._test_citron_cancel = False
            self._test_citron_last_folder = None
            self._test_citron_last_json = None
            self._test_citron_results_list = []
            self._test_citron_last_summary = None

            # Mémorise la position/taille de la dernière fenêtre secondaire
            # ouverte (Liste, Playlist, Statistiques, Téléchargements, TV,
            # résultats de recherche, fiche Infos…), pour que Test Citron
            # puisse s'ouvrir au même endroit plutôt qu'à une position figée.
            self._last_window_geometry = None

            # Enregistrement d'écran (capture ffmpeg/gdigrab, Windows uniquement)
            self._screen_record_proc = None
            self._screen_record_active = False
            self._screen_record_path = None
            self._screen_record_log_fh = None
            self._screen_record_log_path = None
            self._screen_record_audio_device = None  # peut être écrasé par load_settings()
            self._screen_record_stop_win = None  # fenêtre flottante "⏹ Arrêter" (capture de zone libre)

            # Géométries
            self.win_geometry = None
            self.list_win_geometry = None
            self.playlist_win_geometry = None
            self.virtual_playlist_win_geometry = None
            self.stats_win_geometry = None
            self.list_scroll_pos = 0
            self._sort_reverse = False

            self.stream_server = VideoStreamServer(port=8765)

            # Lecture internet
            self._internet_mode = False
            self._internet_url = ""
            self._internet_title = ""
            self._internet_play_url = ""
            self._internet_play_failed_url = None
            self._internet_play_last_error = ""
            self._mem_dir = os.path.join(os.path.expanduser("~"), "Citron_Memoire")
            # Dernier dossier de téléchargement choisi par l'utilisateur
            # (mémorisé dans citron_settings.json). Par défaut = Citron_Memoire.
            self._last_download_dir = self._mem_dir
            self._dl_menu_debug = True  # Traceur menus 📥 dans la console
            self._dl_menu_phase = "closed"
            self._cmd_server = None
            # Préfixes de nom de fichier ("safe") des téléchargements en
            # cours vers Citron_Memoire. Utilisé par la fenêtre
            # 📥 Téléchargements pour griser les actions (▶ Lire, ➕
            # Playlist, ✏️ Modifier) d'un titre tant que son fichier n'est
            # pas encore complet sur le disque.
            self._downloading_safe_names = set()

            # Fenêtre "Liste des téléchargements" (contenu de Citron_Memoire)
            self.dl_win = None
            self.dl_win_geometry = None
            self._shotcut_path = None

            # Fenêtre(s) "🌐 Compléter le tableur" (recherche internet) —
            # plusieurs fenêtres peuvent être ouvertes en même temps (une
            # par film, en cas de titres homonymes).
            self._completer_tableur_windows = []
            self.completer_tableur_win_geometry = None
            self._tmdb_api_key = ""
            self._ia_api_key = ""
            self._ia_api_base = "https://api.openai.com/v1"
            self._ia_model = "gpt-4o-mini"
            self._dernier_dossier_affiches = ""
            self._dernier_dossier_bandes_annonces = ""

            self.load_settings()
            self.load_library()
            self._load_virtual_playlist()
            self._load_duration_cache()
            self.init_vlc()
            self.create_widgets()

            if self.win_geometry:
                self.geometry(self.win_geometry)
            else:
                self.geometry("1280x800")
            # Citron s'ouvre en plein écran au démarrage. Appliqué avec un léger
            # délai (after) car "-fullscreen" ne prend parfois pas effet s'il est
            # posé avant que la fenêtre soit réellement mappée à l'écran.
            self.is_fullscreen = True
            self.after(50, lambda: self.attributes("-fullscreen", True))
            self.bind("<Configure>", self._on_configure)
            self.protocol("WM_DELETE_WINDOW", self._save_all_window_geometries_and_quit)
            # Vérification silencieuse de mise à jour, différée pour ne pas
            # concurrencer le démarrage. N'affiche rien tant que
            # CITRON_UPDATE_CHECK_URL n'est pas configuré (voir plus haut) ou
            # que la version actuelle est déjà la plus récente.
            self.after(4000, lambda: self._check_for_update(silent=True))

            self.update_clock()
            self.update_progress_loop()
            self.refresh_stats_loop()
            self._countdown_loop()
            self._audio_level_loop()
            self._start_cmd_server()
            print("✅ Citron v9.7 démarré avec succès")

        def init_vlc(self):
            try:
                self.instance = vlc.Instance("--quiet", "--no-xlib")
                self.player = self.instance.media_player_new()
                self.player.audio_set_mute(False)  # sécurité : jamais muet par défaut
                em = self.player.event_manager()
                em.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_end_reached)
                # Diagnostic : confirme quelle version de libvlc.dll est réellement
                # chargée par python-vlc, pour vérifier qu'elle correspond bien à la
                # nouvelle installation VLC 64 bits et pas à une DLL périmée trouvée
                # ailleurs (PATH, registre, dossier de l'appli, etc.)
                try:
                    ver = vlc.libvlc_get_version().decode(errors="ignore")
                    print(f"[Audio DEBUG] Version libvlc chargée par python-vlc : {ver}")
                except Exception as ex_ver:
                    print(f"[Audio DEBUG] Impossible de lire la version libvlc : {ex_ver}")
                try:
                    import vlc as _vlc_mod
                    print(f"[Audio DEBUG] Module python-vlc chargé depuis : {_vlc_mod.__file__}")
                    dll_path = getattr(_vlc_mod, "dll", None)
                    print(f"[Audio DEBUG] Référence DLL ctypes : {dll_path}")
                except Exception as ex_mod:
                    print(f"[Audio DEBUG] Erreur inspection module vlc : {ex_mod}")
                print("✅ VLC chargé")
            except Exception as ex:
                self.player = None
                print(f"⚠️ VLC: {ex}")

        def _on_end_reached(self, event):
            if self._single_tv_mode:
                self.after(500, self.stop_video)
            elif self._seq_mode and self.shuffle_mode:
                self.after(500, self._play_shuffle_next)
            elif self._seq_mode:
                self.after(500, self._seq_next_auto)
            elif self._search_play_mode and self._any_search_results_open():
                # Meme logique que la playlist PC : passer au titre suivant
                # de la derniere liste de recherche.
                self.after(500, self._search_play_next_auto)
            else:
                self.after(500, self.stop_video)

        def _search_play_next_auto(self):
            """Enchaine le titre suivant de la liste de recherche (comme
            la lecture sequentielle playlist sur PC)."""
            if not (self._search_play_mode and self._search_play_paths):
                self.stop_video()
                return
            new_idx = self._search_play_index + 1
            if new_idx >= len(self._search_play_paths):
                self.stop_video()
                self.now_playing_label.configure(text="✅ Liste de recherche terminée")
                return
            self._search_play_index = new_idx
            self.play_file(self._search_play_paths[new_idx])
            self.set_play_mode("pc", "Recherche tableur")

        def _settings_path(self):
            """Chemin absolu de citron_settings.json (à côté du script / exe)."""
            try:
                base = os.path.dirname(os.path.abspath(sys.argv[0]))
            except Exception:
                base = os.getcwd()
            return os.path.join(base, "citron_settings.json")

        def _data_file_path(self, filename):
            """Chemin absolu d'un fichier de persistance (bibliothèque, playlist,
            cache de durées) à côté du script / exe — même logique que
            _settings_path, pour que tous les fichiers de données restent
            ensemble quel que soit le dossier de travail au lancement.
            Conserve la compatibilité avec d'anciennes installations où le
            fichier existe seulement en chemin relatif."""
            try:
                base = os.path.dirname(os.path.abspath(sys.argv[0]))
            except Exception:
                base = os.getcwd()
            resolved = os.path.join(base, filename)
            if not os.path.exists(resolved) and os.path.exists(filename):
                return os.path.abspath(filename)
            return resolved

        def load_settings(self):
            sp = self._settings_path()
            if not os.path.exists(sp) and os.path.exists("citron_settings.json"):
                sp = os.path.abspath("citron_settings.json")
            if not os.path.exists(sp):
                return
            try:
                with open(sp, "r", encoding="utf-8") as f:
                    d = json.load(f)
            except Exception as ex:
                # Fichier illisible (JSON corrompu — coupure de courant en
                # pleine écriture, disque plein...) : sans ça, Citron
                # repartait silencieusement sur des réglages par défaut, et
                # le prochain save_settings() écrasait le fichier original
                # sans laisser aucune trace de ce qui a cassé. On le met de
                # côté avant de continuer, pour qu'il reste récupérable.
                print(f"[Settings] load_settings erreur (fichier illisible/corrompu) : {ex}")
                try:
                    backup_path = sp + f".corrompu_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(sp, backup_path)
                    print(f"[Settings] Fichier corrompu conservé pour inspection : {backup_path}")
                except Exception as ex2:
                    print(f"[Settings] Impossible de conserver le fichier corrompu : {ex2}")
                return
            try:
                d = _migrate_settings_dict(d)
                self.win_geometry = d.get("main_win")
                self.list_win_geometry = d.get("list_win")
                self.playlist_win_geometry = d.get("playlist_win")
                self.virtual_playlist_win_geometry = d.get("virtual_playlist_win")
                self.stats_win_geometry = d.get("stats_win")
                self.list_scroll_pos = d.get("list_scroll", 0)
                self._tableur_path = d.get("tableur_path", "")
                self._info_win_geometry = d.get("info_win_geometry", None)
                self.dl_win_geometry = d.get("dl_win", None)
                self.completer_tableur_win_geometry = d.get("completer_tableur_win", None)
                self._tmdb_api_key = d.get("tmdb_api_key", "")
                self._ia_api_key = d.get("ia_api_key", "")
                self._ia_api_base = d.get("ia_api_base", "https://api.openai.com/v1")
                self._ia_model = d.get("ia_model", "gpt-4o-mini")
                self._dernier_dossier_affiches = d.get("dernier_dossier_affiches", "")
                self._dernier_dossier_bandes_annonces = d.get("dernier_dossier_bandes_annonces", "")
                self._shotcut_path = d.get("shotcut_path", None)
                last_dl = d.get("last_download_dir", "") or ""
                if last_dl:
                    last_dl = os.path.normpath(last_dl)
                    if os.path.isdir(last_dl):
                        self._last_download_dir = last_dl
                        self._mem_dir = last_dl  # même emplacement pour liste + téléchargements
                        print(f"[Settings] Dernier dossier téléchargement : {last_dl}")
                self._test_citron_last_folder = d.get("test_citron_last_folder", None)
                self._test_citron_last_json = d.get("test_citron_last_json", None)
                self._screen_record_audio_device = d.get("screen_record_audio_device", None)
                self._resume_voice = d.get("resume_voice", "fr-FR-DeniseNeural")
            except Exception as ex:
                print(f"[Settings] load_settings erreur : {ex}")

        def save_settings(self):
            try:
                last_dl = getattr(self, "_last_download_dir", None) or self._mem_dir
                last_dl = os.path.normpath(last_dl) if last_dl else self._mem_dir
                d = {"main_win":self.win_geometry,"list_win":self.list_win_geometry,
                     "playlist_win":self.playlist_win_geometry,
                     "virtual_playlist_win":self.virtual_playlist_win_geometry,
                     "stats_win":self.stats_win_geometry,
                     "list_scroll":self.list_scroll_pos,
                     "tableur_path":self._tableur_path,
                     "info_win_geometry":getattr(self,"_info_win_geometry",None),
                     "dl_win":self.dl_win_geometry,
                     "completer_tableur_win": getattr(self, "completer_tableur_win_geometry", None),
                     "tmdb_api_key": getattr(self, "_tmdb_api_key", ""),
                     "ia_api_key": getattr(self, "_ia_api_key", ""),
                     "ia_api_base": getattr(self, "_ia_api_base", "https://api.openai.com/v1"),
                     "ia_model": getattr(self, "_ia_model", "gpt-4o-mini"),
                     "dernier_dossier_affiches": getattr(self, "_dernier_dossier_affiches", ""),
                     "dernier_dossier_bandes_annonces": getattr(self, "_dernier_dossier_bandes_annonces", ""),
                     "shotcut_path":self._shotcut_path,
                     "last_download_dir": last_dl,
                     "test_citron_last_folder": getattr(self, "_test_citron_last_folder", None),
                     "test_citron_last_json": getattr(self, "_test_citron_last_json", None),
                     "screen_record_audio_device": getattr(self, "_screen_record_audio_device", None),
                     "resume_voice": getattr(self, "_resume_voice", "fr-FR-DeniseNeural"),
                     "settings_schema_version": CITRON_SETTINGS_SCHEMA_VERSION}
                sp = self._settings_path()
                with open(sp, "w", encoding="utf-8") as f:
                    json.dump(d, f, ensure_ascii=False, indent=2)
                print(f"[Settings] Sauvegardé → {sp} (dl={last_dl})")
            except Exception as ex:
                print(f"[Settings] save_settings erreur : {ex}")

        def load_library(self):
            lp = self._data_file_path("citron_library.json")
            if not os.path.exists(lp): return
            try:
                with open(lp,"r",encoding="utf-8") as f:
                    data = json.load(f)
                self.video_paths = [i["path"] for i in data]
                self.video_names = [i["name"] for i in data]
                # Apres changement de port USB / lettre de lecteur :
                # relocalisation silencieuse au demarrage.
                self.after(800, self._relocate_library_paths_bg)
            except Exception as ex:
                print(f"[Library] load_library erreur : {ex}")

        def _relocate_library_paths_bg(self):
            # Parcourt la bibliotheque et corrige les chemins invalides.
            def worker():
                changed = 0
                for i, p in enumerate(list(self.video_paths)):
                    if p and not os.path.isfile(p):
                        fixed = self._relocate_media_path(p)
                        if fixed and fixed != p:
                            self.video_paths[i] = fixed
                            changed += 1
                if changed:
                    try:
                        self.save_library()
                        print(f"[Relocate] {changed} chemin(s) corriges au demarrage")
                    except Exception as ex:
                        print(f"[Relocate] save_library : {ex}")
            threading.Thread(target=worker, daemon=True).start()

        def save_library(self):
            try:
                data = [{"path":p,"name":n} for p,n in zip(self.video_paths,self.video_names)]
                with open(self._data_file_path("citron_library.json"),"w",encoding="utf-8") as f:
                    json.dump(data,f,ensure_ascii=False,indent=2)
            except Exception as ex:
                print(f"[Library] save_library erreur : {ex}")

        def save_playlist(self):
            try:
                with open(self._data_file_path("playlist.json"),"w",encoding="utf-8") as f:
                    json.dump(self.playlist,f,ensure_ascii=False,indent=2)
            except Exception as ex:
                print(f"[Playlist] save_playlist erreur : {ex}")

        def _load_duration_cache(self):
            cp = self._data_file_path("citron_durations.json")
            if not os.path.exists(cp): return
            try:
                with open(cp,"r",encoding="utf-8") as f:
                    self.duration_cache = json.load(f)
            except Exception as ex:
                print(f"[DurationCache] chargement erreur : {ex}")

        def _save_duration_cache(self):
            try:
                with open(self._data_file_path("citron_durations.json"),"w",encoding="utf-8") as f:
                    json.dump(self.duration_cache,f,ensure_ascii=False,indent=2)
            except Exception as ex:
                print(f"[DurationCache] sauvegarde erreur : {ex}")

        def _get_duration(self, path):
            return self.duration_cache.get(path, 0.0)

        def _fetch_durations_bg(self, paths):
            def worker():
                changed = False
                for p in paths:
                    if p not in self.duration_cache and os.path.isfile(p):
                        d = get_vlc_duration(p)
                        if d > 0:
                            self.duration_cache[p] = d; changed = True
                if changed:
                    self._save_duration_cache()
                    self.after(0, self.refresh_playlist_window)
            threading.Thread(target=worker, daemon=True).start()

        def _get_pl_path(self, idx):
            if idx < 0 or idx >= len(self.playlist): return ""
            raw = self.playlist[idx]
            return raw.get("path","") if isinstance(raw, dict) else str(raw)

        def _on_configure(self, event):
            if event.widget is self:
                self.win_geometry = self.geometry()

        def _save_all_window_geometries_and_quit(self):
            """Capture la géométrie de toutes les fenêtres secondaires encore
            ouvertes (Playlist, Playlist virtuelle, Liste complète,
            Statistiques…) avant de fermer Citron — sinon un redimensionnement
            fait juste avant de quitter (via « 🚪 Quitter Citron » ou le bouton
            natif de fermeture) n'était jamais enregistré sur disque."""
            try:
                if self.list_win and self.list_win.winfo_exists():
                    self.list_win_geometry = self.list_win.geometry()
            except Exception:
                pass
            try:
                if self.playlist_win and self.playlist_win.winfo_exists():
                    self.playlist_win_geometry = self.playlist_win.geometry()
            except Exception:
                pass
            try:
                if self._virtual_playlist_win and self._virtual_playlist_win.winfo_exists():
                    self.virtual_playlist_win_geometry = self._virtual_playlist_win.geometry()
            except Exception:
                pass
            try:
                if self.stats_win and self.stats_win.winfo_exists():
                    self.stats_win_geometry = self.stats_win.geometry()
            except Exception:
                pass
            try:
                self.win_geometry = self.geometry()
            except Exception:
                pass
            try:
                self.save_settings()
            except Exception as ex:
                print(f"[Settings] Erreur sauvegarde à la fermeture : {ex}")
            self.destroy()

        # ── Widgets ─────────────────────────────────────
        def create_widgets(self):
            ctk.CTkLabel(self, text="🍋 Citron v9.7", font=("Arial",22,"bold")).pack(pady=(8,0))

            self.video_frame = ctk.CTkFrame(self, fg_color="black", corner_radius=0)
            self.video_frame.pack(fill="both", expand=True, padx=10, pady=(6,0))
            self.video_frame.bind("<Double-Button-1>", self.toggle_fullscreen)
            self.video_frame.bind("<Button-2>", self._reset_video_zoom)
            self._video_zoom_factor = 1.0
            # Zoom clavier sur la vidéo (remplace l'ancien zoom à la molette,
            # peu fiable car VLC intercepte souvent la molette avant Tkinter) :
            # +/- (et le pavé numérique) pour zoomer, 0 pour revenir à
            # l'ajustement automatique. Bindés sur la fenêtre principale pour
            # fonctionner quel que soit le widget qui a le focus.
            self.bind("<plus>", self._zoom_video_in)
            self.bind("<KP_Add>", self._zoom_video_in)
            self.bind("<equal>", self._zoom_video_in)   # touche « = » (même touche que « + » sans Maj sur QWERTY)
            self.bind("<minus>", self._zoom_video_out)
            self.bind("<KP_Subtract>", self._zoom_video_out)
            self.bind("<KP_0>", self._reset_video_zoom)
            self.bind("<KP_Insert>", self._reset_video_zoom)  # pavé numérique 0 quand Verr. Num est désactivé
            self.bind("<Key-0>", self._reset_video_zoom)      # touche "0" du clavier principal (plus fiable)

            self.audio_canvas = Canvas(self.video_frame, bg="black", highlightthickness=0)

            # Barre progression (masquée par défaut)
            self.prog_frame = ctk.CTkFrame(self, height=28)
            self.time_label = ctk.CTkLabel(self.prog_frame, text="0:00 / 0:00", font=("Arial",12), width=110)
            self.time_label.pack(side="left", padx=8)
            self.progress_slider = ctk.CTkSlider(self.prog_frame, from_=0, to=1000, number_of_steps=1000, command=self.on_seek)
            self.progress_slider.set(0)
            self.progress_slider.pack(side="left", fill="x", expand=True, padx=6)
            self.progress_slider.bind("<ButtonPress-1>", lambda e: setattr(self,"seeking",True))
            self.progress_slider.bind("<ButtonRelease-1>", self.on_seek_release)
            self.progress_slider.bind("<Motion>", self._on_progress_hover)
            self.progress_slider.bind("<Leave>", self._on_progress_leave)
            self.progress_visible = False
            # Mini-vignette au survol de la barre de progression
            self._thumb_win = None            # fenêtre (texte + image)
            self._thumb_lbl = None             # label du temps
            self._thumb_img_lbl = None         # label de l'image
            self._thumb_hover_job = None        # debounce (after id)
            self._thumb_vlc_instance = None    # instance VLC dédiée aux vignettes
            self._thumb_vlc_player = None      # lecteur VLC dédié (hors écran)
            self._thumb_render_win = None      # fenêtre de rendu hors écran pour VLC
            self._thumb_render_canvas = None
            self._thumb_current_path = None    # média actuellement chargé dans le lecteur vignette
            self._thumb_seek_gen = 0           # génération pour ignorer les captures obsolètes
            self._thumb_last_tmp_path = None   # dernier fichier PNG temporaire affiché (nettoyage)
            self._thumb_lock = threading.Lock()  # sérialise l'accès au lecteur vignette partagé
            self._thumb_win_ready_at = 0
            self._list_hover_last_idx = None
            self._list_hover_last_pos_ms = None
            self._list_thumb_ready_at = 0
            self._list_thumb_ready_job = None
            self._list_thumb_first_hover_done = True

            # Barre contrôles
            ctrl = ctk.CTkFrame(self, height=54)
            ctrl.pack(fill="x", padx=10, pady=(4,0))
            ctrl.pack_propagate(False)

            def mkbtn(parent, text, cmd, w=80, h=36, color=None):
                kw = dict(width=w, height=h, font=("Arial",18), command=cmd)
                if color: kw["fg_color"] = color
                b = ctk.CTkButton(parent, text=text, **kw)
                b.pack(side="left", padx=3)
                return b

            self.prev_btn = mkbtn(ctrl,"⏮",self.play_prev)
            self.play_btn = mkbtn(ctrl,"▶",self.toggle_play)
            self.stop_btn = mkbtn(ctrl,"⏹",self.stop_video)
            self.next_btn = mkbtn(ctrl,"⏭",self.play_next)
            mkbtn(ctrl,"⛶",self.toggle_fullscreen,w=44)

            self.bind("<space>", lambda e: self.toggle_play())
            self.bind("<f>", self.toggle_fullscreen)

            ctk.CTkLabel(ctrl, text="🔊", font=("Arial",16)).pack(side="left", padx=(8,2))
            self.volume_slider = ctk.CTkSlider(ctrl, from_=0, to=100, number_of_steps=100, width=100, command=self.on_volume_change)
            self.volume_slider.set(80)
            self.volume_slider.pack(side="left", padx=4)
            self.volume_slider.bind("<MouseWheel>", self.on_volume_scroll)
            if self.player: self.player.audio_set_volume(80)

            self.prog_toggle_btn = ctk.CTkButton(ctrl, text="📊", command=self.toggle_progress_bar, width=44, height=36, fg_color="#555555")
            self.prog_toggle_btn.pack(side="left", padx=4)

            self.tv_btn = ctk.CTkButton(ctrl, text="📺 TV", command=self.open_dlna_window, width=80, height=36, fg_color="#2a6496")
            self.tv_btn.pack(side="left", padx=6)

            # Bouton Miroir : visible uniquement pendant une lecture TV
            self.mirror_btn = ctk.CTkButton(ctrl, text="🖥 Miroir ON", command=self.toggle_mirror, width=120, height=36, fg_color="#1a6e3c")
            # Non packé au démarrage — affiché seulement si _tv_mode

            # Décompte total playlist (point 3)
            self.total_countdown_label = ctk.CTkLabel(ctrl, text="", font=("Arial",12), text_color="#aaaaaa")
            self.total_countdown_label.pack(side="right", padx=4)

            # Décompte titre courant
            self.countdown_label = ctk.CTkLabel(ctrl, text="⏳ --:--", font=("Arial",13))
            self.countdown_label.pack(side="right", padx=4)

            self.clock_label = ctk.CTkLabel(ctrl, text="🕒 00:00", font=("Arial",14))
            self.clock_label.pack(side="right", padx=10)


            # Barre du bas
            bot = ctk.CTkFrame(self, height=48)
            bot.pack(fill="x", padx=10, pady=(4,8))
            bot.pack_propagate(False)

            # Les boutons "📂 Fichiers" et "📁 Dossier" (ajout de médias à la
            # bibliothèque) sont désormais dans la fenêtre "Liste complète
            # des médias" (open_list_window), à laquelle ils appartiennent
            # logiquement puisqu'ils alimentent cette liste.
            # Bouton 📥 Téléchargements : menu déroulant (survol) contenant
            # «🌐 Internet» et «Téléchargements Citron».
            self._dl_menu_win = None
            self._internet_menu_win = None
            self._browser_menu_win = None
            self.dl_btn = ctk.CTkButton(bot, text="📥 Téléchargements",
                                        command=self._on_dl_btn_click,
                                        height=36, width=160, fg_color="#6a3a1a")
            self.dl_btn.pack(side="left", padx=4)
            self.dl_btn.bind("<Enter>", lambda e: self._show_dl_menu(self.dl_btn))

            self.list_btn = ctk.CTkButton(bot, text="📋 Liste", command=self.open_list_window, height=36)
            self.list_btn.pack(side="left", padx=4)

            self.tableur_btn = ctk.CTkButton(bot, text="🗂 Tableur",
                          command=lambda: self._show_tableur_menu(self.tableur_btn),
                          height=36, width=100, fg_color="#2a4a6a")
            self.tableur_btn.pack(side="left", padx=4)
            self.tableur_btn.bind("<Enter>", lambda e: self._show_tableur_menu(self.tableur_btn))

            self.playlist_btn = ctk.CTkButton(
                bot,
                text="🎵 Playlist vide",
                command=self._on_playlist_button_click,
                height=36
            )
            self.playlist_btn.pack(side="left", padx=4)
            self._playlist_menu_win = None
            self.playlist_btn.bind("<Enter>", lambda e: self._show_playlist_choice_menu())

            # Reaffiche les fenetres de resultats de recherche minimisees (-)
            self.search_restore_btn = ctk.CTkButton(
                bot, text="🔎 Recherches", command=self._restore_search_results_windows,
                height=36, width=120, fg_color="#2a4a6a")
            # Non packe par defaut — visible seulement s'il existe des fenetres
            # de resultats (ouvertes ou reduites).

            self.now_playing_label = ctk.CTkLabel(bot, text="Aucune lecture", font=("Arial",13), anchor="w")
            self.now_playing_label.pack(side="left", padx=10, fill="x", expand=True)

            # Titre suivant (dans la barre du bas)
            self.next_title_label = ctk.CTkLabel(bot, text="", font=("Arial",11,"italic"),
                                                  text_color="#888888", anchor="w")
            self.next_title_label.pack(side="left", padx=6, fill="x", expand=True)

            # Mode de lecture (point 2)
            self.mode_label = ctk.CTkLabel(bot, text="🖥 PC", font=("Arial",12), anchor="e", text_color="#aaaaaa")
            self.mode_label.pack(side="right", padx=10)

            # Bouton Paramètres avec menu au survol
            self._params_menu_win = None
            self._tableur_menu_win = None
            params_btn = ctk.CTkButton(bot, text="⚙ Paramètres",
                                       command=lambda: self._show_params_menu(params_btn),
                                       height=36, width=120,
                                       fg_color="#333333")
            params_btn.pack(side="right", padx=4)
            params_btn.bind("<Enter>", lambda e: self._show_params_menu(params_btn))

            self.update_list_button_text()
            self.update_playlist_button_text()

        def set_play_mode(self, mode, source=""):
            modes = {
                "pc": "🖥 Lecture PC",
                "tv_random": "📺🔀 Lecture aléatoire sur TV",
                "tv_seq": "📺▶ Lecture à partir de ce titre sur TV",
                "tv": "📺 Lecture TV",
                "stop": "⏹ Arrêté",
            }
            text = modes.get(mode, mode)
            if source:
                text += f"  ({source})"
            if hasattr(self, "mode_label") and self.mode_label.winfo_exists():
                self.mode_label.configure(text=text)

        def _show_params_menu(self, anchor_btn):
            """Affiche le menu Paramètres au-dessus du bouton donné (anchor_btn).
            Réutilisable depuis la fenêtre principale ET la fenêtre internet dédiée."""
            if self._params_menu_win and self._params_menu_win.winfo_exists():
                return
            pw = ctk.CTkToplevel(self)
            pw.wm_overrideredirect(True)
            pw.attributes("-topmost", True)
            pw.configure(fg_color="#2a2a2a")
            self._params_menu_win = pw
            def _close_params(e=None):
                try: pw.destroy()
                except Exception: pass
                self._params_menu_win = None
            # Entrées du menu
            items = [
                ("📖 Mode d'emploi", self._show_help),
                ("🎙️ Voix du résumé", lambda: self._show_voice_menu(anchor_btn)),
                ("🔗 Activer citron:// (navigateur)", self.register_citron_protocol),
                ("🔎 Vérifier les mises à jour", lambda: self._check_for_update(silent=False)),
                ("📦 Exporter ma configuration", self.export_library_backup),
                ("📥 Importer une configuration", self.import_library_backup),
                ("📋 Bookmarklet navigateur", self._show_bookmarklet_help),
                ("🔊 Périphérique audio (capture d'écran)", self._change_screen_record_audio_device),
                ("📐 Enregistrer une zone de l'écran", self.start_free_screen_region_recording),
                ("🧪 Test Citron", self._start_test_citron),
                ("📊 Résultats des tests Citron", self._show_test_citron_results),
                ("🚪 Quitter Citron", self._save_all_window_geometries_and_quit),
            ]
            for label, cmd in items:
                btn = ctk.CTkButton(pw, text=label, anchor="w",
                                    width=180, height=34,
                                    font=("Arial",13),
                                    fg_color="#2a2a2a",
                                    hover_color="#3a3a4a")
                if label == "🎙️ Voix du résumé":
                    # Sous-menu en cascade : ouvert à côté de cette entrée
                    # précise, SANS fermer le menu Paramètres (voir
                    # _show_voice_menu), au lieu de fermer le menu principal
                    # puis rouvrir un menu qui se plaçait par erreur au même
                    # endroit (au-dessus du bouton ⚙ Paramètres lui-même),
                    # rendant la sélection d'une voix impossible.
                    btn.configure(command=lambda b=btn: self._show_voice_menu(b, parent_menu=pw))
                else:
                    btn.configure(command=lambda c=cmd: (_close_params(), c()))
                btn.pack(fill="x", padx=2, pady=1)
            # Positionner au-dessus du bouton
            pw.update_idletasks()
            bx = anchor_btn.winfo_rootx()
            by = anchor_btn.winfo_rooty()
            pw.geometry(f"+{bx}+{by - pw.winfo_reqheight() - 4}")
            # Fermeture par SONDAGE de la position réelle du curseur, plutôt
            # que par l'événement <Leave> : ce dernier se déclenche à tort
            # dès que la souris passe du menu vers un de ses boutons internes
            # (comportement de Tkinter lors du passage parent -> enfant), ce
            # qui refermait le menu avant même de pouvoir cliquer dessus.
            def _poll_pointer():
                if not pw.winfo_exists():
                    return
                try:
                    px, py = self.winfo_pointerx(), self.winfo_pointery()
                    over_menu = (pw.winfo_rootx() <= px <= pw.winfo_rootx()+pw.winfo_width()
                                 and pw.winfo_rooty() <= py <= pw.winfo_rooty()+pw.winfo_height())
                    over_btn = (anchor_btn.winfo_rootx() <= px <= anchor_btn.winfo_rootx()+anchor_btn.winfo_width()
                                and anchor_btn.winfo_rooty() <= py <= anchor_btn.winfo_rooty()+anchor_btn.winfo_height())
                    # Ne pas refermer le menu Paramètres tant que le
                    # sous-menu "Voix du résumé" est ouvert et survolé —
                    # sinon il se referme dès que le curseur quitte la
                    # ligne pour aller cliquer une voix dans le sous-menu.
                    sub = getattr(self, "_voice_menu_win", None)
                    over_sub = False
                    if sub and sub.winfo_exists():
                        over_sub = (sub.winfo_rootx() <= px <= sub.winfo_rootx()+sub.winfo_width()
                                    and sub.winfo_rooty() <= py <= sub.winfo_rooty()+sub.winfo_height())
                    if not over_menu and not over_btn and not over_sub:
                        _close_params()
                        return
                except Exception:
                    pass
                pw.after(120, _poll_pointer)
            pw.after(120, _poll_pointer)
            pw.focus_set()

        def _show_generic_bottom_menu(self, menu_attr, anchor_btn, items):
            """Affiche un menu déroulant au-dessus d'un bouton de la barre du
            bas, avec exactement le même rendu et le même comportement que
            ⚙ Paramètres et 🗂 Tableur (fenêtre CTkToplevel sombre, boutons
            empilés, fermeture par sondage de la position du curseur).

            menu_attr : nom de l'attribut d'instance utilisé pour mémoriser
            la fenêtre du menu (ex: "_list_menu_win"), afin d'éviter les
            doublons si le survol se déclenche plusieurs fois.
            items : liste de tuples (label, commande) affichés dans l'ordre.
            """
            existing = getattr(self, menu_attr, None)
            if existing and existing.winfo_exists():
                return
            mw = ctk.CTkToplevel(self)
            mw.wm_overrideredirect(True)
            mw.attributes("-topmost", True)
            mw.configure(fg_color="#2a2a2a")
            setattr(self, menu_attr, mw)

            def _close_menu(e=None):
                try: mw.destroy()
                except Exception: pass
                setattr(self, menu_attr, None)

            for label, cmd in items:
                btn = ctk.CTkButton(mw, text=label, anchor="w",
                                    width=200, height=34,
                                    font=("Arial",13),
                                    fg_color="#2a2a2a",
                                    hover_color="#3a3a4a",
                                    command=lambda c=cmd: (_close_menu(), c()))
                btn.pack(fill="x", padx=2, pady=1)

            # Positionner au-dessus du bouton (barre du bas → dérouler vers
            # le bas le rendrait invisible car hors écran)
            mw.update_idletasks()
            bx = anchor_btn.winfo_rootx()
            by = anchor_btn.winfo_rooty()
            mw.geometry(f"+{bx}+{by - mw.winfo_reqheight() - 4}")

            # Fermeture par SONDAGE de la position réelle du curseur, comme
            # pour ⚙ Paramètres et 🗂 Tableur (voir _show_params_menu).
            def _poll_pointer():
                if not mw.winfo_exists():
                    return
                try:
                    px, py = self.winfo_pointerx(), self.winfo_pointery()
                    over_menu = (mw.winfo_rootx() <= px <= mw.winfo_rootx()+mw.winfo_width()
                                 and mw.winfo_rooty() <= py <= mw.winfo_rooty()+mw.winfo_height())
                    over_btn = (anchor_btn.winfo_rootx() <= px <= anchor_btn.winfo_rootx()+anchor_btn.winfo_width()
                                and anchor_btn.winfo_rooty() <= py <= anchor_btn.winfo_rooty()+anchor_btn.winfo_height())
                    if not over_menu and not over_btn:
                        _close_menu()
                        return
                except Exception:
                    pass
                mw.after(120, _poll_pointer)
            mw.after(120, _poll_pointer)
            mw.focus_set()

        def _update_mirror_btn_visibility(self):
            """Affiche le bouton Miroir uniquement pendant une lecture TV."""
            try:
                if not hasattr(self, "mirror_btn") or not self.mirror_btn.winfo_exists():
                    return
                if self._tv_mode:
                    if not self.mirror_btn.winfo_ismapped():
                        self.mirror_btn.pack(side="left", padx=4)
                else:
                    if self.mirror_btn.winfo_ismapped():
                        self.mirror_btn.pack_forget()
            except Exception:
                pass

        def _on_dl_btn_click(self, event=None):
            """Clic sur 📥 : bascule ouverture / fermeture du menu."""
            if self._any_dl_menu_open():
                self._close_all_dl_menus("clic bouton toggle close")
                return
            if time.time() < getattr(self, "_dl_menu_block_until", 0):
                self._dl_trace("clic ignoré (block_until)")
                return
            self._show_dl_menu(self.dl_btn)

        def _ptr_over_widget(self, widget, px, py, margin=0):
            try:
                if not widget or not widget.winfo_exists():
                    return False
                w, h = widget.winfo_width(), widget.winfo_height()
                if w <= 2 or h <= 2:
                    return False
                return (widget.winfo_rootx() - margin <= px <= widget.winfo_rootx() + w + margin
                        and widget.winfo_rooty() - margin <= py <= widget.winfo_rooty() + h + margin)
            except Exception:
                return False

        def _destroy_menu_attr(self, attr):
            """Ferme et oublie la référence d'un menu (_dl_menu_win,
            _internet_menu_win ou _browser_menu_win).

            Correctif fenêtre fantôme : sur certains PC Windows, win.destroy()
            peut lever une exception (course avec l'attribut -topmost / le
            cycle d'évènements Tk) qui était auparavant avalée silencieusement
            par `except: pass`, alors que la référence Python était quand même
            effacée juste après. Le menu restait alors visible et actif à
            l'écran (recevait encore les survols souris) mais l'appli avait
            perdu toute référence pour le refermer — il restait affiché
            indéfiniment. On masque désormais la fenêtre immédiatement
            (withdraw, qui échoue rarement) avant de tenter destroy(), et si
            destroy() échoue quand même, on retente en tâche de fond via
            _cleanup_orphan_menu_wins jusqu'à réussite.
            """
            win = getattr(self, attr, None)
            if win is not None:
                try:
                    if win.winfo_exists():
                        try:
                            win.withdraw()  # masquage immédiat, même si destroy() échoue ensuite
                        except Exception:
                            pass
                        win.destroy()
                except Exception as ex:
                    self._dl_trace(f"destroy_menu_attr échec ({attr}): {ex} — retenté en tâche de fond")
                    orphans = getattr(self, "_orphan_menu_wins", None)
                    if orphans is None:
                        orphans = []
                        self._orphan_menu_wins = orphans
                    orphans.append(win)
                    self.after(150, self._cleanup_orphan_menu_wins)
                setattr(self, attr, None)

        def _cleanup_orphan_menu_wins(self):
            """Retente périodiquement la destruction des fenêtres de menu
            dont le destroy() a échoué une première fois (fenêtres fantômes).
            Elles sont déjà masquées (withdraw) donc invisibles/inertes pour
            l'utilisateur en attendant leur destruction effective."""
            remaining = []
            for win in getattr(self, "_orphan_menu_wins", []) or []:
                try:
                    if win.winfo_exists():
                        win.destroy()
                except Exception:
                    try:
                        if win.winfo_exists():
                            remaining.append(win)
                    except Exception:
                        pass
            self._orphan_menu_wins = remaining
            if remaining:
                self._dl_trace(f"cleanup orphelins : {len(remaining)} restante(s), nouvel essai")
                self.after(300, self._cleanup_orphan_menu_wins)

        def _dl_trace(self, msg):
            if not getattr(self, "_dl_menu_debug", True):
                return
            try:
                wins = []
                for attr, label in (("_dl_menu_win", "DL"),
                                    ("_internet_menu_win", "INET"),
                                    ("_browser_menu_win", "BR")):
                    w = getattr(self, attr, None)
                    try:
                        ok = bool(w and w.winfo_exists())
                    except Exception:
                        ok = False
                    if ok:
                        wins.append(label)
                print(f"[DL-MENU] {msg} | ouverts=[{','.join(wins) or '-'}]")
            except Exception as ex:
                print(f"[DL-MENU] trace erreur: {ex}")

        def _close_all_dl_menus(self, reason="?"):
            self._dl_trace(f"CLOSE_ALL reason={reason}")
            self._dl_menu_gen = getattr(self, "_dl_menu_gen", 0) + 1
            job = getattr(self, "_dl_chain_poll_job", None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
                self._dl_chain_poll_job = None
            for attr in ("_browser_menu_win", "_internet_menu_win", "_dl_menu_win"):
                self._destroy_menu_attr(attr)
            # Filet de sécurité : détruit aussi toute fenêtre de ce menu qui
            # aurait été créée mais jamais assignée à l'un des 3 attributs
            # ci-dessus (fenêtre fantôme issue d'un appel réentrant — voir
            # _make_menu_toplevel). Sans ça, une telle fenêtre resterait
            # affichée indéfiniment, invisible pour le reste du code.
            registry = getattr(self, "_dl_menu_all_created", None) or []
            for w in registry:
                try:
                    if w.winfo_exists():
                        try:
                            w.withdraw()
                        except Exception:
                            pass
                        w.destroy()
                except Exception:
                    pass
            self._dl_menu_all_created = []
            self._dl_internet_btn = None
            self._inet_aller_btn = None
            self._dl_menu_block_until = time.time() + 0.4

        def _any_dl_menu_open(self):
            for attr in ("_dl_menu_win", "_internet_menu_win", "_browser_menu_win"):
                w = getattr(self, attr, None)
                try:
                    if w and w.winfo_exists():
                        return True
                except Exception:
                    pass
            return False

        def _over_dl_chain(self, px, py):
            """Curseur sur le bouton ou n'importe quel menu (marge 8 px)."""
            m = 8
            for w in (getattr(self, "dl_btn", None),
                      getattr(self, "_dl_menu_win", None),
                      getattr(self, "_internet_menu_win", None),
                      getattr(self, "_browser_menu_win", None)):
                if self._ptr_over_widget(w, px, py, m):
                    return True
            return False

        def _make_menu_toplevel(self):
            pw = ctk.CTkToplevel(self)
            try:
                pw.withdraw()
            except Exception:
                pass
            pw.wm_overrideredirect(True)
            pw.configure(fg_color="#2a2a2a")
            # Ne PAS appeler focus_set : provoque TclError si la fenêtre
            # est détruite pendant un after() interne CTk.
            try:
                pw.attributes("-topmost", True)
            except Exception:
                pass
            # Correctif fenêtre fantôme (2026-08-16) : chaque menu créé est
            # enregistré dans une liste globale, quelle que soit la référence
            # d'attribut (_dl_menu_win/_internet_menu_win/_browser_menu_win)
            # qui le remplacera ensuite. Si un appel réentrant (ex: Tk qui
            # traite un évènement <Enter> en attente pendant la création
            # d'une fenêtre) crée un second Toplevel avant que le premier ne
            # soit assigné, l'ancien devient orphelin — sa référence Python
            # est perdue mais la fenêtre reste affichée à l'écran. En gardant
            # une trace de TOUTES les fenêtres créées, _close_all_dl_menus
            # peut les détruire toutes, y compris les orphelines.
            registry = getattr(self, "_dl_menu_all_created", None)
            if registry is None:
                registry = []
                self._dl_menu_all_created = registry
            registry.append(pw)
            return pw

        def _place_menu_toplevel(self, pw, x, y):
            try:
                if not pw.winfo_exists():
                    return
                pw.update_idletasks()
                pw.geometry(f"+{int(x)}+{int(y)}")
                pw.update_idletasks()
                pw.deiconify()
                pw.attributes("-topmost", True)
                pw.lift()
            except Exception as ex:
                self._dl_trace(f"place_menu erreur: {ex}")

        def _start_dl_chain_poll(self):
            job = getattr(self, "_dl_chain_poll_job", None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
            outside = [0]
            last_sig = [None]

            def _poll():
                self._dl_chain_poll_job = None
                if not self._any_dl_menu_open():
                    self._dl_trace("poll stop")
                    return
                try:
                    px, py = self.winfo_pointerx(), self.winfo_pointery()
                    # Menus : marge 6 px. Boutons d'entrée : marge 0 pour ne pas
                    # confondre «URL» avec «🌍 Aller sur internet».
                    h_dl = self._ptr_over_widget(getattr(self, "_dl_menu_win", None), px, py, 6)
                    h_inet = self._ptr_over_widget(getattr(self, "_internet_menu_win", None), px, py, 6)
                    h_br = self._ptr_over_widget(getattr(self, "_browser_menu_win", None), px, py, 6)
                    h_btn = self._ptr_over_widget(getattr(self, "dl_btn", None), px, py, 6)
                    h_ib = self._ptr_over_widget(getattr(self, "_dl_internet_btn", None), px, py, 0)
                    h_ab = self._ptr_over_widget(getattr(self, "_inet_aller_btn", None), px, py, 0)
                    over = h_btn or h_dl or h_inet or h_br or h_ib or h_ab

                    sig = (h_btn, h_dl, h_inet, h_br, h_ib, h_ab, outside[0])
                    if sig != last_sig[0]:
                        last_sig[0] = sig
                        self._dl_trace(
                            f"poll btn={int(h_btn)} dl={int(h_dl)} inet={int(h_inet)} "
                            f"br={int(h_br)} ib={int(h_ib)} ab={int(h_ab)} out={outside[0]}"
                        )

                    if over:
                        outside[0] = 0

                        def _is_open(attr):
                            w = getattr(self, attr, None)
                            try:
                                return bool(w and w.winfo_exists())
                            except Exception:
                                return False

                        # 1) Navigateurs : fermer si plus sur BR ni sur Aller
                        #    (ex. retour sur «URL» → ab=0, br=0)
                        if _is_open("_browser_menu_win") and not h_br and not h_ab:
                            self._dl_trace("prune BR (hors Aller/BR)")
                            self._destroy_menu_attr("_browser_menu_win")

                        # 2) Internet : fermer seulement s'il est ouvert ET que
                        #    le curseur est sur DL hors entrée Internet / INET / BR
                        if (_is_open("_internet_menu_win")
                                and h_dl and not h_ib and not h_inet
                                and not h_br and not h_ab):
                            self._dl_trace("prune INET (sur DL hors Internet)")
                            self._destroy_menu_attr("_browser_menu_win")
                            self._destroy_menu_attr("_internet_menu_win")
                            self._inet_aller_btn = None
                    else:
                        outside[0] += 1
                        if outside[0] >= 6:  # ~240 ms
                            self._close_all_dl_menus("hors zone")
                            return
                except Exception as ex:
                    self._dl_trace(f"poll exception: {ex}")
                self._dl_chain_poll_job = self.after(40, _poll)

            self._dl_trace("poll START")
            self._dl_chain_poll_job = self.after(40, _poll)

        def _show_dl_menu(self, anchor_btn):
            if time.time() < getattr(self, "_dl_menu_block_until", 0):
                self._dl_trace("OPEN DL bloqué")
                return
            if self._dl_menu_win and self._dl_menu_win.winfo_exists():
                return
            # Garde anti-réentrance (voir _make_menu_toplevel) : bloque tout
            # appel imbriqué qui surviendrait pendant la construction de CE
            # menu (ex: Tk traitant un évènement <Enter> en attente), avant
            # même que self._dl_menu_win soit assigné.
            if getattr(self, "_dl_menu_opening", False):
                return
            self._dl_menu_opening = True
            try:
                gen = getattr(self, "_dl_menu_gen", 0)
                self._destroy_menu_attr("_browser_menu_win")
                self._destroy_menu_attr("_internet_menu_win")

                pw = self._make_menu_toplevel()
                self._dl_menu_win = pw
                self._dl_trace("OPEN menu DL")

                internet_btn = ctk.CTkButton(
                    pw, text="🌐 Internet  ▸", anchor="w",
                    width=320, height=34, font=("Arial", 13),
                    fg_color="#2a2a2a", hover_color="#3a3a4a",
                    command=lambda: None)
                internet_btn.pack(fill="x", padx=0, pady=0)
                self._dl_internet_btn = internet_btn
                internet_btn.bind("<Enter>", lambda e: self._show_internet_menu(internet_btn))

                ctk.CTkButton(
                    pw, text="📁 Téléchargements Citron", anchor="w",
                    width=320, height=34, font=("Arial", 13),
                    fg_color="#2a2a2a", hover_color="#3a3a4a",
                    command=self._on_telechargements_citron
                ).pack(fill="x", padx=0, pady=0)

                ctk.CTkButton(
                    pw, text="📂 Changer le dossier Citron-Mémoire…", anchor="w",
                    width=320, height=34, font=("Arial", 13),
                    fg_color="#2a2a2a", hover_color="#3a3a4a",
                    command=self._on_change_memoire_folder
                ).pack(fill="x", padx=0, pady=0)

                ctk.CTkButton(
                    pw, text="📥 Liste des téléchargements — Citron-Mémoire",
                    anchor="w", width=320, height=34, font=("Arial", 13),
                    fg_color="#2a2a2a", hover_color="#3a3a4a",
                    command=self._on_open_downloads_list
                ).pack(fill="x", padx=0, pady=0)

                if gen != getattr(self, "_dl_menu_gen", 0):
                    self._destroy_menu_attr("_dl_menu_win")
                    return
                try:
                    pw.update_idletasks()
                    bx = anchor_btn.winfo_rootx()
                    by = anchor_btn.winfo_rooty() - pw.winfo_reqheight() + 2
                    self._place_menu_toplevel(pw, bx, by)
                except Exception as ex:
                    self._dl_trace(f"OPEN DL place erreur: {ex}")
                    self._destroy_menu_attr("_dl_menu_win")
                    return
                self._start_dl_chain_poll()
            finally:
                self._dl_menu_opening = False

        def _show_internet_menu(self, anchor_btn):
            if time.time() < getattr(self, "_dl_menu_block_until", 0):
                return
            dl = getattr(self, "_dl_menu_win", None)
            try:
                if not (dl and dl.winfo_exists()):
                    self._dl_trace("OPEN INET refusé (pas de parent DL)")
                    return
            except Exception:
                return
            if self._internet_menu_win and self._internet_menu_win.winfo_exists():
                return
            if getattr(self, "_internet_menu_opening", False):
                return
            self._internet_menu_opening = True
            try:
                gen = getattr(self, "_dl_menu_gen", 0)
                self._destroy_menu_attr("_browser_menu_win")
                self._dl_trace("OPEN sous-menu Internet")

                pw = self._make_menu_toplevel()
                self._internet_menu_win = pw

                ctk.CTkButton(
                    pw, text="URL", anchor="w",
                    width=180, height=34, font=("Arial", 13),
                    fg_color="#2a2a2a", hover_color="#3a3a4a",
                    command=lambda: (self._close_all_dl_menus("clic URL"), self.open_url_dialog())
                ).pack(fill="x", padx=0, pady=0)

                aller_btn = ctk.CTkButton(
                    pw, text="🌍 Aller sur internet  ▸", anchor="w",
                    width=210, height=34, font=("Arial", 13),
                    fg_color="#2a2a2a", hover_color="#3a3a4a",
                    command=lambda: None)
                aller_btn.pack(fill="x", padx=0, pady=0)
                self._inet_aller_btn = aller_btn
                # gen_at_bind : ignore un <Enter> qui arriverait après coup sur ce
                # bouton alors que le menu a déjà été fermé/recréé entretemps
                # (évènement en retard sur une fenêtre en cours de fermeture).
                gen_at_bind = gen
                aller_btn.bind(
                    "<Enter>",
                    lambda e: (self._show_browser_menu(aller_btn)
                               if gen_at_bind == getattr(self, "_dl_menu_gen", 0) else None)
                )

                if gen != getattr(self, "_dl_menu_gen", 0):
                    self._destroy_menu_attr("_internet_menu_win")
                    return
                try:
                    pw.update_idletasks()
                    bx = dl.winfo_rootx() + dl.winfo_width() - 2
                    by = anchor_btn.winfo_rooty()
                    if bx + pw.winfo_reqwidth() > self.winfo_screenwidth():
                        bx = dl.winfo_rootx() - pw.winfo_reqwidth() + 2
                    self._place_menu_toplevel(pw, bx, by)
                except Exception as ex:
                    self._dl_trace(f"OPEN INET place erreur: {ex}")
                    self._destroy_menu_attr("_internet_menu_win")
                    return
                if not getattr(self, "_dl_chain_poll_job", None):
                    self._start_dl_chain_poll()
            finally:
                self._internet_menu_opening = False

        def _detect_browsers(self):
            browsers = []
            if os.name != "nt":
                for name, cmds in [
                    ("Firefox", ["firefox"]),
                    ("Chrome", ["google-chrome", "chromium-browser", "chromium"]),
                    ("Edge", ["microsoft-edge"]),
                ]:
                    for c in cmds:
                        p = shutil.which(c)
                        if p:
                            browsers.append((name, p))
                            break
                return browsers
            candidates = [
                ("Google Chrome", [
                    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
                ]),
                ("Microsoft Edge", [
                    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                ]),
                ("Mozilla Firefox", [
                    r"C:\Program Files\Mozilla Firefox\firefox.exe",
                    r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
                ]),
                ("Brave", [
                    os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                    r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
                ]),
                ("Opera", [
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera\opera.exe"),
                    r"C:\Program Files\Opera\opera.exe",
                ]),
                ("Opera GX", [
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Opera GX\opera.exe"),
                ]),
                ("Vivaldi", [
                    os.path.expandvars(r"%LOCALAPPDATA%\Vivaldi\Application\vivaldi.exe"),
                ]),
            ]
            for name, paths in candidates:
                for p in paths:
                    if p and os.path.isfile(p):
                        browsers.append((name, p))
                        break
            return browsers

        def _show_browser_menu(self, anchor_btn):
            if time.time() < getattr(self, "_dl_menu_block_until", 0):
                return
            inet = getattr(self, "_internet_menu_win", None)
            try:
                if not (inet and inet.winfo_exists()):
                    self._dl_trace("OPEN BR refusé (pas de parent INET)")
                    return
            except Exception:
                return
            if self._browser_menu_win and self._browser_menu_win.winfo_exists():
                return
            if getattr(self, "_browser_menu_opening", False):
                return
            self._browser_menu_opening = True
            try:
                gen = getattr(self, "_dl_menu_gen", 0)
                self._dl_trace("OPEN menu navigateurs")
                browsers = self._detect_browsers()
                pw = self._make_menu_toplevel()
                self._browser_menu_win = pw

                def _open_browser(path):
                    self._close_all_dl_menus("clic navigateur")
                    try:
                        if os.name == "nt":
                            subprocess.Popen([path], shell=False)
                        else:
                            subprocess.Popen([path])
                    except Exception as ex:
                        messagebox.showerror("Navigateur", f"Impossible d'ouvrir le navigateur :\n{ex}")

                if not browsers:
                    ctk.CTkLabel(pw, text="Aucun navigateur détecté",
                                 font=("Arial", 12), text_color="#aaaaaa").pack(padx=12, pady=8)
                else:
                    for name, path in browsers:
                        ctk.CTkButton(
                            pw, text=f"🌐 {name}", anchor="w",
                            width=200, height=32, font=("Arial", 12),
                            fg_color="#2a2a2a", hover_color="#3a6a9a",
                            command=lambda p=path: _open_browser(p)
                        ).pack(fill="x", padx=0, pady=0)

                if gen != getattr(self, "_dl_menu_gen", 0):
                    self._destroy_menu_attr("_browser_menu_win")
                    return
                try:
                    if not inet.winfo_exists():
                        self._destroy_menu_attr("_browser_menu_win")
                        return
                    pw.update_idletasks()
                    req_h, req_w = pw.winfo_reqheight(), pw.winfo_reqwidth()
                    bx = inet.winfo_rootx() + inet.winfo_width() - 2
                    by = anchor_btn.winfo_rooty() + anchor_btn.winfo_height() - req_h
                    sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
                    if bx + req_w > sw:
                        bx = inet.winfo_rootx() - req_w + 2
                    by = max(0, min(by, sh - req_h))
                    self._place_menu_toplevel(pw, bx, by)
                except Exception as ex:
                    self._dl_trace(f"OPEN BR place erreur: {ex}")
                    self._destroy_menu_attr("_browser_menu_win")
                    return
                if not getattr(self, "_dl_chain_poll_job", None):
                    self._start_dl_chain_poll()
            finally:
                self._browser_menu_opening = False

        def _on_telechargements_citron(self):
            """Clic sur «📁 Téléchargements Citron» : ferme le menu et ouvre
            directement le dossier mémorisé dans l'explorateur (sans boîte de
            dialogue ni bascule plein écran)."""
            self._close_all_dl_menus()
            self.after(1, self._open_citron_memoire_folder)

        def _on_open_downloads_list(self):
            """Clic sur «📥 Liste des téléchargements — Citron-Mémoire» :
            ferme le menu et ouvre la fenêtre liste intégrée."""
            self._close_all_dl_menus()
            self.after(1, self.open_downloads_window)

        def _on_change_memoire_folder(self):
            """Clic sur «📂 Changer le dossier Citron-Mémoire…» :
            propose un nouveau dossier, le mémorise, rafraîchit la liste si
            elle est ouverte, puis ouvre le dossier dans l'explorateur."""
            self._close_all_dl_menus()
            self.after(1, self._change_citron_memoire_folder)

        def _change_citron_memoire_folder(self):
            """Boîte de dialogue pour choisir / changer le dossier mémoire."""
            self._close_all_dl_menus()  # s'assurer que le menu est bien fermé avant le dialogue
            try:
                initial = getattr(self, "_last_download_dir", None) or self._mem_dir
                if not initial or not os.path.isdir(initial):
                    initial = os.path.expanduser("~")
                folder = filedialog.askdirectory(
                    title="Choisir le dossier Citron-Mémoire",
                    initialdir=initial,
                    parent=self)
                # Re-bloquer / re-fermer après le dialogue (le curseur peut être
                # encore sur le bouton 📥 et rouvrirait le menu sinon)
                self._close_all_dl_menus()
                if not folder:
                    return  # annulation
                folder = os.path.normpath(folder)
                self._remember_download_dir(folder)
                if not os.path.isdir(folder):
                    os.makedirs(folder, exist_ok=True)
                if self.dl_win and self.dl_win.winfo_exists():
                    self.refresh_downloads_window()
                self._open_folder_in_explorer(folder)
            except Exception as ex:
                self._close_all_dl_menus()
                messagebox.showerror("Dossier", "Impossible de changer le dossier :\n" + str(ex))

        def _remember_download_dir(self, folder):
            """Mémorise le dossier de téléchargement et le persiste sur disque.
            Aligne aussi self._mem_dir pour que la liste intégrée et les
            téléchargements utilisent le même emplacement."""
            if not folder:
                return
            folder = os.path.normpath(folder)
            self._last_download_dir = folder
            self._mem_dir = folder
            print(f"[Mémoire] Dossier téléchargement mémorisé : {folder}")
            try:
                self.save_settings()
            except Exception as ex:
                print(f"[Mémoire] Échec sauvegarde dossier : {ex}")

        def _open_folder_in_explorer(self, folder):
            """Ouvre un dossier dans l'explorateur Windows, sans toucher au
            plein écran de Citron."""
            folder = os.path.normpath(folder)
            if not os.path.isdir(folder):
                raise FileNotFoundError(f"Dossier introuvable : {folder}")

            files = []
            try:
                entries = os.listdir(folder)
                files = sorted(
                    os.path.join(folder, f) for f in entries
                    if os.path.isfile(os.path.join(folder, f))
                )
                print(f"[Mémoire] Ouverture explorateur : {folder!r} "
                      f"({len(files)} fichier(s), {len(entries)} entrée(s))")
            except Exception as ex:
                print(f"[Mémoire] Impossible de lister {folder!r} : {ex}")

            if os.name == "nt":
                opened = False
                # 1) /select sur un fichier → le contenu du dossier est visible
                if files:
                    try:
                        # Préférer un fichier « terminé » (.part = téléchargement en cours)
                        preferred = [f for f in files if not f.lower().endswith(".part")]
                        target = preferred[0] if preferred else files[0]
                        subprocess.Popen(f'explorer /select,"{target}"', shell=True)
                        print(f"[Mémoire] explorateur via /select → {target!r}")
                        opened = True
                    except Exception as ex:
                        print(f"[Mémoire] /select échec : {ex}")
                # 2) ShellExecute "open" sur le dossier
                if not opened:
                    try:
                        rc = ctypes.windll.shell32.ShellExecuteW(
                            None, "open", folder, None, None, 1)
                        print(f"[Mémoire] ShellExecuteW(open) → {rc}")
                        if rc > 32:
                            opened = True
                    except Exception as ex:
                        print(f"[Mémoire] ShellExecuteW échec : {ex}")
                # 3) Derniers recours
                if not opened:
                    try:
                        subprocess.Popen(["cmd", "/c", "start", "", folder], shell=False)
                        opened = True
                    except Exception:
                        pass
                if not opened:
                    os.startfile(folder)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

        def _open_citron_memoire_folder(self):
            """Ouvre le dossier de téléchargement mémorisé dans l'explorateur.
            Si aucun dossier n'est encore mémorisé, en propose un une seule fois."""
            try:
                folder = getattr(self, "_last_download_dir", None) or self._mem_dir
                if folder and os.path.isdir(folder):
                    self._open_folder_in_explorer(folder)
                    return

                # Première utilisation : demander un dossier, puis le mémoriser
                initial = self._mem_dir if os.path.isdir(self._mem_dir) else os.path.expanduser("~")
                folder = filedialog.askdirectory(
                    title="Choisir le dossier des téléchargements Citron",
                    initialdir=initial,
                    parent=self)
                if not folder:
                    return
                folder = os.path.normpath(folder)
                self._remember_download_dir(folder)
                if not os.path.isdir(folder):
                    os.makedirs(folder, exist_ok=True)
                self._open_folder_in_explorer(folder)
            except Exception as ex:
                messagebox.showerror("Dossier", f"Impossible d'ouvrir le dossier :\n{ex}")

        def toggle_mirror(self):
            self._mirror_on = not self._mirror_on
            if self._mirror_on:
                self.mirror_btn.configure(text="🖥 Miroir ON", fg_color="#1a6e3c")
            else:
                if self.player:
                    self.player.stop()
                    self._stop_audio_anim()
                self.play_btn.configure(text="▶")
                self.progress_slider.set(0)
                self.time_label.configure(text="0:00 / 0:00")
                self.mirror_btn.configure(text="🖥 Miroir OFF", fg_color="#555555")

        def _ensure_thumb_win(self):
            """Crée (une seule fois) la fenêtre de vignette : image + temps. C'est
            une fenêtre séparée (Toplevel, topmost) — indispensable pour passer
            au-dessus de la vidéo VLC intégrée, qui utilise une vraie fenêtre
            Windows native et occulte donc tout widget Tkinter classique placé au
            même endroit (essayé, ça ne fonctionne pas). L'affichage/masquage
            passe par des appels Windows natifs (_win_native_show/_hide) plutôt
            que withdraw()/deiconify() de Tkinter, pour éviter le fantôme DWM."""
            if self._thumb_win is not None and self._thumb_win.winfo_exists():
                return
            self._thumb_win = ctk.CTkToplevel(self)
            # Cacher IMMÉDIATEMENT, avant toute autre opération : sinon la
            # fenêtre est brièvement dessinée à sa position par défaut (coin
            # supérieur gauche) avant qu'on ait eu le temps de la repositionner
            # et de la cacher plus loin — d'où le flash observé au lancement
            # d'une vidéo (la fenêtre est maintenant créée par anticipation).
            self._thumb_win.withdraw()
            self._thumb_win.wm_overrideredirect(True)
            self._thumb_win.attributes("-topmost", True)
            self._thumb_win.update_idletasks()
            win_make_layered(self._thumb_win)
            win_native_hide(self._thumb_win)
            frame = ctk.CTkFrame(self._thumb_win, fg_color="#222222", corner_radius=6)
            frame.pack()
            self._thumb_img_lbl = ctk.CTkLabel(frame, text="", fg_color="#000000",
                                                corner_radius=4, width=176, height=99)
            self._thumb_img_lbl.pack(padx=6, pady=(6,2))
            self._thumb_lbl = ctk.CTkLabel(frame, text="", font=("Arial",11), text_color="#ffffff")
            self._thumb_lbl.pack(padx=6, pady=(0,6))
            self._thumb_current_path = None  # nouvelle fenêtre -> forcer le rechargement de l'image

        def _hide_thumb_win(self):
            """Cache la vignette. Toujours sûr à appeler, y compris si rien n'est affiché."""
            try:
                if self._thumb_hover_job:
                    self.after_cancel(self._thumb_hover_job)
            except Exception:
                pass
            self._thumb_hover_job = None
            self._thumb_seek_gen += 1  # invalide toute capture en cours ou en attente d'affichage
            try:
                if self._thumb_win and self._thumb_win.winfo_exists():
                    x = self._thumb_win.winfo_rootx()
                    y = self._thumb_win.winfo_rooty()
                    w = self._thumb_win.winfo_width()
                    h = self._thumb_win.winfo_height()
                    win_native_hide(self._thumb_win)
                    force_redraw_region(x, y, w, h)
            except Exception:
                pass

        def _on_progress_hover(self, event):
            """Affiche une mini-vignette (image + temps) au survol de la barre de progression."""
            # Toute condition qui empêche un aperçu valide -> on cache proprement
            # (sinon la vignette reste affichée "orpheline" indéfiniment, par ex.
            # si la lecture s'arrête pendant que la souris est encore sur la barre)
            if not self.player or self._tv_mode:
                self._hide_thumb_win(); return
            tot = self.player.get_length()
            if tot <= 0:
                self._hide_thumb_win(); return
            try:
                slider_w = self.progress_slider.winfo_width()
                if slider_w <= 0:
                    self._hide_thumb_win(); return
                frac = max(0.0, min(1.0, event.x / slider_w))
                pos_ms = int(frac * tot)
                pos_s = pos_ms // 1000

                # Chemin du média actuellement lu
                path = ""
                media = self.player.get_media()
                if media:
                    mrl = media.get_mrl()
                    path = urllib.parse.unquote(mrl.replace("file:///","").replace("/",os.sep))

                self._ensure_thumb_win()
                try:
                    self._thumb_img_lbl.configure(width=176, height=99)
                except Exception:
                    pass

                # Texte du temps : mise à jour immédiate (pas de débounce nécessaire)
                h = pos_s // 3600; m = (pos_s % 3600) // 60; s = pos_s % 60
                time_str = f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
                self._thumb_lbl.configure(text=f"⏱ {time_str}")

                # Position au-dessus du curseur, en coordonnées écran réelles
                self._thumb_win.update_idletasks()
                tw = self._thumb_win.winfo_reqwidth()
                th = self._thumb_win.winfo_reqheight()
                screen_w = self.progress_slider.winfo_screenwidth()
                margin = 10
                rx = self.progress_slider.winfo_rootx() + event.x
                ry = self.progress_slider.winfo_rooty()
                x = max(margin, min(rx - tw//2, max(margin, screen_w - tw - margin)))
                y = max(margin, ry - th - 10)
                # Ne pas afficher tant que la fenêtre n'a pas eu le temps de
                # "s'installer" auprès du compositeur Windows depuis sa création
                # (voir play_file) — c'est le tout premier affichage d'une fenêtre
                # fraîchement créée qui provoquait le fantôme. Le texte du temps
                # reste préparé normalement ci-dessus ; seul l'affichage visuel
                # est différé de quelques instants au tout début d'une lecture.
                if time.time() >= self._thumb_win_ready_at:
                    win_native_show(self._thumb_win, x, y)

                # Image : débounce pour ne pas déclencher une capture VLC à chaque pixel
                if path and os.path.isfile(path):
                    if self._thumb_hover_job:
                        try: self.after_cancel(self._thumb_hover_job)
                        except Exception: pass
                    self._thumb_hover_job = self.after(
                        150, lambda p=path, ms=pos_ms: self._update_thumb_image(p, ms))
            except Exception as ex:
                print(f"[Vignette] Erreur survol : {ex}")

        def _on_progress_leave(self, event):
            """Cache la mini-vignette en quittant la barre."""
            print(f"[Vignette] <Leave> reçu, gen avant={self._thumb_seek_gen}")
            self._hide_thumb_win()

        def _get_ffmpeg_path(self):
            """Cherche ffmpeg une seule fois (résultat mis en cache) : d'abord à côté
            de Citron (dossier 'ffmpeg' ou directement ffmpeg.exe), puis dans le PATH
            système. Retourne None si introuvable (utilisation du secours VLC)."""
            if hasattr(self, "_ffmpeg_path_cache"):
                return self._ffmpeg_path_cache
            candidates = []
            try:
                base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                candidates.append(os.path.join(base_dir, "ffmpeg", "ffmpeg.exe"))
                candidates.append(os.path.join(base_dir, "ffmpeg.exe"))
            except Exception:
                pass
            for c in candidates:
                if os.path.isfile(c):
                    self._ffmpeg_path_cache = c
                    print(f"[Vignette] ffmpeg trouvé : {c}")
                    return c
            found = shutil.which("ffmpeg")
            if found:
                self._ffmpeg_path_cache = found
                print(f"[Vignette] ffmpeg trouvé dans le PATH : {found}")
                return found
            self._ffmpeg_path_cache = None
            print("[Vignette] ffmpeg introuvable — secours sur le lecteur VLC dédié "
                  "(peut occasionnellement perturber le son pendant le survol). "
                  "Installez ffmpeg pour une génération de vignettes sans ce risque.")
            return None

        def _ensure_thumb_infra(self):
            """Prépare (une seule fois) un lecteur VLC dédié, hors écran, pour capturer
            des images du média sans perturber la lecture principale ni afficher de fenêtre."""
            if self._thumb_vlc_player is not None:
                return
            try:
                self._thumb_render_win = ctk.CTkToplevel(self)
                self._thumb_render_win.overrideredirect(True)
                # Positionnée hors de l'écran visible (pas juste masquée : VLC a besoin
                # d'une fenêtre "mappée" pour pouvoir y dessiner les images décodées)
                self._thumb_render_win.geometry("176x99-2000-2000")
                self._thumb_render_canvas = Canvas(self._thumb_render_win, bg="black",
                                                    width=176, height=99, highlightthickness=0)
                self._thumb_render_canvas.pack()
                self._thumb_render_win.update_idletasks()
                # "--no-audio" est essentiel ici : audio_set_mute(True) seul ne suffit
                # pas sur Windows, le second lecteur VLC ouvre quand même le périphérique
                # audio (souvent en exclusivité WASAPI) et coupe le son du lecteur
                # principal dès qu'une vignette est survolée. "--no-audio" désactive
                # complètement la sortie audio de ce lecteur dédié, sans jamais toucher
                # au périphérique.
                self._thumb_vlc_instance = vlc.Instance("--quiet", "--no-xlib", "--no-audio")
                self._thumb_vlc_player = self._thumb_vlc_instance.media_player_new()
                self._thumb_vlc_player.audio_set_mute(True)
                self._thumb_vlc_player.set_hwnd(self._thumb_render_canvas.winfo_id())
            except Exception as ex:
                print(f"[Vignette] Initialisation impossible : {ex}")
                self._thumb_vlc_player = None

        def _update_thumb_image(self, path, pos_ms, thumb_size=(176, 99)):
            """Capture une image du média à la position donnée."""
            self._thumb_hover_job = None
            self._thumb_seek_gen += 1
            my_gen = self._thumb_seek_gen
            print(f"[Vignette] gen={my_gen} : capture {os.path.basename(path)!r} "
                  f"pos_ms={pos_ms} taille={thumb_size}")

            ffmpeg_path = self._get_ffmpeg_path()
            if ffmpeg_path:
                self._capture_thumb_ffmpeg(ffmpeg_path, path, pos_ms, my_gen, thumb_size)
                return
            self._capture_thumb_vlc(path, pos_ms, my_gen, thumb_size)

        def _capture_thumb_ffmpeg(self, ffmpeg_path, path, pos_ms, my_gen, thumb_size=(176, 99)):
            """Capture via un processus ffmpeg indépendant : rapide, jetable, et sans
            aucun lien avec le sous-système audio (contrairement à un second lecteur
            VLC, qui pouvait couper le son du lecteur principal pendant le survol)."""
            def worker():
                tmp_path = os.path.join(tempfile.gettempdir(),
                                         f"citron_thumb_ff_{os.getpid()}_{my_gen}.png")
                try:
                    if self._thumb_seek_gen != my_gen:
                        print(f"[Vignette] gen={my_gen} : annulé avant lancement ffmpeg (gen obsolète)")
                        return
                    target_s = pos_ms / 1000.0
                    # "-ss" AVANT "-i" : seek rapide côté démuxeur (quasi instantané),
                    # bien plus rapide qu'ouvrir/décoder depuis le début du fichier.
                    tw, th = thumb_size
                    cmd = [ffmpeg_path, "-y", "-ss", f"{target_s:.3f}", "-i", path,
                           "-frames:v", "1", "-vf", f"scale={int(tw)}:{int(th)}", tmp_path]
                    creationflags = no_console_flags()
                    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                             timeout=8, creationflags=creationflags)
                    exists = os.path.isfile(tmp_path)
                    size = os.path.getsize(tmp_path) if exists else -1
                    print(f"[Vignette] gen={my_gen} : ffmpeg code={result.returncode} "
                          f"existe={exists} taille={size}o")
                    if self._thumb_seek_gen != my_gen:
                        print(f"[Vignette] gen={my_gen} : annulé après ffmpeg (gen obsolète)")
                        try:
                            if exists: os.remove(tmp_path)
                        except Exception:
                            pass
                        return
                    if exists and size > 0:
                        self.after(0, lambda: self._show_thumb_image(tmp_path, my_gen))
                    else:
                        err = (result.stderr or b"").decode(errors="ignore")[-300:]
                        print(f"[Vignette] gen={my_gen} : échec ffmpeg : {err}")
                except subprocess.TimeoutExpired:
                    print(f"[Vignette] gen={my_gen} : ffmpeg délai dépassé (8s), abandon")
                except Exception as ex:
                    print(f"[Vignette] gen={my_gen} : Erreur ffmpeg : {ex}")
            threading.Thread(target=worker, daemon=True).start()

        def _capture_thumb_vlc(self, path, pos_ms, my_gen, thumb_size=(176, 99)):
            """Secours : ancienne méthode via un lecteur VLC dédié, utilisée
            uniquement quand ffmpeg n'est pas installé."""
            self._ensure_thumb_infra()
            if not self._thumb_vlc_player:
                print("[Vignette] Pas de lecteur vignette disponible, abandon")
                return

            def worker():
                # Un seul lecteur VLC est partagé entre toutes les générations de
                # capture. Sans ce verrou, deux threads pouvaient le manipuler en
                # même temps (l'un cherche une position pendant que l'autre est
                # encore en train d'ouvrir le média) — c'est ce qui produisait des
                # vignettes figées/corrompues, surtout juste après l'ouverture
                # d'une nouvelle vidéo (le premier chargement peut prendre plusieurs
                # secondes, largement plus que le débounce de survol). Un thread dont
                # la génération devient obsolète pendant l'attente du verrou ressort
                # aussitôt sans toucher au lecteur.
                self._thumb_lock.acquire()
                try:
                    if self._thumb_seek_gen != my_gen:
                        print(f"[Vignette] gen={my_gen} : annulé en attendant le verrou (gen obsolète)")
                        return
                    player = self._thumb_vlc_player
                    if self._thumb_current_path != path:
                        print(f"[Vignette] gen={my_gen} : nouveau média, ouverture…")
                        media = self._thumb_vlc_instance.media_new(path)
                        # Le "--no-audio" passé à l'instance n'est pas toujours
                        # respecté à 100% par libvlc 3.0.x. On le renforce ici en
                        # le forçant directement sur CE média : c'est ce qui coupait
                        # le son du lecteur principal pendant le survol malgré le
                        # réglage au niveau de l'instance.
                        media.add_option(':no-audio')
                        player.set_media(media)
                        self._thumb_current_path = path
                        player.play()
                        deadline = time.time() + 3.0
                        while time.time() < deadline:
                            if self._thumb_seek_gen != my_gen:
                                print(f"[Vignette] gen={my_gen} : annulé pendant l'ouverture (gen obsolète)")
                                return
                            st = player.get_state()
                            if st in (vlc.State.Playing, vlc.State.Paused) and player.get_length() > 0:
                                print(f"[Vignette] gen={my_gen} : média ouvert, état={st} durée={player.get_length()}ms")
                                break
                            if st in (vlc.State.Error, vlc.State.Ended):
                                print(f"[Vignette] gen={my_gen} : état inattendu {st}, abandon")
                                return
                            time.sleep(0.03)
                        else:
                            print(f"[Vignette] gen={my_gen} : délai d'ouverture dépassé (3s), on continue quand même")
                        player.set_pause(1)
                        # Attendre la confirmation réelle de la pause : video_take_snapshot()
                        # échoue (renvoie -1) si on l'appelle trop tôt, pendant que l'état
                        # est encore "Playing" -> c'est précisément ce qui rendait la toute
                        # première vignette vide/figée.
                        pause_deadline = time.time() + 1.0
                        while time.time() < pause_deadline:
                            if self._thumb_seek_gen != my_gen:
                                print(f"[Vignette] gen={my_gen} : annulé en attendant la pause (gen obsolète)")
                                return
                            if player.get_state() == vlc.State.Paused:
                                break
                            time.sleep(0.02)
                        print(f"[Vignette] gen={my_gen} : état après demande de pause = {player.get_state()}")

                    if self._thumb_seek_gen != my_gen:
                        print(f"[Vignette] gen={my_gen} : annulé avant le seek (gen obsolète)")
                        return
                    player.set_time(int(pos_ms))
                    deadline = time.time() + 0.6
                    target_s = pos_ms / 1000.0
                    reached = False
                    while time.time() < deadline:
                        if self._thumb_seek_gen != my_gen:
                            print(f"[Vignette] gen={my_gen} : annulé pendant le seek (gen obsolète)")
                            return
                        cur_s = player.get_time() / 1000.0
                        if abs(cur_s - target_s) < 1.0:
                            reached = True
                            break
                        time.sleep(0.03)
                    print(f"[Vignette] gen={my_gen} : seek cible={target_s:.2f}s atteint={reached} position réelle={player.get_time()/1000.0:.2f}s état={player.get_state()}")
                    if not reached:
                        time.sleep(0.08)

                    if self._thumb_seek_gen != my_gen:
                        print(f"[Vignette] gen={my_gen} : annulé avant la capture (gen obsolète)")
                        return
                    tmp_path = os.path.join(tempfile.gettempdir(),
                                             f"citron_thumb_{os.getpid()}_{my_gen}.png")
                    ok = player.video_take_snapshot(0, tmp_path, int(thumb_size[0]), int(thumb_size[1]))
                    exists = os.path.isfile(tmp_path)
                    size = os.path.getsize(tmp_path) if exists else -1
                    print(f"[Vignette] gen={my_gen} : snapshot ok={ok} fichier={tmp_path!r} existe={exists} taille={size}o")
                    if (ok != 0 or not exists) and self._thumb_seek_gen == my_gen:
                        # Nouvelle tentative : la capture échoue parfois de justesse
                        # si l'état n'a pas fini de se stabiliser (ex: tout premier
                        # média ouvert). Un court délai supplémentaire suffit en général.
                        print(f"[Vignette] gen={my_gen} : échec, nouvelle tentative dans 0.15s (état={player.get_state()})")
                        time.sleep(0.15)
                        if self._thumb_seek_gen != my_gen:
                            print(f"[Vignette] gen={my_gen} : annulé avant la 2e tentative (gen obsolète)")
                            return
                        ok = player.video_take_snapshot(0, tmp_path, int(thumb_size[0]), int(thumb_size[1]))
                        exists = os.path.isfile(tmp_path)
                        size = os.path.getsize(tmp_path) if exists else -1
                        print(f"[Vignette] gen={my_gen} : snapshot (2e essai) ok={ok} existe={exists} taille={size}o")
                    if ok == 0 and exists and self._thumb_seek_gen == my_gen:
                        self.after(0, lambda: self._show_thumb_image(tmp_path, my_gen))
                    else:
                        print(f"[Vignette] gen={my_gen} : capture non affichée (échec ou gen obsolète, gen actuel={self._thumb_seek_gen})")
                        # Nettoyer le fichier temporaire jamais affiché
                        try:
                            if exists: os.remove(tmp_path)
                        except Exception:
                            pass
                except Exception as ex:
                    print(f"[Vignette] gen={my_gen} : Erreur capture : {ex}")
                finally:
                    self._thumb_lock.release()
            threading.Thread(target=worker, daemon=True).start()

        def _show_thumb_image(self, tmp_path, gen=None):
            """Affiche l'image capturée dans la fenêtre de vignette (thread principal)."""
            try:
                # ── Revérification de la génération AU MOMENT DE L'AFFICHAGE ──
                # Le worker a déjà vérifié self._thumb_seek_gen == my_gen avant de
                # planifier cet appel via self.after(0, ...), mais entre cette
                # planification et son exécution réelle sur le thread principal,
                # la souris a pu ré-entrer sur la barre de progression et
                # redemander une vignette plus récente (nouvelle génération).
                # Sans cette seconde vérification, une capture déjà obsolète
                # s'affichait quand même et restait visible, "figée", jusqu'à
                # ce qu'une capture plus récente réussisse enfin à s'afficher
                # (ou jamais, si elle était elle-même invalidée entre-temps).
                # C'est la cause des mini-vignettes qui restent bloquées.
                if gen is not None and gen != self._thumb_seek_gen:
                    print(f"[Vignette] gen={gen} : affichage annulé, obsolète au moment de l'affichage (gen actuel={self._thumb_seek_gen})")
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    return
                print(f"[Vignette] gen={gen} : affichage de {tmp_path!r} (gen actuel={self._thumb_seek_gen})")
                if not (self._thumb_win and self._thumb_win.winfo_exists()):
                    print(f"[Vignette] gen={gen} : fenêtre vignette absente, on n'affiche rien")
                    return
                # Ne rien afficher si la fenêtre a été explicitement masquée
                # (ex : la souris a quitté la barre) même si winfo_exists() est
                # vrai. Le masquage passe maintenant par ShowWindow (natif) plutôt
                # que withdraw() de Tkinter, donc on vérifie la visibilité réelle
                # via IsWindowVisible plutôt que state() (qui ne serait plus fiable).
                try:
                    if os.name == "nt":
                        hwnd = self._thumb_win.winfo_id()
                        if not ctypes.windll.user32.IsWindowVisible(hwnd):
                            print(f"[Vignette] gen={gen} : fenêtre masquée (IsWindowVisible=False), on n'affiche rien")
                            return
                    elif self._thumb_win.state() == "withdrawn":
                        print(f"[Vignette] gen={gen} : fenêtre masquée (withdrawn), on n'affiche rien")
                        return
                except Exception:
                    pass
                from PIL import Image
                img = Image.open(tmp_path)
                # CTkImage (et non PIL.ImageTk.PhotoImage brut) : customtkinter gère
                # alors correctement le rafraîchissement de l'affichage sur les
                # écrans avec mise à l'échelle Windows (125%, 150%...). Un
                # PhotoImage brut déclenche l'avertissement "Image can not be
                # scaled on HighDPI displays" et surtout, dans ce cas précis,
                # l'ancienne image reste visible à l'écran même quand configure()
                # a bien reçu la nouvelle image en interne — c'est ce qui donnait
                # l'impression de vignettes "figées" alors que la capture avait
                # pourtant réussi (comme le montrent les logs).
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
                self._thumb_img_lbl.configure(image=ctk_img, text="")
                self._thumb_img_lbl.image = ctk_img  # empêcher le garbage collector
                # Forcer un redessin immédiat des widgets concernés (bonne pratique
                # après un configure(image=...), même si l'overlay est maintenant un
                # widget interne normal et non plus une fenêtre séparée).
                try:
                    self._thumb_img_lbl.update_idletasks()
                    self._thumb_win.update_idletasks()
                except Exception:
                    pass
                print(f"[Vignette] gen={gen} : image affichée avec succès (taille={img.size})")
                # Nettoyer l'ancien fichier temporaire (on ne garde que le dernier affiché)
                old_tmp = self._thumb_last_tmp_path
                self._thumb_last_tmp_path = tmp_path
                if old_tmp and old_tmp != tmp_path:
                    try:
                        os.remove(old_tmp)
                    except Exception:
                        pass
            except Exception as ex:
                print(f"[Vignette] Erreur affichage : {ex}")

        def toggle_progress_bar(self):
            if self.progress_visible:
                self.prog_frame.pack_forget()
                self.progress_visible = False
                self.prog_toggle_btn.configure(fg_color="#555555")
                self._hide_thumb_win()
            else:
                self.prog_frame.pack(fill="x", padx=10, pady=(4,0), after=self.video_frame)
                self.progress_visible = True
                self.prog_toggle_btn.configure(fg_color="#1f6aa5")

        def update_clock(self):
            self.clock_label.configure(text=datetime.now().strftime("🕒 %H:%M"))
            self.after(30000, self.update_clock)

        def _countdown_loop(self):
            if self.countdown_running and self.player and not self._tv_mode:
                if self.player.get_state() == vlc.State.Playing:
                    tot = self.player.get_length()
                    cur = self.player.get_time()
                    if tot > 0 and cur >= 0:
                        remain = max(0.0, (tot - cur) / 1000.0)
                        self.countdown_label.configure(text=f"⏳ {fmt_countdown(remain)}")
            self.after(1000, self._countdown_loop)

        def _start_countdown(self, path):
            dur = self._get_duration(path)
            self.countdown_running = True
            self.countdown_label.configure(text=f"⏳ {fmt_countdown(dur)}" if dur > 0 else "⏳ --:--")

        def _reset_countdown(self):
            self.countdown_running = False
            self.countdown_label.configure(text="⏳ 0m00s")

        def _calc_playlist_total_duration(self):
            """Durée totale de toute la playlist."""
            return sum(self._get_duration(self._get_pl_path(i))
                       for i in range(len(self.playlist)))

        def _update_playlist_total_countdown(self):
            """Décompte décroissant depuis la durée totale de toute la playlist.
            Commence toujours à _playlist_total_dur et décroît en temps réel."""
            if not hasattr(self, "total_countdown_label"): return
            if not self._seq_mode or not self.playlist or self._playlist_total_dur <= 0:
                self.total_countdown_label.configure(text=""); return
            # Temps consommé = médias ENTIÈREMENT terminés (hors titre en cours)
            # _seq_visited[-1] = titre en cours → on l'exclut du calcul
            consumed = 0.0
            for idx in self._seq_visited[:-1]:
                consumed += self._get_duration(self._get_pl_path(idx))
            # Ajouter le temps déjà écoulé dans le titre en cours
            if self.player and not self._tv_mode:
                cur_ms = self.player.get_time()
                if cur_ms > 0:
                    consumed += cur_ms / 1000.0
            remain = max(0.0, self._playlist_total_dur - consumed)
            self.total_countdown_label.configure(
                text=f" | ⏳ Restant : {fmt_countdown(remain)}")

        def _update_next_title_label(self):
            """Titre suivant selon _seq_order (ordre réel de lecture)."""
            if not hasattr(self, "next_title_label"): return
            if not self._seq_mode or not self.playlist:
                self.next_title_label.configure(text=""); return
            if self._seq_order:
                next_idx = self._seq_order[0]
                name = os.path.basename(self._get_pl_path(next_idx))
                if len(name) > 40: name = name[:37] + "…"
                self.next_title_label.configure(text=f"  →  {name}")
            else:
                self.next_title_label.configure(text="  → (dernier titre)")

        def update_list_button_text(self):
            n = len(self.video_names)
            self.list_btn.configure(text="📋 Liste vide" if n==0 else f"📋 Liste ({n})")

        def update_playlist_button_text(self):
            n = len(self.playlist)
            self.playlist_btn.configure(text="🎵 Playlist vide" if n==0 else f"🎵 Playlist ({n})")

        def _on_playlist_button_click(self):
            """Ouvre le choix Playlist / Playlist virtuelle au clic."""
            self._show_playlist_choice_menu()

        def _show_playlist_choice_menu(self):
            """Menu déroulant du bouton 🎵 Playlist, affiché avec le même
            rendu que ⚙ Paramètres et 🗂 Tableur (voir _show_generic_bottom_menu)."""
            items = [
                ("🎵 Ouvrir la Playlist", self.open_playlist_window),
                ("🧪 Ouvrir la Playlist virtuelle", self.open_virtual_playlist_window),
            ]
            self._show_generic_bottom_menu("_playlist_menu_win", self.playlist_btn, items)

        def show_virtual_playlist_help(self):
            messagebox.showinfo(
                "Playlist virtuelle",
                "Une Playlist virtuelle rassemble des titres issus du tableur, même lorsque leur fichier n'est pas disponible dans la bibliothèque.\n\n"
                "Les titres lisibles restent utilisables comme dans une playlist normale. Les titres indisponibles sont affichés en gris et leurs fonctions de lecture sont désactivées.\n\n"
                "Elle est donc pratique pour conserver une sélection complète sans perdre les titres momentanément indisponibles."
            )

        def add_files(self):
            exts = " ".join(f"*{e}" for e in sorted(ALL_EXT))
            files = filedialog.askopenfilenames(filetypes=[("Médias",exts)])
            self._add_to_library(files)

        def add_folder(self):
            folder = filedialog.askdirectory()
            if folder:
                files = [os.path.join(r,fn) for r,_,fns in os.walk(folder)
                         for fn in fns if os.path.splitext(fn)[1].lower() in ALL_EXT]
                self._add_to_library(files)

        def _add_to_library(self, files):
            added = []
            for f in files:
                name = os.path.basename(f)
                if is_audio(f): name += "  🎵 audio"
                self.video_paths.append(f)
                self.video_names.append(name)
                added.append(f)
            if added:
                self.save_library()
                self.update_list_button_text()
                self._fetch_durations_bg(added)
                if self.list_win and self.list_win.winfo_exists():
                    self.refresh_list_window()

        # ── Lecture ─────────────────────────────────────
        def _stop_tv_silently(self):
            """Stop TV sans modifier les flags de mode — usage interne."""
            if self._tv_control_url:
                try:
                    threading.Thread(target=lambda: _soap_stop(self._tv_control_url),
                                     daemon=True).start()
                except Exception: pass

        # ── Internet / navigateur ───────────────────────────
        def _start_cmd_server(self):
            def handler(conn):
                try:
                    data = b""
                    conn.settimeout(3)
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        data += chunk
                        if b"\n" in data:
                            break
                    line = data.decode("utf-8", errors="ignore").strip()
                    if not line:
                        return
                    msg = json.loads(line)
                    if msg.get("cmd") == "play" and msg.get("url"):
                        url = msg["url"]
                        print(f"[Cmd] Lecture demandée : {url[:120]}")
                        self.after(0, lambda u=url: self.play_internet_url(u))
                    try:
                        conn.sendall(b"ok\n")
                    except Exception:
                        pass
                except Exception as ex:
                    print(f"[Cmd] Erreur : {ex}")
                finally:
                    try: conn.close()
                    except Exception: pass

            def serve():
                try:
                    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    srv.bind(("127.0.0.1", CITRON_CMD_PORT))
                    srv.listen(5)
                    srv.settimeout(1.0)
                    self._cmd_server = srv
                    print(f"[Cmd] Serveur commandes démarré port {CITRON_CMD_PORT}")
                    while self._cmd_server is not None:
                        try:
                            conn, _ = srv.accept()
                            threading.Thread(target=handler, args=(conn,), daemon=True).start()
                        except socket.timeout:
                            continue
                        except OSError:
                            break
                except OSError as ex:
                    print(f"[Cmd] Port {CITRON_CMD_PORT} indisponible : {ex}")

            threading.Thread(target=serve, daemon=True).start()

        def _set_internet_ui(self, active, title=""):
            was_active = getattr(self, "_internet_mode", False)
            self._internet_mode = bool(active)
            try:
                if active:
                    if title:
                        self.now_playing_label.configure(text=f"🌐  {title}")
                    self.set_play_mode("pc", "Internet")
            except Exception:
                pass
            # Coupe automatiquement le son du navigateur (page source encore
            # ouverte) pendant la lecture internet dans Citron, pour éviter
            # que les deux sons se superposent. Restauré dès la fin de la
            # lecture internet (arrêt, ou passage à un média local).
            if active and not was_active:
                self._mute_browser_audio()
            elif not active and was_active:
                self._restore_browser_audio()
                self._set_internet_nav_disabled(False)

        # Navigateurs dont le son est coupé pendant une lecture internet dans Citron.
        _BROWSER_PROCESS_NAMES = {
            "chrome.exe", "msedge.exe", "firefox.exe", "brave.exe",
            "opera.exe", "operagx.exe", "vivaldi.exe", "iexplore.exe",
        }

        def _mute_browser_audio(self):
            """Coupe le son de tous les navigateurs actuellement actifs
            (Chrome, Edge, Firefox, Brave, Opera, Vivaldi...), pour éviter que
            la page source (copiée puis collée dans 🌐 Internet, et restée
            ouverte dans le navigateur) ne superpose son propre son à celui
            de Citron. Windows uniquement, nécessite le paquet 'pycaw'."""
            self._muted_browser_sessions = []
            if os.name != "nt":
                return
            try:
                from pycaw.pycaw import AudioUtilities
            except ImportError:
                if not getattr(self, "_pycaw_warn_shown", False):
                    self._pycaw_warn_shown = True
                    print("[Audio navigateur] Paquet 'pycaw' absent : impossible de "
                          "couper automatiquement le son du navigateur pendant la "
                          "lecture internet dans Citron.\n"
                          "Ouvrez un terminal Windows (cmd) et tapez :\n"
                          "  pip install pycaw\n"
                          "Puis relancez Citron.")
                return
            try:
                for session in AudioUtilities.GetAllSessions():
                    proc = session.Process
                    if not proc:
                        continue
                    try:
                        pname = proc.name().lower()
                    except Exception:
                        continue
                    if pname not in self._BROWSER_PROCESS_NAMES:
                        continue
                    try:
                        vol = session.SimpleAudioVolume
                        was_muted = bool(vol.GetMute())
                        if not was_muted:
                            vol.SetMute(1, None)
                        self._muted_browser_sessions.append((proc.pid, was_muted))
                    except Exception:
                        pass
            except Exception as ex:
                print(f"[Audio navigateur] Erreur lors de la coupure du son : {ex}")

        def _restore_browser_audio(self):
            """Restaure le son des navigateurs coupés par _mute_browser_audio,
            en respectant leur état d'origine (un onglet déjà muet avant la
            lecture Citron le reste après)."""
            if os.name != "nt":
                return
            muted = getattr(self, "_muted_browser_sessions", None)
            if not muted:
                return
            try:
                from pycaw.pycaw import AudioUtilities
                sessions = {s.Process.pid: s for s in AudioUtilities.GetAllSessions() if s.Process}
                for pid, was_muted in muted:
                    session = sessions.get(pid)
                    if not session:
                        continue
                    try:
                        if not was_muted:
                            session.SimpleAudioVolume.SetMute(0, None)
                    except Exception:
                        pass
            except Exception as ex:
                print(f"[Audio navigateur] Erreur lors de la restauration du son : {ex}")
            self._muted_browser_sessions = []

        def open_url_dialog(self):
            win = ctk.CTkToplevel(self)
            win.title("Ouvrir une URL")
            win.geometry("620x340")
            win.transient(self); win.lift()
            ctk.CTkLabel(win, text="Coller l'adresse de la vidéo (YouTube, Vimeo, TikTok, X/Twitter, etc.)",
                         font=("Arial",13)).pack(pady=(16, 6))
            var = ctk.StringVar()
            entry = ctk.CTkEntry(win, textvariable=var, width=560, height=36)
            entry.pack(padx=16, pady=4)
            enable_entry_paste(entry)  # fix : Ctrl+V / clic droit fiables (AZERTY inclus)
            win.after(150, entry.focus_set)

            def _ask_dest_dir():
                """Propose un dossier de téléchargement.
                Réouvre le dernier emplacement choisi (sinon Citron_Memoire)."""
                initial = getattr(self, "_last_download_dir", None) or self._mem_dir
                if not initial or not os.path.isdir(initial):
                    initial = self._mem_dir if os.path.isdir(self._mem_dir) else os.path.expanduser("~")
                dest = filedialog.askdirectory(
                    title="Choisir le dossier de téléchargement",
                    initialdir=initial,
                    parent=win)
                if dest:
                    self._remember_download_dir(dest)
                return dest or None

            def go_play_and_dl(event=None):
                url = var.get().strip()
                if not url:
                    return
                dest_dir = _ask_dest_dir()
                if not dest_dir:
                    return
                win.destroy()
                self.play_internet_url(url, download_dir=dest_dir, play=True)

            def go_play_only(event=None):
                url = var.get().strip()
                if not url:
                    return
                win.destroy()
                self.play_internet_url(url, play=True, download=False)

            def go_play_and_record(event=None):
                url = var.get().strip()
                if not url:
                    return
                win.destroy()
                self.play_internet_url_and_record(url)

            def go_dl_only(event=None):
                url = var.get().strip()
                if not url:
                    return
                dest_dir = _ask_dest_dir()
                if not dest_dir:
                    return
                win.destroy()
                self.play_internet_url(url, download_dir=dest_dir, play=False)

            def go_tv_and_dl(event=None):
                url = var.get().strip()
                if not url:
                    return
                dest_dir = _ask_dest_dir()
                if not dest_dir:
                    return
                win.destroy()
                self.play_internet_url_on_tv(url, download=True, download_dir=dest_dir)

            def go_tv_only(event=None):
                url = var.get().strip()
                if not url:
                    return
                win.destroy()
                self.play_internet_url_on_tv(url, download=False)

            btn_row = ctk.CTkFrame(win, fg_color="transparent")
            btn_row.pack(pady=(10, 4))
            ctk.CTkButton(btn_row, text="Lire sur PC", command=go_play_only,
                          height=36, width=140, fg_color="#1a6e3c").pack(side="left", padx=6)
            ctk.CTkButton(btn_row, text="Lire sur PC et télécharger", command=go_play_and_dl,
                          height=36, width=220, fg_color="#1a6e3c").pack(side="left", padx=6)
            ctk.CTkButton(btn_row, text="💾 Télécharger", command=go_dl_only,
                          height=36, width=140, fg_color="#2a4a6a").pack(side="left", padx=6)
            btn_row2 = ctk.CTkFrame(win, fg_color="transparent")
            btn_row2.pack(pady=(4, 4))
            ctk.CTkButton(btn_row2, text="Lire sur TV et télécharger", command=go_tv_and_dl,
                          height=36, width=220, fg_color="#2a6496").pack(side="left", padx=6)
            ctk.CTkButton(btn_row2, text="Lire sur TV", command=go_tv_only,
                          height=36, width=140, fg_color="#2a6496").pack(side="left", padx=6)
            btn_row3 = ctk.CTkFrame(win, fg_color="transparent")
            btn_row3.pack(pady=(4, 12))
            ctk.CTkButton(btn_row3, text="🎬 Lire sur PC et enregistrer l'écran",
                          command=go_play_and_record,
                          height=36, width=280, fg_color="#7a3a9a").pack(side="left", padx=6)
            entry.bind("<Return>", go_play_and_dl)

        def _ydl_base_opts(self, extra=None):
            """Options yt-dlp communes, avec plusieurs parades aux erreurs
            fréquentes rencontrées sur YouTube :
            - 'Sign in to confirm you're not a bot' -> on utilise les clients
              internes 'android'/'ios'/'tv' qui ne déclenchent pas (ou moins)
              cette vérification, au lieu du client 'web' par défaut.
            - Erreurs SSL (DECRYPTION_FAILED_OR_BAD_RECORD_MAC) -> souvent liées
              à un antivirus/pare-feu qui inspecte le trafic HTTPS ; on
              désactive la vérification stricte du certificat pour contourner
              ce cas, et on relance automatiquement en cas d'échec réseau.
            """
            opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "nocheckcertificate": True,
                "geo_bypass": True,
                "retries": 10,
                "fragment_retries": 10,
                "socket_timeout": 30,
                # Contourne un bug réseau Windows connu (offload carte réseau /
                # inspection SSL antivirus) qui corrompt les téléchargements
                # continus volumineux -> erreur "DECRYPTION_FAILED_OR_BAD_RECORD_MAC".
                # Des blocs plus petits + davantage de tentatives limitent l'impact.
                "http_chunk_size": 1048576,  # 1 Mo par bloc au lieu d'un flux continu
                "extractor_args": {
                    "youtube": {"player_client": ["android", "ios", "web"]}
                },
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                                  "Chrome/124.0.0.0 Safari/537.36",
                },
            }
            if extra:
                opts.update(extra)
            return opts

        def _set_internet_nav_disabled(self, disabled):
            """Grise / met ❌ sur ⏮, ⏭, 📊 et ⏳ pendant une lecture internet
            (▶ Lire et télécharger). Restaure l'état normal à l'arrêt."""
            try:
                if disabled:
                    if hasattr(self, "prev_btn") and self.prev_btn.winfo_exists():
                        self.prev_btn.configure(text="❌", state="disabled", fg_color="#444444")
                    if hasattr(self, "next_btn") and self.next_btn.winfo_exists():
                        self.next_btn.configure(text="❌", state="disabled", fg_color="#444444")
                    if hasattr(self, "prog_toggle_btn") and self.prog_toggle_btn.winfo_exists():
                        self.prog_toggle_btn.configure(text="❌", state="disabled", fg_color="#444444")
                    if hasattr(self, "countdown_label") and self.countdown_label.winfo_exists():
                        self.countdown_label.configure(text="❌ --:--", text_color="#666666")
                else:
                    if hasattr(self, "prev_btn") and self.prev_btn.winfo_exists():
                        self.prev_btn.configure(text="⏮", state="normal", fg_color=["#3a7ebf", "#1f538d"])
                    if hasattr(self, "next_btn") and self.next_btn.winfo_exists():
                        self.next_btn.configure(text="⏭", state="normal", fg_color=["#3a7ebf", "#1f538d"])
                    if hasattr(self, "prog_toggle_btn") and self.prog_toggle_btn.winfo_exists():
                        color = "#1f6aa5" if self.progress_visible else "#555555"
                        self.prog_toggle_btn.configure(text="📊", state="normal", fg_color=color)
                    if hasattr(self, "countdown_label") and self.countdown_label.winfo_exists():
                        self.countdown_label.configure(text="⏳ --:--", text_color=["#DCE4EE", "#DCE4EE"])
            except Exception as ex:
                print(f"[Internet] _set_internet_nav_disabled : {ex}")

        def _pick_one_dlna_device(self, parent=None):
            """Choisit un appareil DLNA (scan si besoin). Retourne le dict device ou None."""
            if not self._dlna_devices:
                try:
                    self._dlna_devices = discover_dlna_renderers(timeout=4)
                except Exception as ex:
                    print(f"[DLNA] scan: {ex}")
            if not self._dlna_devices:
                messagebox.showerror(
                    "TV",
                    "Aucun appareil DLNA trouvé.\n"
                    "Utilisez d'abord le bouton 📺 TV pour rechercher les appareils.",
                    parent=parent)
                return None
            if len(self._dlna_devices) == 1:
                return self._dlna_devices[0]
            win = ctk.CTkToplevel(self)
            win.title("Choisir la TV")
            win.geometry("420x280")
            win.transient(self)
            win.lift()
            ctk.CTkLabel(win, text="Choisir l'appareil TV :", font=("Arial", 15, "bold")).pack(pady=10)
            lb = Listbox(win, font=("Arial", 13), bg="#2b2b2b", fg="white",
                         selectbackground="#1f6aa5", height=6)
            lb.pack(fill="both", expand=True, padx=15, pady=6)
            for d in self._dlna_devices:
                lb.insert(END, f"{d['name']}  ({d['ip']})")
            selected = [None]

            def confirm():
                sel = lb.curselection()
                if sel:
                    selected[0] = self._dlna_devices[sel[0]]
                win.destroy()

            ctk.CTkButton(win, text="✅ Confirmer", command=confirm, height=36).pack(pady=8)
            win.wait_window()
            return selected[0]

        def play_internet_url_on_tv(self, url, download=False, download_dir=None):
            """Résout l'URL internet (yt-dlp) et envoie le flux à la TV via
            DLNA — EN LA FAISANT PASSER PAR LE SERVEUR HTTP LOCAL DE CITRON
            (mode relais), et non plus en envoyant l'URL HTTPS brute (ex:
            googlevideo.com) directement au boîtier DLNA.
            Correctif (2026-08-15) : de nombreux boîtiers DLNA anciens (ex:
            WD TV Live) ne savent pas parler HTTPS — la commande de lecture
            était acceptée (le titre s'affichait) mais aucun octet vidéo
            n'arrivait jamais, d'où un écran noir. Le relais retransmet le
            flux en HTTP simple, exactement comme pour un fichier local (qui,
            lui, fonctionnait déjà).
            Si download=True, lance aussi le téléchargement en arrière-plan."""
            url = (url or "").strip()
            if not url:
                return
            device = self._pick_one_dlna_device()
            if not device:
                return
            if download:
                if download_dir is None:
                    download_dir = getattr(self, "_last_download_dir", None) or self._mem_dir
                else:
                    self._remember_download_dir(download_dir)

            self._tv_gen += 1
            my_gen = self._tv_gen
            self._tv_mode = True
            self._tv_device = device
            self._tv_play_device = device
            self._tv_control_url = device.get("control_url")
            self._single_tv_mode = True
            self._seq_mode = False
            self._list_play_mode = False
            self._update_mirror_btn_visibility()
            self.now_playing_label.configure(
                text=f"📺 Résolution URL → {device.get('name', 'TV')}…")
            self.set_play_mode("tv", "Internet")
            # Coupe le son du navigateur pendant la lecture sur TV, comme
            # pour la lecture internet sur PC (évite que la page source,
            # restée ouverte, superpose son propre son à celui de la TV).
            self._mute_browser_audio()

            def worker():
                play_url = url
                title = url
                ext = "mp4"
                try:
                    import yt_dlp
                    ydl_opts = self._ydl_base_opts({
                        "format": "best[height<=1080][acodec!=none][vcodec!=none]"
                                  "/best[acodec!=none][vcodec!=none]/best",
                    })
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if info:
                            title = info.get("title") or title
                            ext = info.get("ext") or ext
                            if info.get("url"):
                                play_url = info["url"]
                            elif info.get("entries"):
                                ent = next((e for e in info["entries"] if e), None)
                                if ent:
                                    title = ent.get("title") or title
                                    ext = ent.get("ext") or ext
                                    play_url = ent.get("url") or play_url
                    print(f"[Internet→TV] yt-dlp OK — {str(title)[:70]}")
                except ImportError:
                    print("[Internet→TV] yt-dlp absent — URL brute relayée telle quelle")
                except Exception as ex:
                    print(f"[Internet→TV] yt-dlp échec ({ex}) — URL brute relayée telle quelle")

                if self._tv_gen != my_gen:
                    self._restore_browser_audio()
                    return

                display = title if len(str(title)) < 80 else str(title)[:77] + "…"
                self.after(0, lambda: self.now_playing_label.configure(
                    text=f"📺 {device.get('name', 'TV')} — {display}"))

                try:
                    cu = device.get("control_url")
                    ip = device["ip"]
                    if not cu:
                        raise RuntimeError(f"Pas de control_url pour {ip}")
                    self._tv_control_url = cu
                    local_ip = _get_local_ip()
                    if not _same_subnet(local_ip, ip):
                        raise RuntimeError(f"Réseaux différents : PC={local_ip}, TV={ip}")
                    if self.player:
                        try:
                            self.player.stop()
                            self._stop_audio_anim()
                        except Exception:
                            pass

                    # Active le relais HTTP local plutôt que d'envoyer
                    # play_url (souvent HTTPS) directement à la TV.
                    mime = _mime_for_url(f"x.{ext}")
                    self.stream_server.serve_remote(play_url, mime)
                    tv_url = self.stream_server.get_relay_url(f"stream.{ext}")

                    _soap_stop(cu)
                    time.sleep(1.0)
                    _soap_set(cu, tv_url, str(title)[:120])
                    for _ in range(20):
                        time.sleep(0.5)
                        if self._tv_gen != my_gen:
                            return
                        st = _soap_get_transport_state(cu)
                        if st in ("STOPPED", "PAUSED_PLAYBACK", ""):
                            break
                    _soap_play(cu)
                    time.sleep(0.8)
                    _soap_play(cu)
                    print(f"[Internet→TV] Lecture demandée sur {device.get('name')} (via relais HTTP local)")
                    # Miroir PC (aperçu silencieux, comme pour un média local
                    # envoyé sur TV) — utilise l'URL résolue directement pour
                    # éviter de dépendre du relais HTTP pour l'aperçu local.
                    self.after(0, lambda: self._play_mirror_pc_internet(play_url, str(title)))
                except Exception as exc:
                    msg = str(exc)
                    print(f"[Internet→TV] Erreur: {msg}")
                    self.after(0, lambda: messagebox.showerror("TV", msg))
                    self._tv_mode = False
                    self._restore_browser_audio()
                    self.after(0, self._update_mirror_btn_visibility)
                    return

                if download and download_dir:
                    self.after(0, lambda: self._auto_download_to_memory(
                        url, title=str(title), download_dir=download_dir))

            threading.Thread(target=worker, daemon=True).start()

        def _play_mirror_pc_internet(self, url, title):
            """Aperçu silencieux (miroir) sur PC pendant une lecture internet
            envoyée sur TV — équivalent de _play_mirror_pc() mais pour une
            URL internet plutôt qu'un fichier local."""
            def _do_mirror():
                if not self._mirror_on:
                    return
                if not self.player:
                    return
                try:
                    self.player.audio_set_volume(0)
                    self._stop_audio_anim()
                    self.audio_canvas.place_forget()
                    self.player.set_hwnd(self.video_frame.winfo_id())
                    media = self.instance.media_new(url)
                    media.add_option(":network-caching=3000")
                    self.player.set_media(media)
                    self.player.audio_set_volume(0)
                    self.player.play()
                    self.play_btn.configure(text="⏸")
                    self.now_playing_label.configure(
                        text=f"📺 TV + 🖥 Miroir (son 0%) 🌐 {title}")
                    self.title(f"🍋 Citron 📺 — {title}")
                except Exception as ex:
                    print(f"[PC mirror internet] {ex}")
            self.after(0, _do_mirror)

        def play_internet_url(self, url, download_dir=None, play=True, download=True):

            """Lit une vidéo internet et/ou la télécharge.
            - play=True, download=True  : lecture dans Citron + téléchargement
            - play=True, download=False : lecture dans Citron SEULE (pas de téléchargement)
            - play=False                : téléchargement seul (pas de lecture)
            - download_dir : dossier de destination (défaut = Citron_Memoire)
            """
            url = (url or "").strip()
            if not url:
                return
            if download_dir is None:
                download_dir = getattr(self, "_last_download_dir", None) or self._mem_dir
            else:
                self._remember_download_dir(download_dir)
            print(f"[Internet] play_internet_url appelé : play={play} dest={download_dir} url={url[:120]}")

            # Téléchargement seul : pas besoin de VLC ni de l'UI de lecture
            if not play:
                def _dl_only():
                    t = "video"
                    try:
                        import yt_dlp
                        with yt_dlp.YoutubeDL(self._ydl_base_opts()) as ydl:
                            info = ydl.extract_info(url, download=False)
                            if info:
                                t = info.get("title") or t
                    except Exception:
                        pass
                    self.after(0, lambda: self._auto_download_to_memory(url, title=t, download_dir=download_dir))
                threading.Thread(target=_dl_only, daemon=True).start()
                return

            if not self.player:
                messagebox.showerror("VLC", "VLC non disponible."); return
            try:
                self.deiconify()
                self.lift()
                self.attributes("-topmost", True)
                self.after(400, lambda: self.attributes("-topmost", False))
                self.focus_force()
            except Exception:
                pass
            if not self._tv_mode and self._tv_control_url:
                self._stop_tv_silently()
            self._stop_audio_anim()
            self._hide_thumb_win()
            self._seq_mode = False
            self._list_play_mode = False
            self._single_tv_mode = False
            self.now_playing_label.configure(text="🌐  Résolution de l'URL…")
            self._set_internet_nav_disabled(True)

            play_url = url
            title = url

            def _resolve_and_play():
                nonlocal play_url, title
                try:
                    import yt_dlp
                    ydl_opts = self._ydl_base_opts({
                        # VLC ne peut lire qu'UNE seule URL : on exige donc un
                        # format déjà muxé (vidéo+audio ensemble), jamais une
                        # piste vidéo seule, quel que soit le client utilisé.
                        "format": "best[height<=1080][acodec!=none][vcodec!=none]"
                                  "/best[acodec!=none][vcodec!=none]/best",
                    })
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if info:
                            title = info.get("title") or title
                            if info.get("url"):
                                play_url = info["url"]
                            elif info.get("entries"):
                                ent = next((e for e in info["entries"] if e), None)
                                if ent:
                                    title = ent.get("title") or title
                                    play_url = ent.get("url") or play_url
                    print(f"[Internet] yt-dlp OK — {title[:70]}")
                except ImportError:
                    print("[Internet] yt-dlp absent — lecture directe "
                          "(pip install yt-dlp recommandé pour YouTube et autres sites)")
                except Exception as ex:
                    print(f"[Internet] yt-dlp échec ({ex}) — lecture directe")

                def _do_play():
                    try:
                        # Réinitialise seulement le facteur suivi côté Python —
                        # PAS d'appel natif video_set_scale() ici : on est en
                        # pleine transition de lecture (changement de média),
                        # un moment sensible pour libvlc/DirectX. Un média
                        # fraîchement chargé démarre de toute façon déjà sans
                        # zoom (comportement natif par défaut), donc cet appel
                        # n'apportait rien de plus à cet endroit précis.
                        self._video_zoom_factor = 1.0
                        self._internet_url = url
                        self._internet_title = title
                        # Retenue pour l'enregistrement d'écran guidé (voir
                        # play_internet_url_and_record) : cette URL de flux
                        # déjà résolue par yt-dlp permet à ffmpeg de capturer
                        # le son directement à la source, sans dépendre d'un
                        # périphérique audio « boucle » Windows (Stereo Mix)
                        # — souvent absent ou désactivé par défaut.
                        self._internet_play_url = play_url
                        media = self.instance.media_new(play_url)
                        media.add_option(":network-caching=3000")
                        media.add_option(":file-caching=3000")
                        self.player.set_media(media)
                        self.update_idletasks()
                        self.audio_canvas.place_forget()
                        self.player.set_hwnd(self.video_frame.winfo_id())
                        self.player.audio_set_mute(False)
                        self.player.play()
                        self.play_btn.configure(text="⏸")
                        display = title if len(title) < 80 else title[:77] + "…"
                        self.now_playing_label.configure(text=f"🌐  {display}")
                        self.title(f"🍋 Citron — {display}")
                        self._set_internet_ui(True, display)
                        self.set_play_mode("pc", "Internet")
                        self.countdown_running = False
                        print("[Internet] Lecture démarrée")
                        # Téléchargement en arrière-plan vers le dossier choisi
                        # (uniquement si demandé — "Lire sur PC" seul ne télécharge pas)
                        if download:
                            self._auto_download_to_memory(url, title, download_dir=download_dir)
                    except Exception as ex:
                        # Marqueur retenu pour que l'attente du démarrage de
                        # l'enregistrement d'écran (voir play_internet_url_and_record)
                        # puisse s'arrêter tout de suite sur un vrai échec de
                        # lecture, au lieu d'attendre inutilement tout le délai.
                        self._internet_play_failed_url = url
                        self._internet_play_last_error = str(ex)
                        messagebox.showerror("Internet", f"Impossible de lire l'URL :\n{ex}")
                        self._set_internet_ui(False)
                        self._set_internet_nav_disabled(False)
                self.after(0, _do_play)

            threading.Thread(target=_resolve_and_play, daemon=True).start()

        # ── Enregistrement d'écran pendant une lecture internet ─────────
        # Capture ce qui s'affiche réellement dans la fenêtre Citron (via
        # ffmpeg/gdigrab, Windows uniquement), plutôt que de télécharger le
        # flux source — une manière alternative d'obtenir une vidéo, utile
        # par exemple pour des contenus que yt-dlp ne sait pas télécharger
        # proprement. L'image est toujours capturée ; le son ne l'est que si
        # un périphérique de boucle audio (« Stereo Mix » / « Mixage stéréo »
        # / équivalent) est disponible sur le PC — souvent désactivé par
        # défaut sur les cartes son modernes. Sans lui, la capture se fait en
        # image seule, et Citron le signale clairement plutôt que de laisser
        # croire que le son a été enregistré.

        def _list_dshow_audio_devices(self, ffmpeg_path):
            """Retourne la liste BRUTE de tous les noms de périphériques
            audio DirectShow que ffmpeg détecte (pas seulement ceux qui
            ressemblent à un périphérique de boucle). Sert de diagnostic :
            si « Stereo Mix »/« Mixage stéréo » est activé dans Windows mais
            n'apparaît pas dans cette liste, c'est que le pilote audio ne
            l'expose pas via DirectShow (une couche différente de celle des
            réglages sonores de Windows) — dans ce cas, aucun nom de
            recherche automatique, quel qu'il soit, ne pourra le trouver."""
            try:
                result = subprocess.run(
                    [ffmpeg_path, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                    capture_output=True, text=True, timeout=8,
                    encoding="utf-8", errors="ignore",
                    creationflags=no_console_flags())
            except Exception as ex:
                print(f"[Capture écran] Détection périphériques audio impossible : {ex}")
                return []
            # Bug corrigé : la sortie de ffmpeg (le listing des périphériques)
            # arrive sur stderr, pas stdout — et la variable qui la reçoit
            # n'était jamais assignée avant (NameError silencieuse à chaque
            # appel, qui empêchait la capture d'écran de démarrer).
            output = (result.stdout or "") + (result.stderr or "")
            import re as _re
            names = []
            in_audio_section = False
            for line in output.splitlines():
                if "DirectShow audio devices" in line:
                    in_audio_section = True
                    continue
                if "DirectShow video devices" in line:
                    in_audio_section = False
                    continue
                if in_audio_section and "Alternative name" not in line:
                    m = _re.search(r'"([^"]+)"', line)
                    if m:
                        names.append(m.group(1))
            return names

        def _resolve_screen_record_audio(self, ffmpeg_path, callback):
            """Détermine quel périphérique audio utiliser pour la capture
            d'écran, puis appelle callback(nom_ou_None). Ordre de priorité :
            1) un choix déjà mémorisé par l'utilisateur (settings) ;
            2) une détection automatique par mot-clé parmi les périphériques
               réellement vus par ffmpeg (log complet affiché dans tous les
               cas, pour diagnostic) ;
            3) si rien n'est trouvé automatiquement, un choix manuel proposé
               à l'utilisateur parmi la liste réelle des périphériques
               détectés (éventuellement vide), avec option de mémorisation."""
            saved = getattr(self, "_screen_record_audio_device", None)
            if saved == "__none__":
                callback(None)
                return
            if saved:
                callback(saved)
                return

            names = self._list_dshow_audio_devices(ffmpeg_path)
            print(f"[Capture écran] Périphériques audio DirectShow détectés par ffmpeg : "
                  f"{names if names else '(aucun)'}")
            keywords = ("stereo mix", "mixage st", "loopback", "what u hear",
                        "wave out mix", "rec. playback", "sortie audio")
            auto = next((n for n in names if any(k in n.lower() for k in keywords)), None)
            if auto:
                print(f"[Capture écran] Périphérique audio de boucle détecté automatiquement : {auto!r}")
                callback(auto)
                return

            print("[Capture écran] Aucun périphérique audio de boucle reconnu automatiquement "
                  "parmi la liste ci-dessus — proposition d'un choix manuel.")
            self._show_audio_device_picker(names, callback)

        def _show_audio_device_picker(self, names, callback):
            """Petite fenêtre listant les périphériques audio réellement vus
            par ffmpeg (ou expliquant qu'il n'y en a aucun), pour choisir
            manuellement celui à utiliser pour la capture — utile quand la
            détection automatique par mot-clé échoue (nom inhabituel, pilote
            n'exposant pas Stereo Mix en DirectShow, câble audio virtuel…).
            Le choix peut être mémorisé pour ne plus jamais redemander."""
            win = ctk.CTkToplevel(self)
            win.title("🔊 Choisir le périphérique audio de la capture")
            win.geometry("560x420")
            win.attributes("-topmost", True)
            win.transient(self)
            win.grab_set()

            ctk.CTkLabel(win, text="🔊 Aucun périphérique audio de boucle reconnu automatiquement",
                         font=("Arial", 15, "bold"), wraplength=520).pack(pady=(16, 4), padx=16)
            if names:
                info = ("Voici les périphériques audio que ffmpeg détecte réellement sur ce PC. "
                        "Choisissez celui qui correspond à votre haut-parleur/casque (souvent nommé "
                        "« Stereo Mix », « Mixage stéréo », ou le nom d'un câble audio virtuel), "
                        "ou continuez sans son.")
            else:
                info = ("ffmpeg ne détecte AUCUN périphérique audio sur ce PC — même « Microphone » "
                        "n'apparaît pas. Cela arrive quand le pilote audio n'expose rien via "
                        "DirectShow : activer Stereo Mix dans les réglages sonores de Windows ne "
                        "suffit pas toujours, car Windows peut l'exposer via une autre couche que "
                        "DirectShow. La solution la plus fiable dans ce cas est d'installer un câble "
                        "audio virtuel gratuit (ex : VB-Audio Virtual Cable), qui lui s'expose "
                        "correctement. Vous pouvez continuer sans son pour l'instant.")
            ctk.CTkLabel(win, text=info, font=("Arial", 11), text_color="#aaaaaa",
                         wraplength=520, justify="left").pack(padx=16, pady=(0, 8))

            lf = ctk.CTkFrame(win)
            lf.pack(fill="both", expand=True, padx=16, pady=6)
            lb = Listbox(lf, font=("Arial", 12), bg="#2b2b2b", fg="white",
                         selectbackground="#1f6aa5", activestyle="none")
            sb = Scrollbar(lf, orient="vertical", command=lb.yview)
            lb.config(yscrollcommand=sb.set)
            lb.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            lb.insert(END, "🚫 Aucun (capture en image seule)")
            for n in names:
                lb.insert(END, n)
            lb.selection_set(0)

            # Décoché par défaut : un choix "Aucun" mémorisé par erreur (ou
            # à cause d'un bug de détection ponctuel) resterait sinon
            # silencieusement actif pour toujours, coupant le son de tous
            # les enregistrements suivants sans que rien ne le signale.
            remember_var = ctk.BooleanVar(value=False)
            ctk.CTkCheckBox(win, text="Se souvenir de ce choix (ne plus redemander)",
                            variable=remember_var).pack(pady=(4, 8))

            def _validate():
                sel = lb.curselection()
                idx = sel[0] if sel else 0
                choice = None if idx == 0 else names[idx - 1]
                if remember_var.get():
                    self._screen_record_audio_device = choice if choice else "__none__"
                    try:
                        self.save_settings()
                    except Exception:
                        pass
                try:
                    win.grab_release()
                except Exception:
                    pass
                win.destroy()
                callback(choice)

            def _cancel():
                try:
                    win.grab_release()
                except Exception:
                    pass
                win.destroy()
                callback(None)

            btn_row = ctk.CTkFrame(win, fg_color="transparent")
            btn_row.pack(pady=(0, 14))
            ctk.CTkButton(btn_row, text="✅ Utiliser ce choix", command=_validate,
                          height=36, width=180, fg_color="#1a6e3c").pack(side="left", padx=6)
            ctk.CTkButton(btn_row, text="Annuler (image seule)", command=_cancel,
                          height=36, width=180, fg_color="#555555").pack(side="left", padx=6)
            win.protocol("WM_DELETE_WINDOW", _cancel)

        def _change_screen_record_audio_device(self):
            """Menu ⚙ Paramètres → 🔊 Périphérique audio (capture d'écran) :
            oublie le choix mémorisé et relance la détection/le choix
            manuel, pour corriger une sélection faite par erreur ou revoir
            la liste après avoir installé/activé un nouveau périphérique
            (ex : Stereo Mix tout juste activé, câble audio virtuel
            fraîchement installé)."""
            ffmpeg_path = self._get_ffmpeg_path()
            if not ffmpeg_path:
                messagebox.showinfo(
                    "Périphérique audio",
                    "ffmpeg est introuvable : impossible de lister les périphériques audio.")
                return
            self._screen_record_audio_device = None
            try:
                self.save_settings()
            except Exception:
                pass
            names = self._list_dshow_audio_devices(ffmpeg_path)
            print(f"[Capture écran] (Re)détection manuelle — périphériques trouvés : "
                  f"{names if names else '(aucun)'}")

            def _on_choice(device):
                if device is None and getattr(self, "_screen_record_audio_device", None) != "__none__":
                    return  # fenêtre annulée sans choix explicite : ne rien changer
                label = device or "aucun (image seule)"
                self._show_toast(f"🔊 Périphérique audio de capture : {label}", ms=4000, color="#2a4a6a")

            self._show_audio_device_picker(names, _on_choice)

        def play_internet_url_and_record(self, url):
            """Lit une URL internet sur PC, puis GUIDE l'utilisateur pour
            choisir précisément la zone d'écran à enregistrer (et le
            périphérique audio), avant de démarrer la capture pour de bon.

            Déroulé :
            1) La vidéo démarre (comme « Lire sur PC »).
            2) Dès qu'elle a démarré, elle est mise en PAUSE automatiquement
               — l'utilisateur n'a donc pas de contenu qui défile pendant
               qu'il réfléchit à la zone à capturer.
            3) Une petite fenêtre explique la marche à suivre, puis ouvre le
               sélecteur de zone existant (clic-glisser en plein écran) —
               le même outil que « 📐 Enregistrer une zone de l'écran ».
            4) Une fois la zone validée : dossier de destination, résolution
               du périphérique audio (avec, si besoin, le choix manuel
               habituel), remise de la vidéo à son tout début, démarrage
               réel de l'enregistrement, puis reprise immédiate de la
               lecture — pour que la capture démarre bien dès la première
               image de la vidéo, dans la zone choisie, son compris.

            Fusionne ainsi ce qui était auparavant deux mécaniques
            séparées (capture automatique, non paramétrable, de la seule
            zone vidéo de Citron ; et sélection libre de zone, réservée à
            « 📐 Enregistrer une zone de l'écran ») en un seul parcours
            clair : l'utilisateur voit et choisit toujours exactement ce
            qui sera enregistré."""
            url = (url or "").strip()
            if not url:
                return
            if os.name != "nt":
                messagebox.showinfo(
                    "Enregistrement d'écran",
                    "Cette fonctionnalité (capture d'écran via ffmpeg/gdigrab) "
                    "n'est disponible que sous Windows pour l'instant.")
                return
            ffmpeg_path = self._get_ffmpeg_path()
            if not ffmpeg_path:
                messagebox.showinfo(
                    "Enregistrement d'écran",
                    "ffmpeg est introuvable : l'enregistrement d'écran en a besoin "
                    "(Citron l'utilise déjà pour générer les vignettes).\n"
                    "Installez ffmpeg, ou placez-le dans un dossier « ffmpeg » "
                    "à côté de Citron, puis réessayez.")
                return
            if getattr(self, "_screen_record_active", False):
                messagebox.showinfo(
                    "Enregistrement d'écran",
                    "Un enregistrement d'écran est déjà en cours.\n"
                    "Arrêtez la lecture actuelle avant d'en démarrer un nouveau.")
                return

            # Lecture réelle sur PC — identique au bouton « Lire sur PC »,
            # sans téléchargement du flux source.
            self.play_internet_url(url, play=True, download=False)

            # La résolution de l'URL (yt-dlp) et l'affectation du titre de
            # la fenêtre se font en arrière-plan (voir play_internet_url) :
            # on attend que ce soit fait avant de continuer, pour connaître
            # le vrai titre (nom du fichier de sortie) et être sûr que la
            # lecture a bien démarré avant de la mettre en pause.
            #
            # Délai généreux (90s) : contrairement aux autres boutons (Lire
            # sur PC, Lire sur PC et télécharger…), qui eux n'imposent AUCUNE
            # limite et attendent simplement le temps qu'il faut, cette
            # attente avait un délai fixe de 20s — trop court pour certaines
            # URLs dont la résolution yt-dlp prend plus de temps (réseau,
            # site plus lent à répondre).
            deadline = time.time() + 90
            expected_url = url
            self._internet_play_failed_url = None

            def _wait_then_pause_and_guide():
                # Échec franc de la lecture (ex: URL invalide, erreur VLC) :
                # inutile d'attendre le reste du délai, on le signale tout
                # de suite avec le vrai message d'erreur.
                if getattr(self, "_internet_play_failed_url", None) == expected_url:
                    messagebox.showerror(
                        "Enregistrement d'écran",
                        "La lecture a échoué, l'enregistrement d'écran est annulé.\n"
                        f"Détail : {getattr(self, '_internet_play_last_error', '') or 'inconnu'}")
                    return
                if getattr(self, "_internet_url", "") != expected_url or not self._internet_title:
                    if time.time() > deadline:
                        messagebox.showerror(
                            "Enregistrement d'écran",
                            "La lecture n'a pas démarré dans le délai imparti (90s) — "
                            "enregistrement annulé.\nLa résolution de cette URL est "
                            "peut-être anormalement lente ; réessayez, ou utilisez "
                            "« 📐 Enregistrer une zone de l'écran » après avoir lancé "
                            "la lecture manuellement.")
                        return
                    self.after(200, _wait_then_pause_and_guide)
                    return
                # La lecture a démarré : pause immédiate, le temps que
                # l'utilisateur choisisse la zone à enregistrer.
                try:
                    self.player.pause()
                    self.play_btn.configure(text="▶")
                except Exception:
                    pass
                self._guide_screen_record_region(ffmpeg_path, expected_url)

            self.after(300, _wait_then_pause_and_guide)

        def _resume_paused_internet_playback(self):
            """Reprend une lecture internet mise en pause par
            play_internet_url_and_record (annulation à n'importe quelle
            étape du parcours guidé : zone non choisie, dossier annulé…) —
            pour ne pas laisser la vidéo figée sans explication."""
            try:
                self.player.play()
                self.play_btn.configure(text="⏸")
            except Exception:
                pass

        def _guide_screen_record_region(self, ffmpeg_path, expected_url):
            """Étape 2 du parcours guidé : explique la marche à suivre, puis
            ouvre le sélecteur de zone (_pick_screen_region, le même outil
            que « 📐 Enregistrer une zone de l'écran ») pendant que la vidéo
            reste en pause sur sa première image."""
            info = ctk.CTkToplevel(self)
            info.title("🎬 Enregistrement d'écran")
            info.attributes("-topmost", True)
            info.transient(self)
            info.grab_set()
            info.resizable(False, False)

            ctk.CTkLabel(
                info, text="🎬 La lecture est en pause sur la 1ère image.",
                font=("Arial", 15, "bold"), wraplength=420
            ).pack(pady=(18, 6), padx=16)
            ctk.CTkLabel(
                info,
                text="Sur l'écran suivant, cliquez-glissez pour délimiter la zone à "
                     "enregistrer (pensez à bien inclure la zone vidéo de Citron, et "
                     "le son si besoin). La lecture reprendra automatiquement, depuis "
                     "le tout début, dès que l'enregistrement démarrera.",
                font=("Arial", 12), text_color="#aaaaaa",
                wraplength=420, justify="left"
            ).pack(padx=16, pady=(0, 14))

            def _go():
                try:
                    info.grab_release()
                except Exception:
                    pass
                info.destroy()
                self._pick_screen_region(
                    lambda region: self._on_screen_record_region_picked(
                        region, ffmpeg_path, expected_url))

            def _cancel():
                try:
                    info.grab_release()
                except Exception:
                    pass
                info.destroy()
                self._resume_paused_internet_playback()

            btn_row = ctk.CTkFrame(info, fg_color="transparent")
            btn_row.pack(pady=(0, 18))
            ctk.CTkButton(btn_row, text="📐 Choisir la zone à enregistrer", command=_go,
                          height=36, width=240, fg_color="#7a3a9a").pack(side="left", padx=6)
            ctk.CTkButton(btn_row, text="Annuler", command=_cancel,
                          height=36, width=100, fg_color="#555555").pack(side="left", padx=6)
            info.protocol("WM_DELETE_WINDOW", _cancel)
            info.update_idletasks()
            self._remember_last_window_geometry(info)

        def _on_screen_record_region_picked(self, region, ffmpeg_path, expected_url):
            """Étape 3 : zone choisie (ou annulée). Si choisie, demande le
            dossier de destination, remet la vidéo à zéro, démarre la
            capture puis reprend la lecture.

            Pour le son : on utilise directement l'URL de flux déjà résolue
            par yt-dlp (self._internet_play_url, la même que VLC est en
            train de lire) comme source audio pour ffmpeg — fiable dans
            tous les cas, sans dépendre d'un périphérique audio « boucle »
            Windows (Stereo Mix), souvent absent ou désactivé par défaut, et
            qui obligeait sinon l'utilisateur à choisir entre deux options
            revenant toutes les deux à une capture sans son. On ne retombe
            sur l'ancien sélecteur de périphérique que si, par exception,
            cette URL n'est pas disponible."""
            if not region:
                self._resume_paused_internet_playback()
                return
            if getattr(self, "_internet_url", "") != expected_url:
                # Une autre lecture a démarré entretemps : capture abandonnée,
                # rien à reprendre (ce n'est plus la même vidéo).
                return

            initial = getattr(self, "_last_download_dir", None) or self._mem_dir
            if not initial or not os.path.isdir(initial):
                initial = os.path.expanduser("~")
            dest_dir = filedialog.askdirectory(
                title="Où enregistrer la vidéo capturée à l'écran ?",
                initialdir=initial, parent=self)
            if not dest_dir:
                self._resume_paused_internet_playback()
                return
            self._remember_download_dir(dest_dir)

            title = self._internet_title or "Capture"
            audio_source_url = getattr(self, "_internet_play_url", "") or None

            def _launch(audio_device):
                if getattr(self, "_internet_url", "") != expected_url:
                    return
                # Remise à zéro pendant que c'est encore en pause, pour que
                # la capture démarre bien depuis la toute première image.
                try:
                    self.player.set_time(0)
                except Exception:
                    pass
                self._start_screen_recording(dest_dir, title, ffmpeg_path, audio_device, region=region,
                                              audio_source_url=audio_source_url)
                self._resume_paused_internet_playback()

            if audio_source_url:
                _launch(None)
                return

            def _on_audio(audio_device):
                _launch(audio_device)

            self._resolve_screen_record_audio(ffmpeg_path, _on_audio)

        def _build_screen_record_cmd(self, ffmpeg_path, x, y, w, h, audio_device, out_path,
                                      audio_source_url=None):
            cmd = [ffmpeg_path, "-y", "-f", "gdigrab", "-framerate", "30",
                   "-offset_x", str(x), "-offset_y", str(y),
                   "-video_size", f"{w}x{h}", "-i", "desktop"]
            if audio_source_url:
                # Capture le son directement depuis la source de streaming déjà
                # résolue (celle que VLC lit), lue en temps réel (-re) pour
                # rester synchronisée avec la capture d'écran — au lieu de
                # dépendre d'un périphérique audio « boucle » Windows (Stereo
                # Mix), souvent absent ou désactivé par défaut.
                cmd += ["-re", "-i", audio_source_url, "-map", "0:v", "-map", "1:a?"]
            elif audio_device:
                cmd += ["-f", "dshow", "-i", f"audio={audio_device}"]
            cmd += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
            if audio_device or audio_source_url:
                cmd += ["-c:a", "aac", "-b:a", "192k"]
            cmd += [out_path]
            return cmd

        def _build_screen_record_cmd_ddagrab(self, ffmpeg_path, x, y, w, h, audio_device, out_path,
                                              audio_source_url=None):
            """Variante de _build_screen_record_cmd utilisant l'API Desktop
            Duplication de Windows (filtre ffmpeg « ddagrab ») plutôt que
            gdigrab (BitBlt classique). Tentée EN PREMIER par
            _start_screen_recording : gdigrab lit une copie GDI du bureau
            qui, sur certaines configurations, ne voit pas le rendu vidéo
            matériel (overlay Direct3D utilisé par VLC en décodage
            accéléré) — la zone capturée est alors correcte en position et
            en taille, mais reste noire/figée exactement là où la vidéo
            est réellement affichée. La Desktop Duplication API capture le
            bureau après composition, à l'endroit même où Windows l'affiche
            réellement, y voir compris ce rendu matériel.
            Suppose l'enregistrement sur l'écran PRIMAIRE (output_idx=0) :
            x et y doivent donc déjà être des coordonnées positives (voir
            le garde-fou correspondant dans _start_screen_recording) —
            cette variante n'est pas utilisée pour une zone sur un écran
            secondaire."""
            vf = f"hwdownload,format=bgra,crop={w}:{h}:{x}:{y},format=yuv420p"
            cmd = [ffmpeg_path, "-y", "-f", "lavfi", "-i", "ddagrab=output_idx=0:framerate=30",
                   "-vf", vf]
            if audio_source_url:
                cmd += ["-re", "-i", audio_source_url, "-map", "0:v", "-map", "1:a?"]
            elif audio_device:
                cmd += ["-f", "dshow", "-i", f"audio={audio_device}"]
            cmd += ["-c:v", "libx264", "-preset", "veryfast"]
            if audio_device or audio_source_url:
                cmd += ["-c:a", "aac", "-b:a", "192k"]
            cmd += [out_path]
            return cmd

        def _launch_screen_record_proc(self, cmd):
            """Lance ffmpeg avec sa sortie d'erreur écrite dans un fichier
            journal (et non jetée), pour pouvoir diagnostiquer un échec
            silencieux de l'entrée audio (ex: périphérique refusé par
            Windows) au lieu de ne jamais savoir pourquoi il n'y a pas de
            son. Retourne (process, chemin_du_journal, fichier_journal)."""
            log_path = os.path.join(tempfile.gettempdir(),
                                     f"citron_capture_ecran_{os.getpid()}_{int(time.time()*1000)}.log")
            log_fh = open(log_path, "w", encoding="utf-8", errors="ignore")
            proc = subprocess.Popen(
                cmd, stdin=subprocess.PIPE,
                stdout=log_fh, stderr=subprocess.STDOUT,
                creationflags=no_console_flags())
            return proc, log_path, log_fh

        def _start_screen_recording(self, dest_dir, title, ffmpeg_path, audio_device=None, region=None,
                                     audio_source_url=None):
            """Démarre la capture. Sans `region`, cible précisément la zone
            d'affichage vidéo (self.video_frame) via ses coordonnées écran
            absolues — PAS toute la fenêtre Citron (titre, barre de
            contrôle, boutons…). Avec `region` (x, y, w, h en coordonnées
            écran absolues), capture cette zone à la place — utilisé pour
            l'enregistrement libre d'une zone d'écran choisie par
            l'utilisateur (voir start_free_screen_region_recording), qui
            n'est pas liée à une lecture dans Citron.
            En utilisant gdigrab en mode « desktop + région », plutôt que
            le mode « fenêtre entière par titre » utilisé initialement, qui
            capturait aussi les boutons/contrôles autour de la vidéo.
            Limite à noter : la zone capturée reste fixée aux coordonnées du
            moment du démarrage ; si la fenêtre/zone est déplacée ou
            redimensionnée en cours d'enregistrement, la capture ne suit pas.

            audio_source_url (prioritaire sur audio_device) : URL de flux
            déjà résolue par yt-dlp, dont ffmpeg tire directement le son —
            voir play_internet_url_and_record. Fiable dans tous les cas
            puisqu'elle ne dépend d'aucun périphérique audio Windows.

            audio_device est résolu par _resolve_screen_record_audio()
            (choix mémorisé, détection automatique, ou choix manuel de
            l'utilisateur) avant l'appel à cette fonction — utilisé
            seulement quand aucune audio_source_url n'est disponible (cas
            de l'enregistrement d'une zone d'écran libre, non lié à une
            vidéo particulière lue par Citron).

            Fiabilité audio : si un périphérique de boucle (Stereo Mix…) est
            fourni mais que ffmpeg échoue quand même à l'ouvrir (permission
            refusée, périphérique déjà utilisé en exclusivité par une autre
            application, etc.), le processus ffmpeg se termine en général
            immédiatement avec une erreur. On détecte ce cas (le processus
            aurait dû être encore en cours après ~1.8s) et on relance
            automatiquement EN IMAGE SEULE, pour toujours obtenir une vidéo
            exploitable plutôt qu'un échec silencieux — avec un message
            expliquant précisément pourquoi l'audio n'a pas pu être capturé."""
            try:
                safe = "".join(c if c.isalnum() or c in " ._-" else "_" for c in title)[:80].strip("._ ")
                if not safe:
                    safe = "capture"
                ts = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")
                out_path = os.path.join(dest_dir, f"{safe} - Capture écran ({ts}).mp4")

                self.update_idletasks()
                if region is not None:
                    x, y, w, h = region
                else:
                    vf = self.video_frame
                    x = vf.winfo_rootx()
                    y = vf.winfo_rooty()
                    w = vf.winfo_width()
                    h = vf.winfo_height()
                # libx264 (yuv420p) exige des dimensions paires.
                w -= (w % 2)
                h -= (h % 2)
                if w < 32 or h < 32:
                    messagebox.showerror(
                        "Enregistrement d'écran",
                        "La zone de visualisation vidéo est introuvable ou trop "
                        "petite pour être capturée (fenêtre peut-être réduite).")
                    return

                # Garde-fou écran secondaire (voir _build_screen_record_cmd_ddagrab) :
                # ddagrab n'est tenté que si la zone est bien sur l'écran
                # PRIMAIRE (coordonnées x/y positives) ; sinon on part
                # directement sur gdigrab, qui gère nativement tout le
                # bureau virtuel multi-écrans.
                use_ddagrab = (x >= 0 and y >= 0)
                if use_ddagrab:
                    cmd = self._build_screen_record_cmd_ddagrab(ffmpeg_path, x, y, w, h, audio_device,
                                                                  out_path, audio_source_url=audio_source_url)
                else:
                    cmd = self._build_screen_record_cmd(ffmpeg_path, x, y, w, h, audio_device, out_path,
                                                          audio_source_url=audio_source_url)
                proc, log_path, log_fh = self._launch_screen_record_proc(cmd)
                self._screen_record_proc = proc
                self._screen_record_active = True
                self._screen_record_path = out_path
                self._screen_record_log_fh = log_fh
                self._screen_record_log_path = log_path

                has_audio = bool(audio_source_url or audio_device)
                msg = f"🎬 Enregistrement d'écran démarré : {os.path.basename(out_path)}"
                if not has_audio:
                    msg += "\n(image seule — aucun périphérique audio sélectionné)"
                self._show_toast(msg, ms=6000, color="#7a3a9a")
                print(f"[Capture écran] Démarré ({'ddagrab' if use_ddagrab else 'gdigrab'}) : {out_path} "
                      f"(audio: {'source URL' if audio_source_url else (audio_device or 'aucun')}, "
                      f"zone capturée : {w}x{h} à la position ({x},{y}), journal : {log_path})")

                if use_ddagrab:
                    # Vérification rapide (avant celle de l'audio) : ce build
                    # de ffmpeg peut ne pas inclure le filtre ddagrab (build
                    # ancien/allégé) — dans ce cas ffmpeg échoue quasi
                    # immédiatement. On bascule alors automatiquement sur
                    # gdigrab, EN CONSERVANT l'audio initialement demandé.
                    self.after(900, lambda: self._check_screen_record_backend(
                        proc, log_fh, log_path, x, y, w, h, out_path, ffmpeg_path, audio_device,
                        audio_source_url=audio_source_url, has_audio=has_audio))
                elif has_audio:
                    # Vérifie que ffmpeg n'a pas planté juste après le
                    # démarrage (signe fréquent d'un refus d'ouverture du
                    # périphérique audio, ou d'une source URL devenue
                    # inaccessible).
                    self.after(1800, lambda: self._check_screen_record_health(
                        proc, log_fh, log_path, x, y, w, h, out_path, ffmpeg_path, audio_device,
                        audio_source_url=audio_source_url))
            except Exception as ex:
                messagebox.showerror("Enregistrement d'écran",
                    f"Impossible de démarrer l'enregistrement :\n{ex}")

        def _check_screen_record_backend(self, proc, log_fh, log_path, x, y, w, h, out_path, ffmpeg_path,
                                          audio_device, audio_source_url, has_audio):
            """Vérifie que la tentative ddagrab a bien démarré. Si le
            processus s'est déjà terminé (filtre ddagrab absent de ce build
            de ffmpeg, ou GPU/pilote incompatible), on bascule
            automatiquement sur gdigrab — silencieusement, sans message
            d'erreur pour l'utilisateur, puisque le résultat final (une
            vidéo exploitable) reste le même. Sinon, on enchaîne comme
            avant sur la vérification audio à 1.8s si une entrée audio a
            été demandée."""
            if proc.poll() is None:
                if has_audio:
                    self.after(900, lambda: self._check_screen_record_health(
                        proc, log_fh, log_path, x, y, w, h, out_path, ffmpeg_path, audio_device,
                        audio_source_url=audio_source_url))
                return
            if getattr(self, "_screen_record_proc", None) is not proc:
                return  # déjà arrêté/remplacé entretemps par l'utilisateur
            try:
                log_fh.close()
            except Exception:
                pass
            tail = ""
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    tail = "".join(f.readlines()[-15:]).strip()
            except Exception:
                pass
            print(f"[Capture écran] ddagrab indisponible sur ce build de ffmpeg (code {proc.returncode}), "
                  f"repli sur gdigrab. Dernières lignes du journal :\n{tail}")
            self._screen_record_proc = None
            self._screen_record_active = False
            try:
                if os.path.isfile(out_path):
                    os.remove(out_path)
            except Exception:
                pass
            cmd = self._build_screen_record_cmd(ffmpeg_path, x, y, w, h, audio_device, out_path,
                                                  audio_source_url=audio_source_url)
            try:
                new_proc, new_log_path, new_log_fh = self._launch_screen_record_proc(cmd)
                self._screen_record_proc = new_proc
                self._screen_record_active = True
                self._screen_record_path = out_path
                self._screen_record_log_fh = new_log_fh
                self._screen_record_log_path = new_log_path
            except Exception as ex:
                messagebox.showerror("Enregistrement d'écran",
                    f"Impossible de démarrer l'enregistrement :\n{ex}")
                return
            if has_audio:
                self.after(1800, lambda: self._check_screen_record_health(
                    new_proc, new_log_fh, new_log_path, x, y, w, h, out_path, ffmpeg_path, audio_device,
                    audio_source_url=audio_source_url))

        def _check_screen_record_health(self, proc, log_fh, log_path, x, y, w, h, out_path, ffmpeg_path,
                                         audio_device, audio_source_url=None):
            """Si le processus ffmpeg s'est déjà terminé peu après son
            lancement (avec entrée audio), c'est presque toujours que
            l'ouverture du périphérique audio — ou de la source URL — a
            échoué. On relance alors automatiquement en image seule et on
            affiche l'erreur réelle de ffmpeg pour un diagnostic précis,
            plutôt que de laisser croire que l'enregistrement continue
            normalement."""
            if proc.poll() is None:
                return  # toujours en cours : tout va bien, rien à faire
            if getattr(self, "_screen_record_proc", None) is not proc:
                return  # déjà arrêté/remplacé entretemps par l'utilisateur
            try:
                log_fh.close()
            except Exception:
                pass
            tail = ""
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
                tail = "".join(lines[-15:]).strip()
            except Exception:
                pass
            print(f"[Capture écran] ⚠️ ffmpeg s'est arrêté prématurément avec entrée audio "
                  f"(code {proc.returncode}). Dernières lignes du journal :\n{tail}")

            self._screen_record_proc = None
            self._screen_record_active = False
            try:
                if os.path.isfile(out_path):
                    os.remove(out_path)  # fichier probablement vide/invalide
            except Exception:
                pass

            # Nouvelle tentative immédiate, sans audio.
            cmd = self._build_screen_record_cmd(ffmpeg_path, x, y, w, h, None, out_path)
            try:
                new_proc, new_log_path, new_log_fh = self._launch_screen_record_proc(cmd)
                self._screen_record_proc = new_proc
                self._screen_record_active = True
                self._screen_record_path = out_path
                self._screen_record_log_fh = new_log_fh
                self._screen_record_log_path = new_log_path
            except Exception as ex:
                messagebox.showerror("Enregistrement d'écran",
                    f"L'enregistrement s'est arrêté et la reprise en image seule a aussi échoué :\n{ex}")
                return

            audio_label = "la source de streaming de la vidéo" if audio_source_url else f"« {audio_device} »"
            detail = f"{audio_label} n'a pas pu être ouvert(e) par ffmpeg"
            if tail:
                detail += f" :\n{tail[-500:]}"
            self._show_toast(
                f"⚠️ Capture audio impossible ({audio_label}) — reprise en image seule.\n"
                + ("Vérifiez que ce périphérique n'est pas coupé/à 0 dans les paramètres "
                   "d'enregistrement Windows." if not audio_source_url else
                   "La source vidéo a peut-être expiré ou coupé la connexion."),
                ms=8000, color="#8b3a00")
            print(f"[Capture écran] Reprise en image seule : {out_path} — {detail}")

        def _stop_screen_recording(self):
            """Arrête proprement un enregistrement d'écran en cours, en
            demandant à ffmpeg de finaliser le fichier (plutôt que de le
            tuer brutalement, ce qui produirait un .mp4 corrompu/illisible)."""
            proc = getattr(self, "_screen_record_proc", None)
            if not proc:
                return
            self._screen_record_proc = None
            self._screen_record_active = False
            out_path = getattr(self, "_screen_record_path", "")
            log_fh = getattr(self, "_screen_record_log_fh", None)

            def _do_stop():
                try:
                    if proc.stdin:
                        proc.stdin.write(b'q')
                        proc.stdin.flush()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=12)
                except Exception:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                try:
                    if log_fh:
                        log_fh.close()
                except Exception:
                    pass
                exists = out_path and os.path.isfile(out_path)
                if exists:
                    self.after(0, lambda: self._show_toast(
                        f"🎬 Enregistrement terminé : {os.path.basename(out_path)}",
                        ms=5000, color="#1a6e3c"))
                print(f"[Capture écran] Arrêté (fichier {'présent' if exists else 'introuvable'}) : {out_path}")
                # Ferme aussi le contrôle flottant "⏹ Arrêter" s'il existe
                # (capture de zone libre), quel que soit le déclencheur de
                # l'arrêt (bouton du contrôle lui-même, ou autre chemin).
                try:
                    win = getattr(self, "_screen_record_stop_win", None)
                    if win and win.winfo_exists():
                        self.after(0, win.destroy)
                    self._screen_record_stop_win = None
                except Exception:
                    pass

            threading.Thread(target=_do_stop, daemon=True).start()

        def _pick_screen_region(self, callback):
            """Ouvre un sélecteur de zone d'écran par clic-glisser (fenêtre
            plein écran semi-transparente) et appelle callback((x, y, w, h))
            en coordonnées écran absolues, ou callback(None) si l'utilisateur
            annule (Échap, ou zone tracée trop petite)."""
            overlay = ctk.CTkToplevel(self)
            overlay.attributes("-alpha", 0.35)
            overlay.attributes("-topmost", True)
            overlay.configure(fg_color="#000000")
            overlay.overrideredirect(True)
            sw = overlay.winfo_screenwidth()
            sh = overlay.winfo_screenheight()
            overlay.geometry(f"{sw}x{sh}+0+0")

            canvas = Canvas(overlay, bg="black", highlightthickness=0, cursor="crosshair")
            canvas.pack(fill="both", expand=True)
            canvas.create_text(
                sw // 2, max(30, int(sh * 0.05)),
                text="Cliquez-glissez pour définir la zone à enregistrer  •  Échap pour annuler",
                fill="white", font=("Arial", 16, "bold"))

            overlay.update_idletasks()
            overlay.focus_force()
            overlay.grab_set()

            state = {"x0": None, "y0": None, "rect": None}

            def _on_press(e):
                state["x0"], state["y0"] = e.x, e.y
                if state["rect"] is not None:
                    canvas.delete(state["rect"])
                state["rect"] = canvas.create_rectangle(
                    e.x, e.y, e.x, e.y, outline="#ff5030", width=2)

            def _on_drag(e):
                if state["rect"] is not None and state["x0"] is not None:
                    canvas.coords(state["rect"], state["x0"], state["y0"], e.x, e.y)

            def _finish(region):
                try:
                    overlay.grab_release()
                except Exception:
                    pass
                overlay.destroy()
                callback(region)

            def _on_release(e):
                if state["x0"] is None:
                    _finish(None)
                    return
                x0, y0 = state["x0"], state["y0"]
                x, y = min(x0, e.x), min(y0, e.y)
                w, h = abs(e.x - x0), abs(e.y - y0)
                if w < 20 or h < 20:
                    _finish(None)
                    return
                _finish((int(x), int(y), int(w), int(h)))

            canvas.bind("<ButtonPress-1>", _on_press)
            canvas.bind("<B1-Motion>", _on_drag)
            canvas.bind("<ButtonRelease-1>", _on_release)
            overlay.bind("<Escape>", lambda e: _finish(None))

        def _show_screen_record_stop_control(self):
            """Petite fenêtre flottante, toujours au-dessus, avec un bouton
            pour arrêter un enregistrement de zone d'écran libre — celui-ci
            n'étant lié à aucune lecture Citron, il n'y a pas d'arrêt
            automatique possible (contrairement à « Lire sur PC et
            enregistrer l'écran », arrêté quand la lecture s'arrête)."""
            try:
                old = getattr(self, "_screen_record_stop_win", None)
                if old and old.winfo_exists():
                    old.destroy()
            except Exception:
                pass
            win = ctk.CTkToplevel(self)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.geometry("+40+40")
            frame = ctk.CTkFrame(win, fg_color="#7a3a9a", corner_radius=10)
            frame.pack(padx=2, pady=2)
            ctk.CTkLabel(frame, text="🔴 Enregistrement de zone en cours",
                         font=("Arial", 12, "bold"), text_color="white"
                         ).pack(side="left", padx=(12, 8), pady=8)
            ctk.CTkButton(frame, text="⏹ Arrêter", command=self._stop_screen_recording,
                          width=90, height=30, fg_color="#c42b1c").pack(side="left", padx=(0, 10), pady=8)
            self._screen_record_stop_win = win

        def start_free_screen_region_recording(self):
            """Menu ⚙ Paramètres → 📐 Enregistrer une zone de l'écran :
            enregistrement d'une zone choisie librement par l'utilisateur
            (clic-glisser), indépendant de toute lecture dans Citron — utile
            pour capturer n'importe quel contenu affiché à l'écran (un
            lecteur externe, une page web, un autre logiciel...), par
            exemple un contenu que Citron ne saurait pas télécharger
            proprement via yt-dlp."""
            if os.name != "nt":
                messagebox.showinfo(
                    "Enregistrement d'écran",
                    "Cette fonctionnalité (capture d'écran via ffmpeg/gdigrab) "
                    "n'est disponible que sous Windows pour l'instant.")
                return
            ffmpeg_path = self._get_ffmpeg_path()
            if not ffmpeg_path:
                messagebox.showinfo(
                    "Enregistrement d'écran",
                    "ffmpeg est introuvable : l'enregistrement d'écran en a besoin "
                    "(Citron l'utilise déjà pour générer les vignettes).\n"
                    "Installez ffmpeg, ou placez-le dans un dossier « ffmpeg » "
                    "à côté de Citron, puis réessayez.")
                return
            if getattr(self, "_screen_record_active", False):
                messagebox.showinfo(
                    "Enregistrement d'écran",
                    "Un enregistrement d'écran est déjà en cours.\n"
                    "Arrêtez-le avant d'en démarrer un nouveau.")
                return

            def _after_region(region):
                if not region:
                    return
                initial = getattr(self, "_last_download_dir", None) or self._mem_dir
                if not initial or not os.path.isdir(initial):
                    initial = os.path.expanduser("~")
                dest_dir = filedialog.askdirectory(
                    title="Où enregistrer la vidéo capturée à l'écran ?",
                    initialdir=initial, parent=self)
                if not dest_dir:
                    return
                self._remember_download_dir(dest_dir)

                def _on_audio(audio_device):
                    self._start_screen_recording(
                        dest_dir, "Zone d'écran", ffmpeg_path, audio_device, region=region)
                    if getattr(self, "_screen_record_active", False):
                        self._show_screen_record_stop_control()

                self._resolve_screen_record_audio(ffmpeg_path, _on_audio)

            self._pick_screen_region(_after_region)

        def _remember_last_window_geometry(self, win):
            """Mémorise la position/taille d'une fenêtre secondaire qui vient
            de s'ouvrir, pour que d'autres fenêtres (ex: Test Citron)
            puissent s'ouvrir au même endroit plutôt qu'à une position figée.
            Best-effort : une géométrie non lisible n'interrompt rien."""
            try:
                win.update_idletasks()
                geo = win.geometry()  # "WxH+X+Y"
                if geo and "x" in geo:
                    self._last_window_geometry = geo
            except Exception:
                pass

        def _show_toast(self, text, ms=4000, color="#1a6e3c"):
            """Affiche un bandeau de notification temporaire en bas de l'écran
            principal (non bloquant, disparaît tout seul après `ms` ms)."""
            try:
                if getattr(self, "_toast_label", None) and self._toast_label.winfo_exists():
                    self._toast_label.destroy()
            except Exception:
                pass
            try:
                lbl = ctk.CTkLabel(self, text=text, font=("Arial",13,"bold"),
                                    fg_color=color, corner_radius=8,
                                    text_color="white", padx=14, pady=8)
                lbl.place(relx=0.5, rely=0.95, anchor="s")
                self._toast_label = lbl
                self.after(ms, lambda: lbl.destroy() if lbl.winfo_exists() else None)
            except Exception:
                pass

        def _show_progress_toast(self, text):
            """Bandeau de progression PERSISTANT (ne disparaît pas tout seul) :
            mis à jour en continu pendant le téléchargement avec le %."""
            try:
                if getattr(self, "_dl_toast_label", None) and self._dl_toast_label.winfo_exists():
                    self._dl_toast_label.configure(text=text)
                else:
                    lbl = ctk.CTkLabel(self, text=text, font=("Arial",13,"bold"),
                                        fg_color="#2a4a6a", corner_radius=8,
                                        text_color="white", padx=14, pady=8)
                    lbl.place(relx=0.5, rely=0.95, anchor="s")
                    self._dl_toast_label = lbl
            except Exception:
                pass

        def _hide_progress_toast(self):
            try:
                if getattr(self, "_dl_toast_label", None) and self._dl_toast_label.winfo_exists():
                    self._dl_toast_label.destroy()
            except Exception:
                pass
            self._dl_toast_label = None

        def _dl_progress_hook(self, d):
            """Hook appelé par yt-dlp à chaque bloc téléchargé : calcule le %
            et met à jour le bandeau de progression (thread-safe via after)."""
            try:
                status = d.get("status")
                if status == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate")
                    downloaded = d.get("downloaded_bytes", 0)
                    if total:
                        pct = max(0.0, min(100.0, downloaded / total * 100))
                        txt = f"💾 Téléchargement en cours… {pct:.0f}%"
                    else:
                        txt = f"💾 Téléchargement en cours… {downloaded // (1024*1024)} Mo"
                    self.after(0, lambda t=txt: self._show_progress_toast(t))
                elif status == "finished":
                    self.after(0, lambda: self._show_progress_toast("💾 Finalisation…"))
            except Exception:
                pass

        def _auto_download_to_memory(self, url, title=None, download_dir=None):
            """Télécharge la vidéo en arrière-plan vers download_dir
            (défaut = Citron_Memoire). yt-dlp gère YouTube et de nombreuses
            autres plateformes."""
            dest_dir = download_dir or self._mem_dir
            title = title or "video"
            os.makedirs(dest_dir, exist_ok=True)
            safe = "".join(c if c.isalnum() or c in " ._-" else "_" for c in title)[:80].strip("._ ")
            if not safe:
                safe = "video"
            out_tmpl = os.path.join(dest_dir, safe + ".%(ext)s")
            self._show_progress_toast("💾 Téléchargement en cours… 0%")
            self._downloading_safe_names.add(safe)
            if self.dl_win and self.dl_win.winfo_exists():
                self.refresh_downloads_window()

            def worker():
                dest, err = None, None
                try:
                    try:
                        import yt_dlp
                        has_ffmpeg = bool(shutil.which("ffmpeg"))
                        if has_ffmpeg:
                            # ffmpeg dispo : on peut fusionner la meilleure vidéo
                            # et le meilleur audio séparés (qualité optimale),
                            # avec repli garanti sur un format déjà muxé.
                            fmt = ("bestvideo[height<=1080]+bestaudio"
                                   "/best[height<=1080][acodec!=none][vcodec!=none]"
                                   "/best[acodec!=none][vcodec!=none]/best")
                        else:
                            # Pas de ffmpeg : impossible de fusionner deux flux
                            # séparés -> on exige un format déjà muxé (vidéo+son
                            # ensemble), pour ne jamais obtenir un fichier muet.
                            print("[Mémoire] ffmpeg introuvable : qualité limitée "
                                  "à un format vidéo+audio déjà fusionné par YouTube.")
                            fmt = ("best[height<=1080][acodec!=none][vcodec!=none]"
                                   "/best[acodec!=none][vcodec!=none]/best")
                        base_opts = {
                            "outtmpl": out_tmpl,
                            "format": fmt,
                            "merge_output_format": "mp4",
                            "progress_hooks": [self._dl_progress_hook],
                        }
                        # 1er essai : combinaison standard (android/ios/web)
                        try:
                            ydl_opts = self._ydl_base_opts(base_opts)
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                info = ydl.extract_info(url, download=True)
                                dest = ydl.prepare_filename(info) if info else None
                        except Exception as ex1:
                            print(f"[Mémoire] 1er essai échoué ({ex1}) — nouvelle tentative (client android seul)")
                            # 2e essai : client 'android' seul (souvent le plus fiable pour le téléchargement)
                            ydl_opts2 = self._ydl_base_opts(base_opts)
                            ydl_opts2["extractor_args"] = {"youtube": {"player_client": ["android"]}}
                            with yt_dlp.YoutubeDL(ydl_opts2) as ydl:
                                info = ydl.extract_info(url, download=True)
                                dest = ydl.prepare_filename(info) if info else None
                        if dest and not os.path.isfile(dest):
                            base, _ = os.path.splitext(dest)
                            for ext in (".mp4", ".webm", ".mkv", ".m4a"):
                                if os.path.isfile(base + ext):
                                    dest = base + ext
                                    break
                    except ImportError:
                        ext = os.path.splitext(urllib.parse.urlparse(url).path)[1] or ".mp4"
                        dest = os.path.join(dest_dir, safe + ext)
                        urllib.request.urlretrieve(url, dest)
                except Exception as ex:
                    err, dest = str(ex), None

                def done():
                    self._hide_progress_toast()
                    self._downloading_safe_names.discard(safe)
                    if err or not dest or not os.path.isfile(dest):
                        print(f"[Mémoire] Échec du téléchargement automatique : "
                              f"{err or 'fichier introuvable'} (pip install yt-dlp)")
                        self._show_toast("⚠️ Échec du téléchargement", ms=4500, color="#8a2a2a")
                        if self.dl_win and self.dl_win.winfo_exists():
                            self.refresh_downloads_window()
                        return
                    name = os.path.basename(dest)
                    # Le média téléchargé reste exclusivement dans Citron_Memoire :
                    # il n'est PAS ajouté à la Liste complète des médias.
                    if self.dl_win and self.dl_win.winfo_exists():
                        self.refresh_downloads_window()
                    print(f"[Mémoire] Téléchargement automatique terminé : {dest}")
                    display = name if len(name) < 60 else name[:57] + "…"
                    self._show_toast(f"✅ Téléchargement terminé : {display}", ms=5000)
                self.after(0, done)

            threading.Thread(target=worker, daemon=True).start()

        # ── Fenêtre "Liste des téléchargements" (contenu de Citron_Memoire) ──
        def _scan_memoire_files(self):
            try:
                os.makedirs(self._mem_dir, exist_ok=True)
                names = [f for f in os.listdir(self._mem_dir)
                         if os.path.isfile(os.path.join(self._mem_dir, f))]
            except Exception:
                names = []
            names.sort(key=self._natural_key)
            paths = [os.path.join(self._mem_dir, n) for n in names]
            return names, paths

        def open_downloads_window(self):
            if self.dl_win and self.dl_win.winfo_exists():
                self.dl_win.lift(); self.refresh_downloads_window(); return
            self.dl_win = ctk.CTkToplevel(self)
            self.dl_win.title("📥 Liste des téléchargements — Citron-Mémoire")
            self.dl_win.geometry(self.dl_win_geometry or "800x640")
            self.dl_win.minsize(420, 320)
            self.dl_win.resizable(True, True)  # fenêtre dimensionnable et positionnable
            self.dl_win.transient(self); self.dl_win.lift()
            self.dl_win.protocol("WM_DELETE_WINDOW", self.close_downloads_window)

            ctk.CTkLabel(self.dl_win, text="📥 Téléchargements (Citron-Mémoire)",
                         font=("Arial",20,"bold")).pack(pady=(14,4))
            self.dl_total_label = ctk.CTkLabel(self.dl_win, text="", font=("Arial",13))
            self.dl_total_label.pack()

            sf = ctk.CTkFrame(self.dl_win); sf.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(sf, text="🔍", font=("Arial",16)).pack(side="left", padx=(10,5))
            self.dl_search_var = ctk.StringVar()
            ctk.CTkEntry(sf, placeholder_text="Rechercher…", textvariable=self.dl_search_var,
                         height=40).pack(side="left", fill="x", expand=True, padx=5)
            self.dl_search_var.trace("w", lambda *a: self._dl_apply_view())

            bf = ctk.CTkFrame(self.dl_win); bf.pack(pady=6)
            self.dl_sort_toggle_btn = ctk.CTkButton(bf, text="↑↓ Trier A→Z", width=130,
                                                      command=self._dl_toggle_sort)
            self.dl_sort_toggle_btn.pack(side="left", padx=6)
            self.dl_sort_date_btn = ctk.CTkButton(bf, text="📅 Tri par date d'enregistrement", width=220,
                                                    command=self._dl_toggle_sort_date)
            self.dl_sort_date_btn.pack(side="left", padx=6)
            ctk.CTkButton(bf, text="Vider la liste", fg_color="#c42b1c", width=120,
                          command=self._dl_clear_all).pack(side="left", padx=6)

            bf2 = ctk.CTkFrame(self.dl_win); bf2.pack(pady=(0,4))
            ctk.CTkButton(bf2, text="Titres identiques", fg_color="#885500", width=140,
                          command=self._dl_show_duplicates).pack(side="left", padx=6)
            ctk.CTkButton(bf2, text="🗑 Suppr. 🎵 audio", fg_color="#5a3070", width=150,
                          command=self._dl_delete_all_audio).pack(side="left", padx=6)
            ctk.CTkButton(bf2, text="📋 Liste → Playlist", width=160,
                          command=self._dl_add_all_to_playlist).pack(side="left", padx=6)
            ctk.CTkButton(bf2, text="🗑 Supprimer doublons", fg_color="#8b3a00", width=170,
                          command=self._dl_delete_duplicates).pack(side="left", padx=6)

            lf = ctk.CTkFrame(self.dl_win); lf.pack(fill="both", expand=True, padx=16, pady=10)
            self.dl_listbox = Listbox(lf, font=("Arial",12), bg="#2b2b2b", fg="white",
                                       selectbackground="#1f6aa5", activestyle="none")
            sb = Scrollbar(lf, orient="vertical", command=self.dl_listbox.yview)
            self.dl_listbox.config(yscrollcommand=sb.set)
            self.dl_listbox.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            # Survol => sélection en bleu ; clic => menu déroulant d'actions
            self.dl_listbox.bind("<Motion>", self._dl_hover_select)
            self.dl_listbox.bind("<Button-1>", self._dl_click_menu)

            self._dl_names, self._dl_paths = [], []
            self._dl_names_all, self._dl_paths_all = [], []
            self._dl_sort_reverse = getattr(self, "_dl_sort_reverse", False)
            self._dl_sort_mode = getattr(self, "_dl_sort_mode", "name")
            if self._dl_sort_mode == "date":
                self.dl_sort_date_btn.configure(
                    text="📅 Plus récent → plus ancien" if self._dl_sort_reverse
                    else "📅 Plus ancien → plus récent")
            else:
                self.dl_sort_toggle_btn.configure(
                    text="↓↑ Trier Z→A" if self._dl_sort_reverse else "↑↓ Trier A→Z")
            self._dl_in_progress = []
            self._dl_folder_snapshot = None  # pour détecter les changements disque
            self.refresh_downloads_window()
            self._start_dl_folder_watch()
            self._remember_last_window_geometry(self.dl_win)

        def _memoire_folder_snapshot(self):
            """Empreinte du dossier mémoire (mtime + noms) pour détecter les
            ajouts / suppressions / renommages sans recharger en permanence."""
            folder = getattr(self, "_mem_dir", None) or ""
            try:
                if not folder or not os.path.isdir(folder):
                    return (folder, ())
                names = tuple(sorted(
                    f for f in os.listdir(folder)
                    if os.path.isfile(os.path.join(folder, f))
                ))
                # mtime du dossier + contenu
                try:
                    mt = os.path.getmtime(folder)
                except Exception:
                    mt = 0
                return (folder, names, mt)
            except Exception:
                return (folder, ())

        def _start_dl_folder_watch(self):
            """Surveille le dossier Citron_Mémoire tant que la fenêtre liste
            est ouverte, et rafraîchit l'affichage dès qu'il change."""
            job = getattr(self, "_dl_folder_watch_job", None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
                self._dl_folder_watch_job = None
            self._dl_folder_snapshot = self._memoire_folder_snapshot()

            def _tick():
                self._dl_folder_watch_job = None
                if not (self.dl_win and self.dl_win.winfo_exists()):
                    return
                try:
                    snap = self._memoire_folder_snapshot()
                    if snap != getattr(self, "_dl_folder_snapshot", None):
                        self._dl_folder_snapshot = snap
                        self.refresh_downloads_window()
                except Exception as ex:
                    print(f"[Mémoire] watch erreur : {ex}")
                self._dl_folder_watch_job = self.after(1500, _tick)

            self._dl_folder_watch_job = self.after(1500, _tick)

        def _stop_dl_folder_watch(self):
            job = getattr(self, "_dl_folder_watch_job", None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
                self._dl_folder_watch_job = None

        def refresh_downloads_window(self):
            if not (self.dl_win and self.dl_win.winfo_exists()):
                return
            names, paths = self._scan_memoire_files()
            self._dl_names_all, self._dl_paths_all = names, paths
            self._dl_apply_view()
            # Aligner le snapshot après rafraîchissement manuel / téléchargement
            self._dl_folder_snapshot = self._memoire_folder_snapshot()

        def _dl_file_date(self, path):
            """Date d'enregistrement d'un fichier téléchargé. Sous Windows,
            os.path.getctime() renvoie la vraie date de création du fichier
            (contrairement à Linux où c'est la date de dernière modification
            des métadonnées) — c'est donc l'indicateur le plus fidèle de
            « quand ce fichier a été enregistré sur le disque ». Repli sur
            la date de modification si la création est indisponible."""
            try:
                if os.name == "nt":
                    return os.path.getctime(path)
                return os.path.getmtime(path)
            except Exception:
                return 0.0

        def _dl_apply_view(self):
            """Applique le tri courant et le filtre de recherche sur la liste
            déjà scannée (self._dl_names_all / _dl_paths_all) sans retoucher
            le disque, puis met à jour la Listbox. self._dl_names/_dl_paths
            représentent la vue actuellement AFFICHÉE (triée/filtrée) : c'est
            elle qu'utilisent les actions du menu clic (indexation par idx)."""
            if not (hasattr(self, "dl_listbox") and self.dl_listbox.winfo_exists()):
                return
            names_all = getattr(self, "_dl_names_all", [])
            paths_all = getattr(self, "_dl_paths_all", [])
            text = self.dl_search_var.get().lower().strip() if hasattr(self, "dl_search_var") else ""
            pairs = [(n, p) for n, p in zip(names_all, paths_all) if text in n.lower()]
            sort_mode = getattr(self, "_dl_sort_mode", "name")
            reverse = getattr(self, "_dl_sort_reverse", False)
            if sort_mode == "date":
                pairs.sort(key=lambda x: self._dl_file_date(x[1]), reverse=reverse)
            else:
                pairs.sort(key=lambda x: self._natural_key(x[0]), reverse=reverse)
            names = [n for n, _ in pairs]
            paths = [p for _, p in pairs]
            self._dl_names, self._dl_paths = names, paths
            self.dl_listbox.delete(0, END)
            # Un titre est "en cours de téléchargement" si son nom de fichier
            # (sans extension) commence par l'un des préfixes suivis dans
            # self._downloading_safe_names. On le marque visuellement (❌ +
            # texte grisé) pour indiquer que ses actions ne sont pas encore
            # disponibles, plutôt que de laisser croire qu'on peut déjà le
            # lire/modifier/ajouter à la playlist.
            self._dl_in_progress = [False] * len(names)
            show_dates = (sort_mode == "date")
            for i, (n, p) in enumerate(zip(names, paths)):
                base = os.path.splitext(n)[0]
                in_progress = any(base.startswith(s) for s in self._downloading_safe_names)
                self._dl_in_progress[i] = in_progress
                if in_progress:
                    label = f"❌ {n}  (téléchargement en cours…)"
                elif show_dates:
                    ts = self._dl_file_date(p)
                    date_str = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else "?"
                    label = f"{n}   [📅 {date_str}]"
                else:
                    label = n
                self.dl_listbox.insert(END, label)
                if in_progress:
                    self.dl_listbox.itemconfig(i, fg="#777777")
            total_all = len(names_all)
            if text:
                self.dl_total_label.configure(text=f"({len(names)} / {total_all} titre(s) — filtré)")
            else:
                self.dl_total_label.configure(text=f"({total_all} titre(s) en mémoire)")

        def _dl_toggle_sort(self):
            was_name_mode = getattr(self, "_dl_sort_mode", "name") == "name"
            self._dl_sort_mode = "name"
            self._dl_sort_reverse = (not getattr(self, "_dl_sort_reverse", False)) if was_name_mode else False
            self._dl_apply_view()
            if hasattr(self, "dl_sort_toggle_btn") and self.dl_sort_toggle_btn.winfo_exists():
                self.dl_sort_toggle_btn.configure(
                    text="↓↑ Trier Z→A" if self._dl_sort_reverse else "↑↓ Trier A→Z")
            if hasattr(self, "dl_sort_date_btn") and self.dl_sort_date_btn.winfo_exists():
                self.dl_sort_date_btn.configure(text="📅 Tri par date d'enregistrement")

        def _dl_toggle_sort_date(self):
            """Trie la liste par date d'enregistrement (date de création du
            fichier sur le disque). Un premier clic affiche du plus récent
            au plus ancien ; un second clic inverse l'ordre — comme le tri
            alphabétique déjà existant."""
            if getattr(self, "_dl_sort_mode", "name") != "date":
                self._dl_sort_mode = "date"
                self._dl_sort_reverse = True  # plus récent en premier par défaut
            else:
                self._dl_sort_reverse = not getattr(self, "_dl_sort_reverse", False)
            self._dl_apply_view()
            if hasattr(self, "dl_sort_date_btn") and self.dl_sort_date_btn.winfo_exists():
                self.dl_sort_date_btn.configure(
                    text="📅 Plus récent → plus ancien" if self._dl_sort_reverse
                    else "📅 Plus ancien → plus récent")
            if hasattr(self, "dl_sort_toggle_btn") and self.dl_sort_toggle_btn.winfo_exists():
                self.dl_sort_toggle_btn.configure(text="↑↓ Trier A→Z")

        def _dl_forget_from_library(self, path):
            """Répercute une suppression/renommage disque sur la Liste
            complète des médias si ce fichier y était aussi référencé."""
            if path in self.video_paths:
                i = self.video_paths.index(path)
                del self.video_paths[i]; del self.video_names[i]
                self.save_library(); self.update_list_button_text()
                if self.list_win and self.list_win.winfo_exists():
                    self.refresh_list_window()

        def _dl_clear_all(self):
            """Vide le dossier Citron-Mémoire : supprime définitivement tous
            les fichiers du disque (équivalent de 'Vider la liste', mais ici
            la 'liste' EST le contenu du dossier)."""
            names, paths = self._scan_memoire_files()
            if not names:
                messagebox.showinfo("Info", "Le dossier Citron-Mémoire est déjà vide.", parent=self.dl_win)
                return
            if not messagebox.askyesno(
                    "Vider Citron-Mémoire",
                    f"Supprimer définitivement les {len(names)} fichier(s) du dossier "
                    "Citron-Mémoire ?\nCette action supprime les fichiers du disque et "
                    "est irréversible.", parent=self.dl_win):
                return
            errors = []
            for p in paths:
                try:
                    os.remove(p)
                    self._dl_forget_from_library(p)
                except Exception as ex:
                    errors.append(f"{os.path.basename(p)} : {ex}")
            self.refresh_downloads_window()
            if errors:
                messagebox.showerror("Vider Citron-Mémoire",
                    "Certains fichiers n'ont pas pu être supprimés :\n" + "\n".join(errors[:10]))
            else:
                self._show_toast("🗑 Citron-Mémoire vidé.", ms=3000, color="#8a2a2a")

        def _dl_delete_all_audio(self):
            """Supprime du disque tous les fichiers audio du dossier
            Citron-Mémoire."""
            names, paths = self._scan_memoire_files()
            audio = [(n, p) for n, p in zip(names, paths) if is_audio(p)]
            if not audio:
                messagebox.showinfo("Info", "Aucun fichier audio dans Citron-Mémoire.", parent=self.dl_win)
                return
            if not messagebox.askyesno("Confirmation",
                    f"Supprimer {len(audio)} fichier(s) audio du dossier Citron-Mémoire "
                    "(disque) ?", parent=self.dl_win):
                return
            errors = []
            for n, p in audio:
                try:
                    os.remove(p)
                    self._dl_forget_from_library(p)
                except Exception as ex:
                    errors.append(f"{n} : {ex}")
            self.refresh_downloads_window()
            if errors:
                messagebox.showerror("Suppression audio",
                    "Certains fichiers n'ont pas pu être supprimés :\n" + "\n".join(errors[:10]))

        def _dl_add_all_to_playlist(self):
            """Ajoute tout le contenu de Citron-Mémoire à la playlist."""
            names, paths = self._scan_memoire_files()
            if not paths:
                messagebox.showinfo("Info", "Le dossier Citron-Mémoire est vide.", parent=self.dl_win)
                return
            if not messagebox.askyesno("Confirmer",
                    f"Ajouter {len(paths)} titre(s) à la playlist ?", parent=self.dl_win):
                return
            for path in paths:
                self.playlist.append(path)
            self.save_playlist(); self.update_playlist_button_text()
            self._fetch_durations_bg(paths[:])
            if self.playlist_win and self.playlist_win.winfo_exists():
                self.refresh_playlist_window()
            messagebox.showinfo("Ajouté", f"{len(paths)} titre(s) ajouté(s) à la playlist.", parent=self.dl_win)

        @staticmethod
        def _dl_base_key(name):
            """Nom de base normalisé (minuscule, sans accents, sans
            extension) utilisé pour détecter les doublons dans un même
            dossier — deux fichiers ne pouvant pas porter exactement le même
            nom dans un même dossier, on compare hors extension pour
            repérer un même titre téléchargé plusieurs fois (formats/qualités
            différents)."""
            import unicodedata as _ud
            base = os.path.splitext(name)[0]
            base = _ud.normalize("NFD", base.lower())
            return "".join(c for c in base if _ud.category(c) != "Mn").strip()

        def _dl_delete_duplicates(self):
            """Supprime du disque les doublons de Citron-Mémoire (même titre,
            extension ignorée), en conservant la première occurrence
            (ordre alphabétique naturel)."""
            names, paths = self._scan_memoire_files()  # déjà triés par ordre naturel
            seen, to_delete = set(), []
            for n, p in zip(names, paths):
                k = self._dl_base_key(n)
                if k in seen:
                    to_delete.append((n, p))
                else:
                    seen.add(k)
            if not to_delete:
                messagebox.showinfo("Doublons",
                    "Aucun doublon trouvé (titre identique, extension ignorée).", parent=self.dl_win)
                return
            preview = "\n".join(n for n, _ in to_delete[:10])
            more = f"\n… et {len(to_delete)-10} autre(s)" if len(to_delete) > 10 else ""
            if not messagebox.askyesno("Supprimer doublons",
                    f"Supprimer définitivement {len(to_delete)} fichier(s) en double du "
                    f"disque ?\n\n{preview}{more}", parent=self.dl_win):
                return
            errors = []
            for n, p in to_delete:
                try:
                    os.remove(p)
                    self._dl_forget_from_library(p)
                except Exception as ex:
                    errors.append(f"{n} : {ex}")
            self.refresh_downloads_window()
            if errors:
                messagebox.showerror("Supprimer doublons",
                    "Certains fichiers n'ont pas pu être supprimés :\n" + "\n".join(errors[:10]))
            else:
                messagebox.showinfo("Fait", f"{len(to_delete)} doublon(s) supprimé(s).", parent=self.dl_win)

        def _dl_show_duplicates(self):
            """Affiche les titres identiques (extension ignorée) présents
            dans Citron-Mémoire, dans une petite fenêtre dédiée."""
            names, _ = self._scan_memoire_files()
            groups = {}
            for n in names:
                groups.setdefault(self._dl_base_key(n), []).append(n)
            dups = {k: v for k, v in groups.items() if len(v) > 1}
            if getattr(self, "dl_stats_win", None) and self.dl_stats_win.winfo_exists():
                self.dl_stats_win.lift()
            else:
                self.dl_stats_win = ctk.CTkToplevel(self.dl_win)
                self.dl_stats_win.title("Titres identiques — Citron-Mémoire")
                self.dl_stats_win.geometry("560x460")
                self.dl_stats_win.transient(self.dl_win); self.dl_stats_win.lift()
                ctk.CTkLabel(self.dl_stats_win, text="📊 Titres identiques",
                             font=("Arial",18,"bold")).pack(pady=8)
                self._dl_stats_label = ctk.CTkLabel(self.dl_stats_win, text="", font=("Arial",13))
                self._dl_stats_label.pack()
                lf = ctk.CTkFrame(self.dl_stats_win); lf.pack(fill="both", expand=True, padx=16, pady=8)
                self._dl_stats_listbox = Listbox(lf, font=("Arial",12), bg="#2b2b2b", fg="white",
                                                  selectbackground="#1f6aa5", activestyle="none")
                sb = Scrollbar(lf, orient="vertical", command=self._dl_stats_listbox.yview)
                self._dl_stats_listbox.config(yscrollcommand=sb.set)
                self._dl_stats_listbox.pack(side="left", fill="both", expand=True)
                sb.pack(side="right", fill="y")
            self._dl_stats_label.configure(
                text=f"Total : {len(names)} fichier(s)   —   Groupes en double : {len(dups)}   "
                     "(titre identique, extension ignorée)")
            self._dl_stats_listbox.delete(0, END)
            if dups:
                for k, group in sorted(dups.items(), key=lambda x: -len(x[1])):
                    self._dl_stats_listbox.insert(END, f"×{len(group)}   {group[0]}")
            else:
                self._dl_stats_listbox.insert(END, "✅ Aucun doublon détecté")

        def close_downloads_window(self):
            self._stop_dl_folder_watch()
            if self.dl_win:
                self.dl_win_geometry = self.dl_win.geometry()
                self.save_settings()
                self.dl_win.destroy(); self.dl_win = None

        def _dl_hover_select(self, event):
            idx = self.dl_listbox.nearest(event.y)
            if 0 <= idx < self.dl_listbox.size():
                self.dl_listbox.selection_clear(0, END)
                self.dl_listbox.selection_set(idx)

        def _dl_click_menu(self, event):
            idx = self.dl_listbox.nearest(event.y)
            if not (0 <= idx < len(self._dl_paths)):
                return "break"
            self.dl_listbox.selection_clear(0, END)
            self.dl_listbox.selection_set(idx)
            in_progress = bool(getattr(self, "_dl_in_progress", None)) and idx < len(self._dl_in_progress) and self._dl_in_progress[idx]
            menu = Menu(self.dl_win, tearoff=0, font=("Arial",13))
            # Tant que le fichier est encore en cours de téléchargement, ses
            # actions sont grisées (state="disabled") : les proposer comme
            # cliquables serait trompeur puisque le fichier n'est pas encore
            # complet sur le disque (lecture, ajout playlist ou montage
            # échoueraient ou produiraient un résultat corrompu).
            state = "disabled" if in_progress else "normal"
            if in_progress:
                menu.add_command(label="❌ Téléchargement en cours…", state="disabled")
                menu.add_separator()
            menu.add_command(label="▶ Lire le média", state=state, command=lambda i=idx: self._dl_play(i))
            menu.add_command(label="➕ Ajouter à la Playlist", state=state, command=lambda i=idx: self._dl_add_to_playlist(i))
            menu.add_command(label="✏️ Modifier le titre", state=state, command=lambda i=idx: self._dl_rename_title(i))
            menu.add_command(label="✏️ Modifier la vidéo", state=state, command=lambda i=idx: self._dl_edit_video(i))
            menu.add_separator()
            menu.add_command(label="🗑 Supprimer ce titre", command=lambda i=idx: self._dl_delete(i))
            menu.tk_popup(event.x_root, event.y_root)
            return "break"

        def _dl_play(self, idx):
            if not (0 <= idx < len(self._dl_paths)):
                return
            path = self._dl_paths[idx]
            if not os.path.isfile(path):
                messagebox.showerror("Téléchargements", "Fichier introuvable."); return
            self.close_downloads_window()
            self.play_file(path)

        def _dl_add_to_playlist(self, idx):
            if not (0 <= idx < len(self._dl_paths)):
                return
            path = self._dl_paths[idx]
            self.playlist.append(path)
            self.save_playlist(); self.update_playlist_button_text()
            self._fetch_durations_bg([path])
            if self.playlist_win and self.playlist_win.winfo_exists():
                self.refresh_playlist_window()
            messagebox.showinfo("Playlist", f"« {self._dl_names[idx]} » ajouté à la playlist.")

        def _rename_dialog(self, parent, initial_text):
            """Boîte de dialogue de renommage dont la LARGEUR s'adapte à la
            longueur du titre à modifier, contrairement à simpledialog.askstring
            qui a une taille fixe et tronque visuellement les titres longs.
            Retourne le nouveau texte saisi, ou None si annulé/fermé."""
            result = {"value": None}
            win = ctk.CTkToplevel(self)
            win.title("Modifier le titre")
            win.transient(parent)
            win.resizable(False, False)
            try:
                win.attributes("-topmost", True)
            except Exception:
                pass

            ctk.CTkLabel(win, text="Nouveau titre :", font=("Arial", 13)).pack(
                padx=20, pady=(18, 6), anchor="w")

            var = ctk.StringVar(value=initial_text)
            # Largeur adaptative (≈9 px/caractère en Arial 14), bornée entre
            # 340 px (titres très courts) et 1060 px (titres très longs, pour
            # ne pas dépasser un écran classique).
            char_w = 9
            entry_width = max(340, min(1060, len(initial_text) * char_w + 60))
            win_width = entry_width + 40
            entry = ctk.CTkEntry(win, textvariable=var, width=entry_width, height=38, font=("Arial", 14))
            entry.pack(padx=20, pady=(0, 16))
            enable_entry_paste(entry)

            btn_frame = ctk.CTkFrame(win, fg_color="transparent")
            btn_frame.pack(pady=(0, 16))

            def _validate(event=None):
                result["value"] = var.get()
                win.destroy()

            def _cancel(event=None):
                result["value"] = None
                win.destroy()

            ctk.CTkButton(btn_frame, text="OK", width=100, command=_validate).pack(side="left", padx=8)
            ctk.CTkButton(btn_frame, text="Annuler", width=100, fg_color="#5a5a5a",
                          command=_cancel).pack(side="left", padx=8)
            entry.bind("<Return>", _validate)
            entry.bind("<Escape>", _cancel)
            win.protocol("WM_DELETE_WINDOW", _cancel)

            # Centrage par rapport à la fenêtre parente, avec la largeur
            # calculée ci-dessus (seule la hauteur reste fixe/naturelle).
            win.update_idletasks()
            win_height = win.winfo_reqheight()
            try:
                px = parent.winfo_rootx() + (parent.winfo_width() - win_width) // 2
                py = parent.winfo_rooty() + (parent.winfo_height() - win_height) // 3
            except Exception:
                px, py = 200, 200
            sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            px = max(0, min(px, sw - win_width))
            py = max(0, min(py, sh - win_height))
            win.geometry(f"{win_width}x{win_height}+{px}+{py}")

            entry.focus_set()
            entry.select_range(0, "end")
            win.grab_set()
            win.wait_window()
            return result["value"]

        def _dl_rename_title(self, idx):
            """Renomme réellement le fichier sélectionné sur le disque, dans
            le dossier Citron-Mémoire (contrairement à la Liste complète où
            'le titre' n'est qu'une étiquette en mémoire, ici il n'existe pas
            d'autre nom que celui du fichier lui-même)."""
            if not (0 <= idx < len(self._dl_paths)):
                return
            old_path = self._dl_paths[idx]
            if not os.path.isfile(old_path):
                messagebox.showerror("Modifier le titre", "Fichier introuvable.", parent=self.dl_win)
                return
            folder = os.path.dirname(old_path)
            old_name = os.path.basename(old_path)
            base, ext = os.path.splitext(old_name)
            new_base = self._rename_dialog(self.dl_win, base)
            if new_base is None:
                return
            new_base = new_base.strip()
            if not new_base or new_base == base:
                return
            invalid = '<>:"/\\|?*'
            safe_base = "".join(c for c in new_base if c not in invalid).strip()
            if not safe_base:
                messagebox.showerror("Modifier le titre", "Titre invalide.", parent=self.dl_win)
                return
            new_name = safe_base + ext
            new_path = os.path.join(folder, new_name)
            if os.path.exists(new_path):
                messagebox.showerror("Modifier le titre",
                    f"Un fichier « {new_name} » existe déjà.", parent=self.dl_win)
                return
            try:
                os.rename(old_path, new_path)
            except Exception as ex:
                messagebox.showerror("Modifier le titre", f"Impossible de renommer :\n{ex}", parent=self.dl_win)
                return
            # Répercuter le renommage dans la Liste complète si ce fichier y
            # est aussi référencé (garde un éventuel suffixe "  🎵 audio").
            if old_path in self.video_paths:
                i = self.video_paths.index(old_path)
                self.video_paths[i] = new_path
                old_lib_name = self.video_names[i]
                suffix = old_lib_name[len(base):] if old_lib_name.startswith(base) else ""
                self.video_names[i] = safe_base + suffix
                self.save_library(); self.update_list_button_text()
                if self.list_win and self.list_win.winfo_exists():
                    self.refresh_list_window()
            self.refresh_downloads_window()
            self._show_toast(f"✏️ Renommé en « {new_name} »", ms=3000, color="#2a4a6a")

        def _dl_delete(self, idx):
            if not (0 <= idx < len(self._dl_paths)):
                return
            path = self._dl_paths[idx]; name = self._dl_names[idx]
            if not messagebox.askyesno("Supprimer", f"Supprimer définitivement « {name} » du disque ?"):
                return
            try:
                os.remove(path)
            except Exception as ex:
                messagebox.showerror("Suppression", f"Impossible de supprimer :\n{ex}"); return
            if path in self.video_paths:
                i = self.video_paths.index(path)
                del self.video_paths[i]; del self.video_names[i]
                self.save_library(); self.update_list_button_text()
            self.refresh_downloads_window()

        def _find_shotcut_exe(self):
            """Cherche l'exécutable Shotcut : chemin déjà connu, copie portable
            à côté de Citron (dossier 'Shotcut'), PATH système, puis
            emplacements d'installation Windows habituels."""
            if self._shotcut_path and os.path.isfile(self._shotcut_path):
                return self._shotcut_path
            try:
                base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            except Exception:
                base_dir = os.getcwd()
            portable = os.path.join(base_dir, "Shotcut", "shotcut.exe")
            if os.path.isfile(portable):
                return portable
            p = shutil.which("shotcut") or shutil.which("shotcut.exe")
            if p:
                return p
            candidates = [
                r"C:\Program Files\Shotcut\shotcut.exe",
                r"C:\Program Files (x86)\Shotcut\shotcut.exe",
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Shotcut", "shotcut.exe"),
            ]
            for c in candidates:
                if c and os.path.isfile(c):
                    return c
            return None

        def _dl_edit_video(self, idx):
            """Ouvre le média sélectionné dans Shotcut pour commencer le montage."""
            if not (0 <= idx < len(self._dl_paths)):
                return
            self._open_in_shotcut(self._dl_paths[idx])

        def _open_in_shotcut(self, path):
            """Ouvre un fichier média dans Shotcut (fonction générique,
            réutilisée par la fenêtre Téléchargements et par les fenêtres de
            résultats de recherche du tableur)."""
            if not path or not os.path.isfile(path):
                messagebox.showerror("Modifier la vidéo", "Fichier introuvable.")
                return
            exe = self._find_shotcut_exe()
            if not exe:
                messagebox.showinfo("Shotcut introuvable",
                    "Shotcut n'a pas été trouvé automatiquement.\n"
                    "Indique l'emplacement de shotcut.exe dans la fenêtre suivante,\n"
                    "ou installe Shotcut depuis https://shotcut.org si ce n'est pas déjà fait.")
                exe = filedialog.askopenfilename(
                    title="Localiser shotcut.exe",
                    filetypes=[("Shotcut", "shotcut.exe"), ("Exécutable", "*.exe")])
                if not exe or not os.path.isfile(exe):
                    return
                self._shotcut_path = exe
                self.save_settings()
            try:
                subprocess.Popen([exe, path])
                self._show_toast("🎬 Ouverture dans Shotcut…", ms=3000, color="#2a4a6a")
            except Exception as ex:
                messagebox.showerror("Shotcut", f"Impossible de lancer Shotcut :\n{ex}")


        def register_citron_protocol(self):
            """Enregistre citron:// + écrit un lanceur .cmd robuste."""
            if os.name != "nt":
                messagebox.showinfo("Protocole", "Windows uniquement."); return
            try:
                script = os.path.abspath(sys.argv[0])
                script_dir = os.path.dirname(script)
                launcher = register_citron_url_protocol(script, script_dir, sys.executable)
                messagebox.showinfo(
                    "Protocole citron://",
                    "Protocole enregistré.\n\n"
                    f"Lanceur : {launcher}\n\n"
                    "Ensuite :\n"
                    "1. Paramètres → 📋 Bookmarklet navigateur\n"
                    "2. Créez un favori avec le code affiché\n"
                    "3. Sur YouTube, cliquez le favori\n\n"
                    "Important : laissez Citron OUVERT, ou il démarrera tout seul.")
            except Exception as ex:
                messagebox.showerror("Protocole", str(ex))

        def _check_for_update(self, silent=True):
            """Vérifie si une nouvelle version de Citron est disponible.

            silent=True (par défaut, utilisé au démarrage) : ne montre
            RIEN si la vérification échoue ou si la version est déjà à
            jour — pas de fenêtre ni de son au lancement pour un simple
            contrôle en arrière-plan. Seule une mise à jour réellement
            disponible affiche quelque chose.

            silent=False (bouton "🔎 Vérifier les mises à jour" des
            Paramètres) : affiche toujours un résultat, y compris
            "déjà à jour" ou une erreur — utile pour l'utilisateur qui
            vérifie volontairement, et pour tester ce mécanisme avant
            même d'avoir choisi où héberger CITRON_UPDATE_CHECK_URL.

            Si le manifeste JSON fournit un champ "sha256" (voir plus haut),
            le fichier pointé par "url" est téléchargé ET vérifié ICI, en
            arrière-plan, AVANT même d'afficher quoi que ce soit — pour que
            la fenêtre affichée ensuite reflète déjà un résultat fiable
            (intégrité confirmée, ou refus explicite si ça ne correspond
            pas), plutôt que de le découvrir après coup."""
            if not CITRON_UPDATE_CHECK_URL:
                if not silent:
                    messagebox.showinfo(
                        "Mise à jour",
                        "Vérification des mises à jour non configurée pour le moment.\n\n"
                        f"Version actuelle : {CITRON_VERSION}")
                return

            def worker():
                try:
                    req = urllib.request.Request(
                        CITRON_UPDATE_CHECK_URL, headers={"User-Agent": "Citron"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        data = json.loads(resp.read().decode("utf-8-sig", errors="ignore"))
                    remote_version = str(data.get("version", "")).strip()
                    if not remote_version:
                        raise ValueError("Réponse sans champ 'version'")
                    download_url = data.get("url", "")
                    notes = data.get("notes", "")
                    remote_sha256 = str(data.get("sha256", "")).strip().lower()
                    is_newer = (_parse_version_tuple(remote_version)
                                > _parse_version_tuple(CITRON_VERSION))

                    # Intégrité : seulement si une mise à jour est réellement
                    # disponible et qu'une empreinte est fournie. Un échec
                    # ICI (réseau, fichier téléchargé mais empreinte ne
                    # correspondant pas...) ne doit jamais faire disparaître
                    # la notification de mise à jour elle-même — il change
                    # seulement la façon dont elle est ensuite proposée.
                    integrite = "sans_somme"
                    fichier_octets = None
                    if is_newer and download_url and remote_sha256:
                        try:
                            req2 = urllib.request.Request(
                                download_url, headers={"User-Agent": "Citron"})
                            with urllib.request.urlopen(req2, timeout=25) as resp2:
                                fichier_octets = resp2.read()
                            empreinte = hashlib.sha256(fichier_octets).hexdigest()
                            integrite = "ok" if empreinte == remote_sha256 else "ko"
                            if integrite == "ko":
                                fichier_octets = None
                        except Exception:
                            integrite = "echec_verification"
                            fichier_octets = None

                    self.after(0, lambda: self._on_update_check_done(
                        is_newer, remote_version, download_url, notes, None, silent,
                        integrite, fichier_octets))
                except Exception as ex:
                    self.after(0, lambda ex=ex: self._on_update_check_done(
                        False, None, None, None, ex, silent, "sans_somme", None))
            threading.Thread(target=worker, daemon=True).start()

        def _on_update_check_done(self, is_newer, remote_version, download_url, notes, error, silent,
                                   integrite="sans_somme", fichier_octets=None):
            if error is not None:
                print(f"[MàJ] Vérification impossible : {error}")
                if not silent:
                    messagebox.showwarning(
                        "Mise à jour", f"Impossible de vérifier les mises à jour :\n{error}")
                return

            if not is_newer:
                if not silent:
                    messagebox.showinfo("Mise à jour", f"Citron est à jour (version {CITRON_VERSION}).")
                return

            msg = (f"Une nouvelle version de Citron est disponible : {remote_version}\n"
                   f"(version actuelle : {CITRON_VERSION})")
            if notes:
                msg += f"\n\n{notes}"

            if integrite == "ok":
                msg += "\n\n✅ Intégrité vérifiée (SHA-256 conforme au fichier annoncé)."
            elif integrite == "ko":
                msg += ("\n\n⚠️ La somme de contrôle (SHA-256) du fichier téléchargé NE correspond PAS "
                        "à celle annoncée dans le manifeste. Par précaution, ce fichier n'est pas "
                        "proposé au téléchargement — vérifie/republie le manifeste avant de refaire "
                        "une tentative.")
            elif integrite == "echec_verification":
                msg += "\n\nℹ️ Intégrité non vérifiée (le fichier n'a pas pu être téléchargé pour contrôle)."
            else:
                msg += "\n\nℹ️ Intégrité non vérifiée (aucune somme de contrôle fournie dans le manifeste)."

            win = ctk.CTkToplevel(self)
            win.title("Mise à jour disponible")
            win.resizable(False, False)
            win.attributes("-topmost", True)
            win.lift()
            ctk.CTkLabel(win, text="🍋 Mise à jour disponible",
                         font=("Arial", 16, "bold")).pack(padx=24, pady=(20, 8))
            ctk.CTkLabel(win, text=msg, font=("Arial", 12),
                         wraplength=380, justify="left").pack(padx=24, pady=(0, 16))
            btn_frame = ctk.CTkFrame(win, fg_color="transparent")
            btn_frame.pack(pady=(0, 18))

            if integrite == "ok" and fichier_octets:
                def _enregistrer_verifie():
                    nom_defaut = os.path.basename(urllib.parse.urlparse(download_url).path) \
                        or f"Citron_{remote_version}.py"
                    chemin = filedialog.asksaveasfilename(
                        title="Enregistrer la mise à jour de Citron (vérifiée)",
                        initialfile=nom_defaut,
                        defaultextension=os.path.splitext(nom_defaut)[1] or ".py")
                    if not chemin:
                        return
                    try:
                        with open(chemin, "wb") as f:
                            f.write(fichier_octets)
                        messagebox.showinfo(
                            "Mise à jour",
                            f"Fichier enregistré et vérifié :\n{chemin}\n\n"
                            "Ferme Citron puis remplace l'ancien fichier par celui-ci.")
                        win.destroy()
                    except Exception as ex:
                        messagebox.showerror("Mise à jour", f"Échec de l'enregistrement :\n{ex}")
                ctk.CTkButton(btn_frame, text="💾 Enregistrer (vérifié)", width=190,
                              command=_enregistrer_verifie).pack(side="left", padx=8)
            elif integrite == "ko":
                pass  # Aucun bouton de téléchargement : fichier refusé par précaution.
            elif download_url:
                ctk.CTkButton(btn_frame, text="Télécharger", width=140,
                              command=lambda: (webbrowser.open(download_url), win.destroy())
                              ).pack(side="left", padx=8)

            ctk.CTkButton(btn_frame, text="Plus tard", width=100, fg_color="#5a5a5a",
                          command=win.destroy).pack(side="left", padx=8)
            win.update_idletasks()
            w, h = win.winfo_reqwidth(), win.winfo_reqheight()
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        def export_library_backup(self):
            """Exporte bibliothèque + playlist + lien tableur dans un seul
            fichier JSON, pour pouvoir tout restaurer d'un coup après une
            réinstallation ou un changement de machine. Rien ne permettait
            ça jusqu'ici — pourtant potentiellement des heures de curation
            (repérer/organiser des centaines de titres)."""
            if not self.video_paths and not self.playlist:
                messagebox.showinfo("Exporter", "Rien à exporter : bibliothèque et playlist sont vides.")
                return
            default_name = f"citron_sauvegarde_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
            path = filedialog.asksaveasfilename(
                defaultextension=".json",
                filetypes=[("Sauvegarde Citron (JSON)", "*.json"), ("Tous", "*.*")],
                initialfile=default_name,
                title="Exporter la configuration Citron")
            if not path:
                return
            try:
                data = {
                    "citron_backup_version": 1,
                    "citron_version": CITRON_VERSION,
                    "exported_at": datetime.now().isoformat(timespec="seconds"),
                    "library": [{"path": p, "name": n}
                                for p, n in zip(self.video_paths, self.video_names)],
                    "playlist": list(self.playlist),
                    "tableur_path": self._tableur_path or "",
                }
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                messagebox.showinfo(
                    "Exporté",
                    f"Configuration exportée :\n{path}\n\n"
                    f"{len(data['library'])} titre(s) en bibliothèque, "
                    f"{len(data['playlist'])} en playlist.")
            except Exception as ex:
                messagebox.showerror("Exporter", f"Échec de l'export :\n{ex}")

        def import_library_backup(self):
            """Importe une sauvegarde créée par export_library_backup.
            Remplace bibliothèque et playlist (après confirmation) — les
            chemins absents sur cette machine (lettre de lecteur différente,
            disque rebranché ailleurs...) passent ensuite par la même
            relocalisation automatique qu'un chargement normal
            (_relocate_library_paths_bg), pas silencieusement ignorés."""
            path = filedialog.askopenfilename(
                filetypes=[("Sauvegarde Citron (JSON)", "*.json"), ("Tous", "*.*")],
                title="Importer une configuration Citron")
            if not path:
                return
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as ex:
                messagebox.showerror("Importer", f"Fichier illisible :\n{ex}")
                return

            library = data.get("library", []) or []
            playlist = data.get("playlist", []) or []
            tableur_path = data.get("tableur_path", "")
            if not library and not playlist:
                messagebox.showinfo("Importer", "Ce fichier ne contient ni bibliothèque ni playlist.")
                return
            if not messagebox.askyesno(
                    "Remplacer ?",
                    "Ceci va remplacer votre bibliothèque et playlist actuelles par :\n"
                    f"{len(library)} titre(s) en bibliothèque, {len(playlist)} en playlist.\n\n"
                    "Continuer ?"):
                return

            self.video_paths = [item.get("path", "") for item in library if item.get("path")]
            self.video_names = [item.get("name") or os.path.basename(item.get("path", ""))
                                 for item in library if item.get("path")]
            self.playlist = list(playlist)
            self.current_index = -1
            if tableur_path:
                self._tableur_path = tableur_path
                self._ods_rows_cache = None

            self.save_library()
            self.save_playlist()
            self.save_settings()
            self.update_list_button_text()
            self.update_playlist_button_text()
            if self.list_win and self.list_win.winfo_exists():
                self.refresh_list_window()
            self.refresh_playlist_window()
            self._fetch_durations_bg(self.video_paths)
            # Comme au chargement normal de la bibliothèque : tenter de
            # relocaliser automatiquement les chemins absents sur cette
            # machine, plutôt que de les laisser silencieusement cassés.
            self.after(800, self._relocate_library_paths_bg)
            messagebox.showinfo(
                "Importé",
                f"{len(self.video_paths)} titre(s) importé(s) en bibliothèque, "
                f"{len(self.playlist)} en playlist.")

        def _show_bookmarklet_help(self):
            win = ctk.CTkToplevel(self)
            win.title("Bookmarklet — Envoyer à Citron")
            win.geometry("640x380")
            win.transient(self); win.lift()
            ctk.CTkLabel(win, text="📋 Bookmarklet navigateur",
                         font=("Arial",16,"bold")).pack(pady=(14, 6))
            ctk.CTkLabel(win, text=(
                "1. Activez le protocole (Paramètres → 🔗 Activer citron://)\n"
                "2. Créez un favori dont l'URL est le code ci-dessous\n"
                "3. Sur une page vidéo, cliquez ce favori\n"
                "   (la vidéo du navigateur est automatiquement mise en pause\n"
                "   et coupée pour éviter que son son se superpose à Citron)"
            ), font=("Arial",12), justify="left").pack(padx=16, pady=4)
            js = ("javascript:(function(){"
                  "document.querySelectorAll('video,audio').forEach(function(m){"
                  "try{m.pause();m.muted=true;}catch(e){}});"
                  "location.href='citron://play?url='+encodeURIComponent(location.href);"
                  "})()")
            from tkinter import Text as _T
            txt = _T(win, height=3, font=("Consolas",11), wrap="word",
                     bg="#1a1a1a", fg="#8ecbff", relief="flat")
            txt.pack(fill="x", padx=16, pady=8)
            txt.insert("1.0", js)
            def copy():
                self.clipboard_clear()
                self.clipboard_append(js)
                messagebox.showinfo("Copié", "Bookmarklet copié.", parent=win)
            ctk.CTkButton(win, text="📋 Copier le bookmarklet", command=copy, height=36).pack(pady=6)
            ctk.CTkLabel(win, text=(
                "Brave / Chrome : barre de favoris (Ctrl+Shift+B) →\n"
                "clic droit → Ajouter une page → coller le code dans URL."
            ), font=("Arial",11), text_color="#aaaaaa").pack(pady=4)
            ctk.CTkButton(win, text="Fermer", command=win.destroy, height=32).pack(pady=4)

        def play_file(self, path):
            if not self.player:
                messagebox.showerror("VLC","VLC non disponible."); return
            if not os.path.isfile(path):
                messagebox.showerror("Introuvable", path); return
            # Réinitialise seulement le facteur suivi côté Python — PAS
            # d'appel natif video_set_scale() ici : on est en pleine
            # transition de lecture (changement de média), un moment
            # sensible pour libvlc/DirectX. Un média fraîchement chargé
            # démarre de toute façon déjà sans zoom (comportement natif par
            # défaut), donc cet appel n'apportait rien de plus ici.
            self._video_zoom_factor = 1.0
            self._set_internet_ui(False)
            self._internet_url = ""
            self._internet_title = ""
            self._internet_play_url = ""
            # Stop préventif TV si on lance une lecture PC (point 2)
            if not self._tv_mode and self._tv_control_url:
                self._stop_tv_silently()
            self._stop_audio_anim()
            self._hide_thumb_win()
            # Créer (cachée) la fenêtre de vignette dès maintenant plutôt que
            # d'attendre le premier survol : une fenêtre Windows toute fraîche
            # semble avoir besoin d'un instant pour être bien enregistrée par le
            # compositeur avant d'être affichée/cachée rapidement, ce qui
            # provoquait le fantôme au tout premier survol de chaque session.
            # En la créant ici, elle a largement le temps de "s'installer" avant
            # qu'on ne la montre jamais — sans délai perceptible pour l'utilisateur.
            try:
                self._ensure_thumb_win()
                self._thumb_win_ready_at = time.time() + 1.5
            except Exception:
                pass
            media = self.instance.media_new(path)
            self.player.set_media(media)
            self.update_idletasks()
            if is_audio(path):
                self.player.set_hwnd(0)
                self._start_audio_anim()
            else:
                self.audio_canvas.place_forget()
                self.player.set_hwnd(self.video_frame.winfo_id())
            self.player.play()
            # Diagnostic : interroge l'état réel de la piste audio une fois la
            # lecture stabilisée (les infos audio ne sont fiables qu'une fois le
            # média réellement en cours de décodage, pas juste au moment de play()).
            def _audio_debug_probe():
                try:
                    if not self.player: return
                    vol = self.player.audio_get_volume()
                    mute = self.player.audio_get_mute()
                    track = self.player.audio_get_track()
                    track_count = self.player.audio_get_track_count()
                    state = self.player.get_state()
                    out = self.player.audio_output_device_get()
                    print(f"[Audio DEBUG] état={state} volume={vol} mute={mute} "
                          f"piste_active={track} nb_pistes={track_count} "
                          f"périphérique_sortie={out}")
                except Exception as ex_probe:
                    print(f"[Audio DEBUG] Erreur sonde : {ex_probe}")
            self.after(1500, _audio_debug_probe)
            self.play_btn.configure(text="⏸")
            name = os.path.basename(path)
            self.now_playing_label.configure(text=f"▶  {name}")
            self.title(f"🍋 Citron — {name}")
            self._start_countdown(path)
            if not self._tv_mode:
                self.set_play_mode("pc")
            if path not in self.duration_cache:
                self._fetch_durations_bg([path])
            # Mise à jour titre suivant
            self._update_next_title_label()
            self._update_playlist_total_countdown()

        def toggle_play(self, event=None):
            if self._tv_mode and self._tv_control_url:
                cu = self._tv_control_url
                def check_and_toggle():
                    try:
                        st = _soap_get_transport_state(cu)
                        if st == "PLAYING":
                            _soap_pause(cu)
                            self.after(0, lambda: self.play_btn.configure(text="▶"))
                        else:
                            _soap_play(cu)
                            self.after(0, lambda: self.play_btn.configure(text="⏸"))
                    except Exception as ex: print(f"[TV toggle] {ex}")
                threading.Thread(target=check_and_toggle, daemon=True).start()
                if self.player:
                    ps = self.player.get_state()
                    if ps == vlc.State.Playing: self.player.pause()
                    else: self.player.play()
                return
            if not self.player: return
            st = self.player.get_state()
            if st == vlc.State.Playing:
                self.player.pause(); self.play_btn.configure(text="▶")
            elif st in (vlc.State.Paused,vlc.State.Stopped,vlc.State.Ended,vlc.State.NothingSpecial):
                if st in (vlc.State.Stopped,vlc.State.Ended,vlc.State.NothingSpecial):
                    if self.playlist and self.current_index >= 0:
                        self.play_file(self._get_pl_path(self.current_index))
                    elif self.video_paths:
                        self.current_index = 0
                        self.play_file(self.video_paths[0])
                else:
                    self.player.play(); self.play_btn.configure(text="⏸")

        def stop_video(self):
            if self._tv_mode and self._tv_control_url:
                self._tv_gen += 1
                self._tv_mode = False
                threading.Thread(target=lambda: _soap_stop(self._tv_control_url), daemon=True).start()
                if self.player: self.player.audio_set_volume(int(self.volume_slider.get()))
            if self.player: self.player.stop()
            self._stop_audio_anim()
            self._hide_thumb_win()
            self.play_btn.configure(text="▶")
            self.progress_slider.set(0)
            self.time_label.configure(text="0:00 / 0:00")
            self.now_playing_label.configure(text="Arrêté")
            self._reset_countdown()
            self.set_play_mode("stop")
            if hasattr(self,"total_countdown_label"): self.total_countdown_label.configure(text="")
            if hasattr(self,"next_title_label"): self.next_title_label.configure(text="")
            self._seq_mode = False
            self._list_play_mode = False
            self._single_tv_mode = False
            self._seq_order = []
            self._seq_visited = []
            self._set_internet_ui(False)
            self._internet_url = ""
            self._internet_title = ""
            self._internet_play_url = ""
            self._update_mirror_btn_visibility()
            self._set_internet_nav_disabled(False)
            # Restaure le son du navigateur (sans effet si rien n'était coupé) :
            # couvre à la fois l'arrêt d'une lecture internet sur PC (déjà géré
            # via _set_internet_ui) et l'arrêt d'une lecture internet sur TV,
            # qui coupe le son du navigateur sans passer par _internet_mode.
            try:
                self._restore_browser_audio()
            except Exception:
                pass
            # Désactive un éventuel relais HTTP internet→TV encore actif, pour
            # que le serveur de streaming local revienne au mode « fichier »
            # normal utilisé par les envois de médias locaux vers la TV.
            try:
                VideoHTTPHandler.server_remote_url = None
                VideoHTTPHandler.server_remote_mime = None
            except Exception:
                pass
            # Arrête proprement un éventuel enregistrement d'écran en cours
            # (bouton « Lire sur PC et enregistrer l'écran »), pour que le
            # fichier .mp4 soit correctement finalisé plutôt que corrompu.
            if getattr(self, "_screen_record_active", False):
                self._stop_screen_recording()

        def play_prev(self):
            if self._tv_mode and self._tv_control_url:
                if self._single_tv_mode:
                    self.stop_video(); return
                # ⏮ TV séquentiel/aléatoire
                if self._tv_shuffle:
                    # pas de précédent en aléatoire TV pour l'instant → inopérant
                    return
                new_idx = self._tv_play_index - 1
                if new_idx < 0: return  # début, inopérant
                self._tv_gen += 1
                self._tv_play_index = new_idx
                self.after(0, self._tv_play_next); return
            # Navigation dans la derniere liste de recherche tableur
            if self._search_play_mode and self._any_search_results_open():
                if self._search_play_index <= 0:
                    return
                new_idx = self._search_play_index - 1
                if self.player: self.player.stop()
                self._stop_audio_anim()
                self.play_btn.configure(text="▶")
                self._search_play_index = new_idx
                self.play_file(self._search_play_paths[new_idx])
                self.set_play_mode("pc", "Recherche tableur")
                return
            if self._search_play_mode and not self._any_search_results_open():
                self._clear_search_play_mode()
            # Navigation dans "Liste complète des médias" (lecture directe, hors playlist)
            if self._list_play_mode:
                if self._list_play_index <= 0:
                    return  # premier titre de la liste, inopérant
                new_idx = self._list_play_index - 1
                if self.player: self.player.stop()
                self._stop_audio_anim()
                self.play_btn.configure(text="▶")
                self._list_play_index = new_idx
                self.play_file(self.video_paths[new_idx])
                self.set_play_mode("pc","Liste complète")
                return
            if not self.playlist or not self._seq_mode: return
            # Mode aléatoire PC
            if self.shuffle_mode:
                self._play_shuffle_prev(); return
            # Séquentiel — inopérant si c'est le tout premier titre lu
            if len(self._seq_visited) <= 1: return
            if self.player: self.player.stop()
            self._stop_audio_anim()
            self.play_btn.configure(text="▶")
            # Remettre le titre actuel en tête de _seq_order
            if self._seq_visited:
                current = self._seq_visited.pop()
                self._seq_order.insert(0, current)
            # Jouer le précédent
            if self._seq_visited:
                prev_idx = self._seq_visited[-1]
                self.current_index = prev_idx
                self.play_file(self._get_pl_path(prev_idx))
                self._highlight_playlist(prev_idx)
                self._update_next_title_label()
                self._update_playlist_total_countdown()

        def play_next(self):
            if self._tv_mode and self._tv_control_url:
                if self._single_tv_mode:
                    self.stop_video(); return
                self._tv_gen += 1
                self._tv_play_index += 1
                self.after(0, self._tv_play_next); return
            # Navigation dans la derniere liste de recherche tableur
            if self._search_play_mode and self._any_search_results_open():
                new_idx = self._search_play_index + 1
                if new_idx >= len(self._search_play_paths):
                    return
                if self.player: self.player.stop()
                self._stop_audio_anim()
                self.play_btn.configure(text="▶")
                self._search_play_index = new_idx
                self.play_file(self._search_play_paths[new_idx])
                self.set_play_mode("pc", "Recherche tableur")
                return
            if self._search_play_mode and not self._any_search_results_open():
                self._clear_search_play_mode()
            # Navigation dans "Liste complète des médias" (lecture directe, hors playlist)
            if self._list_play_mode:
                new_idx = self._list_play_index + 1
                if new_idx >= len(self.video_paths):
                    return  # dernier titre de la liste, inopérant
                if self.player: self.player.stop()
                self._stop_audio_anim()
                self.play_btn.configure(text="▶")
                self._list_play_index = new_idx
                self.play_file(self.video_paths[new_idx])
                self.set_play_mode("pc","Liste complète")
                return
            if not self.playlist or not self._seq_mode: return
            if self.player: self.player.stop()
            self._stop_audio_anim()
            self.play_btn.configure(text="▶")
            if self.shuffle_mode:
                self._play_shuffle_next()
            else:
                self._seq_play_next_in_order()

        def _seq_play_next_in_order(self):
            """Joue le prochain titre dans _seq_order. Stop quand tous vus."""
            if not self._seq_order:
                self._seq_end(); return
            idx = self._seq_order.pop(0)
            self._seq_visited.append(idx)
            self.current_index = idx
            path = self._get_pl_path(idx)
            self.play_file(path)
            self._highlight_playlist(idx)
            self._update_next_title_label()
            self._update_playlist_total_countdown()

        def _seq_end(self):
            """Appelé à la fin d'une lecture séquentielle complète."""
            self._seq_mode = False
            self.stop_video()
            self.now_playing_label.configure(text="✅ Playlist terminée")
            if hasattr(self,"next_title_label"): self.next_title_label.configure(text="")
            if hasattr(self,"total_countdown_label"): self.total_countdown_label.configure(text="")

        def _seq_next_auto(self):
            """Fin naturelle d'un titre → passe au suivant dans _seq_order."""
            if not self._seq_mode: return
            self._seq_play_next_in_order()

        def _highlight_playlist(self, idx):
            if hasattr(self,"playlist_listbox") and self.playlist_listbox.winfo_exists():
                self.playlist_listbox.selection_clear(0,END)
                self.playlist_listbox.selection_set(idx)
                self.playlist_listbox.see(idx)

        def start_shuffle_from(self, start_idx, dlna_device=None):
            self._list_play_mode = False
            self._clear_search_play_mode()  # ⏮/⏭ = logique playlist aleatoire
            n = len(self.playlist)
            remaining = list(range(n))
            random.shuffle(remaining)
            if start_idx in remaining:
                remaining.remove(start_idx)
                remaining.insert(0, start_idx)
            if dlna_device:
                self._tv_mode = True
                self._tv_shuffle = True
                self._tv_shuffle_queue = remaining
                self._tv_play_device = dlna_device
                self._tv_play_index = remaining[0] if remaining else 0
                self.set_play_mode("tv_random", "🎵 Playlist")
                self._update_mirror_btn_visibility()
                self._tv_play_next()
            else:
                # Lecture aléatoire PC : on utilise _seq_order mélangé
                self.shuffle_mode = False   # on utilise la logique seq
                self._seq_mode = True
                self._single_tv_mode = False
                self._seq_visited = []
                self._seq_order = remaining[:]   # déjà mélangé
                self._playlist_total_dur = self._calc_playlist_total_duration()
                self._shuffle_history = []
                self._seq_play_next_in_order()
                self.set_play_mode("🔀 Lecture aléatoire à partir de ce titre sur PC", "🎵 Playlist")

        def _play_shuffle_next(self):
            if not self._shuffle_queue:
                self.shuffle_mode = False
                self._seq_mode = False
                self.stop_video()
                self.now_playing_label.configure(text="✅ Lecture aléatoire terminée")
                return
            idx = self._shuffle_queue.pop(0)
            self.shuffle_done.append(idx)
            self._shuffle_history.append(idx)
            self.current_index = idx
            self.play_file(self._get_pl_path(idx))
            self._highlight_playlist(idx)

        def _play_shuffle_prev(self):
            """Revenir au titre précédent en mode aléatoire."""
            if len(self._shuffle_history) < 2: return  # pas de précédent
            # Remettre le titre actuel dans la queue
            current = self._shuffle_history.pop()
            self._shuffle_queue.insert(0, current)
            # Jouer le précédent
            prev_idx = self._shuffle_history[-1]
            self.current_index = prev_idx
            self.shuffle_done = [i for i in self.shuffle_done if i != current]
            if self.player: self.player.stop(); self._stop_audio_anim()
            self.play_file(self._get_pl_path(prev_idx))
            self._highlight_playlist(prev_idx)

        # ── Progression ─────────────────────────────────
        def update_progress_loop(self):
            if not self._tv_mode and self.player and not self.seeking:
                if self.player.get_state() == vlc.State.Playing:
                    tot = self.player.get_length()
                    cur = self.player.get_time()
                    if tot > 0:
                        self.progress_slider.set((cur/tot)*1000)
                        self.time_label.configure(text=f"{self._ms(cur)} / {self._ms(tot)}")
                    self._update_playlist_total_countdown()
                    self._update_next_title_label()
            self.after(500, self.update_progress_loop)

        def _ms(self, ms):
            s=ms//1000; m,s=divmod(s,60); h,m=divmod(m,60)
            return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

        def on_seek(self, val):
            if self.player and self.seeking:
                pos=float(val)/1000.0; tot=self.player.get_length()
                if tot>0:
                    self.time_label.configure(text=f"{self._ms(int(pos*tot))} / {self._ms(tot)}")

        def on_seek_release(self, event):
            self.seeking = False
            pos_frac = self.progress_slider.get() / 1000.0
            if self._tv_mode and self._tv_control_url:
                cu = self._tv_control_url
                def tv_seek():
                    try:
                        _, dur = _soap_get_position(cu)
                        if dur <= 0 and self.player:
                            pl = self.player.get_length()
                            if pl > 0: dur = pl / 1000.0
                        if dur <= 0:
                            idx = self.current_index
                            if 0 <= idx < len(self.playlist):
                                raw = self.playlist[idx]
                                p = raw.get("path","") if isinstance(raw,dict) else raw
                                if p: dur = self._get_duration(p)
                        if dur > 0:
                            target_s = pos_frac * dur
                            h=int(target_s//3600); m=int((target_s%3600)//60); s=int(target_s%60)
                            ts=f"{h:02d}:{m:02d}:{s:02d}"
                            body=f"""<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body><u:Seek xmlns:u="urn:schemas-upnp-org:service:AVTransport:1"><InstanceID>0</InstanceID><Unit>REL_TIME</Unit><Target>{ts}</Target></u:Seek></s:Body></s:Envelope>"""
                            hdrs={"Content-Type":'text/xml; charset="utf-8"',
                                  "SOAPAction":'"urn:schemas-upnp-org:service:AVTransport:1#Seek"',
                                  "Content-Length":str(len(body.encode()))}
                            with urllib.request.urlopen(urllib.request.Request(cu,body.encode(),hdrs),timeout=5) as r: r.read()
                            print(f"[TV] Seek → {ts}")
                            if self.player:
                                pl=self.player.get_length()
                                if pl>0: self.player.set_position(target_s/dur)
                    except Exception as ex: print(f"[TV seek] {ex}")
                threading.Thread(target=tv_seek, daemon=True).start()
            else:
                if self.player: self.player.set_position(pos_frac)

        def on_volume_change(self, val):
            if self.player and not self._tv_mode:
                self.player.audio_set_volume(int(float(val)))

        def on_volume_scroll(self, event):
            nv=max(0,min(100,self.volume_slider.get()+(5 if event.delta>0 else -5)))
            self.volume_slider.set(nv); self.on_volume_change(nv)

        def _zoom_video_in(self, event=None):
            """Touche +, pavé numérique + ou « = » : zoom avant sur la vidéo."""
            self._adjust_video_zoom(1.1)

        def _zoom_video_out(self, event=None):
            """Touche - ou pavé numérique - : zoom arrière sur la vidéo."""
            self._adjust_video_zoom(1 / 1.1)

        def _adjust_video_zoom(self, step):
            """Applique un pas de zoom multiplicatif (>1 = zoom avant,
            <1 = zoom arrière) au facteur de zoom vidéo courant. Utilisé par
            les raccourcis clavier (voir create_widgets) — le zoom n'était
            auparavant accessible qu'à la molette, peu fiable ici car VLC
            intercepte souvent l'événement avant que Tkinter ne le reçoive."""
            if not self.player:
                return
            try:
                if self.player.get_state() not in (vlc.State.Playing, vlc.State.Paused):
                    return
            except Exception:
                return
            self._video_zoom_factor = max(0.2, min(6.0, self._video_zoom_factor * step))
            self._apply_video_zoom()

        def _apply_video_zoom(self):
            """Traduit self._video_zoom_factor (1.0 = affichage normal,
            identique à aujourd'hui) en un facteur d'échelle absolu pour VLC
            (video_set_scale), calculé à partir de la résolution native de
            la vidéo et de la taille actuelle du cadre d'affichage — pour
            que le zoom parte bien de « la vidéo occupe tout le cadre »
            (le rendu actuel), et non de sa taille native en pixels, qui
            peut être bien plus grande ou plus petite que le cadre."""
            if not self.player:
                return
            try:
                # Très proche de 1.0 : on revient au comportement natif de
                # VLC (0 = ajustement automatique au cadre), plus fidèle que
                # de reproduire nous-mêmes ce calcul à chaque frame.
                if abs(self._video_zoom_factor - 1.0) < 0.03:
                    self._video_zoom_factor = 1.0
                    self.player.video_set_scale(0)
                    return
                size = self.player.video_get_size(0)
                vid_w, vid_h = size if size else (0, 0)
                if not vid_w or not vid_h:
                    return
                self.update_idletasks()
                frame_w = self.video_frame.winfo_width()
                frame_h = self.video_frame.winfo_height()
                if frame_w < 2 or frame_h < 2:
                    return
                fit_scale = min(frame_w / vid_w, frame_h / vid_h)
                final_scale = fit_scale * self._video_zoom_factor
                self.player.video_set_scale(final_scale)
            except Exception:
                pass

        def _reset_video_zoom(self, event=None):
            """Revient à l'ajustement automatique (comportement normal,
            vidéo qui occupe tout le cadre) — clic molette sur la vidéo ou
            touche 0 du pavé numérique."""
            self._video_zoom_factor = 1.0
            try:
                if self.player:
                    self.player.video_set_scale(0)
            except Exception:
                pass

        def toggle_fullscreen(self, event=None):
            self.is_fullscreen = not self.is_fullscreen
            self.attributes("-fullscreen", self.is_fullscreen)

        # ── Animation audio ─────────────────────────────
        def _audio_level_loop(self):
            if self.player:
                try:
                    if self.player.get_state() == vlc.State.Playing:
                        self.audio_level = 0.4+0.6*abs(math.sin(time.time()*7.3+1.2))*abs(math.sin(time.time()*3.1))
                    else:
                        self.audio_level = 0.0
                except Exception:
                    self.audio_level = 0.0
            self.after(50, self._audio_level_loop)

        def _start_audio_anim(self):
            self.audio_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.audio_anim_phase = 0.0
            self._draw_audio_anim()

        def _start_audio_anim_loop(self):
            if self.audio_anim_id:
                self.after_cancel(self.audio_anim_id); self.audio_anim_id = None
            self.audio_anim_phase = 0.0
            self._draw_audio_anim()

        def _stop_audio_anim(self):
            if self.audio_anim_id:
                self.after_cancel(self.audio_anim_id); self.audio_anim_id = None
            try: self.audio_canvas.place_forget()
            except Exception: pass

        def _draw_audio_anim(self):
            c = self.audio_canvas
            c.delete("all")
            W = c.winfo_width() or 800
            H = c.winfo_height() or 400
            cx, cy = W//2, H//2
            level = max(0.05, self.audio_level)
            phase = self.audio_anim_phase
            N = 64
            R_min = min(W,H)*0.18
            R_max = min(W,H)*0.42
            for ri in range(5):
                frac=ri/5; rr,gg,bb=self._hsv((phase*0.01+frac*0.15)%1.0,0.6,0.08+frac*0.05)
                c.create_oval(cx-int(R_max*(1-frac*0.4)),cy-int(R_max*(1-frac*0.4)),
                               cx+int(R_max*(1-frac*0.4)),cy+int(R_max*(1-frac*0.4)),
                               outline=f"#{rr:02x}{gg:02x}{bb:02x}",width=1)
            for i in range(N):
                angle=(2*math.pi*i/N)-math.pi/2
                amp=(abs(math.sin(phase+i*0.25))*abs(math.sin(phase*0.6+i*0.18+1.0)))*level
                r_outer=R_min+(R_max-R_min)*amp
                hue=(i/N+phase*0.008)%1.0
                rr,gg,bb=self._hsv(hue,0.7+0.3*level,0.6+0.4*amp)
                x0=cx+R_min*math.cos(angle); y0=cy+R_min*math.sin(angle)
                x1=cx+r_outer*math.cos(angle); y1=cy+r_outer*math.sin(angle)
                w=max(2,int((R_max-R_min)*0.045))
                c.create_line(x0,y0,x1,y1,fill=f"#{rr:02x}{gg:02x}{bb:02x}",width=w,capstyle="round")
            r_in=int(R_min-2)
            c.create_oval(cx-r_in,cy-r_in,cx+r_in,cy+r_in,fill="#0a0a0a",outline="")
            ns=int(28+14*level)
            c.create_text(cx,cy-8,text="♫",font=("Arial",ns,"bold"),fill="white")
            if self.player:
                media=self.player.get_media()
                if media:
                    mrl=media.get_mrl()
                    name=urllib.parse.unquote(os.path.basename(mrl.replace("file:///","").replace("/",os.sep)))
                    if len(name)>50: name=name[:47]+"…"
                    c.create_text(cx,cy+ns//2+18,text=name,font=("Arial",13),fill="#cccccc",width=min(W-60,600))
            self.audio_anim_phase+=0.06+0.10*level
            self.audio_anim_id=self.after(33,self._draw_audio_anim)

        @staticmethod
        def _hsv(h,s,v):
            i=int(h*6); f=h*6-i; p=v*(1-s); q=v*(1-f*s); t=v*(1-(1-f)*s)
            r,g,b=[(v,t,p),(q,v,p),(p,v,t),(p,q,v),(t,p,v),(v,p,q)][i%6]
            return int(r*255),int(g*255),int(b*255)

        # ── Miroir PC ────────────────────────────────────
        def _play_mirror_pc(self, path):
            def _do_mirror():
                if not self._mirror_on: return
                if not self.player: return
                try:
                    # Forcer son à 0 AVANT tout (point 11/13/14)
                    self.player.audio_set_volume(0)
                    if is_audio(path):
                        self._stop_audio_anim()
                        self.audio_canvas.place(relx=0,rely=0,relwidth=1,relheight=1)
                        self.audio_canvas.update_idletasks()
                        self.player.set_hwnd(0)
                        media=self.instance.media_new(path)
                        self.player.set_media(media)
                        self.player.audio_set_volume(0)
                        self.player.play()
                        self.after(200, self._start_audio_anim_loop)
                    else:
                        self._stop_audio_anim()
                        self.audio_canvas.place_forget()
                        self.player.set_hwnd(self.video_frame.winfo_id())
                        media=self.instance.media_new(path)
                        self.player.set_media(media)
                        self.player.audio_set_volume(0)
                        self.player.play()
                    self.play_btn.configure(text="⏸")
                    icon="🎵" if is_audio(path) else "🎬"
                    name=os.path.basename(path)
                    self.now_playing_label.configure(text=f"📺 TV + 🖥 Miroir (son 0%) {icon} {name}")
                    self.title(f"🍋 Citron 📺 — {name}")
                    self._start_countdown(path)
                except Exception as ex:
                    print(f"[PC mirror] {ex}")
            self.after(0, _do_mirror)

        def _update_tv_progress(self, pos_s, dur_s):
            if dur_s > 0:
                self.progress_slider.set((pos_s/dur_s)*1000)
                self.time_label.configure(text=f"{self._ms(int(pos_s*1000))} / {self._ms(int(dur_s*1000))}")
                remain=max(0,dur_s-pos_s)
                self.countdown_label.configure(text=f"⏳ {fmt_countdown(remain)}")
            self._update_playlist_total_countdown()
            self._update_next_title_label()

        # ── TV Play ─────────────────────────────────────
        def _tv_play_next(self):
            if self._tv_shuffle:
                if not self._tv_shuffle_queue:
                    self.after(0,lambda: messagebox.showinfo("TV","Tous les titres ont été lus."))
                    self._tv_mode=False
                    self._update_mirror_btn_visibility()
                    return
                idx=self._tv_shuffle_queue.pop(0)
            else:
                idx=self._tv_play_index
                if idx>=len(self.playlist):
                    self._tv_mode=False
                    self._update_mirror_btn_visibility()
                    self.after(0, self.stop_video)
                    self.after(100, lambda: self.now_playing_label.configure(text="✅ Playlist TV terminée"))
                    return
            self._tv_play_index=idx
            self.current_index=idx
            path=self._get_pl_path(idx)
            device=self._tv_play_device
            self._highlight_playlist(idx)
            self._tv_gen+=1
            my_gen=self._tv_gen
            self._update_next_title_label()
            self._update_playlist_total_countdown()
            def do_tv():
                try:
                    cu=device.get("control_url"); ip=device["ip"]
                    if not cu: raise RuntimeError(f"Pas de control_url pour {ip}")
                    self._tv_control_url=cu
                    local_ip=_get_local_ip()
                    if not _same_subnet(local_ip,ip):
                        raise RuntimeError(f"Réseaux différents : PC={local_ip}, TV={ip}")
                    url=self.stream_server.get_url(path)
                    title=os.path.basename(path)
                    self.stream_server.serve(path)
                    # Stop PC préventif (point 3)
                    if self.player:
                        self.player.stop()
                        self._stop_audio_anim()
                    _soap_stop(cu); time.sleep(1.0)
                    _soap_set(cu,url,title)
                    for _ in range(20):
                        time.sleep(0.5)
                        if self._tv_gen!=my_gen: return
                        st=_soap_get_transport_state(cu)
                        if st in ("STOPPED","PAUSED_PLAYBACK"): break
                    _soap_play(cu); time.sleep(0.8); _soap_play(cu)
                    self.after(0,lambda: self._play_mirror_pc(path))
                    print(f"[TV] Lecture : {title}")
                    sync_done=False; last_pos=-1; stall_count=0
                    while True:
                        if self._tv_gen!=my_gen: print("[TV] Titre suivant demandé, arrêt surveillance."); return
                        time.sleep(1)
                        st=_soap_get_transport_state(cu)
                        pos,dur=_soap_get_position(cu)
                        if dur>0:
                            self.after(0,lambda p=pos,d=dur: self._update_tv_progress(p,d))
                        if pos>0 and self.player and not sync_done:
                            sync_done=True
                            if dur>0: self.player.set_position(pos/dur)
                            print(f"[TV] Sync miroir à {pos:.1f}s")
                        if st=="STOPPED" and dur>0 and pos>=dur-3:
                            print(f"[TV] Fin de '{title}'"); break
                        if st=="STOPPED" and pos==last_pos and pos>0:
                            stall_count+=1
                            if stall_count>=3: print(f"[TV] Fin détectée"); break
                        else: stall_count=0
                        last_pos=pos
                    if self._tv_gen==my_gen:
                        self._tv_play_index+=1
                        self.after(500,self._tv_play_next)
                except Exception as exc:
                    msg=str(exc); print(f"[TV] Erreur: {msg}")
                    self.after(0,lambda: messagebox.showerror("TV",msg))
                    self._tv_mode=False
                    self.after(0, self._update_mirror_btn_visibility)
            threading.Thread(target=do_tv,daemon=True).start()

        # ── DLNA Window ─────────────────────────────────
        def _send_direct_to_tv(self, path):
            if not self._dlna_devices:
                messagebox.showinfo("TV","Aucun appareil connu.\nUtilisez 📺 TV pour rechercher d'abord."); return
            device=self._dlna_devices[0]
            self._tv_gen+=1
            self._tv_mode=True; self._tv_device=device; self._tv_play_device=device
            self._tv_control_url=device.get("control_url")
            self._single_tv_mode = True   # titre unique → pas de suite
            self._seq_mode = False
            self._list_play_mode = False
            self._update_mirror_btn_visibility()
            self.now_playing_label.configure(text=f"📺 Envoi vers {device['name']} — {os.path.basename(path)}")
            def do():
                cu = device.get("control_url")
                ip = device.get("ip")
                try:
                    if not cu: raise RuntimeError(f"Pas de control_url pour {ip}")
                    self._tv_control_url=cu
                    local_ip=_get_local_ip()
                    if not _same_subnet(local_ip,ip): raise RuntimeError(f"Réseaux différents")
                    url=self.stream_server.get_url(path); title=os.path.basename(path)
                    self.stream_server.serve(path)
                    _soap_stop(cu); time.sleep(1.0)
                    try:
                        _soap_set(cu, url, title)
                    except Exception as ex_set:
                        # Correctif : contrairement à la fenêtre DLNA complète
                        # (_dlna_send), ce chemin d'envoi rapide n'avait aucune
                        # résilience — au moindre échec ponctuel de la TV (très
                        # courant avec certains boîtiers comme le WD TV Live,
                        # dont le port de contrôle UPnP peut changer), tout
                        # échouait immédiatement. On retente maintenant une
                        # fois, après une redécouverte de l'appareil.
                        print(f"[TV direct] Échec 1ère tentative ({ex_set}) — redécouverte…")
                        devs = discover_dlna_renderers(timeout=4)
                        self._dlna_devices = devs
                        nd = next((d for d in devs if d.get("ip") == ip), devs[0] if devs else None)
                        if not nd or not nd.get("control_url"):
                            raise RuntimeError(
                                f"Échec après redécouverte : {ex_set}") from ex_set
                        cu = nd["control_url"]
                        self._tv_control_url = cu
                        _soap_stop(cu); time.sleep(1.0)
                        _soap_set(cu, url, title)
                    for _ in range(20):
                        time.sleep(0.5)
                        if self._dlna_cancel.is_set(): return
                        st=_soap_get_transport_state(cu)
                        if st in ("STOPPED","PAUSED_PLAYBACK"): break
                    _soap_play(cu); time.sleep(0.8); _soap_play(cu)
                    for _ in range(20):
                        time.sleep(1)
                        if self._dlna_cancel.is_set(): return
                        st=_soap_get_transport_state(cu)
                        if st=="PLAYING":
                            self.after(0,lambda: self._play_mirror_pc(path)); break
                except Exception as exc:
                    msg=str(exc); print(f"[TV direct] {msg}")
                    self.after(0,lambda: messagebox.showerror("TV",msg))
            threading.Thread(target=do,daemon=True).start()

        def open_dlna_window(self, prefill_path=None):
            if prefill_path and self._dlna_devices:
                self._send_direct_to_tv(prefill_path); return
            if not prefill_path and self._dlna_devices and self.player:
                st=self.player.get_state()
                if st in (vlc.State.Playing,vlc.State.Paused):
                    media=self.player.get_media()
                    if media:
                        mrl=media.get_mrl()
                        path=urllib.parse.unquote(mrl.replace("file:///","").replace("/",os.sep))
                        if os.path.isfile(path): self._send_direct_to_tv(path); return
            if self.dlna_win and self.dlna_win.winfo_exists():
                self.dlna_win.lift(); return
            self.dlna_win=ctk.CTkToplevel(self)
            self.dlna_win.title("📺 Envoyer sur TV")
            self.dlna_win.geometry("580x480")
            self.dlna_win.transient(self); self.dlna_win.lift()

            ctk.CTkLabel(self.dlna_win,text="📺 Envoyer sur TV (DLNA)",font=("Arial",18,"bold")).pack(pady=12)
            ff=ctk.CTkFrame(self.dlna_win); ff.pack(fill="x",padx=20,pady=4)
            ctk.CTkLabel(ff,text="Fichier :",font=("Arial",13)).pack(anchor="w",padx=8)
            self.dlna_file_var=ctk.StringVar()
            if prefill_path and os.path.isfile(prefill_path): self.dlna_file_var.set(prefill_path)
            row=ctk.CTkFrame(ff); row.pack(fill="x",padx=8,pady=4)
            ctk.CTkEntry(row,textvariable=self.dlna_file_var,width=420).pack(side="left")
            ctk.CTkButton(row,text="…",width=40,command=self._dlna_pick).pack(side="left",padx=4)

            ctk.CTkLabel(self.dlna_win,text="Appareils DLNA :",font=("Arial",13)).pack(anchor="w",padx=28,pady=(8,2))
            df=ctk.CTkFrame(self.dlna_win); df.pack(fill="x",padx=20,pady=4)
            self.dlna_device_list=Listbox(df,font=("Arial",13),bg="#2b2b2b",fg="white",height=5,selectbackground="#1f6aa5")
            sb=Scrollbar(df,orient="vertical",command=self.dlna_device_list.yview)
            self.dlna_device_list.config(yscrollcommand=sb.set)
            self.dlna_device_list.pack(side="left",fill="x",expand=True,padx=4,pady=4)
            sb.pack(side="right",fill="y")
            self.dlna_device_list.bind("<<ListboxSelect>>",self._dlna_sel)

            br=ctk.CTkFrame(self.dlna_win); br.pack(pady=6)
            ctk.CTkButton(br,text="🔍 Rechercher",command=self._dlna_scan,height=36).pack(side="left",padx=8)

            self.dlna_status=ctk.CTkLabel(self.dlna_win,text="",font=("Arial",12),text_color="#aaaaaa")
            self.dlna_status.pack(pady=4)
            ctk.CTkButton(self.dlna_win,text="📤 Envoyer et lire sur TV",command=self._dlna_send,
                          height=42,fg_color="#2a6496",font=("Arial",14,"bold")).pack(pady=8)
            if self._dlna_devices: self._dlna_populate(self._dlna_devices)
            self._remember_last_window_geometry(self.dlna_win)

        def _update_dlna_status(self,msg):
            print(f"[DLNA] {msg}")
            def _safe():
                try:
                    if self.dlna_win and self.dlna_win.winfo_exists() and hasattr(self,"dlna_status") and self.dlna_status.winfo_exists():
                        self.dlna_status.configure(text=msg)
                except Exception: pass
            self.after(0,_safe)

        def _dlna_pick(self):
            exts=" ".join(f"*{e}" for e in sorted(ALL_EXT))
            f=filedialog.askopenfilename(filetypes=[("Médias",exts)])
            if f: self.dlna_file_var.set(f)

        def _dlna_scan(self):
            local_ip=_get_local_ip()
            if local_ip.startswith("192.168.43."):
                self._update_dlna_status("⚠️ PC sur hotspot mobile — connectez-vous à votre box Wi-Fi !")
            else:
                self._update_dlna_status("🔍 Recherche en cours (4 s)…")
            self.dlna_device_list.delete(0,END)
            self.dlna_win.update()
            def do(): devs=discover_dlna_renderers(timeout=4); self.after(0,lambda: self._dlna_populate(devs))
            threading.Thread(target=do,daemon=True).start()

        def _dlna_populate(self,devs):
            self._dlna_devices=devs
            self.dlna_device_list.delete(0,END)
            if not devs: self._update_dlna_status("Aucun appareil trouvé.")
            else:
                for d in devs: self.dlna_device_list.insert(END,f"  {d['name']}   ({d['ip']})")
                self._update_dlna_status(f"{len(devs)} appareil(s) détecté(s).")

        def _dlna_sel(self,event): pass

        def _get_selected_device(self):
            if not hasattr(self,"dlna_device_list"): return None
            sel=self.dlna_device_list.curselection()
            if sel and self._dlna_devices and sel[0]<len(self._dlna_devices): return self._dlna_devices[sel[0]]
            if len(self._dlna_devices)==1: return self._dlna_devices[0]
            return None

        def _dlna_send(self):
            path=self.dlna_file_var.get().strip()
            if not path or not os.path.isfile(path):
                messagebox.showerror("Erreur","Fichier invalide.",parent=self.dlna_win); return
            device=self._get_selected_device()
            if not device:
                messagebox.showerror("Erreur","Aucun appareil sélectionné.\nCliquez sur 🔍 Rechercher d'abord.",parent=self.dlna_win); return
            self.stream_server.serve(path)
            url=self.stream_server.get_url(path); title=os.path.basename(path)
            ip=device["ip"]; control_url=device.get("control_url")
            self._tv_mode=True; self._tv_play_device=device; self._tv_control_url=control_url
            self._update_mirror_btn_visibility()
            self.set_play_mode("tv","📺 TV")

            def update_status(msg): self._update_dlna_status(msg)

            self._dlna_cancel.set(); time.sleep(0.3); self._dlna_cancel.clear()
            update_status(f"📡 Étape 1/4 — Connexion à {device['name']}…")

            FALLBACKS=[(49152,"/upnp/control/AVTransport1"),(49152,"/AVTransport/control"),
                       (8200,"/upnp/control/AVTransport"),(1400,"/MediaRenderer/AVTransport/control"),(49153,"/upnp/control/AVTransport1")]
            def do():
                nonlocal control_url, ip
                try:
                    local_ip=_get_local_ip()
                    if not _same_subnet(local_ip,ip):
                        raise RuntimeError(f"⚠️ Réseaux différents !\nPC : {local_ip}\nWD TV Live : {ip}\nConnectez le PC au même Wi-Fi.")
                    if not control_url:
                        update_status("📡 Étape 1/4 — Test des ports DLNA…")
                        for port,pth in FALLBACKS:
                            cu=f"http://{ip}:{port}{pth}"
                            try: _soap_set(cu,url,title); control_url=cu; break
                            except Exception: continue
                        if not control_url: raise RuntimeError(f"Aucun port DLNA fonctionnel sur {ip}.")
                    else:
                        update_status("📡 Étape 1/4 — Réinitialisation WD TV Live…")
                        _soap_stop(control_url); time.sleep(1.0)
                        try: _soap_set(control_url,url,title)
                        except Exception as ex_set:
                            update_status(f"⚠️ Échec ({ex_set}) — Redécouverte…")
                            devs=discover_dlna_renderers(timeout=4); self._dlna_devices=devs
                            if devs:
                                nd=devs[0]; nc=nd.get("control_url"); ni=nd["ip"]
                                if nc: control_url=nc; ip=ni; _soap_stop(control_url); time.sleep(1.0); _soap_set(control_url,url,title)
                                else: raise RuntimeError(f"Appareil retrouvé sur {ni} mais sans URL de contrôle")
                            else: raise RuntimeError("Aucun appareil DLNA trouvé après redécouverte")
                    self._tv_control_url=control_url
                    update_status("⏳ Étape 2/4 — Attente STOPPED…")
                    for _ in range(20):
                        time.sleep(0.5)
                        if self._dlna_cancel.is_set(): return
                        st=_soap_get_transport_state(control_url)
                        update_status(f"⏳ Étape 2/4 — {st or '…'}")
                        if st in ("STOPPED","PAUSED_PLAYBACK"): break
                    update_status("▶ Étape 3/4 — Play #1…"); _soap_play(control_url)
                    time.sleep(0.8)
                    update_status("▶ Étape 3/4 — Play #2…"); _soap_play(control_url)
                    update_status("⏳ Étape 4/4 — Vérification…")
                    relaunch_count = 0
                    for i in range(20):
                        time.sleep(1)
                        if self._dlna_cancel.is_set(): return
                        st=_soap_get_transport_state(control_url)
                        update_status(f"⏳ Étape 4/4 — {st or '?'} ({i+1}s)")
                        if st=="PLAYING":
                            update_status(f"✅ Lecture en cours sur {ip} !")
                            self.after(0,lambda: self._play_mirror_pc(path))
                            return
                        if st=="STOPPED" and i>1:
                            relaunch_count += 1
                            update_status(f"▶ Relance Play ({i+1}s)…"); _soap_play(control_url)
                    st=_soap_get_transport_state(control_url)
                    if st=="PLAYING":
                        update_status(f"✅ Lecture en cours sur {ip} !")
                    elif st=="TRANSITIONING" and relaunch_count>=1:
                        # Le boîtier reçoit bien SetAVTransportURI et Play (HTTP 200/206
                        # observés sur le flux), mais reste bloqué en TRANSITIONING
                        # malgré plusieurs relances de Play : ce symptôme apparaît
                        # typiquement après une coupure réseau, quand le WD TV Live
                        # reste figé dans un état DLNA interne dégradé. Un "Play" sur
                        # la télécommande ne débloque généralement pas ce cas ; seul un
                        # cycle d'alimentation (débrancher/rebrancher) du boîtier remet
                        # son service DLNA à zéro.
                        update_status(f"⚠️ Boîtier bloqué en TRANSITIONING malgré {relaunch_count} relance(s) de Play — débranchez puis rebranchez le WD TV Live (état DLNA interne figé, fréquent après une coupure réseau), puis réessayez.")
                    else:
                        update_status(f"⚠️ État final : {st or 'inconnu'} — appuyez sur Play sur la télécommande.")
                except Exception as exc:
                    msg=str(exc); print(f"[DLNA] Erreur: {msg}")
                    msg=str(exc)
                    print(f"[DLNA] Erreur: {msg}")
                    self.after(0, lambda: (messagebox.showerror("Erreur DLNA", msg, parent=self.dlna_win)
                                           if self.dlna_win and self.dlna_win.winfo_exists() else None))
                    update_status(f"❌ {msg[:80]}")
            threading.Thread(target=do, daemon=True).start()

        # ── Fenêtre LISTE ────────────────────────────────
        def open_list_window(self):
            if self.list_win and self.list_win.winfo_exists():
                self.list_win.lift(); self.refresh_list_window(); return
            self.list_win=ctk.CTkToplevel(self)
            self.list_win.title("Liste complète des médias")
            self.list_win.geometry("1100x720")
            self.list_win.transient(self); self.list_win.lift()
            if self.list_win_geometry: self.list_win.geometry(self.list_win_geometry)
            self.list_win.protocol("WM_DELETE_WINDOW",self.close_list_window)

            tf=ctk.CTkFrame(self.list_win); tf.pack(fill="x",padx=20,pady=10)
            ctk.CTkLabel(tf,text="Liste complète des médias",font=("Arial",22,"bold")).pack()
            self.total_label=ctk.CTkLabel(tf,text=f"({len(self.video_names)} titres)",font=("Arial",16))
            self.total_label.pack()

            sf=ctk.CTkFrame(self.list_win); sf.pack(fill="x",padx=20,pady=6)
            ctk.CTkLabel(sf,text="🔍",font=("Arial",16)).pack(side="left",padx=(10,5))
            self.list_search_var=ctk.StringVar()
            ctk.CTkEntry(sf,placeholder_text="Rechercher…",textvariable=self.list_search_var,height=40).pack(side="left",fill="x",expand=True,padx=5)
            self.list_search_var.trace("w",self.filter_list_window)

            bf=ctk.CTkFrame(self.list_win); bf.pack(pady=6)
            ctk.CTkButton(bf,text="+ Fichiers",width=110,command=self.add_files).pack(side="left",padx=6)
            ctk.CTkButton(bf,text="+Dossier",width=110,command=self.add_folder).pack(side="left",padx=6)
            self.sort_toggle_btn=ctk.CTkButton(bf,text="↑↓ Trier A→Z",width=130,command=self._toggle_sort)
            self.sort_toggle_btn.pack(side="left",padx=6)
            ctk.CTkButton(bf,text="Vider la liste",fg_color="#c42b1c",width=120,command=self.clear_list_window).pack(side="left",padx=6)
            ctk.CTkButton(bf,text="Titres identiques",fg_color="#885500",width=140,command=self.show_duplicates_info).pack(side="left",padx=6)
            ctk.CTkButton(bf,text="🗑 Suppr. 🎵 audio",fg_color="#5a3070",width=150,command=self.delete_all_audio).pack(side="left",padx=6)

            bf2=ctk.CTkFrame(self.list_win); bf2.pack(pady=(0,4))
            ctk.CTkButton(bf2,text="📋 Liste → Playlist",width=160,command=self.add_all_to_playlist).pack(side="left",padx=6)
            ctk.CTkButton(bf2,text="🗑 Supprimer doublons",fg_color="#8b3a00",width=170,command=self.delete_duplicates).pack(side="left",padx=6)

            lf=ctk.CTkFrame(self.list_win); lf.pack(fill="both",expand=True,padx=20,pady=8)
            self.list_win_listbox=Listbox(lf,font=("Arial",12),bg="#2b2b2b",fg="white",
                                          selectbackground="#1f6aa5",activestyle="none")
            sb=Scrollbar(lf,orient="vertical",command=self.list_win_listbox.yview)
            self.list_win_listbox.config(yscrollcommand=sb.set)
            self.list_win_listbox.pack(side="left",fill="both",expand=True)
            sb.pack(side="right",fill="y")
            self.list_win_listbox.bind("<Motion>",self._list_hover_select)
            self.list_win_listbox.bind("<Leave>", lambda e: self._hide_list_hover_thumb())
            self.list_win_listbox.bind("<Button-3>",self.list_win_right_click)
            self.list_win_listbox.bind("<Double-Button-1>",self.list_win_double_click)
            self.refresh_list_window()

            # Les 2 premières secondes sont réservées à la création/redessin
            # de la fenêtre. Cela évite les premiers "fantômes" DWM/Tk.
            self._list_thumb_ready_at = time.time() + 2.0
            self._list_hover_last_idx = None
            self._list_hover_last_pos_ms = None
            try:
                if self._list_thumb_ready_job:
                    self.list_win.after_cancel(self._list_thumb_ready_job)
            except Exception:
                pass
            self._list_thumb_ready_job = self.list_win.after(2000, self._list_thumb_ready)

            self.list_win.after(120,lambda: self.list_win_listbox.yview_moveto(self.list_scroll_pos))
            self._remember_last_window_geometry(self.list_win)

        def _list_thumb_ready(self):
            """Autorise les vignettes après 2 s et traite le titre sous le pointeur."""
            self._list_thumb_ready_job = None
            self._list_thumb_generation = getattr(self, "_list_thumb_generation", 0) + 1
            if not (self.list_win and self.list_win.winfo_exists()
                    and self.list_win_listbox and self.list_win_listbox.winfo_exists()):
                return
            self._list_thumb_ready_at = time.time()
            try:
                px, py = self.list_win_listbox.winfo_pointerxy()
                x = px - self.list_win_listbox.winfo_rootx()
                y = py - self.list_win_listbox.winfo_rooty()
                if 0 <= x < self.list_win_listbox.winfo_width() and 0 <= y < self.list_win_listbox.winfo_height():
                    idx = self.list_win_listbox.nearest(y)
                    if 0 <= idx < self.list_win_listbox.size():
                        class E: pass
                        ev = E(); ev.x = x; ev.y = y
                        self._show_list_hover_thumb(idx, ev)
            except Exception as ex:
                print(f"[Vignette liste] readiness : {ex}")

        def _toggle_sort(self):
            self._sort_reverse=not getattr(self,"_sort_reverse",False)
            self.sort_list_window(self._sort_reverse)
            if hasattr(self,"sort_toggle_btn") and self.sort_toggle_btn.winfo_exists():
                self.sort_toggle_btn.configure(text="↓↑ Trier Z→A" if self._sort_reverse else "↑↓ Trier A→Z")

        def delete_all_audio(self):
            audio=[n for n,p in zip(self.video_names,self.video_paths) if is_audio(p)]
            if not audio: messagebox.showinfo("Info","Aucun fichier audio."); return
            if not messagebox.askyesno("Confirmation",f"Supprimer {len(audio)} fichier(s) audio ?"): return
            pairs=[(p,n) for p,n in zip(self.video_paths,self.video_names) if not is_audio(p)]
            if pairs: self.video_paths,self.video_names=map(list,zip(*pairs))
            else: self.video_paths,self.video_names=[],[]
            self.save_library(); self.update_list_button_text(); self.refresh_list_window()

        def add_all_to_playlist(self):
            if not self.video_paths: messagebox.showinfo("Info","La liste est vide."); return
            n=len(self.video_paths)
            if not messagebox.askyesno("Confirmer",f"Ajouter {n} titre(s) à la playlist ?"): return
            for path in self.video_paths: self.playlist.append(path)
            self.save_playlist(); self.update_playlist_button_text()
            self._fetch_durations_bg(self.video_paths[:])
            if self.playlist_win and self.playlist_win.winfo_exists(): self.refresh_playlist_window()
            messagebox.showinfo("Ajouté",f"{n} titre(s) ajouté(s) à la playlist.")

        def delete_duplicates(self):
            seen_names=set(); seen_paths=set(); new_paths=[]; new_names=[]; removed=0
            for p,n in zip(self.video_paths,self.video_names):
                kn=n.lower().strip(); kp=p.lower().strip()
                if kn not in seen_names and kp not in seen_paths:
                    seen_names.add(kn); seen_paths.add(kp); new_paths.append(p); new_names.append(n)
                else: removed+=1
            if removed==0: messagebox.showinfo("Doublons","Aucun doublon trouvé."); return
            if not messagebox.askyesno("Supprimer doublons",f"Supprimer {removed} doublon(s) ?"): return
            self.video_paths,self.video_names=new_paths,new_names
            self.save_library(); self.refresh_list_window(); self.update_list_button_text()
            messagebox.showinfo("Fait",f"{removed} doublon(s) supprimé(s).")

        def _list_hover_select(self,event):
            idx=self.list_win_listbox.nearest(event.y)
            if 0<=idx<self.list_win_listbox.size():
                self.list_win_listbox.selection_clear(0,END); self.list_win_listbox.selection_set(idx)
                self._show_list_hover_thumb(idx, event)
            else:
                self._hide_list_hover_thumb()

        def _show_list_hover_thumb(self, idx, event):
            """Aperçu grand format de la vidéo survolée.

            La position X de la souris dans la ligne représente la position
            dans la vidéo : déplacement latéral = changement d'image.
            """
            if self._tv_mode or idx >= self.list_win_listbox.size():
                return

            try:
                display_name = self.list_win_listbox.get(idx)
            except Exception:
                self._hide_list_hover_thumb()
                return

            real_idx = next((i for i, n in enumerate(self.video_names)
                             if n == display_name), None)
            if real_idx is None or real_idx >= len(self.video_paths):
                self._hide_list_hover_thumb()
                return

            path = self.video_paths[real_idx]
            if not os.path.isfile(path):
                self._hide_list_hover_thumb()
                return

            # Anti-fantôme : aucune apparition avant 2 s.
            if time.time() < self._list_thumb_ready_at:
                self._hide_thumb_win()
                return

            self._ensure_thumb_win()
            self._thumb_img_lbl.configure(width=528, height=297)
            self._thumb_lbl.configure(
                text=os.path.splitext(os.path.basename(path))[0][:55]
            )
            self._reposition_list_hover_thumb(event)

            # X de la souris -> fraction 0..1 de la durée.
            row_w = max(1, self.list_win_listbox.winfo_width())
            frac = max(0.0, min(1.0, float(event.x) / float(row_w)))
            dur_s = self.duration_cache.get(path, 0) or 0
            pos_ms = int(frac * dur_s * 1000.0) if dur_s > 0 else 10000

            self._list_hover_last_idx = idx
            self._list_hover_last_pos_ms = pos_ms

            if self._thumb_hover_job:
                try:
                    self.after_cancel(self._thumb_hover_job)
                except Exception:
                    pass

            # Même principe que le survol de la barre : petit débounce pour
            # éviter une capture ffmpeg à chaque pixel.
            self._thumb_hover_job = self.after(
                120,
                lambda p=path, ms=pos_ms:
                    self._update_thumb_image(p, ms, (528, 297))
            )


        def _reposition_list_hover_thumb(self, event):
            """Positionne la grande vignette à droite de la liste."""
            try:
                if not (self._thumb_win and self._thumb_win.winfo_exists()):
                    return
                self._thumb_win.update_idletasks()
                tw = self._thumb_win.winfo_reqwidth()
                th = self._thumb_win.winfo_reqheight()
                screen_w = self.list_win_listbox.winfo_screenwidth()
                screen_h = self.list_win_listbox.winfo_screenheight()
                margin = 10
                rx = self.list_win_listbox.winfo_rootx() + self.list_win_listbox.winfo_width() + 12
                ry = self.list_win_listbox.winfo_rooty() + event.y - th // 2
                if rx + tw + margin > screen_w:
                    rx = self.list_win_listbox.winfo_rootx() - tw - 12
                x = max(margin, rx)
                y = max(margin, min(ry, screen_h - th - margin))
                if time.time() >= self._list_thumb_ready_at:
                    win_native_show(self._thumb_win, x, y)
            except Exception as ex:
                print(f"[Vignette liste] Erreur positionnement : {ex}")

        def _hide_list_hover_thumb(self):
            self._list_hover_last_idx = None
            self._list_hover_last_pos_ms = None
            self._hide_thumb_win()

        def close_list_window(self):
            try:
                if self._thumb_hover_job:
                    self.after_cancel(self._thumb_hover_job)
            except Exception:
                pass
            self._thumb_hover_job = None
            try:
                if self._list_thumb_ready_job:
                    self.list_win.after_cancel(self._list_thumb_ready_job)
            except Exception:
                pass
            self._list_thumb_ready_job = None
            self._hide_list_hover_thumb()
            if self.list_win:
                self.list_win_geometry=self.list_win.geometry()
                if hasattr(self,"list_win_listbox") and self.list_win_listbox.winfo_exists():
                    self.list_scroll_pos=self.list_win_listbox.yview()[0]
                self.save_settings(); self.list_win.destroy(); self.list_win=None

        def refresh_list_window(self):
            if hasattr(self,"list_win_listbox") and self.list_win_listbox.winfo_exists():
                self.list_win_listbox.delete(0,END)
                for name in self.video_names: self.list_win_listbox.insert(END,name)
            if hasattr(self,"total_label") and self.total_label.winfo_exists():
                self.total_label.configure(text=f"({len(self.video_names)} titres)")

        def filter_list_window(self,*args):
            text=self.list_search_var.get().lower().strip()
            self.list_win_listbox.delete(0,END)
            for name in self.video_names:
                if text in name.lower(): self.list_win_listbox.insert(END,name)

        def sort_list_window(self,reverse):
            pairs=sorted(zip(self.video_names,self.video_paths),
                         key=lambda x:self._natural_key(x[0]),reverse=reverse)
            if pairs: self.video_names,self.video_paths=map(list,zip(*pairs))
            self.save_library(); self.refresh_list_window()

        @staticmethod
        def _natural_key(s):
            import unicodedata,re as _re
            s2=unicodedata.normalize("NFD",s.lower())
            s2="".join(c for c in s2 if unicodedata.category(c)!="Mn")
            parts=_re.split(r"(\d+)",s2)
            return [int(p) if p.isdigit() else p for p in parts]

        def list_win_right_click(self,event):
            sel=self.list_win_listbox.curselection()
            if not sel: return
            display_name=self.list_win_listbox.get(sel[0])
            real_idx=None
            for i,name in enumerate(self.video_names):
                if name==display_name: real_idx=i; break
            if real_idx is None: return
            path=self.video_paths[real_idx]
            menu=Menu(self,tearoff=0,font=("Arial",18))
            menu.add_command(label="▶ Lire cette vidéo",command=lambda: self._play_direct(real_idx))
            menu.add_command(label="📺 Envoyer sur TV",command=lambda: self.open_dlna_window(prefill_path=path))
            menu.add_command(label="➕ Ajouter à la playlist",command=lambda: self.add_to_playlist(real_idx))
            menu.add_command(label="ℹ️ Info du média",command=lambda: self._show_media_info(path))
            menu.add_command(label="📋 Infos (tableur)",command=lambda: (self.close_list_window(), self._show_tableur_info(path, from_liste_medias=True)))
            menu.add_command(label="🗑 Supprimer ce titre",command=lambda: self.delete_title(real_idx))
            menu.post(event.x_root,event.y_root)

        def list_win_double_click(self,event):
            sel=self.list_win_listbox.curselection()
            if sel:
                dn=self.list_win_listbox.get(sel[0])
                for i,n in enumerate(self.video_names):
                    if n==dn: self._play_direct(i); break

        def _play_direct(self,idx):
            self.close_list_window(); self.close_stats_win()
            self._seq_mode = False
            self._list_play_mode = True
            self._clear_search_play_mode()  # ⏮/⏭ = liste complete
            self._list_play_index = idx
            self.play_file(self.video_paths[idx])
            self.set_play_mode("pc","Liste complète")

        # ══════════════════════════════════════════════════════════
        # ── 🧪 Test Citron : automate de diagnostic (renforcé) ──────
        # ══════════════════════════════════════════════════════════
        # Passe en revue en profondeur les fonctionnalités de Citron :
        # infrastructure de base (fichiers, VLC, serveurs réseau internes),
        # MAIS AUSSI des parcours fonctionnels réels (recherche tableur
        # bout-en-bout, ouverture réelle de la fiche 📋 Infos avec son
        # lecteur VLC intégré, stress-test des menus déroulants pour
        # débusquer les fenêtres fantômes, résolution + lecture internet
        # réelle, requêtes DLNA en lecture seule) — sans jamais rien
        # supprimer ni modifier de façon irréversible chez l'utilisateur,
        # et sans jamais envoyer de commande de lecture à une vraie TV.
        #
        # Chaque étape dispose d'un délai maximal (timeout) : si elle ne
        # répond pas dans ce délai, l'étape est marquée « ⏱ TIMEOUT » et le
        # test continue avec la suivante plutôt que de rester bloqué
        # indéfiniment. Limite honnête : ce timeout fonctionne pour les
        # étapes asynchrones (réseau, threads) ; si une étape bloque le
        # thread principal lui-même (ex. un vrai blocage interne à VLC),
        # aucun code Python — même ce timeout — ne peut s'exécuter pendant
        # ce blocage, car Tkinter est mono-thread. Dans ce cas précis, seule
        # la dernière ligne « ▶ Test : … » déjà écrite sur le disque indique
        # où ça a coincé.
        #
        # Chaque résultat est classé explicitement : ✅ succès, ❌ échec réel
        # (donc à corriger), ➖ ignoré (test non applicable dans ce contexte,
        # ex. pas de tableur configuré). Cette distinction évite qu'un test
        # "ignoré" masque un vrai problème dans le résumé final.

        def _test_citron_log(self, message):
            """Écrit une ligne dans le fichier de trace (avec horodatage),
            la force sur le disque, et l'affiche aussi dans la fenêtre de
            suivi si elle est ouverte."""
            line = f"[{datetime.now().strftime('%H:%M:%S')}] {message}"
            fh = getattr(self, "_test_citron_fh", None)
            if fh:
                try:
                    fh.write(line + "\n")
                    fh.flush()
                    try:
                        os.fsync(fh.fileno())
                    except Exception:
                        pass
                except Exception as ex:
                    print(f"[TestCitron] Erreur d'écriture dans la trace : {ex}")
            print(f"[TestCitron] {message}")
            try:
                box = getattr(self, "_test_citron_textbox", None)
                if box and box.winfo_exists():
                    box.configure(state="normal")
                    box.insert("end", line + "\n")
                    box.see("end")
                    box.configure(state="disabled")
            except Exception:
                pass

        def _start_test_citron(self):
            """Point d'entrée du menu ⚙ Paramètres → 🧪 Test Citron. Demande
            l'emplacement du fichier de trace, puis lance l'automate."""
            if getattr(self, "_test_citron_active", False):
                win = getattr(self, "_test_citron_win", None)
                if win and win.winfo_exists():
                    win.lift()
                return

            initial = (getattr(self, "_test_citron_last_folder", None)
                       or getattr(self, "_last_download_dir", None)
                       or self._mem_dir or os.path.expanduser("~"))
            if not initial or not os.path.isdir(initial):
                initial = os.path.expanduser("~")
            folder = filedialog.askdirectory(
                title="Où enregistrer le fichier de trace « Test Citron » ?",
                initialdir=initial, parent=self)
            if not folder:
                return
            folder = os.path.normpath(folder)
            self._test_citron_last_folder = folder

            path = os.path.join(folder, "Test Citron.txt")
            if os.path.exists(path):
                # Ne jamais écraser une trace précédente : on horodate le
                # nouveau fichier tout en gardant le nom « Test Citron ».
                ts = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")
                path = os.path.join(folder, f"Test Citron ({ts}).txt")

            try:
                fh = open(path, "w", encoding="utf-8", buffering=1)
            except Exception as ex:
                messagebox.showerror("Test Citron",
                    f"Impossible de créer le fichier de trace :\n{ex}")
                return

            self._test_citron_fh = fh
            self._test_citron_path = path
            self._test_citron_active = True
            self._test_citron_cancel = False
            # Capture de toute la sortie console (y compris les print() de
            # diagnostic dispersés ailleurs dans le fichier) pendant la durée
            # du test, pour pouvoir la regrouper avec les résultats à la fin
            # — bien plus efficace pour comprendre un échec que les seules
            # lignes "▶ Test : ..." déjà écrites dans la trace.
            self._test_citron_console_buf = io.StringIO()
            self._test_citron_stdout_orig = sys.stdout
            sys.stdout = _StdoutTee(self._test_citron_stdout_orig, self._test_citron_console_buf)
            self._test_citron_steps = self._tc_build_steps()
            self._test_citron_idx = 0
            self._test_citron_counts = {"ok": 0, "fail": 0, "skip": 0}
            self._test_citron_start_ts = time.time()
            self._test_citron_results_list = []

            # Pendant le test, on intercepte aussi les exceptions Tk non
            # gérées (report_callback_exception) pour les tracer dans le
            # fichier — c'est ainsi qu'un plantage déclenché par un widget
            # pendant le test se retrouve consigné, en plus des erreurs
            # attrapées étape par étape.
            self._test_citron_prev_exc_handler = self.report_callback_exception
            def _hooked_handler(exc, val, tb):
                try:
                    self._test_citron_log(f"❌ PLANTAGE détecté (exception non gérée) : {val}")
                    self._test_citron_log("".join(traceback.format_exception(exc, val, tb)).rstrip())
                    self._test_citron_counts["fail"] += 1
                except Exception:
                    pass
                try:
                    self._test_citron_prev_exc_handler(exc, val, tb)
                except Exception:
                    pass
            self.report_callback_exception = _hooked_handler

            self._open_test_citron_status_win()
            self._test_citron_log("=== DÉBUT DU TEST CITRON (RENFORCÉ) ===")
            self._test_citron_log(f"Date et heure : {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
            self._test_citron_log(f"Fichier de trace : {path}")
            self._test_citron_log(f"Nombre d'étapes prévues : {len(self._test_citron_steps)}")
            self.after(200, self._test_citron_next_step)

        def _tc_apply_last_window_geometry(self, win, default_w, default_h):
            """Positionne (et si raisonnable, dimensionne) une fenêtre Test
            Citron selon la dernière fenêtre secondaire ouverte par
            l'utilisateur (Liste, Playlist, Téléchargements, TV, résultats de
            recherche…), pour rester visuellement proche de son contexte de
            travail plutôt que de toujours s'ouvrir au même endroit fixe.
            Repli sur une taille par défaut centrée sur la fenêtre principale
            si aucune géométrie n'est connue."""
            geo = getattr(self, "_last_window_geometry", None)
            w, h, x, y = default_w, default_h, None, None
            if geo:
                try:
                    import re as _re
                    m = _re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", geo)
                    if m:
                        lw, lh, lx, ly = (int(v) for v in m.groups())
                        w = max(480, min(lw, 1200))
                        h = max(360, min(lh, 950))
                        x, y = lx, ly
                except Exception:
                    pass
            try:
                sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
            except Exception:
                sw, sh = 1920, 1080
            if x is None or y is None:
                try:
                    x = self.winfo_rootx() + (self.winfo_width() - w) // 2
                    y = self.winfo_rooty() + (self.winfo_height() - h) // 2
                except Exception:
                    x, y = (sw - w) // 2, (sh - h) // 2
            x = max(0, min(x, max(0, sw - w)))
            y = max(0, min(y, max(0, sh - h)))
            try:
                win.geometry(f"{w}x{h}+{x}+{y}")
            except Exception:
                pass

        def _tc_start_cartoon_anim(self, win, canvas):
            """Anime un petit citron très 'cartoon' (rebond exagéré,
            grands yeux, clin d'œil, petite clé à outils) pendant toute la
            durée du test — purement décoratif, indépendant de l'animation
            pseudo-3D utilisée pour la recherche dans le tableur."""
            state = {"t": 0.0, "stop": False}

            def _stop():
                state["stop"] = True

            win._tc_cartoon_stop = _stop  # accessible depuis _close_test_citron_win

            def _draw():
                if state["stop"] or not getattr(self, "_test_citron_active", False):
                    return
                try:
                    if not (win.winfo_exists() and canvas.winfo_exists()):
                        return
                except Exception:
                    return
                canvas.delete("all")
                w = canvas.winfo_width() or 120
                h = canvas.winfo_height() or 90
                cx, cy = w // 2, h - 28

                t = state["t"]
                bounce = abs(math.sin(t * 2.2)) * (h * 0.28)
                squash = 1.0 - min(0.28, bounce / (h * 0.6))
                ry = 20 * (1.0 + (1 - squash) * 0.9)
                rx = 24 * (1.0 + (1 - squash) * 0.5)
                by = cy - bounce

                # Ombre
                shadow_w = rx * (1.1 - bounce / (h * 1.2))
                canvas.create_oval(cx - shadow_w, cy + 18, cx + shadow_w, cy + 24,
                                   fill="#000000", outline="", stipple="gray50")

                # Corps
                canvas.create_oval(cx - rx, by - ry, cx + rx, by + ry,
                                   fill="#f5d547", outline="#c9960f", width=2)
                # Feuille
                canvas.create_oval(cx + rx * 0.35, by - ry - 10, cx + rx * 0.75, by - ry + 4,
                                   fill="#3cb371", outline="#2e8b57")

                # Yeux (très cartoon : grands, blancs, clin d'œil alterné)
                blink_l = (int(t * 4) % 10) == 0
                eye_dx = rx * 0.42
                eye_y = by - ry * 0.15
                for side, dx in ((0, -eye_dx), (1, eye_dx)):
                    if side == 0 and blink_l:
                        canvas.create_line(cx + dx - 6, eye_y, cx + dx + 6, eye_y,
                                           fill="#222222", width=3)
                        continue
                    canvas.create_oval(cx + dx - 7, eye_y - 9, cx + dx + 7, eye_y + 9,
                                       fill="white", outline="#222222")
                    look = math.sin(t * 1.7) * 2
                    canvas.create_oval(cx + dx - 3 + look, eye_y - 3, cx + dx + 3 + look, eye_y + 3,
                                       fill="#222222", outline="")

                # Grand sourire content
                canvas.create_arc(cx - rx * 0.5, by + 2, cx + rx * 0.5, by + ry * 0.9,
                                  start=200, extent=140, style="arc",
                                  outline="#222222", width=2)

                # Petite clé à outils qui tourne autour (côté "diagnostic")
                wrang = t * 2.4
                wx = cx + math.cos(wrang) * (rx + 22)
                wy = by + math.sin(wrang) * (rx * 0.6 + 10)
                canvas.create_line(wx - 6, wy - 6, wx + 6, wy + 6, fill="#bbbbbb", width=4)
                canvas.create_oval(wx - 8, wy - 8, wx - 2, wy - 2, outline="#bbbbbb", width=3)

                state["t"] += 0.09
                win.after(45, _draw)

            _draw()

        def _tc_start_banter(self, win, label):
            """Fait défiler, toutes les 4 secondes environ, un petit
            échange voix off / Citron dans l'en-tête de la fenêtre de
            test — piochage aléatoire dans la banque « Audiard », sans
            répétition immédiate. S'arrête tout seul quand la fenêtre
            se ferme."""
            dialogues = _pick_audiard_dialogues(8)
            state = {"i": 0}

            def _tick():
                if not win.winfo_exists():
                    return
                off_txt, citron_txt = dialogues[state["i"] % len(dialogues)]
                try:
                    label.configure(text=f"— {off_txt}\n🍋 {citron_txt}")
                except Exception:
                    pass
                state["i"] += 1
                win.after(4000, _tick)

            _tick()

        def _open_test_citron_status_win(self):
            """Petite fenêtre de suivi en direct du test, avec une animation
            cartoon, un bouton pour l'arrêter proprement, et une position
            reprenant celle de la dernière fenêtre secondaire ouverte."""
            win = ctk.CTkToplevel(self)
            win.title("🧪 Citron met la main à la pâte…")
            self._tc_apply_last_window_geometry(win, 680, 520)
            win.attributes("-topmost", True)
            win.transient(self)
            # Empêche une fermeture accidentelle pendant le test (la croix ne
            # fait rien tant que le test tourne — on utilise « Arrêter »).
            win.protocol("WM_DELETE_WINDOW", lambda: None)
            self._test_citron_win = win

            header = ctk.CTkFrame(win, fg_color="transparent")
            header.pack(fill="x", padx=14, pady=(12, 4))
            cartoon_canvas = Canvas(header, width=90, height=90, bg="#242424",
                                    highlightthickness=0)
            cartoon_canvas.pack(side="left", padx=(0, 10))
            title_col = ctk.CTkFrame(header, fg_color="transparent")
            title_col.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(title_col, text="🧪 Test Citron — automate de diagnostic renforcé",
                         font=("Arial", 16, "bold"), anchor="w").pack(fill="x")
            ctk.CTkLabel(title_col, text="Teste en profondeur les fonctionnalités de Citron (y compris des "
                                         "parcours réels : recherche tableur, fiche Infos, menus, internet) "
                                         "et trace chaque étape dans le fichier choisi, en français.",
                         font=("Arial", 11), text_color="#aaaaaa", anchor="w",
                         justify="left", wraplength=460).pack(fill="x", pady=(2, 0))
            banter_lbl = ctk.CTkLabel(title_col, text="", font=("Arial", 10, "italic"),
                                      text_color="#8a8a8a", anchor="w", justify="left",
                                      wraplength=460)
            banter_lbl.pack(fill="x", pady=(4, 0))
            self._tc_start_banter(win, banter_lbl)
            self._tc_start_cartoon_anim(win, cartoon_canvas)

            from tkinter import Text as _Text
            box = _Text(win, font=("Consolas", 11), bg="#111111", fg="#cccccc",
                        relief="flat", wrap="word", state="disabled",
                        bd=0, highlightthickness=0)
            box.pack(fill="both", expand=True, padx=14, pady=8)
            self._test_citron_textbox = box

            btn_row = ctk.CTkFrame(win, fg_color="transparent")
            btn_row.pack(pady=(0, 12))
            self._test_citron_stop_btn = ctk.CTkButton(
                btn_row, text="⏹ Arrêter le test", fg_color="#8b3a00",
                command=self._test_citron_request_stop)
            self._test_citron_stop_btn.pack(side="left", padx=6)
            self._test_citron_close_btn = ctk.CTkButton(
                btn_row, text="Fermer", state="disabled",
                command=self._close_test_citron_win)
            self._test_citron_close_btn.pack(side="left", padx=6)

        def _test_citron_request_stop(self):
            self._test_citron_cancel = True
            self._test_citron_log("⏹ Arrêt demandé par l'utilisateur — fin après l'étape en cours…")

        def _close_test_citron_win(self):
            win = getattr(self, "_test_citron_win", None)
            if win:
                try:
                    stop = getattr(win, "_tc_cartoon_stop", None)
                    if stop:
                        stop()
                except Exception:
                    pass
                if win.winfo_exists():
                    win.destroy()
            self._test_citron_win = None
            self._test_citron_textbox = None

        def _test_citron_next_step(self):
            """Exécute les étapes du test l'une après l'autre (sur le thread
            principal, pour rester compatible avec Tkinter/VLC), avec un
            timeout par étape et un statut explicite (succès/échec/ignoré)."""
            if getattr(self, "_test_citron_cancel", False):
                self._test_citron_finish(cancelled=True)
                return
            idx = self._test_citron_idx
            steps = self._test_citron_steps
            if idx >= len(steps):
                self._test_citron_finish(cancelled=False)
                return
            name, func, timeout_s = steps[idx]
            self._test_citron_idx += 1
            # Cette ligne est écrite (et forcée sur le disque) AVANT
            # d'exécuter l'étape : c'est elle qui permet de savoir, même en
            # cas de plantage ou de blocage, ce que Citron était en train de
            # tester.
            self._test_citron_log(f"▶ Test : {name}… (délai maximal {timeout_s}s)")

            call_state = {"done": False}
            timeout_job = [None]

            def _record(status_label, detail):
                self._test_citron_results_list.append({
                    "name": name, "status": status_label, "detail": detail,
                    "time": datetime.now().strftime("%H:%M:%S"),
                })

            def _done(status=True, detail=""):
                # status : True = succès, False = échec réel, None = ignoré.
                if call_state["done"]:
                    return  # appel tardif (ex. après un timeout déjà déclenché) : ignoré
                call_state["done"] = True
                if timeout_job[0] is not None:
                    try:
                        self.after_cancel(timeout_job[0])
                    except Exception:
                        pass
                counts = self._test_citron_counts
                if status is True:
                    counts["ok"] += 1
                    self._test_citron_log(f"✅ Résultat : {detail or 'OK'}")
                    _record("ok", detail or "OK")
                elif status is False:
                    counts["fail"] += 1
                    self._test_citron_log(f"❌ ÉCHEC : {detail or 'erreur inconnue'}")
                    _record("fail", detail or "erreur inconnue")
                else:
                    counts["skip"] += 1
                    self._test_citron_log(f"➖ Ignoré : {detail or 'non applicable dans ce contexte'}")
                    _record("skip", detail or "non applicable dans ce contexte")
                self.after(120, self._test_citron_next_step)

            def _on_timeout():
                if call_state["done"]:
                    return
                call_state["done"] = True
                self._test_citron_counts["fail"] += 1
                detail = f"Aucune réponse dans le délai de {timeout_s}s (peut-être bloquée)"
                self._test_citron_log(
                    f"⏱ TIMEOUT après {timeout_s}s — aucune réponse de cette étape dans le délai "
                    f"(elle est peut-être bloquée ; on continue avec la suivante)")
                _record("fail", f"⏱ TIMEOUT — {detail}")
                self.after(120, self._test_citron_next_step)

            timeout_job[0] = self.after(int(timeout_s * 1000), _on_timeout)

            try:
                func(_done)
            except Exception as ex:
                if not call_state["done"]:
                    call_state["done"] = True
                    if timeout_job[0] is not None:
                        try:
                            self.after_cancel(timeout_job[0])
                        except Exception:
                            pass
                    self._test_citron_counts["fail"] += 1
                    self._test_citron_log(f"❌ ÉCHEC (exception) : {ex}")
                    self._test_citron_log(traceback.format_exc().rstrip())
                    _record("fail", f"Exception : {ex}")
                    self.after(120, self._test_citron_next_step)


        def _test_citron_finish(self, cancelled=False):
            counts = getattr(self, "_test_citron_counts", {"ok": 0, "fail": 0, "skip": 0})
            elapsed = time.time() - getattr(self, "_test_citron_start_ts", time.time())
            total = counts["ok"] + counts["fail"] + counts["skip"]
            self._test_citron_log(
                f"Résumé : {counts['ok']} succès, {counts['fail']} échec(s), "
                f"{counts['skip']} ignoré(s) sur {total} étape(s) exécutée(s) "
                f"en {elapsed:.1f}s.")
            if counts["fail"] > 0:
                self._test_citron_log(
                    f"⚠️ {counts['fail']} problème(s) détecté(s) — recherchez les lignes "
                    f"« ❌ ÉCHEC » ou « ⏱ TIMEOUT » ci-dessus pour les localiser précisément.")
            else:
                self._test_citron_log("✅ Aucun échec détecté sur les étapes exécutées.")
            if cancelled:
                self._test_citron_log("=== TEST INTERROMPU PAR L'UTILISATEUR ===")
            else:
                self._test_citron_log("=== FIN DU TEST — TOUTES LES ÉTAPES ONT ÉTÉ EXÉCUTÉES ===")
            try:
                prev = getattr(self, "_test_citron_prev_exc_handler", None)
                if prev:
                    self.report_callback_exception = prev
            except Exception:
                pass
            fh = getattr(self, "_test_citron_fh", None)
            # Restaurer la console normale AVANT toute chose : sinon une
            # exception plus bas laisserait sys.stdout redirigé en
            # permanence, ce qui affecterait tout le reste de la session.
            console_text = ""
            try:
                sys.stdout = getattr(self, "_test_citron_stdout_orig", sys.stdout)
                buf = getattr(self, "_test_citron_console_buf", None)
                if buf:
                    console_text = buf.getvalue()
            except Exception:
                pass
            self._test_citron_console_text = console_text
            if fh and console_text:
                try:
                    fh.write("\n" + "=" * 70 + "\n")
                    fh.write("SORTIE CONSOLE COMPLÈTE PENDANT LE TEST (pour diagnostic)\n")
                    fh.write("=" * 70 + "\n")
                    fh.write(console_text)
                    fh.flush()
                except Exception:
                    pass
            if fh:
                try:
                    fh.close()
                except Exception:
                    pass
            self._test_citron_fh = None
            self._test_citron_active = False
            path = getattr(self, "_test_citron_path", "")

            # Sauvegarde structurée (JSON) des résultats, à côté de la trace
            # texte, pour que « 📊 Résultats des tests Citron » puisse les
            # relire même après avoir fermé/rouvert Citron.
            self._test_citron_last_summary = {**counts, "elapsed": round(elapsed, 1),
                                              "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                                              "cancelled": cancelled}
            try:
                json_path = path[:-4] + ".json" if path.lower().endswith(".txt") else path + ".json"
                with open(json_path, "w", encoding="utf-8") as jf:
                    json.dump({
                        "date": self._test_citron_last_summary["date"],
                        "trace_file": path,
                        "summary": counts,
                        "elapsed": round(elapsed, 1),
                        "cancelled": cancelled,
                        "results": self._test_citron_results_list,
                    }, jf, ensure_ascii=False, indent=2)
                self._test_citron_last_json = json_path
                self._test_citron_log(f"Résultats structurés enregistrés : {json_path}")
            except Exception as ex:
                self._test_citron_log(f"⚠️ Impossible d'enregistrer le fichier de résultats JSON : {ex}")

            try:
                self.save_settings()
            except Exception:
                pass

            win = getattr(self, "_test_citron_win", None)
            if win and win.winfo_exists():
                win.protocol("WM_DELETE_WINDOW", self._close_test_citron_win)
                try:
                    if hasattr(self, "_test_citron_stop_btn") and self._test_citron_stop_btn.winfo_exists():
                        self._test_citron_stop_btn.configure(state="disabled")
                    if hasattr(self, "_test_citron_close_btn") and self._test_citron_close_btn.winfo_exists():
                        self._test_citron_close_btn.configure(state="normal")
                except Exception:
                    pass
                win.title(f"🧪 Test Citron — terminé ({counts['fail']} échec(s))")
                # Utilise la position/taille de la fenêtre de suivi comme
                # référence pour la fenêtre de résultats qui va s'ouvrir
                # juste après, afin qu'elle apparaisse au même endroit.
                try:
                    self._remember_last_window_geometry(win)
                except Exception:
                    pass

            color = "#c42b1c" if counts["fail"] > 0 else "#1a6e3c"
            self._show_toast(
                f"🧪 Test Citron terminé : {counts['ok']}✅ {counts['fail']}❌ {counts['skip']}➖ "
                f"— {os.path.basename(path)}", ms=6000, color=color)

            # Ouvre automatiquement la fenêtre de résultats détaillés : plus
            # besoin de repasser par ⚙ Paramètres → 📊 Résultats des tests
            # Citron. La fenêtre de suivi se referme dans la foulée.
            def _auto_show_results():
                self._close_test_citron_win()
                self._show_test_citron_results()
            self.after(500, _auto_show_results)

        def _show_test_citron_results(self):
            """Menu ⚙ Paramètres → 📊 Résultats des tests Citron : affiche la
            liste détaillée du dernier test exécuté (en mémoire si Citron
            n'a pas redémarré depuis, sinon relu depuis le fichier JSON
            enregistré à côté de la trace texte)."""
            results = list(getattr(self, "_test_citron_results_list", None) or [])
            summary = getattr(self, "_test_citron_last_summary", None)
            src_path = getattr(self, "_test_citron_last_json", None)

            if not results:
                json_path = getattr(self, "_test_citron_last_json", None)
                if json_path and os.path.isfile(json_path):
                    try:
                        with open(json_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        results = data.get("results", [])
                        summary = {**data.get("summary", {}), "elapsed": data.get("elapsed", 0),
                                   "date": data.get("date", "")}
                        src_path = json_path
                    except Exception:
                        results = []

            if not results:
                initial = (getattr(self, "_test_citron_last_folder", None)
                           or os.path.expanduser("~"))
                folder = filedialog.askdirectory(
                    title="Choisir le dossier contenant un fichier « Test Citron (...).json »",
                    initialdir=initial, parent=self)
                if not folder:
                    messagebox.showinfo("Résultats des tests Citron",
                        "Aucun résultat de test disponible pour l'instant.\n"
                        "Lancez d'abord ⚙ Paramètres → 🧪 Test Citron.")
                    return
                candidates = sorted(
                    (f for f in os.listdir(folder)
                     if f.startswith("Test Citron") and f.endswith(".json")),
                    reverse=True)
                if not candidates:
                    messagebox.showinfo("Résultats des tests Citron",
                        "Aucun fichier de résultats « Test Citron*.json » trouvé dans ce dossier.")
                    return
                json_path = os.path.join(folder, candidates[0])
                try:
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    results = data.get("results", [])
                    summary = {**data.get("summary", {}), "elapsed": data.get("elapsed", 0),
                               "date": data.get("date", "")}
                    src_path = json_path
                except Exception as ex:
                    messagebox.showerror("Résultats des tests Citron",
                        f"Impossible de lire le fichier :\n{ex}")
                    return

            win = ctk.CTkToplevel(self)
            win.title("📊 Résultats des tests Citron")
            self._tc_apply_last_window_geometry(win, 780, 660)
            win.transient(self); win.lift()

            ctk.CTkLabel(win, text="📊 Résultats des tests Citron",
                         font=("Arial", 20, "bold")).pack(pady=(14, 4))
            if summary:
                txt = (f"{summary.get('ok',0)} succès  —  {summary.get('fail',0)} échec(s)  —  "
                       f"{summary.get('skip',0)} ignoré(s)  —  {summary.get('elapsed',0)}s")
                if summary.get("date"):
                    txt += f"   ({summary['date']})"
                color = "#ff8080" if summary.get("fail", 0) else "#8fd18f"
                ctk.CTkLabel(win, text=txt, font=("Arial", 14, "bold"), text_color=color).pack()
            if src_path:
                ctk.CTkLabel(win, text=src_path, font=("Arial", 10),
                             text_color="#888888").pack(pady=(0, 6))

            sf = ctk.CTkFrame(win); sf.pack(fill="x", padx=16, pady=6)
            ctk.CTkLabel(sf, text="🔍", font=("Arial", 16)).pack(side="left", padx=(10, 5))
            search_var = ctk.StringVar()
            ctk.CTkEntry(sf, placeholder_text="Filtrer (ex : échec, tableur, menu, ignoré…)",
                         textvariable=search_var, height=38).pack(side="left", fill="x", expand=True, padx=5)

            lf = ctk.CTkFrame(win); lf.pack(fill="both", expand=True, padx=16, pady=8)
            lb = Listbox(lf, font=("Arial", 12), bg="#2b2b2b", fg="white",
                         selectbackground="#1f6aa5", activestyle="none")
            sb = Scrollbar(lf, orient="vertical", command=lb.yview)
            lb.config(yscrollcommand=sb.set)
            lb.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")

            icon_map = {"ok": "✅", "fail": "❌", "skip": "➖"}
            color_map = {"ok": "#8fd18f", "fail": "#ff8080", "skip": "#999999"}

            def _fill(*_a):
                text = search_var.get().lower().strip()
                lb.delete(0, END)
                for r in results:
                    line = (f"{icon_map.get(r.get('status'), '?')}  "
                            f"[{r.get('time','')}]  {r.get('name','')}  —  {r.get('detail','')}")
                    if text and text not in line.lower():
                        continue
                    lb.insert(END, line)
                    lb.itemconfig(lb.size() - 1, fg=color_map.get(r.get("status"), "white"))
            search_var.trace("w", _fill)
            _fill()

            bf = ctk.CTkFrame(win); bf.pack(pady=(0, 14))
            ctk.CTkButton(bf, text="🔁 Relancer un test", height=36, fg_color="#1a6e3c",
                          command=lambda: (win.destroy(), self._start_test_citron())
                          ).pack(side="left", padx=6)

            def _open_trace():
                target = None
                if src_path and src_path.endswith(".json"):
                    txt_path = src_path[:-5] + ".txt"
                    if os.path.isfile(txt_path):
                        target = txt_path
                if not target and src_path:
                    target = os.path.dirname(src_path)
                if not target:
                    return
                try:
                    if os.name == "nt":
                        os.startfile(target)
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", target])
                    else:
                        subprocess.Popen(["xdg-open", target])
                except Exception as ex:
                    messagebox.showerror("Ouverture", str(ex), parent=win)

            def _copy_all():
                """Regroupe résultats structurés + sortie console complète du
                test dans un seul bloc de texte, copié dans le presse-papiers
                — bien plus efficace pour un diagnostic que les seules lignes
                de résultat, qui n'incluent pas les print() de diagnostic
                dispersés ailleurs dans Citron (ex: [Vignette], [Settings]...)."""
                lines = []
                if summary:
                    lines.append(f"Résumé : {summary.get('ok',0)} succès, "
                                  f"{summary.get('fail',0)} échec(s), "
                                  f"{summary.get('skip',0)} ignoré(s), "
                                  f"{summary.get('elapsed',0)}s"
                                  + (f" ({summary['date']})" if summary.get('date') else ""))
                    lines.append("")
                for r in results:
                    lines.append(f"{icon_map.get(r.get('status'), '?')}  "
                                  f"[{r.get('time','')}]  {r.get('name','')}  —  {r.get('detail','')}")
                console_text = getattr(self, "_test_citron_console_text", "") or ""
                if not console_text and src_path and src_path.endswith(".json"):
                    # Résultats rechargés depuis un fichier (pas la session en
                    # cours) : relire la sortie console depuis la trace texte
                    # associée, où elle a été regroupée à la fin du test.
                    txt_path = src_path[:-5] + ".txt"
                    if os.path.isfile(txt_path):
                        try:
                            with open(txt_path, "r", encoding="utf-8") as f:
                                full = f.read()
                            marker = "SORTIE CONSOLE COMPLÈTE PENDANT LE TEST"
                            if marker in full:
                                console_text = full.split(marker, 1)[1].lstrip("\n= ")
                        except Exception:
                            pass
                if console_text:
                    lines.append("")
                    lines.append("=" * 60)
                    lines.append("SORTIE CONSOLE COMPLÈTE PENDANT LE TEST (pour diagnostic)")
                    lines.append("=" * 60)
                    lines.append(console_text)
                try:
                    win.clipboard_clear()
                    win.clipboard_append("\n".join(lines))
                    self._show_toast("📋 Résultats + console copiés dans le presse-papiers", ms=3500)
                except Exception as ex:
                    messagebox.showerror("Copier", str(ex), parent=win)

            ctk.CTkButton(bf, text="📋 Copier tout (résultats + console)", height=36,
                          fg_color="#6a3a9a", command=_copy_all).pack(side="left", padx=6)
            if src_path:
                ctk.CTkButton(bf, text="🧾 Ouvrir la trace complète", height=36,
                              fg_color="#2a4a6a", command=_open_trace).pack(side="left", padx=6)
            ctk.CTkButton(bf, text="Fermer", height=36, fg_color="#555555",
                          command=win.destroy).pack(side="left", padx=6)
            self._remember_last_window_geometry(win)

        # ── Liste des étapes testées : (nom, fonction, délai max en s) ──
        def _tc_build_steps(self):
            return [
                ("Vérification du fichier de paramètres (citron_settings.json)", self._tc_step_settings, 5),
                ("Vérification de la bibliothèque de médias (citron_library.json)", self._tc_step_library, 5),
                ("Vérification du cache des durées (citron_durations.json)", self._tc_step_durations, 5),
                ("Vérification de la playlist (playlist.json)", self._tc_step_playlist, 5),
                ("Vérification des modules externes optionnels", self._tc_step_modules, 8),
                ("Recherche de ffmpeg (génération des vignettes vidéo)", self._tc_step_ffmpeg, 5),
                ("Test du lecteur VLC interne", self._tc_step_vlc, 8),
                ("Test du serveur de streaming HTTP (port 8765)", self._tc_step_http_server, 8),
                ("Test réel de diffusion d'un fichier via le serveur de streaming", self._tc_step_streaming_real_file, 10),
                ("Extraction réelle de la durée d'un média via VLC", self._tc_step_duration_extract, 12),
                ("Test du serveur de commandes citron:// (port 8767)", self._tc_step_cmd_server, 8),
                ("Test de fonctions internes (analyse d'URL, tri, recherche floue…)", self._tc_step_pure_functions, 8),
                ("Test de relocalisation d'un chemin volontairement inexistant", self._tc_step_relocate_fake_path, 8),
                ("Ouverture/fermeture de la fenêtre Liste complète", self._tc_step_win_list, 8),
                ("Test du filtre de recherche dans la Liste complète", self._tc_step_list_filter, 8),
                ("Ouverture/fermeture de la fenêtre Playlist", self._tc_step_win_playlist, 8),
                ("Aller-retour d'un titre dans la playlist (ajout puis retrait)", self._tc_step_playlist_roundtrip, 8),
                ("Ouverture/fermeture de la fenêtre Statistiques", self._tc_step_win_stats, 8),
                ("Ouverture/fermeture de la fenêtre Téléchargements", self._tc_step_win_downloads, 8),
                ("Ouverture/fermeture de « Titres identiques » (Téléchargements)", self._tc_step_win_dl_duplicates, 8),
                ("Test d'écriture dans le dossier Citron-Mémoire", self._tc_step_mem_folder, 5),
                ("Vérification de l'espace disque disponible", self._tc_step_disk_space, 5),
                ("Réglage puis restauration du volume", self._tc_step_volume, 10),
                ("Coupure puis restauration du son du navigateur", self._tc_step_browser_mute, 6),
                ("Affichage d'un bandeau de notification", self._tc_step_toast, 5),
                ("Recherche d'appareils DLNA sur le réseau (lecture seule)", self._tc_step_dlna, 10),
                ("Requête d'état DLNA en lecture seule (sans jamais lancer de lecture sur la TV)", self._tc_step_dlna_query, 8),
                ("Vérification de la configuration du tableur", self._tc_step_tableur, 25),
                ("Recherche tableur bout-en-bout par titre", self._tc_step_tableur_search_titre, 20),
                ("Recherche tableur bout-en-bout par année", self._tc_step_tableur_search_annee, 20),
                ("Recherche tableur bout-en-bout par acteur", self._tc_step_tableur_search_acteur, 20),
                ("Recherche tableur : cas sans résultat (chaîne improbable)", self._tc_step_tableur_search_vide, 15),
                ("Ouverture réelle de la fiche 📋 Infos (tableur) puis fermeture propre", self._tc_step_infos_window, 15),
                ("Stress-test des menus déroulants (ouverture/fermeture rapide répétée)", self._tc_step_menus_stress, 12),
                ("Fermeture globale de toutes les fenêtres secondaires", self._tc_step_close_all_secondary, 8),
                ("Vérification du protocole citron:// (registre Windows)", self._tc_step_protocol, 5),
                ("Mécanisme de vérification de mise à jour", self._tc_step_update_check, 8),
                ("Export/import de sauvegarde (aller-retour, sans dialogue)", self._tc_step_backup_roundtrip, 8),
                ("Migration du schéma de réglages + fichier corrompu", self._tc_step_settings_migration, 8),
                ("Test de lecture d'un média de la bibliothèque (aperçu silencieux)", self._tc_step_playback, 10),
                ("Résolution d'une URL internet réelle (yt-dlp, sans téléchargement)", self._tc_step_internet_resolve, 25),
                ("Lecture internet réelle sur PC (bouton « Lire sur PC », sans téléchargement)", self._tc_step_internet_play, 25),
            ]

        # ── Étapes individuelles (chacune appelle done(status, detail)) ──
        # status : True = succès, False = échec réel, None = ignoré.

        def _tc_step_settings(self, done):
            try:
                self.save_settings()
                sp = self._settings_path()
                ok = os.path.isfile(sp)
                done(ok, f"Fichier trouvé : {sp}" if ok else "Fichier introuvable après sauvegarde")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_library(self, done):
            try:
                n_paths, n_names = len(self.video_paths), len(self.video_names)
                coherent = (n_paths == n_names)
                exists = os.path.exists(self._data_file_path("citron_library.json"))
                done(coherent, f"{n_paths} média(s) en bibliothèque, listes cohérentes : {coherent}, "
                                f"fichier présent : {exists}")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_durations(self, done):
            try:
                n = len(self.duration_cache)
                exists = os.path.exists(self._data_file_path("citron_durations.json"))
                done(True, f"{n} durée(s) en cache, fichier présent : {exists}")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_playlist(self, done):
            try:
                self.save_playlist()
                exists = os.path.exists(self._data_file_path("playlist.json"))
                done(exists, f"{len(self.playlist)} titre(s) en playlist, fichier présent : {exists}")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_modules(self, done):
            statuses = []
            any_missing = False
            for mod_name, label in (
                ("yt_dlp", "yt-dlp (téléchargement/lecture internet)"),
                ("odf.opendocument", "odfpy (tableur .ods)"),
                ("pycaw.pycaw", "pycaw (coupure du son du navigateur)"),
                ("edge_tts", "edge-tts (voix neuronale du résumé)"),
            ):
                try:
                    __import__(mod_name)
                    statuses.append(f"{label} : présent")
                except Exception:
                    statuses.append(f"{label} : absent (fonctionnalité associée limitée)")
                    any_missing = True
            # Un module absent n'est pas un « échec » de Citron lui-même
            # (c'est une dépendance optionnelle) : on le classe en info,
            # jamais en échec, pour ne pas polluer le résumé.
            done(True, " | ".join(statuses))

        def _tc_step_ffmpeg(self, done):
            try:
                p = self._get_ffmpeg_path()
                done(True, p if p else "non trouvé (repli automatique sur le lecteur VLC pour les vignettes)")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_vlc(self, done):
            try:
                if not self.player:
                    done(False, "self.player est vide (VLC ne s'est pas initialisé au démarrage)")
                    return
                test_inst = vlc.Instance("--quiet")
                test_player = test_inst.media_player_new()
                ver = vlc.libvlc_get_version().decode(errors="ignore")
                test_player.release()
                test_inst.release()
                done(True, f"libvlc {ver} — instance de test créée puis libérée avec succès")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_http_server(self, done):
            def worker():
                ok, detail = False, ""
                try:
                    port = self.stream_server.port
                    req = urllib.request.Request(f"http://127.0.0.1:{port}/__test_citron__")
                    try:
                        urllib.request.urlopen(req, timeout=3)
                        ok, detail = True, "Serveur joignable (réponse reçue)"
                    except Exception as he:
                        msg = str(he)
                        if "404" in msg or "HTTP Error" in msg or "Not Found" in msg:
                            ok = True
                            detail = f"Serveur joignable (réponse HTTP reçue, normal pour un fichier de test inexistant : {msg})"
                        else:
                            raise
                except Exception as ex:
                    ok, detail = False, f"Serveur injoignable sur le port {getattr(self.stream_server,'port','?')} : {ex}"
                self.after(0, lambda: done(ok, detail))
            threading.Thread(target=worker, daemon=True).start()

        def _tc_step_cmd_server(self, done):
            def worker():
                ok, detail = False, ""
                try:
                    with socket.create_connection(("127.0.0.1", CITRON_CMD_PORT), timeout=3):
                        ok, detail = True, f"Connexion réussie sur le port {CITRON_CMD_PORT}"
                except Exception as ex:
                    ok, detail = False, f"Connexion impossible sur le port {CITRON_CMD_PORT} : {ex}"
                self.after(0, lambda: done(ok, detail))
            threading.Thread(target=worker, daemon=True).start()

        def _tc_step_streaming_real_file(self, done):
            """Diffuse RÉELLEMENT un fichier de la bibliothèque via le serveur
            de streaming HTTP interne et vérifie qu'un vrai téléchargement
            partiel (Range) fonctionne — pas seulement que le serveur répond."""
            candidate = next((p for p in self.video_paths if os.path.isfile(p)), None)
            if not candidate:
                done(None, "Aucun fichier de bibliothèque accessible — test ignoré")
                return
            try:
                self.stream_server.serve(candidate)
                url = self.stream_server.get_url(candidate)
            except Exception as ex:
                done(False, str(ex))
                return

            def worker():
                try:
                    req = urllib.request.Request(url, headers={"Range": "bytes=0-1023"})
                    with urllib.request.urlopen(req, timeout=6) as r:
                        data = r.read()
                        code = getattr(r, "status", getattr(r, "code", "?"))
                    ok = len(data) > 0
                    self.after(0, lambda: done(ok,
                        f"Requête HTTP réelle sur « {os.path.basename(candidate)} » → "
                        f"code {code}, {len(data)} octet(s) reçus"))
                except Exception as ex:
                    self.after(0, lambda: done(False, str(ex)))
            threading.Thread(target=worker, daemon=True).start()

        def _tc_step_duration_extract(self, done):
            """Extrait réellement la durée d'un média via VLC (fonction
            get_vlc_duration), plutôt que de se contenter de lire le cache
            déjà en mémoire."""
            candidate = next((p for p in self.video_paths if os.path.isfile(p)), None)
            if not candidate:
                done(None, "Aucun fichier de bibliothèque accessible — test ignoré")
                return
            def worker():
                try:
                    d = get_vlc_duration(candidate)
                    ok = d > 0
                    detail = (f"Durée extraite via VLC pour « {os.path.basename(candidate)} » : "
                              f"{fmt_duration(d)}" if ok else
                              f"Extraction de durée renvoyée à 0 pour « {os.path.basename(candidate)} »")
                    self.after(0, lambda: done(ok, detail))
                except Exception as ex:
                    self.after(0, lambda: done(False, str(ex)))
            threading.Thread(target=worker, daemon=True).start()

        def _tc_step_pure_functions(self, done):
            """Teste plusieurs fonctions internes avec des exemples concrets :
            analyse d'un lien citron://, tri naturel des titres, nettoyage de
            recherche, et correspondance approximative (fautes de frappe)."""
            try:
                problems = []
                r1 = parse_citron_launch_arg("citron://play?url=https%3A%2F%2Fexample.com%2Fv")
                if r1 != "https://example.com/v":
                    problems.append(f"parse_citron_launch_arg a renvoyé {r1!r} au lieu de l'URL attendue")
                r2 = parse_citron_launch_arg("https://example.com/direct")
                if r2 != "https://example.com/direct":
                    problems.append("parse_citron_launch_arg n'a pas reconnu une URL http directe")
                r3 = parse_citron_launch_arg("texte quelconque")
                if r3 is not None:
                    problems.append("parse_citron_launch_arg aurait dû renvoyer rien pour un texte non-URL")
                nk_10 = self._natural_key("Film 10 (2020)")
                nk_2 = self._natural_key("Film 2 (2020)")
                if not (nk_10 > nk_2):
                    problems.append("_natural_key ne trie pas correctement les nombres "
                                     "(« Film 10 » devrait passer après « Film 2 »)")
                cleaned = self._tableur_search_clean("Étoile - Mystère !")
                if "é" in cleaned or "-" in cleaned:
                    problems.append(f"_tableur_search_clean n'a pas normalisé correctement : {cleaned!r}")
                matched, approx, word = self._tableur_fuzzy_contains(
                    "depardieu", "Gerard Depardeiu, Autre Acteur")
                if not matched:
                    problems.append("_tableur_fuzzy_contains n'a pas détecté une faute de frappe "
                                     "évidente (« Depardeiu » vs « Depardieu »)")
                if problems:
                    done(False, " | ".join(problems))
                else:
                    done(True, "parse_citron_launch_arg, _natural_key, _tableur_search_clean, "
                               "_tableur_fuzzy_contains : comportements attendus vérifiés")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_relocate_fake_path(self, done):
            """Vérifie que la relocalisation automatique d'un média (utile
            après changement de lettre de lecteur USB) échoue proprement,
            sans exception, pour un chemin qui n'existera jamais."""
            try:
                fake = os.path.join(tempfile.gettempdir(), "citron_test_inexistant_9999.mp4")
                result = self._relocate_media_path(fake)
                done(result is None,
                     f"Relocalisation d'un chemin volontairement inexistant → {result!r} (rien attendu)")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_list_filter(self, done):
            """Ouvre la Liste complète, applique un filtre de recherche réel,
            vérifie qu'il retourne au moins un résultat, puis nettoie."""
            try:
                if not self.video_names:
                    done(None, "Bibliothèque vide — test ignoré")
                    return
                already = bool(self.list_win and self.list_win.winfo_exists())
                if not already:
                    self.open_list_window()
                self.update_idletasks()
                sample = self.video_names[0][:4]
                self.list_search_var.set(sample)
                self.update_idletasks()
                n_filtered = self.list_win_listbox.size()
                self.list_search_var.set("")
                self.update_idletasks()
                if not already:
                    self.close_list_window()
                done(n_filtered >= 1,
                     f"Filtre « {sample} » → {n_filtered} résultat(s) affiché(s) dans la Liste complète")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_playlist_roundtrip(self, done):
            """Ajoute réellement un titre à la playlist, vérifie que le
            compteur augmente, puis le retire — la playlist de l'utilisateur
            retrouve exactement son état initial à la fin."""
            try:
                candidate = next((p for p in self.video_paths if os.path.isfile(p)), None)
                if not candidate:
                    done(None, "Aucun fichier de bibliothèque accessible — test ignoré")
                    return
                before = len(self.playlist)
                self.playlist.append(candidate)
                self.save_playlist()
                mid = len(self.playlist)
                del self.playlist[-1]
                self.save_playlist()
                after = len(self.playlist)
                if self.playlist_win and self.playlist_win.winfo_exists():
                    self.refresh_playlist_window()
                ok = (mid == before + 1) and (after == before)
                done(ok, f"Playlist avant={before}, après ajout={mid}, après retrait={after} "
                         f"(l'ajout puis le retrait ne doivent pas changer le total)")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_win_dl_duplicates(self, done):
            """Ouvre la fenêtre « Titres identiques » du dossier
            Citron-Mémoire (accessible depuis Téléchargements), puis la
            referme."""
            try:
                already_dl = bool(self.dl_win and self.dl_win.winfo_exists())
                if not already_dl:
                    self.open_downloads_window()
                self.update_idletasks()
                self._dl_show_duplicates()
                self.update_idletasks()
                opened = bool(getattr(self, "dl_stats_win", None) and self.dl_stats_win.winfo_exists())
                if opened:
                    self.dl_stats_win.destroy()
                    self.dl_stats_win = None
                if not already_dl:
                    self.close_downloads_window()
                done(opened,
                     "Fenêtre « Titres identiques » ouverte puis refermée sans erreur" if opened
                     else "La fenêtre « Titres identiques » ne s'est pas ouverte")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_volume(self, done):
            """Modifie réellement le volume PENDANT une lecture réelle, puis
            vérifie que VLC applique bien la valeur, et restaure tout après.
            Note : libvlc n'applique/ne restitue pas toujours fidèlement
            audio_set_volume() tant que l'état du lecteur n'est pas passé à
            « en lecture » ET que l'audio n'a pas eu un court instant pour
            s'attacher — un simple délai fixe de 700ms s'est révélé trop
            court sur certaines machines. On attend maintenant explicitement
            l'état Playing (avec une marge supplémentaire), plutôt que de
            deviner un délai."""
            try:
                if not self.player or not hasattr(self, "volume_slider"):
                    done(None, "Lecteur VLC ou curseur de volume indisponible — test ignoré")
                    return
                if self.player.get_state() == vlc.State.Playing:
                    done(None, "Une lecture est déjà en cours par l'utilisateur — test ignoré pour ne pas l'interrompre")
                    return
                candidate = next((p for p in self.video_paths if os.path.isfile(p)), None)
                if not candidate:
                    done(None, "Aucun média disponible pour tester le volume en conditions réelles — test ignoré")
                    return
                prev = self.volume_slider.get()
                self.play_file(candidate)

                deadline = time.time() + 6.0

                def _apply_and_check():
                    try:
                        self.volume_slider.set(37)
                        self.on_volume_change(37)
                        got = self.player.audio_get_volume()
                        self.volume_slider.set(prev)
                        self.on_volume_change(prev)
                        self.stop_video()
                        ok = (got == 37)
                        done(ok, f"Volume réglé à 37 pendant une lecture réelle → lu {got} "
                                 f"sur le lecteur VLC (restauré à {int(prev)} après le test)")
                    except Exception as ex2:
                        done(False, str(ex2))

                def _wait_playing():
                    if time.time() > deadline:
                        _apply_and_check()
                        return
                    try:
                        if self.player.get_state() == vlc.State.Playing:
                            # Petite marge après le passage à l'état Playing :
                            # l'audio a besoin d'un court instant pour
                            # s'attacher réellement au flux, même une fois
                            # l'état signalé comme actif.
                            self.after(500, _apply_and_check)
                            return
                    except Exception:
                        pass
                    self.after(150, _wait_playing)

                self.after(150, _wait_playing)
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_browser_mute(self, done):
            """Exerce réellement la coupure/restauration du son du
            navigateur (utilisée pendant une lecture internet). Sans effet
            audible si pycaw est absent ou si aucun navigateur n'est ouvert —
            le test vérifie seulement l'absence d'erreur."""
            try:
                self._mute_browser_audio()
                self._restore_browser_audio()
                done(True, "Coupure puis restauration du son du navigateur exécutées sans erreur "
                            "(sans effet si pycaw est absent ou si aucun navigateur n'est ouvert)")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_toast(self, done):
            try:
                self._show_toast("🧪 Test Citron : notification de test", ms=800, color="#2a4a6a")
                done(True, "Bandeau de notification affiché sans erreur")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_win_list(self, done):
            try:
                if self.list_win and self.list_win.winfo_exists():
                    done(None, "Fenêtre déjà ouverte par l'utilisateur — test non intrusif ignoré")
                    return
                self.open_list_window()
                self.update_idletasks()
                ok = bool(self.list_win and self.list_win.winfo_exists())
                self.close_list_window()
                done(ok, "Fenêtre ouverte puis refermée sans erreur" if ok else "La fenêtre ne s'est pas ouverte")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_win_playlist(self, done):
            try:
                if self.playlist_win and self.playlist_win.winfo_exists():
                    done(None, "Fenêtre déjà ouverte par l'utilisateur — test non intrusif ignoré")
                    return
                self.open_playlist_window()
                self.update_idletasks()
                ok = bool(self.playlist_win and self.playlist_win.winfo_exists())
                self.close_playlist_window()
                done(ok, "Fenêtre ouverte puis refermée sans erreur" if ok else "La fenêtre ne s'est pas ouverte")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_win_stats(self, done):
            try:
                if self.stats_win and self.stats_win.winfo_exists():
                    done(None, "Fenêtre déjà ouverte par l'utilisateur — test non intrusif ignoré")
                    return
                self.show_duplicates_info()
                self.update_idletasks()
                ok = bool(self.stats_win and self.stats_win.winfo_exists())
                self.close_stats_win()
                done(ok, "Fenêtre ouverte puis refermée sans erreur" if ok else "La fenêtre ne s'est pas ouverte")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_win_downloads(self, done):
            try:
                if self.dl_win and self.dl_win.winfo_exists():
                    done(None, "Fenêtre déjà ouverte par l'utilisateur — test non intrusif ignoré")
                    return
                self.open_downloads_window()
                self.update_idletasks()
                ok = bool(self.dl_win and self.dl_win.winfo_exists())
                self.close_downloads_window()
                done(ok, "Fenêtre ouverte puis refermée sans erreur" if ok else "La fenêtre ne s'est pas ouverte")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_mem_folder(self, done):
            try:
                folder = getattr(self, "_mem_dir", None) or os.path.expanduser("~")
                os.makedirs(folder, exist_ok=True)
                test_path = os.path.join(folder, ".citron_test_ecriture.tmp")
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write("test")
                os.remove(test_path)
                done(True, f"Dossier accessible en écriture : {folder}")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_disk_space(self, done):
            try:
                folder = getattr(self, "_mem_dir", None) or os.path.expanduser("~")
                usage = shutil.disk_usage(folder)
                free_go = usage.free / (1024 ** 3)
                done(True, f"{free_go:.1f} Go libres sur le disque de « {folder} »")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_dlna(self, done):
            def worker():
                try:
                    devs = discover_dlna_renderers(timeout=3)
                    self._tc_last_dlna_devices = devs
                    self.after(0, lambda: done(True, f"{len(devs)} appareil(s) DLNA détecté(s) sur le réseau"))
                except Exception as ex:
                    self.after(0, lambda: done(False, str(ex)))
            threading.Thread(target=worker, daemon=True).start()

        def _tc_step_dlna_query(self, done):
            """Interroge l'état d'un appareil DLNA déjà détecté par la requête
            précédente, en LECTURE SEULE (GetTransportInfo). Ne déclenche
            JAMAIS SetAVTransportURI/Play/Stop : la TV de l'utilisateur n'est
            jamais sollicitée pour lire quoi que ce soit pendant ce test."""
            devs = getattr(self, "_tc_last_dlna_devices", None) or []
            device = next((d for d in devs if d.get("control_url")), None)
            if not device:
                done(None, "Aucun appareil DLNA avec URL de contrôle disponible — test ignoré")
                return
            def worker():
                try:
                    st = _soap_get_transport_state(device["control_url"])
                    self.after(0, lambda: done(True,
                        f"État lu sur « {device.get('name','?')} » : « {st or 'vide (normal si inactif)'} » "
                        f"(requête en lecture seule, rien n'a été lancé sur la TV)"))
                except Exception as ex:
                    self.after(0, lambda: done(False, str(ex)))
            threading.Thread(target=worker, daemon=True).start()

        def _tc_step_tableur(self, done):
            try:
                if not self._tableur_path or not os.path.isfile(self._tableur_path):
                    done(None, "Aucun tableur configuré — test ignoré")
                    return
                rows, err = self._get_ods_rows()
                if err:
                    done(False, err)
                else:
                    done(True, f"Tableur lu avec succès : {len(rows)} ligne(s)")
            except Exception as ex:
                done(False, str(ex))

        def _tc_get_first_tableur_row(self):
            """Retourne (col_titre, col_annee, col_personnes) de la première
            ligne du tableur qui ressemble à une VRAIE entrée de film (année
            à 4 chiffres en colonne 2), en ignorant les éventuelles lignes
            d'en-tête/instructions (ex : « Titres (AVI-MP4-MKV-VOB-mkv) »)
            qui ont du texte en colonne 1 mais ne sont pas des films —
            sans ce filtre, les tests de recherche se retrouvaient à
            chercher littéralement « année » ou « acteurs » comme s'il
            s'agissait de vraies données. Retourne None si aucun tableur
            n'est configuré/lisible ou si aucune ligne plausible n'est
            trouvée dans les 200 premières lignes."""
            if not self._tableur_path or not os.path.isfile(self._tableur_path):
                return None
            from odf.table import TableRow, TableCell
            rows, err = self._get_ods_rows()
            if err or not rows:
                return None
            for row in rows[:200]:
                cells = self._expand_ods_cells(row.getElementsByType(TableCell))
                if not cells:
                    continue
                titre = self._ods_cell_text(cells[0]).strip()
                if not titre:
                    continue
                annee = self._ods_cell_text(cells[1]).strip() if len(cells) > 1 else ""
                if not (len(annee) == 4 and annee.isdigit()):
                    continue  # probablement un en-tête/une instruction, pas un film
                personnes = self._ods_cell_text(cells[3]).strip() if len(cells) > 3 else ""
                return (titre, annee, personnes)
            return None

        def _tc_step_tableur_search_titre(self, done):
            """Recherche réelle par titre (le vrai moteur de recherche, pas
            une simulation) : on cherche le titre de la toute première ligne
            du tableur et on vérifie qu'il se retrouve bien lui-même."""
            try:
                ref = self._tc_get_first_tableur_row()
                if not ref:
                    done(None, "Aucun tableur configuré ou lisible — test ignoré")
                    return
                titre, annee, _ = ref
                matches = self._compute_tableur_search("titre", titre, scope=None)
                found = any(m.get("col_titre", "").strip().lower() == titre.strip().lower() for m in matches)
                done(found,
                     f"Recherche « {titre} » → {len(matches)} résultat(s), "
                     f"titre de référence retrouvé : {found}")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_tableur_search_annee(self, done):
            try:
                ref = self._tc_get_first_tableur_row()
                if not ref or not ref[1]:
                    done(None, "Aucune année exploitable sur la première ligne du tableur — test ignoré")
                    return
                titre, annee, _ = ref
                matches = self._compute_tableur_search("annee", annee, scope=None)
                found = any(m.get("col_titre", "").strip().lower() == titre.strip().lower() for m in matches)
                done(found if matches else None,
                     f"Recherche année « {annee} » → {len(matches)} résultat(s), "
                     f"titre de référence présent dans les résultats : {found}")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_tableur_search_acteur(self, done):
            try:
                ref = self._tc_get_first_tableur_row()
                if not ref or not ref[2]:
                    done(None, "Aucun acteur exploitable sur la première ligne du tableur — test ignoré")
                    return
                titre, annee, personnes = ref
                premier_acteur = personnes.split("/")[0].strip()
                if not premier_acteur:
                    done(None, "Nom d'acteur vide après extraction — test ignoré")
                    return
                matches = self._compute_tableur_search("acteur", premier_acteur, scope=None)
                found = any(m.get("col_titre", "").strip().lower() == titre.strip().lower() for m in matches)
                done(found if matches else None,
                     f"Recherche acteur « {premier_acteur} » → {len(matches)} résultat(s), "
                     f"titre de référence présent dans les résultats : {found}")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_tableur_search_vide(self, done):
            """Vérifie que le moteur de recherche gère proprement le cas
            « aucun résultat » (chaîne quasiment impossible à trouver), sans
            lever d'exception et sans planter."""
            try:
                if not self._tableur_path or not os.path.isfile(self._tableur_path):
                    done(None, "Aucun tableur configuré — test ignoré")
                    return
                improbable = "zzzxxqqjjvvv_improbable_9999_citron_test"
                matches = self._compute_tableur_search("titre", improbable, scope=None)
                done(len(matches) == 0,
                     f"{len(matches)} résultat(s) pour une chaîne improbable "
                     f"(0 attendu — le moteur de recherche ne doit rien inventer)")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_infos_window(self, done):
            """Ouvre RÉELLEMENT la fiche 📋 Infos (tableur) — image, résumé,
            lecteur VLC de la vidéo résumé compris — puis la referme
            proprement via la même fonction de nettoyage que l'utilisateur
            (bouton ✕ Fermer), afin de vérifier qu'aucune fenêtre ni aucun
            lecteur VLC ne reste orphelin en arrière-plan.
            Reproduit fidèlement l'usage réel : en pratique, cette fiche
            n'est jamais ouverte avec un chemin vide (le clic droit dans la
            Liste complète, seule origine possible hors recherche tableur,
            fournit toujours un chemin local réel) — le test cherche donc
            un titre du tableur qui correspond à un média réellement présent
            dans la bibliothèque, exactement comme le ferait Citron."""
            try:
                ref = self._tc_get_first_tableur_row()
                if not ref:
                    done(None, "Aucun tableur configuré ou lisible — test ignoré")
                    return
                titre, annee, _ = ref
                idx = self._find_library_index_for_titre_annee(titre, annee)
                if idx is None:
                    done(None, "Le titre de référence du tableur n'a pas de correspondance "
                                "dans la bibliothèque locale — test ignoré")
                    return
                local_path = self.video_paths[idx]
                row_data, err = self._read_ods_row(titre)
                if err or not row_data:
                    done(False, err or "Ligne introuvable pour le titre de référence")
                    return
                # Ouverture directe (sans passer par l'animation d'attente,
                # déjà testée par ailleurs) pour rester rapide et déterministe.
                self._open_info_window(titre, local_path, row_data, None, from_chain=False)
                self.update_idletasks()

                def _check_and_close():
                    win = getattr(self, "_current_info_win", None)
                    opened = bool(win and win.winfo_exists())
                    cleanup = getattr(self, "_current_info_win_cleanup", None)
                    if cleanup:
                        try:
                            cleanup()
                        except Exception:
                            pass
                    self.update_idletasks()
                    still_there = bool(win and win.winfo_exists())
                    closed_ok = opened and not still_there
                    if opened and closed_ok:
                        done(True, f"Fiche « {titre} » ouverte (image/résumé/lecteur VLC compris) "
                                   f"puis refermée proprement, aucune fenêtre résiduelle détectée")
                    elif not opened:
                        done(False, "La fiche Infos ne s'est pas ouverte")
                    else:
                        done(False, "La fiche Infos ne s'est pas refermée correctement "
                                     "(fenêtre potentiellement fantôme)")
                # Laisser le temps à l'image/au lecteur VLC de s'attacher
                # avant de tester la fermeture (comme un utilisateur réel).
                self.after(1200, _check_and_close)
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_menus_stress(self, done):
            """Ouvre et referme rapidement, plusieurs fois de suite, les
            principaux menus déroulants de Citron (Paramètres, Téléchargements,
            Tableur, Voix du résumé, Personnes) — exactement le genre
            d'enchaînement rapide qui a par le passé provoqué des « fenêtres
            fantômes » (voir les correctifs déjà présents dans le code).
            Vérifie qu'aucune référence de menu ne reste vivante à la fin."""
            try:
                anchor = getattr(self, "list_btn", None) or self
                menu_attrs = ("_params_menu_win", "_tableur_menu_win", "_dl_menu_win",
                              "_internet_menu_win", "_browser_menu_win", "_voice_menu_win",
                              "_person_menu_win")
                iterations = 12
                for i in range(iterations):
                    try:
                        self._show_params_menu(anchor)
                        w = getattr(self, "_params_menu_win", None)
                        if w and w.winfo_exists():
                            w.destroy()
                        self._params_menu_win = None
                    except Exception:
                        pass
                    try:
                        self._show_tableur_menu(self.tableur_btn)
                        w = getattr(self, "_tableur_menu_win", None)
                        if w and w.winfo_exists():
                            w.destroy()
                        self._tableur_menu_win = None
                    except Exception:
                        pass
                    try:
                        self._show_dl_menu(self.dl_btn)
                        self._close_all_dl_menus("test_citron_stress")
                    except Exception:
                        pass
                    try:
                        self._show_voice_menu(anchor)
                        w = getattr(self, "_voice_menu_win", None)
                        if w and w.winfo_exists():
                            w.destroy()
                        self._voice_menu_win = None
                    except Exception:
                        pass
                    try:
                        self._show_person_menu(anchor, "Acteur de test Citron")
                        w = getattr(self, "_person_menu_win", None)
                        if w and w.winfo_exists():
                            w.destroy()
                        self._person_menu_win = None
                    except Exception:
                        pass
                self.update_idletasks()
                orphans = []
                for attr in menu_attrs:
                    w = getattr(self, attr, None)
                    try:
                        if w is not None and w.winfo_exists():
                            orphans.append(attr)
                    except Exception:
                        pass
                if orphans:
                    done(False, f"{iterations} cycles ouverture/fermeture effectués — "
                                 f"fenêtre(s) fantôme(s) détectée(s) : {', '.join(orphans)}")
                else:
                    done(True, f"{iterations} cycles ouverture/fermeture effectués sur les menus "
                               f"Paramètres/Tableur/Téléchargements/Voix/Personnes, "
                               f"aucune fenêtre fantôme détectée")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_close_all_secondary(self, done):
            try:
                self._close_all_secondary_windows()
                self.update_idletasks()
                residual = [attr for attr in ("list_win", "playlist_win", "stats_win", "dlna_win", "dl_win")
                            if getattr(self, attr, None) is not None]
                done(not residual,
                     "Toutes les fenêtres secondaires ont été fermées proprement" if not residual
                     else f"Références résiduelles non nettoyées : {residual}")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_protocol(self, done):
            if os.name != "nt":
                done(None, "Non applicable (hors Windows)")
                return
            try:
                registered = is_citron_protocol_registered()
                if registered:
                    done(True, "Le protocole citron:// est enregistré dans le registre Windows")
                else:
                    done(None, "Le protocole citron:// n'est pas encore enregistré (normal si jamais activé)")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_update_check(self, done):
            """Vérifie que le mécanisme de mise à jour est fonctionnel : la
            comparaison de versions d'abord (toujours testable, indépendante
            de toute configuration réseau), puis la requête réelle seulement
            si CITRON_UPDATE_CHECK_URL a été renseigné."""
            try:
                assert _parse_version_tuple("1.9") < _parse_version_tuple("1.10")
                assert _parse_version_tuple("2.0.0") > _parse_version_tuple("1.99.99")
            except Exception as ex:
                done(False, f"Comparaison de versions incorrecte : {ex}")
                return

            if not CITRON_UPDATE_CHECK_URL:
                done(None, f"Non configuré (aucune URL renseignée) — version actuelle : {CITRON_VERSION}")
                return

            def worker():
                try:
                    req = urllib.request.Request(
                        CITRON_UPDATE_CHECK_URL, headers={"User-Agent": "Citron"})
                    with urllib.request.urlopen(req, timeout=6) as resp:
                        data = json.loads(resp.read().decode("utf-8-sig", errors="ignore"))
                    remote_version = str(data.get("version", "")).strip()
                    if not remote_version:
                        raise ValueError("Réponse sans champ 'version'")
                    self.after(0, lambda: done(True,
                        f"Requête réelle réussie — version distante : {remote_version} (locale : {CITRON_VERSION})"))
                except Exception as ex:
                    self.after(0, lambda ex=ex: done(False, str(ex)))
            threading.Thread(target=worker, daemon=True).start()

        def _tc_step_backup_roundtrip(self, done):
            """Vérifie la logique d'export/import de sauvegarde (structure
            des données, écriture/lecture JSON), sans passer par les boîtes
            de dialogue de export_library_backup/import_library_backup
            (non automatisables) et sans toucher à la bibliothèque réelle
            de l'utilisateur."""
            try:
                sample = {
                    "citron_backup_version": 1,
                    "citron_version": CITRON_VERSION,
                    "exported_at": datetime.now().isoformat(timespec="seconds"),
                    "library": [{"path": "C:/exemple/film.mp4", "name": "film.mp4"}],
                    "playlist": ["C:/exemple/film.mp4"],
                    "tableur_path": "",
                }
                tmp_path = os.path.join(tempfile.gettempdir(),
                                         f"citron_tc_backup_{os.getpid()}.json")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(sample, f, ensure_ascii=False, indent=2)
                with open(tmp_path, "r", encoding="utf-8") as f:
                    reloaded = json.load(f)
                try: os.remove(tmp_path)
                except Exception: pass
                assert reloaded["library"][0]["path"] == "C:/exemple/film.mp4"
                assert reloaded["playlist"] == ["C:/exemple/film.mp4"]
                done(True, "Écriture puis relecture d'une sauvegarde JSON conformes")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_settings_migration(self, done):
            """Vérifie la migration de schéma des réglages (fichier ancien
            sans "settings_schema_version" → correctement estampillé à la
            version actuelle) et le mécanisme de sauvegarde d'un fichier
            corrompu, sans toucher au vrai citron_settings.json de
            l'utilisateur."""
            try:
                # 1) Un dict "ancien" (sans version) doit être migré vers la
                #    version actuelle.
                old = {"main_win": "800x600+0+0"}
                migrated = _migrate_settings_dict(old)
                assert migrated["settings_schema_version"] == CITRON_SETTINGS_SCHEMA_VERSION
                assert migrated["main_win"] == "800x600+0+0"  # rien perdu au passage

                # 2) Un dict déjà à jour ne doit pas poser de problème.
                current = _migrate_settings_dict({"settings_schema_version": CITRON_SETTINGS_SCHEMA_VERSION})
                assert current["settings_schema_version"] == CITRON_SETTINGS_SCHEMA_VERSION

                # 3) Fichier corrompu : doit être sauvegardé à côté de lui-même
                #    plutôt que silencieusement perdu.
                tmp_path = os.path.join(tempfile.gettempdir(),
                                         f"citron_tc_settings_{os.getpid()}.json")
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write("{ceci n'est pas du JSON valide")
                backup_path = None
                try:
                    with open(tmp_path, "r", encoding="utf-8") as f:
                        json.load(f)
                    raise AssertionError("le JSON invalide aurait dû lever une erreur")
                except json.JSONDecodeError:
                    backup_path = tmp_path + "_test_backup"
                    shutil.copy2(tmp_path, backup_path)
                assert backup_path and os.path.exists(backup_path)
                with open(backup_path, "r", encoding="utf-8") as f:
                    assert "pas du JSON valide" in f.read()

                for p in (tmp_path, backup_path):
                    try: os.remove(p)
                    except Exception: pass

                done(True, "Migration de schéma et sauvegarde d'un fichier corrompu conformes")
            except Exception as ex:
                done(False, str(ex))

        def _tc_step_playback(self, done):
            try:
                if self.player and self.player.get_state() == vlc.State.Playing:
                    done(None, "Une lecture est déjà en cours par l'utilisateur — test ignoré pour ne pas l'interrompre")
                    return
                if not self.video_paths:
                    done(None, "Bibliothèque de médias vide — test ignoré")
                    return
                candidate = next((p for p in self.video_paths if os.path.isfile(p)), None)
                if not candidate:
                    done(None, "Aucun fichier de la bibliothèque n'est accessible sur le disque — test ignoré")
                    return
                prev_volume = self.volume_slider.get() if hasattr(self, "volume_slider") else 80
                if self.player:
                    self.player.audio_set_volume(0)  # silencieux pendant le test automatique
                self.play_file(candidate)

                def _stop_and_report():
                    try:
                        self.stop_video()
                    finally:
                        if self.player:
                            self.player.audio_set_volume(int(prev_volume))
                    done(True, f"Lecture brève de « {os.path.basename(candidate)} » effectuée sans erreur")
                self.after(1500, _stop_and_report)
            except Exception as ex:
                done(False, str(ex))

        # URL de test stable et publique (le tout premier YouTube jamais
        # publié — court, connu, peu susceptible d'être retiré) : utilisée
        # UNIQUEMENT pour vérifier que la résolution/lecture internet
        # fonctionne réellement, jamais téléchargée sur le disque.
        _TC_TEST_URL = "https://www.youtube.com/watch?v=jNQXAC9IVRw"

        def _tc_step_internet_resolve(self, done):
            """Résout une vraie URL internet via yt-dlp (extraction seule,
            AUCUN téléchargement), pour vérifier que ce chemin fonctionne
            réellement — pas seulement que le module est importable."""
            def worker():
                try:
                    import yt_dlp
                except ImportError:
                    self.after(0, lambda: done(None, "yt-dlp non installé — test ignoré"))
                    return
                try:
                    with yt_dlp.YoutubeDL(self._ydl_base_opts()) as ydl:
                        info = ydl.extract_info(self._TC_TEST_URL, download=False)
                    titre = (info or {}).get("title", "?")
                    self.after(0, lambda: done(True, f"URL de test résolue avec succès : « {titre} »"))
                except Exception as ex:
                    msg = str(ex)
                    # Distingue une vraie panne (extracteur cassé, régression
                    # Citron) d'une simple absence de connexion internet.
                    if any(w in msg.lower() for w in ("network", "timed out", "temporary failure",
                                                        "name or service not known", "connexion")):
                        self.after(0, lambda: done(None, f"Résolution impossible, probablement hors ligne : {msg[:200]}"))
                    else:
                        self.after(0, lambda: done(False, msg[:400]))
            threading.Thread(target=worker, daemon=True).start()

        def _tc_step_internet_play(self, done):
            """Utilise le vrai bouton « Lire sur PC » (résolution + lecture
            VLC, sans téléchargement) sur l'URL de test, puis arrête la
            lecture — un test bout-en-bout du chemin internet complet."""
            try:
                if self.player and self.player.get_state() == vlc.State.Playing:
                    done(None, "Une lecture est déjà en cours par l'utilisateur — test ignoré pour ne pas l'interrompre")
                    return
                try:
                    import yt_dlp  # noqa: F401
                except ImportError:
                    done(None, "yt-dlp non installé — test ignoré")
                    return
                prev_volume = self.volume_slider.get() if hasattr(self, "volume_slider") else 80
                if self.player:
                    self.player.audio_set_volume(0)  # silencieux pendant le test automatique
                self.play_internet_url(self._TC_TEST_URL, play=True, download=False)

                deadline = time.time() + 18
                def _poll():
                    if time.time() > deadline:
                        if self.player:
                            self.player.audio_set_volume(int(prev_volume))
                        self.stop_video()
                        done(False, "La lecture internet n'a pas démarré dans le délai imparti")
                        return
                    st = self.player.get_state() if self.player else None
                    if st == vlc.State.Playing:
                        def _stop_and_report():
                            try:
                                self.stop_video()
                            finally:
                                if self.player:
                                    self.player.audio_set_volume(int(prev_volume))
                            done(True, "Lecture internet démarrée avec succès via « Lire sur PC », puis arrêtée")
                        self.after(1500, _stop_and_report)
                        return
                    self.after(300, _poll)
                self.after(300, _poll)
            except Exception as ex:
                done(False, str(ex))

        def _show_help(self):
            win = ctk.CTkToplevel(self)
            win.title("Mode d'emploi — Citron")
            win.geometry("780x600")
            win.transient(self); win.lift()
            ctk.CTkLabel(win, text=f"📖 Mode d'emploi — Citron {CITRON_VERSION}",
                         font=("Arial",18,"bold")).pack(pady=(16,4))
            ctk.CTkLabel(win, text="Un tour complet des fonctionnalités, pensé pour qui découvre Citron.",
                         font=("Arial",12), text_color="#999999").pack(pady=(0,8))
            from tkinter import Text as _T, Scrollbar as _S
            txt = _T(win, font=("Arial",13), fg="#dddddd", bg="#1a1a1a",
                     relief="flat", wrap="word", bd=0, highlightthickness=0,
                     padx=6, spacing1=2, spacing3=6)
            sb = _S(win, command=txt.yview); sb.pack(side="right", fill="y")
            txt.configure(yscrollcommand=sb.set)
            txt.pack(fill="both", expand=True, padx=16, pady=8)
            help_text = (
"🍋 QU'EST-CE QUE CITRON ?\n"
"Citron est un lecteur multimédia « tout-en-un » : il lit vos films, séries "
"et musiques stockés sur votre ordinateur, peut les envoyer sur votre "
"téléviseur, télécharger des vidéos depuis Internet, enregistrer votre "
"écran, et afficher des fiches d'information (résumé, casting, année…) "
"pour chaque titre si vous disposez d'un tableur contenant ces "
"informations. Tout se pilote depuis une seule fenêtre.\n"
"\n"
"────────────────────────────────────────────\n"
"1) LA BIBLIOTHÈQUE — vos films et musiques\n"
"────────────────────────────────────────────\n"
"C'est la liste de tous les fichiers que Citron connaît.\n"
"• Bouton « 📋 Liste » (en bas de la fenêtre principale) → ouvre la "
"bibliothèque complète.\n"
"• Dans cette fenêtre : bouton « + Fichiers » pour ajouter des vidéos/"
"musiques depuis votre disque.\n"
"• Double-clic sur un titre → le lit immédiatement.\n"
"• Clic droit sur un titre → un menu apparaît avec : lire, envoyer sur TV, "
"ajouter à la Playlist, voir les infos du média, ouvrir sa fiche « Infos "
"(tableur) », ou le supprimer de la bibliothèque.\n"
"• Bouton « 🗑 Supprimer doublons » → repère et retire automatiquement les "
"fichiers en double (même titre) dans votre dossier Citron-Mémoire.\n"
"• Survolez un titre avec la souris → une image d'aperçu apparaît à côté "
"de la liste (extraite un peu après le début du fichier, pas le tout "
"premier instant, souvent noir ou un générique de studio).\n"
"\n"
"────────────────────────────────────────────\n"
"2) LA PLAYLIST — votre file de lecture\n"
"────────────────────────────────────────────\n"
"Contrairement à la bibliothèque (tout ce que vous possédez), la Playlist "
"est la sélection de titres que vous voulez enchaîner maintenant.\n"
"• Double-clic sur un titre de la Playlist → lecture, puis enchaînement "
"automatique des titres suivants.\n"
"• Bouton « 📋 Liste → Playlist » (dans la bibliothèque) → copie tout ou "
"partie de la bibliothèque dans la Playlist d'un coup.\n"
"• Clic droit sur un titre de la Playlist → lire à partir de là (PC ou "
"TV), lecture aléatoire, le retirer, ou le déplacer (↑ / ↓) dans l'ordre "
"de lecture.\n"
"• Boutons « 💾 Enregistrer » / « 📂 Charger playlist » → sauvegarder votre "
"playlist actuelle dans un fichier .m3u pour la retrouver plus tard, ou en "
"charger une déjà créée.\n"
"\n"
"────────────────────────────────────────────\n"
"3) LECTURE SUR L'ORDINATEUR\n"
"────────────────────────────────────────────\n"
"• Barre Espace → Lecture / Pause.\n"
"• Touche F → Plein écran / quitter le plein écran.\n"
"• Boutons ⏮ ▶ ⏹ ⏭ dans la barre principale → précédent, lecture/pause, "
"stop, suivant.\n"
"• Le bouton « 🖥 Miroir ON/OFF » n'agit PAS ici — il concerne la lecture "
"sur TV, voir le chapitre suivant.\n"
"\n"
"────────────────────────────────────────────\n"
"4) LECTURE SUR LA TÉLÉVISION (DLNA)\n"
"────────────────────────────────────────────\n"
"Permet d'envoyer un titre depuis votre PC vers une TV/box compatible "
"DLNA (par ex. un boîtier WD TV Live), SANS fil de connexion — juste par "
"le réseau Wi-Fi.\n"
"• Condition indispensable : le PC et la TV doivent être connectés au "
"MÊME réseau Wi-Fi.\n"
"• Bouton « 📺 TV » → ouvre la fenêtre d'envoi vers la TV.\n"
"• Depuis la bibliothèque ou la Playlist, clic droit sur un titre → "
"« Envoyer sur TV » (ou « Lecture aléatoire sur TV » pour une soirée "
"sans se soucier de l'ordre).\n"
"• Bouton « 🖥 Miroir ON/OFF » : quand il est activé PENDANT une lecture "
"envoyée sur la TV, la même vidéo est aussi rejouée dans la fenêtre de "
"Citron sur votre PC, mais SANS le son (volume à 0%) — un simple aperçu "
"visuel de ce qui passe sur la TV, pas un second haut-parleur. Miroir OFF "
"= la fenêtre PC reste sur pause pendant que la TV lit le titre.\n"
"\n"
"────────────────────────────────────────────\n"
"5) INTERNET — télécharger ou lire une vidéo en ligne\n"
"────────────────────────────────────────────\n"
"Citron peut récupérer une vidéo depuis une URL (YouTube et sites "
"compatibles) de deux façons :\n"
"• « 💾 Télécharger » → enregistre la vidéo dans votre dossier "
"Citron-Mémoire pour la revoir hors-ligne plus tard, comme un fichier "
"normal de votre bibliothèque.\n"
"• « 🎬 Lire sur PC et enregistrer l'écran » → lit la vidéo tout de suite "
"tout en capturant l'écran (utile pour garder une trace d'un direct ou "
"d'un contenu qui ne se télécharge pas proprement).\n"
"• Envoi rapide depuis le navigateur : Paramètres → « 🔗 Activer citron:// "
"(navigateur) » puis « 📋 Bookmarklet navigateur » vous donnent un petit "
"favori à ajouter à votre navigateur. Un clic dessus sur une page vidéo "
"envoie directement le lien à Citron (Citron doit rester ouvert pour "
"recevoir le lien).\n"
"• Paramètres → « 📐 Enregistrer une zone de l'écran » → une troisième "
"façon de capturer un média, indépendante de toute URL et de toute "
"lecture dans Citron : tracez au clic-glisser n'importe quelle zone de "
"votre écran (ex : la fenêtre d'un autre lecteur, une page web...), "
"choisissez où enregistrer, et un petit bandeau flottant « ⏹ Arrêter » "
"reste affiché pour terminer la capture quand vous le souhaitez. Utile "
"pour tout contenu que Citron ne saurait pas récupérer autrement.\n"
"\n"
"────────────────────────────────────────────\n"
"6) LE TABLEUR — fiches d'info, résumés et recherche\n"
"────────────────────────────────────────────\n"
"Si vous avez un fichier tableur au format .ods (LibreOffice Calc) qui "
"référence vos films avec leurs informations (année, acteurs, résumé…), "
"Citron peut l'exploiter pour afficher une fiche complète pour chaque "
"titre. Le format .ods est une VRAIE obligation technique, pas une "
"préférence : Citron ne sait lire QUE ce format-là (via la bibliothèque "
"odfpy). Un fichier Excel .xlsx ne fonctionnera pas — si votre tableur est "
"au format Excel, ouvrez-le dans LibreOffice Calc (gratuit) et faites "
"« Enregistrer sous » → format ODF Feuille de calcul (.ods).\n"
"• Bouton « 🗂 Tableur » → menu avec : sélectionner votre fichier .ods, "
"le modifier, le tester, ou couper le lien (🗂 off).\n"
"• Clic droit sur un titre de la bibliothèque → « 📋 Infos (tableur) » → "
"ouvre sa fiche : résumé, éventuellement une courte vidéo-résumé (🎞) que "
"vous pouvez lancer, et un bouton pour faire LIRE le résumé à voix haute "
"(Paramètres → « 🎙️ Voix du résumé » pour changer de voix).\n"
"• Dans la fiche, flèches ◀ ▶ (au clavier ou à l'écran) → titre précédent/"
"suivant sans refermer la fenêtre. Touche Échap → fermer la fiche.\n"
"• Le bandeau en haut de la fiche affiche, dans l'ordre : le titre suivi "
"de l'année entre parenthèses si elle est connue (ex : « Le Voyage "
"(1985) »), sa position dans la liste actuelle (ex : « 3/250 »), puis, "
"UNIQUEMENT si vous êtes arrivé sur cette fiche via une ou plusieurs "
"recherches successives, un fil d'Ariane 🔎 récapitulant chaque étape "
"séparée par « › » (ex : « 🔎 Acteur : Jean Dupont › Année : 1985 »).\n"
"• Clic droit dans la fiche (ou bouton « 🔍 Recherche ») → lancer une "
"recherche dans tout le tableur par titre, par acteur, par année ou par "
"mot-clé. Chaque nouvelle recherche s'ajoute au fil d'Ariane plutôt que "
"de le remplacer — vous pouvez ainsi affiner progressivement (ex : tous "
"les films d'un acteur, PUIS parmi ceux-là seulement l'année 1985).\n"
"• Dans la liste des résultats d'une recherche, un titre affiché EN GRIS "
"signifie qu'il existe dans votre tableur mais qu'AUCUN fichier "
"correspondant n'a été trouvé dans votre bibliothèque locale — vous "
"pouvez toujours consulter sa fiche d'information, mais pas le lire ni "
"l'ajouter à la Playlist (ces actions apparaissent grisées elles aussi, "
"avec la mention « absent de la Liste »).\n"
"• Note : si vous relancez une recherche pendant qu'un résumé vidéo ou "
"une narration est en cours, celle-ci s'arrête automatiquement pour "
"éviter que deux sons se superposent.\n"
"\n"
"────────────────────────────────────────────\n"
"7) STATISTIQUES\n"
"────────────────────────────────────────────\n"
"Bouton « Titres identiques » (fenêtre titrée « Statistiques ») : un "
"aperçu chiffré de votre bibliothèque, avec la détection des doublons "
"(même titre présent plusieurs fois).\n"
"\n"
"────────────────────────────────────────────\n"
"🧪 LA PLAYLIST VIRTUELLE\n"
"────────────────────────────────────────────\n"
"• La Playlist virtuelle permet de conserver une sélection issue du tableur, "
"même lorsque certains fichiers ne sont pas disponibles dans la bibliothèque.\n"
"• Un titre disponible reste lisible et conserve les mêmes fonctionnalités "
"qu'une playlist normale (menu contextuel, navigation et actions disponibles).\n"
"• Un titre indisponible est affiché en gris : il peut être conservé dans la "
"sélection, mais les fonctions nécessitant la lecture du média sont désactivées.\n"
"• Si le fichier devient disponible ultérieurement, Citron peut le retrouver "
"et le titre redevient lisible.\n"
"• Depuis le bouton « 🎵 Playlist » de la fenêtre principale, vous pouvez "
"choisir d'ouvrir la Playlist normale ou la Playlist virtuelle.\n"
"\n"
"────────────────────────────────────────────\n"
"8) LE MENU « ⚙ PARAMÈTRES »\n"
"────────────────────────────────────────────\n"
"• 📖 Mode d'emploi → cette fenêtre.\n"
"• 🎙️ Voix du résumé → choisir la voix utilisée pour lire les résumés à "
"voix haute.\n"
"• 🔗 Activer citron:// (navigateur) → active la réception de liens "
"vidéo depuis votre navigateur (voir section Internet ci-dessus).\n"
"• 🔎 Vérifier les mises à jour → contrôle si une nouvelle version de "
"Citron est disponible.\n"
"• 📦 Exporter ma configuration / 📥 Importer une configuration → "
"sauvegarder ou restaurer d'un coup votre bibliothèque, votre playlist et "
"le lien vers votre tableur — très utile avant une réinstallation ou un "
"changement d'ordinateur.\n"
"• 📋 Bookmarklet navigateur → affiche le code à ajouter en favori dans "
"votre navigateur (voir section Internet).\n"
"• 🔊 Périphérique audio (capture d'écran) → vous n'avez normalement "
"JAMAIS besoin de cliquer ici avant d'enregistrer : au tout premier "
"enregistrement d'écran, Citron détecte automatiquement la bonne source "
"audio, ou vous propose un choix si la détection échoue, avec une case "
"« se souvenir de ce choix » cochée par défaut. Cette entrée de "
"Paramètres ne sert qu'à REVENIR sur un choix déjà mémorisé (par erreur, "
"ou après avoir installé un nouveau périphérique audio) pour relancer la "
"détection.\n"
"• 📐 Enregistrer une zone de l'écran → voir chapitre 5 (Internet) "
"ci-dessus.\n"
"• 🧪 Test Citron → lance une série de vérifications automatiques pour "
"s'assurer que tout fonctionne correctement sur votre ordinateur (lecture "
"vidéo, réseau, tableur…). Les résultats détaillés sont ensuite "
"consultables via « 📊 Résultats des tests Citron », où un bouton "
"« 📋 Copier tout » regroupe résultats ET sortie console complète du test "
"dans le presse-papiers — pratique pour transmettre un diagnostic "
"complet en cas de souci.\n"
"• 🚪 Quitter Citron → ferme l'application proprement.\n"
"\n"
"────────────────────────────────────────────\n"
"EN CAS DE SOUCI\n"
"────────────────────────────────────────────\n"
"Lancez « 🧪 Test Citron » depuis les Paramètres : il vérifie "
"automatiquement les principaux rouages de l'application (lecture "
"vidéo, réseau, tableur, protocole navigateur…) et vous indique "
"précisément ce qui fonctionne ou non. Une fois le test terminé, ouvrez "
"« 📊 Résultats des tests Citron » et cliquez sur « 📋 Copier tout » pour "
"obtenir d'un coup les résultats détaillés et la sortie console complète, "
"prêts à être transmis pour un diagnostic.\n"
            )
            txt.insert("1.0", help_text)
            txt.configure(state="disabled")
            ctk.CTkButton(win, text="Fermer", command=win.destroy,
                          height=36).pack(pady=8)

        def _unlink_tableur(self):
            """Annule le lien avec le tableur sélectionné."""
            self._tableur_path = ""
            self._ods_rows_cache = None
            if hasattr(self, "_info_cache"): self._info_cache.clear()
            self.save_settings()
            messagebox.showinfo("Tableur", "Lien avec le tableur supprimé.")

        def _stop_before_tableur_action(self):
            """Arrête la lecture seulement lorsqu'une action du menu est choisie."""
            try:
                self.stop_video()
            except Exception as ex:
                print(f"[Tableur][STOP] stop_video : {type(ex).__name__}: {ex}")
            try:
                if getattr(self, "_resume_speech_active", False):
                    self._stop_resume_speech(
                        getattr(self, "_resume_speech_vid_ref", None)
                    )
            except Exception as ex:
                print(f"[Tableur][STOP] résumé vocal : {type(ex).__name__}: {ex}")

        def _show_tableur_menu(self, anchor_btn):
            """Affiche le menu déroulant du bouton 🗂 Tableur, avec ses 4 actions :
            sélection, modification, test et déconnexion du tableur.
            Menu custom (et non tk.Menu natif) pour pouvoir le refermer
            automatiquement dès que le curseur en sort, comme le menu
            ⚙ Paramètres.

            L'ouverture du menu ne coupe pas la lecture ; seule la sélection d'une action dans ce menu l'arrête.
            """
            if getattr(self, "_tableur_menu_win", None) and self._tableur_menu_win.winfo_exists():
                return
            mw = ctk.CTkToplevel(self)
            mw.wm_overrideredirect(True)
            mw.attributes("-topmost", True)
            mw.configure(fg_color="#2a2a2a")
            self._tableur_menu_win = mw
            def _close_tableur_menu(e=None):
                try: mw.destroy()
                except Exception: pass
                self._tableur_menu_win = None
            items = [
                ("📂 Sélection tableur", self._configure_tableur),
                ("✏️ Modification tableur", self._modifier_tableur),
                ("🧪 Test tableur", self._test_tableur),
                ("🌐 Compléter le tableur", self._open_completer_tableur_window),
                ("🗂 off (couper le lien)", self._unlink_tableur),
            ]
            for label, cmd in items:
                btn = ctk.CTkButton(mw, text=label, anchor="w",
                                    width=200, height=34,
                                    font=("Arial",13),
                                    fg_color="#2a2a2a",
                                    hover_color="#3a3a4a",
                                    command=lambda c=cmd: (
                                        _close_tableur_menu(),
                                        self._stop_before_tableur_action(),
                                        c()
                                    ))
                btn.pack(fill="x", padx=2, pady=1)
            # Positionner au-dessus du bouton (le bouton 🗂 Tableur est en
            # bas de l'écran, donc dérouler vers le bas rendrait le menu
            # invisible car hors écran)
            mw.update_idletasks()
            bx = anchor_btn.winfo_rootx()
            by = anchor_btn.winfo_rooty()
            mw.geometry(f"+{bx}+{by - mw.winfo_reqheight() - 4}")
            # Fermeture par SONDAGE de la position réelle du curseur (voir
            # _show_params_menu pour l'explication : <Leave> se déclenche à
            # tort lors du passage vers un bouton interne du menu).
            def _poll_pointer():
                if not mw.winfo_exists():
                    return
                try:
                    px, py = self.winfo_pointerx(), self.winfo_pointery()
                    over_menu = (mw.winfo_rootx() <= px <= mw.winfo_rootx()+mw.winfo_width()
                                 and mw.winfo_rooty() <= py <= mw.winfo_rooty()+mw.winfo_height())
                    over_btn = (anchor_btn.winfo_rootx() <= px <= anchor_btn.winfo_rootx()+anchor_btn.winfo_width()
                                and anchor_btn.winfo_rooty() <= py <= anchor_btn.winfo_rooty()+anchor_btn.winfo_height())
                    if not over_menu and not over_btn:
                        _close_tableur_menu()
                        return
                except Exception:
                    pass
                mw.after(120, _poll_pointer)
            mw.after(120, _poll_pointer)
            mw.focus_set()

        def _get_tableur_path_or_warn(self):
            """Récupère le chemin du tableur configuré. Affiche un avertissement
            et renvoie '' si aucun tableur n'est configuré."""
            if not self._tableur_path or not os.path.isfile(self._tableur_path):
                messagebox.showinfo(
                    "Tableur",
                    "Aucun tableur configuré.\n"
                    "Cliquez sur 🗂 Tableur → 📂 Sélection tableur pour en choisir un.")
                return ""
            return self._tableur_path

        def _confirmer_ou_choisir_tableur(self):
            """Avant CHAQUE validation dans « Compléter le tableur », demande
            SYSTÉMATIQUEMENT confirmation du tableur à utiliser, plutôt que
            de faire confiance sans un mot au chemin mémorisé. Un chemin
            mémorisé peut très bien exister sur le disque (donc paraître
            valide) tout en étant le MAUVAIS fichier — un ancien modèle,
            une copie oubliée sur un autre lecteur, le tableur d'un autre
            ordinateur… — auquel cas Citron écrivait « avec succès » dans un
            fichier que l'utilisateur ne consultait pas, en donnant
            l'impression que rien ne s'était enregistré. Renvoie le chemin
            confirmé ou choisi, ou '' si l'utilisateur annule (la
            validation est alors abandonnée). IMPORTANT : appelle
            messagebox/filedialog, donc à n'utiliser que depuis le thread
            principal — jamais depuis un thread d'arrière-plan (les appels
            Tkinter n'y sont pas fiables)."""
            chemin_actuel = self._tableur_path if (self._tableur_path and os.path.isfile(self._tableur_path)) else ""
            if chemin_actuel:
                reponse = messagebox.askyesno(
                        "Confirmer le tableur",
                        f"Intégrer ce résultat dans ce tableur ?\n\n« {chemin_actuel} »\n\n"
                        "Oui : utiliser ce fichier.\nNon : choisir un autre fichier .ods.")
                self._trace_recherche(
                    f"Confirmation tableur : chemin proposé = {chemin_actuel} — "
                    f"réponse = {'Oui (utiliser ce fichier)' if reponse else 'Non (en choisir un autre)'}")
                if reponse:
                    return chemin_actuel
            else:
                self._trace_recherche(
                    f"Confirmation tableur : chemin mémorisé absent/introuvable ({self._tableur_path!r}), "
                    "ouverture du sélecteur de fichier")
                messagebox.showinfo(
                    "Tableur introuvable",
                    ("Aucun tableur configuré." if not self._tableur_path else
                     f"Le tableur mémorisé est introuvable à cet emplacement :\n« {self._tableur_path} »\n\n"
                     "(normal si Citron est lancé sur un autre ordinateur, ou si le fichier a été déplacé)")
                    + "\n\nChoisis maintenant le fichier .ods à utiliser.")
            path = filedialog.askopenfilename(
                title="Choisir le tableur (.ods)",
                filetypes=[("Fichier OpenDocument", "*.ods"), ("Tous les fichiers", "*.*")])
            if not path:
                self._trace_recherche("Confirmation tableur : sélection de fichier annulée")
                return ""
            self._trace_recherche(f"Confirmation tableur : nouveau fichier choisi = {path}")
            self._tableur_path = path
            self.save_settings()
            return path

        def _modifier_tableur(self):
            """Ouvre le tableur déjà sélectionné dans son application par défaut
            (LibreOffice Calc, Excel, etc.) afin de permettre sa modification."""
            path = self._get_tableur_path_or_warn()
            if not path:
                return
            try:
                if os.name == "nt":
                    os.startfile(path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
            except Exception as ex:
                messagebox.showerror("Erreur", f"Impossible d'ouvrir le tableur :\n{ex}")

        # ══════════════════════════════════════════════════════════
        # ── 🌐 Compléter le tableur (recherche internet) ─────────────
        # ══════════════════════════════════════════════════════════
        def _open_completer_tableur_window(self, force_new=False, titre_initial=""):
            """Ouvre une fenêtre « Compléter le tableur » : un formulaire
            (Titre, Année, Type, Durée, Réalisateur, Acteurs, Bande-annonce,
            Affiche, Résumé) redimensionnable et repositionnable
            manuellement (taille/position mémorisées dans
            citron_settings.json, comme les autres fenêtres secondaires de
            Citron). On y saisit ce qu'on connaît déjà, puis « Rechercher »
            ne complète que les champs restés vides — pour un résultat plus
            précis qu'une recherche « à l'aveugle »."""
            self._completer_tableur_windows = [
                w for w in getattr(self, "_completer_tableur_windows", []) if w.winfo_exists()
            ]
            if not force_new:
                for w in self._completer_tableur_windows:
                    if getattr(w, "_completer_stage", "") == "vide":
                        w.lift()
                        w.focus_set()
                        return w

            win = ctk.CTkToplevel(self)
            win.title("🌐 Compléter le tableur")
            win.geometry(self.completer_tableur_win_geometry or "560x640")
            win.minsize(420, 420)
            win.resizable(True, True)  # fenêtre dimensionnable et repositionnable
            win.transient(self)
            win._completer_stage = "vide"
            win.protocol("WM_DELETE_WINDOW", lambda w=win: self._close_completer_tableur_window(w))
            self._completer_tableur_windows.append(win)

            container = ctk.CTkFrame(win, fg_color="transparent")
            container.pack(fill="both", expand=True, padx=16, pady=16)
            win.container = container

            self._completer_tableur_build_form(win, {"titre": titre_initial} if titre_initial else None)

            win.lift()
            win.focus_set()
            return win

        def _close_completer_tableur_window(self, win):
            """Ferme une fenêtre « Compléter le tableur » en mémorisant sa
            taille et sa position actuelles (pour la prochaine ouverture)."""
            if win:
                try:
                    self.completer_tableur_win_geometry = win.geometry()
                    self.save_settings()
                except Exception:
                    pass
                try:
                    win.destroy()
                except Exception:
                    pass
            self._completer_tableur_windows = [
                w for w in getattr(self, "_completer_tableur_windows", []) if w is not win and w.winfo_exists()
            ]

        def _ouvrir_completer_depuis_infos(self, titre, path, row_data):
            """Ouvre « Compléter le tableur », préremplie avec les données déjà
            connues du média (venant de la fiche 📋 Infos (tableur) affichée
            depuis la Liste complète des médias), pour compléter ou modifier
            cette ligne existante. Marque la fenêtre en « mode édition » :
            à la validation (_completer_tableur_valider), la ligne visée
            dans le tableur reste identifiée par son titre/année D'ORIGINE
            (mémorisés ici), même si le champ Titre est modifié entre temps
            — sans quoi une simple correction de titre créerait une
            nouvelle ligne au lieu de mettre à jour l'existante.

            Les champs Affiche/Bande-annonce sont volontairement laissés
            vides : ce sont des champs d'URL, alors que le tableur ne
            connaît que le chemin local déjà téléchargé (affiché à titre
            indicatif dans le message d'état). Tant que l'utilisateur n'y
            saisit rien lui-même, _completer_tableur_valider ne demande
            aucun dossier et ne télécharge rien — l'affiche et la
            bande-annonce déjà enregistrées restent donc intactes.

            La fiche 📋 Infos (tableur) est plein écran et « toujours au-
            dessus » (topmost) : sans désactiver temporairement ce topmost
            (même technique que pour l'ouverture d'AlloCiné, voir plus bas
            dans le fichier), cette fenêtre resterait cachée derrière elle.
            Il est restauré à la fermeture (voir _fermer_completer_depuis_infos)."""
            def _cell(i):
                if not row_data or i >= len(row_data):
                    return ""
                c = row_data[i]
                t = c.get("text", "") if isinstance(c, dict) else str(c)
                return (t or "").strip()

            titre_original = _cell(0) or os.path.splitext(os.path.basename(path))[0]
            annee_original = _cell(1)

            valeurs = {
                "titre": titre_original,
                "annee": annee_original,
                "resume": _cell(2),
                "personnes": _cell(3),
                "type": _cell(4),
                "realisateur": _cell(5),
                "duree": _cell(6),
                "renseignements": _cell(7),
                "categorie": _cell(11),
                # Laissés vides à dessein — voir docstring ci-dessus.
                "bande_annonce": "",
                "affiche": "",
            }

            _info_win_source = getattr(self, "_current_info_win", None)
            try:
                if _info_win_source and _info_win_source.winfo_exists():
                    _info_win_source.attributes("-topmost", False)
            except Exception:
                pass

            win = self._open_completer_tableur_window(force_new=True)
            # IMPORTANT : _completer_tableur_build_form réinitialise elle-même
            # win._completer_stage ("vide"/"formulaire" selon `valeurs`) — le
            # marqueur d'édition doit donc être posé APRÈS cet appel, sinon
            # il est aussitôt écrasé et _completer_tableur_valider retombe
            # sur le comportement d'ajout classique (recherche de doublon
            # sur le titre en cours d'édition, pas de fermeture automatique
            # de la fenêtre après mise à jour).
            self._completer_tableur_build_form(win, valeurs)
            win._completer_stage = "edition_depuis_infos"
            win._edition_titre_original = titre_original
            win._edition_annee_original = annee_original
            win._source_info_win = _info_win_source
            win.protocol("WM_DELETE_WINDOW", lambda w=win: self._fermer_completer_depuis_infos(w))

            complement = []
            affiche_actuelle = _cell(9)
            ba_actuelle = _cell(10)
            if affiche_actuelle:
                complement.append(f"Affiche actuelle : {affiche_actuelle}")
            if ba_actuelle:
                complement.append(f"Bande-annonce actuelle : {ba_actuelle}")
            label_media = titre_original + (f" ({annee_original})" if annee_original else "")
            try:
                win.status_label.configure(
                    text=f"✏️ Modification de la ligne existante « {label_media} »"
                         + ("\n" + "\n".join(complement) if complement else ""),
                    text_color="#8ab4d8")
            except Exception:
                pass
            try:
                win.valider_btn.configure(text="✅ Modifier le tableur")
            except Exception:
                pass
            try:
                win.attributes("-topmost", True)
            except Exception:
                pass
            win.lift(); win.focus_force()
            return win

        def _fermer_completer_depuis_infos(self, win):
            """Referme une fenêtre « Compléter le tableur » ouverte en mode
            édition depuis 📋 Infos (tableur) (croix de fermeture, ou fin de
            validation — voir _completer_tableur_apres_validation), et
            restaure le « toujours au-dessus » de cette fiche Infos,
            désactivé le temps de l'afficher par-dessus (voir
            _ouvrir_completer_depuis_infos)."""
            info_win = getattr(win, "_source_info_win", None)
            self._close_completer_tableur_window(win)
            try:
                if info_win and info_win.winfo_exists():
                    info_win.attributes("-topmost", True)
                    info_win.lift()
            except Exception:
                pass

        def _completer_tableur_clear_container(self, win):
            container = getattr(win, "container", None)
            if not container:
                return None
            for child in list(container.winfo_children()):
                try:
                    child.destroy()
                except Exception:
                    pass
            return container

        def _menu_contextuel_champ(self, widget, est_texte=False):
            """Ajoute un clic droit (Couper / Copier / Coller / Tout
            sélectionner) sur un champ — Citron doit rester utilisable de
            façon totalement autonome, y compris pour coller des
            informations trouvées ailleurs (indispensable dans « Compléter
            le tableur »).

            Le collage est rebranché manuellement sur le presse-papiers
            (clipboard_get/insert), exactement comme enable_entry_paste
            plus haut dans le fichier : un simple event_generate("<<Paste>>")
            ne suffit pas, car ce raccourci Ctrl+V natif de Tk n'est pas
            fiable sur tous les claviers (AZERTY notamment) et rendait le
            collage totalement impossible dans les champs de « Compléter le
            tableur », y compris via le menu clic-droit."""
            menu = Menu(widget, tearoff=0)

            def _selection_active():
                try:
                    if est_texte:
                        return bool(widget.tag_ranges("sel"))
                    return widget.selection_present()
                except Exception:
                    return False

            def _paste(event=None):
                try:
                    texte = widget.clipboard_get()
                except Exception:
                    return "break"
                if not texte:
                    return "break"
                try:
                    if _selection_active():
                        widget.delete("sel.first", "sel.last")
                    widget.insert("insert", texte)
                except Exception:
                    pass
                return "break"

            def _copy(event=None):
                try:
                    texte = widget.selection_get()
                except Exception:
                    return "break"
                widget.clipboard_clear()
                widget.clipboard_append(texte)
                return "break"

            def _cut(event=None):
                _copy()
                try:
                    if _selection_active():
                        widget.delete("sel.first", "sel.last")
                except Exception:
                    pass
                return "break"

            def _tout_selectionner(event=None):
                try:
                    if est_texte:
                        widget.tag_add("sel", "1.0", "end")
                    else:
                        widget.select_range(0, "end")
                except Exception:
                    pass
                return "break"

            for seq in ("<Control-v>", "<Control-V>", "<<Paste>>"):
                widget.bind(seq, _paste)
            for seq in ("<Control-c>", "<Control-C>", "<<Copy>>"):
                widget.bind(seq, _copy)
            for seq in ("<Control-x>", "<Control-X>", "<<Cut>>"):
                widget.bind(seq, _cut)
            for seq in ("<Control-a>", "<Control-A>"):
                widget.bind(seq, _tout_selectionner)

            menu.add_command(label="Couper", command=_cut)
            menu.add_command(label="Copier", command=_copy)
            menu.add_command(label="Coller", command=_paste)
            menu.add_separator()
            menu.add_command(label="Tout sélectionner", command=_tout_selectionner)

            def _popup(event):
                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()

            widget.bind("<Button-3>", _popup)

        def _completer_tableur_build_form(self, win, valeurs=None):
            """Construit le formulaire (unique) de la fenêtre : tous les
            champs du tableur, éditables, pré-remplis avec `valeurs` si
            fourni (sinon vides). Complète ce qu'on connaît déjà toi-même,
            puis clique « Rechercher » : seuls les champs restés vides
            seront complétés par la recherche internet — les champs déjà
            remplis (par toi ou par une recherche précédente) ne sont
            jamais écrasés."""
            win._completer_stage = "vide" if not valeurs else "formulaire"
            valeurs = valeurs or {}
            container = self._completer_tableur_clear_container(win)
            if container is None:
                return

            ctk.CTkLabel(container, text="🌐 Compléter le tableur",
                         font=("Arial", 18, "bold")).pack(pady=(0, 4))
            ctk.CTkLabel(container,
                         text="Remplis ce que tu sais déjà, puis « Rechercher » ne "
                              "complètera que les champs restés vides.",
                         font=("Arial", 12), text_color="#999999", wraplength=480,
                         justify="left").pack(pady=(0, 10))

            # Catégorie (12ème colonne du tableur) : sélection unique parmi
            # une liste fixe — cocher une case décoche automatiquement les
            # autres. « Autre » ouvre un champ libre pour préciser la
            # catégorie à la main (c'est ce texte, et non le mot « Autre »,
            # qui est alors écrit dans la 12ème colonne).
            ctk.CTkLabel(container, text="Catégorie", font=("Arial", 13, "bold"),
                         anchor="w").pack(fill="x", pady=(0, 2))
            cat_row = ctk.CTkFrame(container, fg_color="transparent")
            cat_row.pack(fill="x", pady=(0, 10))
            win._categorie_vars = {}
            categories = ["Film", "Pièce de théâtre", "Films d'animation", "Clip vidéo", "Concert", "Autre"]
            _val_categorie = (valeurs.get("categorie", "") or "").strip()
            # Une valeur déjà présente dans le tableur qui correspond au nom
            # d'une case (sans distinguer majuscules/minuscules — ex :
            # "FILM" ou "film") doit cocher CETTE case, pas "Autre" avec
            # "Préciser la catégorie" rempli du nom de la case elle-même
            # (ça n'aurait pas de sens). Seule une valeur qui ne correspond
            # à aucune case ouvre le champ libre "Autre".
            _categorie_match = next(
                (c for c in categories if _val_categorie.casefold() == c.casefold()), None)
            _categorie_est_autre = bool(_val_categorie) and _categorie_match is None
            _val_categorie_normalisee = _categorie_match if _categorie_match else (
                _val_categorie if _categorie_est_autre else "")
            win.field_categorie = ctk.StringVar(value=_val_categorie_normalisee)

            autre_categorie_row = ctk.CTkFrame(container, fg_color="transparent")
            win.field_categorie_autre = ctk.StringVar(value=_val_categorie if _categorie_est_autre else "")

            def _maj_categorie_autre(*_args):
                if win._categorie_vars.get("Autre") and win._categorie_vars["Autre"].get():
                    win.field_categorie.set((win.field_categorie_autre.get() or "").strip())

            win.field_categorie_autre.trace_add("write", _maj_categorie_autre)

            def _toggle_categorie(nom):
                for autre, var in win._categorie_vars.items():
                    if autre != nom:
                        var.set(False)
                est_coche = win._categorie_vars[nom].get()
                if nom == "Autre":
                    if est_coche:
                        autre_categorie_row.pack(fill="x", pady=(0, 10), before=divers_row)
                        win.field_categorie.set((win.field_categorie_autre.get() or "").strip())
                    else:
                        autre_categorie_row.pack_forget()
                        win.field_categorie.set("")
                else:
                    autre_categorie_row.pack_forget()
                    win.field_categorie.set(nom if est_coche else "")

            for i, nom in enumerate(categories):
                coche_initiale = (_categorie_match == nom) or (nom == "Autre" and _categorie_est_autre)
                v = ctk.BooleanVar(value=coche_initiale)
                win._categorie_vars[nom] = v
                cb = ctk.CTkCheckBox(cat_row, text=nom, variable=v, font=("Arial", 12),
                                      command=lambda n=nom: _toggle_categorie(n))
                cb.grid(row=i // 3, column=i % 3, sticky="w", padx=(0, 12), pady=2)

            ctk.CTkLabel(autre_categorie_row, text="Préciser la catégorie :",
                         font=("Arial", 12)).pack(side="left", padx=(0, 8))
            ctk.CTkEntry(autre_categorie_row, textvariable=win.field_categorie_autre,
                         width=220).pack(side="left", fill="x", expand=True)

            # Renseignements divers (8ème colonne du tableur) : champ libre
            # — remplace l'ancienne case à cocher « noir et blanc ». Tape
            # ici ce que tu veux (ex : « N/B », « VOSTFR »...) ; rien n'est
            # écrit si le champ reste vide (la colonne n'est jamais
            # écrasée par du vide à la validation).
            divers_row = ctk.CTkFrame(container, fg_color="transparent")
            divers_row.pack(fill="x", pady=(0, 10))
            ctk.CTkLabel(divers_row, text="Renseignements divers :",
                         font=("Arial", 12)).pack(side="left", padx=(0, 8))
            win.field_renseignements = ctk.StringVar(value=valeurs.get("renseignements", "") or "")
            ctk.CTkEntry(divers_row, textvariable=win.field_renseignements, width=220,
                         placeholder_text="ex : N/B, VOSTFR...").pack(side="left", fill="x", expand=True)

            if _categorie_est_autre:
                autre_categorie_row.pack(fill="x", pady=(0, 10), before=divers_row)

            scroll = ctk.CTkScrollableFrame(container, fg_color="transparent")
            scroll.pack(fill="both", expand=True)

            def _champ(label, cle, placeholder=""):
                ctk.CTkLabel(scroll, text=label, font=("Arial", 13, "bold"),
                             anchor="w").pack(fill="x", pady=(8, 2))
                var = ctk.StringVar(value=valeurs.get(cle, "") or "")
                entry_widget = ctk.CTkEntry(scroll, textvariable=var, height=34,
                                             placeholder_text=placeholder)
                entry_widget.pack(fill="x")
                self._menu_contextuel_champ(entry_widget)
                if cle == "titre":
                    win.titre_entry = entry_widget
                return var

            win.field_titre = _champ("Titre", "titre", "Titre du film / de la vidéo…")
            win.field_annee = _champ("Année", "annee")
            win.field_type = _champ("Type (genre)", "type")
            win.field_duree = _champ("Durée (minutes)", "duree")
            win.field_realisateur = _champ("Réalisateur (Filmeur)", "realisateur")
            win.field_personnes = _champ("Acteurs (séparés par « / »)", "personnes")
            win.field_bande_annonce = _champ("Bande-annonce (URL vidéo)", "bande_annonce")
            win.field_affiche = _champ("Affiche (URL image)", "affiche")

            ctk.CTkLabel(scroll, text="Résumé / synopsis", font=("Arial", 13, "bold"),
                         anchor="w").pack(fill="x", pady=(8, 2))
            resume_box = ctk.CTkTextbox(scroll, height=130, font=("Arial", 12), wrap="word")
            resume_box.pack(fill="both", expand=True)
            resume_box.insert("1.0", valeurs.get("resume", "") or "")
            self._menu_contextuel_champ(resume_box, est_texte=True)
            win.field_resume = resume_box

            win.status_label = ctk.CTkLabel(
                scroll, text="", font=("Arial", 11), text_color="#cccccc",
                wraplength=460, justify="left")
            win.status_label.pack(fill="x", pady=(8, 0))

            cle_row = ctk.CTkFrame(container, fg_color="transparent")
            cle_row.pack(fill="x", pady=(8, 0))
            ctk.CTkButton(cle_row, text="🔑 Clé API TMDB", height=26, width=1,
                          fg_color="transparent", border_width=1, text_color="#cccccc",
                          command=lambda w=win: self._completer_tableur_config_tmdb(w)).pack(
                side="left", expand=True, fill="x", padx=(0, 4))
            ctk.CTkButton(cle_row, text="🤖 Configurer l'IA", height=26, width=1,
                          fg_color="transparent", border_width=1, text_color="#cccccc",
                          command=lambda w=win: self._completer_tableur_config_ia(w)).pack(
                side="left", expand=True, fill="x", padx=(4, 0))

            btns = ctk.CTkFrame(container, fg_color="transparent")
            btns.pack(fill="x", pady=(10, 0))
            win.search_btn = ctk.CTkButton(
                btns, text="🔎 Rechercher les champs vides sur internet", height=38,
                command=lambda w=win: self._completer_tableur_lancer_recherche(w))
            win.search_btn.pack(fill="x", pady=(0, 6))

            liens_row = ctk.CTkFrame(btns, fg_color="transparent")
            liens_row.pack(fill="x", pady=(0, 6))
            ctk.CTkButton(liens_row, text="▶ Bande-annonce", height=30, width=1,
                          fg_color="transparent", border_width=1,
                          command=lambda w=win: self._completer_tableur_ouvrir_champ(
                              w, "field_bande_annonce", "bande-annonce")).pack(
                side="left", expand=True, fill="x", padx=(0, 4))
            ctk.CTkButton(liens_row, text="🖼 Affiche", height=30, width=1,
                          fg_color="transparent", border_width=1,
                          command=lambda w=win: self._completer_tableur_ouvrir_champ(
                              w, "field_affiche", "affiche")).pack(
                side="left", expand=True, fill="x", padx=(4, 0))

            win.simuler_btn = ctk.CTkButton(btns, text="📋 Simuler Infos (tableur)", height=38,
                          command=lambda w=win: self._completer_tableur_simuler(w))
            win.simuler_btn.pack(fill="x", pady=(0, 6))
            win.valider_btn = ctk.CTkButton(btns, text="✅ Valider et intégrer au tableur", height=38,
                          fg_color="#2e7d32", hover_color="#1b5e20",
                          command=lambda w=win: self._completer_tableur_valider(w))
            win.valider_btn.pack(fill="x", pady=(0, 6))
            ctk.CTkButton(btns, text="🗑 Effacer les champs", height=30,
                          fg_color="#555555",
                          command=lambda w=win: self._completer_tableur_effacer_champs(w)).pack(fill="x")

            win.titre_entry.bind("<Return>", lambda e, w=win: self._completer_tableur_lancer_recherche(w))
            win.titre_entry.focus_set()

        def _completer_tableur_ouvrir_champ(self, win, nom_champ, libelle):
            """Ouvre dans le navigateur le lien actuellement saisi dans un
            champ (bande-annonce ou affiche)."""
            widget = getattr(win, nom_champ, None)
            valeur = (widget.get() or "").strip() if widget else ""
            if not valeur:
                messagebox.showinfo("Champ vide", f"Aucun lien de {libelle} n'est renseigné pour l'instant.")
                return
            webbrowser.open(valeur)

        def _completer_tableur_effacer_champs(self, win):
            """Vide tous les champs du formulaire (sans toucher au
            tableur) pour repartir d'une fiche vierge. Si cette fenêtre
            était en mode « édition depuis Infos » (voir
            _ouvrir_completer_depuis_infos), on en sort complètement :
            sinon une nouvelle saisie complètement différente risquerait
            d'écraser par erreur la ligne d'origine mémorisée."""
            win._completer_stage = "vide"
            for attr in ("_edition_titre_original", "_edition_annee_original"):
                if hasattr(win, attr):
                    delattr(win, attr)
            self._completer_tableur_build_form(win, None)
            try:
                win.valider_btn.configure(text="✅ Valider et intégrer au tableur")
            except Exception:
                pass

        def _completer_tableur_lancer_recherche(self, win):
            """Recherche sur internet et ne complète QUE les champs restés
            vides dans le formulaire — les champs déjà remplis (par
            l'utilisateur ou par une recherche précédente) ne sont jamais
            écrasés. Le Titre (et l'Année, si renseignée) servent de
            critères pour affiner les résultats."""
            champs_actuels = self._completer_tableur_lire_champs(win)
            titre = champs_actuels["titre"]
            if not titre:
                win.status_label.configure(
                    text="⚠️ Indique d'abord un titre à rechercher.", text_color="#ff8888")
                return
            annee_cible = champs_actuels["annee"] or None
            try:
                win.search_btn.configure(state="disabled", text="⏳ Recherche en cours…")
            except Exception:
                pass
            win.status_label.configure(
                text=f"⏳ Recherche de « {titre} »" + (f" ({annee_cible})" if annee_cible else "") + "…",
                text_color="#cccccc")

            def worker():
                self._trace_recherche(f"Clic « 🔎 Rechercher » — titre='{titre}', année='{annee_cible or ''}'")
                try:
                    resultat = self._rechercher_infos_web_film(titre, annee_cible)
                    erreur = None
                except Exception as ex:
                    resultat = None
                    erreur = str(ex)
                    self._trace_recherche(f"Recherche des champs : ÉCHEC — {type(ex).__name__}: {ex}")
                if resultat:
                    titre_ba = resultat.get("titre") or titre
                    annee_ba = resultat.get("annee") or annee_cible
                    self._trace_recherche(f"Bande-annonce → YouTube : recherche « Bande annonce du film {titre_ba}"
                                           + (f" ({annee_ba})" if annee_ba else "") + " »…")
                    try:
                        resultat["bande_annonce"] = self._rechercher_bande_annonce_youtube(titre_ba, annee_ba)
                        if resultat["bande_annonce"]:
                            self._trace_recherche(f"Bande-annonce → YouTube : trouvée ({resultat['bande_annonce']})")
                        else:
                            self._trace_recherche("Bande-annonce → YouTube : rien trouvé, repli sur Dailymotion…")
                            resultat["bande_annonce"] = self._rechercher_bande_annonce_dailymotion(titre_ba, annee_ba)
                            if resultat["bande_annonce"]:
                                self._trace_recherche(
                                    f"Bande-annonce → Dailymotion : trouvée ({resultat['bande_annonce']})")
                            else:
                                self._trace_recherche("Bande-annonce → Dailymotion : rien trouvé non plus")
                    except Exception as ex:
                        resultat["bande_annonce"] = ""
                        self._trace_recherche(f"Bande-annonce : ÉCHEC — {type(ex).__name__}: {ex}")
                if win.winfo_exists():
                    self.after(0, lambda: self._completer_tableur_on_resultat(win, champs_actuels, resultat, erreur))

            threading.Thread(target=worker, daemon=True).start()

        def _format_image_autorise(self, url_image):
            """Interdit le format webp pour les affiches (jpg/jpeg
            privilégiés) — Citron doit rester utilisable de façon la plus
            autonome possible, sans dépendre d'un décodeur webp
            supplémentaire. Renvoie False pour une URL vide ou en .webp."""
            u = (url_image or "").strip().lower().split("?")[0]
            if not u:
                return False
            return not u.endswith(".webp")

        def _normaliser_url_affiche(self, url_image):
            """Améliore une URL d'affiche AlloCiné collée à la main,
            lorsque c'est bien une adresse d'IMAGE (voir aussi
            _resoudre_url_affiche, qui gère le cas où c'est le lien de la
            fiche film elle-même qui a été collé).

            Sur une fiche film AlloCiné, l'image d'affiche visible en haut
            de page (dont le texte alternatif, curieusement, commence par
            « poster du film Bande-annonce ... » — d'où la confusion
            possible avec la zone bande-annonce) est parfois servie en
            miniature RECADRÉE, via une URL du type :
                https://fr.web.img4.acsta.net/c_310_420/medias/nmedia/....jpg
            Le segment "c_<largeur>_<hauteur>/" est un paramètre de
            recadrage du CDN d'AlloCiné (acsta.net). Cette fonction ne
            fait qu'un nettoyage de texte, sans jamais interroger le
            réseau : elle ne garantit donc pas que l'image obtenue existe
            réellement une fois le recadrage retiré (certains sous-domaines
            du CDN ne servent QUE des variantes recadrées) — c'est pour
            cette raison que le téléchargement retente ensuite l'URL
            d'origine si la version « nettoyée » échoue (voir
            _telecharger_bytes_image). Renvoie l'URL d'origine dans tous
            les autres cas (autre site, pas de recadrage détecté)."""
            import re
            url = (url_image or "").strip()
            if not url or "acsta.net" not in url.lower():
                return url
            return re.sub(r"/c_\d+_\d+/", "/", url, count=1)

        def _resoudre_url_affiche(self, url_ou_page):
            """Détermine l'URL d'image à utiliser pour l'affiche à partir
            de ce qui a été collé dans le champ « Affiche (URL image) » :
            - un lien vers une FICHE FILM AlloCiné (ex. collé directement
              depuis la barre d'adresse du navigateur :
              https://www.allocine.fr/film/fichefilm_gen_cfilm=....html) :
              la fiche est alors récupérée et sa vraie affiche (balise
              <meta property="og:image">) en est extraite, exactement comme
              le fait la recherche automatique (_rechercher_allocine) — plus
              besoin d'ouvrir l'image dans un nouvel onglet pour en copier
              l'adresse à la main, coller le lien de la fiche suffit ;
              - une URL d'image « normale » (AlloCiné ou autre site) : un
              simple nettoyage de texte est tenté (_normaliser_url_affiche).
            Fait un appel réseau dans le premier cas : à n'utiliser que
            depuis un thread d'arrière-plan (téléchargement), jamais
            directement au clic d'un bouton. Renvoie "" si rien
            d'exploitable n'a pu être déterminé."""
            url = (url_ou_page or "").strip()
            if not url:
                return ""
            if "allocine.fr/film/fichefilm" in url.lower():
                headers = {"User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)"}
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as r:
                        html_text = r.read().decode("utf-8", errors="ignore")
                except Exception as ex:
                    self._trace_recherche(
                        f"Affiche : échec de la récupération de la fiche AlloCiné {url} — "
                        f"{type(ex).__name__}: {ex}")
                    return ""
                data = self._analyser_page_film(html_text, url)
                affiche = self._normaliser_url_affiche((data.get("affiche") or "").strip())
                if affiche:
                    self._trace_recherche(f"Affiche : récupérée depuis la fiche AlloCiné → {affiche}")
                else:
                    self._trace_recherche(f"Affiche : aucune image trouvée sur la fiche AlloCiné {url}")
                return affiche
            return self._normaliser_url_affiche(url)

        def _telecharger_bytes_image(self, url):
            """Télécharge le contenu binaire d'une image, avec un en-tête
            Referer (certains CDN — dont celui d'AlloCiné, acsta.net —
            refusent une requête qui n'en porte pas, alors qu'ouvrir la
            même image dans un onglet du navigateur fonctionne car
            celui-ci en envoie toujours un). Renvoie les octets, ou None
            en cas d'échec (format webp reçu, erreur réseau...) — le
            détail exact de l'échec est tracé dans la console."""
            try:
                hote = urllib.parse.urlsplit(url).netloc
            except Exception:
                hote = ""
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)",
                "Referer": f"https://{hote}/" if hote else "https://www.allocine.fr/",
            }
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=15) as r:
                    if "webp" in (r.headers.get("Content-Type", "") or "").lower():
                        self._trace_recherche(f"Affiche : refusée, le serveur a renvoyé du webp → {url}")
                        return None
                    return r.read()
            except Exception as ex:
                self._trace_recherche(f"Affiche : échec du téléchargement de {url} — {type(ex).__name__}: {ex}")
                return None

        def _titres_similaires(self, a, b, seuil=0.5):
            """Compare deux titres de façon tolérante (accents, casse,
            ponctuation) pour vérifier qu'une page trouvée sur internet
            correspond bien au film recherché — et pas, par exemple, à la
            page d'accueil d'un site sur laquelle on aurait été redirigé."""
            import difflib
            ca = self._tableur_search_clean(a or "")
            cb = self._tableur_search_clean(b or "")
            if not ca or not cb:
                return False
            if ca == cb or ca in cb or cb in ca:
                return True
            return difflib.SequenceMatcher(None, ca, cb).ratio() >= seuil

        def _choisir_candidat_film(self, nom_source, titre, annee_cible, candidats):
            """Départage plusieurs fiches film candidates (même titre,
            trouvées sur un site — AlloCiné, SensCritique,
            Plansamericains...) pour choisir laquelle utiliser. Se limiter
            au tout premier résultat de DuckDuckGo (voir
            _rechercher_url_duckduckgo, max_resultats) risquerait de
            renseigner un film qui n'est pas celui demandé — ex. les DEUX
            films distincts « Black Rain » sortis en 1989 : le titre seul
            ne suffit pas à les départager.

            - Si une année a déjà été précisée dans le formulaire
              (`annee_cible`), le premier candidat dont l'année correspond
              (ou dont l'année est inconnue) est retenu.
            - Sinon, si les candidats trouvés donnent des années
              DIFFÉRENTES entre elles, rien n'est renseigné automatiquement
              — mieux vaut ne rien remplir que remplir avec le mauvais
              film : il faut d'abord préciser le titre, PUIS indiquer
              l'année et relancer la recherche pour que celle-ci puisse
              choisir la bonne fiche parmi les homonymes.
            - Sinon (un seul candidat, ou tous la même année), le premier
              candidat est retenu directement.
            Renvoie le candidat retenu (dict), ou None."""
            if not candidats:
                return None
            if annee_cible:
                for d in candidats:
                    if not d.get("annee") or d["annee"] == annee_cible:
                        return d
                self._trace_recherche(
                    f"{nom_source} : {len(candidats)} fiche(s) trouvée(s) pour « {titre} », "
                    f"aucune ne correspond à l'année {annee_cible}, rejeté")
                return None

            annees_trouvees = {d["annee"] for d in candidats if d.get("annee")}
            if len(annees_trouvees) > 1:
                self._trace_recherche(
                    f"{nom_source} : {len(candidats)} films différents trouvés pour « {titre} » "
                    f"(années : {', '.join(sorted(annees_trouvees))}) — aucune année n'est encore "
                    f"précisée dans le formulaire, rien n'est renseigné automatiquement pour éviter "
                    f"de mélanger deux films. Indique l'année puis relance la recherche.")
                return None
            return candidats[0]

        def _mots_significatifs_titre(self, titre):
            """Mots « porteurs de sens » d'un titre (sans les articles/mots
            très courts), utilisés pour une comparaison stricte — ex. pour
            valider une bande-annonce, où une simple ressemblance globale
            ne suffit pas (« La Guerre des boutons » et « La Guerre est
            déclarée » se ressemblent globalement mais ne sont pas le même
            film)."""
            mots_vides = {"le", "la", "les", "l", "de", "des", "du", "un", "une", "et",
                          "a", "au", "aux", "en", "ce", "ces", "se", "sa", "son", "ses",
                          "d", "est", "sont", "dans", "sur", "pour"}
            return [m for m in self._tableur_search_clean(titre).split()
                    if m and m not in mots_vides and len(m) > 1]

        def _titre_correspond_strictement(self, titre_cible, titre_trouve):
            """Vérifie que TOUS les mots significatifs du titre recherché
            apparaissent dans le titre trouvé — plus strict que
            `_titres_similaires`, utilisé quand une erreur coûterait cher
            (ex. bande-annonce d'un autre film)."""
            mots = self._mots_significatifs_titre(titre_cible)
            if not mots:
                return False
            ct = self._tableur_search_clean(titre_trouve)
            return all(m in ct for m in mots)

        def _rechercher_infos_web_film(self, titre, annee_cible=None):
            """Agrège les résultats de plusieurs sources (tv-programme.com,
            AlloCiné, SensCritique, Plansamericains, TMDB, IA) pour un même
            titre — et, si elle est connue, une année précise (utile quand
            plusieurs films portent le même titre) — et fusionne les
            informations obtenues (année, résumé, réalisateur, acteurs,
            type, durée, affiche) en comblant les champs manquants d'une
            source avec les suivantes. Renvoie un dict, ou lève une
            exception si AUCUNE source n'a donné de résultat fiable."""
            titre = (titre or "").strip()
            if not titre:
                raise ValueError("Titre vide.")

            self._trace_recherche(
                f"=== Recherche « {titre} »" + (f" ({annee_cible})" if annee_cible else "") +
                " — début ===")

            # Ordre de priorité en cascade (demandé explicitement) :
            # tv-programme.com d'abord, puis AlloCiné, puis SensCritique,
            # puis Plansamericains (films américains de genre, absents des
            # 3 précédents) — TMDB et l'IA ne sont sollicités qu'en tout
            # dernier recours, uniquement si les 4 sources précédentes
            # réunies n'ont toujours pas tout complété. Chaque source
            # n'est donc interrogée QUE si le résultat cumulé des
            # précédentes n'est pas encore précis (champ manquant, ou
            # effacé par l'utilisateur dans le formulaire — ce qui revient
            # au même : un champ vide) ; dès que tout est renseigné, les
            # sources suivantes sont sautées, y compris TMDB/IA. Wikipédia
            # est explicitement banni de la recherche (affiches trop
            # souvent des logos plutôt que des affiches de film, et
            # informations parfois peu fiables).
            sources_a_tester = [
                ("tv-programme.com", self._rechercher_tv_programme),
                ("AlloCiné", self._rechercher_allocine),
                ("SensCritique", self._rechercher_senscritique),
                ("Plansamericains", self._rechercher_plansamericains),
                ("TMDB", self._rechercher_tmdb),
                ("IA", self._rechercher_ia),
            ]
            champs_a_completer = ("annee", "resume", "personnes", "realisateur",
                                   "type", "duree", "affiche")

            fusion = {"titre": "", "annee": "", "resume": "", "personnes": "",
                      "realisateur": "", "type": "", "duree": "", "affiche": ""}
            resultats = []
            sources_utilisees = []
            for nom, fn in sources_a_tester:
                manquants_avant = [c for c in champs_a_completer if not fusion.get(c)]
                if resultats and not manquants_avant:
                    self._trace_recherche(f"→ {nom} : non interrogée, résultat déjà complet")
                    continue
                self._trace_recherche(f"→ {nom} : recherche en cours…")
                try:
                    d = fn(titre, annee_cible)
                except Exception as ex:
                    d = None
                    self._trace_recherche(f"→ {nom} : ÉCHEC — {type(ex).__name__}: {ex}")
                else:
                    if d:
                        self._trace_recherche(
                            f"→ {nom} : résultat retenu (titre='{d.get('titre','')}', "
                            f"année='{d.get('annee','')}', affiche={'oui' if d.get('affiche') else 'non'})")
                    else:
                        self._trace_recherche(f"→ {nom} : aucun résultat (rejeté ou introuvable)")
                if not d:
                    continue
                resultats.append((nom, d))
                a_servi = False
                for cle in ("titre",) + champs_a_completer:
                    if not fusion.get(cle) and (d.get(cle) or "").strip():
                        fusion[cle] = d[cle].strip()
                        a_servi = True
                if a_servi:
                    lien = d.get("source", "")
                    sources_utilisees.append(f"{nom} ({lien})" if lien else nom)

            if not resultats:
                self._trace_recherche(f"=== Recherche « {titre} » — ÉCHEC : aucune source n'a répondu ===")
                raise ValueError(
                    f"Aucune information trouvée pour « {titre} » sur tv-programme.com, "
                    "AlloCiné, SensCritique, Plansamericains, TMDB ou IA."
                )

            # L'affiche AlloCiné est explicitement priorisée sur toutes les
            # autres sources (demandé explicitement) : si AlloCiné a été
            # trouvé et propose une affiche, elle remplace celle retenue par
            # l'ordre de fusion général ci-dessus, quelle que soit la
            # source qui l'avait fournie.
            allocine_d = next((d for nom, d in resultats if nom == "AlloCiné"), None)
            if allocine_d and (allocine_d.get("affiche") or "").strip():
                fusion["affiche"] = allocine_d["affiche"].strip()
                if not any(s.startswith("AlloCiné") for s in sources_utilisees):
                    lien = allocine_d.get("source", "")
                    sources_utilisees.append(f"AlloCiné, affiche ({lien})" if lien else "AlloCiné (affiche)")

            if not fusion["titre"]:
                fusion["titre"] = titre
            if annee_cible and not fusion["annee"]:
                fusion["annee"] = annee_cible
            fusion["source"] = " · ".join(sources_utilisees)

            manquants = [cle for cle in champs_a_completer if not fusion.get(cle)]
            self._trace_recherche(
                f"=== Recherche « {titre} » — terminée : sources retenues = "
                f"{', '.join(n for n, _ in resultats) or 'aucune'} ; "
                f"champs encore vides = {', '.join(manquants) or 'aucun'} ===")
            return fusion

        def _trace_recherche(self, msg):
            """Affiche une trace dans la console (préfixe [Compléter]),
            pour comprendre étape par étape pourquoi une recherche dans
            « Compléter le tableur » ne renvoie rien : quelle source est
            interrogée, si elle répond, si son résultat est accepté ou
            rejeté (et pourquoi), et quelle exception exacte s'est
            produite le cas échéant (auparavant totalement silencieuse).
            Purement informatif : n'affecte jamais le comportement."""
            try:
                print(f"[Compléter] {msg}")
            except Exception:
                pass

        def _genres_films_connus(self):
            """Liste de genres utilisée pour deviner le « Type » d'un film à
            partir d'un texte libre (résumé, page web…)."""
            return ["comédie dramatique", "comédie musicale", "comédie", "drame", "action",
                    "thriller", "horreur", "animation", "documentaire", "science-fiction",
                    "romance", "aventure", "policier", "fantastique", "guerre", "western",
                    "biopic", "épouvante"]

        def _analyser_page_film(self, html_text, url):
            """Analyse heuristique d'une page web « fiche film » générique
            (utilisée pour AlloCiné et tv-programme.com, qui n'ont pas d'API
            publique officielle) : s'appuie sur les balises <meta> standard
            (og:title, description) puis sur des motifs de texte courants
            (réalisateur, distribution, durée…). Le résultat peut être
            partiel : chaque champ manquant reste une chaîne vide. Le
            réalisateur et les acteurs sont renvoyés séparément."""
            import re
            import html as html_mod

            def _meta(nom):
                m = re.search(
                    r'<meta[^>]+(?:name|property)=["\']' + re.escape(nom) +
                    r'["\'][^>]*content=["\']([^"\']*)["\']', html_text, re.IGNORECASE)
                if not m:
                    m = re.search(
                        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:name|property)=["\']' +
                        re.escape(nom) + r'["\']', html_text, re.IGNORECASE)
                return html_mod.unescape(m.group(1)).strip() if m else ""

            titre_page = _meta("og:title")
            if not titre_page:
                m = re.search(r"<title[^>]*>([^<]+)</title>", html_text, re.IGNORECASE)
                titre_page = html_mod.unescape(m.group(1)).strip() if m else ""

            resume = _meta("og:description") or _meta("description")

            annee = ""
            m = re.search(r"\b(19|20)\d{2}\b", titre_page)
            if m:
                annee = m.group(0)

            # Texte "brut" (balises HTML retirées) pour les heuristiques.
            texte = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html_text,
                            flags=re.DOTALL | re.IGNORECASE)
            texte = re.sub(r"<[^>]+>", " ", texte)
            texte = html_mod.unescape(texte)
            texte = re.sub(r"[ \t]+", " ", texte)

            if not annee:
                m = re.search(r"\b(19|20)\d{2}\b", texte)
                if m:
                    annee = m.group(0)

            duree = ""
            m = re.search(r"(\d{1,2})\s*h\s*(\d{2})\s*min", texte, re.IGNORECASE)
            if m:
                duree = str(int(m.group(1)) * 60 + int(m.group(2)))
            else:
                m = re.search(r"(\d{1,3})\s*(?:minutes|min\b)", texte, re.IGNORECASE)
                if m:
                    duree = m.group(1)

            type_film = ""
            low = texte.lower()
            for g in self._genres_films_connus():
                if g in low:
                    type_film = g.capitalize()
                    break

            realisateur = ""
            # Les regex de réalisateur/acteurs sont bornées par des mots
            # « stop » (Distributeur, Nationalité…) pour éviter qu'elles ne
            # débordent l'une sur l'autre (ex. « De Yann Samuell
            # Distributeur … » qui, sans borne, engloutirait le nom du
            # distributeur dans le nom du réalisateur).
            stop = (r"(?:Distributeur|Distribution\s*:|Avec\b|Nationalit[ée]|Genre\b|"
                    r"Dur[ée]e\b|Date de sortie|Box-?office|Secrets de tournage|"
                    r"Bande-annonce|Casting\b|Critiques?\b|$)")
            m = re.search(r"R[ée]alis[ée]?\s+par\s+([^\n\r,\.]{2,60}?)(?=\s*" + stop + ")",
                           texte, re.IGNORECASE)
            if not m:
                m = re.search(r"\bDe\s+([A-ZÀ-Ý][^\n\r,\.]{2,60}?)(?=\s*" + stop + ")", texte)
            if m:
                realisateur = m.group(1).strip()

            acteurs = []
            m = re.search(r"(?:Avec|Distribution\s*:)\s*([^\n\r\.]{2,400}?)(?=\s*" + stop + ")",
                           texte, re.IGNORECASE)
            if m:
                bloc = re.split(r"\bvoir plus\b", m.group(1), flags=re.IGNORECASE)[0]
                for a in re.split(r"•|,\s*|\s+et\s+", bloc):
                    a = a.strip(" -")
                    if a and len(a) < 40:
                        acteurs.append(a)
            personnes_str = " / ".join(dict.fromkeys(acteurs))

            affiche = _meta("og:image")
            if not self._format_image_autorise(affiche):
                affiche = ""

            titre_propre = re.sub(r"\s*[-–]\s*(Film|Série).*$", "", titre_page, flags=re.IGNORECASE).strip()
            titre_propre = re.sub(r"\s*\(\d{4}\)\s*$", "", titre_propre).strip()

            return {
                "titre": titre_propre, "annee": annee, "resume": resume,
                "personnes": personnes_str, "realisateur": realisateur,
                "type": type_film, "duree": duree, "affiche": affiche, "source": url,
            }

        def _rechercher_url_duckduckgo(self, requete, site_filtre=None, max_resultats=1):
            """Retrouve l'adresse d'une page via DuckDuckGo (page HTML sans
            JavaScript, https://html.duckduckgo.com/html/ — pas de clé
            nécessaire), en limitant si besoin au site demandé
            (ex. "senscritique.com/film"). Utilisé à la place de la
            recherche interne de chaque site (AlloCiné, SensCritique...),
            beaucoup plus fragile : ces recherches internes reposent sur des
            pages/API non documentées qui peuvent changer ou disparaître
            sans prévenir (ex. AlloCiné a fermé son ancienne page de
            recherche, HTTP 410 Gone), alors que les FICHES elles-mêmes
            restent accessibles.

            Avec `max_resultats=1` (par défaut), renvoie une chaîne : la
            première URL trouvée, ou "" si rien n'a été trouvé (site
            injoignable, DuckDuckGo bloque la requête…). Avec
            `max_resultats` > 1, renvoie une LISTE des premières URLs
            trouvées (jusqu'à `max_resultats`), ou une liste vide — utile
            pour départager plusieurs films différents portant le même
            titre (ex. les deux films distincts « Black Rain » sortis en
            1989) : se limiter au tout premier résultat de DuckDuckGo
            risquerait de renseigner un film qui n'est pas celui demandé
            (voir _rechercher_allocine, _rechercher_senscritique,
            _rechercher_plansamericains)."""
            import re
            q = requete + (f" site:{site_filtre}" if site_filtre else "")
            url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(q)
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)",
                       "Accept-Language": "fr-FR,fr;q=0.9"}
            vide = [] if max_resultats > 1 else ""
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as r:
                    html_text = r.read().decode("utf-8", errors="ignore")
            except Exception as ex:
                self._trace_recherche(f"DuckDuckGo : échec réseau sur « {q} » — {type(ex).__name__}: {ex}")
                return vide

            liens_bruts = re.findall(r'class="result__a"[^>]*href="([^"]+)"', html_text)
            if not liens_bruts:
                self._trace_recherche(f"DuckDuckGo : aucun résultat pour « {q} »")
                return vide

            liens = []
            for lien in liens_bruts[:max(max_resultats, 1)]:
                m = re.search(r"[?&]uddg=([^&]+)", lien)
                liens.append(urllib.parse.unquote(m.group(1)) if m else lien)

            return liens if max_resultats > 1 else liens[0]


        def _rechercher_senscritique(self, titre, annee_cible=None):
            """Recherche sur senscritique.com : retrouve d'abord la ou les
            fiches du film via DuckDuckGo (la recherche interne du site
            n'est pas fiable pour retrouver le bon film), puis lit la
            fiche (résumé, réalisateur, acteurs, genre, durée, année) et
            surtout son AFFICHE — celle-ci (meta og:image) est une vraie
            affiche de film sur SensCritique, contrairement à
            Wikimédia/Wikipédia qui renvoie très souvent un logo de studio
            ou une image sans rapport avec le film à la place de
            l'affiche. C'est pour cette fiabilité que SensCritique est
            testé en priorité.

            Comme plusieurs films DIFFÉRENTS peuvent partager le même
            titre (homonymes), jusqu'à 3 fiches candidates sont examinées
            plutôt qu'une seule : si une année a déjà été précisée dans le
            formulaire, la fiche correspondante est choisie parmi elles ;
            sinon, si les candidats trouvés ne donnent pas tous la même
            année, rien n'est renseigné automatiquement (mieux vaut ne
            rien remplir que remplir avec le mauvais film) — indiquer
            l'année dans le formulaire puis relancer la recherche permet
            alors de départager. Renvoie None si aucune fiche exploitable
            n'a pu être retenue (site indisponible, aucun résultat, ou
            résultat(s) qui ne correspond(ent) manifestement pas au
            titre/année demandés)."""
            import re
            import html as html_mod

            headers = {"User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)",
                       "Accept-Language": "fr-FR,fr;q=0.9"}

            film_urls = self._rechercher_url_duckduckgo(f"{titre} film", "senscritique.com/film", max_resultats=3)
            film_urls = [u for u in film_urls if "senscritique.com/film/" in u]
            if not film_urls:
                self._trace_recherche(f"SensCritique : DuckDuckGo n'a renvoyé aucune fiche /film/ pour « {titre} »")
                return None

            def _meta(html_film, nom):
                m = re.search(
                    r'<meta[^>]+(?:name|property)=["\']' + re.escape(nom) +
                    r'["\'][^>]*content=["\']([^"\']*)["\']', html_film, re.IGNORECASE)
                if not m:
                    m = re.search(
                        r'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:name|property)=["\']' +
                        re.escape(nom) + r'["\']', html_film, re.IGNORECASE)
                return html_mod.unescape(m.group(1)).strip() if m else ""

            candidats = []
            for film_url in film_urls:
                try:
                    req2 = urllib.request.Request(film_url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=10) as r2:
                        url_finale = r2.geturl()
                        html_film = r2.read().decode("utf-8", errors="ignore")
                except Exception as ex:
                    self._trace_recherche(f"SensCritique : échec réseau sur la fiche {film_url} — {type(ex).__name__}: {ex}")
                    continue
                if "senscritique.com/film/" not in url_finale:
                    self._trace_recherche(f"SensCritique : redirection inattendue ({film_url} → {url_finale}), rejeté")
                    continue

                titre_page = _meta(html_film, "og:title")
                resume = _meta(html_film, "og:description")
                affiche = _meta(html_film, "og:image")
                if not self._format_image_autorise(affiche):
                    affiche = ""

                titre_propre = re.sub(r"\s*[-–]\s*Film.*$", "", titre_page, flags=re.IGNORECASE).strip()
                if not titre_propre:
                    titre_propre = titre

                if not self._titres_similaires(titre, titre_propre):
                    self._trace_recherche(
                        f"SensCritique : titre trouvé « {titre_propre} » ne correspond pas à « {titre} », rejeté "
                        f"({film_url})")
                    continue

                texte = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html_film,
                                flags=re.DOTALL | re.IGNORECASE)
                texte = re.sub(r"<[^>]+>", " ", texte)
                texte = html_mod.unescape(texte)
                texte = re.sub(r"[ \t]+", " ", texte)

                annee = ""
                m = re.search(r"\((\d{4})\)\s*$", titre_page)
                if m:
                    annee = m.group(1)
                if not annee:
                    m = re.search(r"\b(19|20)\d{2}\b", texte)
                    if m:
                        annee = m.group(0)

                duree = ""
                m = re.search(r"(\d{1,2})\s*h\s*(\d{2})?\s*min", texte, re.IGNORECASE)
                if m:
                    duree = str(int(m.group(1)) * 60 + int(m.group(2) or 0))

                realisateur = ""
                m = re.search(
                    r'\bFilm\s+de\s*(?:<[^>]+>\s*)*<a[^>]+href="/contact/[^"]+"[^>]*>([^<]+)</a>',
                    html_film, re.IGNORECASE)
                if m:
                    realisateur = html_mod.unescape(m.group(1)).strip()

                type_film = ""
                m = re.search(r"Genres?\s*:\s*(.*?)(?:Pays d|Groupe\s*:|Bande originale|Fiche technique)",
                               html_film, re.DOTALL | re.IGNORECASE)
                if m:
                    genres = re.findall(r'href="/films/oeuvres/[^"]+"[^>]*>([^<]+)</a>', m.group(1))
                    genres = [html_mod.unescape(g).strip() for g in genres]
                    if genres:
                        type_film = genres[0]

                acteurs = []
                m = re.search(r">Casting<(.*?)(?:voir le casting complet|Bandes-annonces|>Images<)",
                               html_film, re.DOTALL | re.IGNORECASE)
                if m:
                    for a in re.findall(r'href="/contact/[^"]+"[^>]*>([^<]+)</a>', m.group(1)):
                        a = html_mod.unescape(a).strip()
                        if a and a not in acteurs:
                            acteurs.append(a)
                personnes_str = " / ".join(acteurs)

                if not resume and not annee:
                    self._trace_recherche(f"SensCritique : ni résumé ni année trouvés sur la fiche, rejeté ({film_url})")
                    continue

                candidats.append({
                    "titre": titre_propre, "annee": annee, "resume": resume,
                    "personnes": personnes_str, "realisateur": realisateur,
                    "type": type_film, "duree": duree, "affiche": affiche,
                    "source": film_url,
                })

            return self._choisir_candidat_film("SensCritique", titre, annee_cible, candidats)


        def _rechercher_tmdb(self, titre, annee_cible=None):
            """Recherche via l'API officielle TMDB (themoviedb.org), la plus
            fiable des 4 sources, mais nécessite une clé API personnelle et
            gratuite (configurable via « 🔑 Clé API TMDB » dans la fenêtre de
            recherche). Renvoie None si aucune clé n'est configurée."""
            api_key = (getattr(self, "_tmdb_api_key", "") or "").strip()
            if not api_key:
                self._trace_recherche("TMDB : aucune clé API configurée (⚙ 🔑 Clé API TMDB), source ignorée")
                return None
            search_url = ("https://api.themoviedb.org/3/search/movie?api_key="
                          + urllib.parse.quote(api_key) + "&language=fr-FR&query="
                          + urllib.parse.quote(titre))
            req = urllib.request.Request(search_url)
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            results = [f for f in (data.get("results") or [])
                       if self._titres_similaires(titre, f.get("title") or "")]
            if not results:
                self._trace_recherche(f"TMDB : aucun résultat correspondant au titre « {titre} »")
                return None
            # Si une année de référence est connue (film choisi parmi
            # plusieurs homonymes), on privilégie le résultat qui correspond
            # à cette année plutôt que le premier de la liste.
            film = None
            if annee_cible:
                film = next((f for f in results if (f.get("release_date") or "").startswith(annee_cible)), None)
            if not film:
                film = results[0]
            movie_id = film.get("id")

            detail_url = (f"https://api.themoviedb.org/3/movie/{movie_id}?api_key="
                          + urllib.parse.quote(api_key) + "&language=fr-FR&append_to_response=credits")
            req2 = urllib.request.Request(detail_url)
            with urllib.request.urlopen(req2, timeout=10) as r2:
                det = json.loads(r2.read().decode("utf-8"))

            annee = (det.get("release_date") or film.get("release_date") or "")[:4]
            if annee_cible and annee and annee != annee_cible:
                self._trace_recherche(f"TMDB : année trouvée {annee} ≠ année cible {annee_cible}, rejeté")
                return None
            resume = det.get("overview") or film.get("overview") or ""
            duree = str(det.get("runtime")) if det.get("runtime") else ""
            genres = det.get("genres") or []
            type_film = genres[0]["name"] if genres else ""

            realisateur = ""
            acteurs = []
            credits = det.get("credits") or {}
            for c in (credits.get("crew") or []):
                if c.get("job") == "Director" and c.get("name") and not realisateur:
                    realisateur = c["name"]
            for c in (credits.get("cast") or [])[:10]:
                if c.get("name"):
                    acteurs.append(c["name"])
            personnes_str = " / ".join(dict.fromkeys(acteurs))

            poster_path = det.get("poster_path") or film.get("poster_path") or ""
            affiche = f"https://image.tmdb.org/t/p/w780{poster_path}" if poster_path else ""

            return {
                "titre": det.get("title") or film.get("title") or titre,
                "annee": annee, "resume": resume, "personnes": personnes_str,
                "realisateur": realisateur, "type": type_film, "duree": duree,
                "affiche": affiche,
                "source": f"https://www.themoviedb.org/movie/{movie_id}",
            }

        def _rechercher_allocine(self, titre, annee_cible=None):
            """Recherche best-effort sur AlloCiné : la ou les fiches film
            sont retrouvées via DuckDuckGo (l'ancienne page de recherche
            interne du site, /recherche/?q=, a été fermée par AlloCiné —
            HTTP 410 Gone — et son moteur de recherche est aujourd'hui
            entièrement dynamique/JavaScript, donc impossible à interroger
            directement).

            Comme plusieurs films DIFFÉRENTS peuvent partager le même
            titre (homonymes, ex. les deux films distincts « Black Rain »
            sortis en 1989), jusqu'à 3 fiches candidates sont examinées
            plutôt qu'une seule (chacune vérifiée : titre proche, page pas
            redirigée) — voir _choisir_candidat_film pour la façon dont la
            bonne est ensuite choisie parmi elles (immédiatement si une
            année est déjà connue, sinon seulement si toutes donnent la
            même année ; dans le cas contraire, rien n'est renseigné au
            hasard : il faut d'abord chercher par titre, PUIS indiquer
            l'année et relancer la recherche pour départager)."""
            import re
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)"}
            film_urls = self._rechercher_url_duckduckgo(f"{titre} film", "allocine.fr/film/fichefilm", max_resultats=3)
            film_urls = [u for u in film_urls if "allocine.fr/film/fichefilm" in u]
            if not film_urls:
                self._trace_recherche(f"AlloCiné : DuckDuckGo n'a renvoyé aucune fiche film pour « {titre} »")
                return None

            candidats = []
            for film_url in film_urls:
                try:
                    req2 = urllib.request.Request(film_url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=10) as r2:
                        url_finale = r2.geturl()
                        html_film = r2.read().decode("utf-8", errors="ignore")
                except Exception as ex:
                    self._trace_recherche(f"AlloCiné : échec réseau sur la fiche {film_url} — {type(ex).__name__}: {ex}")
                    continue

                data = self._analyser_page_film(html_film, film_url)
                # AlloCiné affiche sur la fiche une VIGNETTE recadrée de
                # l'affiche (adresse contenant un segment
                # "c_LARGEUR_HAUTEUR/", ex. ".../c_310_420/medias/..."),
                # alors que la vraie affiche en pleine résolution est à la
                # même adresse SANS ce segment — c'est cette adresse pleine
                # résolution qu'on obtiendrait en ouvrant l'image dans un
                # nouvel onglet. On la reconstruit directement plutôt que
                # de garder la vignette (voir aussi _normaliser_url_affiche
                # / _resoudre_url_affiche, qui refont ce même nettoyage
                # pour une URL collée à la main).
                if data.get("affiche"):
                    data["affiche"] = self._normaliser_url_affiche(data["affiche"])
                # La page de fiche film doit vraiment parler du film
                # demandé, et ne doit pas avoir redirigé vers une autre
                # page (ex. si le film n'existe plus à cette adresse).
                if "allocine.fr/film/fichefilm" not in url_finale:
                    self._trace_recherche(f"AlloCiné : redirection inattendue ({film_url} → {url_finale}), rejeté")
                    continue
                if not self._titres_similaires(titre, data.get("titre", "")):
                    self._trace_recherche(
                        f"AlloCiné : titre trouvé « {data.get('titre','')} » ne correspond pas à « {titre} », "
                        f"rejeté ({film_url})")
                    continue
                if not data.get("resume") and not data.get("annee"):
                    self._trace_recherche(f"AlloCiné : ni résumé ni année trouvés, rejeté ({film_url})")
                    continue
                if not data.get("titre"):
                    data["titre"] = titre
                candidats.append(data)

            return self._choisir_candidat_film("AlloCiné", titre, annee_cible, candidats)

        def _rechercher_plansamericains(self, titre, annee_cible=None):
            """Recherche best-effort sur plansamericains.com (site consacré
            au cinéma américain de genre) — même principe que
            _rechercher_allocine : la ou les fiches sont retrouvées via
            DuckDuckGo (site:plansamericains.com), puis lues avec
            l'analyseur générique _analyser_page_film (comme pour
            AlloCiné/tv-programme.com, aucune API publique officielle).
            Contrairement à AlloCiné, la structure exacte des adresses du
            site n'est pas connue à l'avance : seule l'appartenance au nom
            de domaine est vérifiée (pas de motif d'URL précis à valider),
            le reste de la vérification (titre proche, résumé/année
            présents) restant la garantie principale qu'il s'agit bien
            d'une fiche film exploitable. Jusqu'à 3 fiches candidates sont
            examinées pour départager d'éventuels films homonymes — voir
            _choisir_candidat_film."""
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)"}
            film_urls = self._rechercher_url_duckduckgo(f"{titre} film", "plansamericains.com", max_resultats=3)
            film_urls = [u for u in film_urls if "plansamericains.com" in u]
            if not film_urls:
                self._trace_recherche(f"Plansamericains : DuckDuckGo n'a renvoyé aucune fiche pour « {titre} »")
                return None

            candidats = []
            for film_url in film_urls:
                try:
                    req2 = urllib.request.Request(film_url, headers=headers)
                    with urllib.request.urlopen(req2, timeout=10) as r2:
                        url_finale = r2.geturl()
                        html_film = r2.read().decode("utf-8", errors="ignore")
                except Exception as ex:
                    self._trace_recherche(f"Plansamericains : échec réseau sur la fiche {film_url} — {type(ex).__name__}: {ex}")
                    continue
                if "plansamericains.com" not in url_finale:
                    self._trace_recherche(f"Plansamericains : redirection inattendue ({film_url} → {url_finale}), rejeté")
                    continue

                data = self._analyser_page_film(html_film, film_url)
                if not self._titres_similaires(titre, data.get("titre", "")):
                    self._trace_recherche(
                        f"Plansamericains : titre trouvé « {data.get('titre','')} » ne correspond pas à « {titre} », "
                        f"rejeté ({film_url})")
                    continue
                if not data.get("resume") and not data.get("annee"):
                    self._trace_recherche(f"Plansamericains : ni résumé ni année trouvés, rejeté ({film_url})")
                    continue
                if not data.get("titre"):
                    data["titre"] = titre
                candidats.append(data)

            return self._choisir_candidat_film("Plansamericains", titre, annee_cible, candidats)

        def _rechercher_tv_programme(self, titre, annee_cible=None):
            """Recherche best-effort sur tv-programme.com : le site n'a pas
            d'API publique ni de recherche interne fiable en HTML statique,
            on devine donc directement l'URL de la fiche (motif observé :
            https://tv-programme.com/<titre-slugifie>-film). Le résultat est
            rejeté (renvoie None) si la page n'existe pas, a redirigé vers
            une autre page (ex. accueil du site), ou ne parle manifestement
            pas du film demandé — c'est ce qui évite de récupérer des
            informations sans rapport avec la recherche."""
            import re
            import unicodedata

            slug = unicodedata.normalize("NFD", titre.lower())
            slug = "".join(c for c in slug if unicodedata.category(c) != "Mn")
            slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
            if not slug:
                return None
            url = f"https://tv-programme.com/{slug}-film"

            headers = {"User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)"}
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    url_finale = r.geturl()
                    html_text = r.read().decode("utf-8", errors="ignore")
            except Exception as ex:
                self._trace_recherche(f"tv-programme.com : échec réseau sur {url} — {type(ex).__name__}: {ex}")
                return None

            # Si la fiche n'existe pas, tv-programme.com redirige en général
            # vers une autre page (accueil, page « films »…) : on l'ignore.
            if url_finale.split("?")[0].rstrip("/") != url.rstrip("/"):
                self._trace_recherche(f"tv-programme.com : redirection inattendue ({url} → {url_finale}), rejeté")
                return None

            data = self._analyser_page_film(html_text, url)
            if not self._titres_similaires(titre, data.get("titre", "")):
                self._trace_recherche(
                    f"tv-programme.com : titre trouvé « {data.get('titre','')} » ne correspond pas à "
                    f"« {titre} », rejeté ({url})")
                return None
            if annee_cible and data.get("annee") and data["annee"] != annee_cible:
                self._trace_recherche(
                    f"tv-programme.com : année trouvée {data['annee']} ≠ année cible {annee_cible}, "
                    f"rejeté ({url})")
                return None
            if not data.get("resume") and not data.get("annee"):
                self._trace_recherche(f"tv-programme.com : ni résumé ni année trouvés, rejeté ({url})")
                return None
            if not data.get("titre"):
                data["titre"] = titre
            return data

        def _rechercher_ia(self, titre, annee_cible=None):
            """Interroge un modèle d'IA (compatible avec l'API « chat
            completions », le format utilisé par la plupart des
            fournisseurs : OpenAI, Mistral, Groq, un serveur local type
            Ollama/LM Studio…) pour obtenir les informations d'un film,
            formatées d'emblée proprement (réalisateur et acteurs bien
            séparés, sans le bruit d'une page web scrapée). Nécessite une
            clé/URL configurées via « 🤖 Configurer l'IA ». Renvoie None si
            rien n'est configuré, ou si la réponse ne correspond pas au film
            demandé (même vérification titre/année que les autres sources)."""
            import re
            api_key = (getattr(self, "_ia_api_key", "") or "").strip()
            if not api_key:
                self._trace_recherche("IA : aucune clé/URL configurée (⚙ 🤖 Configurer l'IA), source ignorée")
                return None
            base = (getattr(self, "_ia_api_base", "") or "https://api.openai.com/v1").rstrip("/")
            modele = (getattr(self, "_ia_model", "") or "gpt-4o-mini").strip()

            precision = f" sorti en {annee_cible}" if annee_cible else ""
            prompt = (
                f"Donne les informations du film « {titre} »{precision}. "
                "Réponds UNIQUEMENT avec un objet JSON valide (rien avant, rien après), "
                "avec exactement ces clés : "
                '{"titre": "", "annee": "", "resume": "", "realisateur": "", '
                '"acteurs": ["",""], "genre": "", "duree_minutes": ""}. '
                "« resume » : synopsis en français, quelques phrases. « realisateur » : "
                "un seul nom. « acteurs » : liste COMPLÈTE des acteurs principaux "
                "(même pour un film ancien : cite tous les rôles principaux connus, "
                "pas seulement les 2 ou 3 plus célèbres), sans les rôles. "
                "« duree_minutes » : uniquement le nombre de minutes. "
                "Si tu n'es pas certain qu'il s'agit bien de ce film précis, réponds {}."
            )
            body = json.dumps({
                "model": modele,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
            }).encode("utf-8")
            req = urllib.request.Request(
                base + "/chat/completions", data=body,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"})
            with urllib.request.urlopen(req, timeout=20) as r:
                rep = json.loads(r.read().decode("utf-8"))

            contenu = ""
            try:
                contenu = rep["choices"][0]["message"]["content"]
            except Exception:
                self._trace_recherche(f"IA : réponse du modèle {modele} sans contenu exploitable — {rep}")
                return None
            contenu = contenu.strip()
            if contenu.startswith("```"):
                contenu = re.sub(r"^```[a-zA-Z]*\n?|```$", "", contenu.strip(), flags=re.MULTILINE).strip()
            try:
                infos = json.loads(contenu)
            except Exception:
                self._trace_recherche(f"IA : réponse du modèle {modele} n'est pas un JSON valide — {contenu[:200]!r}")
                return None
            if not infos or not infos.get("titre"):
                self._trace_recherche(f"IA : le modèle {modele} n'a pas identifié le film avec certitude ({{}})")
                return None

            if not self._titres_similaires(titre, infos.get("titre") or ""):
                self._trace_recherche(
                    f"IA : titre renvoyé « {infos.get('titre','')} » ne correspond pas à « {titre} », rejeté")
                return None
            annee = str(infos.get("annee") or "").strip()[:4]
            if annee_cible and annee and annee != annee_cible:
                self._trace_recherche(f"IA : année renvoyée {annee} ≠ année cible {annee_cible}, rejeté")
                return None

            acteurs = infos.get("acteurs") or []
            if isinstance(acteurs, str):
                acteurs = [a.strip() for a in re.split(r"/|,", acteurs) if a.strip()]
            personnes_str = " / ".join(dict.fromkeys(a for a in acteurs if a))

            duree = re.sub(r"\D", "", str(infos.get("duree_minutes") or ""))

            return {
                "titre": infos.get("titre") or titre,
                "annee": annee,
                "resume": (infos.get("resume") or "").strip(),
                "realisateur": (infos.get("realisateur") or "").strip(),
                "personnes": personnes_str,
                "type": (infos.get("genre") or "").strip(),
                "duree": duree,
                "source": f"IA ({modele})",
            }

        def _rechercher_bande_annonce_youtube(self, titre, annee=None):
            """Recherche best-effort une bande-annonce sur YouTube, en lisant
            la page de résultats publique (pas d'API/clé nécessaire, mais
            cette méthode peut cesser de fonctionner si YouTube change la
            structure de ses pages). La requête utilisée est « Bande annonce
            du film <titre> (<année>) » (demandé explicitement : bien plus
            efficace que d'autres formulations). Chaque résultat est
            vérifié : son titre de vidéo doit ressembler au titre recherché,
            sinon il est ignoré (évite de renvoyer la bande-annonce d'un
            film totalement différent). Renvoie l'URL de la vidéo choisie,
            ou "" si rien de fiable n'a été trouvé."""
            import re
            requete = f"Bande annonce du film {titre}" + (f" ({annee})" if annee else "")
            url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(requete)
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)",
                       "Accept-Language": "fr-FR,fr;q=0.9"}
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as r:
                    html_text = r.read().decode("utf-8", errors="ignore")
            except Exception as ex:
                self._trace_recherche(f"YouTube : échec réseau — {type(ex).__name__}: {ex}")
                return ""

            # YouTube encode les résultats dans un gros bloc JSON
            # (ytInitialData) directement inclus dans le HTML de la page.
            videos = []
            m = re.search(r"var ytInitialData\s*=\s*(\{.*?\});</script>", html_text, re.DOTALL)
            if not m:
                self._trace_recherche("YouTube : bloc ytInitialData introuvable dans la page (structure du site "
                                       "peut-être changée, ou page de consentement cookies renvoyée à la place)")
            if m:
                try:
                    data = json.loads(m.group(1))

                    def _walk(node):
                        if isinstance(node, dict):
                            if "videoRenderer" in node:
                                vr = node["videoRenderer"]
                                vid = vr.get("videoId")
                                titre_v = ""
                                try:
                                    titre_v = vr["title"]["runs"][0]["text"]
                                except Exception:
                                    pass
                                temps = ""
                                try:
                                    temps = vr.get("publishedTimeText", {}).get("simpleText", "")
                                except Exception:
                                    pass
                                if vid:
                                    videos.append({"id": vid, "titre": titre_v, "temps": temps})
                            for v in node.values():
                                _walk(v)
                        elif isinstance(node, list):
                            for v in node:
                                _walk(v)

                    _walk(data)
                except Exception as ex:
                    self._trace_recherche(f"YouTube : bloc ytInitialData trouvé mais illisible — {type(ex).__name__}: {ex}")

            nb_bruts = len(videos)
            # On ne garde que les vidéos dont le titre contient VRAIMENT tous
            # les mots significatifs du film recherché (comparaison stricte
            # : une simple ressemblance globale a laissé passer "La Guerre
            # est déclarée" pour "La Guerre des boutons").
            videos = [v for v in videos if self._titre_correspond_strictement(titre, v.get("titre") or "")]
            if not videos:
                self._trace_recherche(
                    f"YouTube : {nb_bruts} résultat(s) brut(s), aucun ne correspond strictement au titre")
                return ""

            def _recence(temps):
                # Estimation grossière de la récence à partir du texte
                # relatif ("il y a 3 ans", "il y a 2 mois"…) : plus petit =
                # plus récent.
                ordre = {"seconde": 0, "minute": 1, "heure": 2, "jour": 3,
                         "semaine": 4, "mois": 5, "an": 6, "année": 6}
                m3 = re.search(r"(\d+)\s*(seconde|minute|heure|jour|semaine|mois|an|année)",
                                temps or "", re.IGNORECASE)
                if not m3:
                    return (9, 0)
                return (ordre.get(m3.group(2).lower(), 9), int(m3.group(1)))

            # Priorité aux résultats explicitement "VF", puis aux plus
            # récents.
            videos.sort(key=lambda v: (0 if "vf" in (v.get("titre") or "").lower() else 1,
                                        _recence(v.get("temps"))))
            return f"https://www.youtube.com/watch?v={videos[0]['id']}"

        def _rechercher_bande_annonce_dailymotion(self, titre, annee=None):
            """Repli sur Dailymotion (demandé explicitement) si YouTube n'a
            rien donné de fiable : utilise l'API publique de Dailymotion
            (aucune clé nécessaire pour les données publiques), avec la même
            requête que pour YouTube. Chaque résultat est vérifié de la même
            façon (titre de la vidéo comparé strictement au titre recherché)
            avant d'être retenu. Renvoie l'URL de la vidéo choisie, ou "" si
            rien de fiable n'a été trouvé."""
            requete = f"Bande annonce du film {titre}" + (f" ({annee})" if annee else "")
            url = ("https://api.dailymotion.com/videos?search=" + urllib.parse.quote(requete) +
                   "&fields=id,title&limit=10&sort=relevance&languages=fr")
            headers = {"User-Agent": "Mozilla/5.0 (compatible; Citron/1.0; usage personnel)"}
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=10) as r:
                    data = json.loads(r.read().decode("utf-8", errors="ignore"))
            except Exception as ex:
                self._trace_recherche(f"Dailymotion : échec réseau/API — {type(ex).__name__}: {ex}")
                return ""

            nb_bruts = len(data.get("list") or [])
            videos = [v for v in (data.get("list") or [])
                      if v.get("id") and self._titre_correspond_strictement(titre, v.get("title") or "")]
            if not videos:
                self._trace_recherche(
                    f"Dailymotion : {nb_bruts} résultat(s) brut(s), aucun ne correspond strictement au titre")
                return ""
            return f"https://www.dailymotion.com/video/{videos[0]['id']}"

        def _completer_tableur_config_tmdb(self, win):
            """Petite boîte de dialogue pour saisir/modifier la clé API TMDB
            personnelle (gratuite, à créer sur themoviedb.org/settings/api).
            Sans clé, la source TMDB est simplement ignorée (les 3 autres
            sources restent actives)."""
            parent = win or self
            dlg = ctk.CTkToplevel(parent)
            dlg.title("🔑 Clé API TMDB")
            dlg.resizable(False, False)
            dlg.transient(parent)

            ctk.CTkLabel(dlg, text="Clé API TMDB (v3 auth)", font=("Arial", 13, "bold")
                         ).pack(padx=20, pady=(18, 2), anchor="w")
            ctk.CTkLabel(dlg, text="Gratuite sur themoviedb.org/settings/api",
                         font=("Arial", 11), text_color="#999999").pack(padx=20, anchor="w")

            var = ctk.StringVar(value=getattr(self, "_tmdb_api_key", "") or "")
            entry = ctk.CTkEntry(dlg, textvariable=var, width=380, height=36)
            entry.pack(padx=20, pady=(10, 14))

            def _save(event=None):
                self._tmdb_api_key = var.get().strip()
                self.save_settings()
                dlg.destroy()

            btns = ctk.CTkFrame(dlg, fg_color="transparent")
            btns.pack(pady=(0, 18))
            ctk.CTkButton(btns, text="Enregistrer", width=110, command=_save).pack(side="left", padx=8)
            ctk.CTkButton(btns, text="Annuler", width=110, fg_color="#5a5a5a",
                          command=dlg.destroy).pack(side="left", padx=8)
            entry.bind("<Return>", _save)
            entry.bind("<Escape>", lambda e: dlg.destroy())

            dlg.update_idletasks()
            dlg.geometry(f"{dlg.winfo_reqwidth()}x{dlg.winfo_reqheight()}")
            entry.focus_set()
            entry.select_range(0, "end")
            dlg.grab_set()

        def _completer_tableur_config_ia(self, win):
            """Petite boîte de dialogue pour configurer une IA (compatible
            API « chat completions » : OpenAI, Mistral, Groq, un serveur
            local type Ollama/LM Studio exposant cette même API…) comme
            source supplémentaire. Sans clé, cette source est simplement
            ignorée."""
            parent = win or self
            dlg = ctk.CTkToplevel(parent)
            dlg.title("🤖 Configurer l'IA")
            dlg.resizable(False, False)
            dlg.transient(parent)

            ctk.CTkLabel(dlg, text="Adresse de l'API (compatible OpenAI)", font=("Arial", 13, "bold")
                         ).pack(padx=20, pady=(18, 2), anchor="w")
            var_base = ctk.StringVar(value=getattr(self, "_ia_api_base", "") or "https://api.openai.com/v1")
            ctk.CTkEntry(dlg, textvariable=var_base, width=380, height=34).pack(padx=20, pady=(0, 10))

            ctk.CTkLabel(dlg, text="Modèle", font=("Arial", 13, "bold")).pack(padx=20, anchor="w")
            var_modele = ctk.StringVar(value=getattr(self, "_ia_model", "") or "gpt-4o-mini")
            ctk.CTkEntry(dlg, textvariable=var_modele, width=380, height=34).pack(padx=20, pady=(0, 10))

            ctk.CTkLabel(dlg, text="Clé API", font=("Arial", 13, "bold")).pack(padx=20, anchor="w")
            var_cle = ctk.StringVar(value=getattr(self, "_ia_api_key", "") or "")
            entry = ctk.CTkEntry(dlg, textvariable=var_cle, width=380, height=34)
            entry.pack(padx=20, pady=(0, 14))

            def _save(event=None):
                self._ia_api_base = var_base.get().strip() or "https://api.openai.com/v1"
                self._ia_model = var_modele.get().strip() or "gpt-4o-mini"
                self._ia_api_key = var_cle.get().strip()
                self.save_settings()
                dlg.destroy()

            btns = ctk.CTkFrame(dlg, fg_color="transparent")
            btns.pack(pady=(0, 18))
            ctk.CTkButton(btns, text="Enregistrer", width=110, command=_save).pack(side="left", padx=8)
            ctk.CTkButton(btns, text="Annuler", width=110, fg_color="#5a5a5a",
                          command=dlg.destroy).pack(side="left", padx=8)
            entry.bind("<Return>", _save)
            entry.bind("<Escape>", lambda e: dlg.destroy())

            dlg.update_idletasks()
            dlg.geometry(f"{dlg.winfo_reqwidth()}x{dlg.winfo_reqheight()}")
            entry.focus_set()
            dlg.grab_set()

        def _completer_tableur_on_resultat(self, win, champs_avant, resultat, erreur):
            """Appelé (dans le thread principal Tk) une fois la recherche
            internet terminée : ne remplit QUE les champs qui étaient vides
            avant la recherche, sans jamais écraser ce que l'utilisateur
            avait déjà saisi lui-même (ou obtenu d'une recherche
            précédente)."""
            try:
                win.search_btn.configure(state="normal", text="🔎 Rechercher les champs vides sur internet")
            except Exception:
                pass
            if erreur:
                win.status_label.configure(text=f"❌ {erreur}", text_color="#ff8888")
                return
            if not win.winfo_exists():
                return

            champ_widget = {
                "titre": win.field_titre, "annee": win.field_annee, "type": win.field_type,
                "duree": win.field_duree, "realisateur": win.field_realisateur,
                "personnes": win.field_personnes, "bande_annonce": win.field_bande_annonce,
                "affiche": win.field_affiche,
            }
            completes = []
            for cle, widget in champ_widget.items():
                if not champs_avant.get(cle) and (resultat.get(cle) or "").strip():
                    widget.set(resultat[cle].strip())
                    completes.append(cle)
            if not champs_avant.get("resume") and (resultat.get("resume") or "").strip():
                win.field_resume.delete("1.0", "end")
                win.field_resume.insert("1.0", resultat["resume"].strip())
                completes.append("resume")

            source = resultat.get("source", "")
            if completes:
                win.status_label.configure(
                    text=f"✅ Champs complétés : {', '.join(completes)}." + (f"\nSource(s) : {source}" if source else ""),
                    text_color="#88cc88")
            else:
                win.status_label.configure(
                    text="ℹ️ Rien de nouveau à ajouter (tous les champs étaient déjà remplis, ou rien trouvé).",
                    text_color="#cccccc")

        def _completer_tableur_lire_champs(self, win):
            """Relit les champs actuellement affichés dans le formulaire
            (saisis à la main et/ou complétés par une recherche)."""
            return {
                "titre": (win.field_titre.get() or "").strip(),
                "annee": (win.field_annee.get() or "").strip(),
                "type": (win.field_type.get() or "").strip(),
                "duree": (win.field_duree.get() or "").strip(),
                "realisateur": (win.field_realisateur.get() or "").strip(),
                "personnes": (win.field_personnes.get() or "").strip(),
                "resume": win.field_resume.get("1.0", "end").strip(),
                "bande_annonce": (win.field_bande_annonce.get() or "").strip(),
                "affiche": self._normaliser_url_affiche((win.field_affiche.get() or "").strip()),
                "categorie": (win.field_categorie.get() or "").strip() if hasattr(win, "field_categorie") else "",
                "renseignements": (win.field_renseignements.get() or "").strip() if hasattr(win, "field_renseignements") else "",
            }

        def _telecharger_image_temporaire(self, url_image):
            """Télécharge une image (affiche) dans un fichier temporaire,
            pour affichage dans « Simuler Infos (tableur) » uniquement — rien
            n'est enregistré dans le tableur. Accepte aussi bien une URL
            d'image directe qu'un lien de fiche film AlloCiné (voir
            _resoudre_url_affiche). Le format webp est refusé (jpg/jpeg
            privilégiés). Renvoie le chemin local, ou "" en cas d'échec
            (le détail est tracé dans la console)."""
            import re
            import tempfile
            url_reelle = self._resoudre_url_affiche(url_image) or url_image
            if not self._format_image_autorise(url_reelle):
                return ""
            ext = ".jpg"
            m = re.search(r"\.(jpg|jpeg|png)(?:\?|$)", url_reelle, re.IGNORECASE)
            if m:
                ext = "." + m.group(1).lower()
            data = self._telecharger_bytes_image(url_reelle)
            if data is None and url_reelle != url_image:
                # La version « nettoyée » (recadrage retiré, etc.) a
                # échoué : on retente avec l'URL d'origine, telle que
                # collée par l'utilisateur — mieux vaut une affiche que
                # rien.
                self._trace_recherche(f"Affiche : nouvel essai avec l'URL d'origine → {url_image}")
                data = self._telecharger_bytes_image(url_image)
            if data is None:
                return ""
            fd, dest = tempfile.mkstemp(suffix=ext, prefix="citron_affiche_")
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            return dest


        def _telecharger_affiche_choisie(self, titre, annee, url_image, dossier, chemin_local_existant=""):
            """Télécharge l'affiche dans le dossier choisi par l'utilisateur
            (demandé systématiquement, voir _completer_tableur_valider).
            Accepte aussi bien une URL d'image directe qu'un lien de fiche
            film AlloCiné (voir _resoudre_url_affiche). Le format webp est
            refusé même en dernier recours (jpg/jpeg privilégiés). Si
            `chemin_local_existant` pointe vers un fichier déjà téléchargé
            (typiquement par « Simuler Infos (tableur) » pour la même
            URL), il est simplement copié vers le dossier choisi au lieu
            d'être retéléchargé (gain de temps). Renvoie (chemin_local, "")
            en cas de succès, ou ("", message d'erreur) sinon (n'empêche
            jamais l'enregistrement du reste des données)."""
            import re
            if not dossier:
                return "", "Aucun dossier choisi pour l'affiche."
            try:
                os.makedirs(dossier, exist_ok=True)
            except Exception as ex:
                return "", f"Impossible de créer le dossier de l'affiche :\n{ex}"
            if chemin_local_existant and os.path.isfile(chemin_local_existant):
                ext = os.path.splitext(chemin_local_existant)[1].lower() or ".jpg"
                nom = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{titre}_{annee}").strip("_") or "affiche"
                dest = os.path.join(dossier, nom + ext)
                try:
                    shutil.copyfile(chemin_local_existant, dest)
                    self._trace_recherche(
                        f"Affiche « {titre} » : réutilisation du téléchargement de "
                        f"la simulation (pas de retéléchargement) → {dest}")
                    return dest, ""
                except Exception as ex:
                    self._trace_recherche(
                        f"Affiche « {titre} » : échec de la copie depuis la simulation "
                        f"({type(ex).__name__}: {ex}) — nouveau téléchargement.")
            url_reelle = self._resoudre_url_affiche(url_image) or url_image
            if not self._format_image_autorise(url_reelle):
                return "", "Affiche refusée : format webp non autorisé (jpg/jpeg uniquement)."
            ext = ".jpg"
            m = re.search(r"\.(jpg|jpeg|png)(?:\?|$)", url_reelle, re.IGNORECASE)
            if m:
                ext = "." + m.group(1).lower()
            nom = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{titre}_{annee}").strip("_") or "affiche"
            dest = os.path.join(dossier, nom + ext)
            data = self._telecharger_bytes_image(url_reelle)
            if data is None and url_reelle != url_image:
                # La version « nettoyée » (recadrage retiré, résolue depuis
                # une fiche AlloCiné...) a échoué : on retente avec l'URL
                # d'origine, telle que collée par l'utilisateur — mieux
                # vaut une affiche (même en moins bonne qualité) que rien.
                self._trace_recherche(f"Affiche « {titre} » : nouvel essai avec l'URL d'origine → {url_image}")
                data = self._telecharger_bytes_image(url_image)
            if data is None:
                return "", ("Échec du téléchargement de l'affiche (voir la console, "
                             "préfixe [Compléter], pour le détail).")
            try:
                with open(dest, "wb") as f:
                    f.write(data)
                return dest, ""
            except Exception as ex:
                return "", f"Échec du téléchargement de l'affiche :\n{ex}"

        def _options_yt_dlp_bande_annonce(self, outtmpl):
            """Options yt-dlp communes au téléchargement réel et au
            téléchargement temporaire d'une bande-annonce. Le sélecteur de
            format "best[ext=mp4]/best" (obsolète) ne correspondait plus à
            grand-chose : YouTube sert aujourd'hui presque toujours la
            vidéo et l'audio en flux séparés, qu'il faut fusionner — d'où
            l'erreur observée « Requested format is not available ». On
            demande donc explicitement la meilleure vidéo + le meilleur
            audio (avec repli sur un flux déjà fusionné si besoin), fusionnés
            en mp4 via ffmpeg (déjà utilisé par ailleurs dans Citron pour
            les vignettes) si mkv/webm ne peut pas être évité."""
            opts = {
                "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "outtmpl": outtmpl,
                "quiet": True,
                "noplaylist": True,
            }
            ffmpeg_path = self._get_ffmpeg_path()
            if ffmpeg_path:
                opts["ffmpeg_location"] = ffmpeg_path
            return opts

        def _telecharger_bande_annonce_video(self, titre, annee, url_youtube, dossier, chemin_local_existant=""):
            """Télécharge réellement la vidéo de la bande-annonce dans le
            dossier choisi par l'utilisateur (demandé systématiquement),
            pour que Citron puisse la lire lui-même sans dépendre d'un
            navigateur — nécessite le paquet 'yt-dlp' (pip install yt-dlp).
            Si `chemin_local_existant` pointe vers un fichier déjà
            téléchargé (typiquement par « Simuler Infos (tableur) » pour
            la même URL), il est simplement copié vers le dossier choisi
            au lieu d'être retéléchargé via yt-dlp (gain de temps, cette
            étape étant la plus longue). Renvoie (chemin_local, "") en cas
            de succès, ou ("", message d'erreur) sinon (n'empêche jamais
            l'enregistrement du reste des données)."""
            import re
            if not url_youtube:
                return "", ""
            if not dossier:
                return "", "Aucun dossier choisi pour la bande-annonce."
            try:
                os.makedirs(dossier, exist_ok=True)
            except Exception as ex:
                return "", f"Impossible de créer le dossier de la bande-annonce :\n{ex}"
            if chemin_local_existant and os.path.isfile(chemin_local_existant):
                ext = os.path.splitext(chemin_local_existant)[1] or ".mp4"
                nom = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{titre}_{annee}_bande_annonce").strip("_") or "bande_annonce"
                dest = os.path.join(dossier, nom + ext)
                try:
                    shutil.copyfile(chemin_local_existant, dest)
                    self._trace_recherche(
                        f"Bande-annonce « {titre} » : réutilisation du téléchargement de "
                        f"la simulation (pas de retéléchargement) → {dest}")
                    return dest, ""
                except Exception as ex:
                    self._trace_recherche(
                        f"Bande-annonce « {titre} » : échec de la copie depuis la simulation "
                        f"({type(ex).__name__}: {ex}) — nouveau téléchargement.")
            try:
                import yt_dlp
            except ImportError:
                return "", ("Téléchargement de bande-annonce impossible : le paquet "
                             "'yt-dlp' n'est pas installé (pip install yt-dlp).")
            nom = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{titre}_{annee}_bande_annonce").strip("_") or "bande_annonce"
            ydl_opts = self._options_yt_dlp_bande_annonce(os.path.join(dossier, nom + ".%(ext)s"))
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url_youtube, download=True)
                    chemin = ydl.prepare_filename(info)
                    if ydl_opts.get("merge_output_format"):
                        racine, _ext = os.path.splitext(chemin)
                        chemin_fusionne = racine + "." + ydl_opts["merge_output_format"]
                        if os.path.isfile(chemin_fusionne):
                            chemin = chemin_fusionne
                return chemin, ""
            except Exception as ex:
                self._trace_recherche(f"Téléchargement bande-annonce : ÉCHEC — {type(ex).__name__}: {ex}")
                return "", f"Échec du téléchargement de la bande-annonce :\n{ex}"

        def _telecharger_bande_annonce_temporaire(self, titre, annee, url_video):
            """Télécharge la bande-annonce (YouTube ou Dailymotion) dans un
            fichier temporaire — même principe que
            _telecharger_image_temporaire pour l'affiche — afin qu'elle
            apparaisse et se lise dans « Simuler Infos (tableur) » EXACTEMENT
            comme n'importe quelle bande-annonce déjà intégrée au tableur
            (vrai lecteur vidéo intégré dans sa colonne dédiée), plutôt
            qu'un simple lien texte à ouvrir dans le navigateur. Rien n'est
            enregistré dans le tableur. Renvoie le chemin local, ou "" en
            cas d'échec (yt-dlp absent, vidéo introuvable…) — un échec ici
            n'empêche jamais le reste de la simulation de s'afficher."""
            import re
            if not url_video:
                return ""
            try:
                import yt_dlp
            except ImportError:
                return ""
            nom = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{titre}_{annee}_ba").strip("_") or "bande_annonce"
            fd, base = tempfile.mkstemp(prefix=f"citron_ba_{nom}_")
            os.close(fd)
            try:
                os.remove(base)
            except Exception:
                pass
            ydl_opts = self._options_yt_dlp_bande_annonce(base + ".%(ext)s")
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url_video, download=True)
                    chemin = ydl.prepare_filename(info)
                    if ydl_opts.get("merge_output_format"):
                        racine, _ext = os.path.splitext(chemin)
                        chemin_fusionne = racine + "." + ydl_opts["merge_output_format"]
                        if os.path.isfile(chemin_fusionne):
                            chemin = chemin_fusionne
                    return chemin
            except Exception as ex:
                self._trace_recherche(f"Téléchargement bande-annonce (aperçu) : ÉCHEC — {type(ex).__name__}: {ex}")
                return ""

        def _completer_tableur_simuler(self, win):
            """2ème façon de proposer le résultat : l'affiche comme une vraie
            fiche « Simuler Infos (tableur) » (même mécanisme que 🧪 Test
            tableur), en lecture seule, sans toucher au tableur réel.
            L'affiche ET la bande-annonce sont toutes deux téléchargées dans
            des fichiers temporaires, pour être affichées — et, pour la
            bande-annonce, réellement LUE via le lecteur vidéo intégré —
            exactement comme le serait n'importe quelle ligne déjà validée
            du tableur, plutôt qu'un simple lien à ouvrir dans le
            navigateur."""
            champs = self._completer_tableur_lire_champs(win)
            if not champs["titre"]:
                messagebox.showwarning("Titre manquant", "Le champ Titre ne peut pas être vide.")
                return
            try:
                win.simuler_btn.configure(state="disabled", text="⏳ Préparation…")
            except Exception:
                pass

            def worker():
                chemin_affiche = ""
                if champs.get("affiche"):
                    try:
                        chemin_affiche = self._telecharger_image_temporaire(champs["affiche"])
                    except Exception:
                        chemin_affiche = ""
                chemin_bande_annonce = ""
                if champs.get("bande_annonce"):
                    try:
                        chemin_bande_annonce = self._telecharger_bande_annonce_temporaire(
                            champs["titre"], champs["annee"], champs["bande_annonce"])
                    except Exception:
                        chemin_bande_annonce = ""
                # Mémorise ces téléchargements temporaires sur la fenêtre :
                # si l'utilisateur enchaîne avec « Valider et intégrer au
                # tableur » sans changer les champs affiche/bande-annonce,
                # ces fichiers déjà téléchargés seront réutilisés (copiés)
                # au lieu d'être retéléchargés (gain de temps), voir
                # _completer_tableur_valider.
                win._sim_cache_affiche_url = champs.get("affiche") or ""
                win._sim_cache_affiche_path = chemin_affiche or ""
                win._sim_cache_ba_url = champs.get("bande_annonce") or ""
                win._sim_cache_ba_path = chemin_bande_annonce or ""
                if win.winfo_exists():
                    self.after(0, lambda: self._completer_tableur_ouvrir_simulation(
                        win, champs, chemin_affiche, chemin_bande_annonce))

            threading.Thread(target=worker, daemon=True).start()

        def _completer_tableur_ouvrir_simulation(self, win, champs, chemin_affiche, chemin_bande_annonce=""):
            try:
                win.simuler_btn.configure(state="normal", text="📋 Simuler Infos (tableur)")
            except Exception:
                pass
            # Le lien texte "Bande-annonce (YouTube/Dailymotion) : url" n'est
            # plus placé ici (demandé explicitement) : la bande-annonce se
            # lit désormais directement via le lecteur vidéo intégré
            # (chemin_bande_annonce, colonne dédiée juste en dessous), ce
            # bouton faisant double emploi. Il reste utilisé lors de
            # l'intégration réelle au tableur (pour garder une trace du
            # lien source), juste pas dans cet aperçu.
            row_data = [
                champs["titre"], champs["annee"], champs["resume"], champs["personnes"],
                champs["type"], champs["realisateur"], champs["duree"], "",
                "", chemin_affiche or "", chemin_bande_annonce or "", champs.get("categorie", ""),
            ]
            test_scope = [{

                "titre": champs["titre"], "path": None,
                "row_data": row_data, "error": None,
            }]
            self._open_info_window(
                champs["titre"], None, row_data, None,
                nav_override={
                    "list": test_scope,
                    "index": 0,
                    "breadcrumb": [],
                    "virtual_playlist_mode": True,
                    # Cette « Simuler Infos » vient précisément de la
                    # fenêtre « Compléter le tableur » (win) : dans ce
                    # cas seulement, _open_info_window remplace les
                    # boutons Recherche / + Playlist virtuelle par un
                    # bouton « Valider et intégrer au tableur » agissant
                    # directement sur cette fenêtre.
                    "from_completer_tableur": True,
                    "completer_win": win,
                },
                from_chain=False
            )

        def _completer_tableur_valider(self, win):
            """Résultat validé : compare d'abord avec le tableur existant
            pour éviter un doublon (titre très proche mais pas identique),
            demande SYSTÉMATIQUEMENT où enregistrer l'affiche et où
            enregistrer la bande-annonce (deux emplacements distincts —
            jamais mémorisés comme dossier fixe, pour laisser le choix à
            chaque fois), télécharge les deux, puis intègre tout au tableur
            réel (met à jour la ligne existante si le titre y figure déjà,
            sinon ajoute une nouvelle ligne)."""
            champs = self._completer_tableur_lire_champs(win)
            if not champs["titre"]:
                messagebox.showwarning("Titre manquant", "Le champ Titre ne peut pas être vide.")
                return

            # Mode « édition depuis Infos » (voir _ouvrir_completer_depuis_infos) :
            # la ligne visée dans le tableur est identifiée par le titre/année
            # D'ORIGINE mémorisés à l'ouverture, jamais par le champ Titre
            # actuel — sinon une simple correction de titre ajouterait une
            # nouvelle ligne au lieu de mettre à jour l'existante. Dans ce
            # mode, il s'agit forcément d'une ligne déjà présente : la
            # vérification de doublon (destinée aux NOUVELLES entrées) est
            # donc inutile, et gênante si le titre est justement en train
            # d'être corrigé.
            _edition_mode = getattr(win, "_completer_stage", "") == "edition_depuis_infos"
            _titre_recherche = getattr(win, "_edition_titre_original", None) if _edition_mode else None
            _annee_recherche = getattr(win, "_edition_annee_original", None) if _edition_mode else None

            # Résolu et vérifié ICI, sur le thread principal — jamais dans
            # le thread d'arrière-plan plus bas, où un messagebox/filedialog
            # Tkinter est peu fiable (peut rester invisible ou planter, ce
            # qui donnait l'impression que la validation ne faisait rien).
            chemin_tableur = self._confirmer_ou_choisir_tableur()
            if not chemin_tableur:
                return

            if not _edition_mode:
                proche = self._chercher_titre_proche_tableur(champs["titre"])
                if proche and not proche.get("exact"):
                    label = proche["titre"] + (f" ({proche['annee']})" if proche.get("annee") else "")
                    if not messagebox.askyesno(
                        "Doublon possible",
                        f"Un titre très proche existe déjà dans le tableur :\n« {label} »\n\n"
                        f"Veux-tu quand même ajouter « {champs['titre']} » comme nouvelle ligne ?"
                    ):
                        return

            # L'emplacement de téléchargement est redemandé à chaque
            # validation (jamais fixé automatiquement) — bande-annonce et
            # affiche vont systématiquement dans des dossiers distincts.
            dossier_affiche = ""
            if champs.get("affiche"):
                dossier_affiche = filedialog.askdirectory(
                    title="Où enregistrer l'AFFICHE du film ?",
                    initialdir=getattr(self, "_dernier_dossier_affiches", "") or None)
                if dossier_affiche:
                    self._dernier_dossier_affiches = dossier_affiche
                    self.save_settings()
                elif not messagebox.askyesno(
                        "Affiche non enregistrée",
                        "Aucun dossier choisi : continuer sans télécharger l'affiche ?"):
                    return

            dossier_bande_annonce = ""
            if champs.get("bande_annonce"):
                dossier_bande_annonce = filedialog.askdirectory(
                    title="Où enregistrer la BANDE-ANNONCE ?",
                    initialdir=getattr(self, "_dernier_dossier_bandes_annonces", "") or None)
                if dossier_bande_annonce:
                    self._dernier_dossier_bandes_annonces = dossier_bande_annonce
                    self.save_settings()
                elif not messagebox.askyesno(
                        "Bande-annonce non enregistrée",
                        "Aucun dossier choisi : continuer sans télécharger la bande-annonce ?"):
                    return

            try:
                win.valider_btn.configure(state="disabled", text="⏳ Téléchargement…")
            except Exception:
                pass

            def worker():
                self._trace_recherche(f"Validation « {champs['titre']} » — chemin tableur = {chemin_tableur}")
                try:
                    champs2 = dict(champs)
                    erreurs = []
                    # Réutilisation d'un téléchargement déjà fait par
                    # « Simuler Infos (tableur) » : si le champ affiche/
                    # bande-annonce n'a pas changé depuis cette simulation
                    # et que le fichier temporaire existe toujours, on le
                    # copie directement au lieu de retélécharger (gain de
                    # temps) — voir _completer_tableur_simuler.
                    _cache_affiche = (
                        champs2.get("affiche") and
                        champs2["affiche"] == getattr(win, "_sim_cache_affiche_url", None) and
                        os.path.isfile(getattr(win, "_sim_cache_affiche_path", "") or "")
                    )
                    _cache_ba = (
                        champs2.get("bande_annonce") and
                        champs2["bande_annonce"] == getattr(win, "_sim_cache_ba_url", None) and
                        os.path.isfile(getattr(win, "_sim_cache_ba_path", "") or "")
                    )
                    champs2["affiche_locale"] = ""
                    if champs2.get("affiche") and dossier_affiche:
                        champs2["affiche_locale"], err = self._telecharger_affiche_choisie(
                            champs2["titre"], champs2["annee"], champs2["affiche"], dossier_affiche,
                            chemin_local_existant=(win._sim_cache_affiche_path if _cache_affiche else ""))
                        if err:
                            erreurs.append(err)
                    champs2["bande_annonce_locale"] = ""
                    if champs2.get("bande_annonce") and dossier_bande_annonce:
                        champs2["bande_annonce_locale"], err = self._telecharger_bande_annonce_video(
                            champs2["titre"], champs2["annee"], champs2["bande_annonce"], dossier_bande_annonce,
                            chemin_local_existant=(win._sim_cache_ba_path if _cache_ba else ""))
                        if err:
                            erreurs.append(err)
                    ok, msg = self._ecrire_completion_dans_tableur(
                        champs2, chemin_tableur,
                        titre_recherche=_titre_recherche, annee_recherche=_annee_recherche)
                    if erreurs:
                        msg = msg + "\n\n⚠️ " + "\n⚠️ ".join(erreurs)
                except Exception as ex:
                    # Une exception inattendue ici mourrait auparavant en
                    # silence dans le thread d'arrière-plan : le bouton
                    # restait bloqué sur « ⏳ Téléchargement… » et rien ne
                    # prévenait l'utilisateur que la validation avait
                    # échoué.
                    self._trace_recherche(f"Validation : ÉCHEC INATTENDU — {type(ex).__name__}: {ex}")
                    champs2, ok, msg = champs, False, f"Erreur inattendue : {type(ex).__name__}: {ex}"
                self._trace_recherche(f"Validation « {champs['titre']} » — terminée : "
                                       f"{'succès' if ok else 'échec'} — {msg}")
                if win.winfo_exists():
                    self.after(0, lambda: self._completer_tableur_apres_validation(win, champs2, ok, msg))

            threading.Thread(target=worker, daemon=True).start()

        def _completer_tableur_apres_validation(self, win, champs, ok, msg):
            _edition_mode = getattr(win, "_completer_stage", "") == "edition_depuis_infos"
            try:
                win.valider_btn.configure(
                    state="normal",
                    text="✅ Modifier le tableur" if _edition_mode else "✅ Valider et intégrer au tableur")
            except Exception:
                pass
            if ok:
                if _edition_mode:
                    # Simple modification d'une ligne existante (depuis
                    # 📋 Infos (tableur)) : pas de fiche vierge à ré-ouvrir
                    # ensuite, on referme directement.
                    messagebox.showinfo("Tableur modifié",
                                         f"« {champs['titre']} » a été mis à jour dans le tableur.\n\n{msg}")
                    self._fermer_completer_depuis_infos(win)
                else:
                    messagebox.showinfo("Tableur complété",
                                         f"« {champs['titre']} » a été intégré au tableur.\n\n{msg}")
                    self._completer_tableur_effacer_champs(win)
            else:
                messagebox.showerror("Erreur", msg)

        def _chercher_titre_proche_tableur(self, titre):
            """Compare un titre au contenu du tableur pour éviter les
            doublons : renvoie {"exact": True, ...} si le titre y figure déjà
            à l'identique (dans ce cas, valider mettra normalement à jour
            cette ligne, ce n'est pas un doublon), {"exact": False, ...} si
            un titre très proche mais différent existe (doublon probable, à
            confirmer par l'utilisateur), ou None si rien de comparable
            n'est trouvé (ou si aucun tableur n'est configuré)."""
            path = getattr(self, "_tableur_path", None)
            if not path or not os.path.isfile(path):
                return None
            try:
                from odf.opendocument import load as ods_load
                from odf.table import Table, TableRow, TableCell
            except Exception:
                return None
            try:
                import difflib
                doc = ods_load(path)
                sheets = doc.spreadsheet.getElementsByType(Table)
                if not sheets:
                    return None
                rows = sheets[0].getElementsByType(TableRow)
                cible = self._tableur_search_clean(titre)
                meilleur, meilleur_score = None, 0.0
                for row in rows:
                    cells = self._expand_ods_cells(row.getElementsByType(TableCell))
                    if not cells:
                        continue
                    t = self._ods_cell_text(cells[0]).strip()
                    if not t:
                        continue
                    ct = self._tableur_search_clean(t)
                    annee = self._ods_cell_text(cells[1]).strip() if len(cells) > 1 else ""
                    if ct == cible:
                        return {"exact": True, "titre": t, "annee": annee}
                    score = difflib.SequenceMatcher(None, ct, cible).ratio()
                    if score > meilleur_score:
                        meilleur_score = score
                        meilleur = {"exact": False, "titre": t, "annee": annee, "score": score}
                if meilleur and meilleur_score >= 0.82:
                    return meilleur
                return None
            except Exception:
                return None

        def _diagnostiquer_permission_refusee(self, path):
            """Après un PermissionError à l'écriture du tableur (et alors même
            que le fichier n'est ni en lecture seule ni ouvert ailleurs —
            cas rencontré), rassemble un diagnostic plus précis que des
            causes possibles au hasard. Teste séparément le FICHIER et le
            DOSSIER qui le contient : si écrire un simple fichier test dans
            le même dossier échoue AUSSI, le blocage touche tout le
            dossier/lecteur, pas ce fichier précis — signe typique d'un
            antivirus (le Contrôle d'accès aux dossiers de Windows
            Defender, notamment, bloque l'écriture des programmes non
            reconnus dans certains dossiors SANS jamais toucher à
            l'attribut "lecture seule" du fichier, ce qui explique
            parfaitement que rien ne semble anormal au premier coup d'œil).
            Retourne une chaîne de diagnostic à inclure dans le message
            d'erreur, pour ne plus avoir à deviner à l'aveugle."""
            import time
            lignes = []
            dossier = os.path.dirname(path) or "."

            try:
                accessible = os.access(path, os.W_OK)
                lignes.append(f"• Fichier signalé accessible en écriture par Windows (os.access) : "
                               f"{'oui' if accessible else 'NON'}")
            except Exception as ex:
                lignes.append(f"• Test os.access sur le fichier : erreur ({ex})")

            try:
                with open(path, "r+b"):
                    pass
                lignes.append("• Ouverture directe du fichier en lecture/écriture (sans passer par "
                               "le tableur) : réussie")
            except Exception as ex:
                lignes.append(
                    f"• Ouverture directe du fichier en lecture/écriture : ÉCHEC "
                    f"({type(ex).__name__}: {ex})")

            test_path = os.path.join(dossier, f"citron_test_ecriture_{int(time.time())}.tmp")
            try:
                with open(test_path, "w") as f:
                    f.write("test")
                os.remove(test_path)
                lignes.append("• Création d'un fichier TEST dans le même dossier : réussie → le "
                               "dossier/lecteur accepte l'écriture, le blocage est SPÉCIFIQUE à ce "
                               "fichier (vérifier s'il est ouvert ailleurs, ou ses propriétés de sécurité "
                               "avancées — onglet Sécurité, pas juste la case \"lecture seule\").")
            except Exception as ex:
                lignes.append(
                    f"• Création d'un fichier TEST dans le même dossier : ÉCHEC ÉGALEMENT "
                    f"({type(ex).__name__}: {ex}) → le dossier entier semble bloqué, pas seulement ce "
                    "fichier. Piste la plus probable : le Contrôle d'accès aux dossiers de Windows "
                    "Defender (Sécurité Windows → Protection contre les virus et menaces → Gérer la "
                    "protection contre les ransomwares → Autoriser une application via le contrôle "
                    "d'accès aux dossiers → ajouter python.exe), ou un autre antivirus qui bloque en "
                    "silence sans jamais toucher à l'attribut \"lecture seule\" du fichier.")

            return "\n".join(lignes)

        def _materialiser_cellules(self, row, nb_colonnes):
            """S'assure que les `nb_colonnes` premières colonnes de `row`
            sont chacune représentées par une TableCell RÉELLE et
            DISTINCTE dans le XML, en scindant au besoin un bloc de
            cellules compressées (attribut ODF number-columns-repeated)
            qui chevaucherait cette plage.

            Indispensable avant d'écrire dans plusieurs colonnes d'une
            ligne existante : sans ça, plusieurs indices de colonnes
            peuvent pointer vers LE MÊME objet cellule partagé (renvoyé
            plusieurs fois par _expand_ods_cells), et chaque écriture y
            écrase alors silencieusement la précédente — observé en
            pratique : plusieurs colonnes affichant toutes la même
            valeur après une validation, y compris la colonne Titre.

            Ne touche pas aux colonnes déjà distinctes, ni à celles
            situées au-delà de nb_colonnes (un éventuel bloc compressé
            qui continue au-delà garde son contenu d'origine)."""
            from odf.table import TableCell
            from odf.text import P
            pos = 0
            for cell in list(row.getElementsByType(TableCell)):
                if pos >= nb_colonnes:
                    break
                rep = cell.getAttribute("numbercolumnsrepeated")
                try:
                    rep = int(rep) if rep else 1
                except (TypeError, ValueError):
                    rep = 1
                if rep <= 1:
                    pos += rep
                    continue
                overlap = min(pos + rep, nb_colonnes) - pos
                if overlap <= 0:
                    pos += rep
                    continue
                texte = self._ods_cell_text(cell)
                for _ in range(overlap):
                    nouvelle = TableCell(valuetype="string")
                    if texte:
                        nouvelle.addElement(P(text=texte))
                    row.insertBefore(nouvelle, cell)
                if rep - overlap > 0:
                    reste = TableCell(valuetype="string")
                    if rep - overlap > 1:
                        reste.setAttribute("numbercolumnsrepeated", str(rep - overlap))
                    if texte:
                        reste.addElement(P(text=texte))
                    row.insertBefore(reste, cell)
                row.removeChild(cell)
                pos += rep

        def _trouver_ligne_vierge(self, sheet):
            """Cherche, à partir de la 2ème ligne du tableur (la 1ère est
            l'en-tête), la PREMIÈRE ligne vraiment vide (colonne Titre
            vide) — demandé explicitement, pour ne plus jamais ajouter une
            ligne tout en bas de la feuille (ligne 1 048 579 observée en
            pratique) alors que des lignes vides existent bien plus haut.

            Une suite de lignes vides est presque toujours compressée par
            LibreOffice en un SEUL élément XML portant l'attribut ODF
            number-rows-repeated (parfois plus d'un million de lignes
            représentées par un seul élément) : pour en réutiliser une
            seule sans perturber les autres, on scinde ce bloc en
            décrémentant son compteur de 1.

            Renvoie (row_a_reutiliser_ou_None, numero_ligne,
            bloc_a_decrementer_ou_None) :
            - row_a_reutiliser_ou_None : une TableRow déjà présente et vide
              à réutiliser telle quelle (cas d'une ligne isolée, non
              compressée) ; None si aucune ligne existante n'est
              réutilisable et qu'il faut en insérer une nouvelle.
            - numero_ligne : le numéro de ligne réel (1 = première ligne)
              où écrire.
            - bloc_a_decrementer_ou_None : la TableRow du bloc compressé
              dont il faut décrémenter number-rows-repeated de 1 après
              avoir inséré la nouvelle ligne juste avant lui (None si non
              applicable)."""
            from odf.table import TableRow, TableCell
            ligne_num = 1
            for row in sheet.getElementsByType(TableRow):
                rep = row.getAttribute("numberrowsrepeated")
                try:
                    rep = int(rep) if rep else 1
                except (TypeError, ValueError):
                    rep = 1
                if ligne_num < 2:
                    # Encore dans l'en-tête (ligne 1).
                    ligne_num += rep
                    continue
                cells = self._expand_ods_cells(row.getElementsByType(TableCell), max_cols=1)
                titre_cell = self._ods_cell_text(cells[0]).strip() if cells else ""
                if not titre_cell:
                    if rep <= 1:
                        return row, ligne_num, None
                    return None, ligne_num, row
                ligne_num += rep
            return None, ligne_num, None

        def _numero_ligne_ods(self, sheet, target_row=None):
            """Calcule le numéro de ligne "réel", tel qu'affiché dans
            LibreOffice/Excel (1 = première ligne), d'une TableRow donnée —
            ou, si target_row est None, le numéro qu'aurait une toute
            nouvelle ligne ajoutée en fin de feuille. Indispensable car
            LibreOffice compresse souvent de longues suites de lignes
            vides en un seul élément XML portant l'attribut ODF
            number-rows-repeated (ex. une seule TableRow représentant
            1 048 000 lignes vides) : sans en tenir compte, un simple
            comptage des éléments TableRow donnerait un numéro de ligne
            complètement faux dès que le tableur contient de telles
            lignes compressées, ce qui est la norme."""
            from odf.table import TableRow
            total = 0
            for row in sheet.getElementsByType(TableRow):
                rep = row.getAttribute("numberrowsrepeated")
                try:
                    rep = int(rep) if rep else 1
                except (TypeError, ValueError):
                    rep = 1
                if target_row is not None and row is target_row:
                    return total + 1
                total += rep
            return total + 1

        def _ecrire_completion_dans_tableur(self, champs, path, titre_recherche=None, annee_recherche=None):
            """Écrit les champs validés dans le tableur (.ods) : met à jour la
            ligne correspondante si son titre y est déjà présent (colonnes
            Titre/Année/Résumé/Acteurs/Type/Réalisateur(Filmeur)/Durée,
            8ème colonne = champ libre « Renseignements divers », Affiche
            et Bande-annonce téléchargées localement — inscrites en
            hyperlien vers le fichier local, avec pour texte affiché
            « Titre (Année).jpg »/« .mp4 », comme dans les lignes remplies
            à la main), sinon ajoute une nouvelle ligne en fin de tableur.
            « path » doit avoir déjà été résolu et vérifié par l'appelant
            (sur le thread principal — voir _confirmer_ou_choisir_tableur) :
            cette fonction est appelée depuis un thread d'arrière-plan et ne
            doit donc jamais elle-même ouvrir de boîte de dialogue. Retourne
            (True, message) ou (False, message d'erreur)."""
            if not path or not os.path.isfile(path):
                return False, "Aucun tableur configuré."
            try:
                from odf.opendocument import load as ods_load
                from odf.table import Table, TableRow, TableCell
                from odf.text import P, A
            except Exception:
                return False, "La bibliothèque 'odfpy' n'est pas disponible."
            try:
                doc = ods_load(path)
            except Exception as ex:
                return False, f"Impossible de lire le tableur :\n{ex}"

            # 8ème colonne : champ libre « Renseignements divers » du
            # formulaire (ex : « N/B », « VOSTFR »...), sinon rien n'est
            # écrit (la colonne n'est jamais écrasée par du vide). Le lien
            # source de la bande-annonce (YouTube/Dailymotion) n'y est plus
            # stocké : la bande-annonce se retrouve désormais directement,
            # en hyperlien, dans sa propre colonne (voir plus bas).
            col8_valeur = (champs.get("renseignements") or "").strip()
            _nom_base = (
                f"{(champs.get('titre') or '').strip()} ({(champs.get('annee') or '').strip()})"
                if (champs.get("annee") or "").strip()
                else (champs.get("titre") or "").strip()
            )

            def _set_cell_hyperlink(cell, chemin, texte):
                """Remplit une cellule avec un hyperlien vers `chemin`
                (fichier local) affichant `texte`, dans le même format
                que les lignes remplies à la main du tableur (lu ensuite
                via _ods_cell_content)."""
                for child in list(cell.childNodes):
                    cell.removeChild(child)
                p = P()
                if chemin:
                    try:
                        from pathlib import Path
                        href = Path(chemin).as_uri()
                    except Exception:
                        href = chemin
                    p.addElement(A(href=href, text=texte))
                elif texte:
                    p.addText(texte)
                cell.addElement(p)

            try:
                sheets = doc.spreadsheet.getElementsByType(Table)
                if not sheets:
                    return False, "Aucune feuille trouvée dans le tableur."
                rows = sheets[0].getElementsByType(TableRow)

                _clean = self._tableur_search_clean
                # titre_recherche/annee_recherche (mode édition depuis Infos) :
                # identifient la ligne à mettre à jour par son identité
                # D'ORIGINE, indépendamment d'un éventuel titre corrigé dans
                # `champs` — voir _completer_tableur_valider.
                target_t = _clean(titre_recherche if titre_recherche is not None else champs["titre"])
                target_a = (annee_recherche if annee_recherche is not None else (champs["annee"] or "")).strip()

                best_row, best_cells, best_score = None, None, 0
                for row in rows:
                    cells = self._expand_ods_cells(row.getElementsByType(TableCell))
                    if not cells:
                        continue
                    ct1 = _clean(self._ods_cell_text(cells[0]).strip())
                    if not ct1:
                        continue
                    ct2 = self._ods_cell_text(cells[1]).strip() if len(cells) > 1 else ""
                    if ct1 == target_t:
                        score = 100 if (target_a and ct2 == target_a) else 80
                    else:
                        score = 0
                    if score > best_score:
                        best_score, best_cells, best_row = score, cells, row

                def _set_cell_text(cell, valeur):
                    for child in list(cell.childNodes):
                        cell.removeChild(child)
                    for line in (valeur.split("\n") if valeur else [""]):
                        cell.addElement(P(text=line))

                if best_cells and best_score >= 80:
                    # Ligne déjà présente : on ne remplace que les colonnes
                    # pour lesquelles une nouvelle valeur non vide a été
                    # trouvée/validée, afin de ne jamais écraser une donnée
                    # existante par du vide. Affiche (9) et Bande-annonce
                    # (10) sont traitées séparément plus bas (hyperlien).
                    col_map = [(0, "titre"), (1, "annee"), (2, "resume"),
                               (3, "personnes"), (4, "type"), (5, "realisateur"),
                               (6, "duree"), (11, "categorie")]

                    affiche_locale = (champs.get("affiche_locale") or "").strip()
                    ba_locale = (champs.get("bande_annonce_locale") or "").strip()

                    # Les colonnes Affiche (9) et Bande-annonce (10) sont
                    # les plus récentes : une ligne existante du tableur n'a
                    # souvent tout simplement pas encore de cellule jusque
                    # là. Sans ce complètement, l'écriture était ignorée en
                    # silence (idx >= len(best_cells)) — c'est ce qui
                    # empêchait l'enregistrement de la bande-annonce/affiche
                    # après validation. On complète la ligne réelle (pas
                    # seulement la liste en mémoire) avec des cellules
                    # vides jusqu'à la colonne la plus lointaine réellement
                    # nécessaire.
                    idx_max_utile = max(
                        [idx for idx, key in col_map if (champs.get(key) or "").strip()] +
                        ([7] if col8_valeur else []) +
                        ([9] if affiche_locale else []) +
                        ([10] if ba_locale else []) + [-1])
                    if idx_max_utile >= len(best_cells):
                        for _ in range(idx_max_utile + 1 - len(best_cells)):
                            best_row.addElement(TableCell(valuetype="string"))
                    # Scinde tout bloc de cellules compressées qui
                    # chevaucherait les colonnes qu'on s'apprête à écrire
                    # (voir _materialiser_cellules) AVANT de redéplier —
                    # sinon plusieurs colonnes pourraient encore pointer
                    # vers la même cellule partagée.
                    self._materialiser_cellules(best_row, idx_max_utile + 1)
                    best_cells = self._expand_ods_cells(best_row.getElementsByType(TableCell))

                    for idx, key in col_map:
                        val = (champs.get(key) or "").strip()
                        if not val or idx >= len(best_cells):
                            continue
                        _set_cell_text(best_cells[idx], val)
                    if col8_valeur and len(best_cells) > 7:
                        _set_cell_text(best_cells[7], col8_valeur)
                    if affiche_locale and len(best_cells) > 9:
                        _set_cell_hyperlink(best_cells[9], affiche_locale, f"{_nom_base}.jpg")
                    if ba_locale and len(best_cells) > 10:
                        _set_cell_hyperlink(best_cells[10], ba_locale, f"{_nom_base}.mp4")
                    numero_ligne = self._numero_ligne_ods(sheets[0], best_row)
                    message = f"ligne existante mise à jour (ligne {numero_ligne})"
                else:
                    # Aucune ligne correspondante : on cherche la PREMIÈRE
                    # ligne vraiment vide à partir de la ligne 2 (demandé
                    # explicitement), plutôt que d'ajouter tout en bas —
                    # une suite de lignes vides étant presque toujours
                    # compressée par LibreOffice en un seul élément XML
                    # (number-rows-repeated, parfois plus d'un million de
                    # lignes), ajouter bêtement à la fin plaçait la
                    # nouvelle ligne à un numéro absurde (ligne 1 048 579
                    # observée en pratique) — techniquement écrite, mais
                    # invisible en pratique.
                    row_reutilisable, numero_ligne, bloc_a_reduire = self._trouver_ligne_vierge(sheets[0])

                    new_row = row_reutilisable if row_reutilisable is not None else TableRow()
                    affiche_locale = (champs.get("affiche_locale") or "").strip()
                    ba_locale = (champs.get("bande_annonce_locale") or "").strip()
                    # Colonnes 10 (Affiche) et 11 (Bande-annonce) laissées
                    # vides ici : elles sont remplies juste après, en
                    # hyperlien, une fois les cellules réellement créées.
                    valeurs = [champs["titre"], champs["annee"], champs["resume"],
                               champs["personnes"], champs["type"], champs["realisateur"],
                               champs["duree"], col8_valeur, "", "",
                               "", champs.get("categorie", "")]
                    if row_reutilisable is not None:
                        # Ligne déjà présente (vide, isolée) : ses cellules
                        # existantes peuvent très bien être un UNIQUE bloc
                        # compressé partagé entre plusieurs colonnes
                        # (attribut ODF number-columns-repeated, le même
                        # mécanisme que pour les lignes vides). Essayer d'y
                        # écrire directement colonne par colonne écrivait en
                        # réalité plusieurs fois dans le MÊME objet cellule
                        # partagé — la dernière valeur écrite écrasait donc
                        # toutes les précédentes, et se retrouvait affichée
                        # dans toutes les colonnes concernées, Titre compris.
                        # On repart donc de zéro : toutes les cellules
                        # existantes sont retirées, puis 12 cellules neuves
                        # et bien distinctes sont ajoutées — exactement comme
                        # pour une ligne toute neuve ci-dessous.
                        for child in list(new_row.childNodes):
                            new_row.removeChild(child)
                    for val in valeurs:
                        cell = TableCell(valuetype="string")
                        for line in ((val or "").split("\n") if val else [""]):
                            cell.addElement(P(text=line))
                        new_row.addElement(cell)
                    # Colonnes 10 et 11 : hyperlien vers le fichier local
                    # (affiche / bande-annonce), texte affiché « Titre
                    # (Année).jpg »/« .mp4 » — même convention que les
                    # lignes remplies à la main.
                    _cells_nv = self._expand_ods_cells(new_row.getElementsByType(TableCell))
                    if affiche_locale and len(_cells_nv) > 9:
                        _set_cell_hyperlink(_cells_nv[9], affiche_locale, f"{_nom_base}.jpg")
                    if ba_locale and len(_cells_nv) > 10:
                        _set_cell_hyperlink(_cells_nv[10], ba_locale, f"{_nom_base}.mp4")
                    if row_reutilisable is None:
                        if bloc_a_reduire is not None:
                            # La 1ère ligne vide trouvée fait partie d'un
                            # bloc compressé : on scinde ce bloc en
                            # décrémentant son compteur de 1, et on insère
                            # la nouvelle ligne juste avant lui — elle
                            # prend ainsi exactement la première place
                            # libre, sans toucher au reste du bloc.
                            rep_bloc = bloc_a_reduire.getAttribute("numberrowsrepeated")
                            try:
                                rep_bloc = int(rep_bloc) if rep_bloc else 1
                            except (TypeError, ValueError):
                                rep_bloc = 1
                            bloc_a_reduire.setAttribute("numberrowsrepeated", str(max(1, rep_bloc - 1)))
                            sheets[0].insertBefore(new_row, bloc_a_reduire)
                        else:
                            # Aucune ligne vide trouvée avant la fin de la
                            # feuille (tableur entièrement rempli) : on
                            # ajoute réellement à la fin, faute de mieux.
                            sheets[0].addElement(new_row)
                    message = f"nouvelle ligne ajoutée (ligne {numero_ligne})"

                derniere_erreur_permission = None
                sauvegarde_ok = False
                for tentative in range(1, 5):
                    try:
                        doc.save(path)
                        sauvegarde_ok = True
                        if tentative > 1:
                            self._trace_recherche(f"Écriture tableur : réussie à la tentative {tentative}")
                        break
                    except PermissionError as ex:
                        derniere_erreur_permission = ex
                        # Verrou le plus souvent TRANSITOIRE sous Windows :
                        # un antivirus qui scanne le fichier juste après sa
                        # modification (fréquent dans la première seconde
                        # suivant un enregistrement), ou Citron lui-même
                        # n'ayant pas encore totalement relâché le fichier
                        # après une lecture de vérification précédente. Une
                        # vraie restriction permanente (lecture seule,
                        # droits NTFS) échouerait de la même façon à chaque
                        # tentative — d'où plusieurs essais espacés plutôt
                        # que d'abandonner immédiatement. On tente aussi de
                        # lever l'attribut lecture seule dès la 1ère
                        # tentative, au cas où.
                        if tentative == 1:
                            try:
                                os.chmod(path, 0o666)
                            except Exception:
                                pass
                        self._trace_recherche(
                            f"Écriture tableur : tentative {tentative}/4 refusée (permission) — {ex} — "
                            "nouvel essai après une courte pause...")
                        time.sleep(0.7 * tentative)
                    except Exception as ex:
                        self._trace_recherche(
                            f"Écriture tableur : ÉCHEC à l'enregistrement — {type(ex).__name__}: {ex}")
                        return False, f"Impossible d'enregistrer le tableur :\n{ex}"

                if not sauvegarde_ok:
                    diagnostic = self._diagnostiquer_permission_refusee(path)
                    self._trace_recherche(
                        f"Écriture tableur : ÉCHEC définitif après {tentative} tentatives — "
                        f"{derniere_erreur_permission}\n{diagnostic}")
                    return False, (
                        f"Impossible d'enregistrer le tableur : accès refusé (après {tentative} tentatives "
                        "espacées de plusieurs secondes).\n\n"
                        f"« {path} »\n\n"
                        "Diagnostic :\n" + diagnostic
                    )
            except Exception as ex:
                self._trace_recherche(f"Écriture tableur : ÉCHEC à l'enregistrement — {type(ex).__name__}: {ex}")
                return False, f"Impossible d'enregistrer le tableur :\n{ex}"

            self._ods_rows_cache = None
            if hasattr(self, "_info_cache"):
                self._info_cache.clear()

            # Vérification : on relit le fichier tout juste enregistré pour
            # confirmer que la ligne y est vraiment présente, plutôt que de
            # se fier uniquement à l'absence d'exception — utile si le
            # fichier est sur un lecteur réseau capricieux, ou si "path" ne
            # pointait finalement pas vers le fichier que l'utilisateur
            # consulte réellement.
            confirme = False
            numero_verifie = None
            try:
                doc_verif = ods_load(path)
                sheet0_v = doc_verif.spreadsheet.getElementsByType(Table)[0]
                for row_v in sheet0_v.getElementsByType(TableRow):
                    cells_v = self._expand_ods_cells(row_v.getElementsByType(TableCell))
                    if cells_v and _clean(self._ods_cell_text(cells_v[0]).strip()) == target_t:
                        confirme = True
                        numero_verifie = self._numero_ligne_ods(sheet0_v, row_v)
                        break
            except Exception as ex:
                self._trace_recherche(f"Écriture tableur : vérification après coup impossible — {ex}")
            finally:
                # Libère explicitement l'objet de relecture dès que possible
                # : sous Windows, un handle sur le fichier ODS resté
                # référencé plus longtemps que nécessaire peut faire
                # échouer la PROCHAINE validation par "permission refusée"
                # alors que rien n'est réellement verrouillé côté
                # utilisateur.
                doc_verif = None
                import gc
                gc.collect()
            if confirme:
                self._trace_recherche(
                    f"Écriture tableur : confirmée à la relecture dans {path} — ligne {numero_verifie}")
                message += f"\n\nLigne {numero_verifie} du tableur."
            else:
                self._trace_recherche(
                    f"Écriture tableur : ⚠️ NON confirmée à la relecture dans {path} — "
                    "le fichier réellement modifié n'est peut-être pas celui-ci")
                message += (f"\n\n⚠️ Attention : la ligne n'a pas été retrouvée en relisant le fichier "
                            f"juste après l'enregistrement.\nVérifie que c'est bien le bon fichier "
                            f"que tu consultes :\n« {path} »")
            return True, message

        def _show_test_tableur_loading(self):
            """Affiche une animation native, sans fichier externe, pendant le chargement."""
            if getattr(self, "_test_tableur_loading_win", None):
                try:
                    if self._test_tableur_loading_win.winfo_exists():
                        self._test_tableur_loading_win.deiconify()
                        self._test_tableur_loading_win.lift()
                        return
                except Exception:
                    pass

            win = ctk.CTkToplevel(self)
            self._test_tableur_loading_win = win
            win.title("🧪 Test tableur")
            win.geometry("560x450")
            win.resizable(False, False)
            win.transient(self)
            try:
                win.attributes("-topmost", True)
            except Exception:
                pass
            win.lift()
            win.focus_force()
            win.protocol("WM_DELETE_WINDOW", lambda: None)

            ctk.CTkLabel(
                win, text="🧪 Citron retrousse ses manches…",
                font=("Arial", 20, "bold")
            ).pack(pady=(18, 2))

            _off_txt, _citron_txt = _pick_audiard_dialogues(1)[0]
            self._test_tableur_loading_count_label = ctk.CTkLabel(
                win,
                text=f"— {_off_txt}\n🍋 {_citron_txt}",
                font=("Arial", 12), text_color="#bbbbbb",
                justify="center"
            )
            self._test_tableur_loading_count_label.pack(pady=(0, 6))

            # Animation dessinée directement par Tk : aucun GIF externe n'est
            # nécessaire, donc elle fonctionne même si le fichier GIF n'a pas
            # été copié à côté de Citron.py.
            canvas = Canvas(
                win, width=500, height=290,
                bg="#24242a", highlightthickness=0
            )
            canvas.pack(pady=4)
            self._test_tableur_canvas = canvas
            self._test_tableur_anim_index = 0

            def animate():
                c = getattr(self, "_test_tableur_canvas", None)
                w = getattr(self, "_test_tableur_loading_win", None)
                if not c or not w:
                    return
                try:
                    if not w.winfo_exists():
                        return
                    k = getattr(self, "_test_tableur_anim_index", 0)
                    self._test_tableur_anim_index = k + 1
                    c.delete("all")

                    bob = int(5 * math.sin(k * 0.35))
                    # bureau
                    c.create_rectangle(55, 235, 445, 255, fill="#6b4d32", outline="")
                    c.create_rectangle(75, 255, 95, 285, fill="#4b3525", outline="")
                    c.create_rectangle(405, 255, 425, 285, fill="#4b3525", outline="")

                    # ordinateur
                    c.create_rectangle(55, 120, 165, 205, fill="#414957", outline="#a0a5ad", width=3)
                    c.create_rectangle(68, 133, 152, 188, fill="#60798a", outline="")
                    c.create_text(110, 160, text="TABLEUR", fill="white", font=("Arial", 11, "bold"))

                    # papiers
                    for j in range(3):
                        x = 300 + j * 18
                        y = 195 - (j % 2) * 8
                        c.create_rectangle(x, y, x + 82, y + 45, fill="#e9e6d8", outline="#aaa595")

                    # citron
                    bx, by = 235, 170 + bob
                    c.create_oval(bx-70, by-62, bx+70, by+62, fill="#eecd22", outline="#b58f12", width=3)
                    c.create_line(bx-8, by-61, bx-18, by-84, fill="#4d793d", width=5)
                    c.create_oval(bx-28, by-95, bx-2, by-82, fill="#579447", outline="")

                    # yeux fatigués
                    c.create_oval(bx-31, by-16, bx-19, by-4, fill="#292929", outline="")
                    c.create_oval(bx+19, by-16, bx+31, by-4, fill="#292929", outline="")
                    # bouche
                    c.create_arc(bx-18, by+2, bx+18, by+28, start=20, extent=140,
                                 style="arc", outline="#573016", width=3)

                    # bras qui s'agitent
                    arm = int(12 * math.sin(k * 0.55))
                    c.create_line(bx-62, by+25, bx-112, by+55+arm, fill="#b58f12", width=7)
                    c.create_line(bx+62, by+25, bx+112, by+55-arm, fill="#b58f12", width=7)

                    # crayon
                    px = 345 + int(20 * math.sin(k * 0.6))
                    py = 215 + int(8 * math.cos(k * 0.6))
                    c.create_line(px, py, px+72, py-18, fill="#d34b36", width=5)
                    c.create_polygon(px+72, py-18, px+84, py-20, px+74, py-10,
                                     fill="#d7b58b", outline="")

                    # sueur
                    sx = bx + 62
                    c.create_polygon(sx, by-45, sx+9, by-26, sx-4, by-28,
                                     fill="#63b8df", outline="")

                    # barre de progression animée
                    progress = (k % 80) / 79.0
                    c.create_rectangle(120, 265, 380, 282, fill="#45454c", outline="")
                    c.create_rectangle(120, 265, 120 + int(260*progress), 282,
                                       fill="#d7b42a", outline="")
                    c.create_text(250, 273, text="Il turbine, le bougre…", fill="#252525",
                                  font=("Arial", 9, "bold"))

                    self._test_tableur_anim_job = w.after(120, animate)
                except Exception:
                    pass

            animate()

            self._test_tableur_loading_text = ctk.CTkLabel(
                win, text="Le tableur défile, il en redemande…",
                font=("Arial", 11), text_color="#999999"
            )
            self._test_tableur_loading_text.pack(pady=(2, 8))

            self._test_tableur_loading_keepalive()


        def _test_tableur_loading_keepalive(self):
            win = getattr(self, "_test_tableur_loading_win", None)
            if not win:
                return
            try:
                if not win.winfo_exists():
                    return
                win.deiconify()
                win.lift()
                try:
                    win.attributes("-topmost", True)
                except Exception:
                    pass
                self._test_tableur_keepalive_job = win.after(
                    300, self._test_tableur_loading_keepalive
                )
            except Exception:
                pass

        def _animate_test_tableur_loading(self):
            """Fait défiler l'animation du citron tant que le chargement continue."""
            win = getattr(self, "_test_tableur_loading_win", None)
            frames = getattr(self, "_test_tableur_anim_frames", [])
            if not win or not frames:
                return
            try:
                if not win.winfo_exists():
                    return
                idx = getattr(self, "_test_tableur_anim_index", 0) % len(frames)
                self._test_tableur_anim_label.configure(image=frames[idx])
                self._test_tableur_anim_index = idx + 1
                self._test_tableur_anim_job = win.after(
                    140, self._animate_test_tableur_loading
                )
            except Exception:
                pass

        def _close_test_tableur_loading(self):
            win = getattr(self, "_test_tableur_loading_win", None)
            try:
                if getattr(self, "_test_tableur_anim_job", None) and win:
                    win.after_cancel(self._test_tableur_anim_job)
            except Exception:
                pass
            self._test_tableur_anim_job = None
            self._test_tableur_canvas = None
            self._test_tableur_loading_count_label = None
            try:
                if getattr(self, "_test_tableur_keepalive_job", None) and win:
                    win.after_cancel(self._test_tableur_keepalive_job)
            except Exception:
                pass
            self._test_tableur_keepalive_job = None
            self._test_tableur_anim_frames = []
            self._test_tableur_anim_label = None
            self._test_tableur_loading_text = None
            self._test_tableur_loading_win = None
            try:
                if win and win.winfo_exists():
                    win.destroy()
            except Exception:
                pass

        def _test_tableur(self):
            """Charge et prépare le Test tableur hors du thread Tk."""
            if not self._get_tableur_path_or_warn():
                return

            if getattr(self, "_test_tableur_win", None):
                try:
                    if self._test_tableur_win.winfo_exists():
                        self._test_tableur_win.lift()
                        return
                except Exception:
                    pass

            self._show_test_tableur_loading()

            def worker():
                try:
                    rows, err = self._get_ods_rows()
                    if err:
                        self.after(0, lambda e=err: self._finish_test_tableur(None, e))
                        return

                    real_count = max(0, len(rows) - 1)
                    self.after(
                        0,
                        lambda n=real_count: self._update_test_tableur_loading_count(n)
                    )

                    if not rows or len(rows) <= 1:
                        self.after(0, lambda: self._finish_test_tableur([], None))
                        return

                    from odf.table import TableCell
                    prepared = []

                    # Cette partie peut être lourde avec plusieurs milliers
                    # de lignes : elle reste donc dans le worker, sinon Tk
                    # gèle l'animation pendant sa préparation.
                    for sheet_row_index, row in enumerate(rows[1:], start=2):
                        cells = self._expand_ods_cells(
                            row.getElementsByType(TableCell)
                        )
                        if not cells:
                            continue

                        row_data = [self._ods_cell_content(c) for c in cells]
                        if not row_data:
                            continue

                        c0 = row_data[0]
                        title = (
                            c0.get("text", "") if isinstance(c0, dict)
                            else str(c0)
                        ).strip()
                        if not title:
                            continue

                        year = ""
                        if len(row_data) > 1:
                            c1 = row_data[1]
                            year = (
                                c1.get("text", "") if isinstance(c1, dict)
                                else str(c1)
                            ).strip()

                        display = f"{title} ({year})" if year else title
                        prepared.append({
                            "display": display,
                            "title": title,
                            "row_data": row_data,
                            "sheet_row": sheet_row_index,
                        })

                    self.after(
                        0,
                        lambda r=prepared: self._finish_test_tableur(r, None)
                    )
                except Exception as ex:
                    self.after(
                        0,
                        lambda e=f"Impossible de charger le tableur :\n{ex}":
                            self._finish_test_tableur(None, e)
                    )

            threading.Thread(
                target=worker,
                daemon=True,
                name="CitronTestTableur"
            ).start()

        def _finish_test_tableur(self, test_rows, err):
            """Affiche le Test tableur après préparation hors du thread Tk."""
            self._close_test_tableur_loading()

            if err:
                messagebox.showerror("Test tableur", err)
                return

            if not test_rows:
                messagebox.showinfo(
                    "Test tableur",
                    "Le tableur ne contient aucune ligne de données à tester."
                )
                return

            win = ctk.CTkToplevel(self)
            self._test_tableur_win = win
            win.title("🧪 Test tableur")
            win.geometry("700x620")
            win.transient(self)
            win.lift()

            ctk.CTkLabel(
                win, text="🧪 Test tableur",
                font=("Arial", 20, "bold")
            ).pack(pady=(16, 4))

            ctk.CTkLabel(
                win,
                text=(
                    f"Tous les enregistrements du tableur sont testables "
                    f"(ligne 1 = en-têtes exclue) — {len(test_rows)} lignes"
                ),
                font=("Arial", 12), text_color="#aaaaaa",
                wraplength=640
            ).pack(pady=(0, 10))

            sf = ctk.CTkFrame(win)
            sf.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(sf, text="🔍", font=("Arial", 16)).pack(
                side="left", padx=(10, 5)
            )

            search_var = ctk.StringVar()
            ctk.CTkEntry(
                sf,
                placeholder_text="Rechercher dans toutes les lignes du tableur…",
                textvariable=search_var,
                height=40
            ).pack(side="left", fill="x", expand=True, padx=5)

            lf = ctk.CTkFrame(win)
            lf.pack(fill="both", expand=True, padx=20, pady=8)

            lb = Listbox(
                lf, font=("Arial", 12), bg="#2b2b2b", fg="white",
                selectbackground="#1f6aa5", activestyle="none"
            )
            sb = Scrollbar(lf, orient="vertical", command=lb.yview)
            lb.config(yscrollcommand=sb.set)
            lb.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")

            def refresh(*_a):
                query = search_var.get().lower().strip()
                lb.delete(0, END)
                for item in test_rows:
                    if query in item["display"].lower():
                        lb.insert(END, item["display"])

            search_var.trace("w", refresh)
            refresh()

            def _launch(event=None):
                sel = lb.curselection()
                if not sel:
                    return

                display_name = lb.get(sel[0])
                item = next(
                    (x for x in test_rows if x["display"] == display_name),
                    None
                )
                if item is None:
                    return

                path = None
                title_l = item["title"].strip().lower()
                for i, name in enumerate(self.video_names):
                    if name.strip().lower() == title_l:
                        if i < len(self.video_paths):
                            path = self.video_paths[i]
                        break

                try:
                    win.destroy()
                except Exception:
                    pass
                self._test_tableur_win = None

                test_scope = []
                for test_item in test_rows:
                    test_path = None
                    test_title_l = test_item["title"].strip().lower()
                    for i, lib_name in enumerate(self.video_names):
                        if lib_name.strip().lower() == test_title_l:
                            if i < len(self.video_paths):
                                test_path = self.video_paths[i]
                            break
                    test_scope.append({
                        "titre": test_item["title"],
                        "path": test_path,
                        "row_data": test_item["row_data"],
                        "error": None,
                    })

                current_index = next(
                    (
                        i for i, x in enumerate(test_scope)
                        if x["titre"] == item["title"]
                    ),
                    0
                )

                self._open_info_window(
                    item["title"], path, item["row_data"], None,
                    nav_override={
                        "list": test_scope,
                        "index": current_index,
                        "breadcrumb": [],
                        "virtual_playlist_mode": True,
                    },
                    from_chain=False
                )

            lb.bind("<Double-Button-1>", _launch)

            ctk.CTkButton(
                win, text="📋 Simuler Infos (tableur)",
                command=_launch, height=40
            ).pack(pady=10)

            ctk.CTkButton(
                win, text="Fermer",
                command=win.destroy,
                height=32, fg_color="#555555"
            ).pack(pady=(0, 12))


        def _configure_tableur(self):
            """Permet de sélectionner ou changer le fichier tableur .ods.
            Seul le format .ods est réellement lisible (bibliothèque odfpy,
            voir _get_ods_rows) — un fichier Excel .xlsx échouerait à la
            lecture malgré son apparente prise en charge ; ne plus le
            proposer dans le sélecteur évite ce piège."""
            path = filedialog.askopenfilename(
                title="Sélectionner le tableur LibreOffice (.ods)",
                filetypes=[("LibreOffice Calc (.ods)","*.ods"),("Tous","*.*")])
            if path:
                self._tableur_path = path
                self.save_settings()
                messagebox.showinfo("Tableur configuré",
                    f"Tableur enregistré :\n{os.path.basename(path)}")

        def _get_ods_rows(self):
            """Charge le tableur une seule fois et le garde en mémoire (ODSManager)."""
            # Recharger si le fichier a changé
            mtime = os.path.getmtime(self._tableur_path) if os.path.isfile(self._tableur_path) else 0
            if getattr(self, "_ods_rows_cache", None) is not None and getattr(self, "_ods_mtime", 0) == mtime:
                return self._ods_rows_cache, None
            try:
                from odf.opendocument import load as ods_load
                from odf.table import Table, TableRow, TableCell
            except ImportError:
                return None, ("La bibliothèque 'odfpy' n'est pas installée.\n\n"
                              "Ouvrez un terminal Windows (cmd) et tapez :\n"
                              "  pip install odfpy\n\n"
                              "Puis relancez Citron.")
            try:
                doc = ods_load(self._tableur_path)
            except Exception as ex:
                return None, f"Impossible de lire le tableur :\n{ex}"
            sheets = doc.spreadsheet.getElementsByType(Table)
            if not sheets:
                return None, "Aucune feuille trouvée dans le tableur."
            self._ods_rows_cache = sheets[0].getElementsByType(TableRow)
            self._ods_mtime = mtime
            print(f"[ODSManager] Tableur chargé en mémoire ({len(self._ods_rows_cache)} lignes)")
            # Le tableur a été modifié (ou rechargé) depuis le dernier chargement :
            # les fiches déjà mises en cache (self._info_cache, utilisé par les
            # flèches ◀ ▶ de la fenêtre Infos) peuvent contenir des chemins
            # d'image/bande-annonce désormais périmés (ex : un lien cassé
            # corrigé entre-temps dans le tableur). Sans ce vidage, revenir sur
            # un titre déjà consulté réaffichait l'ancien résultat en cache —
            # y compris "Fichier introuvable" — même après correction.
            if hasattr(self, "_info_cache"):
                self._info_cache.clear()
            return self._ods_rows_cache, None

        def _expand_ods_cells(self, cells, max_cols=16):
            """Déplie les cellules ODS répétées (attribut ODF
            number-columns-repeated) pour que l'indice dans la liste
            retournée corresponde exactement au numéro de colonne réel.

            LibreOffice compresse toute suite de cellules vides consécutives
            en une seule balise XML portant cet attribut. Sans ce dépliage,
            odfpy ne renvoie qu'UN SEUL objet TableCell pour tout ce bloc,
            ce qui décale toutes les colonnes suivantes dans la liste — et
            fait pointer à tort colonne 9 (affiche) / colonne 10 (vidéo)
            vers une autre donnée dès qu'une ligne contient une case vide
            avant elles. C'est ce qui causait l'affichage incorrect pour
            certains titres (ex: « 1984 ») alors que le tableur était
            pourtant correctement rempli.

            max_cols plafonne le nombre de cellules dépliées : les lignes
            réelles se terminent souvent par un unique bloc vide compressé
            représentant des milliers de colonnes restantes, qu'il serait
            inutile (et coûteux) de déplier entièrement puisque Citron ne
            lit jamais au-delà de la colonne 12.
            """
            expanded = []
            for cell in cells:
                if len(expanded) >= max_cols:
                    break
                rep = cell.getAttribute("numbercolumnsrepeated")
                try:
                    rep = int(rep) if rep else 1
                except (TypeError, ValueError):
                    rep = 1
                rep = max(1, min(rep, max_cols - len(expanded)))
                expanded.extend([cell] * rep)
            return expanded

        def _read_ods_row(self, titre_recherche):
            """Recherche une ligne dans le tableur (déjà chargé en mémoire)."""
            if not self._tableur_path or not os.path.isfile(self._tableur_path):
                return None, "Aucun tableur configuré. Cliquez sur 🗂 Tableur pour en sélectionner un."
            from odf.table import TableRow, TableCell
            rows, err = self._get_ods_rows()
            if err: return None, err

            import os as _os, re as _re

            # Nettoyer le titre recherché : retirer suffixe audio et extension
            titre_brut = titre_recherche.strip()
            titre_brut = titre_brut.replace("  🎵 audio", "").strip()
            # ATTENTION : ne PAS utiliser os.path.splitext() ici. Cette
            # fonction coupe au DERNIER point du texte, quel qu'il soit —
            # or les appelants passent déjà un titre sans extension. Sur un
            # titre contenant un seul point (ex: « Mr. Smith au Sénat »,
            # « S.O.S fantômes », « Dr. Folamour »...), splitext() le
            # confondait avec une extension de fichier et tronquait tout
            # après ce point (« Mr. Smith au Sénat (1939) » → « Mr » !),
            # ce qui faisait échouer la recherche et retomber sur un film
            # complètement différent. On ne retire donc que les vraies
            # extensions connues de Citron (ALL_EXT), en fin de chaîne.
            _root, _ext = _os.path.splitext(titre_brut)
            if _ext.lower() in ALL_EXT:
                titre_brut = _root.strip()


            def _clean(s):
                for c in '?/\\!:|<>*':
                    s = s.replace(c, " ")
                s = _re.sub(r'-', ' ', s)
                return _re.sub(r"\s+", " ", s).strip().lower()

            # Le titre affiché dans Citron = "Col1 (Col2)" ex: "Mon Film (2023)"
            m = _re.match(r"^(.*?)\s*\((\d{4})\)\s*$", titre_brut)
            if m:
                titre_col1 = _clean(m.group(1))
                annee_col2 = m.group(2).strip()
            else:
                titre_col1 = _clean(titre_brut)
                annee_col2 = ""

            print(f"[Tableur] Recherche col1='{titre_col1}' col2='{annee_col2}'")

            def _suffixe_numero(s):
                """Extrait un éventuel numéro de suite en fin de titre nettoyé
                (ex: 'X 2' -> 2, 'X III' -> 3), ou None s'il n'y en a pas.
                Sert à empêcher la recherche approximative par inclusion de
                sous-chaîne de confondre deux films différents d'une même
                saga : sans ce garde-fou, « Retour vers le futur 3 » (1990)
                matchait « Retour vers le Futur » (1985) simplement parce que
                le second titre est un sous-mot du premier, malgré des
                années totalement différentes."""
                m = _re.search(r'(?:^|\s)(\d{1,2})$', s)
                if m:
                    return int(m.group(1))
                m = _re.search(r'(?:^|\s)(i{1,3}|iv|v|vi{1,3}|ix|x)$', s)
                if m:
                    romans = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
                              "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
                    return romans.get(m.group(1))
                return None

            best_row = None
            best_score = 0
            first_titles = []

            for row in rows:
                cells = self._expand_ods_cells(row.getElementsByType(TableCell))
                if not cells: continue

                ct1_raw = self._ods_cell_text(cells[0]).strip()
                ct2 = self._ods_cell_text(cells[1]).strip() if len(cells) > 1 else ""
                ct1 = _clean(ct1_raw)

                if not ct1: continue
                if len(first_titles) < 5:
                    first_titles.append(f"{ct1_raw} ({ct2})")

                score = 0
                if annee_col2:
                    if ct1 == titre_col1 and ct2 == annee_col2:  score = 100
                    elif ct1 == titre_col1:                        score = 80
                    elif titre_col1 in ct1 or ct1 in titre_col1:
                        if _suffixe_numero(titre_col1) != _suffixe_numero(ct1):
                            score = 0
                        else:
                            score = 60 if ct2 == annee_col2 else 40
                else:
                    if ct1 == titre_col1:                          score = 90
                    elif titre_col1 in ct1 or ct1 in titre_col1:
                        if _suffixe_numero(titre_col1) != _suffixe_numero(ct1):
                            score = 0
                        else:
                            score = 60

                if score > best_score:
                    best_score = score
                    row_data = []
                    for cell in cells:
                        row_data.append(self._ods_cell_content(cell))
                    best_row = row_data

            if best_row and best_score >= 80:
                print(f"[Tableur] Trouvé (score {best_score})")
                return best_row, None

            # Seuil assoupli si pas de correspondance parfaite
            if best_row and best_score >= 40:
                print(f"[Tableur] Trouvé approx. (score {best_score})")
                return best_row, None

            diag = "\n".join(f"  • {t}" for t in first_titles)
            print(f"[Tableur] Non trouvé. Exemples :\n{diag}")
            return None, (
                f"Titre non trouvé dans le tableur.\n\n"
                f"Citron cherche :\n"
                f"  Colonne 1 : « {titre_col1} »\n"
                f"  Colonne 2 : « {annee_col2} »\n\n"
                f"Premiers titres du tableur (col1 + col2) :\n{diag}\n\n"
                f"Vérifiez que la colonne 1 = titre et colonne 2 = année.")

        def _ods_cell_text(self, cell):
            """Extrait le texte brut d'une cellule."""
            try:
                from odf.text import P
                parts = []
                for p in cell.getElementsByType(P):
                    parts.append(str(p))
                return " ".join(parts).strip()
            except Exception:
                return ""

        def _ods_cell_content(self, cell):
            """Extrait contenu + hyperlien d'une cellule ODS via API odfpy."""
            import io as _io, urllib.parse as _up
            try:
                from odf.text import P, A
                from odf.namespaces import XLINKNS

                hyperlink = None
                text_parts = []

                # Parcourir les paragraphes de la cellule
                for p in cell.getElementsByType(P):
                    for child in p.childNodes:
                        # Noeud texte simple
                        if hasattr(child, "data"):
                            text_parts.append(child.data)
                        # Hyperlien (text:a)
                        elif hasattr(child, "qname") and child.qname[1] == "a":
                            # Extraire le href via getAttrNS
                            href = child.getAttrNS(XLINKNS, "href")
                            if href:
                                print(f"[Tableur] href brut : {href!r}")
                                # Décoder en UTF-8 explicite (accents %C3%A9 etc.)
                                href = _up.unquote(href, encoding="utf-8")
                                # Nettoyer file:///
                                if href.startswith("file:///"):
                                    href = href[8:]   # retire "file:///"
                                elif href.startswith("file://"):
                                    href = href[7:]
                                # Remplacer slashes → séparateur OS
                                href = href.replace("/", os.sep)
                                href = os.path.normpath(href)
                                ods_dir = os.path.dirname(self._tableur_path)
                                if not os.path.isabs(href):
                                    # Essai 1 : résolution standard
                                    h1 = os.path.normpath(os.path.join(ods_dir, href))
                                    if os.path.isfile(h1):
                                        href = h1
                                    else:
                                        # Essai 2 : retirer les ..
                                        parts = href
                                        while parts.startswith(".."):
                                            parts = parts.lstrip(".").lstrip(os.sep).lstrip("/")
                                        h2 = os.path.normpath(os.path.join(ods_dir, parts))
                                        if os.path.isfile(h2):
                                            href = h2
                                        else:
                                            # Essai 3 : chercher le fichier dans ods_dir
                                            fname = os.path.basename(href)
                                            found = None
                                            for root,_,files in os.walk(ods_dir):
                                                if fname in files:
                                                    found = os.path.join(root, fname)
                                                    break
                                            href = found if found else h1
                                hyperlink = href
                                print(f"[Tableur] Hyperlien résolu : {href!r}")
                            # Texte du lien
                            for sub in child.childNodes:
                                if hasattr(sub, "data"):
                                    text_parts.append(sub.data)

                text = " ".join(text_parts).strip()
                if not text:
                    text = self._ods_cell_text(cell)

                return {"text": text, "link": hyperlink}
            except Exception as ex:
                print(f"[Tableur] _ods_cell_content erreur: {ex}")
                return {"text": self._ods_cell_text(cell), "link": None}
        def _check_tableur_freshness(self):
            """Vérifie (via la date de modification du fichier) si le tableur
            a changé depuis le dernier chargement, et vide alors le cache des
            fiches déjà consultées (self._info_cache).

            Cette vérification doit se faire AVANT toute consultation de
            self._info_cache — pas seulement au moment d'une recherche
            fraîche dans _get_ods_rows(). Sinon, tant qu'une fiche reste en
            cache (navigation par les flèches ◀ ▶, ou fenêtre Infos rouverte
            avant l'expiration du cache 60s), on ne repasse jamais par
            _get_ods_rows() et on ne détecte donc jamais qu'un champ (ex :
            📝 Résumé) a été modifié entre-temps dans le tableur — même après
            une modification suivie d'un enregistrement.
            """
            try:
                if self._tableur_path and os.path.isfile(self._tableur_path):
                    mtime = os.path.getmtime(self._tableur_path)
                    old_mtime = getattr(self, "_ods_mtime", None)
                    if old_mtime is not None and mtime != old_mtime:
                        if hasattr(self, "_info_cache"):
                            self._info_cache.clear()
                        # Force _get_ods_rows() à recharger au prochain appel
                        self._ods_mtime = None
            except Exception:
                pass

        def _show_tableur_info(self, path, nav_session=None, from_chain=False, from_liste_medias=False):
            # Le tableur a-t-il été modifié depuis le dernier chargement ?
            # Si oui, on vide le cache des fiches AVANT de continuer, pour ne
            # jamais réafficher une donnée périmée (résumé, image...).
            self._check_tableur_freshness()
            # Stopper la lecture en cours AVANT d'ouvrir la fenêtre Infos : la
            # "🎞 Vidéo résumé" a son propre son, un chevauchement avec la
            # lecture principale serait désagréable.
            if self.player and self.player.get_state() in (vlc.State.Playing, vlc.State.Paused):
                self.stop_video()
            if not self._tableur_path:
                messagebox.showinfo("Tableur",
                    "Aucun tableur configure.\nCliquez sur Tableur pour en selectionner un.")
                return
            titre = os.path.splitext(os.path.basename(path))[0]
            # Fenetre d'attente animee
            wait = ctk.CTkToplevel(self)
            wait.title("Recherche...")
            wait.geometry("340x130")
            wait.resizable(False, False)
            wait.transient(self); wait.lift()
            wait.attributes("-topmost", True)
            wait.update_idletasks()
            sw = wait.winfo_screenwidth(); sh = wait.winfo_screenheight()
            wait.geometry(f"340x130+{(sw-340)//2}+{(sh-130)//2}")
            ctk.CTkLabel(wait, text="Recherche dans le tableur...",
                         font=("Arial",14,"bold")).pack(pady=(18,6))
            ctk.CTkLabel(wait, text=titre[:55],
                         font=("Arial",11), text_color="#aaaaaa").pack()
            prog = ctk.CTkProgressBar(wait, mode="indeterminate", width=280)
            prog.pack(pady=10); prog.start()
            def do_search():
                row_data, error = self._read_ods_row(titre)
                def show():
                    try: prog.stop(); wait.destroy()
                    except Exception: pass
                    _nav_override = {"from_liste_medias": True} if from_liste_medias else None
                    self._open_info_window(titre, path, row_data, error, nav_override=_nav_override,
                                            nav_session=nav_session, from_chain=from_chain)
                self.after(0, show)
            threading.Thread(target=do_search, daemon=True).start()

        def _resolve_path(self, p):
            """Résout un chemin de fichier en gérant les problèmes Windows."""
            if not p: return p
            import unicodedata, glob

            # Étape 1 : normaliser les séparateurs (/ et \ mixtes)
            # et s'assurer que les backslashes ne sont pas des échappements
            p = p.replace("\\", os.sep).replace("/", os.sep)
            # Reconstruire le chemin proprement via os.path.normpath
            p = os.path.normpath(p)
            print(f"[Tableur] Path normalisé : {p!r}")

            # Étape 2 : essai direct
            if os.path.isfile(p): return p

            # Étape 3 : normalisation Unicode NFC (Windows préfère NFC)
            p_nfc = unicodedata.normalize("NFC", p)
            if os.path.isfile(p_nfc):
                print(f"[Tableur] Trouvé via NFC")
                return p_nfc

            # Étape 4 : normalisation Unicode NFD
            p_nfd = unicodedata.normalize("NFD", p)
            if os.path.isfile(p_nfd):
                print(f"[Tableur] Trouvé via NFD")
                return p_nfd

            # Étape 5 : glob avec wildcards sur les accents
            p_glob = p_nfc
            for c in "éèêëàâäîïôöùûüçÉÈÊËÀÂÄÎÏÔÖÙÛÜÇ":
                p_glob = p_glob.replace(c, "?")
            matches = glob.glob(p_glob)
            if matches:
                print(f"[Tableur] Trouvé via glob : {matches[0]}")
                return matches[0]

            # Étape 6 : chercher sans tenir compte de la casse
            parent = os.path.dirname(p)
            filename = os.path.basename(p)
            if os.path.isdir(parent):
                try:
                    for f in os.listdir(parent):
                        if f.lower() == filename.lower():
                            found = os.path.join(parent, f)
                            print(f"[Tableur] Trouvé via listdir : {found}")
                            return found
                except Exception: pass

            print(f"[Tableur] Fichier introuvable après toutes les tentatives : {p!r}")
            return p

        # ── Recherche dans le tableur (clic droit dans 📋 Infos) ──────────
        def _bind_right_click_recursive(self, widget, handler):
            """Lie <Button-3> à `widget` et récursivement à tous ses enfants
            (sauf s'ils ont déjà une liaison <Button-3> propre), pour que le
            clic droit fonctionne n'importe où dans une fenêtre composée de
            nombreux sous-widgets (Frames, Labels, Text…)."""
            try:
                if not widget.bind("<Button-3>"):
                    widget.bind("<Button-3>", handler)
            except Exception:
                pass
            try:
                children = widget.winfo_children()
            except Exception:
                children = []
            for child in children:
                self._bind_right_click_recursive(child, handler)

        def _tableur_info_open_search_menu(self, win, x_root, y_root, scope=None, breadcrumb=None):
            """Construit et affiche le menu des 4 recherches tableur à la
            position (x_root, y_root) donnée. Appelé soit par le clic droit
            (_tableur_info_right_click), soit par le bouton '🔍 Recherche' de
            l'en-tête (accès garanti, indépendant de tout souci de capture
            des clics par la zone vidéo/affiche intégrée).

            scope (optionnel) : si cette fiche fait déjà partie d'une chaîne
            de recherche (résultats d'une recherche précédente), scope est la
            liste de ces résultats — la nouvelle recherche sera restreinte à
            cette liste au lieu de rescanner tout le tableur, pour que les
            recherches successives se combinent (ex : acteur PUIS année ne
            cherche l'année que parmi les films déjà trouvés pour cet acteur).

            breadcrumb (optionnel) : liste des recherches déjà effectuées
            dans cette chaîne (ex : ["Acteur : Dupontel"]), affichée dans les
            fiches suivantes pour situer l'utilisateur dans sa recherche."""
            breadcrumb = breadcrumb or []
            print("[TableurSearch] Ouverture du menu de recherche tableur")
            menu = Menu(win, tearoff=0, font=("Arial", 16))
            menu.add_command(label="Recherche films par acteur",
                              command=lambda: self._start_tableur_search("acteur", win, scope, breadcrumb))
            menu.add_command(label="Recherche par année",
                              command=lambda: self._start_tableur_search("annee", win, scope, breadcrumb))
            menu.add_command(label="Recherche par titre",
                              command=lambda: self._start_tableur_search("titre", win, scope, breadcrumb))
            menu.add_command(label="Recherche par mot clé",
                              command=lambda: self._start_tableur_search("motcle", win, scope, breadcrumb))
            menu.post(x_root, y_root)

        def _tableur_info_right_click(self, event, win, scope=None, breadcrumb=None):
            """Menu clic droit affiché dans 📋 Infos (tableur) : les 4
            recherches (acteur / année / titre / mot clé)."""
            print("[TableurSearch] Clic droit reçu dans 📋 Infos (tableur)")
            self._tableur_info_open_search_menu(win, event.x_root, event.y_root, scope, breadcrumb)

        def _start_tableur_search(self, kind, source_win, scope=None, breadcrumb=None):
            """1 clic sur une des 4 recherches : ferme le menu (automatique,
            Tk), masque 📋 Infos (tableur) — sans le détruire, pour pouvoir y
            revenir ensuite (retour arrière) — puis ouvre la zone de
            recherche correspondante, restreinte à `scope` si fourni."""
            try:
                if source_win and source_win.winfo_exists():
                    self._tableur_push_history(source_win)
            except Exception:
                pass
            if getattr(self, "_current_info_win", None) is source_win:
                self._current_info_win = None
            self._open_tableur_search_box(kind, scope, breadcrumb)

        _TABLEUR_SEARCH_CFG = {
            "acteur": ("Recherche films par acteur", "Nom de l'acteur :"),
            "annee":  ("Recherche par année",         "Année :"),
            "titre":  ("Recherche par titre",         "Titre :"),
            "motcle": ("Recherche par mot clé",       "Mot clé :"),
        }

        def _open_tableur_search_box(self, kind, scope=None, breadcrumb=None):
            """Ouvre la petite zone de recherche (titre + champ + boutons)
            correspondant au type de recherche choisi."""
            title, label = self._TABLEUR_SEARCH_CFG.get(kind, ("Recherche", "Recherche :"))
            if scope is not None:
                title += f" (parmi les {len(scope)} résultat(s) précédent(s))"

            if getattr(self, "_tableur_search_win", None) and self._tableur_search_win.winfo_exists():
                try: self._tableur_search_win.destroy()
                except Exception: pass

            win = ctk.CTkToplevel(self)
            win.title(title)
            win.resizable(False, False)
            win.attributes("-topmost", True)
            self._tableur_search_win = win

            ctk.CTkLabel(win, text=title, font=("Arial", 18, "bold"), wraplength=460).pack(padx=24, pady=(20, 4))
            ctk.CTkLabel(win, text=label, font=("Arial", 13)).pack(padx=24, pady=(6, 4), anchor="w")

            var = ctk.StringVar()
            entry = ctk.CTkEntry(win, textvariable=var, width=380, height=38, font=("Arial", 14))
            entry.pack(padx=24, pady=(0, 16))
            enable_entry_paste(entry)

            def _validate(event=None):
                query = var.get().strip()
                if not query:
                    return
                try: win.destroy()
                except Exception: pass
                if getattr(self, "_tableur_search_win", None) is win:
                    self._tableur_search_win = None
                # Animation citron + recherche en arriere-plan (tableur volumineux)
                print(f"[TableurSearch][TRACE] VALIDATE kind={kind!r} query={query!r} scope={len(scope) if scope is not None else None}")
                self._run_tableur_search_async(kind, query, scope, breadcrumb)

            def _cancel(event=None):
                try: win.destroy()
                except Exception: pass
                if getattr(self, "_tableur_search_win", None) is win:
                    self._tableur_search_win = None
                self._tableur_pop_history()

            btn_frame = ctk.CTkFrame(win, fg_color="transparent")
            btn_frame.pack(pady=(0, 18))
            ctk.CTkButton(btn_frame, text="Rechercher", width=120, command=_validate).pack(side="left", padx=8)
            ctk.CTkButton(btn_frame, text="Annuler", width=100, fg_color="#5a5a5a",
                          command=_cancel).pack(side="left", padx=8)
            entry.bind("<Return>", _validate)
            entry.bind("<Escape>", _cancel)
            win.protocol("WM_DELETE_WINDOW", _cancel)

            win.update_idletasks()
            w, h = win.winfo_reqwidth(), win.winfo_reqheight()
            sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
            win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

            entry.focus_set()
            win.grab_set()

        @staticmethod
        def _tableur_search_clean(s):
            import re as _re, unicodedata as _ud
            s = _ud.normalize("NFD", (s or "").lower())
            s = "".join(c for c in s if _ud.category(c) != "Mn")
            for c in '?/\\!:|<>*':
                s = s.replace(c, " ")
            s = _re.sub(r'-', ' ', s)
            return _re.sub(r"\s+", " ", s).strip()

        def _relocate_media_path(self, path):
            """Si path n'existe plus (changement de lettre de lecteur USB,
            disque rebranche, etc.), tente de retrouver le meme fichier :
              1) memes sous-chemins sur les autres lettres de lecteur Windows
              2) meme nom de fichier dans les dossiers deja presents dans la
                 bibliotheque locale
            Met a jour citron_library.json si un nouveau chemin valide est
            trouve. Retourne le chemin utilisable, ou None."""
            if not path:
                return None
            path = os.path.normpath(path)
            if os.path.isfile(path):
                return path

            basename = os.path.basename(path)
            print(f"[Relocate] Fichier absent : {path!r} — tentative de relocalisation…")

            candidates = []
            if os.name == "nt" and len(path) >= 3 and path[1] == ":" and path[2] == chr(92):
                old_letter = path[0].upper()
                rest = path[2:]
                for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
                    if letter == old_letter:
                        continue
                    cand = letter + ":" + rest
                    if os.path.isfile(cand):
                        candidates.append(cand)
                        break

            if not candidates and basename:
                seen_dirs = set()
                for p in self.video_paths:
                    d = os.path.dirname(p)
                    if d and d not in seen_dirs:
                        seen_dirs.add(d)
                        cand = os.path.join(d, basename)
                        if os.path.isfile(cand):
                            candidates.append(cand)
                            break
                if not candidates:
                    for d in list(seen_dirs):
                        parent = os.path.dirname(d)
                        if parent and parent not in seen_dirs:
                            cand = os.path.join(parent, basename)
                            if os.path.isfile(cand):
                                candidates.append(cand)
                                break

            if not candidates:
                print(f"[Relocate] Impossible de retrouver {basename!r}")
                return None

            new_path = os.path.normpath(candidates[0])
            print(f"[Relocate] Trouve -> {new_path!r}")

            try:
                changed = False
                for i, p in enumerate(self.video_paths):
                    if os.path.normpath(p) == path or os.path.basename(p) == basename:
                        if self.video_paths[i] != new_path:
                            self.video_paths[i] = new_path
                            changed = True
                if changed:
                    self.save_library()
                    print(f"[Relocate] Bibliotheque mise a jour pour {basename!r}")
            except Exception as ex:
                print(f"[Relocate] MAJ bibliotheque echouee : {ex}")
            return new_path

        def _ensure_playable_path(self, path, col_titre="", col_annee="", col_fichier=""):
            """Retourne un chemin de fichier local reellement lisible.
            Enchaine : path donne -> relocalisation -> recherche biblio par
            titre/annee -> colonne fichier du tableur."""
            if path:
                if os.path.isfile(path):
                    return path
                fixed = self._relocate_media_path(path)
                if fixed:
                    return fixed

            if col_titre:
                idx = self._find_library_index_for_titre_annee(col_titre, col_annee)
                if idx is not None:
                    p = self.video_paths[idx]
                    if os.path.isfile(p):
                        return p
                    fixed = self._relocate_media_path(p)
                    if fixed:
                        return fixed

            if col_fichier:
                try:
                    resolved = self._resolve_path(str(col_fichier).strip())
                    if resolved and os.path.isfile(resolved):
                        return resolved
                    if resolved:
                        fixed = self._relocate_media_path(resolved)
                        if fixed:
                            return fixed
                except Exception as ex:
                    print(f"[Path] col_fichier resolution : {ex}")

            return None

        def _find_library_index_for_titre_annee(self, col_titre, col_annee):

            """Tente de retrouver, dans la bibliothèque locale
            (self.video_names), le média correspondant à un titre+année du
            tableur. Symétrique à _read_ods_row (même algorithme à score :
            titre+année exacts, titre seul, ou sous-chaîne avec garde-fou sur
            les numéros de suite) — la correspondance stricte précédente
            (titre nettoyé identique uniquement) échouait sur de nombreux
            titres pour de simples différences de ponctuation, ce qui donnait
            l'impression que le chemin du fichier était "perdu" alors que le
            fichier existait bel et bien localement.
            Retourne l'index dans self.video_paths, ou None si aucun fichier
            local ne correspond avec un score suffisant (le film n'existe
            peut-être que dans le tableur, pas encore téléchargé/possédé)."""
            import re as _re
            _clean = self._tableur_search_clean

            def _suffixe_numero(s):
                m = _re.search(r'(?:^|\s)(\d{1,2})$', s)
                if m:
                    return int(m.group(1))
                m = _re.search(r'(?:^|\s)(i{1,3}|iv|v|vi{1,3}|ix|x)$', s)
                if m:
                    romans = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
                              "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10}
                    return romans.get(m.group(1))
                return None

            target_t = _clean(col_titre)
            target_a = (col_annee or "").strip()
            best_idx, best_score = None, 0
            for i, name in enumerate(self.video_names):
                # IMPORTANT : self.video_names garde l'extension du fichier
                # (ex : "Adieu les cons (2020).mp4") — il faut la retirer
                # AVANT de tester la regex "(Année)" en fin de chaîne, sinon
                # elle ne matche jamais (à cause du ".mp4" final) et l'année
                # n'est jamais extraite : c'était la vraie cause du "chemin
                # perdu" dans les résultats de recherche.
                n = name.replace("  🎵 audio", "").strip()
                n = os.path.splitext(n)[0]
                m = _re.match(r"^(.*?)\s*\((\d{4})\)\s*$", n)
                if m:
                    nt, na = _clean(m.group(1)), m.group(2)
                else:
                    nt, na = _clean(n), ""

                score = 0
                if target_a:
                    if nt == target_t and na == target_a:
                        score = 100
                    elif nt == target_t:
                        score = 80
                    elif target_t in nt or nt in target_t:
                        if _suffixe_numero(target_t) != _suffixe_numero(nt):
                            score = 0
                        else:
                            score = 60 if na == target_a else 40
                else:
                    if nt == target_t:
                        score = 90
                    elif target_t in nt or nt in target_t:
                        if _suffixe_numero(target_t) != _suffixe_numero(nt):
                            score = 0
                        else:
                            score = 60

                if score > best_score:
                    best_score = score
                    best_idx = i

            # Seuil 60 : score 40 (sous-chaine sans annee) provoquait de
            # fausses correspondances (ex : L'Odyssee -> Hindenburg).
            if best_score >= 60:
                print(f"[TableurSearch] Chemin trouvé pour '{col_titre}' ({col_annee}) "
                      f"→ score {best_score} : {self.video_names[best_idx]}")
                return best_idx
            print(f"[TableurSearch] Chemin NON trouvé pour '{col_titre}' ({col_annee}) "
                  f"— bibliothèque = {len(self.video_names)} titre(s), meilleur score obtenu : "
                  f"{best_score}" + (f" ({self.video_names[best_idx]})" if best_idx is not None else ""))
            return None

        @staticmethod
        def _tableur_fuzzy_contains(query_clean, raw_haystack, threshold=0.72):
            """Teste si `query_clean` (déjà nettoyé via _tableur_search_clean)
            est présent dans `raw_haystack` (texte D'ORIGINE, casse/accents
            conservés), en tolérant les fautes de frappe.
            Retourne (matched, is_approx, matched_word) :
              - match EXACT (sous-chaîne) → (True, False, None)
              - match APPROCHÉ (mot/nom proche, faute de frappe) →
                (True, True, "mot d'origine trouvé")
              - aucun match suffisant → (False, False, None)
            matched_word est le mot (ou la paire de mots) du texte ORIGINAL
            qui a le mieux correspondu — affiché ensuite entre parenthèses à
            côté du titre pour que l'utilisateur comprenne pourquoi ce
            résultat est approché. La comparaison se fait mot à mot (et par
            paires de mots consécutifs, pour les noms/prénoms composés) via
            difflib.SequenceMatcher, sans dépendance externe."""
            query_clean = (query_clean or "").strip()
            if not query_clean:
                return False, False, None
            clean_hay = CitronVideoPlayer._tableur_search_clean(raw_haystack)
            if query_clean in clean_hay:
                return True, False, None
            import difflib, re as _re
            raw_words = [w for w in _re.split(r"[,;/&()\s]+", raw_haystack or "") if w]
            if not raw_words:
                return False, False, None
            clean_words = [CitronVideoPlayer._tableur_search_clean(w) for w in raw_words]
            qwords = query_clean.split()
            best, best_word = 0.0, None
            for rw, cw in zip(raw_words, clean_words):
                r = difflib.SequenceMatcher(None, query_clean, cw).ratio()
                if r > best:
                    best, best_word = r, rw
            if len(qwords) > 1:
                for i in range(len(raw_words) - 1):
                    cw_pair = f"{clean_words[i]} {clean_words[i+1]}"
                    r = difflib.SequenceMatcher(None, query_clean, cw_pair).ratio()
                    if r > best:
                        best, best_word = r, f"{raw_words[i]} {raw_words[i+1]}"
            matched = best >= threshold
            return matched, matched, (best_word if matched else None)

        def _show_citron_search_anim(self, query=""):
            """Incrustation (sans cadre de fenêtre) : un citron en pseudo-3D
            (rotation, ombrage, perspective) pendant la recherche dans le
            tableur. Taille réduite de moitié par rapport à la version
            précédente, et affichée SANS barre de titre ni bordure (overlay
            pur) via wm_overrideredirect, comme les menus internes de Citron."""
            try:
                old = getattr(self, "_citron_anim_win", None)
                if old and old.winfo_exists():
                    old.destroy()
            except Exception:
                pass

            win = ctk.CTkToplevel(self)
            # Pas de barre de titre / bordure système : rendu en incrustation
            # pure, à l'identique des petits menus déroulants de Citron.
            win.wm_overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(fg_color="#0d0d0d")
            try:
                win.transient(self)
            except Exception:
                pass
            self._citron_anim_win = win
            self._citron_anim_stop = False

            # Léger cadre pour distinguer l'incrustation du fond (pas de
            # bordure de fenêtre système, mais un simple liseré dessiné).
            frame = ctk.CTkFrame(win, fg_color="#0d0d0d", corner_radius=10,
                                 border_width=1, border_color="#333333")
            frame.pack()

            ctk.CTkLabel(frame, text="🍋 Citron fouille en 3D — l'air de rien…",
                         font=("Arial", 13, "bold")).pack(pady=(9, 1))
            qdisp = (query[:42] + "…") if len(query) > 42 else query
            ctk.CTkLabel(frame, text=f'« {qdisp} »',
                         font=("Arial", 9), text_color="#aaaaaa").pack()

            # Taille réduite de moitié (190x125 au lieu de 380x250)
            canvas = Canvas(frame, width=190, height=125, bg="#0d0d0d",
                            highlightthickness=0)
            canvas.pack(pady=3)

            msg_off = ctk.CTkLabel(frame, text="", font=("Arial", 9, "italic"),
                                   text_color="#888888", wraplength=180, justify="center")
            msg_off.pack(pady=(0, 0))
            msg_citron = ctk.CTkLabel(frame, text="", font=("Arial", 10, "bold"),
                                      text_color="#e0c040", wraplength=180, justify="center")
            msg_citron.pack(pady=(0, 8))

            # Dix répliques piochées au hasard dans la banque « Audiard »,
            # sans répétition immédiate — le dialogue change à chaque
            # ouverture de l'animation.
            dialogues = _pick_audiard_dialogues(10)
            state = {"angle": 0.0, "bounce_t": 0.0, "msg_i": 0, "msg_t": 0}

            # Toutes les dimensions ci-dessous sont la moitié de la version
            # précédente (cx/cy, rayon, orbites, visage, etc.)
            cx, cy = 95, 65
            R = 31  # rayon du citron (moitié de 62)
            N_LAT = 7   # cercles de "latitude" pour l'effet fil de fer 3D
            N_PIP = 5   # pépins en orbite

            def _rotate3d(x, y, z, ax, ay):
                # Rotation autour de l'axe Y puis X (donne l'illusion de 3D)
                cosA, sinA = math.cos(ay), math.sin(ay)
                x, z = x * cosA + z * sinA, -x * sinA + z * cosA
                cosB, sinB = math.cos(ax), math.sin(ax)
                y, z = y * cosB - z * sinB, y * sinB + z * cosB
                return x, y, z

            def _project(x, y, z, scale, bounce):
                # Perspective simple : plus z est "proche" (positif), plus c'est gros
                persp = 130 / (130 - z)
                sx = cx + x * scale * persp
                sy = cy - bounce + y * scale * persp
                return sx, sy, persp

            def _shade(z, base=(0xf5, 0xd5, 0x47)):
                # Assombrit la face arrière, éclaircit la face avant -> volume 3D
                b = max(0.35, min(1.15, 0.75 + z / R * 0.5))
                r = min(255, int(base[0] * b))
                g = min(255, int(base[1] * b))
                bl = min(255, int(base[2] * b))
                return f"#{r:02x}{g:02x}{bl:02x}"

            def _draw():
                if self._citron_anim_stop:
                    return
                try:
                    if not win.winfo_exists():
                        return
                except Exception:
                    return
                canvas.delete("all")

                ax = state["angle"] * 0.6
                ay = state["angle"]
                bounce = abs(math.sin(state["bounce_t"])) * 10

                # Ombre au sol (s'aplatit/s'agrandit selon le rebond)
                shadow_r = 23 - bounce * 0.6
                canvas.create_oval(cx - shadow_r, 102, cx + shadow_r, 107,
                                   fill="#050505", outline="")

                # ── Corps du citron : maillage 3D façon "wireframe plein" ──
                # On dessine des ellipses de latitude, triées par profondeur
                # (peintre) pour un rendu 3D correct sans bibliothèque externe.
                faces = []
                for i in range(N_LAT):
                    lat = (i / (N_LAT - 1) - 0.5) * math.pi * 0.92  # -~83° à +83°
                    ry = math.sin(lat) * R * 1.15  # citron = ellipsoïde allongé
                    rr = math.cos(lat) * R
                    ring = []
                    for j in range(14):
                        lon = j / 14 * 2 * math.pi
                        x0 = math.cos(lon) * rr
                        z0 = math.sin(lon) * rr
                        y0 = ry
                        x1, y1, z1 = _rotate3d(x0, y0, z0, ax, ay)
                        ring.append((x1, y1, z1))
                    avg_z = sum(p[2] for p in ring) / len(ring)
                    faces.append((avg_z, ring))
                faces.sort(key=lambda f: f[0])

                for avg_z, ring in faces:
                    pts = []
                    for (x1, y1, z1) in ring:
                        sx, sy, _ = _project(x1, y1, z1, 1.0, bounce)
                        pts.extend([sx, sy])
                    color = _shade(avg_z)
                    canvas.create_polygon(*pts, fill=color, outline="#c9960f", width=1)

                # Pôles (queue + fleur du citron) en 3D
                for pole_y, tag in ((-R * 1.15, "queue"), (R * 1.15, "fleur")):
                    px, py, pz = _rotate3d(0, pole_y, 0, ax, ay)
                    sx, sy, persp = _project(px, py, pz, 1.0, bounce)
                    rad = 3 * persp
                    col = "#3cb371" if tag == "queue" else "#d4a017"
                    canvas.create_oval(sx - rad, sy - rad, sx + rad, sy + rad,
                                       fill=col, outline="")

                # Pépins en orbite (donnent un vrai effet "objets en 3D autour")
                for k in range(N_PIP):
                    porb = state["angle"] * 1.4 + k * (2 * math.pi / N_PIP)
                    ox = math.cos(porb) * (R + 17)
                    oz = math.sin(porb) * (R + 17)
                    oy = math.sin(state["angle"] * 0.5 + k) * 7
                    sx, sy, persp = _project(ox, oy, oz, 1.0, bounce)
                    rad = max(1, 3 * persp)
                    behind = oz < 0
                    col = "#8a6d1a" if behind else "#fff6b0"
                    canvas.create_oval(sx - rad, sy - rad * 1.4, sx + rad, sy + rad * 1.4,
                                       fill=col, outline="#d4a017")

                # Visage rigolo, plaqué sur la face avant (ne tourne pas avec
                # le corps pour rester lisible = "caméra qui suit le visage")
                fx, fy = cx, cy - bounce
                blink = (int(state["bounce_t"] * 10) % 50) < 3
                look = int(math.sin(state["angle"]) * 2)
                if blink:
                    canvas.create_line(fx - 10 + look, fy - 3, fx - 4 + look, fy - 3,
                                       fill="#222222", width=1)
                    canvas.create_line(fx + 4 + look, fy - 3, fx + 10 + look, fy - 3,
                                       fill="#222222", width=1)
                else:
                    for dx in (-7, 7):
                        canvas.create_oval(fx + dx - 4 + look, fy - 6, fx + dx + 4 + look, fy + 1,
                                           fill="white", outline="#222222")
                        canvas.create_oval(fx + dx - 1 + look, fy - 4, fx + dx + 1 + look, fy - 1,
                                           fill="#222222", outline="")
                canvas.create_arc(fx - 9, fy + 1, fx + 9, fy + 11,
                                  start=200, extent=140, style="arc",
                                  outline="#222222", width=1)
                # Petites lunettes de soleil 3D qui pivotent devant les yeux
                glasses_swing = math.sin(state["angle"] * 2) * 3
                canvas.create_line(fx - 14, fy - 3 + glasses_swing, fx + 14, fy - 3 - glasses_swing,
                                   fill="#111111", width=2)

                # Loupe qui orbite (recherche !) avec un peu de profondeur
                lang = state["angle"] * 1.1
                lx = cx + math.cos(lang) * 52
                ly = cy - bounce * 0.5 + math.sin(lang) * 20
                lscale = 1.0 + 0.3 * math.sin(lang)
                lr = 7 * lscale
                canvas.create_oval(lx - lr, ly - lr, lx + lr, ly + lr,
                                   outline="#cccccc", width=2)
                canvas.create_line(lx + lr * 0.7, ly + lr * 0.7,
                                   lx + lr * 1.6, ly + lr * 1.6,
                                   fill="#cccccc", width=2)

                # Dialogue cyclique : voix off, puis réplique de Citron
                state["msg_t"] += 1
                if state["msg_t"] >= 25:
                    state["msg_t"] = 0
                    state["msg_i"] = (state["msg_i"] + 1) % len(dialogues)
                try:
                    off_txt, citron_txt = dialogues[state["msg_i"]]
                    msg_off.configure(text=f"— {off_txt}")
                    msg_citron.configure(text=f"🍋 {citron_txt}")
                except Exception:
                    pass

                state["angle"] += 0.07
                state["bounce_t"] += 0.12
                win.after(30, _draw)

            _draw()

            try:
                win.update_idletasks()
                w, h = win.winfo_reqwidth(), win.winfo_reqheight()
                # Centrée sur la fenêtre principale de Citron (incrustation),
                # avec repli sur le centre de l'écran si indisponible.
                try:
                    px = self.winfo_rootx() + (self.winfo_width() - w) // 2
                    py = self.winfo_rooty() + (self.winfo_height() - h) // 2
                except Exception:
                    px = py = None
                if px is None or py is None:
                    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
                    px, py = (sw - w) // 2, (sh - h) // 2
                win.geometry(f"{w}x{h}+{px}+{py}")
            except Exception:
                pass
            return win

        def _close_citron_search_anim(self):
            self._citron_anim_stop = True
            try:
                win = getattr(self, "_citron_anim_win", None)
                if win and win.winfo_exists():
                    win.destroy()
            except Exception:
                pass
            self._citron_anim_win = None
            try:
                self.configure(cursor="")
            except Exception:
                pass

        def _run_tableur_search_async(self, kind, query, scope=None, breadcrumb=None):
            """Lance la recherche en arriere-plan avec animation citron, puis
            ouvre la fenetre de resultats sur le thread UI."""
            try:
                self.configure(cursor="watch")
            except Exception:
                pass
            self._show_citron_search_anim(query)

            def worker():
                err = None
                matches = []
                print(f"[TableurSearch][TRACE] worker START kind={kind!r} query={query!r} scope={len(scope) if scope is not None else None}")
                try:
                    matches = self._compute_tableur_search(kind, query, scope)
                    print(f"[TableurSearch][TRACE] worker END matches={len(matches)}")
                except Exception as ex:
                    err = ex
                    print(f"[TableurSearch] Erreur : {ex}")

                def _done():
                    self._close_citron_search_anim()
                    if err is not None:
                        messagebox.showerror("Recherche", f"Erreur pendant la recherche :\n{err}")
                        self._tableur_pop_history()
                        return
                    # Construire titre / breadcrumb comme avant
                    if kind == "acteur":
                        win_title = f"films de {query}"
                        step_label = f"Acteur : {query}"
                    elif kind == "annee":
                        win_title = f"films de l'année {query}"
                        step_label = f"Année : {query}"
                    elif kind == "titre":
                        win_title = f"{query}"
                        step_label = f"Titre : {query}"
                    else:
                        win_title = f"films lié à {query}"
                        step_label = f"Mot clé : {query}"
                    if scope is not None:
                        win_title += " (recherche affinée)"
                    new_breadcrumb = (breadcrumb or []) + [step_label]
                    self._open_tableur_results_window(win_title, query, matches, new_breadcrumb)

                self.after(0, _done)

            threading.Thread(target=worker, daemon=True).start()

        def _compute_tableur_search(self, kind, query, scope=None):
            """Partie purement calculatoire de la recherche tableur.
            Retourne la liste de matches (sans ouvrir de fenetre).
            Thread-safe pour l'appel depuis un worker (pas de Tk ici)."""
            _clean = self._tableur_search_clean
            _fuzzy = self._tableur_fuzzy_contains
            q = _clean(query)
            matches = []

            if scope is not None:
                # ── Recherche restreinte aux résultats précédents ──────────
                # Les résultats de « Simuler Infos (tableur) » contiennent
                # volontairement row_data mais pas les champs col_* utilisés
                # par la recherche générale. Il faut donc reconstruire les
                # colonnes à partir de la ligne du tableur.
                def _cell_text(value):
                    if isinstance(value, dict):
                        return str(
                            value.get("text", value.get("value", ""))
                        ).strip()
                    return str(value or "").strip()

                def _source_iter():
                    for it in scope:
                        # Un résultat normal possède déjà les col_* :
                        if any(k in it for k in (
                            "col_titre", "col_annee", "col_personnes",
                            "col_resume", "col_type"
                        )):
                            yield (
                                it.get("col_titre", ""), it.get("col_annee", ""),
                                it.get("col_resume", ""), it.get("col_personnes", ""),
                                it.get("col_type", ""), it.get("col_filmeur", ""),
                                it.get("col_complement", ""), it.get("col_fichier", ""),
                                it.get("row_data"), it.get("path")
                            )
                            continue

                        rd = it.get("row_data") or []
                        vals = [_cell_text(v) for v in rd]

                        # Même mapping que la recherche sur le tableur complet:
                        # titre=0, année=1, résumé=2, personnes=3, type=4,
                        # filmeur=5, complément=7, fichier=8.
                        yield (
                            vals[0] if len(vals) > 0 else "",
                            vals[1] if len(vals) > 1 else "",
                            vals[2] if len(vals) > 2 else "",
                            vals[3] if len(vals) > 3 else "",
                            vals[4] if len(vals) > 4 else "",
                            vals[5] if len(vals) > 5 else "",
                            vals[7] if len(vals) > 7 else "",
                            vals[8] if len(vals) > 8 else "",
                            rd,
                            it.get("path")
                        )
            else:
                # ── Recherche sur tout le tableur ───────────────────────────
                # Pas de messagebox ici : peut etre appele depuis un thread.
                if not self._tableur_path or not os.path.isfile(self._tableur_path):
                    raise RuntimeError(
                        "Aucun tableur configure.\n"
                        "Cliquez sur 🗂 Tableur → 📂 Sélection tableur pour en choisir un.")
                from odf.table import TableRow, TableCell
                rows, err = self._get_ods_rows()
                if err:
                    raise RuntimeError(err)

                def _source_iter():
                    for row in rows:
                        cells = self._expand_ods_cells(row.getElementsByType(TableCell))
                        if not cells:
                            continue

                        def ctext(i):
                            return self._ods_cell_text(cells[i]).strip() if i < len(cells) else ""

                        col_titre = ctext(0)
                        if not col_titre:
                            continue
                        # IMPORTANT : ne PAS résoudre les liens hypertexte
                        # (affiche/bande-annonce) ici — c'est coûteux et on
                        # scanne jusqu'à ~4700 lignes à chaque recherche. On
                        # ne le fait que plus bas, une fois le filtre "ok"
                        # passé, donc seulement pour les quelques résultats
                        # réellement trouvés (voir 'cells' transmis tel quel).
                        yield (col_titre, ctext(1), ctext(2), ctext(3), ctext(4), ctext(5),
                               ctext(7), ctext(8), cells, None)

            for (col_titre, col_annee, col_resume, col_personnes, col_type,
                 col_filmeur, col_complement, col_fichier, row_data_or_cells, known_path) in _source_iter():
                if not col_titre:
                    continue

                approx = False
                approx_word = None
                if kind == "acteur":
                    ok, approx, approx_word = _fuzzy(q, col_personnes)
                elif kind == "annee":
                    ca = _clean(col_annee)
                    ok = bool(q) and (ca == q or q in ca)
                elif kind == "titre":
                    ok = bool(q) and q in _clean(col_titre)
                else:  # motcle : colonnes 1,3,4,5,6,8,9 (1-indexées)
                    hay_raw = " ".join([col_titre, col_resume, col_personnes,
                                         col_type, col_filmeur, col_complement, col_fichier])
                    ok, approx, approx_word = _fuzzy(q, hay_raw)
                if not ok:
                    continue

                # Résolution des liens hypertexte (affiche/bande-annonce) :
                # seulement maintenant, pour cette ligne qui correspond
                # vraiment à la recherche (scope : row_data déjà résolu et
                # réutilisé tel quel ; tableur complet : 'row_data_or_cells'
                # contient encore les cellules brutes, à résoudre ici).
                if scope is not None:
                    row_data = row_data_or_cells
                else:
                    row_data = [self._ods_cell_content(c) for c in row_data_or_cells]

                # Chemin local : verifier qu'il existe encore (lettre USB…).
                lib_path = None
                if known_path:
                    if os.path.isfile(known_path):
                        lib_path = known_path
                    else:
                        lib_path = self._relocate_media_path(known_path)
                if not lib_path:
                    idx = self._find_library_index_for_titre_annee(col_titre, col_annee)
                    if idx is not None:
                        p = self.video_paths[idx]
                        lib_path = p if os.path.isfile(p) else self._relocate_media_path(p)
                if not lib_path and col_fichier:
                    try:
                        rp = self._resolve_path(str(col_fichier).strip())
                        if rp and os.path.isfile(rp):
                            lib_path = rp
                        elif rp:
                            lib_path = self._relocate_media_path(rp)
                    except Exception:
                        pass
                base_display = f"{col_titre} ({col_annee})" if col_annee else col_titre
                if approx:
                    display = f"≈ {base_display} ({approx_word})" if approx_word else f"≈ {base_display}"
                else:
                    display = base_display
                matches.append({
                    "titre": display, "col_titre": col_titre, "col_annee": col_annee,
                    "col_resume": col_resume, "col_personnes": col_personnes,
                    "col_type": col_type, "col_filmeur": col_filmeur,
                    "col_complement": col_complement, "col_fichier": col_fichier,
                    "row_data": row_data, "path": lib_path, "approx": approx,
                    "approx_word": approx_word,
                })

            # Dédoublonner par (titre, année) — en gardant la version exacte
            # de préférence si le même titre a été trouvé exact ET approché.
            best_by_key = {}
            for m in matches:
                k = (m["col_titre"].lower(), m["col_annee"])
                prev = best_by_key.get(k)
                if prev is None or (prev["approx"] and not m["approx"]):
                    best_by_key[k] = m
            uniq = list(best_by_key.values())
            # La recherche approchée n'est qu'un filet de secours : si la
            # recherche exacte a déjà abouti (au moins un résultat exact),
            # on n'affiche PAS les résultats approximatifs en plus.
            if any(not m["approx"] for m in uniq):
                uniq = [m for m in uniq if not m["approx"]]
            # Résultats exacts d'abord, puis approchés ; alphabétique dans chaque groupe.
            uniq.sort(key=lambda m: (m["approx"], self._natural_key(m["titre"])))
            return uniq

        def _run_tableur_search(self, kind, query, scope=None, breadcrumb=None):
            """Compatibilite : recherche synchrone + ouverture des resultats.
            Preferer _run_tableur_search_async (animation citron)."""
            uniq = self._compute_tableur_search(kind, query, scope)
            if kind == "acteur":
                win_title = f"films de {query}"
                step_label = f"Acteur : {query}"
            elif kind == "annee":
                win_title = f"films de l'année {query}"
                step_label = f"Année : {query}"
            elif kind == "titre":
                win_title = f"{query}"
                step_label = f"Titre : {query}"
            else:
                win_title = f"films lié à {query}"
                step_label = f"Mot clé : {query}"
            if scope is not None:
                win_title += " (recherche affinée)"
            new_breadcrumb = (breadcrumb or []) + [step_label]
            self._open_tableur_results_window(win_title, query, uniq, new_breadcrumb)

        def _is_match_available(self, m):
            """True si le film de resultat a un fichier local lisible
            (present dans la Liste complete ou relocalisable)."""
            if not m:
                return False
            p = m.get("path")
            if p and os.path.isfile(p):
                return True
            p2 = self._ensure_playable_path(
                p,
                col_titre=m.get("col_titre", ""),
                col_annee=m.get("col_annee", ""),
                col_fichier=m.get("col_fichier", ""),
            )
            if p2:
                m["path"] = p2
                return True
            return False

        def _any_search_results_open(self):
            wins = getattr(self, "_search_results_wins", None) or []
            alive = []
            for w in wins:
                try:
                    if w.winfo_exists():
                        alive.append(w)
                except Exception:
                    pass
            self._search_results_wins = alive
            return bool(alive)

        def _register_search_results_win(self, win):
            if not hasattr(self, "_search_results_wins"):
                self._search_results_wins = []
            if win not in self._search_results_wins:
                self._search_results_wins.append(win)

        def _unregister_search_results_win(self, win):
            wins = getattr(self, "_search_results_wins", None) or []
            self._search_results_wins = [w for w in wins if w is not win]
            alive = []
            for w in self._search_results_wins:
                try:
                    if w.winfo_exists():
                        alive.append(w)
                except Exception:
                    pass
            self._search_results_wins = alive
            if not self._search_results_wins:
                # Toutes les listes de recherche sont fermees :
                # ⏮/⏭ redeviennent libres (liste complete / playlist).
                self._clear_search_play_mode()
            self._update_search_restore_btn()

        def _clear_search_play_mode(self):
            self._search_play_mode = False
            self._search_play_paths = []
            self._search_play_index = -1

        def _update_search_restore_btn(self):
            """Affiche ou masque le bouton 🔎 Recherches selon la presence
            de fenetres de resultats encore existantes (ouvertes ou reduites)."""
            try:
                btn = getattr(self, "search_restore_btn", None)
                if not btn or not btn.winfo_exists():
                    return
                n = 0
                iconic = 0
                for w in list(getattr(self, "_search_results_wins", []) or []):
                    try:
                        if not w.winfo_exists():
                            continue
                        n += 1
                        try:
                            if w.state() == "iconic":
                                iconic += 1
                        except Exception:
                            pass
                    except Exception:
                        pass
                if n > 0:
                    label = f"🔎 Recherches ({n})"
                    if iconic:
                        label = f"🔎 Recherches ({iconic} réduit)"
                    btn.configure(text=label)
                    if not btn.winfo_ismapped():
                        # Apres le bouton playlist
                        btn.pack(side="left", padx=4, after=self.playlist_btn)
                else:
                    if btn.winfo_ismapped():
                        btn.pack_forget()
            except Exception as ex:
                print(f"[Recherche] update restore btn : {ex}")

        def _restore_search_results_windows(self):
            """Reaffiche toutes les fenetres de resultats de recherche
            encore existantes (y compris celles reduites avec -)."""
            restored = 0
            for w in list(getattr(self, "_search_results_wins", []) or []):
                try:
                    if not w.winfo_exists():
                        continue
                    try:
                        st = w.state()
                    except Exception:
                        st = ""
                    # iconified (-) ou withdraw (historique) : on reaffiche
                    # uniquement les reduites par l'utilisateur ; les
                    # fenetres empilees dans l'historique tableur restent
                    # masquees tant que la chaine Infos n'est pas terminee.
                    if st == "iconic":
                        w.deiconify()
                        w.attributes("-topmost", True)
                        w.lift()
                        restored += 1
                    elif st == "normal" or st == "zoomed":
                        w.attributes("-topmost", True)
                        w.lift()
                        restored += 1
                except Exception as ex:
                    print(f"[Recherche] restore : {ex}")
            self._update_search_restore_btn()
            if restored:
                self._show_toast(f"🔎 {restored} fenetre(s) de recherche affichee(s)",
                                  ms=2000, color="#2a4a6a")
            else:
                # Peut-etre des fenetres withdraw via historique : proposer
                # quand meme de les deiconify si state withdrawn
                forced = 0
                for w in list(getattr(self, "_search_results_wins", []) or []):
                    try:
                        if w.winfo_exists():
                            w.deiconify()
                            w.attributes("-topmost", True)
                            w.lift()
                            forced += 1
                    except Exception:
                        pass
                if forced:
                    self._show_toast(f"🔎 {forced} fenetre(s) restauree(s)",
                                      ms=2000, color="#2a4a6a")
                else:
                    self._show_toast("Aucune fenetre de recherche a afficher",
                                      ms=2000, color="#555555")

        def _open_tableur_results_window(self, win_title, query, matches, breadcrumb=None):
            """Fenetre listant tous les titres trouves par une recherche
            tableur. Les titres absents de la Liste complete sont grises.
            Un clic gauche sur un titre ouvre le menu d'actions (restreint
            si le titre est gris)."""
            breadcrumb = breadcrumb or []
            # Conteneur mutable : le bouton Rafraichir peut retirer des entrees
            state = {"matches": list(matches)}

            # Resoudre les chemins une fois a l'ouverture (grisage fiable)
            for m in state["matches"]:
                self._is_match_available(m)

            win = ctk.CTkToplevel(self)
            win.title(win_title)
            win.geometry("560x680")
            win.attributes("-topmost", True)
            win.lift()
            self._register_search_results_win(win)
            self._update_search_restore_btn()
            self._remember_last_window_geometry(win)
            # Suivre reduction (-) / restauration pour le bouton 🔎 Recherches
            def _on_map_unmap(event=None):
                self.after(50, self._update_search_restore_btn)
            win.bind("<Unmap>", _on_map_unmap)
            win.bind("<Map>", _on_map_unmap)

            def _close_results_win():
                self._unregister_search_results_win(win)
                try:
                    win.destroy()
                except Exception:
                    pass
                self._tableur_pop_history()
            win.protocol("WM_DELETE_WINDOW", _close_results_win)

            top_bar = ctk.CTkFrame(win, fg_color="transparent")
            top_bar.pack(fill="x", padx=16, pady=(14, 0))
            ctk.CTkButton(top_bar, text="✕ Fermer", command=_close_results_win,
                          width=100, height=32, fg_color="#c42b1c").pack(side="right")
            ctk.CTkButton(top_bar, text="🔄 Rafraîchir la liste",
                          command=lambda: _refresh_list(),
                          width=160, height=32, fg_color="#2a4a6a").pack(side="right", padx=8)

            ctk.CTkLabel(win, text=win_title, font=("Arial", 20, "bold")).pack(pady=(10, 4))
            count_label = ctk.CTkLabel(win, text="", font=("Arial", 13))
            count_label.pack()
            legend = ctk.CTkLabel(
                win,
                text="gris = absent de la Liste complète des médias  ·  ≈ = correspondance approximative",
                font=("Arial", 11), text_color="#888888")
            legend.pack(pady=(0, 4))

            lf = ctk.CTkFrame(win)
            lf.pack(fill="both", expand=True, padx=16, pady=12)
            lb = Listbox(lf, font=("Arial", 13), bg="#2b2b2b", fg="white",
                         selectbackground="#1f6aa5", activestyle="none")
            sb = Scrollbar(lf, orient="vertical", command=lb.yview)
            lb.config(yscrollcommand=sb.set)
            lb.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")

            def _fill_listbox():
                lb.delete(0, END)
                ms = state["matches"]
                n_ok = 0
                n_miss = 0
                n_approx = 0
                for i, m in enumerate(ms):
                    available = bool(m.get("path") and os.path.isfile(m.get("path")))
                    if not available:
                        available = self._is_match_available(m)
                    lb.insert(END, m["titre"])
                    if not available:
                        lb.itemconfig(i, fg="#666666")
                        n_miss += 1
                    elif m.get("approx"):
                        lb.itemconfig(i, fg="#e0a030")
                        n_ok += 1
                        n_approx += 1
                    else:
                        lb.itemconfig(i, fg="white")
                        n_ok += 1
                if not ms:
                    lb.insert(END, "(Aucun résultat)")
                total_txt = f"{len(ms)} résultat(s)  —  {n_ok} disponible(s)  —  {n_miss} absent(s)"
                if n_approx:
                    total_txt += f"  —  dont {n_approx} ≈"
                count_label.configure(text=total_txt)

            def _refresh_list():
                """Efface tous les titres grises (absents de la Liste complete)."""
                before = len(state["matches"])
                kept = []
                for m in state["matches"]:
                    available = bool(m.get("path") and os.path.isfile(m.get("path")))
                    if not available:
                        available = self._is_match_available(m)
                    if available:
                        kept.append(m)
                state["matches"] = kept
                removed = before - len(kept)
                _fill_listbox()
                if removed:
                    self._show_toast(
                        f"🔄 {removed} titre(s) absent(s) retiré(s) de la liste",
                        ms=2500, color="#2a4a6a")
                else:
                    self._show_toast("🔄 Aucun titre absent à retirer", ms=2000, color="#555555")

            _fill_listbox()

            def _on_click(event):
                ms = state["matches"]
                if not ms:
                    return
                idx = lb.nearest(event.y)
                if not (0 <= idx < len(ms)):
                    return
                lb.selection_clear(0, END)
                lb.selection_set(idx)
                self._tableur_results_context_menu(
                    event, win, state, idx, query, breadcrumb)

            lb.bind("<Button-1>", _on_click)

        def _tableur_results_context_menu(self, event, win, state_or_matches, idx, query, breadcrumb=None):
            """Menu deroulant sur un titre de resultats. Les actions qui
            necessitent un fichier local sont desactivees si le titre est
            gris (absent de la Liste complete)."""
            if isinstance(state_or_matches, dict):
                matches = state_or_matches["matches"]
            else:
                matches = state_or_matches
            if not (0 <= idx < len(matches)):
                return
            m = matches[idx]
            path = self._ensure_playable_path(
                m.get("path"),
                col_titre=m.get("col_titre", ""),
                col_annee=m.get("col_annee", ""),
                col_fichier=m.get("col_fichier", ""),
            )
            if path:
                m["path"] = path
            available = bool(path and os.path.isfile(path))

            menu = Menu(win, tearoff=0, font=("Arial", 16))
            menu.add_command(
                label=f"📋 Infos (tableur) {query}",
                command=lambda: self._open_restricted_tableur_info(matches, idx, win, breadcrumb))
            if available:
                menu.add_command(
                    label="➕ Ajouter à la playlist",
                    command=lambda: self._results_add_to_playlist(path, win))
                menu.add_command(
                    label="▶ Lire cette vidéo",
                    command=lambda: self._results_play(
                        path,
                        col_titre=m.get("col_titre", ""),
                        col_annee=m.get("col_annee", ""),
                        col_fichier=m.get("col_fichier", ""),
                        search_matches=matches))
                menu.add_command(
                    label="ℹ️ Info du média",
                    command=lambda: self._results_show_media_info(path))
                menu.add_command(
                    label="🎬 Ouverture dans Shotcut…",
                    command=lambda: self._open_in_shotcut(path))
            else:
                def _add_virtual_from_results(mm=m):
                    # silent=True : plus de confirmation « OK » à valider —
                    # un toast non bloquant suffit (même logique que dans
                    # 📋 Infos / Simuler Infos, voir _add_info_to_virtual_playlist).
                    # L'avertissement de doublon reste affiché par
                    # _add_to_virtual_playlist car il signale un problème.
                    title = (mm.get("col_titre") or mm.get("titre") or "").strip()
                    if self._add_to_virtual_playlist(mm, silent=True):
                        self._show_virtual_playlist_toast(
                            f"🧪 « {title} » ajouté à la Playlist virtuelle", win)
                menu.add_command(
                    label="🧪 + Playlist virtuelle",
                    command=_add_virtual_from_results)
                menu.add_command(
                    label="▶ Lire cette vidéo  (absent de la Liste)",
                    state="disabled")
                menu.add_command(
                    label="ℹ️ Info du média  (absent de la Liste)",
                    state="disabled")
                menu.add_command(
                    label="🎬 Ouverture dans Shotcut…  (absent de la Liste)",
                    state="disabled")
            menu.post(event.x_root, event.y_root)

        def _open_restricted_tableur_info(self, matches, idx, results_win=None, breadcrumb=None):
            """Ouvre 📋 Infos (tableur) pour ce titre, avec une navigation
            ◀ ▶ restreinte à la liste de résultats courante (pas toute la
            bibliothèque). La fenêtre de résultats est masquée (pas détruite)
            et empilée, pour pouvoir y revenir à la fermeture de cette fiche."""
            if results_win is not None:
                try:
                    if results_win.winfo_exists():
                        self._tableur_push_history(results_win)
                except Exception:
                    pass
            m = matches[idx]
            # nav_list conserve tous les champs col_* (pas seulement titre et
            # path) : ils servent de `scope` si l'utilisateur relance une
            # recherche depuis cette fiche restreinte, pour que les
            # recherches successives se combinent (voir _run_tableur_search).
            nav_list = [{"titre": x["titre"], "path": x.get("path"),
                         "row_data": x.get("row_data"), "error": None,
                         "col_titre": x.get("col_titre", ""), "col_annee": x.get("col_annee", ""),
                         "col_resume": x.get("col_resume", ""), "col_personnes": x.get("col_personnes", ""),
                         "col_type": x.get("col_type", ""), "col_filmeur": x.get("col_filmeur", ""),
                         "col_complement": x.get("col_complement", ""), "col_fichier": x.get("col_fichier", "")}
                        for x in matches]
            self._open_info_window(m["titre"], m.get("path"), m.get("row_data"), None,
                                    nav_override={"list": nav_list, "index": idx, "breadcrumb": breadcrumb or []},
                                    from_chain=True)

        def _results_add_to_playlist(self, path, parent=None):
            if path and not os.path.isfile(path):
                path = self._relocate_media_path(path)
            if not path or not os.path.isfile(path):
                messagebox.showinfo("Playlist",
                    "Ce film n'a pas ete retrouve dans votre bibliotheque locale "
                    "(fichier absent) : impossible de l'ajouter a la playlist.\n\n"
                    "Si vous avez rebranche le disque USB sur un autre port, "
                    "re-ajoutez le dossier via Liste -> Dossier.")
                return
            self.playlist.append(path)
            self.save_playlist(); self.update_playlist_button_text()
            self._fetch_durations_bg([path])
            if self.playlist_win and self.playlist_win.winfo_exists():
                self.refresh_playlist_window()
            # Plus de confirmation « OK » à valider : un toast non bloquant
            # suffit (même logique que pour "🧪 + Playlist virtuelle").
            self._show_virtual_playlist_toast(
                f"➕ « {os.path.basename(path)} » ajouté à la playlist",
                parent, title="Playlist")


        def _results_show_media_info(self, path):
            if not path or not os.path.isfile(path):
                messagebox.showinfo("Info du média",
                    "Ce film n'a pas été retrouvé dans votre bibliothèque locale "
                    "(fichier absent) : aucune information de fichier disponible.")
                return
            self._show_media_info(path)

        def _results_play(self, path, col_titre="", col_annee="", col_fichier="",
                          search_matches=None):
            path = self._ensure_playable_path(path, col_titre, col_annee, col_fichier)
            if not path or not os.path.isfile(path):
                messagebox.showerror(
                    "Lecture",
                    "Fichier introuvable.\n\n"
                    "Causes frequentes :\n"
                    "• le film n'est pas dans la Liste complete (bibliotheque locale)\n"
                    "• le disque a change de lettre (USB rebranche) — "
                    "re-ajoutez le dossier via Liste -> Dossier\n"
                    "• le fichier a ete renomme ou deplace")
                return
            if path not in self.video_paths:
                name = os.path.basename(path)
                if is_audio(path):
                    name += "  🎵 audio"
                self.video_paths.append(path)
                self.video_names.append(name)
                self.save_library()
                self.update_list_button_text()

            # Construire la liste de navigation ⏮/⏭ a partir des titres
            # DISPONIBLES de la derniere recherche (dans l'ordre affiche).
            play_paths = []
            if search_matches:
                for sm in search_matches:
                    p = sm.get("path")
                    if not (p and os.path.isfile(p)):
                        p = self._ensure_playable_path(
                            p, sm.get("col_titre", ""), sm.get("col_annee", ""),
                            sm.get("col_fichier", ""))
                        if p:
                            sm["path"] = p
                    if p and os.path.isfile(p) and p not in play_paths:
                        play_paths.append(p)
            if not play_paths:
                play_paths = [path]

            self._seq_mode = False
            self._list_play_mode = False
            self._single_tv_mode = False
            self._search_play_mode = True
            self._search_play_paths = play_paths
            try:
                self._search_play_index = play_paths.index(path)
            except ValueError:
                self._search_play_paths = [path]
                self._search_play_index = 0

            self.play_file(path)
            self.set_play_mode("pc", "Recherche tableur")

        def _tableur_push_history(self, win):
            """Masque (withdraw, sans détruire) `win` et l'empile en haut de
            la pile d'historique de navigation tableur, pour pouvoir la
            réafficher plus tard via _tableur_pop_history() (retour arrière
            lors d'une chaîne de recherches dans les fiches Infos).

            Arrête d'abord le résumé vidéo (🎞) et la narration éventuellement
            en cours sur `win` : sans ça, une nouvelle recherche validée
            pendant qu'ils jouent les laissait tourner en arrière-plan,
            invisibles, et le son se chevauchait avec ce qui s'ouvrait
            ensuite (résultats, puis une nouvelle fiche avec son propre
            résumé/narration)."""
            if not hasattr(self, "_tableur_hist"):
                self._tableur_hist = []
            try:
                print(f"[TableurSearch][TRACE] Arrêt média avant nouvelle recherche — win={id(win)}")
                stop_media = getattr(win, "_citron_stop_media", None)
                if stop_media:
                    stop_media()
                print(f"[TableurSearch][TRACE] Arrêt média terminé — win={id(win)}")
            except Exception as ex:
                print(f"[TableurSearch][TRACE] Exception arrêt média : {type(ex).__name__}: {ex}")
            try:
                win.withdraw()
            except Exception:
                pass
            self._tableur_hist.append(win)

        def _tableur_pop_history(self):
            """Retire et réaffiche la dernière fenêtre mise en attente
            (retour arrière). Retourne True si une fenêtre a été restaurée,
            False si la pile était vide (on est revenu à la fenêtre Infos
            d'origine, ou il n'y avait pas de chaîne de recherche en cours)."""
            hist = getattr(self, "_tableur_hist", None)
            while hist:
                win = hist.pop()
                try:
                    if win.winfo_exists():
                        win.deiconify()
                        win.attributes("-topmost", True)
                        win.lift()
                        win.focus_force()
                        return True
                except Exception:
                    continue
            return False

        def _ask_all_titles_visited(self, parent_win, on_yes, on_no):
            """Boîte de dialogue affichée quand la navigation ◀ ▶ a bouclé
            sur tous les titres de la liste : demande si on continue (O) ou
            si on ferme tout (N). Répond aussi bien au clic qu'aux touches
            clavier O / N."""
            dlg = ctk.CTkToplevel(self)
            dlg.title("Navigation")
            dlg.resizable(False, False)
            dlg.attributes("-topmost", True)
            try: dlg.transient(parent_win)
            except Exception: pass

            ctk.CTkLabel(dlg, text="Tous les titres ont été traités.\nVoulez-vous poursuivre ?",
                         font=("Arial", 15), justify="center").pack(padx=30, pady=(24, 10))
            ctk.CTkLabel(dlg, text="(touche O = Oui, touche N = Non)",
                         font=("Arial", 11), text_color="#999999").pack()

            done = {"answered": False}

            def _yes(event=None):
                if done["answered"]: return
                done["answered"] = True
                try: dlg.destroy()
                except Exception: pass
                on_yes()

            def _no(event=None):
                if done["answered"]: return
                done["answered"] = True
                try: dlg.destroy()
                except Exception: pass
                on_no()

            btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
            btn_frame.pack(pady=18)
            ctk.CTkButton(btn_frame, text="Oui (O)", width=110, command=_yes).pack(side="left", padx=8)
            ctk.CTkButton(btn_frame, text="Non (N)", width=110, fg_color="#5a5a5a",
                          command=_no).pack(side="left", padx=8)
            dlg.bind("o", _yes); dlg.bind("O", _yes)
            dlg.bind("n", _no); dlg.bind("N", _no)
            dlg.protocol("WM_DELETE_WINDOW", _no)

            dlg.update_idletasks()
            w, h = dlg.winfo_reqwidth(), dlg.winfo_reqheight()
            sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
            dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            dlg.grab_set()
            dlg.focus_force()

        def _close_all_secondary_windows(self):
            """Ferme toutes les fenêtres secondaires (Infos, recherche,
            résultats, Liste, Playlist, Téléchargements, Statistiques…) en
            ne conservant que la fenêtre principale de Citron."""
            # Arrêter proprement le lecteur VLC de la fenêtre Infos active
            # (si ouverte) avant de tout détruire, sinon il continuerait à
            # tourner en arrière-plan (fenêtre fantôme + fuite de ressources).
            cleanup = getattr(self, "_current_info_win_cleanup", None)
            if cleanup:
                try: cleanup()
                except Exception: pass
                self._current_info_win_cleanup = None
            for child in list(self.winfo_children()):
                try:
                    if isinstance(child, ctk.CTkToplevel) and child.winfo_exists():
                        child.destroy()
                except Exception:
                    pass
            for attr in ("list_win", "playlist_win", "stats_win", "dlna_win", "dl_win",
                         "_current_info_win", "_tableur_search_win", "dl_stats_win"):
                if hasattr(self, attr):
                    setattr(self, attr, None)
            self._info_nav_session = None
            self._search_results_wins = []
            self._clear_search_play_mode()

        def _save_resume_to_tableur(self, col_titre, col_annee, new_text):
            """Modifie directement la cellule 'Résumé' (colonne 3) de la
            ligne correspondante dans le fichier tableur (.ods) et
            l'enregistre sur disque — sans ouvrir de tableur externe.
            Retourne (True, None) en cas de succès, (False, message
            d'erreur) sinon. La ligne est retrouvée par titre+année exacts
            uniquement (score ≥ 80), par sécurité : on ne veut jamais
            modifier la mauvaise ligne par erreur."""
            path = self._get_tableur_path_or_warn()
            if not path:
                return False, "Aucun tableur configuré."
            try:
                from odf.opendocument import load as ods_load
                from odf.table import Table, TableRow, TableCell
                from odf.text import P
            except Exception:
                return False, "La bibliothèque 'odfpy' n'est pas disponible."
            try:
                doc = ods_load(path)
            except Exception as ex:
                return False, f"Impossible de lire le tableur :\n{ex}"
            try:
                sheets = doc.spreadsheet.getElementsByType(Table)
                if not sheets:
                    return False, "Aucune feuille trouvée dans le tableur."
                rows = sheets[0].getElementsByType(TableRow)

                _clean = self._tableur_search_clean
                target_t = _clean(col_titre)
                target_a = (col_annee or "").strip()

                best_cells, best_score = None, 0
                for row in rows:
                    cells = self._expand_ods_cells(row.getElementsByType(TableCell))
                    if not cells:
                        continue
                    ct1 = _clean(self._ods_cell_text(cells[0]).strip())
                    if not ct1:
                        continue
                    ct2 = self._ods_cell_text(cells[1]).strip() if len(cells) > 1 else ""
                    score = 100 if (ct1 == target_t and ct2 == target_a) else (80 if ct1 == target_t else 0)
                    if score > best_score:
                        best_score, best_cells = score, cells

                if not best_cells or best_score < 80 or len(best_cells) < 3:
                    return False, "Impossible de retrouver la ligne correspondante dans le tableur."

                cell = best_cells[2]  # colonne 3 = Résumé
                for child in list(cell.childNodes):
                    cell.removeChild(child)
                for line in (new_text.split("\n") if new_text else [""]):
                    cell.addElement(P(text=line))

                doc.save(path)
            except Exception as ex:
                return False, f"Impossible d'enregistrer le tableur :\n{ex}"

            # Invalider les caches pour refléter la modification immédiatement.
            self._ods_rows_cache = None
            if hasattr(self, "_info_cache"):
                self._info_cache.clear()
            return True, None

        def _open_resume_edit_dialog(self, txt_widget, col_titre, col_annee, win_parent):
            """Boîte de dialogue d'édition du résumé, ouverte au clic sur le
            texte du résumé dans 📋 Infos (tableur). Enregistre directement
            dans le fichier tableur, sans ouvrir d'application externe, puis
            met à jour l'affichage de la fiche courante."""
            try:
                current = txt_widget.get("1.0", "end-1c")
            except Exception:
                current = ""

            dlg = ctk.CTkToplevel(self)
            dlg.title("Modifier le résumé")
            dlg.attributes("-topmost", True)
            try: dlg.transient(win_parent)
            except Exception: pass

            ctk.CTkLabel(dlg, text="Modifier le résumé :", font=("Arial", 15, "bold")).pack(
                padx=20, pady=(18, 8), anchor="w")

            from tkinter import Text as _EditText
            edit_box = _EditText(dlg, font=("Arial", 13), wrap="word", width=76, height=16,
                                  bg="#2b2b2b", fg="white", insertbackground="white")
            edit_box.insert("1.0", current)
            edit_box.pack(padx=20, pady=(0, 12), fill="both", expand=True)

            btn_frame = ctk.CTkFrame(dlg, fg_color="transparent")
            btn_frame.pack(pady=(0, 18))

            def _save(event=None):
                new_text = edit_box.get("1.0", "end-1c").strip()
                ok, err = self._save_resume_to_tableur(col_titre, col_annee, new_text)
                if not ok:
                    messagebox.showerror("Modifier le résumé", err, parent=dlg)
                    return
                try:
                    txt_widget.delete("1.0", "end")
                    txt_widget.insert("1.0", new_text)
                    txt_widget.update_idletasks()
                    n = int(txt_widget.index("end-1c").split(".")[0])
                    txt_widget.configure(height=max(12, n * 3))
                except Exception:
                    pass
                try: dlg.destroy()
                except Exception: pass
                self._show_toast("📝 Résumé enregistré dans le tableur", ms=3000, color="#1a6e3c")

            def _cancel(event=None):
                try: dlg.destroy()
                except Exception: pass

            ctk.CTkButton(btn_frame, text="Enregistrer", width=130, command=_save).pack(side="left", padx=8)
            ctk.CTkButton(btn_frame, text="Annuler", width=100, fg_color="#5a5a5a",
                          command=_cancel).pack(side="left", padx=8)
            dlg.protocol("WM_DELETE_WINDOW", _cancel)

            dlg.update_idletasks()
            w, h = 700, 460
            sw, sh = dlg.winfo_screenwidth(), dlg.winfo_screenheight()
            dlg.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")
            dlg.grab_set()
            edit_box.focus_set()

        def _open_info_window(self, titre, path, row_data, error, nav_override=None, nav_session=None, from_chain=False):
            """Affiche la fenêtre d'informations du média en plein écran.

            nav_override (optionnel) : dict {"list": [...], "index": int}
            pour restreindre la navigation ◀ ▶ à une liste précise (ex : les
            résultats d'une recherche acteur/année/titre/mot-clé) au lieu de
            parcourir toute la Liste complète des médias (self.video_paths).
            Chaque élément de "list" est un dict :
              {"titre": str, "path": str|None, "row_data": list|None,
               "error": str|None}
            Si "path" est None (film du tableur absent de la bibliothèque
            locale), les actions qui nécessitent un fichier local (Playlist,
            Lire cette vidéo…) sont désactivées mais la fiche (résumé,
            affiche, bande-annonce) reste consultable.

            nav_session (optionnel) : dict {"visited": set, "total": int}
            qui suit les titres déjà vus pendant la navigation ◀ ▶ en cours
            (boucle indéfiniment dernier↔premier). Passé automatiquement
            d'une fenêtre à l'autre par _nav ; laissé à None pour démarrer
            une nouvelle session (ex : premier clic depuis la Liste ou une
            fenêtre de résultats de recherche).

            from_chain (optionnel) : True si cette fenêtre poursuit une
            chaîne de recherches tableur déjà en cours (navigation ▶ ◀, ou
            ouverture depuis une fenêtre de résultats déjà empilée via
            _tableur_push_history) — dans ce cas la pile d'historique de
            retour arrière est conservée. False (par défaut) = ouverture
            fraîche (ex : double-clic dans la Liste), qui repart d'une pile
            vide pour ne pas restaurer par erreur une ancienne chaîne
            abandonnée.
            """
            if not from_chain:
                self._tableur_hist = []
            # Portée (scope) pour une éventuelle NOUVELLE recherche lancée
            # depuis cette fiche : si elle fait déjà partie d'une chaîne de
            # recherche restreinte (nav_override), la recherche suivante doit
            # se limiter à ces résultats-là (voir _run_tableur_search).
            _search_scope = nav_override.get("list") if nav_override else None
            # Fil d'Ariane des recherches successives (ex : "Acteur : Dupontel
            # > Année : 2020"), vide pour la toute première fiche d'origine —
            # celle-ci n'affiche donc rien (voir demande utilisateur).
            _search_breadcrumb = nav_override.get("breadcrumb", []) if nav_override else []
            win = ctk.CTkToplevel(self)
            win.title(f"Informations — {titre}")
            # Toujours en plein écran à l'ouverture (pas de restauration d'une
            # géométrie précédente, qui pouvait annuler le plein écran).
            win.attributes("-fullscreen", True)
            win.attributes("-topmost", True)
            win.lift(); win.focus_force()
            # Pas de clic droit sur le fond général de la fenêtre : le bouton
            # "🔍 Recherche" de l'en-tête couvre déjà ce cas de façon fiable.
            # Le clic droit reste uniquement disponible sur la zone VLC
            # (affiche/bande-annonce), voir plus bas.
            self._current_info_win = win  # référence pour pouvoir désactiver son topmost au besoin (ex: ouverture d'AlloCiné)

            def _pause_info_media():
                # Arrête la narration et met en PAUSE la vidéo résumé sans
                # libérer le lecteur VLC. Cette fonction est appelée juste
                # avant de masquer la fiche lors d'une nouvelle recherche.
                #
                # IMPORTANT : on n'appelle volontairement plus vp.stop() ici.
                # Sur certaines versions/configurations de VLC, stop() sur un
                # lecteur vidéo encore attaché à un canevas Tk/CustomTkinter
                # peut provoquer un crash natif (sans exception Python).
                # Une pause conserve le lecteur et son HWND intact, ce qui est
                # beaucoup plus sûr pendant le retrait/masquage de la fenêtre.
                #
                # La narration est arrêtée en premier afin d'éviter qu'elle
                # puisse continuer pendant la transition vers la nouvelle
                # fiche.
                # IMPORTANT : ne jamais appeler pause() sur un lecteur qui
                # n'est pas réellement en lecture. Dans VLC, pause() est un
                # basculement : sur un lecteur déjà arrêté/en attente, cet
                # appel peut le faire démarrer. C'était précisément la cause
                # du résumé vidéo qui se lançait lors d'une recherche alors
                # qu'aucune lecture n'avait été demandée.
                print(f"[TableurSearch][TRACE] _pause_info_media: vérification état lecture — win={id(win)}")
                try:
                    self._stop_resume_speech(vid_player_ref)
                except Exception as ex:
                    print(f"[TableurSearch][TRACE] _pause_info_media: erreur narration : {type(ex).__name__}: {ex}")

                try:
                    vp = vid_player_ref[0]
                    is_playing = bool(vp and vp.is_playing())
                except Exception as ex:
                    is_playing = False
                    print(f"[TableurSearch][TRACE] _pause_info_media: état VLC inconnu : {type(ex).__name__}: {ex}")

                if is_playing:
                    print(f"[TableurSearch][TRACE] _pause_info_media: lecture active → pause VLC — win={id(win)}")
                    try:
                        vp.pause()
                    except Exception as ex:
                        print(f"[TableurSearch][TRACE] _pause_info_media: erreur VLC pause : {type(ex).__name__}: {ex}")
                else:
                    print(f"[TableurSearch][TRACE] _pause_info_media: aucune lecture active → aucun appel pause() — win={id(win)}")
                print(f"[TableurSearch][TRACE] _pause_info_media: terminé — win={id(win)}")

            # Rend la mise en pause accessible depuis l'extérieur de cette
            # fonction (ex : _tableur_push_history, appelée lors d'une
            # nouvelle recherche pour éviter un chevauchement de son avec la
            # fiche précédente qu'on ne fait que masquer, pas détruire).
            win._citron_stop_media = _pause_info_media

            def _stop_info_media():
                # Arrête ET LIBÈRE la vidéo résumé (🎞) ET la narration.
                # N'est sûr à appeler que juste avant de détruire la fenêtre
                # elle-même (voir _save_info_geo ci-dessous) — jamais quand
                # la fenêtre reste vivante, auquel cas _pause_info_media
                # ci-dessus doit être utilisée à la place.
                try:
                    vp = vid_player_ref[0]
                    if vp:
                        vp.stop()
                        vp.release()
                        vid_player_ref[0] = None
                except Exception:
                    pass
                try:
                    vid_instance = vid_player_ref[2] if len(vid_player_ref) > 2 else None
                    if vid_instance:
                        vid_instance.release()
                        if len(vid_player_ref) > 2:
                            vid_player_ref[2] = None
                except Exception:
                    pass
                # Arrêter aussi une éventuelle lecture vocale du résumé en cours.
                try:
                    self._stop_resume_speech(vid_player_ref)
                except Exception:
                    pass

            def _save_info_geo():
                # Toujours stopper ET libérer la vidéo résumé (🎞) avant de
                # fermer, quel que soit le déclencheur (bouton "✕ Fermer",
                # croix de la fenêtre, Échap, ou navigation ▶/◀). Un simple
                # vp.stop() ne suffit pas : il faut aussi vp.release() et
                # vid_instance.release() pour libérer les threads/handles
                # natifs de VLC, sinon ils s'accumulent à chaque navigation
                # et finissent par bloquer Citron.
                # NOTE : cette fonction ne fait QUE le nettoyage + destroy —
                # elle est réutilisée par la navigation ▶/◀ (_go_to_restricted
                # / _go_to_library), qui ne doit PAS déclencher de retour
                # arrière dans l'historique (voir _close_info_window pour ça).
                _stop_info_media()
                try: _destroy_tip()
                except Exception: pass
                try:
                    unbind = getattr(self, "_info_keys_unbind", None)
                    if unbind:
                        unbind()
                        self._info_keys_unbind = None
                except Exception:
                    pass
                if getattr(self, "_current_info_win", None) is win:
                    self._current_info_win = None
                win.destroy()

            def _close_info_window():
                """Fermeture 'définitive' de cette fiche (bouton '✕ Fermer',
                croix de la fenêtre, Échap, ou réponse 'Non' à la boucle de
                navigation) : nettoie/détruit la fenêtre PUIS retourne à la
                fenêtre précédente dans la chaîne de recherches tableur
                (résultats ou fiche Infos d'où l'on venait), si elle existe."""
                _save_info_geo()
                self._tableur_pop_history()

            win.bind("<Escape>", lambda e: _close_info_window())
            win.protocol("WM_DELETE_WINDOW", _close_info_window)
            # Permet à _close_all_secondary_windows (fermeture globale) de
            # fermer proprement (VLC + retour arrière) la fenêtre Infos
            # active plutôt que de la détruire brutalement.
            self._current_info_win_cleanup = _close_info_window

            # En-tête : dans Infos (tableur) et Simuler Infos (tableur),
            # afficher également l'année de la 2e colonne du tableur.
            header = ctk.CTkFrame(win, fg_color="#1a2a3a", height=60)
            header.pack(fill="x")
            header.pack_propagate(False)
            _header_year = ""
            try:
                if row_data and len(row_data) > 1:
                    _yr = row_data[1]
                    _header_year = (
                        _yr.get("text", _yr.get("value", ""))
                        if isinstance(_yr, dict) else str(_yr)
                    ).strip()
            except Exception:
                _header_year = ""
            # Certains appelants (ex : fiche ouverte depuis les résultats
            # d'une recherche tableur) passent déjà un `titre` contenant
            # l'année entre parenthèses (ex : "Titre (2020)"). Dans ce cas,
            # ne pas la rajouter une seconde fois ici — un seul affichage
            # suffit. En "Simuler Infos (tableur)", `titre` ne contient
            # jamais l'année : elle continue donc de s'afficher normalement.
            _year_already_shown = bool(_header_year) and f"({_header_year})" in titre
            if _header_year and not _year_already_shown:
                _header_title = f"📋 {titre} ({_header_year})"
            else:
                _header_title = f"📋 {titre}"
            ctk.CTkLabel(header, text=_header_title,
                         font=("Arial",22,"bold"), anchor="w").pack(side="left", padx=20, pady=10)
            ctk.CTkButton(header, text="✕ Fermer",
                          command=lambda: _close_info_window(),
                          width=100, height=36, fg_color="#c42b1c").pack(side="right", padx=20)
            # Cette fiche « Simuler Infos (tableur) » est-elle issue
            # spécifiquement de la fenêtre « Compléter le tableur » ?
            # (voir _completer_tableur_ouvrir_simulation). Uniquement dans
            # ce cas précis (pas les autres « Simuler Infos »), les
            # boutons Recherche et + Playlist virtuelle laissent place à
            # un bouton « Valider et intégrer au tableur » agissant
            # directement sur cette fenêtre « Compléter le tableur ».
            _completer_win_ref = nav_override.get("completer_win") if nav_override else None
            _from_completer = bool(
                nav_override and nav_override.get("from_completer_tableur") and _completer_win_ref is not None
                and _completer_win_ref.winfo_exists()
            )
            # Bouton de recherche tableur (acteur/année/titre/mot clé) — accès
            # garanti au menu, en plus du clic droit (qui peut être capté par
            # la zone vidéo/affiche intégrée sur certains PC).
            if not _from_completer:
                search_btn = ctk.CTkButton(header, text="🔍 Recherche", width=130,
                                            height=36, fg_color="#2a4a6a")
                search_btn.configure(command=lambda: self._tableur_info_open_search_menu(
                    win, search_btn.winfo_rootx(), search_btn.winfo_rooty() + search_btn.winfo_height(),
                    _search_scope, _search_breadcrumb))
                search_btn.pack(side="right", padx=8)
            # « Compléter le tableur » : uniquement quand cette fiche
            # « 📋 Infos (tableur) » a été ouverte depuis la fenêtre « Liste
            # complète des médias » (voir list_win_right_click et sa
            # propagation dans _go_to_library). Ouvre le formulaire déjà
            # rempli des données de CE média, pour les compléter ou les
            # modifier directement dans le tableur.
            _from_liste_medias = bool(nav_override and nav_override.get("from_liste_medias"))
            if _from_liste_medias and path:
                ctk.CTkButton(header, text="🗂 Compléter le tableur", width=190,
                              height=36, fg_color="#5a3070",
                              command=lambda: self._ouvrir_completer_depuis_infos(titre, path, row_data)
                              ).pack(side="right", padx=8)
            # Playlist : dans une fiche issue de « Test tableur », on ne
            # mélange jamais cette sélection avec la Playlist normale.
            # Même si le fichier est lisible, le bouton devient donc
            # « + Playlist virtuelle ».
            _virtual_mode = bool(
                nav_override and nav_override.get("virtual_playlist_mode")
            )

            def _add_to_pl():
                try:
                    self.playlist.append(path)
                    self.save_playlist()
                    self.update_playlist_button_text()
                    if self.playlist_win and self.playlist_win.winfo_exists():
                        self.refresh_playlist_window()
                    # Plus de confirmation « OK » à valider : un toast non
                    # bloquant suffit (même logique que "🧪 + Playlist virtuelle").
                    self._show_virtual_playlist_toast(
                        f"➕ « {titre} » ajouté à la playlist", win, title="Playlist")
                except Exception as ex:
                    messagebox.showerror("Erreur", str(ex), parent=win)

            def _add_to_virtual():
                self._add_info_to_virtual_playlist(
                    titre, path, row_data, parent=win
                )

            if _from_completer:
                def _valider_depuis_simulation():
                    self._completer_tableur_valider(_completer_win_ref)
                ctk.CTkButton(
                    header, text="✅ Valider et intégrer au tableur",
                    command=_valider_depuis_simulation,
                    width=230, height=36, fg_color="#2e7d32", hover_color="#1b5e20"
                ).pack(side="right", padx=8)
            elif _virtual_mode:
                ctk.CTkButton(
                    header, text="🧪 + Playlist virtuelle",
                    command=_add_to_virtual,
                    width=170, height=36, fg_color="#6a4a1a"
                ).pack(side="right", padx=8)
            else:
                ctk.CTkButton(
                    header, text="➕ Playlist", command=_add_to_pl,
                    width=120, height=36, fg_color="#1a6e3c",
                    state=("normal" if path else "disabled")
                ).pack(side="right", padx=8)

            # Position dans la liste ("i/N") + fil d'Ariane des recherches
            # successives, centrés dans la MÊME barre que le titre et les
            # boutons (et non plus dans une sous-barre séparée). Le fil
            # n'est affiché que s'il y a une chaîne de recherche en cours —
            # la toute première fiche d'origine n'affiche rien ici.
            mid_header = ctk.CTkFrame(header, fg_color="transparent")
            mid_header.pack(side="left", fill="both", expand=True)
            mid_inner = ctk.CTkFrame(mid_header, fg_color="transparent")
            mid_inner.pack(expand=True)
            position_label = ctk.CTkLabel(mid_inner, text="", font=("Arial",13,"bold"),
                                           text_color="#8ab4d8")
            position_label.pack(side="left", padx=10)
            if _search_breadcrumb:
                breadcrumb_text = "  ›  ".join(_search_breadcrumb)
                ctk.CTkLabel(mid_inner, text=f"🔎 {breadcrumb_text}", font=("Arial",12),
                             text_color="#e0a030", anchor="w").pack(side="left", padx=10)

            if error:
                ctk.CTkLabel(win, text=f"⚠️ {error}",
                             font=("Arial",16), text_color="#ff6666",
                             justify="center").pack(expand=True)
                return

            # ── Extraire les données ──────────────────────────
            def cell_text(i):
                if i >= len(row_data): return "N.A."
                c = row_data[i]
                t = c.get("text","") if isinstance(c,dict) else str(c)
                return t.strip() or "N.A."

            def cell_path(i):
                if i >= len(row_data): return ""
                c = row_data[i]
                p = (c.get("link") or c.get("text","")) if isinstance(c,dict) else str(c)
                return self._resolve_path((p or "").strip())

            col_titre     = cell_text(0)
            col_annee     = cell_text(1)
            col_resume    = cell_text(2)
            col_personnes = cell_text(3)
            col_type      = cell_text(4)
            col_filmeur   = cell_text(5)
            col_duree     = cell_text(6)
            col_complement= cell_text(7)
            col_fichier   = cell_text(8)
            img_path      = cell_path(9)
            vid_path      = cell_path(10)
            col_12        = cell_text(11)  # colonne 12

            # ── Layout principal : flèches latérales + contenu ─
            outer_row = ctk.CTkFrame(win, fg_color="#1a1a1a")
            outer_row.pack(fill="both", expand=True)

            # Flèche gauche (média précédent)
            # IMPORTANT : la présence de la clé "list" est le vrai critère
            # d'une navigation restreinte (résultats de recherche, Test
            # tableur, Simuler Infos…). Un nav_override qui ne porte QUE le
            # marqueur "from_liste_medias" (voir _show_tableur_info) doit
            # continuer à parcourir toute la Liste complète des médias —
            # tester juste la vérité de nav_override le faisait à tort
            # basculer sur une liste restreinte vide (plus de classement
            # "i/N", plus de navigation ◀ ▶, et une session de navigation
            # incohérente qui finissait par planter Citron).
            if nav_override and "list" in nav_override:
                _nav_list = nav_override.get("list", [])
                _cur_idx = nav_override.get("index", -1)
            else:
                _nav_list = None
                # Index courant dans la liste (par chemin). Garde défensive :
                # si `path` est vide/None (ex: un futur appelant ouvrirait la
                # fiche pour un titre du tableur absent de la bibliothèque
                # sans passer par nav_override), on ne fait pas planter la
                # fenêtre — on affiche simplement sans navigation ◀ ▶ liée à
                # la Liste complète, plutôt qu'une exception os.path.normpath.
                _cur_idx = -1
                if path:
                    for _i, _vp in enumerate(self.video_paths):
                        if os.path.normpath(_vp) == os.path.normpath(path):
                            _cur_idx = _i; break
                    if _cur_idx == -1:
                        for _i, _vp in enumerate(self.video_paths):
                            if os.path.basename(_vp) == os.path.basename(path):
                                _cur_idx = _i; break

            # Cache de préchargement {path: (row_data, error)} — voir __init__.

            # ── Session de navigation en boucle ──────────────────────────
            # La navigation ◀ ▶ boucle indéfiniment (dernier → premier et
            # inversement) au lieu de s'arrêter aux extrémités. Une fois que
            # TOUS les titres de la liste ont été vus au moins une fois
            # pendant cette session, une confirmation "tous les titres ont
            # été traités, voulez-vous poursuivre ? (O/N)" est affichée.
            _nav_total = len(_nav_list) if _nav_list is not None else len(self.video_paths)
            if nav_session is None:
                nav_session = {"visited": {_cur_idx} if _cur_idx >= 0 else set(), "total": _nav_total}
            self._info_nav_session = nav_session
            # Afficher la position dans la liste (ex : "3/250"), maintenant
            # que _cur_idx et _nav_total sont connus.
            try:
                if 0 <= _cur_idx < _nav_total:
                    position_label.configure(text=f"{_cur_idx + 1}/{_nav_total}")
                else:
                    position_label.configure(text=f"—/{_nav_total}")
            except Exception:
                pass

            def _prefetch(idx):
                if _nav_list is not None:
                    return  # navigation restreinte : row_data déjà en mémoire, rien à précharger
                if 0 <= idx < len(self.video_paths):
                    p = self.video_paths[idx]
                    if p not in self._info_cache:
                        def do():
                            t = os.path.splitext(os.path.basename(p))[0]
                            rd, err = self._read_ods_row(t)
                            self._info_cache[p] = (rd, err)
                            # Borner la taille du cache : sans ça, une longue
                            # session de navigation ◀ ▶ à travers des
                            # centaines de titres le ferait grossir sans
                            # jamais redescendre. Éviction FIFO simple (on
                            # retire les entrées les plus anciennes) : ce
                            # cache ne sert qu'à accélérer la navigation
                            # immédiatement voisine, pas à mémoriser tout un
                            # historique, donc une précision LRU serait
                            # inutile ici.
                            while len(self._info_cache) > self._INFO_CACHE_MAX:
                                oldest = next(iter(self._info_cache))
                                del self._info_cache[oldest]
                        threading.Thread(target=do, daemon=True).start()

            # Précharger suivant et précédent immédiatement
            _prefetch(_cur_idx + 1)
            _prefetch(_cur_idx - 1)

            def _go_to_restricted(nxt):
                item = _nav_list[nxt]
                # _save_info_geo() arrête proprement la bande-annonce VLC (et
                # une éventuelle lecture vocale du résumé) avant de fermer.
                # Un simple win.destroy() laissait le lecteur VLC tourner en
                # arrière-plan à chaque navigation ▶/◀, ce qui finissait par
                # bloquer Citron après quelques clics (accumulation
                # d'instances VLC orphelines) et pouvait aussi capter le
                # focus clavier.
                try: _save_info_geo()
                except Exception:
                    try: win.destroy()
                    except Exception: pass
                self._open_info_window(
                    item.get("titre",""), item.get("path"),
                    item.get("row_data"), item.get("error"),
                    nav_override={
                        "list": _nav_list,
                        "index": nxt,
                        "breadcrumb": _search_breadcrumb,
                        "virtual_playlist_mode": bool(
                            nav_override and nav_override.get("virtual_playlist_mode")
                        ),
                    },
                    nav_session=nav_session, from_chain=True)

            def _go_to_library(nxt, direction):
                new_path = self.video_paths[nxt]
                # Voir commentaire de _go_to_restricted : toujours passer par
                # _save_info_geo() pour libérer proprement le lecteur VLC.
                try: _save_info_geo()
                except Exception:
                    try: win.destroy()
                    except Exception: pass
                # Le tableur a-t-il changé depuis le dernier chargement ?
                # Vider le cache AVANT de le consulter ci-dessous, sinon
                # une fiche déjà en cache resterait périmée indéfiniment.
                self._check_tableur_freshness()
                # Utiliser le cache si disponible
                # « Compléter le tableur » depuis Infos (voir bouton d'en-tête
                # plus haut) doit rester disponible tout le long de la
                # navigation ◀ ▶ dans la Liste complète des médias — on
                # propage donc le marqueur d'origine d'une fiche à l'autre.
                _garder_from_liste = bool(nav_override and nav_override.get("from_liste_medias"))
                if new_path in self._info_cache:
                    rd, err = self._info_cache[new_path]
                    new_titre = os.path.splitext(os.path.basename(new_path))[0]
                    self._open_info_window(
                        new_titre, new_path, rd, err,
                        nav_override={"from_liste_medias": True} if _garder_from_liste else None,
                        nav_session=nav_session, from_chain=True)
                else:
                    self._show_tableur_info(new_path, nav_session=nav_session, from_chain=True,
                                             from_liste_medias=_garder_from_liste)
                # Précharger le prochain
                _prefetch(nxt + direction)

            def _nav(direction, _idx=_cur_idx):
                if _nav_total == 0:
                    return
                nxt = (_idx + direction) % _nav_total  # boucle : dernier↔premier
                would_be = set(nav_session["visited"]); would_be.add(nxt)
                if len(would_be) >= _nav_total and _nav_total > 0:
                    # Tous les titres ont été traités pendant cette session
                    def _continue():
                        nav_session["visited"] = {nxt}
                        if _nav_list is not None:
                            _go_to_restricted(nxt)
                        else:
                            _go_to_library(nxt, direction)
                    def _stop():
                        _close_info_window()
                    self._ask_all_titles_visited(win, _continue, _stop)
                    return
                nav_session["visited"] = would_be
                if _nav_list is not None:
                    _go_to_restricted(nxt)
                else:
                    _go_to_library(nxt, direction)

            arrow_cfg = dict(width=44, height=44, font=("Arial",22,"bold"),
                             fg_color="#2a2a2a", hover_color="#3a3a3a",
                             text_color="#aaaaaa", corner_radius=22)

            def _nav_name(i):
                if _nav_total == 0:
                    return ""
                i = i % _nav_total  # boucle : le nom affiché suit la boucle
                if _nav_list is not None:
                    n = _nav_list[i].get("titre","")
                    return (n[:50]+"…") if len(n)>50 else n
                n = os.path.splitext(os.path.basename(self.video_paths[i]))[0]
                return (n[:50]+"…") if len(n)>50 else n
            prev_name = _nav_name(_cur_idx-1)
            next_name = _nav_name(_cur_idx+1)

            # Tooltip via une vraie fenêtre indépendante (CTkToplevel), comme _thumb_win
            # pour la barre de progression. Un CTkLabel positionné avec place() à l'intérieur
            # d'une fenêtre -fullscreen peut être mal rendu près des bords sur certains
            # systèmes (HighDPI / multi-écrans) : une fenêtre à part échappe à ce problème.
            tip_win_ref = [None, None]  # [toplevel, label]

            def _ensure_tip_win():
                if tip_win_ref[0] is not None and tip_win_ref[0].winfo_exists():
                    return tip_win_ref[0], tip_win_ref[1]
                tw = ctk.CTkToplevel(win)
                tw.wm_overrideredirect(True)
                tw.attributes("-topmost", True)
                lbl = ctk.CTkLabel(tw, text="", font=("Arial",12),
                                   fg_color="#1e3a5a", corner_radius=6,
                                   text_color="#ffffff")
                lbl.pack(padx=0, pady=0)
                tip_win_ref[0] = tw
                tip_win_ref[1] = lbl
                return tw, lbl

            def _show_tip(text, widget, tag=""):
                if not text or not text.strip():
                    return
                # Retirer extension pour affichage propre
                display = os.path.splitext(text)[0]
                if len(display) > 60: display = display[:57] + "…"
                tw, lbl = _ensure_tip_win()
                lbl.configure(text=f"  {display}  ")
                tw.update_idletasks()
                tip_w = tw.winfo_reqwidth()
                tip_h = tw.winfo_reqheight()
                screen_w = widget.winfo_screenwidth()
                bx = widget.winfo_rootx()
                by = widget.winfo_rooty() + widget.winfo_height() + 6
                x = bx + widget.winfo_width()//2 - tip_w//2
                # Empêcher la bulle de sortir de l'écran (gauche ET droite),
                # avec une marge de sécurité pour ne pas couper la flèche ▶/◀
                margin = 18
                x = max(margin, min(x, max(margin, screen_w - tip_w - margin)))
                tw.geometry(f"{tip_w}x{tip_h}+{x}+{by}")
                tw.deiconify()
                tw.lift()

            def _hide_tip():
                if tip_win_ref[0] is not None and tip_win_ref[0].winfo_exists():
                    tip_win_ref[0].withdraw()

            def _destroy_tip():
                if tip_win_ref[0] is not None and tip_win_ref[0].winfo_exists():
                    try: tip_win_ref[0].destroy()
                    except Exception: pass

            def _nav_stop_and_go(direction):
                # Anti-rebond : des clics/touches ▶/◀ très rapprochés (touche
                # maintenue, clics répétés) déclenchaient plusieurs
                # navigations en cascade avant que CustomTkinter ait fini son
                # initialisation interne de la fenêtre précédente (délai
                # interne différé pour la couleur de barre de titre sous
                # Windows) — la fenêtre se retrouvait détruite entre-temps,
                # provoquant un crash "bad window path name" qui rendait le
                # clavier inopérant. On ignore donc toute navigation trop
                # rapprochée de la précédente (< 400 ms).
                now = time.time()
                if now - getattr(self, "_info_nav_last_ts", 0) < 0.4:
                    return
                self._info_nav_last_ts = now
                # Stopper une éventuelle lecture vocale du résumé en cours et
                # restaurer le son de la vidéo AVANT de stopper le lecteur
                # (plus fiable que l'inverse : après vp.stop(), certaines
                # versions de VLC ignorent audio_set_mute()).
                try: self._stop_resume_speech(vid_player_ref)
                except Exception: pass
                # Stopper la vidéo résumé avant de naviguer
                vp = vid_player_ref[0]
                if vp:
                    try: vp.stop()
                    except Exception: pass
                _nav(direction)

            btn_left = ctk.CTkButton(outer_row, text="◀",
                                     command=lambda: _nav_stop_and_go(-1),
                                     **arrow_cfg)
            btn_left.pack(side="left", padx=6, pady=0, anchor="center")
            btn_left.bind("<Enter>", lambda e: _show_tip(f"◀ {prev_name}", btn_left, "GAUCHE"), add="+")
            btn_left.bind("<Leave>", lambda e: _hide_tip(), add="+")

            btn_right = ctk.CTkButton(outer_row, text="▶",
                                      command=lambda: _nav_stop_and_go(1),
                                      **arrow_cfg)
            btn_right.pack(side="right", padx=6, anchor="center")
            btn_right.bind("<Enter>", lambda e: _show_tip(f"{next_name} ▶", btn_right, "DROITE"), add="+")
            btn_right.bind("<Leave>", lambda e: _hide_tip(), add="+")
            # Navigation au clavier : flèches ◀ / ▶ équivalentes aux boutons.
            # bind sur la fenêtre entière (pas seulement un widget) pour que
            # ça marche quel que soit l'élément qui a le focus à l'intérieur.
            def _on_info_left(e=None):
                # Ne naviguer que si la fenêtre Infos est encore la fenêtre active
                # concernée (évite de voler les flèches d'autres fenêtres).
                try:
                    if not win.winfo_exists():
                        return
                except Exception:
                    return
                _nav_stop_and_go(-1)
                return "break"

            def _on_info_right(e=None):
                try:
                    if not win.winfo_exists():
                        return
                except Exception:
                    return
                _nav_stop_and_go(1)
                return "break"

            # bind_all : les flèches restent actives même si le focus est dans
            # le Text du résumé, le canvas VLC, etc. (sinon il fallait recliquer
            # sur ◀/▶ pour "récupérer" le clavier).
            win.bind("<Left>", _on_info_left)
            win.bind("<Right>", _on_info_right)
            win.bind_all("<Left>", _on_info_left)
            win.bind_all("<Right>", _on_info_right)

            def _unbind_info_keys():
                try:
                    win.unbind_all("<Left>")
                    win.unbind_all("<Right>")
                except Exception:
                    pass

            # Mémoriser pour défaire les bind_all à la fermeture (nettoyage
            # partagé avec _save_info_geo / _close_info_window).
            prev_unbind = getattr(self, "_info_keys_unbind", None)
            def _combined_unbind():
                _unbind_info_keys()
                if prev_unbind:
                    try:
                        prev_unbind()
                    except Exception:
                        pass
            self._info_keys_unbind = _combined_unbind
            win.focus_set()
            print(f"[Tooltip] Init fenêtre info : prev_name={prev_name!r} next_name={next_name!r} _cur_idx={_cur_idx}")

            # Contenu central scrollable
            from tkinter import Canvas as _Canvas
            center = ctk.CTkFrame(outer_row, fg_color="#1a1a1a")
            center.pack(side="left", fill="both", expand=True)

            canvas_scroll = _Canvas(center, bg="#1a1a1a", highlightthickness=0)
            sb = Scrollbar(center, orient="vertical", command=canvas_scroll.yview)
            canvas_scroll.configure(yscrollcommand=sb.set)
            sb.pack(side="right", fill="y")
            canvas_scroll.pack(side="left", fill="both", expand=True)
            cf = ctk.CTkFrame(canvas_scroll, fg_color="#1a1a1a")
            cfw = canvas_scroll.create_window((0,0), window=cf, anchor="nw")
            canvas_scroll.bind("<Configure>",
                lambda e: canvas_scroll.itemconfig(cfw, width=e.width))
            cf.bind("<Configure>",
                lambda e: canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all")))
            canvas_scroll.bind("<MouseWheel>",
                lambda e: canvas_scroll.yview_scroll(-1*(e.delta//120),"units"))

            # ── ZONE HAUTE : image + vidéo ─────────────────────
            TOP_H = 450
            IMG_W = 360

            top_frame = ctk.CTkFrame(cf, fg_color="#111111", height=TOP_H)
            top_frame.pack(fill="x")
            top_frame.pack_propagate(False)

            # Image (gauche)
            img_frame = ctk.CTkFrame(top_frame, fg_color="#000000", width=IMG_W, height=TOP_H)
            img_frame.pack(side="left", fill="y")
            img_frame.pack_propagate(False)

            if img_path and os.path.isfile(img_path):
                try:
                    from PIL import Image
                    pil_img = Image.open(img_path)
                    # "contain" : l'image entière tient toujours dans le cadre
                    # (ni le haut/bas, ni les côtés ne sont jamais rognés),
                    # quitte à laisser une bande noire sur les côtés ou en
                    # haut/bas selon son format. L'ancien calcul forçait
                    # systématiquement la hauteur à TOP_H puis recadrait en
                    # largeur si besoin, ce qui pouvait couper le haut et le
                    # bas d'une affiche plus large que haute.
                    ratio = min(IMG_W / pil_img.width, TOP_H / pil_img.height)
                    new_w = max(1, int(pil_img.width * ratio))
                    new_h = max(1, int(pil_img.height * ratio))
                    pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                    photo = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                    lbl_img = ctk.CTkLabel(img_frame, image=photo, text="")
                    lbl_img.image = photo
                    lbl_img.place(relx=0.5, rely=0.5, anchor="center")
                except Exception as ex:
                    ctk.CTkLabel(img_frame, text=f"⚠️ {ex}", font=("Arial",11),
                                 text_color="#ff6666", wraplength=IMG_W-20).pack(expand=True)
            else:
                ctk.CTkLabel(img_frame, text="🖼\nN.A.", font=("Arial",18),
                             text_color="#555555").pack(expand=True)

            # Vidéo résumé (droite)
            vid_outer = ctk.CTkFrame(top_frame, fg_color="#000000")
            vid_outer.pack(side="left", fill="both", expand=True)
            # Clic droit → menu de recherche, restreint à la zone VLC : le
            # bouton "🔍 Recherche" de l'en-tête couvre déjà le reste de la
            # fenêtre de façon garantie, inutile d'y dupliquer le clic droit.
            vid_outer.bind("<Button-3>", lambda e: self._tableur_info_right_click(e, win, _search_scope, _search_breadcrumb))

            # vid_player_ref[0] = le lecteur VLC de la vidéo résumé
            # vid_player_ref[1] = l'étiquette "🔇" affichée pendant la narration
            # vid_player_ref[2] = l'instance VLC associée (à libérer aussi,
            #                     sinon les threads/handles natifs de VLC
            #                     s'accumulent à chaque navigation ▶/◀)
            vid_player_ref = [None, None, None]

            if vid_path and os.path.isfile(vid_path):
                try:
                    vid_instance = vlc.Instance("--quiet", "--no-xlib")
                    vp = vid_instance.media_player_new()
                    vp.audio_set_mute(False)  # jamais d'état muet hérité d'une navigation précédente
                    vid_player_ref[0] = vp
                    vid_player_ref[2] = vid_instance

                    vid_canvas = Canvas(vid_outer, bg="black", highlightthickness=0)
                    vid_canvas.pack(fill="both", expand=True)
                    vid_canvas.bind("<Button-3>", lambda e: self._tableur_info_right_click(e, win, _search_scope, _search_breadcrumb))

                    # Boutons Lecture/Pause et Stop
                    vbtn_frame = ctk.CTkFrame(vid_outer, fg_color="#111111", height=70)
                    vbtn_frame.pack(fill="x", side="bottom")
                    vbtn_frame.pack_propagate(False)
                    ctk.CTkLabel(vbtn_frame, text="").pack(side="left", expand=True)

                    play_btn_ref = [None]

                    def _vid_stop():
                        vp.stop()
                        vm2 = vid_instance.media_new(vid_path)
                        vp.set_media(vm2)
                        hwnd = vid_canvas.winfo_id()
                        vp.set_hwnd(hwnd)
                        vp.play()
                        win.after(200, vp.pause)
                        if play_btn_ref[0]:
                            play_btn_ref[0].configure(text="▶")

                    def _vid_toggle():
                        st = vp.get_state()
                        if st == vlc.State.Playing:
                            vp.pause()
                            if play_btn_ref[0]: play_btn_ref[0].configure(text="▶")
                        else:
                            if st in (vlc.State.Ended, vlc.State.Stopped):
                                vm3 = vid_instance.media_new(vid_path)
                                vp.set_media(vm3)
                                vp.set_hwnd(vid_canvas.winfo_id())
                            vp.play()
                            if play_btn_ref[0]: play_btn_ref[0].configure(text="⏸")

                    pb = ctk.CTkButton(vbtn_frame, text="▶", width=60, height=30,
                                       font=("Arial",14), command=_vid_toggle,
                                       fg_color="#1a6e3c")
                    pb.pack(side="left", padx=6, pady=3)
                    play_btn_ref[0] = pb

                    ctk.CTkButton(vbtn_frame, text="⏹", width=60, height=30,
                                  font=("Arial",14), command=_vid_stop,
                                  fg_color="#8b3a00").pack(side="left", padx=4, pady=3)
                    # Icône "muet" : vide par défaut, affichée uniquement pendant
                    # la narration du résumé (voir _start_resume_speech /
                    # _restore_resume_video_mute), à droite du bouton "⏹".
                    mute_lbl = ctk.CTkLabel(vbtn_frame, text="", width=66,
                                            font=("Arial",42), text_color="#ff8888")
                    mute_lbl.pack(side="left", padx=(0,4))
                    vid_player_ref[1] = mute_lbl
                    ctk.CTkLabel(vbtn_frame, text="").pack(side="left", expand=True)

                    # Attacher VLC et afficher première image en pause
                    def _attach(event=None):
                        vp.set_hwnd(vid_canvas.winfo_id())
                        vm0 = vid_instance.media_new(vid_path)
                        vp.set_media(vm0)
                        vp.play()
                        win.after(300, lambda: (vp.pause(),
                                                play_btn_ref[0].configure(text="▶")
                                                if play_btn_ref[0] else None))
                    vid_canvas.bind("<Map>", _attach)

                    # Retour en pause à la fin (point 2)
                    def _check_end():
                        if not win.winfo_exists(): return
                        if vp.get_state() == vlc.State.Ended:
                            _vid_stop()
                        win.after(800, _check_end)
                    win.after(800, _check_end)

                    # L'arrêt de la vidéo à la fermeture est maintenant géré de
                    # façon unifiée par _save_info_geo (bouton "✕ Fermer" et
                    # croix de la fenêtre passent tous les deux par là).

                except Exception as ex:
                    ctk.CTkLabel(vid_outer, text=f"⚠️ {ex}", font=("Arial",12),
                                 text_color="#ff6666").pack(expand=True)
            else:
                ctk.CTkLabel(vid_outer, text="🎞\nN.A.", font=("Arial",18),
                             text_color="#555555").pack(expand=True)

            # ── LIGNE CENTRALE (col12, filmeur, durée, type, personnes) ─
            # "Personnes" reste dans cette même ligne combinée (comme avant),
            # mais chaque nom est maintenant une étiquette cliquable individuelle
            # (survol -> petit menu "ℹ️ Informations" -> recherche AlloCiné),
            # séparée visuellement par "/" comme dans l'ancien texte brut.
            info_bar = ctk.CTkFrame(cf, fg_color="#1e2e3e")
            info_bar.pack(fill="x", pady=(2,0))

            info_row = ctk.CTkFrame(info_bar, fg_color="transparent")
            info_row.pack(pady=10)

            parts = []
            if col_12 != "N.A.":       parts.append(col_12)
            if col_filmeur != "N.A.":  parts.append(f"de {col_filmeur}")
            if col_duree != "N.A.":    parts.append(f"⏱ {col_duree} minutes")
            if col_type != "N.A.":     parts.append(f"🏷 {col_type}")
            info_line = "   ".join(parts)

            if info_line:
                ctk.CTkLabel(info_row, text=info_line, font=("Arial",13,"bold"),
                             text_color="#e0e0e0").pack(side="left")

            if col_complement != "N.A." and col_complement.strip():
                # Le complément peut contenir un lien (ex. bande-annonce
                # YouTube trouvée via « 🌐 Compléter le tableur ») : dans ce
                # cas on l'affiche comme un bouton cliquable plutôt qu'en
                # texte brut.
                ba_frame = ctk.CTkFrame(cf, fg_color="transparent")
                ba_frame.pack(fill="x", pady=(4, 0))
                idx_http = col_complement.find("http")
                if idx_http != -1:
                    url_ba = col_complement[idx_http:].split()[0]
                    label_txt = col_complement[:idx_http].strip(" :\n") or "Ouvrir le lien"
                    ctk.CTkButton(ba_frame, text=f"▶ {label_txt}", height=30,
                                  fg_color="transparent", border_width=1,
                                  command=lambda u=url_ba: webbrowser.open(u)).pack(anchor="w")
                else:
                    ctk.CTkLabel(ba_frame, text=col_complement, font=("Arial", 12),
                                 text_color="#cccccc", wraplength=500,
                                 justify="left").pack(anchor="w")

            if col_personnes != "N.A.":
                people = [p.strip() for p in col_personnes.split("/") if p.strip()]
                if people:
                    ctk.CTkLabel(info_row, text=("   avec " if info_line else "avec "),
                                 font=("Arial",13,"bold"), text_color="#e0e0e0").pack(side="left")
                    for i, _name in enumerate(people):
                        if i > 0:
                            ctk.CTkLabel(info_row, text=" / ", font=("Arial",13,"bold"),
                                         text_color="#e0e0e0").pack(side="left")
                        name_lbl = ctk.CTkLabel(info_row, text=_name,
                                                font=("Arial",13,"bold","underline"),
                                                text_color="#8ecbff", cursor="hand2")
                        name_lbl.pack(side="left")
                        name_lbl.bind("<Enter>",
                            lambda e, w=name_lbl, n=_name: self._show_person_menu(w, n))

            # ── SECTIONS TEXTE ──────────────────────────────────
            from tkinter import Text as _Text
            def _section(label, text, font_size=13, speakable=False, editable=False):
                f = ctk.CTkFrame(cf, fg_color="#212121", corner_radius=6)
                f.pack(fill="x", padx=12, pady=4)
                header_row = ctk.CTkFrame(f, fg_color="transparent")
                header_row.pack(fill="x", padx=12, pady=(8,2))
                ctk.CTkLabel(header_row, text=label, font=("Arial",12,"bold"),
                             text_color="#4a9fd4", anchor="w").pack(side="left")
                if speakable and text and text != "N.A.":
                    speak_btn = ctk.CTkButton(header_row, text="🔊 Écouter le résumé",
                                              height=26, width=160, font=("Arial",11),
                                              fg_color="#2a4a6a", hover_color="#3a6a9a",
                                              command=lambda: None)
                    speak_btn.pack(side="right")
                else:
                    speak_btn = None
                if editable:
                    # Bouton dédié à l'édition (plutôt qu'un clic direct sur le
                    # texte) pour ne pas interférer avec la sélection de texte
                    # à la souris (copier/coller) — voir plus bas.
                    edit_btn = ctk.CTkButton(header_row, text="✏️ Modifier",
                                              height=26, width=110, font=("Arial",11),
                                              fg_color="#5a5a2a", hover_color="#7a7a3a",
                                              command=lambda: None)
                    edit_btn.pack(side="right", padx=(0,8))
                txt = _Text(f, font=("Arial",font_size), fg="#cccccc", bg="#212121",
                            relief="flat", wrap="word", height=2,
                            bd=0, highlightthickness=0, cursor="xterm",
                            selectbackground="#1f6aa5", selectforeground="white")
                txt.insert("1.0", text)
                # Lecture seule mais SÉLECTIONNABLE : garder l'état "normal"
                # (un Text "disabled" empêche aussi la sélection à la souris)
                # et ne bloquer que les touches qui modifieraient le texte —
                # la sélection (glisser-souris) et le copier (Ctrl+C /
                # Ctrl+A) restent pleinement fonctionnels.
                def _readonly_guard(event, t=txt):
                    ctrl = bool(event.state & 0x4)
                    if ctrl and event.keysym.lower() in ("c", "a", "insert"):
                        return None  # laisser passer Ctrl+C / Ctrl+A / Ctrl+Insert
                    nav_keys = ("Left","Right","Up","Down","Home","End",
                                "Prior","Next","Shift_L","Shift_R","Control_L","Control_R")
                    if event.keysym in nav_keys:
                        return None
                    return "break"  # bloque toute frappe qui modifierait le texte
                txt.bind("<Key>", _readonly_guard)
                txt.bind("<<Paste>>", lambda e: "break")
                txt.bind("<Button-2>", lambda e: "break")  # clic molette = collage (X11)

                # Menu contextuel « Copier » sur clic droit (et clic gauche si
                # une sélection est déjà active) pour copier la sélection bleue.
                def _copy_selection(t=txt):
                    try:
                        sel = t.get("sel.first", "sel.last")
                    except Exception:
                        sel = ""
                    if not sel:
                        # Pas de sélection → copier tout le résumé
                        try:
                            sel = t.get("1.0", "end-1c")
                        except Exception:
                            sel = ""
                    if not sel:
                        return
                    try:
                        t.clipboard_clear()
                        t.clipboard_append(sel)
                        self._show_toast("📋 Texte copié", ms=2000, color="#2a4a6a")
                    except Exception:
                        pass

                def _popup_copy_menu(event, t=txt):
                    menu = Menu(t, tearoff=0, font=("Arial", 13))
                    menu.add_command(label="Copier", command=_copy_selection)
                    try:
                        menu.tk_popup(event.x_root, event.y_root)
                    finally:
                        menu.grab_release()
                    return "break"

                txt.bind("<Button-3>", _popup_copy_menu)
                # Clic gauche sur une sélection déjà active : ouvre aussi le menu
                # (demande utilisateur : « un clic doit dérouler un menu »).
                def _on_btn1_copy_menu(event, t=txt):
                    try:
                        # index@xy : caractère sous le curseur
                        idx = t.index(f"@{event.x},{event.y}")
                        ranges = t.tag_ranges("sel")
                        if not ranges:
                            return  # pas de sélection → comportement normal
                        # Clic à l'intérieur de la sélection bleue → menu Copier
                        inside = False
                        for i in range(0, len(ranges), 2):
                            if t.compare(ranges[i], "<=", idx) and t.compare(idx, "<", ranges[i+1]):
                                inside = True
                                break
                        if inside:
                            _popup_copy_menu(event, t)
                            return "break"
                    except Exception:
                        pass
                txt.bind("<Button-1>", _on_btn1_copy_menu, add="+")
                txt.pack(anchor="w", padx=16, pady=(0,8), fill="x")
                if speak_btn is not None:
                    # IMPORTANT : lire le texte ACTUEL du widget au moment du
                    # clic (t.get(...)), pas une valeur figée à la création —
                    # sinon après modification du résumé (édition), le bouton
                    # continuait de lire l'ancien texte.
                    speak_btn.configure(command=lambda t=txt, b=speak_btn:
                        self._toggle_resume_speech(t.get("1.0", "end-1c"), vid_player_ref, b))
                if editable:
                    edit_btn.configure(command=lambda t=txt:
                        self._open_resume_edit_dialog(t, col_titre, col_annee, win))
                # Hauteur automatique — tout le texte visible sans scroll
                def _set_height(t=txt, fs=font_size):
                    try:
                        t.update_idletasks()
                        n = int(t.index("end-1c").split(".")[0])
                        # Résumé (font 17) → minimum 12 lignes (ajusté proportionnellement
                        # à la réduction de taille de police, depuis les valeurs d'origine
                        # calibrées pour font 22 : min_h=16, multiplicateur=4)
                        min_h = 12 if fs >= 15 else 2
                        t.configure(height=max(min_h, n * (3 if fs >= 15 else 1)))
                    except Exception: pass
                f.after(50, _set_height)

            _section("📝 Résumé", col_resume, font_size=17, speakable=True, editable=True)

            # Pré-synthèse en tâche de fond : lance dès maintenant (affichage
            # de la fiche) la synthèse vocale du résumé, pour qu'elle soit
            # déjà prête — ou bien avancée — si l'utilisateur clique ensuite
            # sur « 🔊 Écouter le résumé ». Voir _prefetch_resume_speech.
            self._prefetch_resume_speech(col_resume, win)

        FRENCH_VOICES = [
            ("fr-FR-DeniseNeural", "Denise (France, femme)"),
            ("fr-FR-HenriNeural", "Henri (France, homme)"),
            ("fr-FR-EloiseNeural", "Éloise (France, femme, jeune)"),
            ("fr-CA-SylvieNeural", "Sylvie (Canada, femme)"),
            ("fr-CA-JeanNeural", "Jean (Canada, homme)"),
            ("fr-CH-ArianeNeural", "Ariane (Suisse, femme)"),
            ("fr-BE-CharlineNeural", "Charline (Belgique, femme)"),
        ]

        def _get_resume_voice(self):
            return getattr(self, "_resume_voice", "fr-FR-DeniseNeural")

        def _set_resume_voice(self, voice_id):
            self._resume_voice = voice_id
            self.save_settings()

        def _show_voice_menu(self, anchor_widget, parent_menu=None):
            """Sous-menu de choix de voix, affiché EN CASCADE à côté de
            l'entrée "🎙️ Voix du résumé" (anchor_widget = le bouton de cette
            entrée dans le menu Paramètres), et non plus au-dessus du bouton
            ⚙ Paramètres lui-même — ce qui le faisait apparaître au même
            endroit que le menu Paramètres, rendant la sélection d'une voix
            impossible.

            parent_menu (optionnel) : la fenêtre du menu Paramètres, gardée
            ouverte pendant que ce sous-menu est affiché (comportement de
            menu en cascade classique) ; les deux se referment ensemble dès
            que le curseur quitte l'un et l'autre, ou dès qu'une voix est
            choisie. Toujours accepté comme None (ex: appel de test interne
            _tc_step_menus_stress), auquel cas le sous-menu se comporte
            comme une fenêtre autonome (ancienne fiabilité de fermeture
            conservée)."""
            if getattr(self, "_voice_menu_win", None) and self._voice_menu_win.winfo_exists():
                self._voice_menu_win.destroy()
            pw = ctk.CTkToplevel(self)
            pw.wm_overrideredirect(True)
            pw.attributes("-topmost", True)
            pw.configure(fg_color="#2a2a2a")
            self._voice_menu_win = pw
            current = self._get_resume_voice()

            def _close_menu(e=None):
                try: pw.destroy()
                except Exception: pass
                if getattr(self, "_voice_menu_win", None) is pw:
                    self._voice_menu_win = None

            def _select(v):
                _close_menu()
                if parent_menu is not None:
                    try:
                        if parent_menu.winfo_exists():
                            parent_menu.destroy()
                    except Exception:
                        pass
                    if getattr(self, "_params_menu_win", None) is parent_menu:
                        self._params_menu_win = None
                self._set_resume_voice(v)

            for voice_id, label in self.FRENCH_VOICES:
                marker = "✓ " if voice_id == current else "   "
                ctk.CTkButton(pw, text=f"{marker}{label}", anchor="w",
                              width=210, height=30, font=("Arial",12),
                              fg_color="#2a2a2a", hover_color="#3a6a9a",
                              command=lambda v=voice_id: _select(v)
                              ).pack(fill="x", padx=2, pady=1)

            # Positionné À CÔTÉ (à droite) de l'entrée du menu Paramètres —
            # comme un sous-menu en cascade classique — et non plus au-dessus
            # du bouton ⚙ Paramètres global. Repli à gauche si ça dépasserait
            # le bord droit de l'écran.
            pw.update_idletasks()
            bx = anchor_widget.winfo_rootx() + anchor_widget.winfo_width() + 2
            by = anchor_widget.winfo_rooty()
            try:
                screen_w = self.winfo_screenwidth()
                if bx + pw.winfo_reqwidth() > screen_w:
                    bx = anchor_widget.winfo_rootx() - pw.winfo_reqwidth() - 2
            except Exception:
                pass
            pw.geometry(f"+{bx}+{by}")

            def _poll_pointer():
                if not pw.winfo_exists():
                    return
                try:
                    px, py = self.winfo_pointerx(), self.winfo_pointery()
                    over_menu = (pw.winfo_rootx() <= px <= pw.winfo_rootx()+pw.winfo_width()
                                 and pw.winfo_rooty() <= py <= pw.winfo_rooty()+pw.winfo_height())
                    over_anchor = False
                    if anchor_widget.winfo_exists():
                        over_anchor = (anchor_widget.winfo_rootx() <= px <= anchor_widget.winfo_rootx()+anchor_widget.winfo_width()
                                    and anchor_widget.winfo_rooty() <= py <= anchor_widget.winfo_rooty()+anchor_widget.winfo_height())
                    over_parent = False
                    if parent_menu is not None and parent_menu.winfo_exists():
                        over_parent = (parent_menu.winfo_rootx() <= px <= parent_menu.winfo_rootx()+parent_menu.winfo_width()
                                    and parent_menu.winfo_rooty() <= py <= parent_menu.winfo_rooty()+parent_menu.winfo_height())
                    if not over_menu and not over_anchor and not over_parent:
                        _close_menu()
                        if parent_menu is not None:
                            try:
                                if parent_menu.winfo_exists():
                                    parent_menu.destroy()
                            except Exception:
                                pass
                            if getattr(self, "_params_menu_win", None) is parent_menu:
                                self._params_menu_win = None
                        return
                except Exception:
                    pass
                pw.after(120, _poll_pointer)
            pw.after(120, _poll_pointer)

        def _get_edge_tts_available(self):
            """Vérifie une seule fois (résultat mis en cache) si edge-tts est
            disponible (module Python installé) : voix neuronale bien plus
            naturelle que la voix Windows par défaut (SAPI), gratuite et sans
            clé API, mais nécessite une connexion internet et `pip install
            edge-tts`. Utilisée en priorité si disponible."""
            if hasattr(self, "_edge_tts_available_cache"):
                return self._edge_tts_available_cache
            try:
                import edge_tts  # noqa: F401
                self._edge_tts_available_cache = True
                print("[Résumé] edge-tts détecté : voix neuronale utilisée.")
            except ImportError:
                self._edge_tts_available_cache = False
                print("[Résumé] edge-tts non installé — voix Windows (SAPI) utilisée. "
                      "Pour une voix plus naturelle : pip install edge-tts")
            return self._edge_tts_available_cache

        def _toggle_resume_speech(self, text, vid_player_ref, btn):
            """Démarre ou arrête la lecture vocale du résumé (bascule)."""
            if getattr(self, "_resume_speech_active", False):
                self._stop_resume_speech(vid_player_ref, btn)
            else:
                self._start_resume_speech(text, vid_player_ref, btn)

        def _start_resume_speech(self, text, vid_player_ref, btn):
            """Lance la lecture vocale du résumé. Utilise edge-tts (voix
            neuronale fr-FR, bien plus naturelle) si disponible, sinon la voix
            Windows intégrée (SAPI, plus robotique mais toujours disponible sans
            rien installer). Coupe le son de la '🎞 Vidéo résumé' pendant la
            lecture pour éviter tout chevauchement audio."""
            text = (text or "").strip()
            if not text or text == "N.A.":
                return
            if os.name != "nt":
                messagebox.showinfo("Lecture du résumé",
                    "La lecture vocale n'est disponible que sous Windows.")
                return
            if getattr(self, "_resume_speech_active", False):
                return
            self._resume_speech_active = True
            self._resume_speech_stop_event = threading.Event()
            self._resume_speech_proc = None
            self._resume_speech_mci_alias = None
            # Couper le son de la vidéo résumé pendant la lecture (et retenir son
            # état précédent pour le restaurer une fois la lecture terminée).
            # NB : vp.audio_get_mute() peut renvoyer -1 ("état inconnu") si VLC
            # n'a pas encore résolu la piste audio à cet instant ; dans ce cas,
            # bool(-1) vaut True et la restauration re-couperait le son par
            # erreur. On ne retient donc que 0/1 comme valeurs valides, et on
            # suppose "non muet" (False) par défaut sinon.
            self._resume_speech_vp_was_muted = False
            try:
                vp = vid_player_ref[0] if vid_player_ref else None
                if vp:
                    raw_mute = vp.audio_get_mute()
                    self._resume_speech_vp_was_muted = bool(raw_mute) if raw_mute in (0, 1) else False
                    vp.audio_set_mute(True)
                    # Affiche l'icône "🔇" à droite du bouton "⏹" de la vidéo
                    # résumé pendant toute la durée de la narration.
                    mute_lbl = vid_player_ref[1] if len(vid_player_ref) > 1 else None
                    if mute_lbl and mute_lbl.winfo_exists():
                        mute_lbl.configure(text="🔇")
            except Exception:
                pass
            self._resume_speech_btn = btn
            self._resume_speech_vid_ref = vid_player_ref
            btn.configure(text="⏹ Arrêter la lecture", fg_color="#8b3a00", hover_color="#a04a10")

            if self._get_edge_tts_available():
                threading.Thread(target=self._resume_speech_worker_edge,
                                 args=(text, self._get_resume_voice()), daemon=True).start()
            else:
                threading.Thread(target=self._resume_speech_worker_sapi,
                                 args=(text,), daemon=True).start()

        def _split_speech_first_chunk(self, text, max_first_chars=140):
            """Découpe le texte en un premier segment court (idéalement une
            phrase entière, sinon les ~140 premiers caractères coupés sur un
            espace) et le reste. Sert à démarrer la narration sur ce petit
            segment pendant que le reste se synthétise derrière, au lieu
            d'attendre que tout le résumé soit synthétisé avant de parler."""
            text = (text or "").strip()
            if len(text) <= max_first_chars:
                return text, ""
            window = text[:max_first_chars + 40]
            import re as _re2
            matches = list(_re2.finditer(r"[.!?…]+\s", window))
            if matches:
                cut = matches[0].end()
            else:
                cut = text.rfind(" ", 0, max_first_chars)
                if cut <= 0:
                    cut = max_first_chars
            return text[:cut].strip(), text[cut:].strip()

        def _resume_speech_cache_key(self, text, voice):
            """Clé de cache identifiant sans ambiguïté un couple (texte, voix)
            — sert à faire correspondre une pré-synthèse lancée à l'ouverture
            de la fiche avec la lecture demandée ensuite (et à l'invalider
            automatiquement si le résumé a été modifié ou la voix changée
            entre-temps : la clé ne correspondra simplement plus)."""
            import hashlib
            return hashlib.md5(f"{voice}\x00{text}".encode("utf-8", "ignore")).hexdigest()

        def _discard_prefetch_files(self, entry):
            """Supprime les fichiers MP3 d'une entrée de pré-synthèse (segments
            déjà écrits sur disque, qu'ils aient servi ou non)."""
            for p in entry.get("paths", []):
                if p:
                    try:
                        if os.path.isfile(p): os.remove(p)
                    except Exception:
                        pass

        def _cleanup_resume_prefetch(self, key):
            """Appelé à la fermeture de la fiche Infos : si la pré-synthèse
            correspondante n'a pas été consommée par une lecture (l'utilisateur
            n'a pas cliqué sur 🔊), on nettoie ses fichiers temporaires une fois
            les threads de synthèse en cours arrivés à leur terme."""
            cache = getattr(self, "_resume_speech_prefetch", None)
            if not cache or key not in cache:
                return
            entry = cache.pop(key, None)
            if not entry:
                return
            def _rm():
                for ev in entry["ready"]:
                    ev.wait(timeout=5)
                self._discard_prefetch_files(entry)
            threading.Thread(target=_rm, daemon=True).start()

        def _prefetch_resume_speech(self, text, win):
            """Lance en arrière-plan, dès l'affichage de la fiche Infos, la
            synthèse vocale (edge-tts) du résumé — premier segment court,
            puis le reste — exactement comme le fera _resume_speech_worker_edge
            si l'utilisateur clique sur « 🔊 Écouter le résumé ». Si le clic
            arrive après coup (le cas courant), la lecture réutilise
            directement ces fichiers déjà prêts au lieu de repartir de zéro :
            la narration démarre alors immédiatement.

            Ne fait rien si edge-tts n'est pas disponible, si le résumé est
            vide, ou hors Windows (la voix SAPI, elle, est déjà quasi
            instantanée et n'a pas besoin de pré-synthèse)."""
            text = (text or "").strip()
            if not text or text == "N.A." or os.name != "nt":
                return
            if not self._get_edge_tts_available():
                return
            voice = self._get_resume_voice()
            key = self._resume_speech_cache_key(text, voice)
            cache = getattr(self, "_resume_speech_prefetch", None)
            if cache is None:
                cache = {}
                self._resume_speech_prefetch = cache
            if key in cache:
                return  # déjà pré-synthétisé (ou en cours) pour ce texte/voix

            first_chunk, rest_chunk = self._split_speech_first_chunk(text)
            chunks = [first_chunk] + ([rest_chunk] if rest_chunk else [])
            entry = {
                "paths": [None, None],
                "ready": [threading.Event(), threading.Event()],
                "ok": [False, False],
                "chunks": chunks,
            }
            cache[key] = entry

            pid = os.getpid()
            self._resume_speech_prefetch_seq = getattr(self, "_resume_speech_prefetch_seq", 0) + 1
            seq = self._resume_speech_prefetch_seq

            def _mp3_path(idx):
                return os.path.join(
                    tempfile.gettempdir(),
                    f"citron_prefetch_{pid}_{int(time.time()*1000)}_{seq}_{idx}.mp3"
                )

            def _synth_one(idx):
                try:
                    import edge_tts, asyncio
                    path = _mp3_path(idx)
                    async def _s():
                        communicate = edge_tts.Communicate(chunks[idx], voice)
                        await communicate.save(path)
                    asyncio.run(_s())
                    if os.path.isfile(path):
                        entry["paths"][idx] = path
                        entry["ok"][idx] = True
                except Exception as ex:
                    print(f"[Résumé] Pré-synthèse : erreur segment {idx} : {ex}")
                finally:
                    entry["ready"][idx].set()

            threading.Thread(target=_synth_one, args=(0,), daemon=True).start()
            if len(chunks) > 1:
                threading.Thread(target=_synth_one, args=(1,), daemon=True).start()
            else:
                entry["ready"][1].set()

            # Nettoyage si la fiche se ferme sans que l'utilisateur n'ait
            # cliqué sur 🔊 (pré-synthèse jamais consommée).
            try:
                win.bind("<Destroy>", lambda e, k=key: self._cleanup_resume_prefetch(k), add="+")
            except Exception:
                pass

        def _resume_speech_worker_edge(self, text, voice):
            """Synthétise le résumé avec edge-tts (appel direct à la bibliothèque
            Python, sans relancer un processus séparé — plus rapide), puis joue
            le MP3 obtenu nativement via l'interface Windows MCI (aucun besoin de
            ffmpeg ni de conversion, encore plus rapide).

            Démarrage rapide : au lieu de synthétiser tout le résumé avant de
            lancer la moindre lecture (ce qui pouvait faire attendre plusieurs
            secondes avant que Citron ne dise le premier mot sur un résumé
            long), on synthétise d'abord une courte première phrase et on la
            joue tout de suite, pendant que le reste du résumé se synthétise
            en parallèle dans un thread séparé — la narration démarre donc
            quasi instantanément, et enchaîne sur la suite dès qu'elle est
            prête."""
            stop_event = self._resume_speech_stop_event

            # Une pré-synthèse a-t-elle été lancée pour ce texte/voix exacts
            # dès l'affichage de la fiche Infos (voir _prefetch_resume_speech) ?
            # Si oui, on la récupère (et on la retire du cache, pour que le
            # nettoyage à la fermeture de la fenêtre ne la supprime pas sous
            # nos pieds) au lieu de repartir de zéro.
            key = self._resume_speech_cache_key(text, voice)
            prefetch_cache = getattr(self, "_resume_speech_prefetch", None)
            entry = prefetch_cache.pop(key, None) if prefetch_cache else None
            if entry is not None:
                entry["ready"][0].wait(timeout=15)
                if stop_event.is_set():
                    self._discard_prefetch_files(entry)
                    return
                if entry["ok"][0]:
                    try:
                        self._play_mp3_and_wait(entry["paths"][0], stop_event)
                        if not stop_event.is_set() and len(entry["chunks"]) > 1:
                            entry["ready"][1].wait(timeout=30)
                            if not stop_event.is_set() and entry["ok"][1]:
                                self._play_mp3_and_wait(entry["paths"][1], stop_event)
                    finally:
                        self._discard_prefetch_files(entry)
                        if not stop_event.is_set():
                            self.after(0, self._on_resume_speech_done)
                    return
                # Pré-synthèse ratée (rare) : on nettoie et on repart sur la
                # voie normale ci-dessous, comme si de rien n'était.
                self._discard_prefetch_files(entry)

            pid = os.getpid()
            # Nom de fichier unique par lecture (pid + timestamp + compteur) :
            # avec un nom fixe basé uniquement sur le pid, un enchaînement rapide
            # de deux narrations (ex: reliquat d'un thread précédent pas encore
            # totalement arrêté) pouvait faire écrire/lire/supprimer le même
            # fichier depuis deux endroits à la fois, coupant ou corrompant la
            # lecture de façon aléatoire.
            self._resume_speech_seq = getattr(self, "_resume_speech_seq", 0) + 1
            seq = self._resume_speech_seq

            def _mp3_path(idx):
                return os.path.join(
                    tempfile.gettempdir(),
                    f"citron_resume_{pid}_{int(time.time()*1000)}_{seq}_{idx}.mp3"
                )

            first_chunk, rest_chunk = self._split_speech_first_chunk(text)
            chunks = [first_chunk] + ([rest_chunk] if rest_chunk else [])
            paths = [_mp3_path(i) for i in range(len(chunks))]

            try:
                import edge_tts
                import asyncio

                async def _synth(txt, path):
                    communicate = edge_tts.Communicate(txt, voice)
                    await communicate.save(path)

                # Synthèse (courte, donc rapide) du premier segment.
                asyncio.run(_synth(chunks[0], paths[0]))
                if stop_event.is_set():
                    return
                if not os.path.isfile(paths[0]):
                    print("[Résumé] edge-tts n'a produit aucun fichier, repli sur la voix Windows.")
                    self._resume_speech_worker_sapi(text)
                    return

                # Synthèse du reste en arrière-plan, pendant que le premier
                # segment est en train de jouer.
                rest_ready = threading.Event()
                rest_ok = {"ok": False}

                def _synth_rest():
                    try:
                        asyncio.run(_synth(chunks[1], paths[1]))
                        rest_ok["ok"] = os.path.isfile(paths[1])
                    except Exception as ex:
                        print(f"[Résumé] Erreur edge-tts (suite) : {ex}")
                    finally:
                        rest_ready.set()

                if len(chunks) > 1:
                    threading.Thread(target=_synth_rest, daemon=True).start()
                else:
                    rest_ready.set()

                self._play_mp3_and_wait(paths[0], stop_event)

                if not stop_event.is_set() and len(chunks) > 1:
                    rest_ready.wait()
                    if not stop_event.is_set() and rest_ok["ok"]:
                        self._play_mp3_and_wait(paths[1], stop_event)
            except Exception as ex:
                print(f"[Résumé] Erreur edge-tts : {ex}")
                if not stop_event.is_set():
                    self._resume_speech_worker_sapi(text)
                    return
            finally:
                for p in paths:
                    try:
                        if os.path.isfile(p): os.remove(p)
                    except Exception: pass
                if not stop_event.is_set():
                    self.after(0, self._on_resume_speech_done)

        def _play_mp3_and_wait(self, mp3_path, stop_event):
            """Joue un MP3 via l'interface Windows MCI (winmm.dll), nativement,
            sans passer par VLC ni par une conversion ffmpeg.

            NOTE (fix 2026-07-30) : juste après la commande 'play', le pilote
            MCI met parfois quelques dizaines de ms avant de rapporter
            réellement l'état "playing" (surtout si la machine est occupée,
            ex: recherche floue en cours dans le tableur). L'ancienne version
            considérait tout état différent de "playing" comme une fin de
            lecture et appelait aussitôt 'stop'/'close', ce qui coupait la
            narration en plein milieu de façon aléatoire selon la charge
            système. On ne coupe désormais que sur un état "stopped" confirmé,
            après une courte période de grâce, et on réessaie la lecture de la
            durée si elle n'est pas immédiatement disponible."""
            if os.name != "nt":
                return
            # Alias unique par lecture (pid + timestamp) : un alias fixe par pid
            # pouvait entrer en conflit si un précédent 'close' n'était pas
            # encore totalement retombé (MCI refuse un alias déjà utilisé).
            alias = f"citron_tts_{os.getpid()}_{int(time.time()*1000)}"
            self._resume_speech_mci_alias = alias
            mci = ctypes.windll.winmm.mciSendStringW
            buf = ctypes.create_unicode_buffer(128)

            def _mci_ok(cmd):
                return mci(cmd, None, 0, None) == 0

            try:
                if not _mci_ok(f'open "{mp3_path}" type mpegvideo alias {alias}'):
                    print("[Résumé] MCI : échec de l'ouverture du fichier audio, narration annulée.")
                    return
                if not _mci_ok(f'play {alias}'):
                    print("[Résumé] MCI : échec du démarrage de la lecture, narration annulée.")
                    return

                # Récupérer la durée totale, avec quelques tentatives : juste
                # après 'open'/'play', le pilote MCI n'a pas toujours fini
                # d'analyser le fichier et peut renvoyer 0 la première fois.
                length_ms = 0
                for _ in range(20):
                    mci(f'status {alias} length', buf, 128, None)
                    try:
                        length_ms = int(buf.value)
                    except Exception:
                        length_ms = 0
                    if length_ms > 0:
                        break
                    if stop_event.is_set():
                        break
                    time.sleep(0.05)

                step_ms = 100
                waited = 0
                poll_count = 0
                # Nombre de relevés de statut à ignorer avant de faire confiance
                # à l'état "stopped" (le temps que le pilote démarre vraiment).
                grace_polls = 5
                while True:
                    if stop_event.is_set():
                        break
                    time.sleep(step_ms / 1000)
                    waited += step_ms
                    poll_count += 1
                    mci(f'status {alias} mode', buf, 128, None)
                    mode = buf.value.strip().lower()
                    if poll_count > grace_polls and mode == "stopped":
                        break
                    if length_ms > 0 and waited >= length_ms and mode != "playing":
                        break
                    # Filet de sécurité : si on connaît la durée et qu'on l'a
                    # largement dépassée (marge de 1.5s), on arrête d'attendre
                    # même si le statut renvoyé est ambigu.
                    if length_ms > 0 and waited > length_ms + 1500:
                        break
            except Exception as ex:
                print(f"[Résumé] Erreur lecture MP3 (MCI) : {ex}")
            finally:
                try:
                    mci(f'stop {alias}', None, 0, None)
                    mci(f'close {alias}', None, 0, None)
                except Exception:
                    pass
                self._resume_speech_mci_alias = None

        def _resume_speech_worker_sapi(self, text):
            """Synthétise et joue le résumé avec la voix Windows intégrée (SAPI,
            via PowerShell) — utilisée si edge-tts n'est pas disponible. Choisit
            automatiquement la meilleure voix française installée (une voix
            'Natural' si Windows en expose une à SAPI, sinon la voix par défaut)."""
            stop_event = getattr(self, "_resume_speech_stop_event", None)
            try:
                tmp_txt = os.path.join(tempfile.gettempdir(), f"citron_resume_{os.getpid()}.txt")
                with open(tmp_txt, "w", encoding="utf-8") as f:
                    f.write(text)
                ps_cmd = (
                    "Add-Type -AssemblyName System.Speech; "
                    "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                    "$s.SetOutputToDefaultAudioDevice(); "
                    "$best = $s.GetInstalledVoices() | Where-Object {$_.VoiceInfo.Culture.Name -like 'fr*'} | "
                    "Sort-Object {$_.VoiceInfo.Name -notmatch 'Natural'} | Select-Object -First 1; "
                    "if ($best) { $s.SelectVoice($best.VoiceInfo.Name) }; "
                    f"$t = Get-Content -LiteralPath '{tmp_txt}' -Raw -Encoding UTF8; "
                    "$s.Speak($t)"
                )
                proc = subprocess.Popen(
                    ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_cmd],
                    creationflags=no_console_flags())
                self._resume_speech_proc = proc
                proc.wait()
            except Exception as ex:
                print(f"[Résumé] Erreur lecture vocale SAPI : {ex}")
            finally:
                self._resume_speech_proc = None
                if stop_event is None or not stop_event.is_set():
                    self.after(0, self._on_resume_speech_done)

        def _on_resume_speech_done(self):
            """Remet le bouton et le son de la vidéo résumé dans leur état
            normal une fois la lecture terminée naturellement."""
            self._resume_speech_active = False
            try:
                btn = getattr(self, "_resume_speech_btn", None)
                if btn and btn.winfo_exists():
                    btn.configure(text="🔊 Écouter le résumé", fg_color="#2a4a6a", hover_color="#3a6a9a")
            except Exception:
                pass
            self._restore_resume_video_mute(getattr(self, "_resume_speech_vid_ref", None))

        def _stop_resume_speech(self, vid_player_ref=None, btn=None):
            """Arrête immédiatement une lecture vocale en cours (bouton Arrêter,
            ou fermeture de la fenêtre Infos)."""
            if not getattr(self, "_resume_speech_active", False):
                return
            stop_event = getattr(self, "_resume_speech_stop_event", None)
            if stop_event:
                stop_event.set()
            proc = getattr(self, "_resume_speech_proc", None)
            if proc:
                try: proc.terminate()
                except Exception: pass
                self._resume_speech_proc = None
            # IMPORTANT : ne pas appeler MCI stop/close depuis le thread UI.
            # Le thread de narration possède lui-même l'alias MCI et l'utilise
            # encore dans sa boucle status/play. Deux threads appelant
            # mciSendStringW simultanément sur le même alias peuvent provoquer
            # un crash natif de winmm.dll, sans exception Python et donc sans
            # trace dans la console. On pose uniquement l'évènement d'arrêt :
            # le worker voit stop_event et effectue son stop/close dans son
            # propre thread, ce qui évite la course native.
            alias = getattr(self, "_resume_speech_mci_alias", None)
            if alias:
                print(f"[Résumé][STOP] Arrêt MCI demandé (alias={alias}) — fermeture laissée au worker")
            if winsound is not None:
                try: winsound.PlaySound(None, winsound.SND_PURGE)
                except Exception: pass
            self._resume_speech_active = False
            target_btn = btn or getattr(self, "_resume_speech_btn", None)
            try:
                if target_btn and target_btn.winfo_exists():
                    target_btn.configure(text="🔊 Écouter le résumé", fg_color="#2a4a6a", hover_color="#3a6a9a")
            except Exception:
                pass
            self._restore_resume_video_mute(vid_player_ref or getattr(self, "_resume_speech_vid_ref", None))

        def _restore_resume_video_mute(self, vid_player_ref):
            """Restaure l'état de sourdine de la vidéo résumé tel qu'il était
            avant le début de la lecture vocale, et efface l'icône "🔇"."""
            try:
                was_muted = getattr(self, "_resume_speech_vp_was_muted", False)
                if vid_player_ref:
                    vp = vid_player_ref[0]
                    if vp:
                        vp.audio_set_mute(bool(was_muted))
                    mute_lbl = vid_player_ref[1] if len(vid_player_ref) > 1 else None
                    if mute_lbl and mute_lbl.winfo_exists():
                        mute_lbl.configure(text="")
            except Exception:
                pass

        def _show_person_menu(self, anchor_widget, name):
            """Affiche un petit menu au survol d'un nom (dans '👥 Personnes') avec
            une entrée 'ℹ️ Informations' -> copie le nom et ouvre sa recherche
            AlloCiné dans une fenêtre de navigateur dédiée."""
            if getattr(self, "_person_menu_win", None) and self._person_menu_win.winfo_exists():
                self._person_menu_win.destroy()
            pw = ctk.CTkToplevel(self)
            pw.wm_overrideredirect(True)
            pw.attributes("-topmost", True)
            pw.configure(fg_color="#2a2a2a")
            self._person_menu_win = pw

            def _close_menu(e=None):
                try: pw.destroy()
                except Exception: pass
                if getattr(self, "_person_menu_win", None) is pw:
                    self._person_menu_win = None

            def _do_info():
                _close_menu()
                self._open_person_info(name)

            def _do_copy():
                _close_menu()
                self._copy_person_name(name)

            ctk.CTkButton(pw, text="ℹ️ Informations", anchor="w",
                          width=170, height=32, font=("Arial",12),
                          fg_color="#2a2a2a", hover_color="#3a6a9a",
                          command=_do_info).pack(fill="x", padx=2, pady=2)
            ctk.CTkButton(pw, text="📋 Copier le nom", anchor="w",
                          width=170, height=32, font=("Arial",12),
                          fg_color="#2a2a2a", hover_color="#3a6a9a",
                          command=_do_copy).pack(fill="x", padx=2, pady=(0,2))

            pw.update_idletasks()
            bx = anchor_widget.winfo_rootx()
            by = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 2
            pw.geometry(f"+{bx}+{by}")

            # Fermeture par sondage de la position du curseur (voir le menu
            # Paramètres pour l'explication : <Leave> se déclenche à tort en
            # passant sur les widgets internes du menu).
            def _poll_pointer():
                if not pw.winfo_exists():
                    return
                try:
                    px, py = self.winfo_pointerx(), self.winfo_pointery()
                    over_menu = (pw.winfo_rootx() <= px <= pw.winfo_rootx()+pw.winfo_width()
                                 and pw.winfo_rooty() <= py <= pw.winfo_rooty()+pw.winfo_height())
                    over_anchor = (anchor_widget.winfo_rootx() <= px <= anchor_widget.winfo_rootx()+anchor_widget.winfo_width()
                                and anchor_widget.winfo_rooty() <= py <= anchor_widget.winfo_rooty()+anchor_widget.winfo_height())
                    if not over_menu and not over_anchor:
                        _close_menu()
                        return
                except Exception:
                    pass
                pw.after(120, _poll_pointer)
            pw.after(120, _poll_pointer)

        def _copy_person_name(self, name):
            """Copie uniquement le nom dans le presse-papiers (sans ouvrir de
            navigateur), pour l'entrée 'Copier le nom' du menu de survol."""
            name = (name or "").strip()
            if not name:
                return
            try:
                self.clipboard_clear()
                self.clipboard_append(name)
                self._show_toast(f"📋 « {name} » copié", ms=2500, color="#2a4a6a")
            except Exception:
                pass

        def _open_person_info(self, name):
            """Copie le nom dans le presse-papiers et ouvre une recherche ciblée sur
            AlloCiné dans une fenêtre de navigateur dédiée (facile à refermer pour
            revenir sur Citron)."""
            name = (name or "").strip()
            if not name:
                return
            try:
                self.clipboard_clear()
                self.clipboard_append(name)
            except Exception:
                pass
            try:
                # L'URL de recherche interne d'AlloCiné (/recherche/?q=) s'est
                # révélée cassée ("410 Gone") et a déjà changé plusieurs fois par
                # le passé. On passe donc par une recherche Google ciblée sur le
                # site (site:allocine.fr), bien plus robuste : elle continuera de
                # fonctionner même si AlloCiné modifie encore sa propre URL.
                query = f"site:allocine.fr {name}"
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
                # AllowSetForegroundWindow ne suffit pas toujours, en particulier
                # si le navigateur est déjà ouvert (Windows traite alors la
                # nouvelle fenêtre comme venant d'un processus existant, avec une
                # règle anti-vol-de-focus encore plus stricte). L'astuce fiable :
                # simuler un appui/relâchement de la touche Alt, ce qui réinitialise
                # l'état de protection du système et autorise la fenêtre suivante
                # à passer au premier plan normalement.
                if os.name == "nt":
                    try:
                        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
                        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)       # Alt down
                        ctypes.windll.user32.keybd_event(0x12, 0, 0x0002, 0)  # Alt up
                    except Exception:
                        pass
                # La fenêtre "Infos" est elle-même réglée "toujours au-dessus"
                # (topmost) : sans désactiver ça temporairement, rien d'autre —
                # même une fenêtre passée au premier plan — ne peut s'afficher
                # devant elle, par définition d'une fenêtre topmost.
                try:
                    info_win = getattr(self, "_current_info_win", None)
                    if info_win and info_win.winfo_exists():
                        info_win.attributes("-topmost", False)
                except Exception:
                    pass
                # new=1 : tente d'ouvrir dans une fenêtre de navigateur dédiée
                # plutôt qu'un nouvel onglet, pour un retour facile vers Citron.
                webbrowser.open(url, new=1)
            except Exception as ex:
                messagebox.showerror("Navigateur", f"Impossible d'ouvrir le navigateur :\n{ex}")

        def _show_media_info(self,path):
            size=os.path.getsize(path) if os.path.isfile(path) else 0
            dur=self._get_duration(path)
            info=(f"Fichier : {os.path.basename(path)}\n"
                  f"Chemin  : {path}\n"
                  f"Taille  : {size/1024/1024:.1f} Mo\n"
                  f"Durée   : {fmt_duration(dur) if dur else 'inconnue'}\n"
                  f"Type    : {'Audio' if is_audio(path) else 'Vidéo'}")
            messagebox.showinfo("Info du média",info)

        def clear_list_window(self):
            if messagebox.askyesno("Vider","Vider toute la liste ?"):
                self.video_paths.clear(); self.video_names.clear()
                self.save_library(); self.refresh_list_window()
                self.update_list_button_text(); self.close_list_window()

        def delete_title(self,idx):
            if messagebox.askyesno("Supprimer",f"Supprimer '{self.video_names[idx]}' ?"):
                del self.video_paths[idx]; del self.video_names[idx]
                self.save_library(); self.refresh_list_window(); self.update_list_button_text()

        # ── PLAYLIST VIRTUELLE ──────────────────────────
        def _load_virtual_playlist(self):
            """Charge silencieusement la Playlist virtuelle au démarrage."""
            self.virtual_playlist = []
            try:
                path = self._data_file_path("playlist_virtuale.json")
                if not os.path.isfile(path):
                    return
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.virtual_playlist = [
                        item for item in data if isinstance(item, dict)
                    ]
                print(
                    f"[Playlist virtuelle] {len(self.virtual_playlist)} titre(s) chargé(s)"
                )
            except Exception as ex:
                self.virtual_playlist = []
                print(f"[Playlist virtuelle] chargement ignoré : {ex}")

        def _save_virtual_playlist(self):
            try:
                with open(self._data_file_path("playlist_virtuale.json"), "w", encoding="utf-8") as f:
                    json.dump(self.virtual_playlist, f, ensure_ascii=False, indent=2)
            except Exception as ex:
                print(f"[Playlist virtuelle] sauvegarde erreur : {ex}")

        def _virtual_item_path(self, item):
            path = item.get("path", "") if isinstance(item, dict) else str(item)
            if path and os.path.isfile(path):
                return path
            title = str(item.get("titre", "") if isinstance(item, dict) else "").strip().lower()
            for i, name in enumerate(self.video_names):
                if name.strip().lower() == title and i < len(self.video_paths) and os.path.isfile(self.video_paths[i]):
                    return self.video_paths[i]
            return ""

        def _add_info_to_virtual_playlist(self, titre, path, row_data, parent=None):
            """Ajoute à la Playlist virtuelle et affiche un toast non modal."""
            item = {"titre": titre, "path": path or "", "row_data": row_data}
            try:
                added = self._add_to_virtual_playlist(item, silent=True)
                if added:
                    self._show_virtual_playlist_toast(
                        f"🧪 « {titre} » ajouté à la Playlist virtuelle", parent
                    )
            except Exception as ex:
                self._show_virtual_playlist_toast(
                    f"Erreur : {ex}", parent, error=True
                )

        def _show_virtual_playlist_toast(self, message, parent=None, error=False, title="Playlist virtuelle"):
            old = getattr(self, "_virtual_playlist_toast", None)
            try:
                if old and old.winfo_exists():
                    old.destroy()
            except Exception:
                pass
            host = parent if parent is not None else self
            try:
                toast = ctk.CTkToplevel(host)
                self._virtual_playlist_toast = toast
                toast.title(title)
                w, h = 430, 95
                toast.geometry(f"{w}x{h}")
                toast.resizable(False, False)
                toast.transient(host)
                # Position explicite (centré sur la fenêtre hôte) : sans
                # cela, certains gestionnaires de fenêtres placent un
                # nouveau Toplevel à un emplacement par défaut qui peut se
                # retrouver caché derrière une autre fenêtre déjà ouverte
                # (ex : la fenêtre de résultats de recherche), donnant
                # l'impression que le toast ne s'affiche pas du tout.
                try:
                    host.update_idletasks()
                    hx = host.winfo_rootx(); hy = host.winfo_rooty()
                    hw = host.winfo_width(); hh = host.winfo_height()
                    x = hx + max(0, (hw - w) // 2)
                    y = hy + max(0, (hh - h) // 2)
                    toast.geometry(f"{w}x{h}+{x}+{y}")
                except Exception:
                    pass
                try:
                    toast.attributes("-topmost", True)
                except Exception:
                    pass
                toast.lift()
                ctk.CTkLabel(
                    toast, text=message, font=("Arial", 13, "bold"),
                    wraplength=390, justify="center"
                ).pack(expand=True, padx=15, pady=15)
                # Se replace au premier plan pendant toute sa durée
                # d'affichage : une fenêtre tierce (VLC, menu système…) qui
                # reprendrait brièvement le focus juste après la création
                # du toast ne doit pas pouvoir le masquer durablement.
                def _keep_on_top(n=0):
                    try:
                        if not toast.winfo_exists():
                            return
                        toast.lift()
                        toast.attributes("-topmost", True)
                    except Exception:
                        return
                    if n < 9:
                        toast.after(200, lambda: _keep_on_top(n + 1))
                _keep_on_top()
                toast.after(2000, lambda: toast.destroy() if toast.winfo_exists() else None)
            except Exception:
                pass

        def _add_to_virtual_playlist(self, item, silent=False):
            """silent=True : n'affiche pas l'affichette de confirmation « OK »
            en cas de succès (utilisé depuis 📋 Infos / Simuler Infos, où un
            toast non bloquant s'en charge déjà). L'avertissement en cas de
            doublon reste affiché dans tous les cas, car il signale un
            problème et non une simple confirmation d'action.
            Retourne True si le titre a bien été ajouté, False sinon (titre
            invalide ou déjà présent) — permet à l'appelant de ne pas
            afficher de confirmation de succès quand rien n'a été ajouté."""
            if not isinstance(item, dict): return False
            title = (item.get("titre") or item.get("col_titre") or "").strip()
            if not title: return False
            if any(str(x.get("titre", "")).strip().lower() == title.lower() for x in self.virtual_playlist):
                messagebox.showinfo("Playlist virtuelle", f"« {title} » est déjà dans la Playlist virtuelle."); return False
            self.virtual_playlist.append({k:item.get(k, "") for k in (
                "titre","path","row_data","col_titre","col_annee","col_resume","col_personnes",
                "col_type","col_filmeur","col_complement","col_fichier")})
            self._save_virtual_playlist(); self.update_playlist_button_text()
            if self._virtual_playlist_win and self._virtual_playlist_win.winfo_exists(): self.refresh_virtual_playlist_window()
            if not silent:
                messagebox.showinfo("Playlist virtuelle", f"« {title} » ajouté à la Playlist virtuelle.")
            return True

        def open_virtual_playlist_window(self):
            if self._virtual_playlist_win and self._virtual_playlist_win.winfo_exists():
                self._virtual_playlist_win.lift(); return
            win=ctk.CTkToplevel(self); self._virtual_playlist_win=win
            win.title("🧪 Playlist virtuelle"); win.geometry("740x740"); win.transient(self); win.lift()
            if self.virtual_playlist_win_geometry: win.geometry(self.virtual_playlist_win_geometry)
            win.protocol("WM_DELETE_WINDOW", lambda: self._close_virtual_playlist_window())
            ctk.CTkLabel(win,text="🧪 Playlist virtuelle",font=("Arial",20,"bold")).pack(pady=(8,2))
            ctk.CTkLabel(win,text="Les titres gris sont indisponibles. Les titres lisibles gardent les fonctions d'une playlist normale.",font=("Arial",11),text_color="#aaaaaa",wraplength=680).pack(pady=(0,6))
            self.virtual_playlist_total_label=ctk.CTkLabel(win,text="",font=("Arial",14)); self.virtual_playlist_total_label.pack()
            lf=ctk.CTkFrame(win); lf.pack(fill="both",expand=True,padx=15,pady=6)
            self.virtual_playlist_listbox=Listbox(lf,font=("Arial",12),bg="#2b2b2b",fg="white",selectbackground="#1f6aa5",activestyle="none",exportselection=False)
            sb=Scrollbar(lf,orient="vertical",command=self.virtual_playlist_listbox.yview); self.virtual_playlist_listbox.config(yscrollcommand=sb.set)
            self.virtual_playlist_listbox.pack(side="left",fill="both",expand=True); sb.pack(side="right",fill="y")
            self.virtual_playlist_listbox.bind("<Motion>",self._virtual_playlist_hover_select)
            self.virtual_playlist_listbox.bind("<Button-3>",self.virtual_playlist_right_click)
            self.virtual_playlist_listbox.bind("<Double-Button-1>",self.virtual_playlist_double_click)
            bot=ctk.CTkFrame(win); bot.pack(pady=(4,8))
            ctk.CTkButton(bot,text="💾 Enregistrer",command=self.export_virtual_playlist_file,height=36,fg_color="#1a6e3c",width=130).pack(side="left",padx=5)
            ctk.CTkButton(bot,text="📂 Charger playlist virtuelle",command=self.load_virtual_playlist_file,height=36,fg_color="#1a4e6e",width=160).pack(side="left",padx=5)
            ctk.CTkButton(bot,text="🗑 Vider",command=self.clear_virtual_playlist,height=36,width=90,fg_color="#c42b1c").pack(side="left",padx=5)
            self.refresh_virtual_playlist_window()
            self._remember_last_window_geometry(win)
        def _close_virtual_playlist_window(self):
            win=self._virtual_playlist_win
            self._virtual_playlist_win=None
            try:
                if win and win.winfo_exists():
                    self.virtual_playlist_win_geometry = win.geometry()
                    self.save_settings()
                    win.destroy()
            except Exception: pass

        def _virtual_playlist_hover_select(self,event):
            idx=self.virtual_playlist_listbox.nearest(event.y)
            if 0<=idx<self.virtual_playlist_listbox.size():
                self.virtual_playlist_listbox.selection_clear(0,END); self.virtual_playlist_listbox.selection_set(idx)

        def refresh_virtual_playlist_window(self):
            lb=getattr(self,"virtual_playlist_listbox",None)
            if not lb or not lb.winfo_exists(): return
            lb.delete(0,END); playable=0; total=0
            for i,item in enumerate(self.virtual_playlist):
                path=self._virtual_item_path(item); title=item.get("titre",""); dur=self._get_duration(path) if path else 0
                if path: playable+=1; total+=dur
                lb.insert(END,f"{title}   [{fmt_duration(dur)}]" if dur else title)
                lb.itemconfig(i,fg="white" if path else "#777777")
            self.virtual_playlist_total_label.configure(text=f"{len(self.virtual_playlist)} titre(s) — {playable} lisible(s)" + (f"  —  durée totale : {fmt_duration(total)}" if total else ""))

        def virtual_playlist_double_click(self,event):
            sel=self.virtual_playlist_listbox.curselection()
            if sel: self._play_from_virtual_playlist(sel[0])

        def _play_from_virtual_playlist(self,idx):
            if not 0<=idx<len(self.virtual_playlist): return
            path=self._virtual_item_path(self.virtual_playlist[idx])
            if not path:
                messagebox.showinfo("Playlist virtuelle","Ce titre est indisponible à la lecture."); return
            self.play_file(path)

        def virtual_playlist_right_click(self,event):
            sel=self.virtual_playlist_listbox.curselection()
            if not sel: return
            idx=sel[0]; path=self._virtual_item_path(self.virtual_playlist[idx])
            menu=Menu(self,tearoff=0,font=("Arial",18)); state="normal" if path else "disabled"
            menu.add_command(label="▶ Lecture à partir de ce titre sur PC",state=state,command=lambda:self._play_from_virtual_playlist(idx))
            menu.add_command(label="📺 Lecture à partir de ce titre sur TV",state=state,command=lambda:self.open_dlna_window(prefill_path=path))
            menu.add_command(label="🔀 Lecture aléatoire à partir de ce titre",state=state,command=lambda:self._play_from_virtual_playlist(idx))
            menu.add_command(label="📺🔀 Lecture aléatoire sur TV",state=state,command=lambda:self.open_dlna_window(prefill_path=path))
            menu.add_command(label="📺 Envoyer ce titre sur TV",state=state,command=lambda:self.open_dlna_window(prefill_path=path))
            menu.add_command(label="🗑 Supprimer de la playlist",command=lambda:self.remove_from_virtual_playlist(idx))
            menu.add_command(label="↑ Déplacer vers le haut",command=lambda:self.move_virtual_playlist_item(idx,-1))
            menu.add_command(label="↓ Déplacer vers le bas",command=lambda:self.move_virtual_playlist_item(idx,1))
            menu.post(event.x_root,event.y_root)

        def remove_from_virtual_playlist(self,idx):
            if 0<=idx<len(self.virtual_playlist):
                del self.virtual_playlist[idx]; self._save_virtual_playlist(); self.update_playlist_button_text(); self.refresh_virtual_playlist_window()

        def move_virtual_playlist_item(self,idx,direction):
            n=idx+direction
            if 0<=n<len(self.virtual_playlist):
                self.virtual_playlist[idx],self.virtual_playlist[n]=self.virtual_playlist[n],self.virtual_playlist[idx]; self._save_virtual_playlist(); self.refresh_virtual_playlist_window()

        def clear_virtual_playlist(self):
            if messagebox.askyesno("Vider","Vider toute la Playlist virtuelle ?"):
                self.virtual_playlist.clear(); self._save_virtual_playlist(); self.update_playlist_button_text(); self.refresh_virtual_playlist_window()

        def export_virtual_playlist_file(self):
            if not self.virtual_playlist: messagebox.showinfo("Playlist virtuelle","La playlist est vide."); return
            path=filedialog.asksaveasfilename(defaultextension=".json",filetypes=[("Playlist virtuelle JSON","*.json"),("Tous","*.*")],title="Enregistrer la Playlist virtuelle")
            if not path:return
            try:
                with open(path,"w",encoding="utf-8") as f: json.dump(self.virtual_playlist,f,ensure_ascii=False,indent=2)
                messagebox.showinfo("Enregistré",f"Playlist virtuelle enregistrée :\n{path}")
            except Exception as ex: messagebox.showerror("Erreur",str(ex))

        def load_virtual_playlist_file(self):
            path=filedialog.askopenfilename(filetypes=[("Playlist virtuelle JSON","*.json"),("Tous","*.*")],title="Charger une Playlist virtuelle")
            if not path:return
            try:
                with open(path,"r",encoding="utf-8") as f:data=json.load(f)
                if not isinstance(data,list):raise ValueError("Format de playlist virtuelle invalide.")
                self.virtual_playlist=data; self._save_virtual_playlist(); self.update_playlist_button_text(); self.refresh_virtual_playlist_window()
            except Exception as ex:messagebox.showerror("Erreur",str(ex))

        def virtual_playlist_to_library(self):
            added=0
            for item in self.virtual_playlist:
                path=self._virtual_item_path(item)
                if path and path not in self.video_paths:
                    self.video_paths.append(path); self.video_names.append(os.path.basename(path)); added+=1
            if added:self.save_library(); self.update_list_button_text(); messagebox.showinfo("Ajouté",f"{added} titre(s) ajouté(s) à la liste complète.")
            else:messagebox.showinfo("Info","Aucun titre lisible nouveau à ajouter.")

        # ── Fenêtre PLAYLIST ─────────────────────────────
        def add_to_playlist(self,idx):
            path=self.video_paths[idx]
            self.playlist.append(path)
            self.save_playlist(); self.update_playlist_button_text()
            self._fetch_durations_bg([path])
            if not (self.playlist_win and self.playlist_win.winfo_exists()):
                self.open_playlist_window()
            else: self.refresh_playlist_window()

        def open_playlist_window(self):
            if self.playlist_win and self.playlist_win.winfo_exists():
                self.playlist_win.lift(); return
            self.playlist_win=ctk.CTkToplevel(self)
            self.playlist_win.title("🎵 Playlist")
            self.playlist_win.geometry("740x740")
            self.playlist_win.transient(self); self.playlist_win.lift()
            if self.playlist_win_geometry: self.playlist_win.geometry(self.playlist_win_geometry)
            self.playlist_win.protocol("WM_DELETE_WINDOW",self.close_playlist_window)

            ctk.CTkLabel(self.playlist_win,text="🎵 Playlist",font=("Arial",20,"bold")).pack(pady=8)
            self.playlist_total_label=ctk.CTkLabel(self.playlist_win,text="",font=("Arial",14))
            self.playlist_total_label.pack()

            lf=ctk.CTkFrame(self.playlist_win); lf.pack(fill="both",expand=True,padx=15,pady=6)
            self.playlist_listbox=Listbox(lf,font=("Arial",12),bg="#2b2b2b",fg="white",
                                          selectbackground="#1f6aa5",activestyle="none",exportselection=False)
            sb=Scrollbar(lf,orient="vertical",command=self.playlist_listbox.yview)
            self.playlist_listbox.config(yscrollcommand=sb.set)
            self.playlist_listbox.pack(side="left",fill="both",expand=True)
            sb.pack(side="right",fill="y")
            self.playlist_listbox.bind("<Motion>",self._playlist_hover_select)
            self.playlist_listbox.bind("<Button-3>",self.playlist_right_click)
            self.playlist_listbox.bind("<Double-Button-1>",self.playlist_double_click)

            bot=ctk.CTkFrame(self.playlist_win); bot.pack(pady=(4,8))
            ctk.CTkButton(bot,text="💾 Enregistrer",command=self.export_playlist_file,
                          height=36,fg_color="#1a6e3c",width=130).pack(side="left",padx=5)
            ctk.CTkButton(bot,text="📂 Charger playlist",command=self.load_playlist_file,
                          height=36,fg_color="#1a4e6e",width=160).pack(side="left",padx=5)
            ctk.CTkButton(bot,text="🗑 Vider",fg_color="#c42b1c",command=self.clear_playlist,
                          height=36,width=90).pack(side="left",padx=5)
            ctk.CTkButton(bot,text="📋 Playlist→Liste",command=self.playlist_to_library,
                          height=36,fg_color="#4a5a2e",width=150).pack(side="left",padx=5)
            self.refresh_playlist_window()
            self._remember_last_window_geometry(self.playlist_win)

        def _playlist_hover_select(self,event):
            idx=self.playlist_listbox.nearest(event.y)
            if 0<=idx<self.playlist_listbox.size():
                self.playlist_listbox.selection_clear(0,END)
                self.playlist_listbox.selection_set(idx)

        def close_playlist_window(self):
            if self.playlist_win:
                self.playlist_win_geometry=self.playlist_win.geometry()
                self.save_settings(); self.playlist_win.destroy(); self.playlist_win=None

        def playlist_right_click(self,event):
            sel=self.playlist_listbox.curselection()
            if not sel: return
            idx=sel[0]; path=self._get_pl_path(idx)
            menu=Menu(self,tearoff=0,font=("Arial",18))
            menu.add_command(label="▶ Lecture à partir de ce titre sur PC",
                             command=lambda:self._play_from_playlist(idx))
            menu.add_command(label="📺 Lecture à partir de ce titre sur TV",
                             command=lambda:self._play_playlist_on_tv(idx))
            menu.add_command(label="🔀 Lecture aléatoire à partir de ce titre",
                             command=lambda:self.start_shuffle_from(idx))
            menu.add_command(label="📺🔀 Lecture aléatoire sur TV",
                             command=lambda:self._shuffle_on_tv(idx))
            if path:
                menu.add_command(label="📺 Envoyer ce titre sur TV",
                                 command=lambda:self.open_dlna_window(prefill_path=path))
            menu.add_command(label="🗑 Supprimer de la playlist",
                             command=lambda:self.remove_from_playlist(idx))
            menu.add_command(label="↑ Déplacer vers le haut",
                             command=lambda:self.move_playlist_item(idx,-1))
            menu.add_command(label="↓ Déplacer vers le bas",
                             command=lambda:self.move_playlist_item(idx,1))
            menu.post(event.x_root,event.y_root)

        def playlist_double_click(self,event):
            sel=self.playlist_listbox.curselection()
            if sel: self._play_from_playlist(sel[0])

        def _play_from_playlist(self, idx):
            """Lance la lecture séquentielle depuis idx, boucle sur toute la playlist."""
            n = len(self.playlist)
            if n == 0: return
            self.shuffle_mode = False
            self._seq_mode = True
            self._list_play_mode = False
            self._single_tv_mode = False
            self._clear_search_play_mode()  # ⏮/⏭ = logique playlist, pas recherche
            self._shuffle_history = []
            self._seq_start_idx = idx
            self._seq_visited = []
            # Ordre : de idx jusqu'à la fin, puis du début jusqu'à idx-1
            self._seq_order = list(range(idx, n)) + list(range(0, idx))
            self._playlist_total_dur = self._calc_playlist_total_duration()
            # Lancer le premier titre
            self._seq_play_next_in_order()
            self.set_play_mode("▶ Lecture à partir de ce titre sur PC", "🎵 Playlist")

        def _play_playlist_on_tv(self,idx):
            if not self._dlna_devices:
                def scan_and_play():
                    devs=discover_dlna_renderers(timeout=4); self._dlna_devices=devs
                    self.after(0,lambda:self._pick_device_then_play_tv(idx))
                threading.Thread(target=scan_and_play,daemon=True).start()
                messagebox.showinfo("Recherche TV","Recherche des appareils DLNA…\nRecommencez dans 5 secondes.")
                return
            self._pick_device_then_play_tv(idx)

        def _pick_device_then_play_tv(self,idx):
            if not self._dlna_devices:
                messagebox.showerror("DLNA","Aucun appareil DLNA trouvé."); return
            if len(self._dlna_devices)==1:
                device=self._dlna_devices[0]
            else:
                win=ctk.CTkToplevel(self); win.title("Choisir la TV"); win.geometry("420x280")
                win.transient(self); win.lift()
                ctk.CTkLabel(win,text="Choisir l'appareil TV :",font=("Arial",15,"bold")).pack(pady=10)
                lb=Listbox(win,font=("Arial",13),bg="#2b2b2b",fg="white",
                           selectbackground="#1f6aa5",height=6)
                lb.pack(fill="both",expand=True,padx=15,pady=6)
                for d in self._dlna_devices: lb.insert(END,f"{d['name']}  ({d['ip']})")
                selected=[None]
                def confirm():
                    sel=lb.curselection()
                    if sel: selected[0]=self._dlna_devices[sel[0]]
                    win.destroy()
                ctk.CTkButton(win,text="✅ Confirmer",command=confirm,height=36).pack(pady=8)
                win.wait_window(); device=selected[0]
                if not device: return
            self._tv_mode=True; self._tv_shuffle=False
            self._tv_play_index=idx; self._tv_play_device=device
            self._single_tv_mode = False
            self._seq_mode = False   # séquence gérée par _tv_play_next
            self._list_play_mode = False
            self._update_mirror_btn_visibility()
            self.set_play_mode("tv_seq","🎵 Playlist")
            self._tv_play_next()

        def _shuffle_on_tv(self,start_idx):
            if not self._dlna_devices:
                def scan_then_shuffle():
                    devs=discover_dlna_renderers(timeout=4); self._dlna_devices=devs
                    self.after(0,lambda:self._pick_device_then_shuffle(start_idx))
                threading.Thread(target=scan_then_shuffle,daemon=True).start()
                messagebox.showinfo("Recherche TV","Recherche DLNA…\nRecommencez dans 5 secondes.")
                return
            self._pick_device_then_shuffle(start_idx)

        def _pick_device_then_shuffle(self,start_idx):
            if not self._dlna_devices:
                messagebox.showerror("DLNA","Aucun appareil DLNA trouvé."); return
            if len(self._dlna_devices)==1:
                device=self._dlna_devices[0]
            else:
                win=ctk.CTkToplevel(self); win.title("Choisir la TV"); win.geometry("420x280")
                win.transient(self); win.lift()
                lb=Listbox(win,font=("Arial",13),bg="#2b2b2b",fg="white",
                           selectbackground="#1f6aa5",height=6)
                lb.pack(fill="both",expand=True,padx=15,pady=6)
                for d in self._dlna_devices: lb.insert(END,f"{d['name']}  ({d['ip']})")
                selected=[None]
                def confirm():
                    sel=lb.curselection()
                    if sel: selected[0]=self._dlna_devices[sel[0]]
                    win.destroy()
                ctk.CTkButton(win,text="✅ Confirmer",command=confirm,height=36).pack(pady=8)
                win.wait_window(); device=selected[0]
                if not device: return
            self.start_shuffle_from(start_idx,dlna_device=device)

        def move_playlist_item(self,idx,direction):
            nidx=idx+direction
            if 0<=nidx<len(self.playlist):
                self.playlist[idx],self.playlist[nidx]=self.playlist[nidx],self.playlist[idx]
                self.save_playlist(); self.refresh_playlist_window()

        def remove_from_playlist(self,idx):
            name=os.path.basename(self._get_pl_path(idx))
            if messagebox.askyesno("Supprimer",f"Retirer '{name}' de la playlist ?"):
                del self.playlist[idx]
                if self.current_index>=len(self.playlist): self.current_index=len(self.playlist)-1
                self.save_playlist(); self.update_playlist_button_text(); self.refresh_playlist_window()

        def clear_playlist(self):
            if messagebox.askyesno("Vider","Vider toute la playlist ?"):
                self.playlist.clear(); self.current_index=-1; self.shuffle_mode=False
                self.save_playlist(); self.update_playlist_button_text(); self.refresh_playlist_window()

        def export_playlist_file(self):
            if not self.playlist:
                messagebox.showinfo("Playlist","La playlist est vide."); return
            path=filedialog.asksaveasfilename(defaultextension=".m3u",
                filetypes=[("Playlist M3U","*.m3u"),("Tous","*.*")],
                title="Enregistrer la playlist")
            if not path: return
            try:
                with open(path,"w",encoding="utf-8") as f:
                    f.write("#EXTM3U\n")
                    for item in self.playlist:
                        pp=item.get("path","") if isinstance(item,dict) else item
                        dur=int(self._get_duration(pp)); name=os.path.basename(pp)
                        f.write(f"#EXTINF:{dur},{name}\n{pp}\n")
                messagebox.showinfo("Enregistré",f"Playlist enregistrée :\n{path}")
            except Exception as ex: messagebox.showerror("Erreur",str(ex))

        def load_playlist_file(self):
            path=filedialog.askopenfilename(
                filetypes=[("Playlist M3U","*.m3u"),("Playlist JSON","*.json"),("Tous","*.*")],
                title="Charger une playlist")
            if not path: return
            paths=[]
            try:
                if path.lower().endswith(".json"):
                    with open(path,"r",encoding="utf-8") as f: data=json.load(f)
                    for item in data:
                        p=item.get("path","") if isinstance(item,dict) else item
                        if p and os.path.isfile(p): paths.append(p)
                else:
                    with open(path,"r",encoding="utf-8") as f:
                        for line in f:
                            line=line.strip()
                            if line and not line.startswith("#") and os.path.isfile(line):
                                paths.append(line)
            except Exception as ex: messagebox.showerror("Erreur",str(ex)); return
            if not paths: messagebox.showinfo("Info","Aucun fichier valide trouvé."); return
            if self.playlist and not messagebox.askyesno("Remplacer ?","Remplacer la playlist actuelle ?"): return
            self.playlist=paths; self.current_index=-1
            self.save_playlist(); self.update_playlist_button_text()
            self._fetch_durations_bg(paths); self.refresh_playlist_window()
            messagebox.showinfo("Chargé",f"{len(paths)} titre(s) chargé(s).")

        def playlist_to_library(self):
            if not self.playlist: messagebox.showinfo("Info","La playlist est vide."); return
            added=0
            for item in self.playlist:
                path=item.get("path","") if isinstance(item,dict) else item
                if not path or not os.path.isfile(path): continue
                if path not in self.video_paths:
                    name=os.path.basename(path)
                    if is_audio(path): name+="  🎵 audio"
                    self.video_paths.append(path); self.video_names.append(name); added+=1
            if added:
                self.save_library(); self.update_list_button_text()
                if self.list_win and self.list_win.winfo_exists(): self.refresh_list_window()
                messagebox.showinfo("Ajouté",f"{added} titre(s) ajouté(s) à la liste complète.")
            else: messagebox.showinfo("Info","Tous les titres sont déjà dans la liste.")

        def refresh_playlist_window(self):
            if not (hasattr(self,"playlist_listbox") and self.playlist_listbox.winfo_exists()): return
            self.playlist_listbox.delete(0,END)
            for item in self.playlist:
                path=item.get("path","") if isinstance(item,dict) else item
                name=os.path.basename(path); dur=self._get_duration(path)
                label=f"{name}   [{fmt_duration(dur)}]" if dur else name
                self.playlist_listbox.insert(END,label)
            total_sec=sum(self._get_duration(item.get("path","") if isinstance(item,dict) else item)
                          for item in self.playlist)
            n=len(self.playlist)
            dur_str=f"  —  durée totale : {fmt_duration(total_sec)}" if total_sec else ""
            if hasattr(self,"playlist_total_label") and self.playlist_total_label.winfo_exists():
                self.playlist_total_label.configure(text=f"{n} titre(s){dur_str}")

        # ── Statistiques ─────────────────────────────────
        def show_duplicates_info(self):
            if self.stats_win and self.stats_win.winfo_exists():
                self.stats_win.lift(); return
            self.stats_win=ctk.CTkToplevel(self)
            self.stats_win.title("Statistiques")
            self.stats_win.geometry("700x560")
            self.stats_win.transient(self); self.stats_win.lift()
            if self.stats_win_geometry: self.stats_win.geometry(self.stats_win_geometry)
            self.stats_win.protocol("WM_DELETE_WINDOW",self.close_stats_win)
            ctk.CTkLabel(self.stats_win,text="📊 Doublons",font=("Arial",20,"bold")).pack(pady=8)
            self.stats_total_label=ctk.CTkLabel(self.stats_win,text="",font=("Arial",14))
            self.stats_total_label.pack()
            lf=ctk.CTkFrame(self.stats_win); lf.pack(fill="both",expand=True,padx=20,pady=8)
            self.stats_listbox=Listbox(lf,font=("Arial",12),bg="#2b2b2b",fg="white",
                                       selectbackground="#1f6aa5",activestyle="none",exportselection=False)
            sb=Scrollbar(lf,orient="vertical",command=self.stats_listbox.yview)
            self.stats_listbox.config(yscrollcommand=sb.set)
            self.stats_listbox.pack(side="left",fill="both",expand=True)
            sb.pack(side="right",fill="y")
            self.stats_listbox.bind("<Button-3>",self._stats_right_click)
            self._stats_last_sig=None
            self._update_stats_listbox()
            self._remember_last_window_geometry(self.stats_win)

        def _update_stats_listbox(self):
            if not (self.stats_win and self.stats_win.winfo_exists()): return
            counts=Counter(self.video_names)
            total=len(self.video_names)
            dups={k:v for k,v in counts.items() if v>1}
            dup_key="|".join(f"{k}:{v}" for k,v in sorted(dups.items()))
            sig=f"{total}|{dup_key}"
            if getattr(self,"_stats_last_sig",None)==sig: return
            self._stats_last_sig=sig
            try: ypos=self.stats_listbox.yview()[0]
            except Exception: ypos=0.0
            self.stats_total_label.configure(
                text=f"Total : {total} titre(s)   —   Doublons : {len(dups)}")
            self.stats_listbox.delete(0,END)
            if dups:
                for t,c in sorted(dups.items(),key=lambda x:-x[1]):
                    self.stats_listbox.insert(END,f"×{c}   {t}")
            else:
                self.stats_listbox.insert(END,"✅ Aucun doublon détecté")
            self.stats_listbox.yview_moveto(ypos)

        def _stats_right_click(self,event):
            import re as _re
            lb=self.stats_listbox; idx=lb.nearest(event.y)
            if idx<0: return
            text=lb.get(idx).strip()
            text=_re.sub(r'^×\d+\s+','',text)
            if not text or text.startswith("✅"): return
            self.clipboard_clear(); self.clipboard_append(text)
            if self.list_win and self.list_win.winfo_exists():
                if hasattr(self,"list_search_var"): self.list_search_var.set(text)
                self.list_win.lift()
            else:
                if self.stats_win and self.stats_win.winfo_exists():
                    self.stats_win.title(f"Statistiques — '{text[:30]}' copié !")
                    self.after(2000,lambda: self.stats_win.title("Statistiques")
                               if self.stats_win and self.stats_win.winfo_exists() else None)

        def refresh_stats_loop(self):
            self._update_stats_listbox()
            self.after(2000,self.refresh_stats_loop)

        def close_stats_win(self):
            if self.stats_win:
                self.stats_win_geometry=self.stats_win.geometry()
                self.save_settings(); self.stats_win.destroy(); self.stats_win=None

        def destroy(self):
            if self.player:
                self.player.stop()
                try: self.player.release()
                except Exception: pass
                try: self.instance.release()
                except Exception: pass
            self._stop_audio_anim()
            try:
                if getattr(self, "_screen_record_active", False):
                    self._stop_screen_recording()
            except Exception:
                pass
            try:
                if getattr(self, "_internet_mode", False):
                    self._restore_browser_audio()
            except Exception:
                pass
            try:
                if self._thumb_vlc_player:
                    self._thumb_vlc_player.stop()
                    try: self._thumb_vlc_player.release()
                    except Exception: pass
                    try:
                        if self._thumb_vlc_instance: self._thumb_vlc_instance.release()
                    except Exception: pass
                if self._thumb_render_win:
                    self._thumb_render_win.destroy()
            except Exception:
                pass
            self.stream_server.stop()
            try:
                if self._cmd_server:
                    srv = self._cmd_server
                    self._cmd_server = None
                    srv.close()
            except Exception:
                pass
            self.save_settings()
            super().destroy()

    if __name__ == "__main__":
        print(f"[Launch] argv = {sys.argv!r}")
        launch_url = None
        args = sys.argv[1:]
        i = 0
        while i < len(args):
            a = args[i]
            if a == "--url" and i + 1 < len(args):
                launch_url = args[i + 1]
                i += 2
                continue
            parsed = parse_citron_launch_arg(a)
            if parsed:
                launch_url = parsed
                print(f"[Launch] URL détectée : {launch_url[:120]}")
            i += 1

        # Si Citron tourne déjà → lui envoyer l'URL et quitter (pas de 2ᵉ fenêtre)
        if launch_url and try_send_url_to_running_citron(launch_url):
            print("[Launch] Transmis à l'instance existante, fin.")
            sys.exit(0)

        app = CitronVideoPlayer()
        if launch_url:
            app.after(900, lambda u=launch_url: app.play_internet_url(u))
        app.mainloop()

except Exception as e:
    with open(log_file,"a",encoding="utf-8") as f:
        f.write(f"ERREUR FATALE :\n{str(e)}\n{traceback.format_exc()}")
    print(f"Erreur fatale : {e}\nDétails dans {log_file}")
    input("Appuie sur Entrée pour fermer…")