. "$PSScriptRoot\common.ps1"

$process = Start-ServiceProcess -Name "beat"
Write-Host "Beat running (PID $($process.Id))."
