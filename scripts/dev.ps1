. "$PSScriptRoot\common.ps1"

foreach ($name in @("api", "worker", "beat")) {
    $process = Start-ServiceProcess -Name $name
    Write-Host "Started $name (PID $($process.Id))."
}

Get-ServiceStatus -Name "api"
Get-ServiceStatus -Name "worker"
Get-ServiceStatus -Name "beat" | Format-Table -AutoSize
