# generate-selfsigned-cert.ps1
# Gera um certificado auto-assinado (para desenvolvimento/local)
# Usado para testes locais antes de obter certificado EV para produção.
#
# NOTA: Certificados auto-assinados NÃO satisfazem o Windows Defender SmartScreen.
# Para produção, obter um certificado EV (Digicert, GlobalSign, etc.) é obrigatório.

param(
    [Parameter(Position = 0)]
    [ValidateRange(1, 999)]
    [string]$CertName = "Ampliagro"
)

# Gera um certificado auto-assinado
# Este é apenas para desenvolvimento local - não substitui um certificado EV

$certPath = Join-Path $PSScriptRoot "ampliagro-codesign.pfx"

Write-Host "Gerando certificado auto-assinado: $certPath"

# Cria o certificado
$cert = New-SelfSignedCertificate -SubjectName $CertName -KeyLength 2048 -NotBefore (Get-Date) -NotAfter (Get-Date).AddDays(1)

# Exporta o certificado em formato PFX
$pfxData = [System.Security.Cryptography.X509Certificates.Certificate]::FindByCommonName($cert).ExportToPfx($certPath, -Force)

Write-Host "Certificado gerado em: $certPath"
Write-Host "Certificado: $CertName"
Write-Host "Para uso com electron-builder, defina as variáveis de ambiente:"
Write-Host "  CSC_LINK=$certPath"
Write-Host "  CSC_KEY_PASSWORD=\"$(Get-Credential -Message 'Senha do certificado' | ForEach-Object { $_ } | ForEach-Object { $_.ToString().Replace('$', '\\$') })\"}"

# Salvar o caminho do certificado para referência futura
$env:CODE_SIGN_CERTIFICATE = $certPath
$env:CODE_SIGN_PASSWORD = "senha-do-certificato"  # Será substituído pelo secret

exit 0
