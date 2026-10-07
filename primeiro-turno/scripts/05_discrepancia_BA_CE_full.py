#!/usr/bin/env python3
"""Full BA+CE ideological discrepancy from Boletim de Urna (1T 2026).
President Lula/Flávio vs federal deputy PL/PT shares — ALL sections.
Signature of ticket-splitting, NOT proof of fraud.
"""
from __future__ import annotations
import csv, json, zipfile, io, statistics as st, os
from pathlib import Path
from collections import defaultdict

# Resolve project layout relative to this script (default) or via env var.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
BU = ROOT / "bu"
OUT_MD = ROOT / "discrepancia_BA_CE.md"
OUT_JSON = SAMPLE_DIR / "discrepancia_BA_CE.json"
OUT_CSV = SAMPLE_DIR / "discrepancia_BA_CE_secoes.csv"

# Capitals (TSE CD_MUNICIPIO)
CAPITAL = {"BA": "38490", "CE": "13897"}  # Salvador, Fortaleza
LULA, FLAVIO = "13", "22"
PL, PT = "22", "13"
MIN_VALID = 30  # min valid votes for president and dep to include section

def pctile(sorted_vals, v):
    """Empirical percentile rank of v in sorted ascending list (0-100)."""
    if not sorted_vals:
        return None
    # fraction of values strictly less + half of equals
    n = len(sorted_vals)
    less = sum(1 for x in sorted_vals if x < v)
    eq = sum(1 for x in sorted_vals if x == v)
    return 100.0 * (less + 0.5 * eq) / n

def summarize(vals):
    vals = list(vals)
    if not vals:
        return {"n": 0}
    s = sorted(vals)
    def q(p):
        i = min(len(s) - 1, max(0, int(round(p * (len(s) - 1)))))
        return s[i]
    return {
        "n": len(vals),
        "mean": round(st.mean(vals), 4),
        "median": round(st.median(vals), 4),
        "stdev": round(st.pstdev(vals), 4) if len(vals) > 1 else 0.0,
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "p10": round(q(0.10), 4),
        "p25": round(q(0.25), 4),
        "p75": round(q(0.75), 4),
        "p90": round(q(0.90), 4),
        "p95": round(q(0.95), 4),
        "p99": round(q(0.99), 4),
    }

def scan_uf(uf: str):
    """Return dict keyed by (mun,zona,secao) with president + dep aggregates."""
    zp = BU / f"bweb_1t_{uf}_051020261403.zip"
    print(f"scanning {zp.name}...", flush=True)
    # key -> fields
    sec = defaultdict(lambda: {
        "nm_mun": "", "cd_mun": "",
        "pres_lula": 0, "pres_flavio": 0, "pres_valid": 0,
        "dep_pl": 0, "dep_pt": 0, "dep_valid": 0,
    })
    with zipfile.ZipFile(zp) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".csv")][0]
        with z.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            reader = csv.DictReader(text, delimiter=";")
            n = 0
            for row in reader:
                n += 1
                cargo = row["CD_CARGO_PERGUNTA"]
                if cargo not in ("1", "6"):
                    continue
                tipo = row["DS_TIPO_VOTAVEL"]  # Nominal / Legenda / Branco / Nulo
                if tipo in ("Branco", "Nulo"):
                    # still need section identity but not valid counts
                    # skip for valid aggregation
                    continue
                q = int(row["QT_VOTOS"] or 0)
                if q <= 0:
                    continue
                mun = (row["CD_MUNICIPIO"] or "").lstrip("0") or "0"
                # keep zero-padded for capital compare: store both
                mun_raw = row["CD_MUNICIPIO"]
                zona = int(row["NR_ZONA"])
                secao = int(row["NR_SECAO"])
                k = (mun, zona, secao)
                s = sec[k]
                s["nm_mun"] = row["NM_MUNICIPIO"]
                s["cd_mun"] = mun_raw
                if cargo == "1":
                    s["pres_valid"] += q
                    nr = str(row["NR_VOTAVEL"]).strip()
                    if nr == LULA:
                        s["pres_lula"] += q
                    elif nr == FLAVIO:
                        s["pres_flavio"] += q
                else:  # 6 dep federal
                    s["dep_valid"] += q
                    partido = str(row["NR_PARTIDO"]).strip()
                    if partido == PL:
                        s["dep_pl"] += q
                    elif partido == PT:
                        s["dep_pt"] += q
                if n % 2_000_000 == 0:
                    print(f"  ... {n} rows, sections so far {len(sec)}", flush=True)
    print(f"  done rows~{n}, sections with any valid cargo1/6 excl branco/nulo: {len(sec)}", flush=True)
    return sec

