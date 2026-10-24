$ErrorActionPreference = 'Stop'
$PythonExe = 'D:\software\miniconda\envs\gllm\python.exe'
$env:PYTHONHASHSEED = '0'
$RunRoot = 'experiments\v3_dynamic_pathspace\runs\formal_adaptive_v3'
$DriverLog = Join-Path $RunRoot 'isolated_driver.log'
$Jobs = @(
    @('C1_multi', 'static', 0),
    @('C1_multi', 'static', 1),
    @('C1_multi', 'static', 2),
    @('C1_multi', 'adaptive_link', 0),
    @('C1_multi', 'adaptive_link', 2)
)
$Code = "import sys; from experiments.v3_dynamic_pathspace.run import run_one; print(run_one(sys.argv[1], sys.argv[2], int(sys.argv[3]), 1800, 'formal_adaptive_v3'), flush=True)"
foreach ($Job in $Jobs) {
    $Condition = $Job[0]
    $Cell = $Job[1]
    $Seed = $Job[2]
    $Output = Join-Path $RunRoot "$Condition\${Cell}_seed${Seed}.json"
    if (Test-Path -LiteralPath $Output) {
        $Line = "SKIP existing $Condition $Cell seed=$Seed"
        Add-Content -LiteralPath $DriverLog -Value $Line
        Write-Output $Line
        continue
    }
    $Line = "START $Condition $Cell seed=$Seed $(Get-Date -Format o)"
    Add-Content -LiteralPath $DriverLog -Value $Line
    Write-Output $Line
    & $PythonExe -X faulthandler -c $Code $Condition $Cell $Seed
    $Exit = $LASTEXITCODE
    $Exists = Test-Path -LiteralPath $Output
    $Line = "END $Condition $Cell seed=$Seed exit=$Exit result_exists=$Exists $(Get-Date -Format o)"
    Add-Content -LiteralPath $DriverLog -Value $Line
    Write-Output $Line
    if (-not $Exists) { exit 1 }
    if ($Exit -ne 0) { exit $Exit }
}
