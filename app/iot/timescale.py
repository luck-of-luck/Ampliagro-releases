"""
Helpers TimescaleDB — cria hypertable e políticas quando Postgres é Timescale.

Chamado via: python manage.py timescale_setup
Ou automaticamente no primeiro deploy se DATABASES aponta para Timescale.
"""

from django.db import connection


def is_timescale():
    if connection.vendor != "postgresql":
        return False
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_extension WHERE extname='timescaledb'")
            return cur.fetchone() is not None
    except Exception:
        return False


def ensure_hypertable():
    if not is_timescale():
        return "SQLite/Postgres sem Timescale — skip hypertable (índices normais já criados)"
    with connection.cursor() as cur:
        cur.execute("""
            SELECT create_hypertable('app_telemetrydata', 'timestamp',
                if_not_exists => TRUE, migrate_data => TRUE);
        """)
        cur.execute("""
            SELECT add_retention_policy('app_telemetrydata', INTERVAL '365 days', if_not_exists => TRUE);
        """)
        cur.execute("""
            SELECT add_compression_policy('app_telemetrydata', INTERVAL '7 days', if_not_exists => TRUE);
        """)
        # Hypertable também para LeituraSensor legado
        cur.execute("""
            SELECT create_hypertable('app_leiturasensor', 'timestamp',
                if_not_exists => TRUE, migrate_data => TRUE);
        """)
        cur.execute("""
            CREATE MATERIALIZED VIEW IF NOT EXISTS telemetry_hourly
            WITH (timescaledb.continuous) AS
            SELECT time_bucket('1 hour', timestamp) AS bucket,
                   propriedade_id, device_id, metric,
                   avg(value) as avg_val, max(value) as max_val, min(value) as min_val, count(*) as n
            FROM app_telemetrydata GROUP BY bucket, propriedade_id, device_id, metric
            WITH NO DATA;
        """)
        cur.execute("""
            SELECT add_continuous_aggregate_policy('telemetry_hourly',
                start_offset => INTERVAL '3 hours',
                end_offset   => INTERVAL '1 hour',
                schedule_interval => INTERVAL '1 hour',
                if_not_exists => TRUE);
        """)
    return "Hypertable + policies + cagg criados"


def chunk_stats():
    if not is_timescale():
        return []
    with connection.cursor() as cur:
        cur.execute("SELECT * FROM chunk_detailed_size('app_telemetrydata') LIMIT 20;")
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=False)) for row in cur.fetchall()]
