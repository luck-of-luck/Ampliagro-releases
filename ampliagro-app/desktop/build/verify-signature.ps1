param(
    [Parameter(Mandatory = $true)][string]$Artifact,
    [Parameter(Mandatory = $true)][string]$ExpectedPublisher
)

$ErrorActionPreference = 'Stop'
$resolved = (Resolve-Path -LiteralPath $Artifact).Path
if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
    throw 'Informe um arquivo de release.'
}
$signature = Get-AuthenticodeSignature -LiteralPath $resolved
if ($signature.Status -ne 'Valid') {
    throw "Assinatura não confiável: $($signature.Status). Não publique como certificado."
}
$certificate = $signature.SignerCertificate
if ($certificate.GetNameInfo([System.Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false) -ne $ExpectedPublisher) {
    throw 'O publicador não corresponde à identidade esperada.'
}
if (-not $signature.TimeStamperCertificate) {
    throw 'A assinatura precisa de carimbo de tempo confiável.'
}
[pscustomobject]@{
    File = $resolved
    Publisher = $ExpectedPublisher
    Signature = $signature.Status.ToString()
    SHA256 = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
} | ConvertTo-Json
