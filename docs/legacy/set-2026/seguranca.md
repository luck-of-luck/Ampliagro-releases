# Segurança Ampliagro — estado + roadmap ponta a ponta

## ✅ Fase 1 — em repouso (neste commit)
- **Fernet** (`app/seguranca.py`, chave em `AMPLIAGRO_DATA_KEY`; dev usa chave
  fixa com aviso, prod sem chave **não sobe**): `EncryptedCharField` com prefixo
  `enc1:`, passthrough de legado em claro, `hash_cego()` (SHA-256) p/ busca.
- **Campos**: `LancamentoFinanceiro.participante_doc` (CPF/CNPJ), `Gateway.api_key`
  (+ `api_key_hash` p/ auth sem descriptografar; backfill na migração `0046`).
- **Financeiro fechado**: permission `PodeVerFinanceiro` — produtor sempre;
  servidor só com `pode_ver_financeiro` (área FINANCEIRO); querysets pela
  vinculada; `financeiro_data` cai pra vinculada quando permitido.
- **Uploads**: extensão + 10 MB por campo (VRA, MIP, receituário, relatórios);
  OFX 5 MB + extensão; teto global `DATA/FILE_UPLOAD_MAX_MEMORY_SIZE`.
- **Base pronta**: CSP, HSTS/SSL-redirect (prod), `X-Frame: DENY`, cookies
  `Secure`/`HttpOnly`(sessão), throttling IA, auditoria total, `.env` ignorado.
- **Regra de ouro**: Fernet é randomizado — NUNCA `filter(campo=valor)` em campo
  cifrado; use índice cego (`hash_cego`).

## 🔜 Fase 2 — ponta a ponta de verdade (browser → banco sem ver claro)
1. **Chave por fazenda**: `Propriedade.data_key_enc` (Fernet gerada no cadastro,
   ela mesma cifrada pela master) em vez de chave global única.
2. **Envelope no frontend**: `crypto.subtle` (AES-GCM) cifra CPF/conta no
   `cadastro-financeiro.html` antes do POST; servidor só repassa o envelope
   (nunca vê claro nem em log — hoje `IAEvento.dados.entrada` guarda texto!).
3. **Zerar logs claros**: `IAEvento`/`IAExecucao` passam a guardar hash ou nada
   de PII (hoje guardam entrada/resposta).
4. **Push assinado**: assinar payloads de comando gateway (HMAC com api_key)
   contra replay.
5. **Rotação de chave**: comando `rotate_data_key` re-cifra com re-encrypt.

## 🔑 Operação
```bash
# gerar chave de produção (uma vez, guardar no .env, NUNCA no git)
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# .env
AMPLIAGRO_DATA_KEY=<saída>
```
