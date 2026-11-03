param(
    [Parameter(Mandatory = $true)][string]$OutputFile,
    [switch]$AllowMissing
)

$ErrorActionPreference = 'Stop'
if ((Split-Path -Leaf $OutputFile) -ne $OutputFile -or $OutputFile -notmatch '\.json$') {
    throw 'OutputFile must be a JSON filename in this evidence directory'
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$replayBase = Join-Path $PSScriptRoot 'milp_failure_replay'
$indexPath = Join-Path $replayBase 'index.json'
$formalIndexPath = Join-Path $PSScriptRoot 'milp/formal/index.json'
$outputPath = Join-Path $PSScriptRoot $OutputFile
if (Test-Path -LiteralPath $outputPath) { throw "Evidence snapshot already exists: $outputPath" }

function Get-Sha256([string]$path) {
    (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$indexSha = Get-Sha256 $indexPath
$index = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
$formalSha = Get-Sha256 $formalIndexPath
$formalIndex = Get-Content -LiteralPath $formalIndexPath -Raw | ConvertFrom-Json
$records = @()
foreach ($entry in $index.jobs.PSObject.Properties) {
    $state = $entry.Value
    if ($state.status -ne 'failed' -or $state.exit_code -ne 3221225477) { continue }
    $key = $entry.Name
    $formal = $formalIndex.jobs.PSObject.Properties[$key].Value
    if ($formal.status -ne 'failed') { throw "Formal key is no longer failed: $key" }
    $replayArtifact = Join-Path $root $state.source
    $formalArtifact = Join-Path $root $formal.source
    $workerLog = Join-Path (Join-Path $replayBase 'runs') (Join-Path $key 'worker.log')
    if ((Get-Sha256 $replayArtifact) -ne $state.artifact_sha256 -or
        (Get-Sha256 $formalArtifact) -ne $formal.artifact_sha256) {
        throw "Indexed artifact SHA mismatch: $key"
    }
    $start = [datetimeoffset]::Parse($state.started_at).LocalDateTime.AddSeconds(-60)
    $end = [datetimeoffset]::Parse($state.finished_at).LocalDateTime.AddSeconds(60)
    $matches = @(Get-WinEvent -FilterHashtable @{
        LogName = 'Application'; Id = 1000; StartTime = $start; EndTime = $end
    } -ErrorAction SilentlyContinue | Where-Object {
        $_.ProviderName -eq 'Application Error' -and
        $_.Properties.Count -ge 13 -and
        $_.Properties[0].Value -eq 'python.exe' -and
        $_.Properties[6].Value -eq 'c0000005' -and
        [int]$_.Properties[8].Value -eq [int]$state.pid
    })
    if ($matches.Count -gt 1 -or ($matches.Count -eq 0 -and -not $AllowMissing)) {
        throw "Expected one matching Windows event for $key; got $($matches.Count)"
    }
    $eventEvidence = if ($matches.Count -eq 1) {
        $event = $matches[0]
        [ordered]@{
            match_status = 'matched'; log = 'Application'; record_id = $event.RecordId
            provider = $event.ProviderName; event_id = $event.Id
            time_created = $event.TimeCreated.ToString('o')
            exception_code = $event.Properties[6].Value
            faulting_module = $event.Properties[3].Value
            faulting_application_path = $event.Properties[10].Value
            faulting_module_path = $event.Properties[11].Value
            report_id = $event.Properties[12].Value
        }
    } else {
        [ordered]@{
            match_status = 'not_found'; log = 'Application'; event_id = 1000
            searched_from = $start.ToString('o'); searched_until = $end.ToString('o')
            pid = $state.pid; exception_code = 'c0000005'
        }
    }
    $records += [ordered]@{
        key = $key
        replay = [ordered]@{
            pid = $state.pid; started_at = $state.started_at; finished_at = $state.finished_at
            exit_code = $state.exit_code; artifact = $state.source
            artifact_sha256 = $state.artifact_sha256
            worker_log = $workerLog.Substring($root.Length + 1).Replace('\', '/')
            worker_log_sha256 = Get-Sha256 $workerLog
        }
        formal = [ordered]@{
            pid = $formal.pid; exit_code = $formal.exit_code
            artifact = $formal.source; artifact_sha256 = $formal.artifact_sha256
        }
        windows_event = $eventEvidence
    }
}
if ((Get-Sha256 $indexPath) -ne $indexSha -or (Get-Sha256 $formalIndexPath) -ne $formalSha) {
    throw 'Index changed while collecting evidence; retry with a new output filename'
}
$snapshot = [ordered]@{
    recorded_at = (Get-Date).ToString('o')
    interpretation = 'Matched PID/time/exception events confirm the corresponding process crashes, not their root cause. Unmatched native exits retain worker and artifact evidence without a Windows event attribution. Replay and formal outcomes remain separate.'
    replay_index_status = $index.status
    replay_index_sha256 = $indexSha
    formal_index_sha256 = $formalSha
    native_failure_count = $records.Count
    event_matched_count = @($records | Where-Object { $_.windows_event.match_status -eq 'matched' }).Count
    event_unmatched_count = @($records | Where-Object { $_.windows_event.match_status -eq 'not_found' }).Count
    records = $records
}
$snapshot | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputPath -Encoding utf8
Write-Output "Saved $($records.Count) native exits ($($snapshot.event_matched_count) matched, $($snapshot.event_unmatched_count) unmatched) to $outputPath"
