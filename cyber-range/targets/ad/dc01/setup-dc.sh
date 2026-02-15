#!/bin/bash
# =============================================================================
# DC01 Setup — Provisions Samba AD DC with intentional vulnerabilities
# =============================================================================
set -e

DOMAIN="PSYCHE"
REALM="PSYCHE.LOCAL"
ADMIN_PASS="${ADMIN_PASS:-P@ssw0rd123!}"

# Skip provisioning if already done
if [ -f /var/lib/samba/.provisioned ]; then
    echo "[dc01] Already provisioned, starting services..."
    exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
fi

echo "[dc01] Provisioning Samba AD DC for ${REALM}..."

# Remove default config
rm -f /etc/samba/smb.conf

# Provision the domain
samba-tool domain provision \
    --use-rfc2307 \
    --realm="${REALM}" \
    --domain="${DOMAIN}" \
    --server-role=dc \
    --dns-backend=SAMBA_INTERNAL \
    --adminpass="${ADMIN_PASS}" \
    --option="ldap server require strong auth = no" \
    --option="server signing = disabled" \
    --option="server min protocol = NT1"

# Kerberos config
cp /var/lib/samba/private/krb5.conf /etc/krb5.conf

# AD-04: Disable LDAP signing requirement
cat >> /etc/samba/smb.conf <<'EOF'

# AD-04: LDAP signing not required (intentional vuln)
[global]
    ldap server require strong auth = no
    server signing = disabled
    # AD-11: SMB signing disabled (NTLM relay)
    server signing = disabled
    client signing = disabled
    # AD-05: Weak password policy applied via samba-tool below
    # AD-09: Print spooler enabled (PrintNightmare surface)
    rpc_server:spoolss = external
    spoolss:architecture = Windows x64
    # AD-10: Netlogon — simulated via weak machine account config
    server schannel = auto
    # NT1 protocol for legacy attacks
    server min protocol = NT1
    client min protocol = NT1
EOF

# AD-05: Set weak password policy
samba-tool domain passwordsettings set \
    --min-pwd-length=4 \
    --complexity=off \
    --min-pwd-age=0 \
    --max-pwd-age=0 \
    --history-length=0

# Populate AD with vulnerable accounts/groups
/populate-ad.sh

touch /var/lib/samba/.provisioned
echo "[dc01] Provisioning complete. Starting services..."

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
