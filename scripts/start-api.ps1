. "$PSScriptRoot\common.ps1"

$process = Start-ServiceProcess -Name "api"
Write-Host "API running (PID $($process.Id))."
Write-Host "Health URL: http://127.0.0.1:8000/api/v1/health"
