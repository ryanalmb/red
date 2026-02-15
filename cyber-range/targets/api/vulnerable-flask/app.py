# =============================================================================
# Deliberately Vulnerable Flask REST API — Cyber Range Tier 2
# =============================================================================
# DO NOT deploy outside the cyber-range. Every flaw is intentional.
#
# Vulnerabilities:
#   FLASK-IDOR-001   IDOR on /api/users/<id> — any user can read any profile
#   FLASK-JWT-001    JWT signed with weak secret ("supersecret")
#   FLASK-MASS-001   Mass assignment — PUT /api/users/<id> overwrites role
#   FLASK-SSRF-001   SSRF via /api/fetch — fetches arbitrary server-side URLs
#   FLASK-DEBUG-001  Werkzeug debugger enabled (interactive RCE)
#   FLASK-KEY-001    Hardcoded API key in source code
#   FLASK-BRUTE-001  No rate limiting on /api/login
# =============================================================================

import json
import urllib.request

import jwt
from flask import Flask, jsonify, request

app = Flask(__name__)

# ---- Hardcoded secrets (intentional) ----------------------------------------
JWT_SECRET = "supersecret"
API_KEY = "sk-mantis-hardcoded-key-12345"

# ---- In-memory user store ----------------------------------------------------
USERS = {
    1: {"id": 1, "username": "admin", "password": "admin", "role": "admin",
        "email": "admin@corp.local", "ssn": "123-45-6789"},
    2: {"id": 2, "username": "alice", "password": "password123", "role": "user",
        "email": "alice@corp.local", "ssn": "987-65-4321"},
    3: {"id": 3, "username": "bob", "password": "bob2024", "role": "user",
        "email": "bob@corp.local", "ssn": "555-12-3456"},
}
_next_id = 4


def _issue_token(user_id: int, role: str) -> str:
    return jwt.encode({"user_id": user_id, "role": role}, JWT_SECRET, algorithm="HS256")


def _decode_token():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        return jwt.decode(auth[7:], JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None


# ---- Routes ------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/login", methods=["POST"])
def login():
    """No rate limiting — brute-forceable."""
    data = request.get_json(force=True, silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    for user in USERS.values():
        if user["username"] == username and user["password"] == password:
            return jsonify({"token": _issue_token(user["id"], user["role"])})
    return jsonify({"error": "invalid credentials"}), 401


@app.route("/api/users/<int:user_id>")
def get_user(user_id: int):
    """IDOR — any authenticated user can read any other user's PII."""
    if _decode_token() is None:
        return jsonify({"error": "unauthorized"}), 401
    user = USERS.get(user_id)
    if user is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(user)  # leaks password, SSN — intentional


@app.route("/api/users/<int:user_id>", methods=["PUT"])
def update_user(user_id: int):
    """Mass assignment — caller can overwrite role to escalate privileges."""
    if _decode_token() is None:
        return jsonify({"error": "unauthorized"}), 401
    user = USERS.get(user_id)
    if user is None:
        return jsonify({"error": "not found"}), 404
    data = request.get_json(force=True, silent=True) or {}
    user.update(data)  # blindly merges all fields
    return jsonify(user)


@app.route("/api/users", methods=["POST"])
def create_user():
    """Mass assignment on creation — caller can set role=admin."""
    global _next_id
    if _decode_token() is None:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    data["id"] = _next_id
    data.setdefault("role", "user")
    USERS[_next_id] = data
    _next_id += 1
    return jsonify(data), 201


@app.route("/api/fetch", methods=["POST"])
def fetch_url():
    """SSRF — fetches arbitrary URLs from the server side."""
    if _decode_token() is None:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(force=True, silent=True) or {}
    url = data.get("url", "")
    if not url:
        return jsonify({"error": "url required"}), 400
    try:
        resp = urllib.request.urlopen(url, timeout=5)
        body = resp.read().decode("utf-8", errors="replace")[:4096]
        return jsonify({"status": resp.status, "body": body})
    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/config")
def config():
    """Exposes API key — information disclosure."""
    return jsonify({"api_key": API_KEY, "debug": app.debug, "jwt_alg": "HS256"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)  # Werkzeug debugger enabled
