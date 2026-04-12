. "$PSScriptRoot\common.ps1"

@("api", "worker", "beat") |
    ForEach-Object { Get-ServiceStatus -Name $_ } |
    Format-Table -AutoSize
