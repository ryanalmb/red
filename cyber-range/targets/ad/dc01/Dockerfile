# =============================================================================
# Domain Controller (DC01) — Samba AD DC — Cyber Range Tier 3
# =============================================================================
# DO NOT deploy outside the cyber-range. Every flaw is intentional.
#
# Domain: PSYCHE.LOCAL
# Dual-homed: cyber-range-ad + cyber-range-ot (pivot to Tier 4)
#
# Vulnerabilities:
#   AD-01  AS-REP Roasting (5 accounts, no preauth)
#   AD-02  Kerberoasting (3 SPNs with weak passwords)
#   AD-03  Unconstrained delegation on FILESERVER
#   AD-04  LDAP signing not required
#   AD-05  Password policy: min 4 chars, no complexity
#   AD-06  Domain admin password reuse from Jenkins (CORP-05)
#   AD-07  DCSync rights on compromised service account
#   AD-08  GPP passwords in SYSVOL
#   AD-09  PrintNightmare (Print Spooler enabled)
#   AD-10  ZeroLogon (Netlogon — simulated via weak config)
#   AD-11  NTLM relay (SMB signing disabled)
#   AD-12  Golden Ticket possibility (KRBTGT weak)
#   AD-13  LAPS not deployed
#   AD-14  AdminSDHolder ACL abuse
# =============================================================================

FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV DOMAIN=PSYCHE.LOCAL
ENV REALM=PSYCHE.LOCAL
ENV ADMIN_PASS=P@ssw0rd123!

RUN apt-get update && apt-get install -y --no-install-recommends \
    samba \
    samba-dsdb-modules \
    samba-vfs-modules \
    winbind \
    krb5-user \
    krb5-kdc \
    ldap-utils \
    ldb-tools \
    python3 \
    python3-samba \
    dnsutils \
    net-tools \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY setup-dc.sh /setup-dc.sh
COPY populate-ad.sh /populate-ad.sh
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
RUN chmod +x /setup-dc.sh /populate-ad.sh

EXPOSE 53 88 135 139 389 445 464 636 3268 3269

ENTRYPOINT ["/setup-dc.sh"]
