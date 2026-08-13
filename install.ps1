# Usage: .\install.ps1 -Dist <dist-folder>
# Creates a directory junction in <dist-folder> for each skill under .\skills\.
# Skips any skill that already has an entry with the same name in the destination.
# Note: directory junctions do not require administrator privileges on Windows.
param(
    [Parameter(Mandatory)]
    [string]$Dist
)

# Resolve absolute paths so junctions point to stable locations
$SkillsDir = Join-Path $PSScriptRoot "skills"
$DistDir   = [System.IO.Path]::GetFullPath($Dist)

Write-Host "[install] Skills source : $SkillsDir"
Write-Host "[install] Destination   : $DistDir"

# Create the destination folder if it does not exist yet
if (-not (Test-Path $DistDir)) {
    New-Item -ItemType Directory -Path $DistDir | Out-Null
}

foreach ($skill in Get-ChildItem -Path $SkillsDir -Directory) {
    $link = Join-Path $DistDir $skill.Name

    if (Test-Path $link) {
        Write-Host "[skip]    $($skill.Name)  (already exists at $link)"
    } else {
        # Junction acts like a symlink for directories without requiring elevated privileges
        New-Item -ItemType Junction -Path $link -Target $skill.FullName | Out-Null
        Write-Host "[linked]  $($skill.Name)  ->  $link"
    }
}

Write-Host "[install] Done."
