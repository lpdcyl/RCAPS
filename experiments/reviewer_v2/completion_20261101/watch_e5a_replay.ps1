# Local recovery guard for the frozen E5a failure replay. Run as the logged-in user.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$base = Join-Path $PSScriptRoot 'e5a_failure_replay'
$indexPath = Join-Path $base 'index.json'
$logPath = Join-Path $base 'watchdog.log'
$mutex = [System.Threading.Mutex]::new($false, 'Local\RCAPS_E5a_Replay_Watchdog')
if (-not $mutex.WaitOne(0)) { exit 0 }

function Write-Event([string]$message) {
    Add-Content -LiteralPath $logPath -Value ('{0} {1}' -f (Get-Date -Format 'o'), $message)
}

function Start-Retry([string]$snapshot, [bool]$resume) {
    $launcher = Join-Path $snapshot 'retry.cmd'
    $option = if ($resume) { ' --resume' } else { '' }
    @('@echo off', 'call D:\software\miniconda\condabin\conda.bat activate gllm',
      'if errorlevel 1 exit /b 1', 'cd /d D:\PythonProject\Helix-GREEN',
      ('python -u -m experiments.reviewer_v2.completion_20261101.retry_failed_replays' + $option)) |
        Set-Content -LiteralPath $launcher -Encoding ascii
    $started = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/c', $launcher) `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $snapshot 'controller.stdout.log') `
        -RedirectStandardError (Join-Path $snapshot 'controller.stderr.log') -PassThru
    Write-Event "Started bounded failed-key retry, launcher PID $($started.Id); snapshot $snapshot"
}

function Start-Milp([string]$snapshot, [bool]$resume) {
    $launcher = Join-Path $snapshot 'milp_replay.cmd'
    $option = if ($resume) { ' --resume' } else { '' }
    @('@echo off', 'call D:\software\miniconda\condabin\conda.bat activate gllm',
      'if errorlevel 1 exit /b 1', 'cd /d D:\PythonProject\Helix-GREEN',
      ('python -u -m experiments.reviewer_v2.completion_20261101.replay_milp_failed' + $option)) |
        Set-Content -LiteralPath $launcher -Encoding ascii
    $started = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/c', $launcher) `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $snapshot 'controller.stdout.log') `
        -RedirectStandardError (Join-Path $snapshot 'controller.stderr.log') -PassThru
    Write-Event "Started independent MILP failure replay, launcher PID $($started.Id); snapshot $snapshot"
    return $started.Id
}

