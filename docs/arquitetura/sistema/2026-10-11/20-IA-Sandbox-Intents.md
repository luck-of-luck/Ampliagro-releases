# IA Sandbox, Intents & AmplIA MCP — Estado 2026-10-11

> Fontes: `app/ia/sandbox.py`, `app/ia/intents.py`, `app/ia/registro.py`, `app/amplia_mcp/`

---

## 1. Sandbox (`app/ia/sandbox.py`)

### Execução Centralizada
```python
def executar(user, intent_nome, params, via="sessao", meta=None):
    # 1. Cache (TTL por intent)
    # 2. Validação campos obrigatórios
    # 3. Human-in-the-loop (confirmação explícita)
    # 4. Executa handler
    # 5. Grava IAExecucao + IAArtefato
    # 6. Retorna resposta padronizada
```

### Cache TTL por Intent
```python
CACHE_TTL = {
    "clima_agora": 0,
    "vai_chover": 0,
    "previsao_estendida": 0,
    "melhor_pulverizar": 0,
    "listar_tarefas": 0,  # Sem cache: reflete conclusão imediata
    "resumo_safra": 300,
    "resumo_financeiro": 300,
    "consultar_estoque": 300,
    # ...
}
```

### Intents NÃO Cacheáveis (Escrita/Ação Física)
```python
INTENTS_NAO_CACHEAVEIS = frozenset({
    "ligar_irrigador", "desligar_irrigador",
    "associar_tarefa", "concluir_tarefa", "feedback",
    "editar_safra", "excluir_safra",
    "cadastrar_maquina", "registrar_manutencao", "registrar_vacina",
    "criar_ordem_compra", "editar_lancamento",
    "automatizar_aerador", "automatizar_bigbrother", "automatizar_hedge",
    "automatizar_moba", "automatizar_piquete", "automatizar_pivo",
    "automatizar_sap", "automatizar_spd",
    "cadastrar_funcionario", "cadastrar_talhao",
    "chamado_criar", "chamado_editar", "chamado_publicar",
    "criar_entidade", "emitir_alerta_proativo",
    "inserir_registro", "ligar_proatividade",
    "provisionar_endpoint_iot", "remarcar_tarefa",
    "revogar_endpoint_iot",
    "pagar_conta", "registar_conta",
    "preset_editar", "preset_apagar",
})
```

### Máquina de Estados Conversacional
| Estado | Descrição |
|--------|-----------|
| `NENHUM` | Inicial |
| `COLETANDO_DADOS` | Perguntando campos obrigatórios faltantes |
| `AGUARDANDO_CONFIRMACAO` | Aguardando "sim" do produtor |

**Regra crítica:** Só recupera estado se `entrada` (resposta humana) existir. Sem `entrada` = intent novo roda, não retoma pendente.

### Validação de Campo (`_perguntar_por`)
```python
_PERGUNTAS_CAMPO = {
    "nome": "Qual é o nome?",
    "area": "Qual é a área em hectares?",
    "cargo": "Qual é a função? Exemplos: tratorista, vaqueiro, diarista, motorista, mecânico, caseiro, técnico agrícola.",
    "tipo": "Que tipo? Se for uma máquina: trator, colheitadeira, pulverizador, caminhão, plantadeira, drone ou implemento.",
    "data": "Para que dia quer ficar? (ex.: 12/10/2026)",
    "titulo": "Como se chama a tarefa? (ex.: aplicar herbicida, vacinar o gado)",
}
```

### Detecção de Recusa (`_e_recusa`)
```python
_RECUSA = re.compile(r"^(?:nao|n|naum|nunca|jamais|deixa|deixar|deixamos|dispenso|dispense|esquece|esqueceu|cancela|cancelar|cancele|sem\s+(?:isso|essa|este|esta|aquilo)|melhor\s+nao|por\s+(?:enquanto\s+)?nao|para\s+(?:com\s+)?isso|muda\s+de\s+(?:assunto|topico))\b", re.IGNORECASE)
```

**Regra:** "não" = cancela operação. Não grava "não" como valor do campo.

---

## 2. Intents (`app/ia/intents.py`, `app/ia/registro.py`)

### Estrutura de Intent
```python
{
    "descricao": "INSTRUÇÃO IA: use para 'quais tarefas', 'tarefas pendentes'. Lista até 10 por data.",
    "exemplos": ["quais tarefas pendentes", "o que fazer hoje", "liste tarefas"],
    "flags": ["tarefa.read"],
    "handler": h_listar_tarefas,
    "required_fields": [],
}
```

### Flags Principais
| Flag | Significado |
|------|-------------|
| `read` | Só leitura |
| `write` | Escrita (cria/edita/apaga) |
| `create` | Cria registro |
| `comando` | Ação física (irrigador, etc.) |
| `tarefa.read` | Leitura de tarefas |
| `tarefa.write` | Escrita de tarefas |
| `estoque.read` | Leitura estoque |
| `financeiro.read` | Leitura financeiro |

### Trava Leitura × Escrita
```python
def parece_cadastro(texto):
    # Verbo forte de escrita (cadastro/edição/exclusão)
    _RE_CADASTRO = re.compile(r"\b(cadastr\w*|cantar\w*|cria\w*|crie|registr\w*|adicion\w*|exclu\w*|delet\w*|apag\w*|edit\w*|atualiz\w*)", re.IGNORECASE)
    # Particípios ("cadastrados", "concluída") NÃO contam
```

**Regra:** Se `parece_cadastro(entrada)` e `somente_leitura(intent)` → bloqueia com orientação.

