.PHONY: up down logs test

up:
	docker compose up --build -d
	@echo "Backend:  http://localhost:8000/health"
	@echo "Frontend: http://localhost:3000"

down:
	docker compose down

logs:
	docker compose logs -f

test:
	cd backend && python -m pytest -q tests
