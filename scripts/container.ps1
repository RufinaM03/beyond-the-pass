param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Stage', 'Validate', 'Build', 'Verify')]
    [string] $Command,
    [ValidateSet('release', 'fixture')]
    [string] $Mode = 'release',
    [string] $Context,
    [string] $Image = 'beyond-the-pass:local',
    [switch] $StorageConfirmed,
    [switch] $CachedOnly
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not $Context) { $Context = Join-Path $projectRoot "data/package/phase5-$Mode" }
$previousLocation = Get-Location
$settings = @{
    TEMP = (Join-Path $projectRoot 'data/tmp')
    TMP = (Join-Path $projectRoot 'data/tmp')
    TMPDIR = (Join-Path $projectRoot 'data/tmp')
    SQLITE_TMPDIR = (Join-Path $projectRoot 'data/tmp')
    OPENBLAS_NUM_THREADS = '1'
    OMP_NUM_THREADS = '1'
}
$previous = @{}

function Invoke-Checked {
    param([string] $Program, [string[]] $Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "$Program failed: $LASTEXITCODE" }
}

try {
    Set-Location -LiteralPath $projectRoot
    foreach ($name in $settings.Keys) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $settings[$name], 'Process')
    }
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    Invoke-Checked $pythonPath @('-c', 'import sys; assert sys.version_info[:2] == (3, 12), sys.version')
    if ($Command -in @('Build', 'Verify')) {
        $memory = Get-CimInstance Win32_OperatingSystem
        $minimum = if ($Command -eq 'Verify' -or $CachedOnly) { 1GB } else { 2GB }
        if ($memory.FreeVirtualMemory * 1KB -lt $minimum -or $memory.FreePhysicalMemory * 1KB -lt $minimum) {
            throw "Insufficient available Windows commit/RAM: $($minimum / 1GB) GiB required for this profile. Cold builds require 2 GiB; offline cached builds and 512 MiB smoke containers require 1 GiB. No settings are changed."
        }
        foreach ($drive in @('C', 'D')) {
            if ((Get-PSDrive $drive).Free -lt 5GB) { throw "Less than 5 GiB free on ${drive}:; do not build until storage is reviewed." }
        }
    }
    switch ($Command) {
        'Stage' { Invoke-Checked $pythonPath @('-m', 'scripts.package_release', 'stage', '--mode', $Mode, '--output', $Context) }
        'Validate' { Invoke-Checked $pythonPath @('-m', 'scripts.package_release', 'validate', '--mode', $Mode, '--context', $Context) }
        'Build' {
            if (-not $StorageConfirmed) { throw 'Confirm Docker Desktop storage and C:/D: free space first; then pass -StorageConfirmed. No settings are changed by this script.' }
            Invoke-Checked 'docker' @('info', '--format', '{{.OSType}} {{.Architecture}} {{.DockerRootDir}}')
            Get-PSDrive C,D | Format-Table Name,Used,Free
            Invoke-Checked $pythonPath @('-m', 'scripts.package_release', 'validate', '--mode', $Mode, '--context', $Context)
            $package = Get-Content (Join-Path $Context 'package-manifest.json') -Raw | ConvertFrom-Json
            $buildArguments = @('build', '--platform', 'linux/amd64', '--build-arg', "ARTIFACT_MODE=$Mode", '--build-arg', "ARTIFACT_VERSION=$($package.artifact_version)", '--build-arg', "CODE_VERSION=$($package.code_version)", '-t', $Image, $Context)
            if ($CachedOnly) { $buildArguments += '--network=none' }
            Invoke-Checked 'docker' $buildArguments
        }
        'Verify' { Invoke-Checked $pythonPath @('-m', 'scripts.container_check', '--mode', $Mode, '--context', $Context, '--image', $Image, '--output', "data/tmp/container-$Mode.json") }
    }
} finally {
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    Set-Location -LiteralPath $previousLocation
}
