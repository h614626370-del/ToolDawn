param(
    [int]$WebPort = 3000,
    [int]$ApiPort = 8000
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$apiRoot = Join-Path $projectRoot "services\api"
$webRoot = Join-Path $projectRoot "apps\web"
$runtimeRoot = Join-Path $projectRoot ".runtime"
$pythonExe = Join-Path $apiRoot ".venv\Scripts\python.exe"
$nuxtEntry = Join-Path $webRoot "node_modules\nuxt\bin\nuxt.mjs"

if (!(Test-Path -LiteralPath $pythonExe) -or !(Test-Path -LiteralPath $nuxtEntry)) {
    throw "Install backend and frontend dependencies first. See README.md."
}
foreach ($port in @($WebPort, $ApiPort)) {
    if (Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. Choose another -WebPort or -ApiPort."
    }
}
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$nodeExe = (Get-Command node.exe).Source
$env:NUXT_API_BASE = "http://127.0.0.1:$ApiPort"
$apiProcess = Start-Process -FilePath $pythonExe `
    -ArgumentList @("-m", "uvicorn", "tooldawn.main:create_app", "--factory", "--host", "127.0.0.1", "--port", "$ApiPort") `
    -WorkingDirectory $apiRoot -WindowStyle Hidden -PassThru `
    -RedirectStandardOutput (Join-Path $runtimeRoot "api.out.log") `
    -RedirectStandardError (Join-Path $runtimeRoot "api.err.log")
try {
    $webProcess = Start-Process -FilePath $nodeExe `
        -ArgumentList @("`"$nuxtEntry`"", "dev", "--host", "127.0.0.1", "--port", "$WebPort") `
        -WorkingDirectory $webRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $runtimeRoot "web.out.log") `
        -RedirectStandardError (Join-Path $runtimeRoot "web.err.log")
} catch {
    Stop-Process -Id $apiProcess.Id -ErrorAction SilentlyContinue
    throw
}
Write-Output "Web: http://127.0.0.1:$WebPort"
Write-Output "API: http://127.0.0.1:$ApiPort/api/docs"
Write-Output "API PID: $($apiProcess.Id); Web PID: $($webProcess.Id)"
Write-Output "Logs: $runtimeRoot"