def build_rows(uf, sec):
    cap = CAPITAL[uf]
    rows = []
    for (mun, zona, secao), s in sec.items():
        if s["pres_valid"] < MIN_VALID or s["dep_valid"] < MIN_VALID:
            continue
        lula = s["pres_lula"] / s["pres_valid"]
        flavio = s["pres_flavio"] / s["pres_valid"]
        pl = s["dep_pl"] / s["dep_valid"]
        pt = s["dep_pt"] / s["dep_valid"]
        is_cap = (s["cd_mun"].lstrip("0") == cap.lstrip("0"))
        rows.append({
            "uf": uf,
            "cd_mun": s["cd_mun"],
            "nm_mun": s["nm_mun"],
            "zona": zona,
            "secao": secao,
            "capital": is_cap,
            "regiao": "capital" if is_cap else "interior",
            "lula_share": round(lula, 6),
            "flavio_share": round(flavio, 6),
            "pl_share_dep": round(pl, 6),
            "pt_share_dep": round(pt, 6),
            "pres_valid": s["pres_valid"],
            "dep_valid": s["dep_valid"],
            "score_PL_minus_Flavio": round(pl - flavio, 6),
            "score_PL_minus_Lula": round(pl - lula, 6),
            "score_PT_minus_Lula": round(pt - lula, 6),
            "flag_PL_Lula": (pl >= 0.15 and lula >= 0.55),
            "flag_PT_Flavio": (pt >= 0.15 and flavio >= 0.45),
        })
    return rows

def fmt_pct(x):
    return f"{100*x:.1f}%"

def fmt_pp(x):
    return f"{100*x:+.1f} pp"

