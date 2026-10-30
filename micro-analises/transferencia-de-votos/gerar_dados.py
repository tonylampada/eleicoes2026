#!/usr/bin/env python3
"""Micro-análise: transferência de votos 1º → 2º turno (presidente).

Lê o banco DuckDB (somente leitura) e gera dados.json, agregado por
(município, hora local de encerramento da urna no 2º turno), com todas as medidas
somáveis que a página index.html precisa para recalcular o Sankey no navegador.

Uso:
    python gerar_dados.py [--db CAMINHO] [--out dados.json]
"""
import argparse, datetime as dt, json, os, sys

import duckdb

AQUI = os.path.dirname(os.path.abspath(__file__))
DB_PADRAO = os.path.normpath(os.path.join(AQUI, "..", "..", "totalizacoes", "data", "db", "eleicoes2026.duckdb"))
FINALISTAS = (13, 22)
OFICIAL_2T = {13: 64256232, 22: 59826041}

# Uma linha por seção comparável (existe no 1º e no 2º turno), com a hora local de encerramento do 2º turno.
SQL_SECOES = """
CREATE TEMP TABLE sec AS
SELECT p.*, coalesce(hour(s.dt_encerramento), -1) AS h
FROM presidente_1t_2t_secao p
LEFT JOIN secoes s ON s.nr_turno = 2 AND s.cd_cargo = 1 AND s.sg_uf = p.sg_uf
     AND s.cd_municipio = p.cd_municipio AND s.nr_zona = p.nr_zona AND s.nr_secao = p.nr_secao
WHERE p.tem_1t AND p.tem_2t
"""

SQL_AGG = """
SELECT sg_uf, cd_municipio, h, count(*) AS n,
       sum(aptos_1t)::BIGINT a1, sum(aptos_2t)::BIGINT a2,
       sum(comparecimento_1t)::BIGINT c1, sum(comparecimento_2t)::BIGINT c2,
       sum(brancos_1t)::BIGINT b1, sum(brancos_2t)::BIGINT b2,
       sum(nulos_1t)::BIGINT u1, sum(nulos_2t)::BIGINT u2,
       sum(lula_1t)::BIGINT l1, sum(lula_2t)::BIGINT l2,
       sum(flavio_1t)::BIGINT f1, sum(flavio_2t)::BIGINT f2,
       sum(outros_1t)::BIGINT o1
FROM sec GROUP BY ALL ORDER BY sg_uf, cd_municipio, h
"""

# votos do 1º turno de cada candidato eliminado, no mesmo agrupamento
SQL_DEMAIS = """
SELECT s.sg_uf, s.cd_municipio, s.h, v.nr_votavel, sum(v.qt_votos)::BIGINT AS votos
FROM votos v JOIN sec s USING (sg_uf, cd_municipio, nr_zona, nr_secao)
WHERE v.nr_turno = 1 AND v.cd_cargo = 1 AND v.cd_tipo_votavel = 1 AND v.nr_votavel NOT IN (13, 22)
GROUP BY ALL
"""

