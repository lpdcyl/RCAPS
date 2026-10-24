param(
    [ValidateSet('smoke', 'development', 'formal')][string]$Phase = 'formal',
    [ValidateRange(1, 3)][int]$Workers = 3
)
$ErrorActionPreference = 'Stop'
(& 'D:\software\miniconda\Scripts\conda.exe' shell.powershell hook) | Out-String | Invoke-Expression
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm') { throw 'Expected active gllm environment' }
$PythonExe = (Get-Command python -ErrorAction Stop).Source
if ($PythonExe -ne 'D:\software\miniconda\envs\gllm\python.exe') { throw "Unexpected Python: $PythonExe" }
$env:PYTHONHASHSEED = '0'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& $PythonExe -X faulthandler -m experiments.v3_adaptive_space_cohort.run --phase $Phase --workers $Workers
if ($LASTEXITCODE -ne 0) { throw 'Matrix failed; inspect preserved index and logs' }
& $PythonExe -m experiments.v3_adaptive_space_cohort.report --phase $Phase
if ($LASTEXITCODE -ne 0) { throw 'Independent result reconstruction failed' }
