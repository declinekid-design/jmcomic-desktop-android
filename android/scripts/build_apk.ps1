param(
    [string]$ToolchainRoot = $env:ANDROID_TOOLCHAIN_ROOT,
    [string]$BuildPython = $env:CHAQUOPY_BUILD_PYTHON,
    [string]$OutputApk = (
        Join-Path (
            Split-Path $PSScriptRoot -Parent
        ) '..\artifacts\JMComic-Android-1.0.0.apk'
    ),
    [switch]$SkipLint
)

$ErrorActionPreference = 'Stop'

if (-not $ToolchainRoot) {
    throw 'Set ANDROID_TOOLCHAIN_ROOT or pass -ToolchainRoot.'
}

$androidRoot = Split-Path $PSScriptRoot -Parent
$jdkRoot = Join-Path $ToolchainRoot 'jdk\17.0.16'
$sdkRoot = Join-Path $ToolchainRoot 'sdk'
$gradleWrapper = Join-Path $androidRoot 'gradlew.bat'
$apksigner = Join-Path $sdkRoot 'build-tools\35.0.0\apksigner.bat'

$required = @(
    (Join-Path $jdkRoot 'bin\java.exe'),
    (Join-Path $sdkRoot 'platforms\android-35\android.jar'),
    $gradleWrapper,
    $apksigner
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required build tool is missing: $path"
    }
}

if (-not $BuildPython) {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if (-not $pythonCommand) {
        throw 'Set CHAQUOPY_BUILD_PYTHON or pass -BuildPython.'
    }
    $BuildPython = $pythonCommand.Source
}

$env:JAVA_HOME = $jdkRoot
$env:ANDROID_HOME = $sdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot
$env:ANDROID_USER_HOME = Join-Path $ToolchainRoot 'user-home'
$env:GRADLE_USER_HOME = Join-Path $ToolchainRoot 'gradle-home'
$env:CHAQUOPY_BUILD_PYTHON = $BuildPython
$env:JAVA_TOOL_OPTIONS = "-Duser.home=$($env:ANDROID_USER_HOME)"
Remove-Item Env:ANDROID_PREFS_ROOT -ErrorAction SilentlyContinue

Push-Location $androidRoot
try {
    $tasks = @('assembleDebug')
    if (-not $SkipLint) {
        $tasks += 'lintDebug'
    }
    & $gradleWrapper @tasks --no-daemon
    if ($LASTEXITCODE -ne 0) {
        throw "Gradle build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

$builtApk = Join-Path $androidRoot 'build\app\outputs\apk\debug\app-debug.apk'
if (-not (Test-Path -LiteralPath $builtApk -PathType Leaf)) {
    throw "Gradle APK output is missing: $builtApk"
}

$outputDirectory = Split-Path $OutputApk -Parent
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
Copy-Item -LiteralPath $builtApk -Destination $OutputApk -Force

& $apksigner verify --verbose --print-certs $OutputApk
if ($LASTEXITCODE -ne 0) {
    throw "apksigner verify failed with exit code $LASTEXITCODE"
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputApk).Hash
$size = (Get-Item -LiteralPath $OutputApk).Length
Write-Output "APK=$OutputApk"
Write-Output "SIZE=$size"
Write-Output "SHA256=$hash"
