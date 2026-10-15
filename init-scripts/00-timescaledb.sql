-- Ampliagro — init do Postgres/TimescaleDB
--
-- Executado uma unica vez, na criacao do volume. Sem esta linha a extension
-- timescaledb nunca era criada no banco da serie temporal, apesar do
-- shared_preload_libraries no compose — e a primeira hypertable falhava.
CREATE EXTENSION IF NOT EXISTS timescaledb;
