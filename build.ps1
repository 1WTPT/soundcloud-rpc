$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 (64-bit).' }
    & .\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & .\.venv\Scripts\python.exe -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
    & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name SoundCloudRPC --icon assets/app.ico --add-data 'assets/app.ico;assets' --add-data 'reader.js;.' --add-data 'app_config.json;.' --add-data 'THIRD_PARTY_NOTICES.txt;.' app.py
    if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
    Write-Host 'Ready: dist\SoundCloudRPC.exe'
} finally {
    Pop-Location
}
