#Requires -Version 5.1
<#
.SYNOPSIS
    Dézipe les fichiers AmazonPhotos(*).zip et trie les photos par année sur le NAS.

.DESCRIPTION
    Pour chaque zip trouvé dans DownloadFolder :
      - Extrait les photos/vidéos dans un dossier temporaire
      - Lit la date EXIF (DateTimeOriginal) pour déterminer l'année
        (repli sur la date de modification si EXIF absent ou fichier vidéo)
      - Copie vers \\redmoon\photo\AAAA - Photo Iphone\
      - Si un fichier du même nom existe déjà, renomme avec un suffixe _1, _2, …
      - Nettoie le dossier temporaire après chaque zip

.PARAMETER DownloadFolder
    Dossier contenant les zips AmazonPhotos(*).zip.
    Défaut : $env:USERPROFILE\Downloads

.PARAMETER NasBase
    Racine sur le NAS où créer les dossiers par année.
    Défaut : \\redmoon\photo

.PARAMETER DryRun
    Simule toutes les opérations sans rien copier ni créer.

.EXAMPLE
    .\unzip_amazon_photos.ps1
    .\unzip_amazon_photos.ps1 -DryRun
    .\unzip_amazon_photos.ps1 -DownloadFolder "D:\Temp" -NasBase "\\redmoon\photo"
