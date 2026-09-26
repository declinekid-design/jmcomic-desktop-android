param(
    [Parameter(Mandatory = $true)]
    [string]$Version
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.IO.Compression.FileSystem

$desktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $desktopDir
$appDir = Join-Path $projectRoot "dist\JMComicDesktop"
$outputDir = Join-Path $projectRoot "dist\updates"
$stagingDir = Join-Path $projectRoot "build\update-package-$Version"
$packagePath = Join-Path $outputDir "JMComicDesktop-$Version-win64.zip"

if (-not (Test-Path -LiteralPath (Join-Path $appDir "JMComicDesktop.exe"))) {
    throw "Main application was not found: $appDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $appDir "updater\JMComicDesktopUpdater.exe"))) {
    throw "Updater was not found in the portable application directory."
}
if (Test-Path -LiteralPath $stagingDir) {
    Remove-Item -LiteralPath $stagingDir -Recurse -Force
}
New-Item -ItemType Directory -Path $stagingDir -Force | Out-Null
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null

Get-ChildItem -LiteralPath $appDir -Force | Where-Object {
    $_.Name -notin @("data", "downloads", "updater")
} | Copy-Item -Destination $stagingDir -Recurse -Force

Copy-Item -LiteralPath (Join-Path $desktopDir "使用说明.txt") `
    -Destination (Join-Path $stagingDir "使用说明.txt") -Force
Copy-Item -LiteralPath (Join-Path $projectRoot "LICENSE") `
    -Destination (Join-Path $stagingDir "LICENSE.jmcomic.txt") -Force
$sourceFile = Join-Path $desktopDir "SOURCE-$Version.txt"
if (-not (Test-Path -LiteralPath $sourceFile)) {
    throw "Source description was not found: $sourceFile"
}
Copy-Item -LiteralPath $sourceFile `
    -Destination (Join-Path $stagingDir "SOURCE.txt") -Force

if (Test-Path -LiteralPath $packagePath) {
    Remove-Item -LiteralPath $packagePath -Force
}
[System.IO.Compression.ZipFile]::CreateFromDirectory(
    $stagingDir,
    $packagePath,
    [System.IO.Compression.CompressionLevel]::Optimal,
    $false
)
Remove-Item -LiteralPath $stagingDir -Recurse -Force

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $packagePath).Hash.ToLowerInvariant()
$size = (Get-Item -LiteralPath $packagePath).Length
$manifestPath = Join-Path $outputDir "JMComicDesktop-$Version-update.json"
$manifest = [ordered]@{
    version = $Version
    url = (Split-Path -Leaf $packagePath)
    sha256 = $hash
    size = $size
    notes = "JMComic Desktop $Version"
} | ConvertTo-Json -Depth 3
Set-Content -LiteralPath $manifestPath -Value $manifest -Encoding utf8

Write-Output "PACKAGE=$packagePath"
Write-Output "MANIFEST=$manifestPath"
Write-Output "SHA256=$hash"
Write-Output "SIZE=$size"
