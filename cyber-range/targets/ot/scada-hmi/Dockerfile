# =============================================================================
# SCADA/HMI Simulator — Cyber Range Tier 4 (OT/Restricted)
# =============================================================================
# DO NOT deploy outside the cyber-range. Every flaw is intentional.
#
# Python-based Modbus TCP server + OPC-UA server + Web HMI dashboard.
#
# Vulnerabilities:
#   OT-01  Modbus no authentication
#   OT-02  OPC-UA anonymous access
#   OT-03  HMI default credentials (admin/admin)
#   OT-04  HMI command injection via setpoint
#   OT-05  Modbus coil/register read without auth
#   OT-06  Firmware version disclosure
#   OT-07  Cleartext Modbus protocol (sniffable)
#   OT-08  No rate limiting on control commands
# =============================================================================

FROM python:3.11-slim

RUN pip install --no-cache-dir \
    flask \
    pymodbus==3.5.4 \
    opcua==0.98.13

COPY app.py /app/app.py

WORKDIR /app

EXPOSE 502 4840 8443

CMD ["python3", "app.py"]
