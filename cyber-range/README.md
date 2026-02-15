# Cyber-Red Cyber Range — 4-Tier Enterprise Topology

> **Spec:** [`docs/3-solutioning/advanced-cyber-range-spec.md`](../docs/3-solutioning/advanced-cyber-range-spec.md)

A network-segmented adversarial cyber range with **19 containers**, **4 Docker networks**, and **114 vulnerabilities** across **13 targets**. Designed to validate swarm intelligence, credential chaining, director-driven strategy, and multi-stage pivoting.

## Quick Start

```bash
cd cyber-range
docker compose up -d
docker compose ps        # verify all 19 services are healthy
```

> **Requirements:** 8+ cores, 16+ GB RAM, 40+ GB disk. Recommended: 16 cores, 32 GB RAM.

## Architecture

```
KALI WORKERS ──► Tier 1: DMZ (cyber-range-net, 172.28.0.0/16)
                   │  DVWA, WordPress*, Mail, DNS, SSH, SMB, FTP, Metasploit
                   │
                   ▼ pivot via shell on DVWA or WordPress
                 Tier 2: Corporate (cyber-range-corp, 10.10.10.0/24, internal)
                   │  Jenkins, PostgreSQL, GitLab*, Flask API
                   │
                   ▼ pivot via GitLab (dual-homed)
                 Tier 3: Active Directory (cyber-range-ad, 10.10.20.0/24, internal)
                   │  DC01* (PSYCHE.LOCAL), FileServer, Exchange
                   │
                   ▼ pivot via DC01 (dual-homed)
                 Tier 4: OT/Restricted (cyber-range-ot, 10.10.30.0/24, internal)
                      SCADA-HMI, Historian (InfluxDB)

* = dual-homed pivot host
```

Workers connect **only** to `cyber-range-net`. Deeper tiers require actual pivoting through compromised dual-homed hosts.

## Services (19 total)

### Tier 1 — DMZ (direct access)

| Service | Container | Ports | Vulns | Role |
|---|---|---|---|---|
| DVWA | `cyber-range-dvwa` | 8080→80 | 12 | Web app, **pivot host** |
| DVWA DB | `cyber-range-dvwa-db` | 3306 | — | MySQL backend |
| WordPress | `cyber-range-wordpress` | 8081→80 | 10 | CMS, **pivot host** |
| WordPress DB | `cyber-range-wordpress-db` | 3307 | — | MariaDB backend |
| Mail | `cyber-range-mail` | 25, 143, 993 | 8 | Postfix + Dovecot |
| DNS | `cyber-range-dns` | 5353→53 | 6 | BIND9 (psyche.local) |
| SSH | `cyber-range-ssh` | 2222 | — | Brute-force target |
| SMB | `cyber-range-smb` | 445, 139 | — | Enumeration target |
| FTP | `cyber-range-ftp` | 21, 20 | — | Anonymous access |
| Metasploit | `cyber-range-metasploit` | 55553 | — | Intelligence RPC |

### Tier 2 — Corporate (behind pivot)

| Service | Container | Ports | Vulns | Role |
|---|---|---|---|---|
| Jenkins | `cyber-range-jenkins` | 8080 | 10 | CI/CD, script console RCE |
| PostgreSQL | `cyber-range-postgres` | 5432 | 8 | Trust auth, COPY RCE |
| GitLab | `cyber-range-gitlab` | 8082 | 10 | ExifTool RCE, **pivot host** |
| Flask API | `cyber-range-flask-api` | 5000 | 8 | SSTI, JWT, debug console |

### Tier 3 — Active Directory (behind 2nd pivot)

| Service | Container | Ports | Vulns | Role |
|---|---|---|---|---|
| DC01 | `cyber-range-dc01` | 88, 135, 389, 445, 636 | 14 | Samba AD DC, **pivot host** |
| FileServer | `cyber-range-fileserver` | 139, 445 | 8 | Weak shares, passwords.xlsx |
| Exchange | `cyber-range-exchange` | 443 | 6 | OWA, ProxyShell/ProxyLogon |

### Tier 4 — OT/Restricted (behind 3rd pivot)

