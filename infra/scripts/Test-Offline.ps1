#Requires -Version 7.0
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$env:TF_IN_AUTOMATION = '1'
$env:TF_INPUT = '0'
$env:CHECKPOINT_DISABLE = '1'

foreach ($tool in @('terraform', 'python')) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "Required offline-check tool is missing: $tool. No dependency was installed."
    }
}

function Invoke-Terraform {
    param([string]$Directory, [string[]]$Arguments)
    & terraform "-chdir=$Directory" @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Terraform $($Arguments[0]) failed in $Directory."
    }
}

& python -B (Join-Path $root 'tests/check_contracts.py') --structure
if ($LASTEXITCODE -ne 0) { throw 'Self-contained source/lifecycle contract checks failed.' }
& python -B -m unittest discover -s (Join-Path $root 'tests') -p 'test_*.py'
if ($LASTEXITCODE -ne 0) { throw 'Nonsecret adapter and readback unit tests failed.' }

Invoke-Terraform -Directory $root -Arguments @('fmt', '-check', '-recursive')
$roots = @($root) + @(Get-ChildItem (Join-Path $root 'examples') -Directory | ForEach-Object { $_.FullName })
foreach ($directory in $roots) {
    Invoke-Terraform -Directory $directory -Arguments @('init', '-backend=false', '-input=false', '-lockfile=readonly')
    Invoke-Terraform -Directory $directory -Arguments @('validate', '-no-color')
}

$lines = & terraform "-chdir=$root" test -no-color -verbose -json
$testExitCode = $LASTEXITCODE
if ($testExitCode -ne 0) {
    foreach ($line in $lines) {
        $message = $line | ConvertFrom-Json -AsHashtable -Depth 100
        if ($message.type -eq 'diagnostic') {
            Write-Host "$($message.diagnostic.summary): $($message.diagnostic.detail)"
        }
    }
    throw 'Provider-mocked Terraform regression tests failed.'
}
$lines | & python -B (Join-Path $root 'tests/check_contracts.py') --plans
if ($LASTEXITCODE -ne 0) { throw 'Mock plan semantic contract checks failed.' }

foreach ($path in Get-ChildItem $PSScriptRoot, (Join-Path $root 'tests') -Filter '*.ps1' -Recurse -File) {
    $tokens = $null
    $errors = $null
    $null = [System.Management.Automation.Language.Parser]::ParseFile($path.FullName, [ref]$tokens, [ref]$errors)
    if ($errors.Count) { throw "PowerShell parse failure: $($path.Name)" }
}
Write-Host 'Offline checks passed. No Azure deployment, inference, telemetry delivery or application acceptance is certified.'
