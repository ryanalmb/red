"""
Exchange OWA Simulator — Deliberately Vulnerable
=================================================
Simulates Microsoft Exchange endpoints with ProxyShell/ProxyLogon
attack surfaces for the cyber-range.

DO NOT deploy outside the cyber-range.

Vulnerabilities:
  AD-23  ProxyShell chain (SSRF via /autodiscover → RCE)
  AD-24  ProxyLogon (pre-auth SSRF via /mapi/nspi → RCE)
  AD-25  Global Address List enumeration (/oab/)
  AD-26  Autodiscover credential harvesting (/autodiscover/autodiscover.xml)
  AD-27  EWS API abuse (/ews/exchange.asmx)
  AD-28  Internal phishing relay (/owa/ mail compose)
"""

import os
import subprocess
from flask import Flask, request, jsonify, render_template_string, Response

app = Flask(__name__)

# Simulated user database (domain accounts)
USERS = {
    "da_jenkins": "JenkinsAdmin2024!",
    "jsmith": "Summer2024!",
    "jdoe": "Welcome1",
    "administrator": "P@ssw0rd123!",
    "svc_repl": "Repl1cate!",
}

# Simulated Global Address List (AD-25)
GAL = [
    {"name": "John Smith", "email": "jsmith@psyche.local", "title": "IT Administrator"},
    {"name": "Jane Doe", "email": "jdoe@psyche.local", "title": "HR Manager"},
    {"name": "Bob Wilson", "email": "bwilson@psyche.local", "title": "Developer"},
    {"name": "Ana Garcia", "email": "agarcia@psyche.local", "title": "Finance Director"},
    {"name": "Ming Chen", "email": "mchen@psyche.local", "title": "Security Analyst"},
    {"name": "Jenkins Admin", "email": "da_jenkins@psyche.local", "title": "Domain Admin"},
    {"name": "SVC Replication", "email": "svc_repl@psyche.local", "title": "Service Account"},
    {"name": "Administrator", "email": "administrator@psyche.local", "title": "Domain Admin"},
]


@app.route("/")
def index():
    return render_template_string("""
    <html><head><title>Outlook Web Access</title></head>
    <body><h1>PSYCHE.LOCAL — Outlook Web Access</h1>
    <p>Microsoft Exchange Server 2019</p>
    <a href="/owa/">Sign In</a></body></html>
    """)


@app.route("/owa/", methods=["GET", "POST"])
def owa_login():
    """OWA Login — accepts domain credentials."""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = username.replace("PSYCHE\\\\", "").replace("psyche.local\\\\", "")
        if user in USERS and USERS[user] == password:
            return jsonify({"status": "authenticated", "user": user, "mailbox": f"{user}@psyche.local"})
        return jsonify({"status": "denied", "error": "Invalid credentials"}), 401
    return render_template_string("""
    <html><head><title>OWA Login</title></head><body>
    <h2>PSYCHE.LOCAL - Sign In</h2>
    <form method="POST">
        <label>Domain\\Username:</label><br>
        <input name="username" placeholder="PSYCHE\\username"><br>
        <label>Password:</label><br>
        <input name="password" type="password"><br><br>
        <button type="submit">Sign In</button>
    </form></body></html>
    """)


# AD-23: ProxyShell — SSRF via autodiscover
@app.route("/autodiscover/autodiscover.xml", methods=["GET", "POST"])
def autodiscover():
    """
    AD-26: Autodiscover credential harvesting.
    AD-23: ProxyShell SSRF — the 'Email' header is used to SSRF.
    """
    email = request.headers.get("X-Autodiscover-Email", "")
    # AD-23: SSRF — if the email contains a URL, we'll fetch it (simulated ProxyShell)
    if email.startswith("http://") or email.startswith("https://"):
        try:
            import urllib.request
            resp = urllib.request.urlopen(email, timeout=5)
            return Response(resp.read(), content_type="text/xml")
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    # AD-26: Return autodiscover config (leaks internal server names)
    xml = f"""<?xml version="1.0" encoding="utf-8"?>
    <Autodiscover xmlns="http://schemas.microsoft.com/exchange/autodiscover/outlook/responseschema/2006a">
      <Response>
        <Account>
          <AccountType>email</AccountType>
          <Action>settings</Action>
          <Protocol><Type>EXPR</Type><Server>exchange.psyche.local</Server>
            <SSL>on</SSL><AuthPackage>Basic</AuthPackage></Protocol>
          <Protocol><Type>EXCH</Type><Server>exchange.psyche.local</Server>
            <AuthPackage>Ntlm</AuthPackage><ServerDN>/o=PSYCHE/ou=Exchange Administrative Group/cn=Configuration/cn=Servers/cn=EXCHANGE01</ServerDN></Protocol>
        </Account>
      </Response>
    </Autodiscover>"""
    return Response(xml, content_type="text/xml")


# AD-24: ProxyLogon — pre-auth SSRF via /mapi/nspi
@app.route("/mapi/nspi/", methods=["GET", "POST"])
def proxylogon():
    """AD-24: ProxyLogon SSRF — accepts SSRF target in cookie."""
    target = request.cookies.get("X-BEResource", "")
    if target and (target.startswith("http://") or target.startswith("https://")):
        try:
            import urllib.request
            resp = urllib.request.urlopen(target, timeout=5)
            return Response(resp.read(), content_type="application/json")
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    return jsonify({"endpoint": "/mapi/nspi/", "status": "Exchange MAPI endpoint", "version": "15.2.986.5"})


# AD-25: Global Address List enumeration
@app.route("/oab/", methods=["GET"])
@app.route("/oab/<path:subpath>", methods=["GET"])
def oab(subpath=""):
    """AD-25: OAB (Offline Address Book) — leaks GAL without auth."""
    return jsonify({"global_address_list": GAL, "count": len(GAL), "domain": "PSYCHE.LOCAL"})


# AD-27: EWS API abuse
@app.route("/ews/exchange.asmx", methods=["GET", "POST"])
def ews():
    """AD-27: EWS endpoint — accepts SOAP requests with domain credentials."""
    auth = request.authorization
    if auth and auth.username in USERS and USERS.get(auth.username) == auth.password:
        if request.method == "POST":
            body = request.get_data(as_text=True)
            # Simulate mailbox search — return "sensitive" data
            if "FindItem" in body or "GetItem" in body:
                return Response("""<?xml version="1.0"?>
                <Envelope><Body><FindItemResponse><Items>
                  <Message><Subject>VPN Credentials</Subject>
                    <Body>VPN: vpn.psyche.local, user: vpnadmin, pass: VPN@dmin2024!</Body></Message>
                  <Message><Subject>OT Access</Subject>
                    <Body>SCADA HMI: admin/admin, Historian: no auth needed on port 8086</Body></Message>
                </Items></FindItemResponse></Body></Envelope>""", content_type="text/xml")
        return jsonify({"service": "EWS", "authenticated_as": auth.username, "actions": ["FindItem", "GetItem", "SendItem"]})
    return Response("Unauthorized", status=401, headers={"WWW-Authenticate": 'Basic realm="PSYCHE"'})


# AD-28: Internal phishing relay
@app.route("/owa/compose", methods=["POST"])
def send_mail():
    """AD-28: Send internal mail — no validation on sender."""
    to = request.form.get("to", "")
    subject = request.form.get("subject", "")
    body = request.form.get("body", "")
    # Just log it — demonstrates phishing relay capability
    return jsonify({"status": "sent", "to": to, "subject": subject, "note": "No sender validation — phishing possible"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=443, ssl_context="adhoc")
