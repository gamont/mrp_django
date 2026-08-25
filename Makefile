.PHONY: up down build check migrate migrations migrations-check roles superuser seed mrp crp net-change test test-cov lint format shell ci

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

check:
	docker compose run --rm web python manage.py check

migrations:
	docker compose run --rm web python manage.py makemigrations

migrations-check:
	docker compose run --rm web python manage.py makemigrations --check --dry-run

migrate:
	docker compose run --rm web python manage.py migrate

roles:
	docker compose run --rm web python manage.py bootstrap_roles

superuser:
	docker compose run --rm web python manage.py createsuperuser

seed:
	docker compose run --rm web python manage.py seed_demo

mrp:
	docker compose run --rm web python manage.py run_mrp $(ARGS)

crp:
	docker compose run --rm web python manage.py run_crp $(ARGS)

net-change:
	docker compose run --rm web python manage.py run_net_change $(ARGS)

test:
	docker compose run --rm web pytest

test-cov:
	docker compose run --rm web coverage run -m pytest
	docker compose run --rm web coverage report

lint:
	docker compose run --rm web ruff check .

format:
	docker compose run --rm web ruff format .

shell:
	docker compose run --rm web python manage.py shell

ci: lint migrations-check check test
