# Usage: .\install.ps1 -Dist <dist-folder>
param(
    [Parameter(Mandatory)]
    [string]$Dist
)

$SkillsDir = Join-Path $PSScriptRoot "skills"
$DistDir   = [System.IO.Path]::GetFullPath($Dist)

Write-Host "[install] Skills source : $SkillsDir"
Write-Host "[install] Destination   : $DistDir"

if (-not (Test-Path $DistDir)) {
    New-Item -ItemType Directory -Path $DistDir | Out-Null
}

foreach ($skill in Get-ChildItem -Path $SkillsDir -Directory) {
    $link = Join-Path $DistDir $skill.Name

    if (Test-Path $link) {
        Write-Host "[skip]    $($skill.Name)  (already exists at $link)"
    } else {
        New-Item -ItemType Junction -Path $link -Target $skill.FullName | Out-Null
        Write-Host "[linked]  $($skill.Name)  ->  $link"
    }
}

Write-Host "[install] Done."
