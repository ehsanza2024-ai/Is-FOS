$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
# No passwords in command arguments, source files, transcripts, or environment files.
function Install-WithWinget([string]$Id) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget not found. Install Python 3.11 and Microsoft Edge WebView2 Runtime manually, then rerun."
    }
    & winget install --id $Id --exact --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) { throw "Prerequisite install failed: $Id" }
}
$Python = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        $candidate = & py -3.11 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0) { $Python = [string]$candidate }
    } catch { $Python = $null }
}
if (-not $Python) {
    $candidate = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
    if (-not (Test-Path $candidate)) { Install-WithWinget 'Python.Python.3.11' }
    if (Test-Path $candidate) { $Python = $candidate }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $Python = [string](& py -3.11 -c "import sys; print(sys.executable)")
    }
}
if (-not $Python -or -not (Test-Path $Python)) { throw 'Python 3.11 not located. Reopen a terminal after installing Python 3.11.' }
& $Python -c "import sys; assert sys.version_info[:2] == (3,11), 'Python 3.11 required'"
if ($LASTEXITCODE -ne 0) { throw 'Use Python 3.11.' }
$WebView = Join-Path ${env:ProgramFiles(x86)} 'Microsoft\EdgeWebView\Application'
$UserWebView = Join-Path $env:LOCALAPPDATA 'Microsoft\EdgeWebView\Application'
if (-not (Test-Path $WebView) -and -not (Test-Path $UserWebView)) { Install-WithWinget 'Microsoft.EdgeWebView2Runtime' }
& $Python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
$Venv = Join-Path $Root '.venv\Scripts\python.exe'
& $Venv -m pip install -r requirements.lock.txt -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check internet access; data was preserved.' }
& $Venv -m scripts.setup_central
if ($LASTEXITCODE -ne 0) { throw 'First-run setup not completed. Use scripts.manage_user if users already exist.' }
$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'Mazandasht Central.lnk'))
$Shortcut.TargetPath = Join-Path $Root 'start.bat'
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = 'Mazandasht installed central entry + read-only dashboard'
$Shortcut.Save()
Write-Host 'Installed. Keep this entire folder in its current location; run the desktop shortcut.'
Write-Host 'No firewall port was opened. See docs/INSTALL_CENTRAL_FA.md for private-LAN port 8001 and HTTPS/VPN.'
