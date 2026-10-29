#!/usr/bin/env python3
"""Converte os CSVs do boletim de urna (buweb) em Parquet tipado, particionado por turno/UF.

Saída: data/parquet/votos_secao/turno=<N>/uf=<UF>/data.parquet (zstd, ordenado por
cargo, município, zona, seção, votável). Retomável: cada partição pronta ganha um
marcador `_OK.json` com a versão/sha512 da fonte e nº de linhas; partições com marcador
válido são puladas. A escrita é atômica (arquivo .tmp + rename).

Uso: python3 scripts/build_parquet.py [--data DIR] [--ufs SP,RJ] [--turnos 1,2]
     [--delete-raw]   # apaga o zip bruto depois de converter (economiza disco)
     [--memory 2GB] [--threads 4]
"""
import argparse, datetime as dt, json, os, shutil, subprocess, sys, time
import duckdb

# Coluna original -> (nome no parquet, tipo SQL, conversão)
#   conversão: None = cast direto; 'd' = data DD/MM/AAAA; 'ts' = timestamp AAAA-MM-DD HH:MM:SS
COLS = [
    ("DT_GERACAO", "dt_geracao", "DATE", "dmy"),
    ("HH_GERACAO", "hh_geracao", "TIME", None),
    ("ANO_ELEICAO", "ano_eleicao", "SMALLINT", None),
    ("CD_TIPO_ELEICAO", "cd_tipo_eleicao", "TINYINT", None),
    ("NM_TIPO_ELEICAO", "nm_tipo_eleicao", "VARCHAR", None),
    ("CD_PLEITO", "cd_pleito", "INTEGER", None),
    ("DT_PLEITO", "dt_pleito", "DATE", "ts"),
    ("NR_TURNO", "nr_turno", "TINYINT", None),
    ("CD_ELEICAO", "cd_eleicao", "INTEGER", None),
    ("DS_ELEICAO", "ds_eleicao", "VARCHAR", None),
    ("SG_UF", "sg_uf", "VARCHAR", None),
    ("CD_MUNICIPIO", "cd_municipio", "INTEGER", None),
    ("NM_MUNICIPIO", "nm_municipio", "VARCHAR", None),
    ("NR_ZONA", "nr_zona", "SMALLINT", None),
    ("NR_SECAO", "nr_secao", "INTEGER", None),
    ("NR_LOCAL_VOTACAO", "nr_local_votacao", "INTEGER", None),
    ("CD_CARGO_PERGUNTA", "cd_cargo", "SMALLINT", None),
    ("DS_CARGO_PERGUNTA", "ds_cargo", "VARCHAR", None),
    ("NR_PARTIDO", "nr_partido", "SMALLINT", None),
    ("SG_PARTIDO", "sg_partido", "VARCHAR", None),
    ("NM_PARTIDO", "nm_partido", "VARCHAR", None),
    ("DT_BU_RECEBIDO", "dt_bu_recebido", "TIMESTAMP", "ts"),
    ("QT_APTOS", "qt_aptos", "INTEGER", None),
    ("QT_COMPARECIMENTO", "qt_comparecimento", "INTEGER", None),
    ("QT_ABSTENCOES", "qt_abstencoes", "INTEGER", None),
    ("CD_TIPO_URNA", "cd_tipo_urna", "TINYINT", None),
    ("DS_TIPO_URNA", "ds_tipo_urna", "VARCHAR", None),
    ("CD_TIPO_VOTAVEL", "cd_tipo_votavel", "TINYINT", None),
    ("DS_TIPO_VOTAVEL", "ds_tipo_votavel", "VARCHAR", None),
    ("NR_VOTAVEL", "nr_votavel", "INTEGER", None),
    ("NM_VOTAVEL", "nm_votavel", "VARCHAR", None),
    ("QT_VOTOS", "qt_votos", "INTEGER", None),
    ("NR_URNA_EFETIVADA", "nr_urna_efetivada", "INTEGER", None),
    ("CD_CARGA_1_URNA_EFETIVADA", "cd_carga_1_urna_efetivada", "VARCHAR", None),
    ("CD_CARGA_2_URNA_EFETIVADA", "cd_carga_2_urna_efetivada", "VARCHAR", None),
    ("CD_FLASHCARD_URNA_EFETIVADA", "cd_flashcard_urna_efetivada", "VARCHAR", None),
    ("DT_CARGA_URNA_EFETIVADA", "dt_carga_urna_efetivada", "TIMESTAMP", "ts"),
    ("DS_CARGO_PERGUNTA_SECAO", "ds_cargo_pergunta_secao", "VARCHAR", None),
    ("DS_SECOES_AGREGADAS", "ds_secoes_agregadas", "VARCHAR", None),
    ("DT_ABERTURA", "dt_abertura", "TIMESTAMP", "ts"),
    ("DT_ENCERRAMENTO", "dt_encerramento", "TIMESTAMP", "ts"),
    ("QT_ELEI_BIOM_SEM_HABILITACAO", "qt_elei_biom_sem_habilitacao", "INTEGER", None),
    ("DT_EMISSAO_BU", "dt_emissao_bu", "TIMESTAMP", "ts"),
    ("NR_JUNTA_APURADORA", "nr_junta_apuradora", "INTEGER", None),
    ("NR_TURMA_APURADORA", "nr_turma_apuradora", "INTEGER", None),
]
SORT = "cd_cargo, cd_municipio, nr_zona, nr_secao, cd_tipo_votavel, nr_votavel"


