#!/bin/bash
# Run on vast.ai instance start. Output goes to /var/log/onstart.log

cd /app

# Quick smoke test first (1 model, Tier A only) to catch env issues early
echo "=== Smoke test ===" >> /workspace/run_v2.log 2>&1
python step3_modelling/run_realworld_experiments_v2.py --quick-test >> /workspace/run_v2.log 2>&1
echo "=== Smoke test complete ===" >> /workspace/run_v2.log 2>&1

# Full run: all 5 models × tiers A/B/C
nohup python step3_modelling/run_realworld_experiments_v2.py >> /workspace/run_v2.log 2>&1 &
echo "run_realworld_experiments_v2.py started with PID $!"
