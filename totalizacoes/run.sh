#!/usr/bin/env bash
# Equivalente ao Makefile para quem não tem `make`.
# Uso: ./run.sh {deps|download|build|db|validate|dist|sizes|all}
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}; DATA=${DATA:-data}; JOBS=${JOBS:-4}; MEM=${MEM:-3GB}; THREADS=${THREADS:-6}
BUILD_FLAGS=${BUILD_FLAGS:-}
mkdir -p "$DATA/logs"
case "${1:-all}" in
  deps)     $PY -m pip install -r requirements.txt ;;
  download) $PY scripts/download.py --data "$DATA" --jobs "$JOBS" 2>&1 | tee -a "$DATA/logs/download.log" ;;
  build)    $PY scripts/build_parquet.py --data "$DATA" --memory "$MEM" --threads "$THREADS" $BUILD_FLAGS 2>&1 | tee -a "$DATA/logs/build.log" ;;
  db)       $PY scripts/build_db.py --data "$DATA" --memory "$MEM" --threads "$THREADS" 2>&1 | tee -a "$DATA/logs/build_db.log"
            $PY scripts/validate.py "$DATA" ;;
  validate) $PY scripts/validate.py "$DATA" ;;
  dist)     mkdir -p dist
            cp "$DATA/parquet/majoritarios_secao.parquet" "$DATA/db/eleicoes2026_compacto.duckdb" dist/
            cp "$DATA/manifest.json" fontes_manifest.json; cp "$DATA/validacao.md" validacao.md
            (cd dist && sha256sum *.parquet *.duckdb > SHA256SUMS) ;;
  sizes)    du -sh "$DATA"/raw "$DATA"/parquet/votos_secao "$DATA"/parquet/majoritarios_secao.parquet "$DATA"/db/*.duckdb 2>/dev/null || true ;;
  all)      "$0" download && "$0" build && "$0" db ;;
  *) echo "uso: $0 {deps|download|build|db|validate|dist|sizes|all}"; exit 1 ;;
esac
