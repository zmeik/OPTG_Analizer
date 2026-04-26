#!/usr/bin/env bash
# One-command reproduction of v19 PRIMARY result: 370/491 = 75.36%.
# Also runs v20 strict ablation: 363/491 = 73.93%.

set -euo pipefail

cd "$(dirname "$0")"

# Python interpreter — prefer local venv if it exists
if [[ -x "venv/bin/python" ]]; then
  PY="venv/bin/python"
elif [[ -x "../venv/bin/python" ]]; then
  PY="../venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi

echo "============================================================"
echo "  v19 PRIMARY (CV-selected sz, full-group voter ranking)"
echo "============================================================"
"$PY" src/mmoral_gate_v19_cv_sz.py

echo ""
echo "============================================================"
echo "  v20 STRICT (per-question pool re-ranking)"
echo "============================================================"
"$PY" src/mmoral_gate_v20_per_question_pool.py

echo ""
echo "============================================================"
echo "  Reproduction complete. Expected results:"
echo "    v19 PRIMARY: 370/491 = 75.36%"
echo "    v20 STRICT:  363/491 = 73.93%"
echo "============================================================"
