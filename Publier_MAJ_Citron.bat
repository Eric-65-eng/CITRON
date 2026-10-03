@echo off
chcp 65001 >nul
setlocal

REM ============================================================
REM   Publier_MAJ_Citron.bat
REM
REM   A placer dans le MEME dossier que Citron.py ET que
REM   Publier_MAJ_Citron.ps1 (les deux fichiers vont ensemble).
REM
REM   Calcule le SHA-256 de Citron.py et genere (ou remplace)
REM   citron_update.json a cote, pret a etre depose sur GitHub
REM   (avec Citron.py) pour que le mecanisme "Verifier les mises
REM   a jour" de Citron puisse le trouver et verifier le fichier.
REM
REM   A relancer a CHAQUE nouvelle version publiee.
REM ============================================================

set "ICI=%~dp0"
set "FICHIER=%ICI%Citron.py"
set "JSON=%ICI%citron_update.json"
set "SCRIPT_PS=%ICI%Publier_MAJ_Citron.ps1"

if not exist "%FICHIER%" (
    echo [ERREUR] Introuvable : %FICHIER%
    echo Place ce script dans le meme dossier que Citron.py.
    echo.
    pause
    exit /b 1
)

if not exist "%SCRIPT_PS%" (
    echo [ERREUR] Introuvable : %SCRIPT_PS%
    echo Publier_MAJ_Citron.ps1 doit etre dans le meme dossier que ce .bat.
    echo.
    pause
    exit /b 1
)

echo.
echo ===========================================================
echo    Publication d'une mise a jour de Citron
echo ===========================================================
echo.
echo Fichier a publier : %FICHIER%
echo.

set "VERSION="
set /p VERSION="Numero de la nouvelle version (ex: 9.8) : "
if "%VERSION%"=="" (
    echo.
    echo [ERREUR] Le numero de version est obligatoire.
    echo.
    pause
    exit /b 1
)

echo.
echo URL a laquelle Citron.py sera telechargeable une fois depose
echo sur GitHub. Exemple (fichier "brut" d'un depot GitHub PUBLIC) :
echo   https://raw.githubusercontent.com/TonCompte/citron/main/Citron.py
echo.
echo IMPORTANT : si ton depot est PRIVE, l'URL "Raw" contient un
echo "?token=..." TEMPORAIRE (il expire au bout de quelques jours) -
echo inutilisable ici. Rends le depot PUBLIC (Settings, tout en bas,
echo Danger Zone, Change visibility) pour obtenir une URL stable,
echo sans token.
echo.
set "URL="
set /p URL="URL de telechargement : "
if "%URL%"=="" (
    echo.
    echo [ERREUR] L'URL est obligatoire.
    echo.
    pause
    exit /b 1
)

echo.
echo Notes de version a afficher dans Citron (une ligne, vide = aucune) :
set "NOTES="
set /p NOTES="> "

echo.
echo Calcul du SHA-256 de Citron.py et ecriture de citron_update.json...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_PS%" ^
    -Version "%VERSION%" -Url "%URL%" -Notes "%NOTES%" ^
    -Fichier "%FICHIER%" -Json "%JSON%"

if errorlevel 1 (
    echo.
    echo [ERREUR] Le calcul ou l'ecriture a echoue - voir le message ci-dessus.
    echo.
    pause
    exit /b 1
)

echo.
echo ===========================================================
echo    Termine !
echo.
echo    citron_update.json a ete (re)genere ici :
echo    %JSON%
echo.
echo    Prochaine etape : deposer (ou remplacer) ces DEUX fichiers
echo    sur GitHub, exactement a l'URL indiquee ci-dessus pour
echo    Citron.py :
echo      - Citron.py
echo      - citron_update.json
echo ===========================================================
echo.
pause
