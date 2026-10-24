param(
    [Parameter(Mandatory = $true)][string]$ServerHost,
    [Parameter(Mandatory = $true)][string]$IdentityFile,
    [string]$SshUser = "root",
    [int]$PostgresPort = 25432,
    [int]$RedisPort = 26379
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $projectRoot "services\api\.env"
if (Test-Path -LiteralPath $target) {
    throw "API .env already exists. Update it deliberately instead of replacing credentials."
}
$remoteSecrets = @{}
foreach ($name in @("postgres_app_password", "postgres_test_password", "redis_password")) {
    $value = & ssh.exe -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=15 `
        -i $IdentityFile "${SshUser}@${ServerHost}" "cat /opt/tooldawn-infra/secrets/$name"
    if ($LASTEXITCODE -ne 0 -or "$value" -notmatch "^[a-f0-9]{64}$") {
        throw "Could not retrieve remote credentials."
    }
    $remoteSecrets[$name] = "$value"
}
$lines = @(
    "TOOLDAWN_ENVIRONMENT=development"
    "TOOLDAWN_CATALOG_BACKEND=postgres"
    "TOOLDAWN_DATABASE_URL=postgresql+asyncpg://tooldawn:$($remoteSecrets.postgres_app_password)@${ServerHost}:${PostgresPort}/tooldawn"
    "TOOLDAWN_TEST_DATABASE_URL=postgresql+asyncpg://tooldawn_test:$($remoteSecrets.postgres_test_password)@${ServerHost}:${PostgresPort}/tooldawn_test"
    "TOOLDAWN_REDIS_URL=redis://tooldawn:$($remoteSecrets.redis_password)@${ServerHost}:${RedisPort}/0"
)
[System.IO.File]::WriteAllLines($target, $lines, [System.Text.UTF8Encoding]::new($false))
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$acl = [System.Security.AccessControl.FileSecurity]::new()
$acl.SetAccessRuleProtection($true, $false)
$acl.SetOwner([System.Security.Principal.NTAccount]::new($identity))
$acl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new($identity, "FullControl", "Allow"))
Set-Acl -LiteralPath $target -AclObject $acl
$remoteSecrets.Clear()
Write-Output "Saved remote development connections to ignored API .env (current Windows user only)."
