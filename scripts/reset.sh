#!/bin/sh
# Remet le système en homéostasie entre deux démos (lève throttle, bans, suspensions, verrouillages)
cd "$(dirname "$0")/.." || exit 1
docker compose exec -T remediator python -m app.reset
