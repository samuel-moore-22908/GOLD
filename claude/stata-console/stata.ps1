# Launcher. `.\claude\stata-console\stata.ps1` opens the console;
# `.\claude\stata-console\stata.ps1 foo.do` runs a do-file and returns a real
# exit code. Uses the repo virtualenv so pandas is present for the parquet path.
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)

$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$py = Join-Path $repo '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'py -3.12' }

if ($Args -and $Args[0] -like '*.do') {
    & $py (Join-Path $PSScriptRoot 'code\run_do.py') @Args
} else {
    & $py (Join-Path $PSScriptRoot 'code\stata_console.py') @Args
}
exit $LASTEXITCODE
