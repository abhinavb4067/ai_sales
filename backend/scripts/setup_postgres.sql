-- Run this once as a Postgres superuser (e.g. the `postgres` role) to
-- provision the dev database. The `vector` extension requires the
-- pgvector/pgvector Postgres image (or pgvector installed on the host) —
-- see docker-compose.yml.
CREATE DATABASE ai_sales;
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'ai_sales') THEN
    CREATE USER ai_sales WITH PASSWORD 'change-me';
  END IF;
END
$$;
GRANT ALL PRIVILEGES ON DATABASE ai_sales TO ai_sales;

\c ai_sales
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL ON SCHEMA public TO ai_sales;
