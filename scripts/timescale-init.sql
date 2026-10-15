-- Ampliagro TimescaleDB init — converte TelemetryData em hypertable + políticas
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Nota: Django cria app_telemetrydata depois do migrate; este script roda no primeiro up.
-- O hypertable é criado via SQL separado (ver app/iot/timescale.py) ou manualmente:
-- SELECT create_hypertable('app_telemetrydata', 'timestamp', if_not_exists => TRUE, migrate_data => TRUE);

-- Políticas padrão (aplicar após hypertable):
-- SELECT add_retention_policy('app_telemetrydata', INTERVAL '365 days', if_not_exists => TRUE);
-- SELECT add_compression_policy('app_telemetrydata', INTERVAL '7 days', if_not_exists => TRUE);

-- Continuous aggregates (exemplos):
-- CREATE MATERIALIZED VIEW telemetry_hourly WITH (timescaledb.continuous) AS
-- SELECT time_bucket('1 hour', timestamp) AS bucket, propriedade_id, device_id, metric,
--        avg(value) as avg_val, max(value) as max_val, min(value) as min_val, count(*) as n
-- FROM app_telemetrydata GROUP BY bucket, propriedade_id, device_id, metric;
