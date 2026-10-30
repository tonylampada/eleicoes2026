#!/usr/bin/env python3
"""Monta data/db/eventos.duckdb a partir dos Parquets de eventos (não toca no banco principal).

  python3 scripts/build_db.py [--data data]

Tabelas: eventos_secao (1 linha por turno × UF × município × zona × seção),
         eventos_tipo (contagem por seção × modelo de evento; só eventos fora da rotina, ver README),
         eventos_dicionario (modelo de evento × nº de ocorrências e de seções, por turno),
         lotes (o manifest: um registro por turno/UF processado).
Gravado em <db>.tmp e renomeado no fim; idempotente.
"""
import argparse, json, os, sys

import duckdb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
    a = ap.parse_args()
    data = os.path.abspath(a.data)
    sec = os.path.join(data, "parquet", "eventos_secao", "*", "*", "data.parquet")
    tip = os.path.join(data, "parquet", "eventos_tipo", "*", "*", "data.parquet")
    os.makedirs(os.path.join(data, "db"), exist_ok=True)
    out = os.path.join(data, "db", "eventos.duckdb")
    tmp = out + ".tmp"
    for p in (tmp, tmp + ".wal"):
        if os.path.exists(p):
            os.remove(p)
    con = duckdb.connect(tmp)
    con.execute(f"CREATE TABLE eventos_secao AS SELECT * FROM read_parquet('{sec}', hive_partitioning=false, union_by_name=true) ORDER BY nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao")
    con.execute(f"CREATE TABLE eventos_tipo AS SELECT * FROM read_parquet('{tip}', hive_partitioning=false, union_by_name=true) ORDER BY nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao, app, modelo")
    con.execute("""CREATE TABLE eventos_dicionario AS
        SELECT nr_turno, app, nivel, modelo, sum(n)::BIGINT AS ocorrencias, count(*) AS secoes
        FROM eventos_tipo GROUP BY ALL ORDER BY nr_turno, secoes DESC, ocorrencias DESC""")
    man = json.load(open(os.path.join(data, "manifest.json")))
    rows = [(v["turno"], v["uf"], v["zip_url"], v["zip_bytes"], v["etag"], v["zip_sha256"], v["n_logs"],
             v["n_votos_log"], v["parser_version"], v["processado_em"]) for v in man.values() if v.get("estado") == "ok"]
    con.execute("CREATE TABLE lotes (nr_turno TINYINT, sg_uf VARCHAR, zip_url VARCHAR, zip_bytes BIGINT, etag VARCHAR, "
                "zip_sha256 VARCHAR, n_logs INTEGER, n_votos_log BIGINT, parser_version VARCHAR, processado_em VARCHAR)")
    if rows:
        con.executemany("INSERT INTO lotes VALUES (?,?,?,?,?,?,?,?,?,?)", rows)
    n = con.execute("SELECT count(*), count(DISTINCT sg_uf) FROM eventos_secao").fetchone()
    con.execute("CHECKPOINT")
    con.close()
    os.replace(tmp, out)
    print(f"eventos.duckdb: {n[0]:,} seções em {n[1]} UF(s) -> {out} ({os.path.getsize(out)/1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())
