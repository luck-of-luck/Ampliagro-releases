# OTA / Firmware / IoT — Estado 2026-10-11

> Fontes: `app/models/iot.py:135`, `app/ia/iot.py`, `MERGED.md` §3.11, `PLANO-EXECUCAO.md` §2.6, `9.md` §8.2, `5.md` §2.5

---

## 1. Estado Atual

| Item | Status | Evidência |
|------|--------|-----------|
| `models/iot.py:135` `firmware_version` | Existe no modelo | Campo `CharField(max_length=50, blank=True)` — **nada escreve** |
| Upload de firmware | **Não existe** | `grep ota_update\|esptool\|micropython\|firmware_upload` → vazio |
| Code-gen para Arduino IDE | Existe | `app/ia/iot.py:357` — gera C++ para colar no Arduino IDE |
| `<option>OTA Atualizar</option>` no template | Existe | UI promete; backend não entrega |

---

## 2. Classificação dos Achados

| Agente | Classificação | Formulação |
|--------|---------------|------------|
| Agente 1 | Divergência | "OTA não existe" |
| Agente 2 | **A que mais dano causa** | *"A divergência que mais dano causa, porque é a única que descreve algo que **não existe** em vez de algo que existe mas está por fazer"* |
| Agente 5 | Promessa enganosa | *"Mata o primeiro cliente e o motivo conta"* |
| Agente 9 | Runtime declarado não existe | §3.2 |

**Consenso:** É a **única promessa do manifesto que descreve algo que não existe** (não "está por fazer", **não existe**).

---

## 3. O Que Existe (code-gen)

`app/ia/iot.py` gera C++ para o produtor colar no Arduino IDE:
- Gera credencial revogável
- Tópico MQTT
- Código C++ pronto
- Token aparece **só na resposta** (aviso ao produtor)

**Limitação:** Exige cabo + Arduino IDE. **Não é OTA**.

---

## 4. Doutrina do Projeto (por que não implementar OTA "verdadeiro")

`models/dinamico.py:32` **proíbe** código gerado por IA a correr no servidor.
Manifesto §VII descreve exatamente isso para outro alvo.

> **Regra:** LLM propõe código → produtor revê linha a linha → upload exige confirmação → botão físico no dispositivo.

---

## 5. Caminho Honesto (Guided Flash)

**Fase intermediária honesta** (nem OTA, nem code-gen puro):

1. Sistema diz ao produtor **exatamente que binário compilar**
2. Dá a linha de comando: `esptool write_flash ...`
3. Verifica o **checksum do `.bin` que o próprio produtor compilou**

**Vantagens:**
- Não compila no servidor
- Não gera firmware em dispositivo de terceiro
- Não salta camada de aprovação
- **Cumpre a promessa** de "não precisa de bootloader" (parte que o produtor sente)

**Custo:** Uma página de texto + uma tarde de guia.

---

## 6. Decisão de Manifesto

| Item | Ação |
|------|------|
| OTA no §VII | **Tirar a promessa** — meia hora, melhor relação esforço/impacto |
| §VII | Reescrever como **roadmap** (guided flash → OTA futuro se quiser) |
| `firmware_version` no modelo | Manter (pode servir no futuro) |

---

## 7. Guardas de Regressão

| Teste | O que impede |
|-------|--------------|
| `test_manifesto_confere_com_codigo.py` | Promessa de OTA no manifesto falha (`xfail(strict=True)`) |
| `tests/test_iot_exige_login.py` | Webhook TTN sem `api_key` falha de propósito |

---

## 8. Resumo para Decisão

| Opção | Esforço | Promessa Cumprida? | Rastreável? |
|-------|---------|-------------------|-------------|
| OTA real (LLM→silício) | Meses | Não (salta aprovação) | Não |
| **Guided Flash** | 1 tarde + doc | **Sim** (parte sentida) | **Sim** (checksum verifica) |
| Code-gen Arduino (atual) | Já existe | Parcial (exige cabo/IDE) | Sim |

**Recomendação:** Tirar OTA do manifesto, documentar Guided Flash como caminho honesto. Se no futuro quiser OTA real → toolchain de firmware = produto novo.