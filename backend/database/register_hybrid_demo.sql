-- Run as an administrator in DBeaver, connected to pyroclast, after the S3
-- package's fresh-download checksum and prediction smoke test pass.
-- User requested current publication time because training completion is unknown.
BEGIN;
INSERT INTO model_registry.models (
    model_name, model_version, s3_bucket, s3_key, sha256,
    trained_at, status, notes
) VALUES (
    'flex2-hybrid', 'demo-20261116-023414',
    'pyroclast-ai-204898220304-us-west-2-an',
    'models/flex2-hybrid/1eaf35a1ccf7fba6157da982c27f224563dcda5c5ba853c2a8e388fd42869534/bundle.zip',
    '1eaf35a1ccf7fba6157da982c27f224563dcda5c5ba853c2a8e388fd42869534',
    TIMESTAMPTZ '2026-11-16 02:34:14+00', 'ready',
    'Publication time supplied at user request; actual training completion was not recorded. Full geometry and baseline CNN package.'
) ON CONFLICT (model_name, model_version) DO NOTHING;
COMMIT;
