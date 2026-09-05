# Smoke test for the Windows bundle (NSIS .exe installer).
#
# Usage: powershell -File windows-smoke.ps1 <path-to-bundle-dir>
# The bundle dir is typically src-tauri\target\release\bundle and contains
# the `nsis` subfolder produced by `tauri build`.

param(
  [Parameter(Mandatory = $true)]
  [string]$BundleDir
)

$ErrorActionPreference = "Stop"
$nsisDir = Join-Path $BundleDir "nsis"
$setup = Get-ChildItem -Path $nsisDir -Filter "*-setup.exe" -ErrorAction SilentlyContinue | Select-Object -First 1

Write-Host "== Windows installer smoke test =="
Write-Host "Bundle dir: $BundleDir"

if (-not $setup) {
  Write-Host "FAIL: no *-setup.exe found under $nsisDir"
  exit 1
}
Write-Host "Found installer: $($setup.FullName)"
if ($setup.Length -eq 0) {
  Write-Host "FAIL: installer is empty"
  exit 1
}

Write-Host "Running silent per-user install ..."
$p = Start-Process -FilePath $setup.FullName -ArgumentList "/S" -Wait -PassThru -NoNewWindow
if ($p.ExitCode -ne 0) {
  Write-Host "FAIL: installer exited with code $($p.ExitCode)"
  exit 1
}

# Tauri NSIS (per-user) installs into LOCALAPPDATA by default.
$candidates = @(
  (Join-Path ${env:LOCALAPPDATA} "MCleaner"),
  (Join-Path ${env:LOCALAPPDATA} "Programs\MCleaner"),
  (Join-Path ${env:ProgramFiles} "MCleaner")
)
$installed = $null
foreach ($dir in $candidates) {
  if (Test-Path $dir) {
    $installed = Get-ChildItem -Path $dir -Filter "*.exe" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike "*uninstall*" -and $_.Name -notlike "*setup*" } | Select-Object -First 1
    if ($installed) { break }
  }
}
if (-not $installed) {
  Write-Host "FAIL: no installed app exe found in:"
  $candidates | ForEach-Object { Write-Host "  - $_" }
  exit 1
}
Write-Host "Installed exe: $($installed.FullName)"

Write-Host "Launching app for 8 seconds ..."
$p = Start-Process -FilePath $installed.FullName -PassThru
Start-Sleep -Seconds 8
if ($p.HasExited) {
  Write-Host "FAIL: app exited early with code $($p.ExitCode)"
  exit 1
}
Write-Host "OK: app stayed alive for 8s"
Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "== Windows smoke test passed =="
