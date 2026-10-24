$ErrorActionPreference = 'Stop'
$CondaExe = 'D:\software\miniconda\Scripts\conda.exe'
(& $CondaExe shell.powershell hook) | Out-String | Invoke-Expression
conda activate gllm
if ($env:CONDA_DEFAULT_ENV -ne 'gllm') { throw "Expected active conda environment 'gllm', got '$env:CONDA_DEFAULT_ENV'" }
$PythonExe = (Get-Command python -ErrorAction Stop).Source
if ($PythonExe -ne 'D:\software\miniconda\envs\gllm\python.exe') { throw "Unexpected Python interpreter: $PythonExe" }
$env:PYTHONHASHSEED = '0'
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$LogRoot = Join-Path $PSScriptRoot 'runs\formal_isolated'
$DriverLog = Join-Path $LogRoot 'isolated_driver.log'
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$Loads = @(@('low', '50'), @('middle', '160'), @('high', '320'))
$Networks = @('nominal', 'crosslink_4x')
$Cells = @('canonical', 'partial', 'full')
$Seeds = @(0, 1, 2)
$Code = "import sys; from experiments.v3_path_crossover.run import execute; print(execute(sys.argv[1],sys.argv[2],sys.argv[3],int(sys.argv[4]),int(sys.argv[5]),'formal_isolated'),flush=True)"
Set-Location $ProjectRoot
foreach ($Seed in $Seeds) {
    foreach ($Load in $Loads) {
        foreach ($Network in $Networks) {
            foreach ($Cell in $Cells) {
                $Label = $Load[0]
                $Output = Join-Path $LogRoot "$Label\$Network\${Cell}_seed${Seed}.json"
                if (Test-Path -LiteralPath $Output) {
                    $Line = "SKIP existing $Label/$Network/$Cell/seed$Seed"
                    Add-Content -LiteralPath $DriverLog -Value $Line
                    Write-Output $Line
                    continue
                }
                $Line = "START $Label/$Network/$Cell/seed$Seed $(Get-Date -Format o)"
                Add-Content -LiteralPath $DriverLog -Value $Line
                Write-Output $Line
                & $PythonExe -X faulthandler -c $Code $Label $Network $Cell $Seed 1800
                $Exit = $LASTEXITCODE
                $Exists = Test-Path -LiteralPath $Output
                $Line = "END $Label/$Network/$Cell/seed$Seed exit=$Exit result_exists=$Exists $(Get-Date -Format o)"
                Add-Content -LiteralPath $DriverLog -Value $Line
                Write-Output $Line
                if (-not $Exists -or $Exit -ne 0) { exit 1 }
            }
        }
    }
}
& $PythonExe -m experiments.v3_path_crossover.validate
if ($LASTEXITCODE -ne 0) { throw 'Formal result validation failed; see validation.json' }
& $PythonExe -m experiments.v3_path_crossover.report
if ($LASTEXITCODE -ne 0) { throw 'Formal report generation failed' }
