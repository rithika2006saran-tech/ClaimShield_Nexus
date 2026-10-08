#!/usr/bin/env bash
# Native PostgreSQL for development when Docker is unavailable.
# Production/demo path remains `docker compose up` (see docker-compose.yml).
set -euo pipefail
PGBIN=${PGBIN:-/usr/lib/postgresql/16/bin}
PGDATA=${PGDATA:-$HOME/.claimshield_pgdata}
PGRUN=${PGRUN:-$HOME/.claimshield_pgrun}
mkdir -p "$PGRUN"
if [ ! -d "$PGDATA/base" ]; then
  "$PGBIN/initdb" -D "$PGDATA" -U postgres --auth=trust -E UTF8 >/dev/null
fi
"$PGBIN/pg_ctl" -D "$PGDATA" -o "-p 5432 -k $PGRUN -c listen_addresses=127.0.0.1" -l "$PGRUN/pg.log" start || true
sleep 2
psql -h 127.0.0.1 -U postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='claimshield'" | grep -q 1 || \
  psql -h 127.0.0.1 -U postgres -c "CREATE USER claimshield WITH PASSWORD 'claimshield' SUPERUSER;"
psql -h 127.0.0.1 -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='claimshield'" | grep -q 1 || \
  psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE claimshield OWNER claimshield;"
pg_isready -h 127.0.0.1
