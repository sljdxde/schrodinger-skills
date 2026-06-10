$ErrorActionPreference = "Stop"

Write-Host "=== No Bash Windows Preflight ==="

Write-Host "`n[System]"
Write-Host "OS: $([System.Environment]::OSVersion.VersionString)"
Write-Host "PowerShell: $($PSVersionTable.PSVersion)"
Write-Host "PSEdition: $($PSVersionTable.PSEdition)"
Write-Host "Current Directory: $(Get-Location)"

Write-Host "`n[Execution Policy]"
try {
    Get-ExecutionPolicy -List
} catch {
    Write-Host "Unable to read execution policy: $($_.Exception.Message)"
}

Write-Host "`n[Commands]"
$commands = @(
    "git",
    "node",
    "npm",
    "pnpm",
    "yarn",
    "python",
    "py",
    "pip",
    "java",
    "mvn",
    "gradle",
    "go",
    "rustc",
    "cargo",
    "docker"
)

foreach ($cmd in $commands) {
    $found = Get-Command $cmd -ErrorAction SilentlyContinue
    if ($found) {
        Write-Host "$cmd => $($found.Source)"
    } else {
        Write-Host "$cmd => NOT FOUND"
    }
}

Write-Host "`n[Project Files]"
$files = @(
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "pom.xml",
    "build.gradle",
    "go.mod",
    "Cargo.toml",
    "Makefile",
    "README.md"
)

foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "FOUND: $file"
    }
}

Write-Host "`n[WSL Check]"
$wsl = Get-Command wsl -ErrorAction SilentlyContinue
if ($wsl) {
    Write-Host "WSL is available: $($wsl.Source)"
    Write-Host "This skill targets native Windows. WSL commands will not be used by default."
} else {
    Write-Host "WSL is NOT available. Using native Windows commands only."
}

Write-Host "`nPreflight complete."
