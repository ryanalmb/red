#!/bin/bash
# =============================================================================
# Populate PSYCHE.LOCAL AD with vulnerable accounts, SPNs, and ACLs
# =============================================================================
REALM="PSYCHE.LOCAL"
ADMIN_PASS="${ADMIN_PASS:-P@ssw0rd123!}"

echo "[dc01] Creating user accounts..."

# Regular users (some with weak passwords)
samba-tool user create jsmith 'Summer2024!' --given-name=John --surname=Smith
samba-tool user create jdoe 'Welcome1' --given-name=Jane --surname=Doe
samba-tool user create bwilson 'Password1' --given-name=Bob --surname=Wilson
samba-tool user create agarcia 'Company1' --given-name=Ana --surname=Garcia
samba-tool user create mchen 'Qwerty123' --given-name=Ming --surname=Chen

# AD-01: AS-REP Roasting — disable preauth on 5 accounts
for user in jsmith jdoe bwilson agarcia mchen; do
    samba-tool user setpassword "$user" --newpassword="$(samba-tool user getpassword "$user" 2>/dev/null || echo 'keep')" 2>/dev/null || true
    # Disable Kerberos preauth via ldbedit
    ldbmodify -H /var/lib/samba/private/sam.ldb <<EOF
dn: CN=${user},CN=Users,DC=psyche,DC=local
changetype: modify
replace: userAccountControl
userAccountControl: 4194816
EOF
done

# Service accounts with SPNs (AD-02: Kerberoasting targets)
samba-tool user create svc_sql 'sql123' --given-name=SVC --surname=SQL
samba-tool user create svc_web 'web123' --given-name=SVC --surname=Web
samba-tool user create svc_backup 'backup1' --given-name=SVC --surname=Backup

# Set SPNs for Kerberoasting
samba-tool spn add MSSQLSvc/sqlserver.psyche.local:1433 svc_sql
samba-tool spn add HTTP/webserver.psyche.local svc_web
samba-tool spn add CIFS/backup.psyche.local svc_backup

# AD-06: Domain admin with password reused from Jenkins (CORP-05)
samba-tool user create da_jenkins 'JenkinsAdmin2024!' --given-name=Jenkins --surname=Admin
samba-tool group addmembers "Domain Admins" da_jenkins

# AD-07: Service account with DCSync rights (Replicating Directory Changes)
samba-tool user create svc_repl 'Repl1cate!' --given-name=SVC --surname=Replication
# Grant DCSync (Replicating Directory Changes + Replicating Directory Changes All)
DOMAIN_DN="DC=psyche,DC=local"
ldbmodify -H /var/lib/samba/private/sam.ldb <<EOF
dn: ${DOMAIN_DN}
changetype: modify
add: nTSecurityDescriptor
nTSecurityDescriptor: O:DAG:DAD:(A;;CR;1131f6aa-9c07-11d1-f79f-00c04fc2dcd2;;CN=svc_repl,CN=Users,${DOMAIN_DN})(A;;CR;1131f6ad-9c07-11d1-f79f-00c04fc2dcd2;;CN=svc_repl,CN=Users,${DOMAIN_DN})
EOF
echo "[dc01] DCSync rights granted to svc_repl (may need manual verification)"

# AD-08: GPP passwords in SYSVOL
SYSVOL="/var/lib/samba/sysvol/psyche.local"
mkdir -p "${SYSVOL}/Policies/{31B2F340-016D-11D2-945F-00C04FB984F9}/Machine/Preferences/Groups"
cat > "${SYSVOL}/Policies/{31B2F340-016D-11D2-945F-00C04FB984F9}/Machine/Preferences/Groups/Groups.xml" <<'GPPXML'
<?xml version="1.0" encoding="utf-8"?>
<Groups clsid="{3125E937-EB16-4b4c-9934-544FC6D24D26}">
  <User clsid="{DF5F1855-51E5-4d24-8B1A-D9BDE98BA1D1}" name="LocalAdmin" image="2"
        changed="2024-01-15 10:30:00" uid="{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}">
    <Properties action="U" newName="" fullName="Local Administrator"
                description="Built-in account for administering the computer"
                cpassword="edBSHOwhZLTjt/QS9FeIcJ83mjWA98gw9guKOhJOdcqh+ZGMeXOsQbCpZ3xUjTLfCuNH8pG5aSVYdYw/NglVmQ"
                changeLogon="0" noChange="0" neverExpires="1"
                acctDisabled="0" userName="localadmin"/>
  </User>
</Groups>
GPPXML

# AD-12: Weak KRBTGT password (enables Golden Ticket)
# Note: KRBTGT is auto-created; its hash being extractable via DCSync is the vuln
# We just ensure the environment makes this possible

# AD-13: LAPS not deployed (intentional omission — no remediation)
echo "[dc01] LAPS intentionally not deployed (AD-13)"

# AD-14: AdminSDHolder ACL abuse — add svc_repl to Account Operators
samba-tool group addmembers "Account Operators" svc_repl 2>/dev/null || true

echo "[dc01] AD population complete."
echo "[dc01] Users: jsmith, jdoe, bwilson, agarcia, mchen, svc_sql, svc_web, svc_backup, svc_repl, da_jenkins"
echo "[dc01] Domain Admin: da_jenkins (JenkinsAdmin2024!)"
echo "[dc01] AS-REP Roastable: jsmith, jdoe, bwilson, agarcia, mchen"
echo "[dc01] Kerberoastable SPNs: svc_sql, svc_web, svc_backup"
echo "[dc01] DCSync: svc_repl"
echo "[dc01] GPP: SYSVOL contains cpassword for localadmin"
