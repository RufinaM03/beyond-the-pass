param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Setup', 'Build', 'Serve', 'Test', 'Integration', 'BrowserTest')]
    [string] $Command,
    [ValidateRange(1024, 65535)]
    [int] $Port = 8000
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$previousLocation = Get-Location
$settings = @{
    TEMP = (Join-Path $projectRoot 'data/tmp')
    TMP = (Join-Path $projectRoot 'data/tmp')
    SQLITE_TMPDIR = (Join-Path $projectRoot 'data/tmp')
    PIP_CACHE_DIR = (Join-Path $projectRoot 'data/cache/pip')
    NPM_CONFIG_CACHE = (Join-Path $projectRoot 'data/cache/npm')
    NODE_COMPILE_CACHE = (Join-Path $projectRoot 'data/cache/node')
    OPENBLAS_NUM_THREADS = '1'
    OMP_NUM_THREADS = '1'
}
$previousEnvironment = @{}

function Invoke-CheckedPython {
    param([string[]] $Arguments)
    & $pythonPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed: $LASTEXITCODE" }
}

function Invoke-Frontend {
    param([string[]] $Arguments)
    Push-Location (Join-Path $projectRoot 'frontend')
    try {
        & npm @Arguments
        if ($LASTEXITCODE -ne 0) { throw "npm command failed: $LASTEXITCODE" }
    } finally { Pop-Location }
}

try {
    Set-Location -LiteralPath $projectRoot
    foreach ($name in $settings.Keys) {
        $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $settings[$name], 'Process')
    }
    New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PIP_CACHE_DIR, $env:NPM_CONFIG_CACHE, $env:NODE_COMPILE_CACHE | Out-Null
    Invoke-CheckedPython -Arguments @('-c', 'import sys; assert sys.version_info[:2] == (3, 12), sys.version')
    switch ($Command) {
        'Setup' {
            Invoke-CheckedPython -Arguments @('-m', 'pip', 'install', '--only-binary=:all:', '--index-url', 'https://pypi.org/simple', '-r', 'requirements-app.lock')
            Invoke-CheckedPython -Arguments @('-m', 'pip', 'check')
            Invoke-Frontend -Arguments @('ci', '--registry=https://registry.npmjs.org')
        }
        'Build' { Invoke-Frontend -Arguments @('run', 'build') }
        'Serve' { Invoke-CheckedPython -Arguments @('-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', "$Port") }
        'Test' {
            Invoke-CheckedPython -Arguments @('-m', 'unittest', 'discover', '-s', 'tests', '-v')
            Invoke-Frontend -Arguments @('test')
        }
        'Integration' { Invoke-CheckedPython -Arguments @('-m', 'scripts.check_app') }
        'BrowserTest' { Invoke-Frontend -Arguments @('run', 'test:browser') }
    }
} finally {
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], 'Process')
    }
    Set-Location -LiteralPath $previousLocation
}
