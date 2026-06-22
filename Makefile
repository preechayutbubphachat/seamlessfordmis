PYTHON ?= python

.PHONY: backend-init backend-seed backend-migrate

backend-init:
	cd backend && $(PYTHON) -m alembic upgrade head

backend-seed:
	cd backend && $(PYTHON) -m app.seeds.disease_mapping_seed

backend-migrate:
	cd backend && $(PYTHON) -m alembic revision --autogenerate -m "update schema"
