Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Ensure-Directory {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }

    return $Path
}

function Get-LogsDirectory {
    return Ensure-Directory -Path (Join-Path (Get-RepoRoot) "logs")
}

function Get-PidsDirectory {
    return Ensure-Directory -Path (Join-Path (Get-RepoRoot) ".claude\pids")
}

function Get-PidFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    return Join-Path (Get-PidsDirectory) "$Name.pid"
}

function Add-UvToPath {
    $uvBin = Join-Path $HOME ".local\bin"
    if ((Test-Path $uvBin) -and -not (($env:Path -split ";") -contains $uvBin)) {
        $env:Path = "$uvBin;$env:Path"
    }
}

function Get-UvExecutable {
    Add-UvToPath
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) {
        throw "uv is not installed or not on PATH. Install it first."
    }

    return $uv.Source
}

function Get-ServiceSpec {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("api", "worker", "beat")]
        [string]$Name
    )

    switch ($Name) {
        "api" {
            return @{
                Args = @(
                    "run", "--project", "backend",
                    "uvicorn", "app.main:app",
                    "--app-dir", "backend",
                    "--reload",
                    "--host", "0.0.0.0",
                    "--port", "8000"
                )
                Readiness = "http"
            }
        }
        "worker" {
            return @{
                Args = @(
                    "run", "--project", "backend",
                    "celery", "-A", "app.tasks.celery_app.celery_app",
                    "worker",
                    "--loglevel=info",
                    "--pool=solo"
                )
                Readiness = "process"
            }
        }
        "beat" {
            return @{
                Args = @(
                    "run", "--project", "backend",
                    "celery", "-A", "app.tasks.celery_app.celery_app",
                    "beat",
                    "--loglevel=info"
                )
                Readiness = "process"
            }
        }
    }
}

function Get-TrackedProcess {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("api", "worker", "beat")]
        [string]$Name
    )

    $pidFile = Get-PidFile -Name $Name
    if (-not (Test-Path $pidFile)) {
        return $null
    }

    $pidText = (Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
    if (-not $pidText) {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        return $null
    }

    try {
        return Get-Process -Id ([int]$pidText) -ErrorAction Stop
    }
    catch {
        Remove-Item -LiteralPath $pidFile -Force -ErrorAction SilentlyContinue
        return $null
    }
}

function Wait-ForApi {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSeconds = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri $Url -Method Get -TimeoutSec 2
            if ($response.status -eq "ok") {
                return $response
            }
        }
        catch {
            Start-Sleep -Seconds 1
        }
    }

    throw "Timed out waiting for API readiness at $Url."
}

function Wait-ForProcess {
    param(
        [Parameter(Mandatory = $true)]
        [int]$Pid,
        [int]$TimeoutSeconds = 5
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Get-Process -Id $Pid -ErrorAction SilentlyContinue) {
            return
        }

        Start-Sleep -Milliseconds 500
    }

    throw "Process $Pid exited before it became ready."
}

function Start-ServiceProcess {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("api", "worker", "beat")]
        [string]$Name
    )

    $existing = Get-TrackedProcess -Name $Name
    if ($existing) {
        return $existing
    }

    $uv = Get-UvExecutable
    $repoRoot = Get-RepoRoot
    $logsDir = Get-LogsDirectory
    $stdoutPath = Join-Path $logsDir "$Name.out.log"
    $stderrPath = Join-Path $logsDir "$Name.err.log"
    $spec = Get-ServiceSpec -Name $Name

    $process = Start-Process `
        -FilePath $uv `
        -ArgumentList $spec.Args `
        -WorkingDirectory $repoRoot `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru

    Set-Content -LiteralPath (Get-PidFile -Name $Name) -Value $process.Id

    try {
        if ($spec.Readiness -eq "http") {
            Wait-ForApi -Url "http://127.0.0.1:8000/api/v1/health" | Out-Null
        }
        else {
            Wait-ForProcess -Pid $process.Id | Out-Null
        }
    }
    catch {
        if (Get-Process -Id $process.Id -ErrorAction SilentlyContinue) {
            Stop-Process -Id $process.Id -Force
        }
        Remove-Item -LiteralPath (Get-PidFile -Name $Name) -Force -ErrorAction SilentlyContinue
        throw
    }

    return $process
}

function Stop-ServiceProcess {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("api", "worker", "beat")]
        [string]$Name
    )

    $pidFile = Get-PidFile -Name $Name
    $process = Get-TrackedProcess -Name $Name
    if ($process) {
        Stop-Process -Id $process.Id -Force
    }

    if (Test-Path $pidFile) {
        Remove-Item -LiteralPath $pidFile -Force
    }
}

function Get-ServiceStatus {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet("api", "worker", "beat")]
        [string]$Name
    )

    $process = Get-TrackedProcess -Name $Name
    $logsDir = Get-LogsDirectory

    [PSCustomObject]@{
        Service = $Name
        Running = [bool]$process
        PID = if ($process) { $process.Id } else { $null }
        Stdout = Join-Path $logsDir "$Name.out.log"
        Stderr = Join-Path $logsDir "$Name.err.log"
    }
}
