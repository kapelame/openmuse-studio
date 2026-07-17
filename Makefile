.PHONY: setup start stop status dev worker test lint render-demo down one-click

setup:
	uv sync
	npm --prefix apps/web install
	cp -n .env.example .env || true

start:
	./start.sh

one-click:
	./start.sh

stop:
	./stop.sh

status:
	./status.sh

dev:
	@echo "Start API: uv run uvicorn openmuse_api.main:app --app-dir apps/api --reload"
	@echo "Start web: npm --prefix apps/web run dev"

worker:
	PYTHONPATH=apps/api:. uv run python -m openmuse_api.worker

test:
	uv run pytest

lint:
	uv run python -m compileall apps/api cli tests
	npm --prefix apps/web run typecheck

render-demo:
	uv run openmuse pipeline --audio examples/demo-tone.wav --cover examples/demo-cover.png --lyrics examples/demo.srt --template editorial-lyrics --aspect 1:1 --output examples/rendered

down:
	docker compose down
