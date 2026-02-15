# =============================================================================
# Deliberately Vulnerable Mail Server — Cyber Range Tier 1 (DMZ)
# =============================================================================
# DO NOT deploy outside the cyber-range. Every flaw is intentional.
#
# Lightweight Postfix + Dovecot on Alpine with intentionally weak config.
#
# Vulnerabilities:
#   DMZ-23  Open SMTP relay (no auth required to relay)
#   DMZ-24  VRFY user enumeration
#   DMZ-25  EXPN mailing list enumeration
#   DMZ-26  Cleartext authentication (no STARTTLS required)
#   DMZ-27  Weak mailbox credentials (user1/password1)
#   DMZ-28  IMAP IDLE information disclosure
#   DMZ-29  Missing SPF/DKIM/DMARC
#   DMZ-30  SMTP command injection
# =============================================================================

FROM debian:bullseye-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    postfix dovecot-imapd dovecot-pop3d bash netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create weak user accounts (DMZ-27)
RUN useradd -m -s /bin/bash user1 && echo "user1:password1" | chpasswd
RUN useradd -m -s /bin/bash admin && echo "admin:mailadmin" | chpasswd
RUN useradd -m -s /bin/bash -g nogroup mailop && echo "mailop:operator123" | chpasswd

# Postfix configuration — intentionally insecure
COPY postfix-main.cf /etc/postfix/main.cf

# Dovecot configuration — intentionally insecure
COPY dovecot.conf /etc/dovecot/dovecot.conf

# Create mailboxes
RUN mkdir -p /var/mail/user1 /var/mail/admin /var/mail/mailop \
    && chown user1:user1 /var/mail/user1 \
    && chown admin:admin /var/mail/admin \
    && chown mailop:nogroup /var/mail/mailop

# Seed a mail with Jenkins credentials (credential chain: DMZ-27 → CORP-03)
RUN mkdir -p /home/user1/Maildir/new && \
    printf "From: admin@psyche.local\nTo: user1@psyche.local\nSubject: Jenkins access\nDate: Mon, 01 Jan 2026 00:00:00 +0000\n\nHi,\n\nHere are the Jenkins credentials for the CI server:\n  URL: http://jenkins:8081\n  User: admin\n  Pass: admin\n\nPlease change the password when you get a chance.\n\n- Admin\n" > /home/user1/Maildir/new/jenkins-creds.eml && \
    chown -R user1:user1 /home/user1/Maildir

COPY entrypoint-mail.sh /entrypoint-mail.sh
RUN chmod +x /entrypoint-mail.sh

EXPOSE 25 143 993

ENTRYPOINT ["/entrypoint-mail.sh"]
