.PHONY: up down test test-unit test-integration

up:
	docker compose up --build

down:
	docker compose down

test: test-unit test-integration

test-unit:
	pytest -m unit -v

test-integration:
	pytest -m integration -v
