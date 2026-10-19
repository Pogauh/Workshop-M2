#!/bin/sh
# Exécuté une seule fois, à l'initialisation du volume pgdata.
# Moindre privilège : un rôle SQL par service, avec des droits de colonne pour l'API.
# (Pour rejouer ce script après modification : docker compose down -v)
psql -v ON_ERROR_STOP=1 -U postgres -d payments <<SQL
CREATE TABLE users(
  username      text PRIMARY KEY,
  pw_hash       text NOT NULL,
  role          text NOT NULL DEFAULT 'customer',
  display_name  text NOT NULL DEFAULT '',
  suspended     boolean NOT NULL DEFAULT false,   -- décision du moteur de remédiation (confinement)
  locked_until  timestamptz,                      -- verrouillage temporaire (brute-force)
  revoked_after timestamptz,                      -- les jetons émis avant cette date sont refusés
  must_reset    boolean NOT NULL DEFAULT false);  -- mot de passe à réinitialiser (compromission)

CREATE TABLE accounts(
  owner   text PRIMARY KEY,
  balance numeric(14,2) NOT NULL CHECK (balance >= 0));

CREATE TABLE payments(
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payer      text NOT NULL,
  payee      text NOT NULL,
  amount     numeric(14,2) NOT NULL CHECK (amount > 0),
  label      text NOT NULL DEFAULT '',
  idem_key   text,
  created_at timestamptz NOT NULL DEFAULT now());
CREATE UNIQUE INDEX payments_idem  ON payments(payer, idem_key) WHERE idem_key IS NOT NULL;
CREATE INDEX        payments_payer ON payments(payer, created_at DESC);
CREATE INDEX        payments_payee ON payments(payee, created_at DESC);

-- 6 comptes x 100000.00 = invariant 600000.00 (vérifié par /api/health/deep après chaque reprise)
INSERT INTO accounts VALUES
  ('alice',100000),('bob',100000),('carol',100000),
  ('attacker',100000),('probe',100000),('merchant',100000);

CREATE ROLE api_user LOGIN PASSWORD '${API_DB_PASSWORD}';
GRANT SELECT (username, display_name, suspended, revoked_after) ON users TO api_user;   -- jamais pw_hash
GRANT SELECT, UPDATE ON accounts TO api_user;
GRANT SELECT, INSERT ON payments TO api_user;

CREATE ROLE auth_user LOGIN PASSWORD '${AUTH_DB_PASSWORD}';
GRANT SELECT, INSERT, UPDATE ON users TO auth_user;
SQL
