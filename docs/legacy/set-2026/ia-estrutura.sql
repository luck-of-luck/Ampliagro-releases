-- =====================================================================
-- Ampliagro — GRÁFICO SQL: estrutura completa da IA com o sistema
-- Banco: db.sqlite3 (80 tabelas app_*). Gerado do DDL real em 2026-09-17.
-- Uso: abra no DB Browser for SQLite / DBeaver, ou rode os SELECTs abaixo.
-- Legenda do grafo:
--   [IA]      tabelas da IA local (artifactory + auditoria)
--   [NUCLEO]  centro do sistema (tudo da IA passa por aqui)
--   [DADO]    tabelas que os intents LEEM/CREIAM
-- Fluxo: painel/JS → /api/ia/executar/ → sandbox → intent → [DADO]
--          + registra IAExecucao --(artefato_id)--> IAArtefato (artifactory)
--          + fontes externas SÓ via allowlist (Open-Meteo + FonteDadosExterna)
-- =====================================================================

-- ---------------------------------------------------------------------
-- PARTE 1 — Consultas vivas: o grafo direto do banco
-- ---------------------------------------------------------------------

-- 1.1 Todas as tabelas da IA e quantas linhas têm
SELECT 'app_iaartefato' AS tabela, COUNT(*) AS linhas FROM app_iaartefato
UNION ALL SELECT 'app_iaexecucao', COUNT(*) FROM app_iaexecucao;

-- 1.2 Todas as FOREIGN KEYS que ligam a IA ao sistema (o grafo em forma de lista)
SELECT m.name AS de_tabela, fk."from" AS de_coluna, fk."table" AS para_tabela, fk."to" AS para_coluna
FROM sqlite_master m, pragma_foreign_key_list(m.name) fk
WHERE m.type = 'table' AND m.name IN (
  'app_iaartefato','app_iaexecucao','app_fontedadosexterna','app_comandodevice',
  'app_device','app_telemetrydata','app_propriedade','app_estacaometeo',
  'app_safra','app_planosafra','app_atividadeplanejada','app_animal',
  'app_loteaquatico','app_despesca','app_insumo','app_lancamentofinanceiro',
  'app_talhao','app_cultura','app_gateway'
)
ORDER BY de_tabela, para_tabela;

-- 1.3 Últimas execuções da IA com flags, latência e satisfação (auditoria ML)
SELECT id, intent, flags, fontes, via, ok, duracao_ms, satisfeito, criado_em
FROM app_iaexecucao ORDER BY id DESC LIMIT 20;

-- 1.4 Artifactory: o que a IA já aprendeu/guardou
SELECT id, chave, tipo, origem, atualizado_em FROM app_iaartefato ORDER BY atualizado_em DESC;

-- 1.5 Latência média por intent (otimização)
SELECT intent, COUNT(*) AS execs, ROUND(AVG(duracao_ms)) AS media_ms,
       MAX(duracao_ms) AS pico_ms
FROM app_iaexecucao GROUP BY intent ORDER BY media_ms DESC;

-- ---------------------------------------------------------------------
-- PARTE 2 — DDL real (cópia fiel do sqlite_master em 2026-09-17)
-- ---------------------------------------------------------------------

-- -- -- [IA] ARTIFACTORY: toda info da IA mora aqui, no BD do sistema -- --
CREATE TABLE "app_iaartefato" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "chave" varchar(100) NOT NULL, "tipo" varchar(30) NOT NULL, "dados" text NOT NULL CHECK ((JSON_VALID("dados") OR "dados" IS NULL)), "origem" varchar(50) NOT NULL, "criado_em" datetime NOT NULL, "atualizado_em" datetime NOT NULL, "user_id" integer NOT NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED);

-- -- -- [IA] AUDITORIA: cada intent vira uma linha (flags, fontes, ms, satisfeito) -- --
CREATE TABLE "app_iaexecucao" ("id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, "intent" varchar(50) NOT NULL, "params" text NOT NULL CHECK ((JSON_VALID("params") OR "params" IS NULL)), "flags" text NOT NULL CHECK ((JSON_VALID("flags") OR "flags" IS NULL)), "fontes" text NOT NULL CHECK ((JSON_VALID("fontes") OR "fonte
...[truncated 8184 chars]