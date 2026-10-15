#!/usr/bin/env pwsh
# Script para gerar certificado auto-assinado para code signing (apenas para desenvolvimento/teste)
# NOTA: Certificados auto-assinados NÃO resolvem o problema do Windows Defender em produção.
# Para produção, use um certificado EV de uma autoridade certificadora (DigiCert, GlobalSign, Microsoft).

param(
    [string]$CertName = "Ampliagro Code Signing",
    [string]$OutputDir = ".\certs",
    [string]$Password = "Ampliagro2026!",
    [int]$ValidityYears = 1
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "Gerando certificado auto-assinado para Code Signing" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "AVISO: Este certificado NÃO é confiável pelo Windows Defender em produção." -ForegroundColor Yellow
Write-Host "Use apenas para desenvolvimento/teste local." -ForegroundColor Yellow
Write-Host ""

# Criar diretório de saída
if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}

# Gerar certificado auto-assinado
$cert = New-SelfSignedCertificate `
    -Subject "CN=$CertName" `
    -CertStoreLocation "Cert:\CurrentUser\My" `
    -KeyUsage "DigitalSignature" `
    -KeyAlgorithm "RSA" `
    -KeyLength 2048 `
    -HashAlgorithm "SHA256" `
    -NotAfter (Get-Date).AddYears($ValidityYears) `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3") # Code Signing EKU

if ($cert) {
    Write-Host "Certificado gerado com sucesso!" -ForegroundColor Green
    Write-Host "Thumbprint: $($cert.Thumbprint)" -ForegroundColor Cyan
    Write-Host ""
    
    # Exportar para PFX
    $pfxPath = Join-Path $OutputDir "ampliagro-codesign.pfx"
    $pwd = ConvertTo-SecureString -String $Password -Force -AsPlainText
    
    Export-PfxCertificate `
        -Cert $cert `
        -FilePath $pfxPath `
        -Password $pwd `
        -ChainOption "BuildChain"
    
    Write-Host "Arquivo PFX exportado para: $pfxPath" -ForegroundColor Cyan
    Write-Host "Senha do certificado: $Password" -ForegroundColor Cyan
    Write-Host ""
    
    # Exportar certificado público (.cer)
    $cerPath = Join-Path $OutputDir "ampliagro-codesign.cer"
    Export-Certificate -Cert $cert -FilePath $cerPath
    Write-Host "Certificado público exportado para: $cerPath" -ForegroundColor Cyan
    Write-Host ""
    
    # Configurar variáveis de ambiente para o build
    Write-Host "Para usar no build, configure estas variáveis de ambiente:" -ForegroundColor Yellow
    Write-Host '$env:CODE_SIGN_CERT = "' + $pfxPath + '"' -ForegroundColor Cyan
    Write-Host '$env:CODE_SIGN_PASSWORD = "' + $Password + '"' -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Exemplo de uso:" -ForegroundColor Yellow
    Write-Host '  $env:CODE_SIGN_CERT = ".\certs\ampliagro-codesign.pfx"' -ForegroundColor Cyan
    Write-Host '  $env:CODE_SIGN_PASSWORD = "Ampliagro2026!"' -ForegroundColor Cyan
    Write-Host '  npm run dist:win' -ForegroundColor Cyan
} else {
    Write-Host "Erro ao gerar certificado!" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Concluído!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
