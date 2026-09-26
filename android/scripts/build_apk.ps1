param(
    [string]$ToolchainRoot = $env:ANDROID_TOOLCHAIN_ROOT,
    [string]$OutputApk = (
        Join-Path (
            Split-Path $PSScriptRoot -Parent
        ) 'build\JMComicBrowser-1.0.0-debug.apk'
    )
)

$ErrorActionPreference = 'Stop'

if (-not $ToolchainRoot) {
    throw 'Set ANDROID_TOOLCHAIN_ROOT or pass -ToolchainRoot.'
}

$projectRoot = Split-Path $PSScriptRoot -Parent
$appRoot = Join-Path $projectRoot 'app'
$buildRoot = Join-Path $projectRoot 'build'
$signingRoot = Join-Path $projectRoot 'signing'

$jdkRoot = Join-Path $toolchainRoot 'jdk\17.0.16'
$sdkRoot = Join-Path $toolchainRoot 'sdk'
$androidJar = Join-Path $sdkRoot 'platforms\android-35\android.jar'
$buildTools = Join-Path $sdkRoot 'build-tools\35.0.0'
$lambdaStubs = Join-Path $buildTools 'core-lambda-stubs.jar'
$aapt2 = Join-Path $buildTools 'aapt2.exe'
$d8 = Join-Path $buildTools 'd8.bat'
$zipalign = Join-Path $buildTools 'zipalign.exe'
$apksigner = Join-Path $buildTools 'apksigner.bat'
$javaC = Join-Path $jdkRoot 'bin\javac.exe'
$jar = Join-Path $jdkRoot 'bin\jar.exe'
$keytool = Join-Path $jdkRoot 'bin\keytool.exe'

$required = @(
    $androidJar,
    $lambdaStubs,
    $aapt2,
    $d8,
    $zipalign,
    $apksigner,
    $javaC,
    $jar,
    $keytool
)
foreach ($path in $required) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required build tool is missing: $path"
    }
}

$resolvedBuild = [IO.Path]::GetFullPath($buildRoot)
$resolvedProject = [IO.Path]::GetFullPath($projectRoot) + [IO.Path]::DirectorySeparatorChar
if (-not $resolvedBuild.StartsWith(
    $resolvedProject,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Refusing to clean build directory outside project: $resolvedBuild"
}
$compiledDir = Join-Path $buildRoot 'compiled'
$generatedDir = Join-Path $buildRoot 'generated'
$classesDir = Join-Path $buildRoot 'classes'
$dexDir = Join-Path $buildRoot 'dex'
$signedDir = Join-Path $buildRoot 'signed'
New-Item -ItemType Directory -Force -Path @(
    $compiledDir,
    $generatedDir,
    $classesDir,
    $dexDir,
    $signedDir
) | Out-Null

$env:JAVA_HOME = $jdkRoot
$env:ANDROID_SDK_ROOT = $sdkRoot

$compiledResources = Join-Path $compiledDir 'resources.zip'
& $aapt2 compile `
    --dir (Join-Path $appRoot 'res') `
    -o $compiledResources
if ($LASTEXITCODE -ne 0) {
    throw "aapt2 compile failed with exit code $LASTEXITCODE"
}

$baseApk = Join-Path $buildRoot 'base.apk'
& $aapt2 link `
    -o $baseApk `
    -I $androidJar `
    --manifest (Join-Path $appRoot 'AndroidManifest.xml') `
    -R $compiledResources `
    --java $generatedDir `
    --auto-add-overlay `
    --min-sdk-version 26 `
    --target-sdk-version 35 `
    --version-code 1 `
    --version-name '1.0.0'
if ($LASTEXITCODE -ne 0) {
    throw "aapt2 link failed with exit code $LASTEXITCODE"
}

$javaSources = @(
    Get-ChildItem -LiteralPath (Join-Path $appRoot 'java') -Recurse -Filter '*.java'
    Get-ChildItem -LiteralPath $generatedDir -Recurse -Filter '*.java'
) | ForEach-Object { $_.FullName }

$javacLog = Join-Path $buildRoot 'javac.log'
& $javaC `
    -encoding UTF-8 `
    -source 8 `
    -target 8 `
    -classpath ($androidJar + ';' + $lambdaStubs) `
    -d $classesDir `
    $javaSources *> $javacLog
$javacExitCode = $LASTEXITCODE
if ($javacExitCode -ne 0) {
    Get-Content -LiteralPath $javacLog
    throw "javac failed with exit code $javacExitCode"
}

$classFiles = @(
    Get-ChildItem -LiteralPath $classesDir -Recurse -Filter '*.class'
) | ForEach-Object { $_.FullName }

& $d8 `
    --release `
    --lib $androidJar `
    --min-api 26 `
    --output $dexDir `
    $classFiles
if ($LASTEXITCODE -ne 0) {
    throw "d8 failed with exit code $LASTEXITCODE"
}

$unsignedApk = Join-Path $signedDir 'unsigned.apk'
Copy-Item -LiteralPath $baseApk -Destination $unsignedApk
& $jar uf $unsignedApk -C $dexDir 'classes.dex'
if ($LASTEXITCODE -ne 0) {
    throw "Adding classes.dex failed with exit code $LASTEXITCODE"
}

$alignedApk = Join-Path $signedDir 'aligned.apk'
& $zipalign -p -f 4 $unsignedApk $alignedApk
if ($LASTEXITCODE -ne 0) {
    throw "zipalign failed with exit code $LASTEXITCODE"
}

New-Item -ItemType Directory -Force -Path $signingRoot | Out-Null
$keystore = Join-Path $signingRoot 'debug-signing.keystore'
if (-not (Test-Path -LiteralPath $keystore -PathType Leaf)) {
    & $keytool `
        -genkeypair `
        -keystore $keystore `
        -storepass android `
        -keypass android `
        -alias androiddebugkey `
        -keyalg RSA `
        -keysize 2048 `
        -validity 10000 `
        -dname 'CN=Android Debug,O=Android,C=US' `
        -noprompt
    if ($LASTEXITCODE -ne 0) {
        throw "keytool failed with exit code $LASTEXITCODE"
    }
}

$outputDirectory = Split-Path $OutputApk -Parent
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null
& $apksigner sign `
    --ks $keystore `
    --ks-key-alias androiddebugkey `
    --ks-pass pass:android `
    --key-pass pass:android `
    --out $OutputApk `
    $alignedApk
if ($LASTEXITCODE -ne 0) {
    throw "apksigner failed with exit code $LASTEXITCODE"
}

& $apksigner verify --verbose --print-certs $OutputApk
if ($LASTEXITCODE -ne 0) {
    throw "apksigner verify failed with exit code $LASTEXITCODE"
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputApk).Hash
Write-Output "APK=$OutputApk"
Write-Output "SHA256=$hash"
