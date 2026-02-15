-- =============================================================================
-- PostgreSQL Seed Data — Cyber Range Tier 2 (Corporate)
-- =============================================================================
-- CORP-15: User credentials table containing AD domain passwords.
-- Discoverable via SQL after gaining PostgreSQL access (CORP-11/CORP-12).
--
-- Note: This file is mounted at /docker-entrypoint-initdb.d/ and runs on
-- first boot. The database is created via the connection below.

-- Create the corporate database (idempotent via \gexec trick won't work here,
-- so docker-entrypoint handles this via POSTGRES_DB or we create it manually)
SELECT 'CREATE DATABASE corporate_db' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'corporate_db')\gexec

\connect corporate_db
--
-- This script runs automatically on first boot via docker-entrypoint-initdb.d.
-- DO NOT deploy outside the cyber-range.
-- =============================================================================

-- Application database with credential leakage
CREATE TABLE IF NOT EXISTS employees (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(100),
    email VARCHAR(100),
    department VARCHAR(50),
    hire_date DATE
);

INSERT INTO employees (full_name, email, department, hire_date) VALUES
    ('John Smith', 'jsmith@psyche.local', 'IT', '2022-03-15'),
    ('Jane Doe', 'jdoe@psyche.local', 'HR', '2021-06-01'),
    ('Bob Wilson', 'bwilson@psyche.local', 'Engineering', '2023-01-10'),
    ('Ana Garcia', 'agarcia@psyche.local', 'Finance', '2020-09-22'),
    ('Ming Chen', 'mchen@psyche.local', 'Security', '2024-02-01');

-- CORP-15: Credentials table — contains AD domain passwords (intentionally insecure)
CREATE TABLE IF NOT EXISTS user_credentials (
    id SERIAL PRIMARY KEY,
    system VARCHAR(50),
    username VARCHAR(50),
    password VARCHAR(100),
    notes TEXT,
    last_updated TIMESTAMP DEFAULT NOW()
);

INSERT INTO user_credentials (system, username, password, notes) VALUES
    ('PSYCHE.LOCAL', 'jsmith', 'Summer2024!', 'AD domain account — IT admin'),
    ('PSYCHE.LOCAL', 'jdoe', 'Welcome1', 'AD domain account — HR'),
    ('PSYCHE.LOCAL', 'bwilson', 'Password1', 'AD domain account — dev'),
    ('PSYCHE.LOCAL', 'agarcia', 'Company1', 'AD domain account — finance'),
    ('PSYCHE.LOCAL', 'mchen', 'Qwerty123', 'AD domain account — security'),
    ('PSYCHE.LOCAL', 'svc_sql', 'sql123', 'Service account — SQL Server SPN'),
    ('PSYCHE.LOCAL', 'svc_backup', 'backup1', 'Service account — backup'),
    ('PSYCHE.LOCAL', 'da_jenkins', 'JenkinsAdmin2024!', 'Domain Admin — Jenkins CI/CD'),
    ('Jenkins', 'admin', 'admin', 'Jenkins CI/CD server — default creds'),
    ('GitLab', 'root', '5iveL!fe', 'GitLab CE — default root password'),
    ('WordPress', 'admin', 'admin123', 'WordPress CMS — admin panel'),
    ('DVWA', 'admin', 'password', 'DVWA — default credentials'),
    ('SCADA-HMI', 'admin', 'admin', 'OT Zone — HMI web dashboard'),
    ('InfluxDB', 'root', '', 'OT Zone — Historian, no auth configured');

-- VPN config table (discoverable via SSRF chain or direct DB access)
CREATE TABLE IF NOT EXISTS vpn_configs (
    id SERIAL PRIMARY KEY,
    vpn_name VARCHAR(50),
    endpoint VARCHAR(100),
    username VARCHAR(50),
    password VARCHAR(100),
    certificate TEXT
);

INSERT INTO vpn_configs (vpn_name, endpoint, username, password) VALUES
    ('Corporate VPN', 'vpn.psyche.local:443', 'vpnadmin', 'VPN@dmin2024!'),
    ('Remote Access', 'ra.psyche.local:1194', 'remoteuser', 'R3m0te!Access');

-- Grant read access to ensure the vuln is discoverable
GRANT SELECT ON ALL TABLES IN SCHEMA public TO PUBLIC;
