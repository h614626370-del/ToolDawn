#!/bin/sh
set -eu

app_password="$(cat /run/secrets/postgres_app_password)"
test_password="$(cat /run/secrets/postgres_test_password)"
psql --username "$POSTGRES_USER" --dbname postgres \
  --set=ON_ERROR_STOP=1 \
  --set=app_password="$app_password" \
  --set=test_password="$test_password" <<'SQL'
CREATE ROLE tooldawn LOGIN PASSWORD :'app_password';
CREATE DATABASE tooldawn OWNER tooldawn;
CREATE ROLE tooldawn_test LOGIN PASSWORD :'test_password';
CREATE DATABASE tooldawn_test OWNER tooldawn_test;
SQL
