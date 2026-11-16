# Model registry database

PostgreSQL setup for database `pyroclast`, schema `model_registry` and table `models`.

1. In DBeaver, connect to an existing database as an administrator. Enable auto-commit and run `CREATE DATABASE pyroclast;` separately. Skip this if the database already exists.
2. Reconnect to `pyroclast` and execute `ddl.sql`.
3. Grant the permission group to your application's existing PostgreSQL login:

   ```sql
   GRANT pyroclast_model_reader TO your_app_login;
   ```

`pyroclast_model_reader` is a NOLOGIN role: it grants CONNECT, schema USAGE and SELECT on this table. It does not create an application login or contain credentials. It grants no insert/update/delete permissions; membership does not remove privileges a login already has from other roles. This is separate from the AWS IAM role used to read S3.

`trained_at` must contain the actual training completion timestamp. `created_at` defaults to registration time. Register versions as staged; mark a verified version ready before making it active. Only one version per model name can be active. This file is initial setup, not an upgrade migration for existing table definitions.

To check read access as an administrator permitted to SET ROLE:

```sql
BEGIN;
SET LOCAL ROLE pyroclast_model_reader;
SELECT * FROM model_registry.models LIMIT 1;
ROLLBACK;
```

Check that a fresh reader role has no write permissions:

```sql
SELECT
    has_table_privilege('pyroclast_model_reader', 'model_registry.models', 'SELECT') AS can_read,
    has_table_privilege('pyroclast_model_reader', 'model_registry.models', 'INSERT') AS can_insert,
    has_table_privilege('pyroclast_model_reader', 'model_registry.models', 'UPDATE') AS can_update,
    has_table_privilege('pyroclast_model_reader', 'model_registry.models', 'DELETE') AS can_delete;
```

Expected: true, false, false, false. Existing PUBLIC or inherited grants can affect these results.

## Newest ready model API

Install the backend requirements. If `backend/.env` does not exist, copy
`backend/.env.example` to it. Otherwise preserve your existing settings and add
these settings (no connection URL or URL-encoding needed):

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=pyroclast
DB_USER=your_app_login
DB_PASSWORD=YOUR_PASSWORD
```

`DB_PORT` must be an integer from 1 to 65535; it defaults to 5432 if omitted.
The other fields are required. `DATABASE_URL` is no longer used. Use an actual
LOGIN user granted `pyroclast_model_reader`; the permission group itself cannot
log in. Keep this setting on the server, never in `NEXT_PUBLIC_*` or Git. For a
remote deployment use verified TLS (`DB_SSLMODE=verify-full` and `DB_SSLROOTCERT` pointing to the database
provider's CA certificate).

Start the backend and request:

```sh
curl 'http://127.0.0.1:5000/api/models/latest?model_name=flex2'
```

The frontend can use `/api/models/latest?model_name=flex2` through the existing
Next.js backend proxy. Omitting the name defaults to `flex2`. The endpoint returns
`{"model": {...}}` with the S3 bucket/key, version, checksum and ISO timestamps.
It selects **ready** records by `trained_at DESC, id DESC`, not registration time
or active status. Thus a newly inserted staged row is not returned, and the
newest ready row can be inactive. This endpoint does not download or activate
weights, and does not change the running CNN.

Missing/invalid parameters return 400, no ready version returns 404, and missing
configuration or database failures return 503 without connection details. Health
and analysis routes do not require a database connection. New registry queries
are made per request, with a five-second connection timeout and five-second SQL
statement timeout.
