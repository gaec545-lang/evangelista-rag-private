.PHONY: setup dev prod ingest watch stats search analyze agents health test demo deploy proposal

# === SETUP ===
setup:
	pip install -r requirements.txt
	ollama pull nomic-embed-text
	docker compose up -d qdrant
	@echo "Setup completo. Ejecuta 'make ingest' para poblar el knowledge base."

# === DESARROLLO ===
dev:
	uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8001

# === PRODUCCIÓN ===
prod:
	docker compose up -d --build

# === KNOWLEDGE BASE ===
ingest:
	python -m cli.ingest --vault-path ./evangelista-vault

watch:
	python -m cli.ingest --vault-path ./evangelista-vault --watch

stats:
	python -m cli.ingest --stats

# === BÚSQUEDA ===
search:
	python -m cli.search "$(q)" --agent $(or $(agent),financial)

# === ORQUESTADOR ===
analyze:
	python -m cli.orchestrate "$(task)"

# === AGENTES ===
agents:
	curl -s http://localhost:8001/api/v1/agents | python -m json.tool

# === HEALTH ===
health:
	curl -s http://localhost:8001/readiness | python -m json.tool

# === TESTS ===
test:
	pytest tests/ -v

# === QDRANT (standalone) ===
qdrant:
	docker compose up -d qdrant

# === PROPUESTAS ===
proposal:
	curl -s -X POST http://localhost:8001/api/v1/proposals/foundation \
		-H "Content-Type: application/json" \
		-d '{"name":"$(or $(client),Empresa Demo)","sector":"$(or $(sector),manufactura)","sucursales":$(or $(sucursales),2),"sistemas_erp":$(or $(erps),1),"city":"Puebla"}' \
		| python -m json.tool

# === DEPLOY ===
deploy:
	bash scripts/deploy.sh

deploy-backend:
	railway up --detach

deploy-frontend:
	cd ../evangelista-dashboard && npm run build && vercel --prod

# === DEMO END-TO-END ===
demo:
	@echo "=== 1. Ingestando vault... ==="
	python -m cli.ingest --vault-path ./evangelista-vault
	@echo ""
	@echo "=== 2. Ejecutando análisis de prueba... ==="
	python -m cli.orchestrate "Calcula el Setup Fee y analiza el proceso de inventarios para una empresa textilera con 2 plantas y 1 SAP"
	@echo ""
	@echo "=== Demo completado. ==="
