#!/bin/sh
# Turns the add-on options (/data/options.json) into MIH_* variables and starts MIH.
set -eu

env_lines="$(python3 /usr/local/lib/mirtv/mirtv_env.py)"
eval "$env_lines"

echo "MIRTVONLINE: profile ${MIRTV_PROFILE}," \
     "language ${MIH_LANG}, time zone ${MIH_TIMEZONE}"
exec mih serve
