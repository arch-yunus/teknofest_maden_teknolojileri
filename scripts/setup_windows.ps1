# ==============================================================================
# DeepMine AI - Windows Geliştirme Ortamı Kurulum Betiği
# Sadece AI modelleri ve Python tabanlı analizler içindir.
# ==============================================================================

Write-Host "----------------------------------------------------" -ForegroundColor Green
Write-Host "⛏️ DeepMine AI (Windows) Setup Başlatılıyor..." -ForegroundColor Green
Write-Host "----------------------------------------------------"

# 1. Python Kontrolü
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python bulunamadı! Lütfen Python 3.10+ yükleyin."
    return
}

# 2. Virtual Environment Oluşturma
$venvPath = "venv"
if (!(Test-Path $venvPath)) {
    Write-Host "🐍 Sanal ortam oluşturuluyor: $venvPath" -ForegroundColor Cyan
    python -m venv $venvPath
} else {
    Write-Host "✅ Sanal ortam zaten mevcut." -ForegroundColor Yellow
}

# 3. Bağımlılıkların Kurulumu
Write-Host "📦 Bağımlılıklar kuruluyor..." -ForegroundColor Cyan
& ".\$venvPath\Scripts\pip" install --upgrade pip
if (Test-Path "requirements.txt") {
    & ".\$venvPath\Scripts\pip" install -r "requirements.txt"
} else {
    Write-Warning "requirements.txt bulunamadı."
}

# 4. Dizinlerin Oluşturulması
Write-Host "📂 Proje dizinleri oluşturuluyor..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "data", "models", "results", "logs" | Out-Null

Write-Host "----------------------------------------------------" -ForegroundColor Green
Write-Host "✅ Kurulum Başarıyla Tamamlandı!" -ForegroundColor Green
Write-Host "Sanal ortamı aktif etmek için: .\venv\Scripts\Activate.ps1"
Write-Host "----------------------------------------------------"
