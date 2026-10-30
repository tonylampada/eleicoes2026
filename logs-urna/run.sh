#!/usr/bin/env bash
# Logs de urna (TSE) -> métricas por seção em Parquet + DuckDB. Equivalente ao Makefile.
# Uso: ./run.sh {fetch|deps|process|db|validate|dist|sizes|all}
#   fetch   = baixa os agregados PRONTOS do GitHub Release (sem login, sem baixar os zips do TSE)
#   process = baixa UF por UF do TSE, agrega e apaga o zip (retomável; UFS=BA,CE TURNO=2 por padrão)
#   all     = process + db (+ validate)
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}; DATA=${DATA:-data}; TURNO=${TURNO:-2}; UFS=${UFS:-BA,CE}; JOBS=${JOBS:-$(nproc 2>/dev/null || echo 4)}
PROCESS_FLAGS=${PROCESS_FLAGS:-}   # ex.: --keep-zip, --force
BANCO=${BANCO:-../totalizacoes/data/db/eleicoes2026.duckdb}
mkdir -p "$DATA/logs"
case "${1:-all}" in
  fetch)    $PY scripts/fetch_release.py --data "$DATA" ${FETCH_FLAGS:-} "${@:2}" ;;
  deps)     $PY -m pip install -r requirements.txt ;;
  process)  $PY scripts/baixar_agregar.py --data "$DATA" --turno "$TURNO" --ufs "$UFS" --jobs "$JOBS" $PROCESS_FLAGS 2>&1 \
              | tee -a "$DATA/logs/baixar_agregar.log" ;;
  db)       $PY scripts/build_db.py --data "$DATA" 2>&1 | tee -a "$DATA/logs/build_db.log"
            $PY scripts/validate.py --data "$DATA" --banco "$BANCO" > /dev/null && echo "validacao: $DATA/validacao.md" ;;
  validate) $PY scripts/validate.py --data "$DATA" --banco "$BANCO" ;;
  dist)     # assets de um GitHub Release em $DATA/dist/ (publicar: gh release create <tag> "$DATA"/dist/*)
            mkdir -p "$DATA/dist"
            cp "$DATA/db/eventos.duckdb" "$DATA/manifest.json" "$DATA/dist/"
            tar --sort=name --owner=0 --group=0 -cf "$DATA/dist/eventos_parquet.tar" -C "$DATA" parquet/eventos_secao parquet/eventos_tipo
            cp "$DATA/manifest.json" fontes_manifest.json; cp "$DATA/validacao.md" validacao.md
            (cd "$DATA/dist" && sha256sum eventos.duckdb eventos_parquet.tar manifest.json > SHA256SUMS) ;;
  sizes)    du -sh "$DATA"/raw "$DATA"/parquet/eventos_secao "$DATA"/parquet/eventos_tipo "$DATA"/db/*.duckdb 2>/dev/null || true ;;
  all)      "$0" process && "$0" db ;;
  *) echo "uso: $0 {fetch|deps|process|db|validate|dist|sizes|all}"; exit 1 ;;
esac
