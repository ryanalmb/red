# =============================================================================
# File Server (FILESERVER01) — Samba — Cyber Range Tier 3
# =============================================================================
# DO NOT deploy outside the cyber-range. Every flaw is intentional.
#
# Joined to PSYCHE.LOCAL domain (simulated via standalone Samba with weak config).
#
# Vulnerabilities:
#   AD-15  Open shares (no auth required)
#   AD-16  Sensitive docs in public share (passwords.xlsx)
#   AD-17  SMBv1 enabled (EternalBlue surface)
#   AD-18  Writable SYSVOL share
#   AD-19  Unconstrained delegation token capture
#   AD-20  Local admin credential reuse
#   AD-21  SAM database accessible via admin share
#   AD-22  SSH private keys in user home directories
# =============================================================================

FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    samba samba-common-bin bash openssh-client netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create users with reused credentials (AD-20)
RUN useradd -m -s /bin/bash localadmin && echo "localadmin:Admin123!" | chpasswd
RUN useradd -m -s /bin/bash jsmith && echo "jsmith:Summer2024!" | chpasswd
RUN useradd -m -s /bin/bash svc_backup && echo "svc_backup:backup1" | chpasswd

# Samba config — intentionally insecure
COPY smb.conf /etc/samba/smb.conf

# Set Samba passwords
RUN printf "Admin123!\nAdmin123!\n" | smbpasswd -a -s localadmin && \
    printf "Summer2024!\nSummer2024!\n" | smbpasswd -a -s jsmith && \
    printf "backup1\nbackup1\n" | smbpasswd -a -s svc_backup

# AD-15 + AD-16: Create public share with sensitive documents
RUN mkdir -p /srv/shares/public /srv/shares/finance /srv/shares/it /srv/shares/sysvol

# AD-16: passwords.xlsx (simulated as CSV — contains OT credentials)
RUN echo "System,Username,Password,Notes" > /srv/shares/public/passwords.xlsx && \
    echo "HMI-SCADA,admin,admin,OT Zone HMI login" >> /srv/shares/public/passwords.xlsx && \
    echo "InfluxDB,root,,No auth configured" >> /srv/shares/public/passwords.xlsx && \
    echo "Jenkins,admin,admin,CI/CD server" >> /srv/shares/public/passwords.xlsx && \
    echo "PostgreSQL,postgres,postgres,Corporate DB" >> /srv/shares/public/passwords.xlsx && \
    echo "DC01-Admin,da_jenkins,JenkinsAdmin2024!,Domain Admin" >> /srv/shares/public/passwords.xlsx

# Other sensitive files in finance share
RUN echo "Q4 2025 Revenue: $4.2M\nPayroll DB: postgres://payroll:Pay2025!@postgres:5432/payroll" > /srv/shares/finance/q4-report.txt

# AD-22: SSH private keys in user home directories
RUN mkdir -p /home/jsmith/.ssh && \
    ssh-keygen -t rsa -b 2048 -f /home/jsmith/.ssh/id_rsa -N "" -q && \
    echo "# This key grants access to gitlab and jenkins servers" > /home/jsmith/.ssh/config && \
    chown -R jsmith:jsmith /home/jsmith

# AD-18: Writable SYSVOL with GPP content
RUN echo "This is a writable SYSVOL share — AD-18" > /srv/shares/sysvol/README.txt

# AD-21: SAM database — accessible via admin share (Samba creates this)
# The SAM is at /var/lib/samba/private/passdb.tdb

# Set permissions — intentionally loose
RUN chmod -R 777 /srv/shares/public && \
    chmod -R 755 /srv/shares/finance && \
    chmod -R 777 /srv/shares/sysvol

EXPOSE 139 445

COPY entrypoint-fs.sh /entrypoint-fs.sh
RUN chmod +x /entrypoint-fs.sh

ENTRYPOINT ["/entrypoint-fs.sh"]
