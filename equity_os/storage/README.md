# `equity_os/storage`

Persistence: the PostgreSQL pool, migrations runner, role logins and the approvals gate; the
append-only record stores; the retained-capture file tree; the fact stores; long-term memory;
retention and purge; and backup and restore. It writes PostgreSQL and the capture tree on disk. The
schema itself is in `migrations/`. It is not the only place SQL runs: several modules in other
buckets issue their own queries on a connection they are given.
