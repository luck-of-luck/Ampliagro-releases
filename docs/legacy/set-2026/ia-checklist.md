# Checklist — novo intent da IA local

Antes de catalogar um intent em `app/ia/intents.py`, responda:

1. **Flags**: quais capacidades mínimas? (`clima.read`, `iot.read`, `iot.comando`,
   `safra.read`, `fin.read`, `estoque.read`, `tarefa.read/write/create`,
   `pecuaria.read`, `aquatico.read`, `campo.read`, `ml.write`). Só leitura?
   Flag vazia `[]` só para `ajuda`.
2. **Escopo**: TODA query filtra `propriedade__user=user` (ou cadeia equivalente:
   `plano__safra__propriedade__user`, `lote__propriedade__user`...)? Teste com
   2 usuários em `app/ia/tests.py` (padrão `EscopoUsuarioTest`).
3. **Tabelas**: liste as tabelas tocadas; leitura ou escrita?
4. **Escrita/ação física?** Exige `confirm=true` (padrão `h_irrigador`:
   sem confirm → `needs_confirm`, sem efeito colateral). Entra em `SEM_CACHE`.
5. **Comando IoT?** Use `enfileirar_comando()` (dedupe + rate-limit 10/h +
   `expira_em`). Rode `manage.py ia_comandos` no cron para expirar travados.
6. **Cache?** Leitura idempotente → TTL em `CACHE_TTL` (`sandbox.py`).
   Escrita/ação física/feedback → `SEM_CACHE`.
7. **Artefato**: resultado reaproveitável? Retorne `"artefato": (chave, tipo)`.
   Dado sensível (fin/safra)? Leitura do artifactory já é por usuário — mantenha.
8. **Teste**: adicione caso em `app/ia/tests.py` e rode
   `manage.py test app.ia.tests`. Catálogo fora do padrão quebra
   `CatalogoHigieneTest` de propósito.

Fronteira de confiança (não mexer sem revisar):
- Painel = sessão (`via=sessao`). Serviços = `X-IA-Key` + `user_id` **somente**
  se em `IA_KEY_USERS` (fail-closed). Chave nunca no JS.
- Allowlist (`app/ia/fontes.py`): só Open-Meteo + hosts de `FonteDadosExterna`
  ativas. Novo destino externo = atualizar `FONTES_POR_TIPO` + teste.

# Checklist — novo wizard guiado (ia-local.js)

9. **Trigger**: verbo no STEM (cadastr/cria/adicion/registr — pega conjugação:
   "cadastra", "cria", "adiciona") + substantivo do domínio. Particípios
   ("cadastrados") NÃO disparam escrita. Registrar em `wiz_test2.js`.
10. **Guardas**: todo `wiz*Step` chama `wizGuardas(META, chave, texto)` após o
    `wizCancelar`. Novo fluxo entra em `WIZ_META` (Q, HELP, data, livres),
    `limparWizard`, roteamento do `iaChat` e `wizDetectTroca`.
11. **Pergunta × resposta inválida**: número (extenso/milhar via `wizParseNum`),
    data (`wizParseDatas` + `wizDataRelativa`), sim/não, vazio, "voltar",
    "ajuda", troca de fluxo e valores absurdos (confirm via `wizArmarConfirm`).
    Cobrir em `wiz_test3.js`/`wiz_test5.js` (padrão adversarial).
12. **Criação**: checar duplicada antes do POST; erro do backend vira mensagem
    curta (nunca JSON cru). `checar_drift` precisa continuar verde.
13. **Roteamento**: menção a `tarefa` vence safra/talhão; `?` prioriza leitura;
    escrita só casa com flag `write|create|comando` (trava fast-path + scorer).
