param(
    [Parameter(Mandatory = $true)][string]$ServerHost,
    [Parameter(Mandatory = $true)][string]$IdentityFile,
    [string]$SshUser = "root",
    [int]$PostgresPort = 15433,
    [int]$RedisPort = 16380
)

$ErrorActionPreference = "Stop"
if (!(Test-Path -LiteralPath $IdentityFile)) {
    throw "SSH identity file not found."
}
foreach ($port in @($PostgresPort, $RedisPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Local tunnel port $port is already in use."
    }
}
Write-Output "Connecting to remote ToolDawn PostgreSQL and Redis. Keep this terminal open."
& ssh.exe -N -T `
    -o BatchMode=yes -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes `
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
    -i $IdentityFile `
    -L "127.0.0.1:${PostgresPort}:127.0.0.1:25432" `
    -L "127.0.0.1:${RedisPort}:127.0.0.1:26379" `
    "${SshUser}@${ServerHost}"
exit $LASTEXITCODE