#>
param(
    [string] $DownloadFolder = "$env:USERPROFILE\Downloads",
    [string] $NasBase        = "\\redmoon\photo",
    [switch] $DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.IO.Compression.FileSystem
try { Add-Type -AssemblyName System.Drawing } catch {}

# ── Extensions reconnues ───────────────────────────────────────────────────────

$PHOTO_EXT = @('.jpg', '.jpeg', '.png', '.heic', '.bmp', '.tiff', '.tif', '.dng', '.raw', '.arw', '.cr2', '.cr3', '.nef')
$VIDEO_EXT = @('.mp4', '.mov', '.avi', '.mkv', '.m4v', '.3gp', '.wmv')
$ALL_EXT   = $PHOTO_EXT + $VIDEO_EXT

# ── Lecture de l'année EXIF ────────────────────────────────────────────────────

function Get-PhotoYear {
    param([string]$FilePath)

    $ext = [System.IO.Path]::GetExtension($FilePath).ToLower()

    # EXIF DateTimeOriginal (tag 36867) — uniquement pour les formats supportés par GDI+
    if ($ext -in @('.jpg', '.jpeg', '.tiff', '.tif')) {
        $img = $null
        try {
            $img  = [System.Drawing.Image]::FromFile($FilePath)
            $prop = $img.GetPropertyItem(36867)
            # Format EXIF : "AAAA:MM:JJ HH:MM:SS\0"
            $date = [System.Text.Encoding]::ASCII.GetString($prop.Value).TrimEnd([char]0)
            if ($date -match '^(\d{4}):') {
                return [int]$Matches[1]
            }
        } catch {
            # EXIF absent ou illisible → repli ci-dessous
        } finally {
            if ($null -ne $img) { $img.Dispose() }
        }
    }

    # Repli : date de modification du fichier (préservée par Amazon Photos dans le zip)
    return (Get-Item -LiteralPath $FilePath).LastWriteTime.Year
}

# ── Copie avec renommage si doublon ────────────────────────────────────────────

function Copy-PhotoSafe {
    param(
        [string]$Source,
        [string]$DestFolder,
        [switch]$DryRun
    )

    $name    = [System.IO.Path]::GetFileNameWithoutExtension($Source)
    $ext     = [System.IO.Path]::GetExtension($Source)
    $dest    = Join-Path $DestFolder "$name$ext"
    $counter = 1

    while (Test-Path -LiteralPath $dest) {
        $dest = Join-Path $DestFolder "${name}_${counter}${ext}"
        $counter++
    }

    $renamed = $counter -gt 1

    if (-not $DryRun) {
        Copy-Item -LiteralPath $Source -Destination $dest
    }

    return [PSCustomObject]@{
        DestName = [System.IO.Path]::GetFileName($dest)
        Renamed  = $renamed
    }
}

# ── Recherche des zips ─────────────────────────────────────────────────────────

if (-not (Test-Path $DownloadFolder)) {
    Write-Error "Dossier introuvable : $DownloadFolder"
    exit 1
}

$zips = @(Get-ChildItem -Path $DownloadFolder -Filter "AmazonPhotos(*).zip" -ErrorAction SilentlyContinue |
          Sort-Object Name)

Write-Host ""
Write-Host "==================================================="
if ($DryRun) {
    Write-Host "  MODE SIMULATION — aucune copie effectuée"
    Write-Host "---------------------------------------------------"
}
Write-Host "  Source  : $DownloadFolder"
Write-Host "  Dest    : $NasBase\AAAA - Photo Iphone\"
Write-Host "==================================================="

if ($zips.Count -eq 0) {
    Write-Host "  Aucun fichier AmazonPhotos(*).zip trouvé."
    Write-Host "==================================================="
    exit 0
}

Write-Host "  $($zips.Count) fichier(s) zip trouvé(s)"
Write-Host ""

$stats   = @{ copied = 0; renamed = 0; errors = 0 }
$tempRoot = Join-Path $env:TEMP "AmazonPhotos_$(Get-Date -Format 'yyyyMMddHHmmss')"

# ── Traitement zip par zip ────────────────────────────────────────────────────

foreach ($zip in $zips) {

    $sizeMo = [math]::Round($zip.Length / 1MB, 1)
    Write-Host "--- $($zip.Name) ($sizeMo Mo) ---"

    $tempDir = Join-Path $tempRoot $zip.BaseName

    # Extraction
    try {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
            [System.IO.Compression.ZipFile]::ExtractToDirectory($zip.FullName, $tempDir)
        } else {
            # En simulation : lire le contenu sans extraire
            $archive  = [System.IO.Compression.ZipFile]::OpenRead($zip.FullName)
            $allExts  = $ALL_EXT
            $entries  = @($archive.Entries | Where-Object {
                $allExts -contains [System.IO.Path]::GetExtension($_.Name).ToLower()
            })
            $archive.Dispose()
            $entryCount = $entries.Count
            Write-Host "  $entryCount fichiers dans l'archive (simulation, non extrait)"
            $stats.copied += $entryCount
            continue
        }
    } catch {
        Write-Warning "  Extraction échouée : $_"
        $stats.errors++
        if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue }
        continue
    }

    # Fichiers extraits
    $files = @(Get-ChildItem -Path $tempDir -Recurse -File |
               Where-Object { $ALL_EXT -contains $_.Extension.ToLower() })

    Write-Host "  $($files.Count) fichier(s) à classer"

    foreach ($file in $files) {

        # Année de la photo
        try {
            $year = Get-PhotoYear -FilePath $file.FullName
        } catch {
            Write-Warning "  Impossible de lire la date de $($file.Name) : $_"
            $stats.errors++
            continue
        }

        $destFolder = Join-Path $NasBase "$year - Photo Iphone"

        # Création du dossier si nécessaire
        if (-not (Test-Path $destFolder)) {
            Write-Host "  + Dossier créé : $year - Photo Iphone"
            New-Item -ItemType Directory -Path $destFolder -Force | Out-Null
        }

        # Copie
        try {
            $result = Copy-PhotoSafe -Source $file.FullName -DestFolder $destFolder
            $stats.copied++
            if ($result.Renamed) {
                Write-Host ("  [$year] {0,-40}  → renommé en {1}" -f $file.Name, $result.DestName)
                $stats.renamed++
            } else {
                Write-Host "  [$year] $($file.Name)"
            }
        } catch {
            Write-Warning "  Erreur copie $($file.Name) : $_"
            $stats.errors++
        }
    }

    # Nettoyage du dossier temporaire de ce zip
    Remove-Item $tempDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host ""
}

# Nettoyage du dossier temporaire racine
if (-not $DryRun -and (Test-Path $tempRoot)) {
    Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

# ── Résumé ─────────────────────────────────────────────────────────────────────

Write-Host "==================================================="
if ($DryRun) { Write-Host "  SIMULATION terminée (aucune copie effectuée)" }
else         { Write-Host "  Terminé !" }
Write-Host "  Copiées          : $($stats.copied)"
if ($stats.renamed -gt 0) {
Write-Host "  Renommées        : $($stats.renamed)  (doublon de nom)"
}
if ($stats.errors -gt 0) {
Write-Host "  Erreurs          : $($stats.errors)  (voir avertissements ci-dessus)"
}
Write-Host "==================================================="
