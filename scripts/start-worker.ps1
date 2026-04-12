. "$PSScriptRoot\common.ps1"

$process = Start-ServiceProcess -Name "worker"
Write-Host "Worker running (PID $($process.Id))."
