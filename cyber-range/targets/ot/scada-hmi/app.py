"""
SCADA/HMI Simulator — Deliberately Vulnerable
===============================================
Simulates a SCADA system with:
  - Modbus TCP server (port 502)
  - OPC-UA server (port 4840)
  - Web HMI dashboard (port 8443)

DO NOT deploy outside the cyber-range.

Vulnerabilities:
  OT-01  Modbus no authentication
  OT-02  OPC-UA anonymous access
  OT-03  HMI default credentials (admin/admin)
  OT-04  HMI command injection via setpoint
  OT-05  Modbus coil/register read without auth
  OT-06  Firmware version disclosure
  OT-07  Cleartext Modbus protocol (sniffable)
  OT-08  No rate limiting on control commands
"""

import os
import subprocess
import threading
import time
import json
import logging

from flask import Flask, request, jsonify, render_template_string, Response

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("scada-hmi")

# ============================================================================
# Simulated Process Data
# ============================================================================

process_data = {
    "temperature": 72.5,
    "pressure": 14.7,
    "flow_rate": 125.0,
    "tank_level": 65.0,
    "valve_1": True,
    "valve_2": False,
    "pump_1": True,
    "pump_2": False,
    "emergency_stop": False,
    "firmware_version": "SCADA-SIM v2.1.3-beta",  # OT-06
    "last_command": "none",
    "command_count": 0,
}

# HMI credentials (OT-03)
HMI_USERS = {
    "admin": "admin",
    "operator": "operator",
    "viewer": "view123",
}

# ============================================================================
# Modbus TCP Server (port 502) — OT-01, OT-05, OT-07, OT-08
# ============================================================================

def start_modbus_server():
    """Start a Modbus TCP server with NO authentication (OT-01)."""
    try:
        from pymodbus.server import StartTcpServer
        from pymodbus.datastore import (
            ModbusSequentialDataBlock,
            ModbusSlaveContext,
            ModbusServerContext,
        )

        # Initialize data store with process values
        # Coils (binary) — valves, pumps, e-stop
        coils = ModbusSequentialDataBlock(0, [True, False, True, False, False] + [False] * 95)
        # Holding registers — temperature, pressure, flow, tank level
        registers = ModbusSequentialDataBlock(0, [725, 147, 1250, 650] + [0] * 96)
        # Input registers (read-only in theory, but no auth = writable too)
        input_regs = ModbusSequentialDataBlock(0, [213, 100, 0, 0] + [0] * 96)
        # Discrete inputs
        discrete = ModbusSequentialDataBlock(0, [True, True, False] + [False] * 97)

        store = ModbusSlaveContext(
            di=discrete,
            co=coils,
            hr=registers,
            ir=input_regs,
        )
        context = ModbusServerContext(slaves=store, single=True)

        log.info("[modbus] Starting Modbus TCP server on port 502 (NO AUTH — OT-01)")
        StartTcpServer(context=context, address=("0.0.0.0", 502))
    except Exception as e:
        log.error(f"[modbus] Failed to start: {e}")


# ============================================================================
# OPC-UA Server (port 4840) — OT-02
# ============================================================================

def start_opcua_server():
    """Start an OPC-UA server with anonymous access (OT-02)."""
    try:
        from opcua import Server

        server = Server()
        server.set_endpoint("opc.tcp://0.0.0.0:4840/freeopcua/server/")
        server.set_server_name("PSYCHE SCADA OPC-UA Server")

        # OT-02: Allow anonymous access
        server.set_security_policy([])

        # Register namespace
        uri = "http://psyche.local/scada"
        idx = server.register_namespace(uri)

        # Add process variables
        objects = server.get_objects_node()
        scada = objects.add_object(idx, "SCADA")

        temp = scada.add_variable(idx, "Temperature", 72.5)
        pressure = scada.add_variable(idx, "Pressure", 14.7)
        flow = scada.add_variable(idx, "FlowRate", 125.0)
        tank = scada.add_variable(idx, "TankLevel", 65.0)
        fw = scada.add_variable(idx, "FirmwareVersion", "SCADA-SIM v2.1.3-beta")

        # Make writable (no auth required)
        temp.set_writable()
        pressure.set_writable()
        flow.set_writable()
        tank.set_writable()

        log.info("[opcua] Starting OPC-UA server on port 4840 (ANONYMOUS — OT-02)")
        server.start()

        # Keep running
        while True:
            time.sleep(1)
            temp.set_value(process_data["temperature"])
            pressure.set_value(process_data["pressure"])
            flow.set_value(process_data["flow_rate"])
            tank.set_value(process_data["tank_level"])
    except Exception as e:
        log.error(f"[opcua] Failed to start: {e}")


# ============================================================================
# Web HMI Dashboard (port 8443) — OT-03, OT-04, OT-06, OT-08
# ============================================================================

app = Flask(__name__)

