#!/usr/bin/env python3
"""Compara os agregados do log com o boletim de urna (banco principal, somente leitura).

  python3 scripts/validate.py [--data data] [--banco ../totalizacoes/data/db/eleicoes2026.duckdb]

Gera <data>/validacao.md e <data>/validacao.json. Sai com erro só se faltar Parquet ou se houver
erros de leitura de log em mais de 1% das seções (divergências log × BU são reportadas, não bloqueiam).
Sem o banco principal, faz só as checagens internas.
"""
import argparse, json, os, sys

import duckdb

AQUI = os.path.dirname(os.path.abspath(__file__))


def pct(a, b):
    return round(100 * a / b, 3) if b else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(AQUI, "..", "data"))
    ap.add_argument("--banco", default=os.path.join(AQUI, "..", "..", "totalizacoes", "data", "db", "eleicoes2026.duckdb"))
    ap.add_argument("--exemplos", type=int, default=8)
    a = ap.parse_args()
    data = os.path.abspath(a.data)
    pq = os.path.join(data, "parquet", "eventos_secao", "*", "*", "data.parquet")
    con = duckdb.connect()
    try:
        con.execute(f"CREATE VIEW ev AS SELECT * FROM read_parquet('{pq}', hive_partitioning=false, union_by_name=true)")
    except duckdb.Error as e:
        sys.exit(f"ERRO: Parquet de eventos ausente ({e})")
    R = {"por_uf": {}}
    md = ["# Validação — logs de urna × boletim de urna", "",
          "Gerado por `scripts/validate.py`. Horários comparados como hora do dia (TIME), sem fuso. "
          "Divergências são descritas, não interpretadas.", ""]
    internos = con.execute("""SELECT nr_turno, sg_uf, count(*) n, count(*) FILTER (erro IS NOT NULL) err,
        sum(n_votos_log) votos, count(*) FILTER (n_votos_log = 0) sem_voto,
        count(*) FILTER (n_arquivos_log > 1) arq, count(*) FILTER (n_urnas_com_voto > 1) urnas,
        sum(n_votos_fora_do_dia) fora FROM ev GROUP BY ALL ORDER BY ALL""").fetchall()
    falha = False
    md += ["## Checagens internas", "", "| turno | UF | seções (logs) | erro de leitura | votos no log | seções com 0 voto no log | seções com log arquivado (.jez aninhado) | seções com votos em >1 urna | votos com data ≠ dia da eleição |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for t, uf, n, err, votos, sv, arq, urnas, fora in internos:
        md.append(f"| {t} | {uf} | {n:,} | {err:,} | {votos:,} | {sv:,} | {arq:,} | {urnas:,} | {fora:,} |")
        R["por_uf"][f"{t}_{uf}"] = {"secoes_log": n, "erros": err, "votos_log": votos, "secoes_sem_voto": sv,
                                    "secoes_log_arquivado": arq, "secoes_multiplas_urnas_com_voto": urnas,
                                    "votos_fora_do_dia": fora}
        if err > 0.01 * n:
            falha = True
    md.append("")
    if not os.path.exists(a.banco):
        md += [f"Banco principal não encontrado em `{a.banco}`: comparação com o BU pulada "
               "(rode `cd ../totalizacoes && ./run.sh fetch`)."]
    else:
        con.execute(f"ATTACH '{a.banco}' AS tse (READ_ONLY)")
        con.execute("""CREATE TEMP VIEW j AS
            SELECT s.nr_turno, s.sg_uf, s.cd_municipio, s.nm_municipio, s.nr_zona, s.nr_secao, s.qt_aptos,
                   s.qt_comparecimento, s.qt_elei_biom_sem_habilitacao, s.dt_abertura, s.dt_encerramento,
                   s.ds_secoes_agregadas, e.* EXCLUDE (nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao),
                   e.arquivo_log IS NOT NULL AS tem_log
            FROM (SELECT * FROM tse.secoes WHERE cd_cargo = 1
                  AND (nr_turno, sg_uf) IN (SELECT DISTINCT nr_turno, sg_uf FROM ev)) s
            FULL JOIN ev e USING (nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao)""")
        rows = con.execute("""SELECT nr_turno, sg_uf,
              count(*) FILTER (qt_aptos IS NOT NULL) bu, count(*) FILTER (tem_log) log,
              count(*) FILTER (qt_aptos IS NOT NULL AND tem_log) ambos,
              count(*) FILTER (qt_aptos IS NULL) so_log, count(*) FILTER (NOT tem_log) so_bu,
              count(*) FILTER (n_votos_log = qt_comparecimento) v_eq,
              count(*) FILTER (abs(n_votos_log - qt_comparecimento) <= 2) v_2,
              sum(qt_comparecimento) FILTER (tem_log) comp, sum(n_votos_log) FILTER (qt_aptos IS NOT NULL) vl,
              count(*) FILTER (hr_abertura_log = dt_abertura::TIME) ab_eq,
              count(*) FILTER (abs(epoch(hr_abertura_log) - epoch(dt_abertura::TIME)) <= 60) ab_60,
              count(*) FILTER (hr_abertura_log IS NOT NULL AND dt_abertura IS NOT NULL) ab_n,
              count(*) FILTER (hr_encerramento_log = dt_encerramento::TIME) en_eq,
              count(*) FILTER (abs(epoch(hr_encerramento_log) - epoch(dt_encerramento::TIME)) <= 60) en_60,
              count(*) FILTER (hr_encerramento_log IS NOT NULL AND dt_encerramento IS NOT NULL) en_n,
              count(*) FILTER (n_hab_manual = qt_elei_biom_sem_habilitacao) man_eq,
              count(*) FILTER (n_hab_manual IS NOT NULL AND qt_elei_biom_sem_habilitacao IS NOT NULL) man_n,
              sum(n_hab_manual) man_log, sum(qt_elei_biom_sem_habilitacao) FILTER (tem_log) man_bu,
              count(*) FILTER (n_habilitados = n_votos_log) hab_eq
            FROM j GROUP BY ALL ORDER BY ALL""").fetchall()
        md += ["## Cobertura e concordância com o boletim de urna (cargo presidente, 1 linha por seção)", "",
               "| turno | UF | seções no BU | seções com log | em ambos | só log | só BU | votos log = comparecimento | dif. ≤ 2 | Σ comparecimento | Σ votos log |",
               "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for r in rows:
            (t, uf, bu, lg, amb, sl, sb, veq, v2, comp, vl, abeq, ab60, abn, eneq, en60, enn, maneq, mann, manl, manb, habeq) = r
            md.append(f"| {t} | {uf} | {bu:,} | {lg:,} | {amb:,} | {sl:,} | {sb:,} | {veq:,} ({pct(veq, amb)}%) | "
                      f"{v2:,} ({pct(v2, amb)}%) | {comp or 0:,} | {vl or 0:,} |")
            R["por_uf"][f"{t}_{uf}"].update({
                "secoes_bu": bu, "secoes_ambos": amb, "so_log": sl, "so_bu": sb,
                "votos_iguais": veq, "pct_votos_iguais": pct(veq, amb), "votos_dif_le2": v2,
                "soma_comparecimento": comp, "soma_votos_log": vl,
                "abertura_igual": abeq, "pct_abertura_igual": pct(abeq, abn), "abertura_le60s": ab60, "abertura_n": abn,
                "encerramento_igual": eneq, "pct_encerramento_igual": pct(eneq, enn), "encerramento_le60s": en60, "encerramento_n": enn,
                "hab_manual_igual_bu": maneq, "pct_hab_manual_igual_bu": pct(maneq, mann),
                "soma_hab_manual_log": manl, "soma_biom_sem_habilitacao_bu": manb,
                "habilitados_igual_votos": habeq})
        md += ["", "| turno | UF | abertura log = `dt_abertura` | ≤ 60 s | encerramento log = `dt_encerramento` | ≤ 60 s | hab. manual log = `qt_elei_biom_sem_habilitacao` | Σ manual log | Σ BU |",
               "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
        for k, v in R["por_uf"].items():
            if "abertura_n" not in v:
                continue
            t, uf = k.split("_")
            md.append(f"| {t} | {uf} | {v['abertura_igual']:,} / {v['abertura_n']:,} ({v['pct_abertura_igual']}%) | {v['abertura_le60s']:,} | "
                      f"{v['encerramento_igual']:,} / {v['encerramento_n']:,} ({v['pct_encerramento_igual']}%) | {v['encerramento_le60s']:,} | "
                      f"{v['hab_manual_igual_bu']:,} ({v['pct_hab_manual_igual_bu']}%) | {v['soma_hab_manual_log']:,} | {v['soma_biom_sem_habilitacao_bu']:,} |")
        # distribuição das diferenças de votos
        dist = con.execute("""SELECT nr_turno, sg_uf, n_votos_log - qt_comparecimento d, count(*) FROM j
            WHERE tem_log AND qt_aptos IS NOT NULL AND n_votos_log <> qt_comparecimento GROUP BY ALL ORDER BY 1, 2, 4 DESC LIMIT 40""").fetchall()
        md += ["", "### Diferença votos no log − comparecimento do BU (só seções que divergem)", "",
               "| turno | UF | diferença | seções |", "|---|---|---:|---:|"]
        md += [f"| {t} | {uf} | {d:+,} | {n:,} |" for t, uf, d, n in dist]
        R["dist_dif_votos"] = [[t, uf, d, n] for t, uf, d, n in dist]
        ex = con.execute(f"""SELECT sg_uf, nm_municipio, cd_municipio, nr_zona, nr_secao, qt_comparecimento, n_votos_log,
                n_arquivos_log, n_urnas_log, n_urnas_com_voto, n_votos_fora_do_dia, hr_abertura_log, dt_abertura::TIME,
                hr_primeiro_voto, hr_ultimo_voto, ds_secoes_agregadas
            FROM j WHERE tem_log AND qt_aptos IS NOT NULL AND n_votos_log <> qt_comparecimento
            ORDER BY abs(n_votos_log - qt_comparecimento) DESC LIMIT {a.exemplos}""").fetchall()
        md += ["", "### Exemplos de divergência de votos (maiores diferenças absolutas)", "",
               "| UF | município | zona | seção | comparec. BU | votos log | arquivos de log | urnas no log | urnas c/ voto | votos fora do dia | abertura log | abertura BU | 1º voto | último voto | seções agregadas |",
               "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|"]
        for e in ex:
            md.append("| " + " | ".join("" if x is None else str(x) for x in (e[0], f"{e[1]} ({e[2]})", *e[3:])) + " |")
        R["exemplos_div_votos"] = [[str(x) for x in e] for e in ex]
        so = con.execute("""SELECT 'só BU' lado, sg_uf, nm_municipio, nr_zona, nr_secao, qt_comparecimento FROM j WHERE NOT tem_log
                            UNION ALL SELECT 'só log', sg_uf, NULL, nr_zona, nr_secao, n_votos_log FROM j WHERE qt_aptos IS NULL
                            ORDER BY 1, 2 LIMIT 20""").fetchall()
        if so:
            md += ["", "### Seções presentes em só um dos lados (até 20)", "", "| lado | UF | município | zona | seção | votos |", "|---|---|---|---:|---:|---:|"]
            md += ["| " + " | ".join("" if x is None else str(x) for x in r) + " |" for r in so]
        # abertura: distribuição da hora (fuso) e divergências
        hz = con.execute("""SELECT nr_turno, sg_uf, hour(hr_abertura_log) h, count(*) FROM j WHERE tem_log
                            GROUP BY ALL ORDER BY 1, 2, 4 DESC""").fetchall()
        md += ["", "### Hora de abertura segundo o log (hora do relógio da urna)", "", "| turno | UF | hora | seções |", "|---|---|---:|---:|"]
        md += [f"| {t} | {uf} | {'' if h is None else h} | {n:,} |" for t, uf, h, n in hz if n >= 5 or h is None]
        R["hora_abertura"] = [[t, uf, h, n] for t, uf, h, n in hz]
        dab = con.execute("""SELECT nr_turno, sg_uf,
              count(*) FILTER (epoch(hr_abertura_log) - epoch(dt_abertura::TIME) BETWEEN -3600 AND -61) menos,
              count(*) FILTER (epoch(hr_abertura_log) - epoch(dt_abertura::TIME) BETWEEN 61 AND 36000) mais,
              count(*) FILTER (hr_abertura_log IS NULL) sem
            FROM j WHERE tem_log AND qt_aptos IS NOT NULL GROUP BY ALL ORDER BY ALL""").fetchall()
        md += ["", "Abertura: seções em que o log é > 60 s antes / depois do `dt_abertura` do BU, e sem a mensagem de abertura:", "",
               "| turno | UF | log antes | log depois | sem 'Urna pronta para receber votos' |", "|---|---|---:|---:|---:|"]
        md += [f"| {t} | {uf} | {a_:,} | {b_:,} | {c_:,} |" for t, uf, a_, b_, c_ in dab]
    open(os.path.join(data, "validacao.md"), "w").write("\n".join(md) + "\n")
    json.dump(R, open(os.path.join(data, "validacao.json"), "w"), indent=1, ensure_ascii=False, default=str)
    print("\n".join(md))
    if falha:
        sys.exit("ERRO: mais de 1% das seções com erro de leitura do log")


if __name__ == "__main__":
    main()
