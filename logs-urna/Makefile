# Logs de urna (TSE) -> métricas por seção (Parquet + DuckDB)
# make fetch     baixa os agregados PRONTOS do GitHub Release (sem login, sem reprocessar)
# make process   baixa UF por UF do TSE, agrega em streaming e apaga o zip (retomável)
# make db        monta data/db/eventos.duckdb e valida contra o banco de totalizacoes/
# make all       process + db
PY ?= python3
DATA ?= data
TURNO ?= 2
UFS ?= BA,CE
JOBS ?= 8
PROCESS_FLAGS ?=
BANCO ?= ../totalizacoes/data/db/eleicoes2026.duckdb

.PHONY: all fetch deps process db validate sizes dist clean-db
all: process db

fetch:
	$(PY) scripts/fetch_release.py --data $(DATA) $(FETCH_FLAGS)

deps:
	$(PY) -m pip install -r requirements.txt

process:
	$(PY) scripts/baixar_agregar.py --data $(DATA) --turno $(TURNO) --ufs $(UFS) --jobs $(JOBS) $(PROCESS_FLAGS)

db:
	$(PY) scripts/build_db.py --data $(DATA)
	$(PY) scripts/validate.py --data $(DATA) --banco $(BANCO) > /dev/null

validate:
	$(PY) scripts/validate.py --data $(DATA) --banco $(BANCO)

sizes:
	@du -sh $(DATA)/raw $(DATA)/parquet/eventos_secao $(DATA)/parquet/eventos_tipo $(DATA)/db/*.duckdb 2>/dev/null || true

clean-db:
	rm -f $(DATA)/db/eventos.duckdb

dist:
	DATA=$(DATA) ./run.sh dist
