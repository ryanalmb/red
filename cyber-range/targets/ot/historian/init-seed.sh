#!/bin/bash
# =============================================================================
# InfluxDB Historian Seed Data — Cyber Range Tier 4 (OT)
# =============================================================================
# Pre-populates the scada_data database with fake SCADA telemetry.
# Makes OT-09 (no auth) and OT-10 (data exfiltration) immediately testable.
#
# Run after historian container is healthy:
#   docker exec cyber-range-historian /seed/init-seed.sh
#
# Or mount as entrypoint wrapper.
# DO NOT deploy outside the cyber-range.
# =============================================================================
set -e

INFLUX_URL="${INFLUX_URL:-http://localhost:8086}"
DB="scada_data"

echo "[historian-seed] Waiting for InfluxDB..."
for i in $(seq 1 30); do
    if curl -sf "${INFLUX_URL}/ping" > /dev/null 2>&1; then
        break
    fi
    sleep 2
done

echo "[historian-seed] Creating database '${DB}'..."
curl -sf -X POST "${INFLUX_URL}/query" --data-urlencode "q=CREATE DATABASE ${DB}" > /dev/null

echo "[historian-seed] Inserting SCADA telemetry data..."

# Generate 24 hours of fake process data (1 point per minute = 1440 points)
# Using InfluxDB line protocol
NOW=$(date +%s)
BATCH=""
for i in $(seq 0 1439); do
    TS=$(( (NOW - 86400 + i * 60) * 1000000000 ))  # nanoseconds

    # Simulate realistic process values with some variation
    TEMP=$(python3 -c "import random; print(f'{70 + random.gauss(0, 3):.1f}')" 2>/dev/null || echo "72.5")
    PRESSURE=$(python3 -c "import random; print(f'{14.7 + random.gauss(0, 0.5):.2f}')" 2>/dev/null || echo "14.70")
    FLOW=$(python3 -c "import random; print(f'{125 + random.gauss(0, 10):.1f}')" 2>/dev/null || echo "125.0")
    TANK=$(python3 -c "import random; print(f'{max(0, min(100, 65 + random.gauss(0, 5))):.1f}')" 2>/dev/null || echo "65.0")

    BATCH="${BATCH}temperature,unit=degF,sensor=T-001 value=${TEMP} ${TS}
pressure,unit=PSI,sensor=P-001 value=${PRESSURE} ${TS}
flow_rate,unit=GPM,sensor=F-001 value=${FLOW} ${TS}
tank_level,unit=percent,sensor=L-001 value=${TANK} ${TS}
"

    # Write in batches of 200 points (50 timestamps × 4 measurements)
    if [ $(( (i + 1) % 50 )) -eq 0 ]; then
        curl -sf -X POST "${INFLUX_URL}/write?db=${DB}" --data-binary "${BATCH}" > /dev/null
        BATCH=""
    fi
done

# Write remaining
if [ -n "$BATCH" ]; then
    curl -sf -X POST "${INFLUX_URL}/write?db=${DB}" --data-binary "${BATCH}" > /dev/null
fi

# Add alarm events
echo "[historian-seed] Inserting alarm history..."
curl -sf -X POST "${INFLUX_URL}/write?db=${DB}" --data-binary "
alarms,severity=HIGH,source=T-001 message=\"Temperature exceeded upper limit\",value=85.3 $((( NOW - 3600 ) * 1000000000))
alarms,severity=CRITICAL,source=P-001 message=\"Pressure spike detected\",value=18.9 $((( NOW - 7200 ) * 1000000000))
alarms,severity=LOW,source=L-001 message=\"Tank level below 20%\",value=18.5 $((( NOW - 14400 ) * 1000000000))
alarms,severity=HIGH,source=F-001 message=\"Flow rate anomaly\",value=0.0 $((( NOW - 21600 ) * 1000000000))
" > /dev/null

# Add operator actions log (shows who did what — sensitive)
echo "[historian-seed] Inserting operator action log..."
curl -sf -X POST "${INFLUX_URL}/write?db=${DB}" --data-binary "
operator_log,user=admin,action=setpoint message=\"Set temperature target to 75F\" $((( NOW - 1800 ) * 1000000000))
operator_log,user=operator,action=acknowledge message=\"Acknowledged pressure alarm\" $((( NOW - 5400 ) * 1000000000))
operator_log,user=admin,action=override message=\"Emergency valve override activated\" $((( NOW - 10800 ) * 1000000000))
operator_log,user=admin,action=login message=\"HMI login from 10.10.20.10 (DC01)\" $((( NOW - 43200 ) * 1000000000))
" > /dev/null

echo "[historian-seed] Seed complete."
echo "[historian-seed] Database: ${DB}"
echo "[historian-seed] Measurements: temperature, pressure, flow_rate, tank_level, alarms, operator_log"
echo "[historian-seed] Data points: ~5760 (24h × 4 sensors @ 1/min) + alarms + operator log"
