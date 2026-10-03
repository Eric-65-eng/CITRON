param(
    [Parameter(Mandatory = $true)][string]$Version,
    [Parameter(Mandatory = $true)][string]$Url,
    [string]$Notes = "",
    [Parameter(Mandatory = $true)][string]$Fichier,
    [Parameter(Mandatory = $true)][string]$Json
)

# Appelé par Publier_MAJ_Citron.bat. Les arguments arrivent ici déjà
# correctement délimités par PowerShell lui-même (via -File), donc plus
# besoin d'échapper quoi que ce soit à la main (contrairement à l'ancienne
# version qui construisait une commande -Command en une seule ligne,
# fragile dès qu'une URL contenait des caractères spéciaux comme "?" ou
# "=" — ex. un lien "Raw" de dépôt privé avec un jeton d'accès).

try {
    if (-not (Test-Path -LiteralPath $Fichier)) {
        Write-Host "[ERREUR] Fichier introuvable : $Fichier"
        exit 1
    }

    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $Fichier).Hash.ToLower()

    $obj = [ordered]@{
        version = $Version
        url     = $Url
        notes   = $Notes
        sha256  = $hash
    }

    $obj | ConvertTo-Json | Set-Content -LiteralPath $Json -Encoding UTF8

    Write-Host "SHA-256 : $hash"
    exit 0
} catch {
    Write-Host "[ERREUR] $($_.Exception.Message)"
    exit 1
}
