#!/usr/bin/env bash
# Shared Noctalia compatibility hook. The guarded Largo adapter discovers native
# and sandbox executables and verifies registration; failures remain retryable.
set -euo pipefail
exec /usr/bin/python3 "$HOME/.config/oma-theme/office_hook.py"
