param([ValidateSet('test','freeze','smoke','development','report')][string]$Phase='test', [string]$Revision='v1')
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
(& 'D:/software/miniconda/Scripts/conda.exe' shell.powershell hook) | Out-String | Invoke-Expression
conda activate gllm
$env:PYTHONHASHSEED='0'
if ($Phase -eq 'test') {
    python -X faulthandler -m unittest work3_control.test_control -v
} else {
    python -X faulthandler -m work3_control.run --revision $Revision --phase $Phase
}
if ($LASTEXITCODE -ne 0) { throw "Experiment failed, exit=$LASTEXITCODE; preserve artifacts." }
