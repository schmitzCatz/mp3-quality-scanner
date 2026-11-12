$ErrorActionPreference = 'Stop'

function Invoke-Checked([string]$Command, [string[]]$Arguments) {
    Write-Host "`n> $Command $($Arguments -join ' ')" -ForegroundColor Cyan
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code $LASTEXITCODE : $Command"
    }
}

Invoke-Checked 'uv' @('sync', '--frozen')
Invoke-Checked 'uv' @('run', 'ruff', 'format', '--check', '.')
Invoke-Checked 'uv' @('run', 'ruff', 'check', '.')
Invoke-Checked 'uv' @('run', 'mypy')
Invoke-Checked 'uv' @('run', 'pytest')
Invoke-Checked 'uv' @('build')

Write-Host "`nRelease verification completed. Inspect dist/ before publishing." -ForegroundColor Green