HMI_TEMPLATE = """
<html>
<head><title>PSYCHE SCADA HMI</title></head>
<body style="font-family: monospace; background: #1a1a2e; color: #0f0;">
<h1>&#x26A1; PSYCHE SCADA — HMI Dashboard</h1>
<h3>Firmware: {{ data.firmware_version }}</h3>
<hr>
<table border="1" cellpadding="8" style="color: #0f0; border-color: #0f0;">
<tr><th>Parameter</th><th>Value</th><th>Unit</th></tr>
<tr><td>Temperature</td><td>{{ data.temperature }}</td><td>&deg;F</td></tr>
<tr><td>Pressure</td><td>{{ data.pressure }}</td><td>PSI</td></tr>
<tr><td>Flow Rate</td><td>{{ data.flow_rate }}</td><td>GPM</td></tr>
<tr><td>Tank Level</td><td>{{ data.tank_level }}</td><td>%</td></tr>
<tr><td>Valve 1</td><td>{{ "OPEN" if data.valve_1 else "CLOSED" }}</td><td>-</td></tr>
<tr><td>Valve 2</td><td>{{ "OPEN" if data.valve_2 else "CLOSED" }}</td><td>-</td></tr>
<tr><td>Pump 1</td><td>{{ "ON" if data.pump_1 else "OFF" }}</td><td>-</td></tr>
<tr><td>Pump 2</td><td>{{ "ON" if data.pump_2 else "OFF" }}</td><td>-</td></tr>
<tr><td>E-Stop</td><td>{{ "ACTIVE" if data.emergency_stop else "INACTIVE" }}</td><td>-</td></tr>
</table>
<hr>
<h3>Control Panel</h3>
<form method="POST" action="/api/control">
<label>Setpoint Command:</label><br>
<input name="command" size="60" placeholder="e.g. SET temperature 80"><br><br>
<button type="submit" style="background: red; color: white; padding: 10px;">Execute</button>
</form>
<p>Commands: {{ data.command_count }} | Last: {{ data.last_command }}</p>
</body>
</html>
"""


@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "scada-hmi"})


@app.route("/", methods=["GET"])
def hmi_home():
    return render_template_string("<h1>PSYCHE SCADA</h1><p><a href='/login'>Login to HMI</a></p>")


@app.route("/login", methods=["GET", "POST"])
def hmi_login():
    """OT-03: Default credentials (admin/admin)."""
    if request.method == "POST":
        user = request.form.get("username", "")
        passwd = request.form.get("password", "")
        if user in HMI_USERS and HMI_USERS[user] == passwd:
            return render_template_string(HMI_TEMPLATE, data=process_data)
        return jsonify({"error": "Invalid credentials"}), 401
    return render_template_string("""
    <html><body style="font-family: monospace; background: #1a1a2e; color: #0f0;">
    <h1>PSYCHE SCADA — Login</h1>
    <form method="POST">
    <label>Username:</label><br><input name="username"><br>
    <label>Password:</label><br><input name="password" type="password"><br><br>
    <button type="submit">Login</button>
    </form></body></html>
    """)


@app.route("/api/status", methods=["GET"])
def api_status():
    """OT-06: Firmware version disclosure (no auth required)."""
    return jsonify(process_data)


@app.route("/api/control", methods=["POST"])
def api_control():
    """
    OT-04: Command injection via setpoint command.
    OT-08: No rate limiting on control commands.
    """
    command = request.form.get("command", request.json.get("command", "") if request.is_json else "")

    process_data["command_count"] += 1
    process_data["last_command"] = command

    # OT-04: Command injection — the command is passed to shell
    if command.startswith("SET "):
        parts = command.split(" ", 2)
        if len(parts) == 3:
            param, value = parts[1], parts[2]
            # Intentional command injection: value is passed unsanitized
            try:
                result = subprocess.run(
                    f"echo 'Setting {param} to {value}'",
                    shell=True,  # OT-04: shell=True with user input
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if param in process_data:
                    try:
                        process_data[param] = float(value)
                    except (ValueError, TypeError):
                        process_data[param] = value
                return jsonify({
                    "status": "executed",
                    "command": command,
                    "output": result.stdout,
                    "param": param,
                    "value": value,
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    return jsonify({"error": "Invalid command format. Use: SET <param> <value>"}), 400


@app.route("/api/registers", methods=["GET"])
def api_registers():
    """OT-05: Read all registers without authentication."""
    return jsonify({
        "registers": {
            "temperature": process_data["temperature"],
            "pressure": process_data["pressure"],
            "flow_rate": process_data["flow_rate"],
            "tank_level": process_data["tank_level"],
        },
        "coils": {
            "valve_1": process_data["valve_1"],
            "valve_2": process_data["valve_2"],
            "pump_1": process_data["pump_1"],
            "pump_2": process_data["pump_2"],
            "emergency_stop": process_data["emergency_stop"],
        },
    })


# ============================================================================
# Main — start all servers
# ============================================================================

if __name__ == "__main__":
    # Start Modbus in background thread
    modbus_thread = threading.Thread(target=start_modbus_server, daemon=True)
    modbus_thread.start()

    # Start OPC-UA in background thread
    opcua_thread = threading.Thread(target=start_opcua_server, daemon=True)
    opcua_thread.start()

    # Start Web HMI in foreground
    log.info("[hmi] Starting Web HMI on port 8443")
    app.run(host="0.0.0.0", port=8443, debug=False)
