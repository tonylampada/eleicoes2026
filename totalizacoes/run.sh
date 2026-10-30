#!/usr/bin/env bash
# Equivalente ao Makefile para quem não tem `make`.
# Uso: ./run.sh {fetch|deps|download|build|db|validate|dist|sizes|all}
#   fetch = baixa o banco PRONTO do GitHub Release (não precisa reconstruir nem de login)
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}; DATA=${DATA:-data}; JOBS=${JOBS:-4}; MEM=${MEM:-3GB}; THREADS=${THREADS:-6}
BUILD_FLAGS=${BUILD_FLAGS:-}
mkdir -p "$DATA/logs"
case "${1:-all}" in
  fetch)    $PY scripts/fetch_release.py --data "$DATA" ${FETCH_FLAGS:-} "${@:2}" ;;
  deps)     $PY -m pip install -r requirements.txt ;;
  download) $PY scripts/download.py --data "$DATA" --jobs "$JOBS" 2>&1 | tee -a "$DATA/logs/download.log" ;;
  build)    $PY scripts/build_parquet.py --data "$DATA" --memory "$MEM" --threads "$THREADS" $BUILD_FLAGS 2>&1 | tee -a "$DATA/logs/build.log" ;;
  db)       $PY scripts/build_db.py --data "$DATA" --memory "$MEM" --threads "$THREADS" 2>&1 | tee -a "$DATA/logs/build_db.log"
            $PY scripts/validate.py "$DATA" ;;
  validate) $PY scripts/validate.py "$DATA" ;;
  dist)     # monta os assets de um GitHub Release em $DATA/dist/ (publicar: gh release create <tag> "$DATA"/dist/*)
            mkdir -p "$DATA/dist"
            cp "$DATA/db/eleicoes2026.duckdb" "$DATA/db/eleicoes2026_compacto.duckdb" "$DATA/parquet/majoritarios_secao.parquet" "$DATA/dist/"
            tar --sort=name --owner=0 --group=0 --exclude=_RELEASE.json -cf "$DATA/dist/votos_secao_parquet.tar" -C "$DATA/parquet" votos_secao
            cp "$DATA/manifest.json" fontes_manifest.json; cp "$DATA/validacao.md" validacao.md
            (cd "$DATA/dist" && sha256sum eleicoes2026.duckdb votos_secao_parquet.tar eleicoes2026_compacto.duckdb majoritarios_secao.parquet > SHA256SUMS) ;;
  sizes)    du -sh "$DATA"/raw "$DATA"/parquet/votos_secao "$DATA"/parquet/majoritarios_secao.parquet "$DATA"/db/*.duckdb 2>/dev/null || true ;;
  all)      "$0" download && "$0" build && "$0" db ;;
  *) echo "uso: $0 {fetch|deps|download|build|db|validate|dist|sizes|all}"; exit 1 ;;
esac
