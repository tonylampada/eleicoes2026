# Totalizações Eleições 2026 (TSE, boletim de urna por seção) -> Parquet + DuckDB
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

.PHONY: all deps download build db validate sizes clean-db clean-parquet dist
all: download build db

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

# Copia os artefatos COMPACTOS para dist/ (versionados via Git LFS) e registra hashes
dist:
	mkdir -p dist
	cp $(DATA)/parquet/majoritarios_secao.parquet dist/
	cp $(DATA)/db/eleicoes2026_compacto.duckdb dist/
	cp $(DATA)/manifest.json fontes_manifest.json
	cp $(DATA)/validacao.md validacao.md
	cd dist && sha256sum *.parquet *.duckdb > SHA256SUMS
