[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ApprovedPlanSha256
)

$ErrorActionPreference = 'Stop'
if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'This helper is for Windows only; Linux uses scripts.aws_release directly.'
}
$root = Split-Path -Parent $PSScriptRoot
$scratch = [IO.Path]::GetFullPath((Join-Path $root 'data/tmp'))
$temporary = Join-Path $scratch ('docker-ecr-auth-' + [guid]::NewGuid().ToString('N'))
$python = Join-Path $root '.venv/Scripts/python.exe'
$registry = '044854093109.dkr.ecr.ap-south-1.amazonaws.com'
$plugins = Join-Path $env:ProgramFiles 'Docker/cli-plugins'
$savedEnvironment = @{}
foreach ($name in @('DOCKER_CONFIG', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'TEMP', 'TMP', 'TMPDIR', 'SQLITE_TMPDIR')) {
    $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$previousLocation = Get-Location
$created = $false
try {
    Set-Location -LiteralPath $root
    $actualPlan = (Get-FileHash -LiteralPath 'docs/DEPLOYMENT_PLAN.md' -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualPlan -ne $ApprovedPlanSha256.ToLowerInvariant()) { throw 'Approved plan hash mismatch.' }
    if (-not (Test-Path -LiteralPath (Join-Path $plugins 'docker-buildx.exe'))) { throw 'Expected bundled Buildx plugin is unavailable.' }
    $endpoint = (& docker context inspect --format '{{ (index .Endpoints "docker").Host }}' | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $endpoint.StartsWith('npipe:')) { throw 'Expected a working local Windows named-pipe Docker context.' }
    New-Item -ItemType Directory -Path $temporary | Out-Null
    $created = $true
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    & icacls $temporary /inheritance:r /grant:r "$($identity):(OI)(CI)F" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot restrict temporary Docker authentication directory.' }
    $auth = @{}
    $auth[$registry] = @{}
    $configuration = @{auths = $auth; cliPluginsExtraDirs = @($plugins)} | ConvertTo-Json -Depth 5
    [IO.File]::WriteAllText((Join-Path $temporary 'config.json'), $configuration, [Text.UTF8Encoding]::new($false))
    $env:DOCKER_CONFIG = $temporary
    $env:DOCKER_HOST = $endpoint
    $env:DOCKER_CONTEXT = $null
    foreach ($name in @('TEMP', 'TMP', 'TMPDIR', 'SQLITE_TMPDIR')) {
        [Environment]::SetEnvironmentVariable($name, $scratch, 'Process')
    }
    & $python -m scripts.aws_release publish --approved-plan-sha256 $ApprovedPlanSha256
    if ($LASTEXITCODE -ne 0) { throw 'Publication failed; inspect registry/release state before retrying immutable tags.' }
}
finally {
    foreach ($name in $savedEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process')
    }
    Set-Location -LiteralPath $previousLocation.Path
    if ($created -and (Test-Path -LiteralPath $temporary)) {
        $resolved = (Resolve-Path -LiteralPath $temporary).Path
        if (-not $resolved.StartsWith($scratch + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
            ((Get-Item -LiteralPath $resolved).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Refusing unsafe temporary authentication cleanup.'
        }
        Remove-Item -LiteralPath $resolved -Recurse -Force
        Write-Output 'Temporary Docker authentication directory removed; normal configuration unchanged.'
    }
}