# fuso estimado por município: as urnas abrem às 8h de Brasília em todo o país (horário unificado),
# então (8 - hora local mais comum de abertura) = horas a somar para converter hora local -> Brasília.
SQL_FUSO = """
SELECT sg_uf, cd_municipio, mode(hour(dt_abertura)) AS ha
FROM secoes WHERE nr_turno = 2 AND cd_cargo = 1 AND dt_abertura IS NOT NULL GROUP BY ALL
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=DB_PADRAO, help=f"banco DuckDB (padrão: {DB_PADRAO})")
    ap.add_argument("--out", default=os.path.join(AQUI, "dados.json"))
    a = ap.parse_args()
    if not os.path.exists(a.db):
        sys.exit(f"banco não encontrado: {a.db} (veja totalizacoes/README.md)")
    con = duckdb.connect(a.db, read_only=True)

    finalistas = [r[0] for r in con.execute(
        "SELECT nr_votavel FROM candidatos WHERE cd_cargo = 1 AND nr_turno = 2 AND cd_tipo_votavel = 1 ORDER BY nr_votavel").fetchall()]
    assert tuple(finalistas) == FINALISTAS, f"finalistas inesperados no banco: {finalistas}"
    nomes = {r[0]: r[1] for r in con.execute(
        "SELECT nr_votavel, nm_votavel FROM candidatos WHERE cd_cargo = 1 AND nr_turno = 1 AND cd_tipo_votavel = 1").fetchall()}
    tot1 = {r[0]: r[1] for r in con.execute(
        "SELECT nr_votavel, votos FROM candidatos WHERE cd_cargo = 1 AND nr_turno = 1 AND cd_tipo_votavel = 1").fetchall()}
    demais = sorted([n for n in tot1 if n not in FINALISTAS], key=lambda n: -tot1[n])

    con.execute(SQL_SECOES)
    agg = con.execute(SQL_AGG).fetchall()
    cols = [d[0] for d in con.description]
    dem = con.execute(SQL_DEMAIS).fetchall()
    fuso = {(u, m): (None if u == "ZZ" or ha is None else 8 - ha) for u, m, ha in con.execute(SQL_FUSO).fetchall()}
    muns = con.execute("SELECT sg_uf, cd_municipio, nm_municipio FROM municipios ORDER BY sg_uf, nm_municipio").fetchall()
    excluidas = con.execute("SELECT count(*) FROM presidente_1t_2t_secao WHERE NOT (tem_1t AND tem_2t)").fetchone()[0]
    aptos_dif = con.execute("SELECT count(*) FROM sec WHERE aptos_1t <> aptos_2t").fetchone()[0]

    ufs = sorted({u for u, _, _ in muns})
    uf_idx = {u: i for i, u in enumerate(ufs)}
    usados = {(r[0], r[1]) for r in agg}
    muns = [m for m in muns if (m[0], m[1]) in usados]
    mun_idx = {(u, c): i for i, (u, c, _) in enumerate(muns)}
    chave = {(r[0], r[1], r[2]): i for i, r in enumerate(agg)}

    linhas = {k: [] for k in cols[3:]}
    linhas["m"] = []
    linhas["h"] = []
    for r in agg:
        linhas["m"].append(mun_idx[(r[0], r[1])])
        linhas["h"].append(r[2])
        for k, v in zip(cols[3:], r[3:]):
            linhas[k].append(int(v))
    d_cols = {n: [0] * len(agg) for n in demais}
    for u, m, h, nr, votos in dem:
        d_cols[nr][chave[(u, m, h)]] = int(votos)

    # ---------------- validações ----------------
    S = lambda k: sum(linhas[k])
    val = {}
    val["lula_2t"] = {"calculado": S("l2"), "oficial": OFICIAL_2T[13]}
    val["flavio_2t"] = {"calculado": S("f2"), "oficial": OFICIAL_2T[22]}
    for k in ("lula_2t", "flavio_2t"):
        val[k]["ok"] = val[k]["calculado"] == val[k]["oficial"]
    soma_demais = sum(sum(v) for v in d_cols.values())
    val["demais_por_candidato_soma_outros"] = {"ok": soma_demais == S("o1"), "valor": soma_demais}
    termos = {"comparecimento": S("c2") - S("c1"), "brancos": -(S("b2") - S("b1")),
              "nulos": -(S("u2") - S("u1")), "demais": S("o1")}
    ganho = {"13": S("l2") - S("l1"), "22": S("f2") - S("f1")}
    fontes = sum(v for v in termos.values() if v > 0) + sum(-v for v in ganho.values() if v < 0)
    destinos = sum(v for v in ganho.values() if v > 0) + sum(-v for v in termos.values() if v < 0)
    val["sankey_fecha_brasil"] = {"bruto": fontes, "liquido": destinos, "ok": fontes == destinos}
    # identidade por linha (cada agrupamento): ganho13 + ganho22 = Δcomp - Δbrancos - Δnulos + demais
    bad = sum(1 for i in range(len(agg)) if
              (linhas["l2"][i] - linhas["l1"][i]) + (linhas["f2"][i] - linhas["f1"][i]) !=
              (linhas["c2"][i] - linhas["c1"][i]) - (linhas["b2"][i] - linhas["b1"][i])
              - (linhas["u2"][i] - linhas["u1"][i]) + linhas["o1"][i])
    val["identidade_por_agrupamento"] = {"linhas_com_erro": bad, "ok": bad == 0}
    ok = all(v["ok"] for v in val.values())

    out = {
        "meta": {
            "titulo": "Transferência de votos 1º → 2º turno — Presidente 2026",
            "gerado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "fonte": "Boletins de urna (TSE) por seção — banco totalizacoes/data/db/eleicoes2026.duckdb",
            "secoes_comparaveis": S("n"),
            "secoes_excluidas_sem_par": excluidas,
            "secoes_com_aptos_diferentes": aptos_dif,
            "brasil": {"termos": termos, "ganho": ganho,
                       "lula_1t": S("l1"), "lula_2t": S("l2"), "flavio_1t": S("f1"), "flavio_2t": S("f2")},
            "validacoes": val, "validacoes_ok": ok,
        },
        "finalistas": [{"nr": n, "nome": nomes[n]} for n in FINALISTAS],
        "demais": [{"nr": n, "nome": nomes[n]} for n in demais],
        "ufs": ufs,
        "mun": {"uf": [uf_idx[u] for u, _, _ in muns], "nome": [n for _, _, n in muns],
                "cd": [c for _, c, _ in muns], "fuso": [fuso.get((u, c)) for u, c, _ in muns]},
        "linhas": {**linhas, "d": [d_cols[n] for n in demais]},
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{a.out}: {os.path.getsize(a.out)/1e3:.0f} kB, {len(agg)} agrupamentos, {len(muns)} municípios")
    print(json.dumps(out["meta"]["brasil"], ensure_ascii=False))
    print(json.dumps(val, ensure_ascii=False))
    if not ok:
        sys.exit("VALIDAÇÃO FALHOU")


if __name__ == "__main__":
    main()
