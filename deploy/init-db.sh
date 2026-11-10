#!/bin/sh
set -eu

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password AUCTION_DB_PASSWORD
\getenv database_name POSTGRES_DB
CREATE ROLE auction LOGIN PASSWORD :'app_password';
ALTER DATABASE :"database_name" OWNER TO auction;
SQL
