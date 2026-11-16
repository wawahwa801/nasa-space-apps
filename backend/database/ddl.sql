-- PostgreSQL setup. Run this first as a separate, auto-committed statement:
-- CREATE DATABASE pyroclast;
-- Then reconnect to pyroclast in DBeaver and execute this file as an admin.

BEGIN;

DO $$
BEGIN
    IF current_database() <> 'pyroclast' THEN
        RAISE EXCEPTION 'Connect to the pyroclast database before running ddl.sql';
    END IF;
END;
$$;

CREATE SCHEMA IF NOT EXISTS model_registry;

CREATE TABLE IF NOT EXISTS model_registry.models (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    s3_bucket TEXT NOT NULL,
    s3_key TEXT NOT NULL,
    sha256 VARCHAR(64) CHECK (sha256 ~ '^[0-9a-fA-F]{64}$'),
    -- Actual training completion time, not the upload/registration time.
    trained_at TIMESTAMPTZ NOT NULL,
    training_duration_seconds INTEGER CHECK (training_duration_seconds >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'staged'
        CHECK (status IN ('staged', 'ready', 'failed', 'retired')),
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,
    CONSTRAINT unique_model_version UNIQUE (model_name, model_version),
    CONSTRAINT active_model_must_be_ready CHECK (NOT is_active OR status = 'ready')
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_version_per_model
    ON model_registry.models (model_name) WHERE is_active;

-- Permission group: assign it to a separately managed login; no password here.
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'model_reader') THEN
        CREATE ROLE model_reader NOLOGIN;
    END IF;
END;
$$;

GRANT CONNECT ON DATABASE pyroclast TO model_reader;
GRANT USAGE ON SCHEMA model_registry TO model_reader;
GRANT SELECT ON TABLE model_registry.models TO model_reader;

GRANT model_reader TO model_publisher;

COMMIT;

-- As an admin, replace your_app_login with an existing PostgreSQL login:
-- GRANT model_reader TO your_app_login;
