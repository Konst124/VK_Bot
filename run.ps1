# Start the bot in a virtual environment.
# If Python 3.14 is not available, uv downloads it automatically.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $BotArgs
)

$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

# Make Russian console output readable in Windows PowerShell 5.1.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
    # Encoding setup is best-effort only.
}
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Creating Python 3.14 environment via uv..."
    python -m pip install --user --quiet uv
    python -m uv venv --python 3.14 .venv
}

# A non-zero exit code of a native command must not stop the script here.
$ErrorActionPreference = "Continue"
& $venvPython -c "import vkbottle" 2>$null
$vkbottleInstalled = $LASTEXITCODE -eq 0
$ErrorActionPreference = "Stop"

if (-not $vkbottleInstalled) {
    Write-Host "Installing dependencies..."
    python -m pip install --user --quiet uv
    python -m uv pip install --python $venvPython -r requirements.txt
}

if (-not (Test-Path (Join-Path $PSScriptRoot ".env"))) {
    Copy-Item (Join-Path $PSScriptRoot ".env.example") (Join-Path $PSScriptRoot ".env")
    Write-Host "Created .env from .env.example. Fill in VK_TOKEN and run again."
    exit 1
}

# Native stderr output must not be turned into a terminating error.
$ErrorActionPreference = "Continue"
& $venvPython bot.py @BotArgs
exit $LASTEXITCODE
