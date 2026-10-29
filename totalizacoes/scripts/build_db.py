#!/usr/bin/env python3
"""Monta os bancos DuckDB e a versão compacta a partir do Parquet por seção.

Saídas (em data/):
  db/eleicoes2026.duckdb            banco completo (todas as tabelas materializadas)
  parquet/majoritarios_secao.parquet  compacto: presidente, governador e senador por seção
  db/eleicoes2026_compacto.duckdb   banco leve: só majoritários + agregados

Idempotente: reconstrói em arquivo .tmp e troca no final. Use --force para refazer
mesmo se o banco for mais novo que todas as partições Parquet.
"""
import argparse, datetime as dt, glob, os, sys, time
import duckdb


def log(*a):
    print(dt.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


# Tabelas agregadas comuns aos dois bancos (dependem de uma tabela/visão `votos_secao`)
AGREGADOS = r"""
CREATE OR REPLACE TABLE partidos AS
SELECT nr_partido, any_value(sg_partido) AS sg_partido, any_value(nm_partido) AS nm_partido
FROM _src WHERE nr_partido IS NOT NULL AND nr_partido > 0
GROUP BY nr_partido ORDER BY nr_partido;

-- candidatos / votáveis (nominais e legendas). Abrangência: BR para presidente, UF para os demais
CREATE OR REPLACE TABLE candidatos AS
SELECT nr_turno, cd_cargo, any_value(ds_cargo) AS ds_cargo,
       CASE WHEN cd_cargo = 1 THEN 'BR' ELSE sg_uf END AS abrangencia,
       cd_tipo_votavel, any_value(ds_tipo_votavel) AS ds_tipo_votavel,
       nr_votavel, any_value(nm_votavel) AS nm_votavel,
       any_value(nr_partido) AS nr_partido, any_value(sg_partido) AS sg_partido,
       sum(qt_votos)::BIGINT AS votos
FROM _src
WHERE cd_tipo_votavel IN (1, 4) -- 1 nominal, 4 legenda
GROUP BY ALL ORDER BY nr_turno, cd_cargo, abrangencia, votos DESC;

-- uma linha por seção/cargo com os dados da urna (aptos, comparecimento, horários etc.)
CREATE OR REPLACE TABLE secoes AS
SELECT nr_turno, sg_uf, cd_municipio, any_value(nm_municipio) AS nm_municipio, nr_zona, nr_secao, cd_cargo,
       any_value(nr_local_votacao) AS nr_local_votacao,
       max(qt_aptos) AS qt_aptos, max(qt_comparecimento) AS qt_comparecimento,
       max(qt_abstencoes) AS qt_abstencoes, any_value(cd_tipo_urna) AS cd_tipo_urna,
       sum(qt_votos)::INTEGER AS qt_votos_total
       __EXTRA_SECAO__
FROM _src GROUP BY nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao, cd_cargo;

CREATE OR REPLACE TABLE totais_municipio AS
SELECT nr_turno, sg_uf, cd_municipio, any_value(nm_municipio) AS nm_municipio, cd_cargo, any_value(ds_cargo) AS ds_cargo,
       cd_tipo_votavel, nr_votavel, any_value(nm_votavel) AS nm_votavel, any_value(sg_partido) AS sg_partido,
       sum(qt_votos)::BIGINT AS votos
FROM _src GROUP BY nr_turno, sg_uf, cd_municipio, cd_cargo, cd_tipo_votavel, nr_votavel;

CREATE OR REPLACE TABLE totais_zona AS
SELECT nr_turno, sg_uf, cd_municipio, any_value(nm_municipio) AS nm_municipio, nr_zona, cd_cargo,
       cd_tipo_votavel, nr_votavel, any_value(nm_votavel) AS nm_votavel, any_value(sg_partido) AS sg_partido,
       sum(qt_votos)::BIGINT AS votos
FROM _src GROUP BY nr_turno, sg_uf, cd_municipio, nr_zona, cd_cargo, cd_tipo_votavel, nr_votavel;

CREATE OR REPLACE TABLE totais_candidato_uf AS
WITH t AS (
  SELECT nr_turno, sg_uf, cd_cargo, any_value(ds_cargo) AS ds_cargo, cd_tipo_votavel,
         nr_votavel, any_value(nm_votavel) AS nm_votavel, any_value(sg_partido) AS sg_partido,
         sum(qt_votos)::BIGINT AS votos
  FROM _src GROUP BY nr_turno, sg_uf, cd_cargo, cd_tipo_votavel, nr_votavel)
SELECT *, round(100.0 * votos / sum(votos) FILTER (WHERE cd_tipo_votavel IN (1, 4))
                OVER (PARTITION BY nr_turno, sg_uf, cd_cargo), 2) AS pct_validos
FROM t;

CREATE OR REPLACE VIEW totais_presidente_br AS
WITH t AS (SELECT nr_turno, cd_tipo_votavel, nr_votavel, any_value(nm_votavel) AS nm_votavel,
                  any_value(sg_partido) AS sg_partido, sum(votos)::BIGINT AS votos
           FROM totais_candidato_uf WHERE cd_cargo = 1 GROUP BY ALL)
SELECT *, round(100.0 * votos / sum(votos) FILTER (WHERE cd_tipo_votavel = 1) OVER (PARTITION BY nr_turno), 2) AS pct_validos
FROM t ORDER BY nr_turno, votos DESC;

-- comparativo 1º x 2º turno para presidente, por seção (13 = LULA, 22 = FLAVIO BOLSONARO)
CREATE OR REPLACE TABLE presidente_1t_2t_secao AS
WITH p AS (
  SELECT nr_turno, sg_uf, cd_municipio, any_value(nm_municipio) AS nm_municipio, nr_zona, nr_secao,
         max(qt_aptos) AS aptos, max(qt_comparecimento) AS comparecimento,
         sum(qt_votos) FILTER (WHERE nr_votavel = 13) AS lula,
         sum(qt_votos) FILTER (WHERE nr_votavel = 22) AS flavio,
         sum(qt_votos) FILTER (WHERE cd_tipo_votavel = 1 AND nr_votavel NOT IN (13, 22)) AS outros,
         sum(qt_votos) FILTER (WHERE cd_tipo_votavel = 2) AS brancos,
         sum(qt_votos) FILTER (WHERE cd_tipo_votavel NOT IN (1, 2)) AS nulos
  FROM _src WHERE cd_cargo = 1
  GROUP BY nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao)
SELECT coalesce(a.sg_uf, b.sg_uf) AS sg_uf, coalesce(a.cd_municipio, b.cd_municipio) AS cd_municipio,
       coalesce(a.nm_municipio, b.nm_municipio) AS nm_municipio,
       coalesce(a.nr_zona, b.nr_zona) AS nr_zona, coalesce(a.nr_secao, b.nr_secao) AS nr_secao,
       a.aptos AS aptos_1t, a.comparecimento AS comparecimento_1t,
       coalesce(a.lula, 0)::INTEGER AS lula_1t, coalesce(a.flavio, 0)::INTEGER AS flavio_1t,
       coalesce(a.outros, 0)::INTEGER AS outros_1t, coalesce(a.brancos, 0)::INTEGER AS brancos_1t,
       coalesce(a.nulos, 0)::INTEGER AS nulos_1t,
       b.aptos AS aptos_2t, b.comparecimento AS comparecimento_2t,
       coalesce(b.lula, 0)::INTEGER AS lula_2t, coalesce(b.flavio, 0)::INTEGER AS flavio_2t,
       coalesce(b.brancos, 0)::INTEGER AS brancos_2t, coalesce(b.nulos, 0)::INTEGER AS nulos_2t,
       (coalesce(b.lula,0) - coalesce(b.flavio,0)) - (coalesce(a.lula,0) - coalesce(a.flavio,0)) AS delta_margem_lula,
       a.nr_turno IS NOT NULL AS tem_1t, b.nr_turno IS NOT NULL AS tem_2t
FROM (SELECT * FROM p WHERE nr_turno = 1) a
FULL OUTER JOIN (SELECT * FROM p WHERE nr_turno = 2) b
  USING (sg_uf, cd_municipio, nr_zona, nr_secao);

CREATE OR REPLACE VIEW cargos AS
SELECT DISTINCT nr_turno, cd_cargo, ds_cargo FROM totais_candidato_uf ORDER BY ALL;
"""

EXTRA_SECAO_FULL = """,
       any_value(nr_urna_efetivada) AS nr_urna_efetivada, any_value(ds_secoes_agregadas) AS ds_secoes_agregadas,
       any_value(dt_abertura) AS dt_abertura, any_value(dt_encerramento) AS dt_encerramento,
       any_value(dt_emissao_bu) AS dt_emissao_bu, any_value(dt_bu_recebido) AS dt_bu_recebido,
       any_value(qt_elei_biom_sem_habilitacao) AS qt_elei_biom_sem_habilitacao"""

COMPACT_COLS = ("nr_turno, sg_uf, cd_municipio, nm_municipio, nr_zona, nr_secao, nr_local_votacao, "
                "cd_cargo, ds_cargo, cd_tipo_votavel, ds_tipo_votavel, nr_votavel, nm_votavel, "
                "nr_partido, sg_partido, nm_partido, qt_votos, qt_aptos, qt_comparecimento, "
                "qt_abstencoes, cd_tipo_urna")


NORMALIZADO = r"""
-- fato enxuto: só chaves inteiras + votos (comprime muito melhor no DuckDB)
CREATE TABLE votos AS
SELECT nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao, cd_cargo, cd_tipo_votavel, nr_votavel, qt_votos
FROM _src ORDER BY nr_turno, sg_uf, cd_cargo, cd_municipio, nr_zona, nr_secao, cd_tipo_votavel, nr_votavel;

CREATE TABLE municipios AS
SELECT sg_uf, cd_municipio, any_value(nm_municipio) AS nm_municipio FROM _src GROUP BY ALL ORDER BY ALL;

CREATE TABLE votaveis AS
SELECT nr_turno, sg_uf, cd_cargo, any_value(ds_cargo) AS ds_cargo, cd_tipo_votavel,
       any_value(ds_tipo_votavel) AS ds_tipo_votavel, nr_votavel, any_value(nm_votavel) AS nm_votavel,
       any_value(nr_partido) AS nr_partido, any_value(sg_partido) AS sg_partido, any_value(nm_partido) AS nm_partido
FROM _src GROUP BY nr_turno, sg_uf, cd_cargo, cd_tipo_votavel, nr_votavel ORDER BY ALL;
"""

VIEW_VOTOS_SECAO = r"""
CREATE OR REPLACE VIEW votos_secao AS
SELECT v.nr_turno, v.sg_uf, v.cd_municipio, m.nm_municipio, v.nr_zona, v.nr_secao, s.nr_local_votacao,
       v.cd_cargo, d.ds_cargo, v.cd_tipo_votavel, d.ds_tipo_votavel, v.nr_votavel, d.nm_votavel,
       d.nr_partido, d.sg_partido, d.nm_partido, v.qt_votos,
       s.qt_aptos, s.qt_comparecimento, s.qt_abstencoes, s.cd_tipo_urna
FROM votos v
JOIN municipios m USING (sg_uf, cd_municipio)
JOIN votaveis d USING (nr_turno, sg_uf, cd_cargo, cd_tipo_votavel, nr_votavel)
JOIN secoes s USING (nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao, cd_cargo);
"""


# Versão de armazenamento do arquivo .duckdb: 'v1.4.0' permite abrir o banco com DuckDB 1.4+ (e 2.x).
STORAGE_VERSION = os.environ.get("DUCKDB_STORAGE_VERSION", "v1.4.0")


def build(path, src, extra_secao, memory, threads):
    tmp = path + ".tmp"
    for f in (tmp, tmp + ".wal"):
        if os.path.exists(f):
            os.remove(f)
    con = duckdb.connect()
    con.execute(f"ATTACH '{tmp}' AS db (STORAGE_VERSION '{STORAGE_VERSION}'); USE db;")
    con.execute(f"SET memory_limit='{memory}'; SET threads={threads}; SET preserve_insertion_order=true;"
                f"SET temp_directory='{os.path.dirname(path)}/spill';")
    t0 = time.time()
    con.execute(f"CREATE TEMP VIEW _src AS SELECT * FROM {src};")
    sql = NORMALIZADO + AGREGADOS.replace("__EXTRA_SECAO__", extra_secao) + VIEW_VOTOS_SECAO
    for stmt in sql.split(";\n"):
        if stmt.strip():
            con.execute(stmt)
    log(f"  votos: {con.execute('SELECT count(*) FROM votos').fetchone()[0]:,} linhas ({time.time()-t0:.0f}s)")
    con.execute("CHECKPOINT")
    con.close()
    os.replace(tmp, path)
    log(f"  {path}: {os.path.getsize(path)/1e6:.1f} MB ({time.time()-t0:.0f}s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--memory", default="3GB")
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only", choices=["full", "compact", "all"], default="all")
    a = ap.parse_args()
    data = os.path.abspath(a.data)
    pq = os.path.join(data, "parquet", "votos_secao", "*", "*", "data.parquet")
    parts = glob.glob(pq)
    if not parts:
        sys.exit("nenhuma partição Parquet; rode `make build` antes")
    newest = max(os.path.getmtime(p) for p in parts)
    os.makedirs(os.path.join(data, "db"), exist_ok=True)
    src = f"read_parquet('{pq}', hive_partitioning=false)"
    full = os.path.join(data, "db", "eleicoes2026.duckdb")
    compact_pq = os.path.join(data, "parquet", "majoritarios_secao.parquet")
    compact_db = os.path.join(data, "db", "eleicoes2026_compacto.duckdb")

    def stale(p):
        return a.force or not os.path.exists(p) or os.path.getmtime(p) < newest

    if a.only in ("compact", "all") and stale(compact_pq):
        log("compacto: majoritarios_secao.parquet")
        con = duckdb.connect()
        con.execute(f"SET memory_limit='{a.memory}'; SET threads={a.threads}; SET preserve_insertion_order=false;")
        con.execute(f"""COPY (SELECT {COMPACT_COLS} FROM {src} WHERE cd_cargo IN (1, 3, 5)
                    ORDER BY nr_turno, cd_cargo, sg_uf, cd_municipio, nr_zona, nr_secao, nr_votavel)
                    TO '{compact_pq}.tmp' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 19, ROW_GROUP_SIZE 1000000)""")
        os.replace(compact_pq + ".tmp", compact_pq)
        log(f"  {compact_pq}: {os.path.getsize(compact_pq)/1e6:.1f} MB")
    if a.only in ("compact", "all") and stale(compact_db):
        log("compacto: eleicoes2026_compacto.duckdb")
        build(compact_db, f"read_parquet('{compact_pq}')", "",
              a.memory, a.threads)
    if a.only in ("full", "all") and stale(full):
        log("completo: eleicoes2026.duckdb")
        build(full, src,
              EXTRA_SECAO_FULL, a.memory, a.threads)
    log("fim")


if __name__ == "__main__":
    main()
