<#
.SYNOPSIS
    Gera ou verifica o hash SHA256 de um instalador do Ampliagro.
.DESCRIPTION
    Este script pode:
    - Gerar o hash SHA256 de um instalador .exe (para publicar na release)
    - Verificar o hash contra um valor esperado (para validação pelo usuário)
    
    O hash SHA256 é a única verificação gratuita de autenticidade do instalador,
    já que o Ampliagro não possui certificado de code signing pago.
.NOTES
    Requer: PowerShell 5.1+
    Uso:
        # Gerar hash para publicar na release
        .\verify-installer-hash.ps1 -Generate -Path .\Ampliagro.exe
        
        # Verificar hash contra um valor esperado
        .\verify-installer-hash.ps1 -Verify -Path .\Ampliagro.exe -ExpectedHash "abc123..."
#>

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("Generate", "Verify")]
    [string]$Action,
    
    [Parameter(Mandatory=$true)]
    [string]$Path,
    
    [Parameter(Mandatory=$false)]
    [string]$ExpectedHash
)

# ---------------------
# FUNÇÕES AUXILIARES
# ---------------------
function Write-Success { param([string]$msg) Write-Host "[+] $msg" -ForegroundColor Green }
function Write-Error { param([string]$msg) Write-Host "[x] $msg" -ForegroundColor Red }
function Write-Warn { param([string]$msg) Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Info { param([string]$msg) Write-Host "[*] $msg" -ForegroundColor Cyan }

# ---------------------
# VALIDAÇÕES INICIAIS
# ---------------------
if (-Not (Test-Path $Path)) {
    Write-Error "Arquivo não encontrado: $Path"
    exit 1
}

if ((Get-Item $Path).Extension -ne ".exe") {
    Write-Error "O arquivo deve ser um .exe: $Path"
    exit 1
}

# ---------------------
# GERAÇÃO DE HASH
# ---------------------
if ($Action -eq "Generate") {
    Write-Info "Calculando SHA256 de: $Path"
    $hash = Get-FileHash -Path $Path -Algorithm SHA256
    
    Write-Success "Hash SHA256 gerado:"
    Write-Host "  $($hash.Hash)" -ForegroundColor White
    Write-Host ""
    Write-Info "Tamanho do arquivo: $([Math]::Round((Get-Item $Path).Length / 1MB, 2)) MB"
    Write-Host ""
    Write-Info "Para publicar na release do GitHub:"
    Write-Host "  1. Acesse: https://github.com/luck-of-luck/Ampliagro-releases/releases/new"
    Write-Host "  2. Faça upload do .exe"
    Write-Host "  3. No campo 'Description', adicione:"
    Write-Host "     SHA256: $($hash.Hash)"
    Write-Host ""
    Write-Info "Para usar em PowerShell:"
    Write-Host "  Get-FileHash $Path -Algorithm SHA256"
    Write-Host ""
    
    exit 0
}

# ---------------------
# VERIFICAÇÃO DE HASH
# ---------------------
if ($Action -eq "Verify") {
    if (-Not $ExpectedHash) {
        Write-Error "Parâmetro -ExpectedHash é obrigatório para ação Verify"
        exit 1
    }
    
    Write-Info "Calculando SHA256 de: $Path"
    $hash = Get-FileHash -Path $Path -Algorithm SHA256
    $actualHash = $hash.Hash.ToLower()
    $expectedHash = $ExpectedHash.ToLower()
    
    Write-Host ""
    Write-Info "Hash calculado:  $actualHash"
    Write-Info "Hash esperado:   $expectedHash"
    Write-Host ""
    
    if ($actualHash -eq $expectedHash) {
        Write-Success "HASH VÁLIDO — O instalador é legítimo."
        Write-Host ""
        Write-Info "Este instalador foi baixado do GitHub Releases e seu hash"
        Write-Info "corresponde ao publicado na release. O aviso do Windows Defender"
        Write-Info "sobre 'publicador desconhecido' é normal para projetos open source"
        Write-Info "sem certificado de code signing pago."
        Write-Host ""
        Write-Info "Você pode prosseguir com a instalação com segurança."
        exit 0
    } else {
        Write-Error "HASH INVÁLIDO — O instalador foi MODIFICADO ou NÃO É LEGÍTIMO."
        Write-Host ""
        Write-Warn "Possíveis causas:"
        Write-Host "  • Arquivo corrompido durante o download"
        Write-Host "  • Arquivo modificado por terceiros"
        Write-Host "  • Hash copiado incorretamente da release"
        Write-Host ""
        Write-Warn "NÃO instale este arquivo."
        Write-Info "Baixe novamente do GitHub Releases:"
        Write-Host "  https://github.com/luck-of-luck/Ampliagro-releases/releases"
        exit 1
    }
}