function Watch-Milp {
    $milpBase = Join-Path $PSScriptRoot 'milp_failure_replay'
    $milpIndexPath = Join-Path $milpBase 'index.json'
    if (-not (Test-Path -LiteralPath $milpIndexPath)) {
        $marker = Join-Path $milpBase 'launch_once.json'
        if (Test-Path -LiteralPath $marker) { return }
        $prior = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'failed_replay_retry_v2/FINAL_AUDIT.json') -Raw | ConvertFrom-Json
        if (-not $prior.passed) { throw 'E5a/E6 retry audit did not pass' }
        $other = Get-CimInstance Win32_Process | Where-Object {
            $_.Name -match 'python' -and $_.CommandLine -match 'experiments\.reviewer_v2\.completion_20261101\.(replay_e5a_failed|replay_e6_failed|retry_failed_replays|replay_milp_failed)'
        }
        if (@($other).Count -gt 0) { return }
        $snapshot = Join-Path $milpBase ('launch_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
        New-Item -ItemType Directory -Path $snapshot | Out-Null
        @{ launched_at = (Get-Date).ToString('o'); state = 'start_attempted'; snapshot = $snapshot } |
            ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding utf8
        $milpLauncherPid = Start-Milp $snapshot $false
        @{ launched_at = (Get-Date).ToString('o'); state = 'started'; launcher_pid = $milpLauncherPid; snapshot = $snapshot } |
            ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding utf8
        return
    }
    $milp = Get-Content -LiteralPath $milpIndexPath -Raw | ConvertFrom-Json
    if ($milp.status -eq 'terminal') {
        $auditPath = Join-Path $milpBase 'FINAL_AUDIT.json'
        $marker = Join-Path $milpBase 'audit_invoked.json'
        if (-not (Test-Path -LiteralPath $auditPath)) {
            if (Test-Path -LiteralPath $marker) { return }
            @{ invoked_at = (Get-Date).ToString('o'); index_sha256 = (Get-FileHash -LiteralPath $milpIndexPath -Algorithm SHA256).Hash.ToLower() } |
                ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding utf8
            $command = 'call D:\software\miniconda\condabin\conda.bat activate gllm && cd /d D:\PythonProject\Helix-GREEN && python -m experiments.reviewer_v2.completion_20261101.audit_milp_failed'
            $output = & $env:ComSpec /d /c $command 2>&1
            $output | Add-Content -LiteralPath (Join-Path $milpBase 'audit_once.log')
            if ($LASTEXITCODE -ne 0) { throw "MILP replay audit failed with exit code $LASTEXITCODE" }
            Write-Event 'MILP failure replay audit completed once.'
        }
        $finalPath = Join-Path $PSScriptRoot 'FINAL_RECONCILIATION.json'
        $finalMarker = Join-Path $PSScriptRoot 'finalize_invoked.json'
        if ((Test-Path -LiteralPath $finalPath) -or (Test-Path -LiteralPath $finalMarker)) { return }
        @{ invoked_at = (Get-Date).ToString('o'); milp_audit_sha256 = (Get-FileHash -LiteralPath $auditPath -Algorithm SHA256).Hash.ToLower() } |
            ConvertTo-Json | Set-Content -LiteralPath $finalMarker -Encoding utf8
        $finalCommand = 'call D:\software\miniconda\condabin\conda.bat activate gllm && cd /d D:\PythonProject\Helix-GREEN && python -m experiments.reviewer_v2.completion_20261101.finalize_completion'
        $finalOutput = & $env:ComSpec /d /c $finalCommand 2>&1
        $finalOutput | Add-Content -LiteralPath (Join-Path $PSScriptRoot 'finalize_once.log')
        if ($LASTEXITCODE -ne 0) { throw "Completion finalization failed with exit code $LASTEXITCODE" }
        Write-Event 'Completion reconciliation and manual commands generated once.'
        return
    }
    if ($milp.status -ne 'running') { throw "Unexpected MILP replay status: $($milp.status)" }
    $processes = @(Get-CimInstance Win32_Process)
    $controller = @($processes | Where-Object {
        $_.ProcessId -eq $milp.controller_pid -and
        $_.CommandLine -match 'experiments\.reviewer_v2\.completion_20261101\.replay_milp_failed'
    })
    $workers = @($processes | Where-Object {
        $_.CommandLine -match 'experiments\.reviewer_v2\.completion_20261101\.replay_milp_failed --worker '
    })
    if ($controller.Count -gt 0 -or $workers.Count -gt 0) { return }
    foreach ($entry in $milp.jobs.PSObject.Properties) {
        if (-not $entry.Value.artifact_sha256) { continue }
        $artifact = Join-Path $root $entry.Value.source
        if ((Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLower() -ne $entry.Value.artifact_sha256) {
            throw "MILP replay artifact SHA mismatch: $($entry.Name)"
        }
    }
    $snapshot = Join-Path $milpBase ('pre_resume_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    New-Item -ItemType Directory -Path $snapshot | Out-Null
    Copy-Item -LiteralPath $milpIndexPath -Destination (Join-Path $snapshot 'original_index.json')
    Get-ChildItem -LiteralPath $milpBase -Recurse -File |
        Where-Object { -not $_.FullName.StartsWith($snapshot) } |
        ForEach-Object {
            [PSCustomObject]@{ path = $_.FullName; bytes = $_.Length;
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower() }
        } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $snapshot 'artifacts_sha256.json') -Encoding utf8
    Start-Milp $snapshot $true | Out-Null
}

function Watch-Retry {
    $retryBase = Join-Path $PSScriptRoot 'failed_replay_retry_v2'
    $retryIndexPath = Join-Path $retryBase 'index.json'
    if (-not (Test-Path -LiteralPath $retryIndexPath)) {
        $audit = Get-Content -LiteralPath (Join-Path $base 'FINAL_AUDIT.json') -Raw | ConvertFrom-Json
        if (-not $audit.passed) { throw 'E5a parent audit did not pass' }
        $other = Get-CimInstance Win32_Process | Where-Object {
            $_.CommandLine -match 'experiments\.reviewer_v2\.completion_20261101\.(replay_e5a_failed|replay_e6_failed|retry_failed_replays)'
        }
        if (@($other).Count -gt 0) { exit 0 }
        $snapshot = Join-Path $retryBase ('launch_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
        New-Item -ItemType Directory -Path $snapshot | Out-Null
        Start-Retry $snapshot $false
        return
    }
    $retry = Get-Content -LiteralPath $retryIndexPath -Raw | ConvertFrom-Json
    if ($retry.status -eq 'terminal') {
        $auditPath = Join-Path $retryBase 'FINAL_AUDIT.json'
        $marker = Join-Path $retryBase 'audit_invoked.json'
        if (-not (Test-Path -LiteralPath $auditPath)) {
            if (Test-Path -LiteralPath $marker) { return }
            @{ invoked_at = (Get-Date).ToString('o'); index_sha256 = (Get-FileHash -LiteralPath $retryIndexPath -Algorithm SHA256).Hash.ToLower() } |
                ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding utf8
            $command = 'call D:\software\miniconda\condabin\conda.bat activate gllm && cd /d D:\PythonProject\Helix-GREEN && python -m experiments.reviewer_v2.completion_20261101.audit_failed_replay_retry'
            $output = & $env:ComSpec /d /c $command 2>&1
            $output | Add-Content -LiteralPath (Join-Path $retryBase 'audit_once.log')
            if ($LASTEXITCODE -ne 0) { throw "Retry audit failed with exit code $LASTEXITCODE" }
            Write-Event 'Bounded failed-key retry audit completed once.'
        }
        Watch-Milp
        return
    }
    if ($retry.status -ne 'running') { throw "Unexpected retry status: $($retry.status)" }
    $processes = @(Get-CimInstance Win32_Process)
    $controller = @($processes | Where-Object {
        $_.ProcessId -eq $retry.controller_pid -and
        $_.CommandLine -match 'experiments\.reviewer_v2\.completion_20261101\.retry_failed_replays'
    })
    $workers = @($processes | Where-Object {
        $_.CommandLine -match 'experiments\.reviewer_v2\.completion_20261101\.retry_failed_replays --worker '
    })
    if ($controller.Count -gt 0 -or $workers.Count -gt 0) { return }
    foreach ($entry in $retry.jobs.PSObject.Properties) {
        if (-not $entry.Value.artifact_sha256) { continue }
        $artifact = Join-Path $root $entry.Value.source
        if ((Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLower() -ne $entry.Value.artifact_sha256) {
            throw "Retry artifact SHA mismatch: $($entry.Name)"
        }
    }
    $snapshot = Join-Path $retryBase ('pre_resume_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    New-Item -ItemType Directory -Path $snapshot | Out-Null
    Copy-Item -LiteralPath $retryIndexPath -Destination (Join-Path $snapshot 'original_index.json')
    Get-ChildItem -LiteralPath $retryBase -Recurse -File |
        Where-Object { -not $_.FullName.StartsWith($snapshot) } |
        ForEach-Object {
            [PSCustomObject]@{ path = $_.FullName; bytes = $_.Length;
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower() }
        } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $snapshot 'artifacts_sha256.json') -Encoding utf8
    $active = @($retry.jobs.PSObject.Properties | Where-Object { $_.Value.status -eq 'running' })
    if ($active.Count -gt 1) { throw 'More than one retry worker is marked running' }
    if ($active.Count -eq 1) {
        $key = $active[0].Name
        $stalePid = $active[0].Value.pid
        $occupant = Get-CimInstance Win32_Process -Filter "ProcessId=$stalePid"
        if ($occupant -and $occupant.CommandLine -notmatch
                'experiments\.reviewer_v2\.completion_20261101\.retry_failed_replays --worker ') {
            $manifest = Get-Content -LiteralPath (Join-Path $retryBase 'manifest.json') -Raw | ConvertFrom-Json
            $item = @($manifest.jobs | Where-Object { $_.key -eq $key })
            if ($item.Count -ne 1) { throw "Cannot identify stale retry worker job: $key" }
            $target = Join-Path (Join-Path $retryBase 'runs') $key
            $resultPath = Join-Path $target 'result.json'
            $failurePath = Join-Path $target 'failure.json'
            if (Test-Path -LiteralPath $resultPath) {
                $artifact = $resultPath
                $outcome = 'completed'
            } else {
                $artifact = $failurePath
                $outcome = 'failed'
                if (-not (Test-Path -LiteralPath $failurePath)) {
                    [ordered]@{ status = 'failed'; job = $item[0].job;
                        campaign = $item[0].campaign; retry_campaign = 'failed_replay_retry_v2';
                        classification = 'controller_interrupted_pid_reused';
                        parent_failure_sha256 = $item[0].parent_failure_sha256;
                        formal_failure_sha256 = $item[0].formal_failure_sha256;
                        finished_at = (Get-Date).ToUniversalTime().ToString('o') } |
                        ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $failurePath -Encoding utf8
                }
            }
            $state = $retry.jobs.PSObject.Properties[$key].Value
            $state.status = $outcome
            $state | Add-Member -NotePropertyName source -NotePropertyValue ($artifact.Substring($root.Length + 1).Replace('\', '/')) -Force
            $state | Add-Member -NotePropertyName artifact_sha256 -NotePropertyValue ((Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLower()) -Force
            $state | Add-Member -NotePropertyName finished_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString('o')) -Force
            $retry | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $retryIndexPath -Encoding utf8
            [ordered]@{ key = $key; stale_pid = $stalePid; occupant_command = $occupant.CommandLine;
                amended_index_sha256 = (Get-FileHash -LiteralPath $retryIndexPath -Algorithm SHA256).Hash.ToLower() } |
                ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $snapshot 'PID_REUSE_AMENDMENT.json') -Encoding utf8
            Write-Event "Classified interrupted retry key $key after unrelated PID reuse $stalePid."
        }
    }
    Start-Retry $snapshot $true
}

try {
    $index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
    if (@($index.jobs.PSObject.Properties).Count -ne 45) { throw 'Unexpected replay job count' }
    if ($index.status -eq 'terminal') {
        $audit = Join-Path $base 'FINAL_AUDIT.json'
        $marker = Join-Path $base 'audit_invoked.json'
        if (-not (Test-Path -LiteralPath $audit)) {
            if (Test-Path -LiteralPath $marker) { exit 0 }
            @{ invoked_at = (Get-Date).ToString('o'); index_sha256 = (Get-FileHash -LiteralPath $indexPath -Algorithm SHA256).Hash.ToLower() } |
                ConvertTo-Json | Set-Content -LiteralPath $marker -Encoding utf8
            $command = 'call D:\software\miniconda\condabin\conda.bat activate gllm && cd /d D:\PythonProject\Helix-GREEN && python -m experiments.reviewer_v2.completion_20261101.audit_e5a_failed'
            $output = & $env:ComSpec /d /c $command 2>&1
            $output | Add-Content -LiteralPath (Join-Path $base 'audit_once.log')
            if ($LASTEXITCODE -ne 0) { throw "E5a audit failed with exit code $LASTEXITCODE" }
            Write-Event 'E5a audit completed once.'
        }
        Watch-Retry
        exit 0
    }
    if ($index.status -ne 'running') { throw "Unexpected replay status: $($index.status)" }

    $processes = @(Get-CimInstance Win32_Process)
    $controller = @($processes | Where-Object {
        $_.ProcessId -eq $index.controller_pid -and
        $_.CommandLine -match 'experiments\.reviewer_v2\.completion_20261101\.replay_e5a_failed'
    })
    $workers = @($processes | Where-Object {
        $_.CommandLine -match 'experiments\.reviewer_v2\.completion_20261101\.replay_e5a_failed --worker '
    })
    if ($controller.Count -gt 0 -or $workers.Count -gt 0) { exit 0 }

    $active = @($index.jobs.PSObject.Properties | Where-Object { $_.Value.status -eq 'running' })
    if ($active.Count -gt 1) { throw 'More than one worker is marked running' }
    foreach ($entry in $index.jobs.PSObject.Properties) {
        if (-not $entry.Value.artifact_sha256) { continue }
        $artifact = Join-Path $root $entry.Value.source
        if (-not (Test-Path -LiteralPath $artifact)) { throw "Missing indexed artifact: $($entry.Name)" }
        $actual = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLower()
        if ($actual -ne $entry.Value.artifact_sha256) { throw "Indexed artifact SHA mismatch: $($entry.Name)" }
    }

    $snapshot = Join-Path $base ('pre_resume_' + (Get-Date -Format 'yyyyMMdd_HHmmss'))
    New-Item -ItemType Directory -Path $snapshot | Out-Null
    Copy-Item -LiteralPath $indexPath -Destination (Join-Path $snapshot 'original_index.json')
    Get-ChildItem -LiteralPath $base -Recurse -File |
        Where-Object { -not $_.FullName.StartsWith($snapshot) -and $_.Name -ne 'watchdog.log' } |
        ForEach-Object {
            [PSCustomObject]@{ path = $_.FullName; bytes = $_.Length;
                sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower() }
        } | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $snapshot 'artifacts_sha256.json') -Encoding utf8

    # The frozen resume script uses tasklist PID presence alone. If Windows reused
    # the dead worker's PID, preserve the old index and classify that window here.
    if ($active.Count -eq 1) {
        $key = $active[0].Name
        $stalePid = $active[0].Value.pid
        $occupant = Get-CimInstance Win32_Process -Filter "ProcessId=$stalePid"
        if ($occupant -and $occupant.CommandLine -notmatch
                'experiments\.reviewer_v2\.completion_20261101\.replay_e5a_failed --worker ') {
            $manifest = Get-Content -LiteralPath (Join-Path $base 'manifest.json') -Raw | ConvertFrom-Json
            $item = @($manifest.jobs | Where-Object { $_.key -eq $key })
            if ($item.Count -ne 1) { throw "Cannot identify stale worker job: $key" }
            $target = Join-Path (Join-Path $base 'runs') $key
            $resultPath = Join-Path $target 'result.json'
            $failurePath = Join-Path $target 'failure.json'
            if (Test-Path -LiteralPath $resultPath) {
                $artifact = $resultPath
                $outcome = 'completed'
            } else {
                $artifact = $failurePath
                $outcome = 'failed'
                if (-not (Test-Path -LiteralPath $failurePath)) {
                    [ordered]@{ status = 'failed'; job = $item[0].job; campaign = 'e5a';
                        classification = 'controller_interrupted_pid_reused';
                        original_failure_sha256 = $item[0].original_failure_sha256;
                        finished_at = (Get-Date).ToUniversalTime().ToString('o') } |
                        ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $failurePath -Encoding utf8
                }
            }
            $state = $index.jobs.PSObject.Properties[$key].Value
            $state.status = $outcome
            $state | Add-Member -NotePropertyName source -NotePropertyValue ($artifact.Substring($root.Length + 1).Replace('\', '/')) -Force
            $state | Add-Member -NotePropertyName artifact_sha256 -NotePropertyValue ((Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLower()) -Force
            $state | Add-Member -NotePropertyName finished_at -NotePropertyValue ((Get-Date).ToUniversalTime().ToString('o')) -Force
            [ordered]@{ key = $key; stale_pid = $stalePid; occupant_name = $occupant.Name;
                original_index_sha256 = (Get-FileHash -LiteralPath (Join-Path $snapshot 'original_index.json') -Algorithm SHA256).Hash.ToLower();
                artifact_sha256 = $state.artifact_sha256; outcome = $outcome } |
                ConvertTo-Json | Set-Content -LiteralPath (Join-Path $snapshot 'stale_pid_amendment.json') -Encoding utf8
            $index | ConvertTo-Json -Depth 30 | Set-Content -LiteralPath $indexPath -Encoding utf8
            Write-Event "Recorded stale worker PID $stalePid reused by $($occupant.Name) for $key."
        }
    }

    $launcher = Join-Path $snapshot 'resume.cmd'
    @('@echo off', 'call D:\software\miniconda\condabin\conda.bat activate gllm',
      'if errorlevel 1 exit /b 1', 'cd /d D:\PythonProject\Helix-GREEN',
      'python -u -m experiments.reviewer_v2.completion_20261101.replay_e5a_failed --resume') |
        Set-Content -LiteralPath $launcher -Encoding ascii
    $started = Start-Process -FilePath $env:ComSpec -ArgumentList @('/d', '/c', $launcher) `
        -WorkingDirectory $root -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $snapshot 'controller.stdout.log') `
        -RedirectStandardError (Join-Path $snapshot 'controller.stderr.log') -PassThru
    Write-Event "Restarted frozen E5a replay via launcher PID $($started.Id); snapshot $snapshot"
} catch {
    Write-Event "ERROR $($_.Exception.Message)"
    exit 1
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
