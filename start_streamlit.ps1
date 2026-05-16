$AppDir = if (Test-Path (Join-Path $PSScriptRoot "streamlit_app.py")) {
    $PSScriptRoot
} else {
    Join-Path $PSScriptRoot "newd2p"
}
$Activate = Join-Path $AppDir "venv\Scripts\Activate.ps1"

if (!(Test-Path $Activate)) {
    Write-Host "Could not find venv at: $Activate"
    Write-Host "Open the folder that contains the app, or recreate the venv."
    exit 1
}

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
& $Activate
Set-Location $AppDir
python -m streamlit run streamlit_app.py
