# 📦 Como verificar a autenticidade do instalador Ampliagro

## 📋 Contexto honesto

O Ampliagro é um projeto **de código aberto**, mantido por estudantes sem fins lucrativos. **Não possuímos certificado de code signing pago** (Authenticode), que custaria cerca de US$ 100-300/ano.

Isso significa que:

1. **O Windows pode exibir um aviso** ao abrir o instalador: *"Windows protegeu seu PC. O publisher deste arquivo não é conhecido"*
2. **Isso é normal** para projetos open source sem certificado pago
3. **O aviso pode ser ignorado com segurança** se você seguir os passos abaixo

## 🔒 Como verificar que o instalador é autêntico

### 1. Baixe apenas do GitHub Releases

Sempre baixe o instalador (`.exe`) nestas URLs:

- **Lançamentos oficiais**: https://github.com/luck-of-luck/Ampliagro-releases/releases
- **Nunca** baixe de sites terceiros, blogs ou avisos pop-up

### 2. Verifique o hash SHA256

O hash SHA256 é o "digital" do arquivo. Se bater com o publicado na release, o instalador é autêntico.

#### No Windows (PowerShell):

```powershell
# Navegue até a pasta do download
cd ~/Downloads

# Calcule o hash
Get-FileHash Ampliagro.exe -Algorithm SHA256
```

Isso retornará algo como: `Sha256 : a1b2c3d4e5f6...` (64 caracteres hexadecimais)

#### No Linux/macOS:

```bash
sha256sum Ampliagro.exe
```

#### Verificando contra a release:

1. Acesse https://github.com/luck-of-luck/Ampliagro-releases/releases
2. Baixe o instalador `.exe`
3. Copie o hash SHA256 publicado lá
4. Compare com o hash que você gerou

Se **bater exatamente**, o instalador é autêntico. Se **não bater**, não o execute — baixe novamente.

### 2. Dica visual no instalador

Ao abrir o instalador, se o Windows mostrar:

> *"Windows protegeu seu PC. O publisher deste arquivo não é conhecido."*

**Isto é esperado.** Clique em "Mais informações" e depois em **"Executar de qualquer forma"**. O instalador funcionará normalmente.

### 2. Por que isso acontece?

- **Certificado de code signing** (Authenticode) custa US$ 100-300/ano
- O projeto é mantido por estudantes sem orçamento para isso
- A confiança vem da **transparência** (código aberto + hash SHA256), não de certificados pagos

## 📋 Checklist de segurança

- [ ] Baixou do **GitHub Releases** oficial?
- [ ] Hash SHA256 **bate** com o publicado?
- [ ] O aviso do Windows foi ignorado com segurança?
- [ ] O instalador abre normalmente?

## 📞 Suporte

Se você tem dúvidas sobre a autenticidade do instalador:

- Entre em contato através dos canais oficiais do GitHub
- Nunca forneça dados sensíveis em sites desconhecidos
- Dúvidas? Abra uma issue no repositório oficial

---

**Lembre-se**: a confiança no Ampliagro vem do código-fonte aberto e da verificação SHA256, não de certificados pagos. O projeto agradece sua compreensão e contribuição para manter o software gratuito e acessível a todos.