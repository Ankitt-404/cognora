CREATE TABLE IF NOT EXISTS login_attempts (
  id bigserial PRIMARY KEY,
  email text NOT NULL,
  ip_address text NOT NULL,
  succeeded boolean NOT NULL,
  attempted_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS login_attempts_email_time ON login_attempts (email, attempted_at);
CREATE INDEX IF NOT EXISTS login_attempts_ip_time ON login_attempts (ip_address, attempted_at);

CREATE TABLE IF NOT EXISTS signups (
  id bigserial PRIMARY KEY,
  ip_address text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS signups_ip_time ON signups (ip_address, created_at);