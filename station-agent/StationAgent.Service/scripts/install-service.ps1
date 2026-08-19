param(
    [Parameter(Mandatory = $true)]
    [string]$PublishDirectory
)

$ErrorActionPreference = "Stop"

$serviceName = "GamingCenterStationAgent"
$displayName = "Gaming Center Station Agent"

$currentIdentity =
    [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal =
    [Security.Principal.WindowsPrincipal]::new(
        $currentIdentity
    )

if (
    -not $currentPrincipal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
) {
    throw "Run this script from an elevated PowerShell session."
}

$resolvedPublishDirectory =
    (Resolve-Path -LiteralPath $PublishDirectory).Path

$exePath = Join-Path `
    $resolvedPublishDirectory `
    "StationAgent.Service.exe"

if (-not (Test-Path $exePath)) {
    throw "StationAgent.Service.exe not found at $exePath"
}

$existingService = Get-Service `
    -Name $serviceName `
    -ErrorAction SilentlyContinue

if ($null -ne $existingService) {
    Write-Host "Removing existing service..."

    Stop-Service `
        -Name $serviceName `
        -Force `
        -ErrorAction SilentlyContinue

    sc.exe delete $serviceName

    if ($LASTEXITCODE -ne 0) {
        throw "Unable to delete the existing Windows service."
    }

    Start-Sleep -Seconds 2
}

Write-Host "Creating Station Agent service..."

sc.exe create `
    $serviceName `
    binPath= "`"$exePath`"" `
    start= auto `
    DisplayName= "`"$displayName`""

if ($LASTEXITCODE -ne 0) {
    throw "Unable to create Windows service."
}

sc.exe config `
    $serviceName `
    start= delayed-auto

if ($LASTEXITCODE -ne 0) {
    throw "Unable to configure delayed automatic start."
}

sc.exe description `
    $serviceName `
    "Gaming Center Management System station agent"

if ($LASTEXITCODE -ne 0) {
    throw "Unable to configure the service description."
}

sc.exe failure `
    $serviceName `
    reset= 86400 `
    actions= restart/5000/restart/15000/restart/30000

if ($LASTEXITCODE -ne 0) {
    throw "Unable to configure service recovery actions."
}

sc.exe failureflag `
    $serviceName `
    1

if ($LASTEXITCODE -ne 0) {
    throw "Unable to enable service recovery for non-crash failures."
}

sc.exe start `
    $serviceName

if ($LASTEXITCODE -ne 0) {
    throw "The service was created but could not be started."
}

Write-Host ""
Write-Host "Station Agent installed successfully."
Write-Host "Service: $serviceName"
Write-Host "Executable: $exePath"
