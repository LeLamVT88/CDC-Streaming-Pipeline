param(
    [switch]$WithCdc
)

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $ProjectRoot "docker/docker-compose.yml"
$CdcComposeFile = Join-Path $ProjectRoot "docker/docker-compose.cdc.yml"
$ComposeArgs = @("-f", $ComposeFile)
if ($WithCdc) {
    $ComposeArgs += @("-f", $CdcComposeFile)
}

function Invoke-Compose {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    docker compose @ComposeArgs @Args
    if ($LASTEXITCODE -ne 0) {
        docker-compose @ComposeArgs @Args
    }
}

Write-Host "S3 Lakehouse DWH - starting services" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot" -ForegroundColor Gray

Invoke-Compose up -d --build
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose failed"
}

Write-Host ""
Write-Host "Services:" -ForegroundColor Cyan
Invoke-Compose ps

Write-Host ""
Write-Host "URLs:" -ForegroundColor Yellow
Write-Host "  Airflow: http://localhost:8080 (admin/admin)"
if ($WithCdc) {
    Write-Host "  Kafka UI: http://localhost:8085"
    Write-Host "  phpMyAdmin: http://localhost:8082 (root/root)"
    Write-Host "  Schema Registry: http://localhost:8081"
}

Write-Host ""
Write-Host "Next:"
Write-Host "  .\.venv\Scripts\python.exe scripts\lakehouse.py --mode all"
Write-Host "  .\.venv\Scripts\python.exe scripts\inspect_lakehouse.py --validate"

