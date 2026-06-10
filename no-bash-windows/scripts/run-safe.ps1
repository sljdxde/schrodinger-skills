param(
    [Parameter(Mandatory = $true)]
    [string]$Command
)

$ErrorActionPreference = "Continue"

Write-Host "=== Running Command ==="
Write-Host $Command
Write-Host ""

$start = Get-Date

try {
    Invoke-Expression $Command
    $exitCode = $LASTEXITCODE

    if ($null -eq $exitCode) {
        $exitCode = 0
    }
} catch {
    Write-Host ""
    Write-Host "=== PowerShell Exception ==="
    Write-Host $_.Exception.Message
    $exitCode = 1
}

$end = Get-Date
$duration = $end - $start

Write-Host ""
Write-Host "=== Result ==="
Write-Host "ExitCode: $exitCode"
Write-Host "Duration: $($duration.TotalSeconds)s"

if ($exitCode -ne 0) {
    Write-Host ""
    Write-Host "Command failed. Check whether this was caused by:"
    Write-Host "- Bash-only syntax"
    Write-Host "- Missing command"
    Write-Host "- Wrong path separator"
    Write-Host "- Environment variable syntax"
    Write-Host "- Execution policy"
    Write-Host "- Missing dependency"
}

exit $exitCode
