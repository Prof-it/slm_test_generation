#!/bin/bash
# This file is run on instance start by vast.ai. Output in /var/log/onstart.log

cd /app
nohup python step3_modelling/run_experiments.py > /workspace/run1.log 2>&1 &
echo "run_experiments.py started with PID $!"