def select_sql():
    out = []
    for src, dst, typ, conv in COLS:
        v = f"NULLIF(NULLIF(NULLIF(\"{src}\", '#NULO#'), '#NULO'), '#NE')"
        if conv == "dmy":
            e = f"CAST(strptime({v}, '%d/%m/%Y') AS DATE)"
        elif conv == "ts":
            e = f"CAST(strptime({v}, '%Y-%m-%d %H:%M:%S') AS {typ})"
        else:
            e = f"CAST({v} AS {typ})"
        out.append(f"{e} AS {dst}")
    return ",\n  ".join(out)


def log(*a):
    print(dt.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--turnos", default="1,2")
    ap.add_argument("--ufs", default="")
    ap.add_argument("--delete-raw", action="store_true")
    ap.add_argument("--memory", default="2GB")
    ap.add_argument("--threads", type=int, default=4)
    a = ap.parse_args()
    data = os.path.abspath(a.data)
    manifest = json.load(open(os.path.join(data, "manifest.json")))
    tmpdir = os.path.join(data, "tmp"); os.makedirs(tmpdir, exist_ok=True)
    outroot = os.path.join(data, "parquet", "votos_secao")
    turnos = {int(t) for t in a.turnos.split(",")}
    ufs = set(a.ufs.split(",")) if a.ufs else None
    # menores primeiro: erros de schema aparecem cedo
    items = sorted((m for m in manifest.values() if m.get("estado") == "ok"),
                   key=lambda m: m.get("bytes", 0))
    con = duckdb.connect()
    con.execute(f"SET memory_limit='{a.memory}'; SET threads={a.threads}; "
                f"SET temp_directory='{tmpdir}/duckdb_spill'; SET preserve_insertion_order=false;")
    sel = select_sql()
    for m in items:
        if m["turno"] not in turnos or (ufs and m["uf"] not in ufs):
            continue
        part = os.path.join(outroot, f"turno={m['turno']}", f"uf={m['uf']}")
        marker = os.path.join(part, "_OK.json")
        if os.path.exists(marker):
            mk = json.load(open(marker))
            if mk.get("fonte_sha512") == m["sha512"]:
                log(f"{m['turno']}t {m['uf']}: pronto, pulando")
                continue
        zpath = os.path.join(data, "raw", os.path.basename(m["zip_url"]))
        if not os.path.exists(zpath):
            log(f"{m['turno']}t {m['uf']}: zip bruto ausente ({zpath}); rode `make download`")
            sys.exit(2)
        t0 = time.time()
        csvname = os.path.basename(zpath)[:-4] + ".csv"
        csv = os.path.join(tmpdir, csvname)
        subprocess.run(["unzip", "-o", "-q", zpath, csvname, "-d", tmpdir], check=True)
        os.makedirs(part, exist_ok=True)
        out_tmp = os.path.join(part, "data.parquet.tmp")
        # contagem independente de linhas (o CSV do TSE não tem quebras de linha dentro de campos)
        with open(csv, "rb") as f:
            n_csv = sum(b.count(b"\n") for b in iter(lambda: f.read(64 << 20), b"")) - 1
        n_pq = votos = None
        # o leitor paralelo do DuckDB já falhou em fronteira de buffer (SP 1t); se der erro
        # ou a contagem não bater, refaz com leitura sequencial (parallel=false)
        for parallel in ("true", "false"):
            try:
                con.execute(f"""
COPY (
 SELECT
  {sel}
 FROM read_csv('{csv}', delim=';', quote='"', escape='"', header=true, all_varchar=true,
               encoding='latin-1', strict_mode=true, parallel={parallel})
 ORDER BY {SORT}
) TO '{out_tmp}' (FORMAT parquet, COMPRESSION zstd, COMPRESSION_LEVEL 9, ROW_GROUP_SIZE 500000)
""")
                n_pq, votos = con.execute(f"SELECT count(*), sum(qt_votos) FROM read_parquet('{out_tmp}')").fetchone()
                if n_pq == n_csv:
                    break
                log(f"{m['turno']}t {m['uf']}: linhas csv={n_csv} parquet={n_pq} (parallel={parallel})")
            except duckdb.Error as e:
                log(f"{m['turno']}t {m['uf']}: erro de leitura com parallel={parallel}: {str(e).splitlines()[0]}")
        if n_pq != n_csv:
            log(f"ERRO {m['uf']} {m['turno']}t: linhas csv={n_csv} parquet={n_pq}"); sys.exit(3)
        os.replace(out_tmp, os.path.join(part, "data.parquet"))
        json.dump({"fonte": m["arquivo"] if "arquivo" in m else os.path.basename(zpath),
                   "versao": m["versao"], "fonte_sha512": m["sha512"], "linhas": n_pq,
                   "soma_qt_votos": int(votos or 0), "leitura_paralela": parallel == "true", "csv_bytes": os.path.getsize(csv),
                   "parquet_bytes": os.path.getsize(os.path.join(part, "data.parquet")),
                   "gerado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds")},
                  open(marker, "w"), indent=1)
        os.remove(csv)
        if a.delete_raw:
            os.remove(zpath)
        log(f"{m['turno']}t {m['uf']}: {n_pq:,} linhas, "
            f"{os.path.getsize(os.path.join(part, 'data.parquet'))/1e6:.1f} MB em {time.time()-t0:.0f}s")
    shutil.rmtree(os.path.join(tmpdir, "duckdb_spill"), ignore_errors=True)
    log("fim")


if __name__ == "__main__":
    main()
