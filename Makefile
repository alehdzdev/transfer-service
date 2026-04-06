.PHONY: up down test test-unit test-integration

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

test: test-unit test-integration

test-unit:
	pytest -m unit -v

test-integration:
	pytest -m integration -v