| Service | Container | Ports | Vulns | Role |
|---|---|---|---|---|
| SCADA-HMI | `cyber-range-scada-hmi` | 502, 4840, 8443 | 8 | Modbus + OPC-UA + Web HMI |
| Historian | `cyber-range-historian` | 8086 | 6 | InfluxDB, no auth |

## Vulnerability Counts

| Tier | Targets | Vulns | ID Range |
|---|---|---|---|
| DMZ | 4 | 36 | DMZ-01 → DMZ-36 |
| Corporate | 4 | 36 | CORP-01 → CORP-36 |
| Active Directory | 3 | 28 | AD-01 → AD-28 |
| OT/Restricted | 2 | 14 | OT-01 → OT-14 |
| **Total** | **13** | **114** | |

## Credential Chains

Credentials discovered in one tier unlock access to the next:

```
DMZ-12 (DVWA admin/password) ──► Shell ──► Pivot to Tier 2
DMZ-27 (Mail user1/password1) ──► Email with Jenkins creds ──► CORP-03
DMZ-18 (wp-config.php) ──► MariaDB ──► reused password ──► GitLab
CORP-05 (Jenkins LDAP pass) ──► AD-06 (Domain Admin da_jenkins)
CORP-15 (PostgreSQL user table) ──► Domain user ──► AD-01 (AS-REP Roast)
CORP-26 (GitLab .env) ──► svc_repl ──► AD-07 (DCSync)
AD-08 (GPP cpassword) ──► AD-20 (localadmin on FileServer)
AD-16 (passwords.xlsx) ──► OT-03 (HMI admin/admin)
AD-07 (DCSync) ──► AD-12 (Golden Ticket via KRBTGT)
OT-03 (HMI login) ──► OT-04 (command injection ──► full OT control)
```

## Graduation Benchmarks

| Level | Coverage | Objectives | Time | Grade |
|---|---|---|---|---|
| **Bronze** | 80%+ (91/114) | O1–O3 (Tier 1 shell) | < 15 min | Minimum viable |
| **Silver** | 90%+ (103/114) | O1–O5 (Domain creds) | < 12 min | Production-ready |
| **Gold** | 95%+ (108/114) | O1–O7 (Full chain) | < 10 min | **Target** |
| **Platinum** | 98%+ (112/114) | O1–O7 + E1–E5 | < 8 min | Exceeds expectations |

## Key Files

| File | Purpose |
|---|---|
| `docker-compose.yml` | All 19 services, 4 networks |
| `expected-findings.json` | Ground truth: 114 vulns with IDs, severity, detection tools |
| `emergence-baseline.json` | Scoring framework, graduation benchmarks, regression criteria |
| `targets/` | Dockerfiles and configs for custom targets |

## Networks

| Network | Subnet | Internal | Access |
|---|---|---|---|
| `cyber-range-net` | 172.28.0.0/16 | No | Direct from workers |
| `cyber-range-corp` | 10.10.10.0/24 | Yes | Via DVWA/WordPress pivot |
| `cyber-range-ad` | 10.10.20.0/24 | Yes | Via GitLab pivot |
| `cyber-range-ot` | 10.10.30.0/24 | Yes | Via DC01 pivot |

## Default Credentials

| Target | Username | Password | Notes |
|---|---|---|---|
| DVWA | admin | password | DMZ-12 |
| WordPress | admin | admin123 | DMZ-22 |
| Mail (IMAP) | user1 | password1 | DMZ-27, contains Jenkins creds |
| Jenkins | admin | admin | CORP-03, setup wizard disabled |
| PostgreSQL | postgres | postgres | CORP-12, trust auth |
| GitLab | root | 5iveL!fe | CORP-21 |
| Flask API | — | supersecret | CORP-29, JWT secret |
| DC01 | Administrator | P@ssw0rd123! | Domain Admin |
| DC01 | da_jenkins | JenkinsAdmin2024! | AD-06, reused from Jenkins |
| FileServer | localadmin | Admin123! | AD-20 |
| SCADA HMI | admin | admin | OT-03 |
| Historian | — | — | OT-09, no auth |
