#!/usr/bin/env bash
set -euo pipefail
cid="SELFTEST_$(date +%Y-%m-%d_%H:%M:%S)"
logger -p local0.notice -t noc_heartbeat "NOC|unit=UN1|device=COLLECTOR|check=SELFTEST|state=UP|host=127.0.0.1|cid=${cid}"
