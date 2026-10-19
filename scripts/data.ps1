param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Setup', 'Discover', 'Inspect', 'CheckSources', 'FetchPilot', 'Documentation', 'Pilot', 'Sample', 'Test', 'FetchJanuary', 'ValidateJanuary', 'Fetch2024', 'Expand', 'Cohort', 'SetupModel', 'Audit', 'Model', 'Verify')]
    [string] $Command
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
$scratchPath = Join-Path $projectRoot 'data/tmp'
$cachePath = Join-Path $projectRoot 'data/cache/pip'
$previousLocation = Get-Location
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousCache = $env:PIP_CACHE_DIR
$previousSqliteTmp = $env:SQLITE_TMPDIR
$previousBlasThreads = $env:OPENBLAS_NUM_THREADS
$previousOmpThreads = $env:OMP_NUM_THREADS

function Invoke-ProjectPython {
    param([string[]] $Arguments)
    & $pythonPath @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python command failed with exit code $LASTEXITCODE" }
}

try {
    Set-Location -LiteralPath $projectRoot
    New-Item -ItemType Directory -Force -Path $scratchPath, $cachePath | Out-Null
    $env:TEMP = $scratchPath
    $env:TMP = $scratchPath
    $env:PIP_CACHE_DIR = $cachePath
    $env:SQLITE_TMPDIR = $scratchPath
    $env:OPENBLAS_NUM_THREADS = '1'
    $env:OMP_NUM_THREADS = '1'
    if ($Command -in @('Setup', 'SetupModel') -and -not (Test-Path -LiteralPath $pythonPath)) {
        & 'D:\Python\Python312\python.exe' -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 virtual environment creation failed' }
    }
    Invoke-ProjectPython -Arguments @('-c', 'import sys; assert sys.version_info[:2] == (3, 12), sys.version')
    switch ($Command) {
        'Setup' {
            Invoke-ProjectPython -Arguments @('-m', 'pip', 'install', '--only-binary=:all:', '-r', 'requirements-data.lock')
            Invoke-ProjectPython -Arguments @('-m', 'pip', 'check')
        }
        'Discover' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.sources', 'discover') }
        'Inspect' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.sources', 'inspect', '--match', '202[2-5].*\.zip$') }
        'CheckSources' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.sources', 'check-sources') }
        'Documentation' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.documentation') }
        'FetchPilot' {
            Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.sources', 'fetch', '--match', 'lookup|\.csv$|\.odt$')
            Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.sources', 'fetch', '--match', '^dft_test_(result|item)_202[23]\.zip$', '--max-bytes', '1300000000')
        }
        'Pilot' {
            Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.pilot', 'ingest', '--years', '2023', '--modulus', '100000', '--name', 'pilot2023')
            Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.pilot', 'report', '--name', 'pilot2023')
        }
        'Sample' {
            Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.pilot', 'ingest', '--years', '2022', '2023', '--modulus', '10000', '--name', 'sample2022-2023')
            Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.pilot', 'report', '--name', 'sample2022-2023')
        }
        'Test' { Invoke-ProjectPython -Arguments @('-m', 'unittest', 'discover', '-s', 'tests', '-v') }
        'FetchJanuary' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.expansion', 'fetch', '--months', '1') }
        'ValidateJanuary' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.expansion', 'gate') }
        'Fetch2024' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.expansion', 'fetch', '--months', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12') }
        'Expand' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.expansion', 'ingest', '--name', 'expanded2022-2024', '--modulus', '1000') }
        'Cohort' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.cohort', '--name', 'expanded2022-2024') }
        'SetupModel' {
            Invoke-ProjectPython -Arguments @('-m', 'pip', 'install', '--only-binary=:all:', '--index-url', 'https://pypi.org/simple', '-r', 'requirements-model.lock')
            Invoke-ProjectPython -Arguments @('-m', 'pip', 'check')
        }
        'Audit' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.evaluation') }
        'Model' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.modeling') }
        'Verify' { Invoke-ProjectPython -Arguments @('-u', '-m', 'pipeline.verification') }
    }
}
finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    $env:PIP_CACHE_DIR = $previousCache
    $env:SQLITE_TMPDIR = $previousSqliteTmp
    $env:OPENBLAS_NUM_THREADS = $previousBlasThreads
    $env:OMP_NUM_THREADS = $previousOmpThreads
    Set-Location -LiteralPath $previousLocation
}
