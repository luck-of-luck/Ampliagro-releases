# Proveniência / Sistema de Evidência — Estado 2026-10-11

> Fontes: `app/validators.py:11-41`, `app/ia/proveniencia.py`, `app/models/producao.py:605`, `MERGED.md` §2.1, `HANDOVER-LCDPR.md` §2.5

---

## 1. Estados de Evidência (oficial)

**Fonte canônica:** `app/validators.py:11-17` — **5 estados**

```python
ESTADOS_FONTE = {
    "medido",              # Sensor/medição real
    "medido_com_ressalva", # Medição com limitação conhecida
    "suspect",             # Dado suspeito/fora de faixa
    "sem_dado",            # **Não é zero** — ausência de sensor/medição
    "declarado"            # Produtor AFIRMOU; afirmar NÃO é medir
}
```

**Regra pétrea** (`validators.py:40-41`):
> *"O sistema nunca promove uma afirmação a medição. Quem mediu foi o sensor; quem afirmou foi a pessoa."*

---

## 2. Divergência Atual (bug conhecido)

| Sítio | Estados | Tipo |
|-------|---------|------|
| `app/validators.py` `ESTADOS_FONTE` | 5 (`medido`, `medido_com_ressalva`, `suspect`, `sem_dado`, `declarado`) | `str` |
| `app/ia/proveniencia.py:88-95` `TODOS` | 6 (`MEDIDO`, `MEDIDO_COM_RESSALVA`, `SUSPECT`, `SEM_DADO`, `SIMULADO`, `DECLARADO`) | `Enum` |
| `app/models/producao.py:605` choices | 3 (`medido`, `medido_com_ressalva`, `suspect`, `sem_dado`, `declarado`) | `str` |

**Consequência:** Payload gravado por `proveniencia` com `simulado` não valida em `validators`. `SIMULADO` só existe num lado.

**Ação pendente:** Alinhar `proveniencia.py` com `validators.py` (remover `SIMULADO`, garantir `Enum`/`str` consistente).

---

## 3. `fonte_dado` — Carimbo por Campo

**Cada número traz `fonte` e `quando`.** Nunca confie num número sem carimbo.

| Valor | Significado |
|-------|-------------|
| `medido` | Sensor leu, medição real |
| `medido_com_ressalva` | Sensor leu mas com limitação (ex: bateria baixa) |
| `suspect` | Valor fora de faixa esperada |
| `sem_dado` | **Não é zero** — não havia sensor, não que sensor disse 0 |
| `simulado` | **Gerado, sem ligação à fazenda** — perigoso, não serve para decidir |
| `declarado` | Produtor afirmou; afirmar NÃO é medir |

---

## 4. `IAExecucao` — Rastreabilidade de IA

Cada execução de intent grava `IAExecucao` (`app/models/ia.py`):

```python
IAExecucao.objects.create(
    user=user,
    intent=intent_nome,
    entrada=entrada,           # Frase do produtor
    deteccao=deteccao,         # Scores do servidor
    passos=ctx["passos"],      # Cadeia de raciocínio
    params=params,
    flags=flags,
    fontes=fontes,             # Fontes consultadas
    via=via,                   # "sessao" | "mcp" | "chave"
    ok=bool,
    erro=str,
    duracao_ms=int
)
```

**Para que serve:** Responder "o que essa IA fez às 14h?" sem adivinhar. Auditoria de decisão.

---

## 5. MRV / Carbono — O que temos e o que NÃO temos

### Temos (camada de evidência)
| Activo | Onde | Por que serve a MRV |
|--------|------|---------------------|
| 6 estados, `fonte_dado` **read_only** | `validators.py`, `proveniencia.py` | Cliente **não escolhe** a confiança. Num MRV isso é o produto. |
| Regra escrita | `validators.py:40` | Política de custódia de evidência, em código. |
| `medir(None)` → `SemDado`, nunca `Medido(0)` | `proveniencia.py:160` | Certificador pergunta "o que acontece quando sensor falhou?" — resposta é um tipo, não zero. |
| `IAExecucao` grava cada intent | `models/ia.py` | Rastreabilidade de quem pediu o que, quando. |
| Testes doutrinários | `test_regras_cultura_motor.py`, `test_csp.py`, `test_placeholder_zero.py` | Cultura de não prometer o que não se mede, **testada em CI**. |

### NÃO temos (não construir)
- **Emissão de GEE / GHG Protocol** — Produto a inteiro; Fluere faz em 30-60 dias com UFSM
- **Tokenização / blockchain** — Commodity
- **MRV próprio** — O Ampliagro é **camada de evidência** para MRV de terceiros

---

## 6. Guardas de regressão

| Teste | O que impede |
|-------|--------------|
| `test_regras_cultura_motor.py` | "Ou admite-se que não existe e tira-se a promessa do ecrã" |
| `test_csp.py` | Política nos settings = o que HTML pede |
| `test_placeholder_zero.py` | Trava zero inventado |
| `test_manifesto_confere_com_codigo.py` | Promessas do manifesto com `xfail(strict=True)` |

---

## 7. Como usar nos serializers/handlers

```python
# SEMPRE carimbar fonte_dado — nunca confie em número sem carimbo
w["config"] = {
    "valor": 123.45,
    "fonte_dado": "medido",           # ou "sem_dado", "declarado", etc.
    "quando": "2026-10-11T10:30:00Z"
}

# NUNCA faça:
w["config"] = {"valor": 123.45}  # Sem carimbo = sem_dado implícito
```

**Regra:** Um número cuja origem ninguém conhece é pior que a sua ausência.