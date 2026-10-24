$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $projectRoot "services\api\.env"
if (!(Test-Path -LiteralPath $target)) { throw "Configure remote connections first." }
$existing = [System.IO.File]::ReadAllText($target)
$lines = @()
if ($existing -notmatch '(?m)^TOOLDAWN_AUTH_SECRET=') {
    $secretBytes = [System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32)
    $lines += "TOOLDAWN_AUTH_SECRET=$([Convert]::ToHexString($secretBytes).ToLowerInvariant())"
}
if ($existing -notmatch '(?m)^TOOLDAWN_MAIL_MODE=') { $lines += "TOOLDAWN_MAIL_MODE=file" }
if ($lines.Count -gt 0) {
    [System.IO.File]::AppendAllText($target, "`n" + ($lines -join "`n") + "`n", [System.Text.UTF8Encoding]::new($false))
}
Write-Output "Authentication development configuration ready; existing secrets preserved."
