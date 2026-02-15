# =============================================================================
# Exchange/Mail Simulator — Cyber Range Tier 3
# =============================================================================
# DO NOT deploy outside the cyber-range. Every flaw is intentional.
#
# Simulates Exchange OWA + SMTP with ProxyShell/ProxyLogon attack surface.
# Built as a Python Flask app mimicking Exchange endpoints.
#
# Vulnerabilities:
#   AD-23  ProxyShell chain (SSRF → RCE)
#   AD-24  ProxyLogon (pre-auth RCE)
#   AD-25  Global Address List enumeration
#   AD-26  Autodiscover credential harvesting
#   AD-27  EWS API abuse with domain creds
#   AD-28  Internal phishing relay
# =============================================================================

FROM python:3.11-slim

RUN pip install --no-cache-dir flask requests gunicorn

COPY app.py /app/app.py

WORKDIR /app

EXPOSE 443 25

# Run with gunicorn (self-signed TLS for OWA simulation)
COPY entrypoint-exchange.sh /entrypoint-exchange.sh
RUN chmod +x /entrypoint-exchange.sh

ENTRYPOINT ["/entrypoint-exchange.sh"]