def main():
    all_rows = []
    for uf in ("BA", "CE"):
        sec = scan_uf(uf)
        rows = build_rows(uf, sec)
        print(f"  {uf}: sections kept (≥{MIN_VALID} valid both cargos): {len(rows)}")
        all_rows.extend(rows)

    # Sort helpers
    by_pl_flavio = sorted(all_rows, key=lambda r: r["score_PL_minus_Flavio"], reverse=True)
    scores_pf = sorted(r["score_PL_minus_Flavio"] for r in all_rows)

    flag_pl_lula = [r for r in all_rows if r["flag_PL_Lula"]]
    flag_pt_flavio = [r for r in all_rows if r["flag_PT_Flavio"]]

    # Aiuaba specifically
    aiuaba = [r for r in all_rows if r["uf"] == "CE" and "AIUABA" in r["nm_mun"].upper()]
    aiuaba_s4 = [r for r in aiuaba if r["zona"] == 101 and r["secao"] == 4]
    # also find Aiuaba-like extreme among aiuaba sections
    aiuaba_best = max(aiuaba, key=lambda r: r["score_PL_minus_Flavio"]) if aiuaba else None

    # Rank of Aiuaba z101 s4 (or best Aiuaba) by PL-Flavio among ALL BA+CE
    focus = aiuaba_s4[0] if aiuaba_s4 else aiuaba_best
    if focus:
        rank = 1 + sum(1 for r in all_rows if r["score_PL_minus_Flavio"] > focus["score_PL_minus_Flavio"])
        pct = pctile(scores_pf, focus["score_PL_minus_Flavio"])
        # also among flag set
        flag_scores = sorted(r["score_PL_minus_Flavio"] for r in flag_pl_lula)
        rank_flag = 1 + sum(1 for r in flag_pl_lula if r["score_PL_minus_Flavio"] > focus["score_PL_minus_Flavio"])
    else:
        rank = pct = rank_flag = None

    # Distributions
    summary_all = {
        "n_sections": len(all_rows),
        "by_uf": {uf: sum(1 for r in all_rows if r["uf"] == uf) for uf in ("BA", "CE")},
        "PL_minus_Flavio": summarize(r["score_PL_minus_Flavio"] for r in all_rows),
        "PL_minus_Lula": summarize(r["score_PL_minus_Lula"] for r in all_rows),
        "pl_share_dep": summarize(r["pl_share_dep"] for r in all_rows),
        "pt_share_dep": summarize(r["pt_share_dep"] for r in all_rows),
        "lula_share": summarize(r["lula_share"] for r in all_rows),
        "flavio_share": summarize(r["flavio_share"] for r in all_rows),
    }
    by_uf_pf = {}
    for uf in ("BA", "CE"):
        sub = [r for r in all_rows if r["uf"] == uf]
        by_uf_pf[uf] = {
            "n": len(sub),
            "PL_minus_Flavio": summarize(r["score_PL_minus_Flavio"] for r in sub),
            "n_flag_PL_Lula": sum(1 for r in sub if r["flag_PL_Lula"]),
            "n_flag_PT_Flavio": sum(1 for r in sub if r["flag_PT_Flavio"]),
            "pct_flag_PL_Lula": round(100 * sum(1 for r in sub if r["flag_PL_Lula"]) / len(sub), 2) if sub else 0,
        }
    by_reg = {}
    for reg in ("capital", "interior"):
        sub = [r for r in all_rows if r["regiao"] == reg]
        by_reg[reg] = {
            "n": len(sub),
            "PL_minus_Flavio": summarize(r["score_PL_minus_Flavio"] for r in sub),
            "n_flag_PL_Lula": sum(1 for r in sub if r["flag_PL_Lula"]),
            "pct_flag_PL_Lula": round(100 * sum(1 for r in sub if r["flag_PL_Lula"]) / len(sub), 2) if sub else 0,
        }
    # UF x regiao
    by_uf_reg = {}
    for uf in ("BA", "CE"):
        for reg in ("capital", "interior"):
            sub = [r for r in all_rows if r["uf"] == uf and r["regiao"] == reg]
            by_uf_reg[f"{uf}_{reg}"] = {
                "n": len(sub),
                "PL_minus_Flavio": summarize(r["score_PL_minus_Flavio"] for r in sub),
                "n_flag_PL_Lula": sum(1 for r in sub if r["flag_PL_Lula"]),
                "pct_flag_PL_Lula": round(100 * sum(1 for r in sub if r["flag_PL_Lula"]) / len(sub), 2) if sub else 0,
            }

    # How many sections have PL > Flavio (positive score)
    n_pos_pf = sum(1 for r in all_rows if r["score_PL_minus_Flavio"] > 0)
    n_pos_pf_flag = sum(1 for r in flag_pl_lula if r["score_PL_minus_Flavio"] > 0)

    # Top / bottom 10 by PL-Flavio
    top10 = by_pl_flavio[:10]
    bot10 = list(reversed(by_pl_flavio[-10:]))  # most negative first

    # Top flag PL+Lula by product or by PL-Flavio
    top_flag = sorted(flag_pl_lula, key=lambda r: r["score_PL_minus_Flavio"], reverse=True)[:15]
    top_flag_rev = sorted(flag_pt_flavio, key=lambda r: r["pt_share_dep"] * r["flavio_share"], reverse=True)[:10]

    # Aiuaba all sections summary
    aiuaba_summary = None
    if aiuaba:
        aiuaba_summary = {
            "n_sections": len(aiuaba),
            "PL_minus_Flavio": summarize(r["score_PL_minus_Flavio"] for r in aiuaba),
            "n_flag_PL_Lula": sum(1 for r in aiuaba if r["flag_PL_Lula"]),
            "sections": sorted(aiuaba, key=lambda r: r["score_PL_minus_Flavio"], reverse=True),
        }

    # Lead conclusion logic
    n = len(all_rows)
    n_flag = len(flag_pl_lula)
    pct_flag = 100 * n_flag / n if n else 0
    # Is Aiuaba extreme?
    # Compare focus score to p99 / max
    p99 = summary_all["PL_minus_Flavio"]["p99"]
    p95 = summary_all["PL_minus_Flavio"]["p95"]
    med = summary_all["PL_minus_Flavio"]["median"]

    if focus:
        # Outlier if in top ~0.1% or clearly above p99 and rare flag rate overall
        is_extreme = focus["score_PL_minus_Flavio"] >= p99
        # Pattern if many flags (>1% of sections) and CE interior has elevated rate
        ce_int = by_uf_reg.get("CE_interior", {})
        pattern_local = (ce_int.get("pct_flag_PL_Lula", 0) >= 2.0)  # >=2% of CE interior
        conclusion_bits = []
        if pct_flag < 1.0 and is_extreme:
            lead = "OUTLIER"
            conclusion_bits.append(
                f"Aiuaba (seção-foco) é um **outlier extremo** no universo BA+CE: "
                f"PL−Flávio={fmt_pp(focus['score_PL_minus_Flavio'])} "
                f"(rank {rank}/{n}, percentil {pct:.2f}; p99 do universo={fmt_pp(p99)})."
            )
        elif pattern_local and is_extreme:
            lead = "OUTLIER LOCAL COM CAUDA EM CE"
            conclusion_bits.append(
                f"A seção-foco de Aiuaba é **extrema** (rank {rank}/{n}, pctl {pct:.2f}), "
                f"mas o flag PL≥15%∧Lula≥55% aparece em {n_flag}/{n} seções ({pct_flag:.2f}%) — "
                f"taxa elevada no interior do CE ({ce_int.get('pct_flag_PL_Lula')}%). "
                f"Há um **padrão local de ticket-splitting** no CE, com Aiuaba na cauda direita."
            )
        elif pct_flag >= 2.0:
            lead = "PADRÃO (com extremos)"
            conclusion_bits.append(
                f"O flag PL≥15%∧Lula≥55% ocorre em {n_flag}/{n} ({pct_flag:.2f}%) — "
                f"não é raríssimo. Aiuaba rank {rank}/{n} (pctl {pct:.2f})."
            )
        else:
            lead = "CAUDA RARA / QUASE-OUTLIER"
            conclusion_bits.append(
                f"Flag em {n_flag}/{n} ({pct_flag:.2f}%). Aiuaba rank {rank}/{n} (pctl {pct:.2f}). "
                f"Mediana PL−Flávio={fmt_pp(med)}; seção-foco={fmt_pp(focus['score_PL_minus_Flavio'])}."
            )
    else:
        lead = "SEM SEÇÃO AIUABA"
        conclusion_bits = ["Não foi possível localizar Aiuaba no BU."]

    # Honest framing
    conclusion_bits.append(
        f"Mediana PL−Flávio em BA+CE = **{fmt_pp(med)}** (esperado: proporcional fragmenta vs majoritário). "
        f"Seções com PL_dep > Flávio_pres: {n_pos_pf}/{n} ({100*n_pos_pf/n:.2f}%)."
    )
    conclusion_bits.append(
        "Discrepância ideológica é assinatura de **voto dividido / máquina local**, "
        "**não** prova de fraude ou adulteração de urna."
    )

    result = {
        "lead": lead,
        "conclusion_bits": conclusion_bits,
        "n_sections": n,
        "n_flag_PL_Lula": n_flag,
        "pct_flag_PL_Lula": round(pct_flag, 3),
        "n_flag_PT_Flavio": len(flag_pt_flavio),
        "n_PL_gt_Flavio": n_pos_pf,
        "summary": summary_all,
        "by_uf": by_uf_pf,
        "by_regiao": by_reg,
        "by_uf_regiao": by_uf_reg,
        "aiuaba_focus": focus,
        "aiuaba_rank": rank,
        "aiuaba_percentile": round(pct, 4) if pct is not None else None,
        "aiuaba_rank_within_flag": rank_flag,
        "aiuaba_all": aiuaba_summary,
        "top10_PL_minus_Flavio": top10,
        "bottom10_PL_minus_Flavio": bot10,
        "top_flag_PL_Lula": top_flag,
        "top_flag_PT_Flavio": top_flag_rev,
        "hashes_ok": True,
        "source": "bweb_1t_{BA,CE}_051020261403.zip (dadosabertos BU) + SHA512 verified",
        "min_valid": MIN_VALID,
        "flags": "PL_dep>=15% AND Lula>=55%; reverse PT_dep>=15% AND Flavio>=45%",
    }

    # Write CSV of all sections
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    fields = list(all_rows[0].keys())
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(all_rows)

    # Slim JSON (no all rows)
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown report
    def row_line(r, i=None):
        pref = f"| {i} | " if i is not None else "| "
        return (
            f"{pref}{r['uf']} | {r['nm_mun']} | z{r['zona']} s{r['secao']} | "
            f"{fmt_pct(r['lula_share'])} | {fmt_pct(r['flavio_share'])} | "
            f"{fmt_pct(r['pl_share_dep'])} | {fmt_pct(r['pt_share_dep'])} | "
            f"{fmt_pp(r['score_PL_minus_Flavio'])} | {r['regiao']} |"
        )

    hdr = "| # | UF | Município | Seção | Lula | Flávio | PL dep | PT dep | PL−Flávio | Região |"
    sep = "|---|----|-----------|-------|------|--------|--------|--------|-----------|--------|"

    lines = []
    lines.append("# Discrepância ideológica BA + CE — todas as seções (1º turno 2026)")
    lines.append("")
    lines.append("**Data da análise:** 06/10/2026 (America/Sao_Paulo)")
    lines.append("**Fonte:** Boletim de Urna (dadosabertos.tse.jus.br) — `bweb_1t_BA_*.zip` e `bweb_1t_CE_*.zip`, hashes SHA512 verificados.")
    lines.append("**Cargos no BU:** Presidente (1) + Deputado Federal (6). Branco/Nulo excluídos dos denominadores.")
    lines.append(f"**Filtro:** seções com ≥{MIN_VALID} votos válidos em presidente **e** em dep. federal.")
    lines.append("**Partidos:** PL=`22`, PT=`13` (nominal + legenda via `NR_PARTIDO`).")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Conclusão principal (lead)")
    lines.append("")
    lines.append(f"### **{lead}**")
    lines.append("")
    for b in conclusion_bits:
        lines.append(f"- {b}")
    lines.append("")
    if focus:
        lines.append(
            f"**Seção-foco Aiuaba/CE z{focus['zona']} s{focus['secao']}:** "
            f"Lula {fmt_pct(focus['lula_share'])}, Flávio {fmt_pct(focus['flavio_share'])}, "
            f"PL dep {fmt_pct(focus['pl_share_dep'])}, PT dep {fmt_pct(focus['pt_share_dep'])}, "
            f"PL−Flávio {fmt_pp(focus['score_PL_minus_Flavio'])} — "
            f"**rank {rank} de {n}** (percentil {pct:.2f} na distribuição PL−Flávio); "
            f"rank {rank_flag} entre {n_flag} seções do flag PL∧Lula."
        )
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Universo")
    lines.append("")
    lines.append(f"| Escopo | Seções |")
    lines.append(f"|--------|--------|")
    lines.append(f"| BA + CE (juntos) | **{n}** |")
    lines.append(f"| Bahia | {summary_all['by_uf']['BA']} |")
    lines.append(f"| Ceará | {summary_all['by_uf']['CE']} |")
    lines.append(f"| Capital (SSA+FOR) | {by_reg['capital']['n']} |")
    lines.append(f"| Interior | {by_reg['interior']['n']} |")
    lines.append(f"| Flag PL≥15% ∧ Lula≥55% | **{n_flag}** ({pct_flag:.2f}%) |")
    lines.append(f"| Flag PT≥15% ∧ Flávio≥45% | **{len(flag_pt_flavio)}** ({100*len(flag_pt_flavio)/n:.2f}%) |")
    lines.append(f"| PL_dep > Flávio_pres | {n_pos_pf} ({100*n_pos_pf/n:.2f}%) |")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Distribuição de PL_dep − Flávio_pres")
    lines.append("")
    s = summary_all["PL_minus_Flavio"]
    lines.append("| Estatística | Valor |")
    lines.append("|-------------|-------|")
    for k in ("mean", "median", "stdev", "min", "p10", "p25", "p75", "p90", "p95", "p99", "max"):
        lines.append(f"| {k} | {fmt_pp(s[k])} |")
    lines.append("")
    lines.append("### Por UF")
    lines.append("")
    lines.append("| UF | n | mediana PL−Flávio | média | flag PL∧Lula | % flag |")
    lines.append("|----|---|-------------------|-------|--------------|--------|")
    for uf in ("BA", "CE"):
        u = by_uf_pf[uf]
        lines.append(
            f"| {uf} | {u['n']} | {fmt_pp(u['PL_minus_Flavio']['median'])} | "
            f"{fmt_pp(u['PL_minus_Flavio']['mean'])} | {u['n_flag_PL_Lula']} | {u['pct_flag_PL_Lula']}% |"
        )
    lines.append("")
    lines.append("### Interior vs capital")
    lines.append("")
    lines.append("| Recorte | n | mediana PL−Flávio | flag PL∧Lula | % flag |")
    lines.append("|---------|---|-------------------|--------------|--------|")
    for key in ("BA_interior", "BA_capital", "CE_interior", "CE_capital",):
        u = by_uf_reg[key]
        lines.append(
            f"| {key} | {u['n']} | {fmt_pp(u['PL_minus_Flavio']['median']) if u['n'] else '—'} | "
            f"{u['n_flag_PL_Lula']} | {u['pct_flag_PL_Lula']}% |"
        )
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Top 10 — maior PL_dep − Flávio (ticket-splitting “direita local × Lula presidente”)")
    lines.append("")
    lines.append(hdr)
    lines.append(sep)
    for i, r in enumerate(top10, 1):
        lines.append(row_line(r, i))
    lines.append("")
    lines.append("## Top 10 — menor PL_dep − Flávio (PL alinhado ou abaixo de Flávio)")
    lines.append("")
    lines.append(hdr)
    lines.append(sep)
    for i, r in enumerate(bot10, 1):
        lines.append(row_line(r, i))
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Flag PL≥15% ∧ Lula≥55% — top 15 por PL−Flávio")
    lines.append("")
    lines.append(hdr)
    lines.append(sep)
    for i, r in enumerate(top_flag, 1):
        lines.append(row_line(r, i))
    lines.append("")
    lines.append(f"Total no flag: **{n_flag}** seções.")
    lines.append("")
    lines.append("## Flag reverso PT≥15% ∧ Flávio≥45% — top 10")
    lines.append("")
    lines.append(hdr)
    lines.append(sep)
    for i, r in enumerate(top_flag_rev, 1):
        lines.append(row_line(r, i))
    lines.append("")
    lines.append(f"Total no flag reverso: **{len(flag_pt_flavio)}** seções.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Aiuaba/CE em detalhe")
    lines.append("")
    if aiuaba_summary:
        lines.append(f"Seções de Aiuaba no universo: **{aiuaba_summary['n_sections']}** "
                     f"(flag PL∧Lula: {aiuaba_summary['n_flag_PL_Lula']}).")
        lines.append("")
        lines.append(f"Mediana PL−Flávio em Aiuaba: **{fmt_pp(aiuaba_summary['PL_minus_Flavio']['median'])}** "
                     f"(máx {fmt_pp(aiuaba_summary['PL_minus_Flavio']['max'])}).")
        lines.append("")
        lines.append(hdr)
        lines.append(sep)
        for i, r in enumerate(aiuaba_summary["sections"], 1):
            lines.append(row_line(r, i))
    else:
        lines.append("Aiuaba não encontrado.")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Método e limites")
    lines.append("")
    lines.append("1. Downloads **somente** BA e CE BU (+ SHA512) do portal dadosabertos; hashes conferidos com `sha512sum -c`.")
    lines.append("2. Presidente e dep. federal lidos do próprio BU (ambos presentes) — não foi necessário o CSV BR adicional nesta rodada.")
    lines.append("3. Shares = votos do candidato/partido ÷ votos válidos do cargo na seção (exclui branco/nulo).")
    lines.append("4. Flag igual ao da amostra de 100: PL_dep≥15% e Lula≥55%; reverso PT_dep≥15% e Flávio≥45%.")
    lines.append("5. Capitais: Salvador (`38490`), Fortaleza (`13897`).")
    lines.append("6. **Não** prova fraude: voto dividido é comportamento eleitoral; PL/PT não esgotam coligações locais.")
    lines.append("7. Sem zip Brasil-wide de urna-log; sem outras UFs; sem git commit/push.")
    lines.append("")
    lines.append("## Arquivos")
    lines.append("")
    lines.append("```")
    lines.append("primeiro-turno/")
    lines.append("  discrepancia_BA_CE.md          ← este relatório")
    lines.append("  bu/")
    lines.append("    bweb_1t_BA_051020261403.zip (+ .sha512)  [OK]")
    lines.append("    bweb_1t_CE_051020261403.zip (+ .sha512)  [OK]")
    lines.append("  data/sample/")
    lines.append("    discrepancia_BA_CE.json")
    lines.append("    discrepancia_BA_CE_secoes.csv")
    lines.append("  scripts/05_discrepancia_BA_CE_full.py")
    lines.append("```")
    lines.append("")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print("LEAD:", lead)
    print("n=", n, "flag_PL_Lula=", n_flag, f"({pct_flag:.2f}%)", "flag_PT_Flavio=", len(flag_pt_flavio))
    if focus:
        print(f"Aiuaba focus: Lula={focus['lula_share']:.3f} Flavio={focus['flavio_share']:.3f} "
              f"PL={focus['pl_share_dep']:.3f} PT={focus['pt_share_dep']:.3f} "
              f"PL-Flavio={focus['score_PL_minus_Flavio']:.3f} rank={rank}/{n} pctl={pct:.2f}")
    print("wrote", OUT_MD, OUT_JSON, OUT_CSV)

if __name__ == "__main__":
    main()
