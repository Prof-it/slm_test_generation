#!/bin/bash
# Run on vast.ai instance start. Output goes to /var/log/onstart.log

cd /app

nohup python step3_modelling/run_realworld_experiments_v2.py --strategies linecov2 >> /workspace/run_v2.log 2>&1 &
echo "run_realworld_experiments_v2.py (linecov2 only) started with PID $!"
