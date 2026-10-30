# Totalizações Eleições 2026 (TSE, boletim de urna por seção) -> Parquet + DuckDB
# make fetch     baixa o banco PRONTO do GitHub Release (sem reconstruir, sem login)
# make download   baixa/retoma os zips buweb e confere SHA-512
# make build      converte UF por UF para Parquet (retomável)
# make db         monta eleicoes2026.duckdb, a versão compacta e valida
# make all        tudo
PY ?= python3
DATA ?= data
JOBS ?= 4
MEM ?= 3GB
THREADS ?= 6
BUILD_FLAGS ?=          # ex.: BUILD_FLAGS=--delete-raw para apagar zips convertidos

.PHONY: all fetch deps download build db validate sizes clean-db clean-parquet dist
all: download build db

fetch:
	$(PY) scripts/fetch_release.py --data $(DATA) $(FETCH_FLAGS)

deps:
	$(PY) -m pip install -r requirements.txt

download:
	$(PY) scripts/download.py --data $(DATA) --jobs $(JOBS)

build:
	$(PY) scripts/build_parquet.py --data $(DATA) --memory $(MEM) --threads $(THREADS) $(BUILD_FLAGS)

db:
	$(PY) scripts/build_db.py --data $(DATA) --memory $(MEM) --threads $(THREADS)
	$(PY) scripts/validate.py $(DATA)

validate:
	$(PY) scripts/validate.py $(DATA)

sizes:
	@du -sh $(DATA)/raw $(DATA)/parquet/votos_secao $(DATA)/parquet/majoritarios_secao.parquet $(DATA)/db/*.duckdb 2>/dev/null || true

clean-db:
	rm -f $(DATA)/db/*.duckdb $(DATA)/parquet/majoritarios_secao.parquet

clean-parquet: clean-db
	rm -rf $(DATA)/parquet/votos_secao

# Monta os assets de um GitHub Release em $(DATA)/dist/ (publicar: gh release create <tag> $(DATA)/dist/*)
dist:
	DATA=$(DATA) ./run.sh dist
