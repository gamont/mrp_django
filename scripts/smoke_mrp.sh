#!/usr/bin/env bash
set -euo pipefail

docker compose run --rm web python manage.py seed_demo
docker compose run --rm web python manage.py run_mrp --plant SP01 --name "1.0.0 smoke"
echo 'MRP_SMOKE_OK'