---

## 3. AmplIA MCP (`app/amplia_mcp/`)

### Servidor MCP (`app/amplia_mcp/servidor.py`)

**Tools = Intents** via `executar_para` → `sandbox.executar`

**Resources:**
| URI | Descrição |
|-----|-----------|
| `amplia://contexto/{usuario}` | O que já existe na fazenda |
| `amplia://modelos` | Telas que valem a pena montar |
| `amplia://widgets` | Dicionário de widgets + `fonte_dado` |
| `amplia://blocos` | Tipos de bloco do Chamado Amplia |
| `amplia://skills` | SKIs de domínio (campo, finanças, IoT) |
| `amplia://capacidades` | Catálogo derivado do código |
| `amplia://fontes` | De onde vem cada número + o que está VAZIO |
| `amplia://contexto/{usuario}` | Contexto do produtor |

**Prompts:** `amplia_ferramentas` (lista tools reais), `amplia_regras_escrita` (regras de escrita).

### Catálogo de Ferramentas (`app/amplia_mcp/ferramentas_aceitas.py`)
```python
TOOLS_CATALOGO = [
    "amplia_catalogos", "amplia_desenhar_pagina", "amplia_estado_sistema",
    "amplia_inventario_carbono", "amplia_chamado_criar", "amplia_chamado_editar",
    "amplia_chamado_publicar", "amplia_chamado_ler",
    # ... 78 tools
]
```

### Execução (`app/amplia_mcp/__init__.py:283`)
```python
def executar_para(user, nome, args, **meta):
    intent = intent_de_tool(nome)
    if intent not in INTENTS: return {"ok": False, "erro": "tool desconhecida", "sugestoes": sugerir_tools(nome)}
    return executar(user, intent, args, via="mcp", meta=meta)
```

**Segurança:** `via="mcp"` fixo para trilha de auditoria. `allowlist` = catálogo, não prefixo.

---

## 4. Chamado Amplia (`app/ia/chamado.py`, `app/ia/chamado_intents.py`)

### Zona de Escrita Única
- **Único preset onde IA escreve:** `chamado-amplia`
- **Outros presets:** IA só lê
- **Trava:** `chamado.pode_escrever` chamado **dentro de cada handler de escrita**

### Modelos
| Modelo | Descrição |
|--------|-----------|
| `ChamadoAmplia` | Peça que IA escreve (slug fixo `chamado-amplia`) |
| `PresetPalco` | Dashboard do produtor (slug `custom-*`) |
| `PalcoIA` | Preset "Amplia" (singleton, `structure` vazio) |
| `AssinaturaPalco` | Dataset ML (pergunta → estrutura + veredito) |

### Intents do Chamado
| Intent | Descrição |
|--------|-----------|
| `chamado_criar` | Monta peça a partir do catálogo de blocos |
| `chamado_editar` | Muda peça por DELTA (adicionar/remover/substituir/reordenar/reescrever) |
| `chamado_ler` | Mostra o que está lá |
| `chamado_publicar` | Publica/arquiva/rascunho |

### Guardas
```python
def pode_escrever(user, preset_slug):
    return preset_slug == "chamado-amplia"  # Único onde IA escreve
```

---

## 5. Palco / Presets (`app/ia/palco.py`, `app/ia/palco_presets.py`)

### Modelos (BUILD 5)
| Modelo | Descrição |
|--------|-----------|
| `PalcoIA` | Singleton "Amplia" — `structure` vazio (widgets efémeros na sessão) |
| `AssinaturaPalco` | Dataset ML — (user, assinatura) único, veredito substituído |
| `PresetPalco` | "Salvar como meu Dashboard" — do produtor, IA só lê |
| `ChamadoAmplia` | **Única zona de escrita da IA** (slug fixo `chamado-amplia`) |

### `palco_clonar` → `PresetPalco`
```python
preset, criado = PresetPalco.objects.get_or_create(
    user=request.user,
    slug=_slug_livre(request.user, nome),
    defaults={"nome": nome, "estrutura": estrutura, "origem": origem, "fixado": True}
)
```

### `palco_avaliar` → `AssinaturaPalco`
```python
registro, criado = AssinaturaPalco.objects.get_or_create(
    user=request.user, assinatura=assinatura,
    defaults={"intent_texto": intent, "estrutura": estrutura, "veredito": veredito}
)
# Veredito SUBSTITUÍDO, não acumulado — último vale
```

---

## 6. Guardas de Regressão (IA)

| Teste | O que impede |
|-------|--------------|
| `tests/test_intents_confirmacao.py` | Toda escrita tem `requires_confirmation` |
| `tests/test_placeholder_zero.py` | Trava zero inventado |
| `tests/test_csp.py` | CSP header real sai |
| `tests/test_manifesto_confere_com_codigo.py` | Promessas do manifesto com `xfail(strict=True)` |
| `tests/test_lcdpr_campos_fiscais.py` | Cadeia modelo → guarda → gerador → ficheiro |

---

## 7. Checklist de Operação

- [ ] `INTENTS_NAO_CACHEAVEIS` cobre todas escritas
- [ ] `parece_cadastro` bloqueia leitura disfarçada de escrita
- [ ] `chamado.pode_escrever` em todos handlers de escrita
- [ ] `PresetPalco` só `custom-*` no dashboard
- [ ] `ChamadoAmplia` slug fixo `chamado-amplia`
- [ ] `IAExecucao` gravada para toda execução (auditoria)
- [ ] `xfail(strict=True)` em promessas do manifesto