param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = "Stop"

Write-Host "=== Path Check ==="
Write-Host "Input: $Path"

try {
    $resolved = Resolve-Path $Path -ErrorAction Stop
    Write-Host "Resolved: $resolved"
    Write-Host "Exists: true"

    $item = Get-Item $resolved
    Write-Host "Type: $($item.GetType().Name)"
    Write-Host "FullName: $($item.FullName)"
} catch {
    Write-Host "Exists: false"
    Write-Host "Error: $($_.Exception.Message)"

    $parent = Split-Path $Path -Parent
    if ($parent -and (Test-Path $parent)) {
        Write-Host ""
        Write-Host "Parent exists. Nearby files:"
        Get-ChildItem $parent | Select-Object -First 30 | ForEach-Object {
            Write-Host $_.Name
        }
    }
}
