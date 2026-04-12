. "$PSScriptRoot\common.ps1"

foreach ($name in @("beat", "worker", "api")) {
    Stop-ServiceProcess -Name $name
    Write-Host "Stopped $name."
}
