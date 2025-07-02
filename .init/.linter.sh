#!/bin/bash
cd /home/kavia/workspace/code-generation/triviaarena-94560-b75d1f92/quiz_realm_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

