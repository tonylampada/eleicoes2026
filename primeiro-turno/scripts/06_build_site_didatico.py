#!/usr/bin/env python3
"""Build didactic here.now site: late-day concentration + biometria habilitação + ideological discrepancy."""
from __future__ import annotations

import csv
import json
import math
import statistics
import os
from pathlib import Path

# Resolve project layout relative to this script (default) or via env var.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
SAMPLE = SAMPLE_DIR
OUT = ROOT / "site-didatico"
DATA = OUT / "data"


def pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def pct(x, digits=1):
    if x is None:
        return None
    return round(100 * x, digits)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    with open(SAMPLE / "log_aggregates.json", encoding="utf-8") as f:
        agg = json.load(f)
    with open(SAMPLE / "amostra100.json", encoding="utf-8") as f:
        amostra = json.load(f)
    with open(SAMPLE / "analise_logs_tarde.json", encoding="utf-8") as f:
        analise = json.load(f)
    with open(SAMPLE / "discrepancia_BA_CE.json", encoding="utf-8") as f:
        disc_sum = json.load(f)
    bio_path = SAMPLE / "biometria_logs.json"
    if not bio_path.exists():
        raise SystemExit("missing sample/biometria_logs.json — run 07_biometria_logs.py first")
    with open(bio_path, encoding="utf-8") as f:
        bio = json.load(f)
    bio_by_key = {}
    for r in bio.get("results") or []:
        if r.get("key") and "erro" not in r and (r.get("n_hab") or 0) > 0:
            bio_by_key[r["key"]] = r

    # index amostra by (uf, zona, secao)
    am_idx = {}
    for row in amostra:
        am_idx[(row["uf"], int(row["zona"]), int(row["secao"]))] = row

    log_rows = []
    for r in agg["results"]:
        if not r.get("n_votos_log"):
            continue
        key = (r["uf"], int(r["zona"]), int(r["secao"]))
        am = am_idx.get(key, {})
        flavio = am.get("flavio_share")
        if flavio is None and am.get("flavio") is not None and am.get("valid"):
            flavio = am["flavio"] / am["valid"]
        hours = r.get("hours") or {}
        # normalize hours keys to int strings 06-19
        hours_out = {str(h).zfill(2): int(hours.get(str(h).zfill(2), hours.get(str(h), 0)) or 0)
                     for h in range(6, 20)}
        b = bio_by_key.get(r.get("key") or "")
        row_out = {
            "uf": r["uf"],
            "nm_mun": r.get("nm_mun") or am.get("nm_mun") or "",
            "zona": int(r["zona"]),
            "secao": int(r["secao"]),
            "n_votos_log": int(r["n_votos_log"]),
            "concentracao_16": round(float(r["share_after16"]), 4),
            "concentracao_17": round(float(r["share_after17"]), 4),
            "lula_share": round(float(r["lula_share"]), 4) if r.get("lula_share") is not None else None,
            "flavio_share": round(float(flavio), 4) if flavio is not None else None,
            "first_ts": r.get("first_ts"),
            "last_ts": r.get("last_ts"),
            "hours": hours_out,
            "estrato": r.get("estrato") or am.get("estrato"),
            "key": r.get("key"),
        }
        if b:
            row_out.update({
                "n_hab": b["n_hab"],
                "n_bio": b["n_bio"],
                "n_nao_bio": b["n_nao_bio"],
                "share_bio": b["share_bio"],
                "share_nao_bio": b["share_nao_bio"],
                "bio_after16": b.get("bio_after16"),
                "nao_bio_after16": b.get("nao_bio_after16"),
                "share_nao_bio_after16": b.get("share_nao_bio_after16"),
                "bio_after17": b.get("bio_after17"),
                "nao_bio_after17": b.get("nao_bio_after17"),
                "share_nao_bio_after17": b.get("share_nao_bio_after17"),
                "hours_bio": b.get("hours_bio"),
                "hours_nao_bio": b.get("hours_nao_bio"),
            })
        log_rows.append(row_out)

    # correlations (only rows with lula/flavio)
    xs16 = [r["concentracao_16"] for r in log_rows if r["lula_share"] is not None]
    ys_l = [r["lula_share"] for r in log_rows if r["lula_share"] is not None]
    xs17 = [r["concentracao_17"] for r in log_rows if r["lula_share"] is not None]
    r_lula_16 = pearson(xs16, ys_l)
    r_lula_17 = pearson(xs17, ys_l)

    flavio_rows = [r for r in log_rows if r["flavio_share"] is not None]
    r_flavio_16 = pearson([r["concentracao_16"] for r in flavio_rows],
                          [r["flavio_share"] for r in flavio_rows])
    r_flavio_17 = pearson([r["concentracao_17"] for r in flavio_rows],
                          [r["flavio_share"] for r in flavio_rows])

    c16 = [r["concentracao_16"] for r in log_rows]
    c17 = [r["concentracao_17"] for r in log_rows]

    def dist_stats(vals):
        vals = sorted(vals)
        n = len(vals)
        def q(p):
            if n == 0:
                return None
            i = min(n - 1, max(0, int(round(p * (n - 1)))))
            return vals[i]
        return {
            "n": n,
            "mean": round(statistics.mean(vals), 4) if n else None,
            "median": round(statistics.median(vals), 4) if n else None,
            "stdev": round(statistics.pstdev(vals), 4) if n > 1 else 0.0,
            "min": round(vals[0], 4) if n else None,
            "max": round(vals[-1], 4) if n else None,
            "p90": round(q(0.90), 4),
            "p95": round(q(0.95), 4),
        }

    # pick extreme / flat examples
    extreme = max(log_rows, key=lambda r: r["concentracao_16"])
    # prefer Acre flat with 0% after16
    flats = [r for r in log_rows if r["uf"] == "AC" and r["concentracao_16"] == 0]
    flat = flats[0] if flats else min(log_rows, key=lambda r: r["concentracao_16"])

    top_late = sorted(log_rows, key=lambda r: r["concentracao_16"], reverse=True)[:15]

    bio_ov = bio["overall"]
    bio_ex = bio["extreme_example"]
    bio_corr = bio["correlation"]
    meta = {
        "titulo": "Concentração + biometria — aula 2026",
        "n_logs": len(log_rows),
        "n_ba_ce": disc_sum["n_sections"],
        "n_bio_sections": bio_ov["n_sections"],
        "corr": {
            "r_lula_concentracao_16": round(r_lula_16, 4) if r_lula_16 is not None else None,
            "r_lula_concentracao_17": round(r_lula_17, 4) if r_lula_17 is not None else None,
            "r_flavio_concentracao_16": round(r_flavio_16, 4) if r_flavio_16 is not None else None,
            "r_flavio_concentracao_17": round(r_flavio_17, 4) if r_flavio_17 is not None else None,
            "n": len(xs16),
            "n_flavio": len(flavio_rows),
        },
        "dist_16": dist_stats(c16),
        "dist_17": dist_stats(c17),
        "prior_corr_check": {
            "analise_r16": analise.get("corr_lula_share_vs_after16"),
            "analise_r17": analise.get("corr_lula_share_vs_after17"),
        },
        "exemplos": {
            "extrema": {
                "uf": extreme["uf"],
                "nm_mun": extreme["nm_mun"],
                "zona": extreme["zona"],
                "secao": extreme["secao"],
                "concentracao_16": extreme["concentracao_16"],
                "concentracao_17": extreme["concentracao_17"],
                "lula_share": extreme["lula_share"],
                "flavio_share": extreme["flavio_share"],
                "n_votos_log": extreme["n_votos_log"],
                "first_ts": extreme["first_ts"],
                "last_ts": extreme["last_ts"],
                "hours": extreme["hours"],
            },
            "plana": {
                "uf": flat["uf"],
                "nm_mun": flat["nm_mun"],
                "zona": flat["zona"],
                "secao": flat["secao"],
                "concentracao_16": flat["concentracao_16"],
                "concentracao_17": flat["concentracao_17"],
                "lula_share": flat["lula_share"],
                "flavio_share": flat["flavio_share"],
                "n_votos_log": flat["n_votos_log"],
                "first_ts": flat["first_ts"],
                "last_ts": flat["last_ts"],
                "hours": flat["hours"],
            },
        },
        "top_late": [
            {
                "uf": r["uf"], "nm_mun": r["nm_mun"], "zona": r["zona"], "secao": r["secao"],
                "concentracao_16": r["concentracao_16"], "concentracao_17": r["concentracao_17"],
                "lula_share": r["lula_share"], "flavio_share": r["flavio_share"],
                "last_ts": r["last_ts"], "n_votos_log": r["n_votos_log"],
            }
            for r in top_late
        ],
        "discrepancia": {
            "n_sections": disc_sum["n_sections"],
            "n_flag_PL_Lula": disc_sum["n_flag_PL_Lula"],
            "pct_flag_PL_Lula": disc_sum["pct_flag_PL_Lula"],
            "n_flag_PT_Flavio": disc_sum["n_flag_PT_Flavio"],
            "n_PL_gt_Flavio": disc_sum["n_PL_gt_Flavio"],
            "by_uf": disc_sum.get("by_uf"),
            "PL_minus_Flavio": disc_sum["summary"]["PL_minus_Flavio"],
            "aiuaba_focus": disc_sum.get("aiuaba_focus"),
            "aiuaba_percentile": disc_sum.get("aiuaba_percentile"),
            "aiuaba_rank": disc_sum.get("aiuaba_rank"),
            "top10": disc_sum.get("top10_PL_minus_Flavio", [])[:10],
            "lead": disc_sum.get("lead"),
            "conclusion_bits": disc_sum.get("conclusion_bits"),
            "stronger_thresholds": disc_sum.get("stronger_thresholds"),
        },
        "metricas": {
            "concentracao_16": "fração de votos no log com horário ≥ 16:00",
            "concentracao_17": "fração de votos no log com horário ≥ 17:00",
            "flavio": "candidato 22 (PL) a presidente — campo Bolsonaro",
            "lula": "candidato 13 (PT) a presidente",
        },
        "caveats": [
            "Concentração no fim do dia exige LOG da urna (timestamps). Só temos ~99 seções com log na amostra deliberada — não é o Brasil.",
            "Correlação moderada (r≈0,3) ≠ prova de fraude. Fila às 17h explica cauda longa no interior.",
            "Discrepância ideológica (PL dep. alto + Lula alto) é ticket-splitting / máquina local — padrão frequente no CE.",
            "Biometria no log = modo de habilitação (biométrica vs manual/nascimento). Não identifica eleitor nem voto. Sucesso biométrico não é obrigatório (até 4 tentativas → fallback).",
        ],
        "biometria": {
            "overall": {
                "n_sections": bio_ov["n_sections"],
                "n_hab": bio_ov["n_hab"],
                "n_bio": bio_ov["n_bio"],
                "n_nao_bio": bio_ov["n_nao_bio"],
                "share_bio": bio_ov["share_bio"],
                "share_nao_bio": bio_ov["share_nao_bio"],
                "after16": bio_ov["after16"],
                "after17": bio_ov["after17"],
                "early_before16": bio_ov["early_before16"],
                "late_vs_early_enrichment_nao_bio": bio_ov["late_vs_early_enrichment_nao_bio"],
                "section_share_nao_bio": bio_ov["section_share_nao_bio"],
            },
            "correlation": bio_corr,
            "extreme": {
                "uf": bio_ex["uf"],
                "nm_mun": bio_ex["nm_mun"],
                "zona": bio_ex["zona"],
                "secao": bio_ex["secao"],
                "n_hab": bio_ex["n_hab"],
                "n_bio": bio_ex["n_bio"],
                "n_nao_bio": bio_ex["n_nao_bio"],
                "share_bio": bio_ex["share_bio"],
                "share_nao_bio": bio_ex["share_nao_bio"],
                "concentracao_16": bio_ex.get("concentracao_16"),
                "concentracao_17": bio_ex.get("concentracao_17"),
                "after16": bio_ex["after16"],
                "after17": bio_ex["after17"],
                "early_before16": bio_ex["early_before16"],
                "hours_bio": bio_ex["hours_bio"],
                "hours_nao_bio": bio_ex["hours_nao_bio"],
                "lula_share": bio_ex.get("lula_share"),
            },
            "method": bio.get("method"),
        },
    }

    # write secoes_logs.json
    with open(DATA / "secoes_logs.json", "w", encoding="utf-8") as f:
        json.dump(log_rows, f, ensure_ascii=False, separators=(",", ":"))

    # lean BA+CE
    ba_ce = []
    with open(SAMPLE / "discrepancia_BA_CE_secoes.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ba_ce.append({
                "uf": row["uf"],
                "m": row["nm_mun"],
                "z": int(row["zona"]),
                "s": int(row["secao"]),
                "l": round(float(row["lula_share"]), 4),
                "f": round(float(row["flavio_share"]), 4),
                "pl": round(float(row["pl_share_dep"]), 4),
                "pt": round(float(row["pt_share_dep"]), 4),
                "g": round(float(row["score_PL_minus_Flavio"]), 4),
                "fl": 1 if row["flag_PL_Lula"] in ("True", "true", "1") else 0,
            })
    with open(DATA / "secoes_ba_ce.json", "w", encoding="utf-8") as f:
        json.dump(ba_ce, f, ensure_ascii=False, separators=(",", ":"))

    with open(DATA / "meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # also a compact combined for embedding small parts
    with open(DATA / "resumo.json", "w", encoding="utf-8") as f:
        json.dump({
            "meta": meta,
            "logs": log_rows,  # only ~99 — embeddable
        }, f, ensure_ascii=False, separators=(",", ":"))

    write_site(meta, log_rows)

    # verification print
    print("=== BUILD OK ===")
    print(f"n_logs={len(log_rows)}")
    print(f"r(Lula, c16)={r_lula_16:.4f}  prior={analise.get('corr_lula_share_vs_after16')}")
    print(f"r(Lula, c17)={r_lula_17:.4f}  prior={analise.get('corr_lula_share_vs_after17')}")
    print(f"r(Flávio, c16)={r_flavio_16:.4f}" if r_flavio_16 else "r(Flávio,c16)=None")
    print(f"extreme: {extreme['nm_mun']}/{extreme['uf']} c16={extreme['concentracao_16']} c17={extreme['concentracao_17']} last={extreme['last_ts']}")
    print(f"flat: {flat['nm_mun']}/{flat['uf']} c16={flat['concentracao_16']}")
    print(f"ba_ce rows={len(ba_ce)}")
    print(f"bio share_bio={bio_ov['share_bio']} share_nao={bio_ov['share_nao_bio']} enrichment={bio_ov['late_vs_early_enrichment_nao_bio']}")
    print(f"bio corr nao vs c16={bio_corr.get('share_nao_bio_vs_concentracao_16')}")
    for p in sorted(OUT.rglob("*")):
        if p.is_file():
            print(f"  {p.relative_to(OUT)}  {p.stat().st_size} bytes")


def write_site(meta, log_rows):
    # Embed logs + meta in page (small); BA+CE loaded async
    embed = {
        "meta": meta,
        "logs": log_rows,
    }
    embed_js = json.dumps(embed, ensure_ascii=False, separators=(",", ":"))

    css = CSS
    html = HTML_TEMPLATE.replace("/*__CSS__*/", css).replace("__EMBED__", embed_js)
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / "app.js").write_text(APP_JS, encoding="utf-8")
    (OUT / "styles.css").write_text(css, encoding="utf-8")


CSS = r"""
:root {
  --bg: #0b1020;
  --bg2: #121a2e;
  --card: #162038;
  --line: rgba(255,255,255,0.08);
  --text: #eef3ff;
  --muted: #9aa8c7;
  --accent: #5ee1a4;
  --accent2: #7eb6ff;
  --warn: #f5c542;
  --hot: #ff7a7a;
  --cool: #6ec8ff;
  --flavio: #f0a05a;
  --lula: #6ad0a0;
  --bar-late: #ff8a6a;
  --bar-norm: #5b8def;
  --radius: 14px;
  --font: "Segoe UI", system-ui, -apple-system, sans-serif;
  --mono: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0; font: 16px/1.55 var(--font); background: var(--bg); color: var(--text);
  background-image:
    radial-gradient(ellipse 80% 50% at 10% -10%, #1a3a5c55, transparent),
    radial-gradient(ellipse 60% 40% at 90% 0%, #3a1a4c33, transparent);
  min-height: 100vh;
}
a { color: var(--accent2); }
main { max-width: 1100px; margin: 0 auto; padding: 1.5rem 1.1rem 4rem; }
.tag {
  display: inline-block; font-size: .72rem; letter-spacing: .04em; text-transform: uppercase;
  padding: .2rem .65rem; border-radius: 999px; border: 1px solid var(--line);
  color: var(--muted); background: var(--bg2); margin-bottom: .75rem;
}
h1 { font-size: clamp(1.45rem, 3.5vw, 2rem); line-height: 1.2; margin: 0 0 .4rem; }
h2 {
  font-size: 1.25rem; margin: 2.4rem 0 .7rem; padding-top: .4rem;
  border-top: 1px solid var(--line);
}
h2 .num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 1.7rem; height: 1.7rem; border-radius: 8px; background: var(--accent);
  color: #0b1020; font-size: .95rem; font-weight: 800; margin-right: .5rem;
}
h3 { font-size: 1rem; margin: 0 0 .5rem; }
.lead { font-size: 1.05rem; color: var(--muted); margin: .5rem 0 1.2rem; max-width: 62ch; }
.muted { color: var(--muted); }
.note {
  background: #1a2438; border-left: 3px solid var(--warn);
  padding: .85rem 1rem; border-radius: 0 12px 12px 0; margin: 1rem 0 1.4rem;
  font-size: .95rem;
}
.note strong { color: var(--warn); }
.caveat {
  background: #1a2030; border: 1px dashed var(--line); border-radius: var(--radius);
  padding: .9rem 1.1rem; margin: 1.2rem 0; font-size: .9rem; color: var(--muted);
}
.grid2 { display: grid; gap: 1rem; grid-template-columns: 1fr; }
@media (min-width: 780px) { .grid2 { grid-template-columns: 1fr 1fr; } }
.card {
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 1rem 1.1rem 1.15rem;
}
.card.hot { border-color: #ff7a7a55; box-shadow: 0 0 0 1px #ff7a7a22 inset; }
.card.cool { border-color: #6ec8ff44; box-shadow: 0 0 0 1px #6ec8ff18 inset; }
.card .label {
  font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
  color: var(--muted); margin-bottom: .35rem;
}
.card .place { font-weight: 700; font-size: 1.05rem; margin-bottom: .15rem; }
.card .meta-line { font-size: .82rem; color: var(--muted); margin-bottom: .75rem; }
.metric-big {
  display: flex; gap: 1rem; flex-wrap: wrap; margin-top: .85rem;
  padding-top: .75rem; border-top: 1px solid var(--line);
}
.metric-big .m {
  flex: 1; min-width: 110px; text-align: center;
  background: var(--bg2); border-radius: 10px; padding: .55rem .4rem;
}
.metric-big .m .v {
  font-size: 1.65rem; font-weight: 800; font-variant-numeric: tabular-nums;
  line-height: 1.1;
}
.metric-big .m .v.hot { color: var(--hot); }
.metric-big .m .v.cool { color: var(--cool); }
.metric-big .m .k { font-size: .7rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; margin-top: .15rem; }
.chart-wrap { width: 100%; overflow-x: auto; }
.chart-wrap svg { display: block; width: 100%; height: auto; max-height: 220px; }
.legend-row {
  display: flex; gap: .9rem; flex-wrap: wrap; font-size: .8rem; color: var(--muted);
  margin: .4rem 0 .8rem;
}
.legend-row span::before {
  content: ""; display: inline-block; width: .7rem; height: .7rem;
  border-radius: 2px; margin-right: .35rem; vertical-align: -1px;
}
.legend-row .late::before { background: var(--bar-late); }
.legend-row .norm::before { background: var(--bar-norm); }
.def-box {
  background: var(--bg2); border: 1px solid var(--line); border-radius: var(--radius);
  padding: 1rem 1.15rem; margin: 1rem 0 1.4rem; font-family: var(--mono); font-size: .88rem;
}
.def-box .formula { color: var(--accent); font-size: 1.05rem; margin: .3rem 0; }
.chips { display: flex; flex-wrap: wrap; gap: .45rem; margin: .6rem 0 1rem; }
.chip {
  font-size: .78rem; padding: .28rem .6rem; border-radius: 999px;
  background: var(--bg2); border: 1px solid var(--line); color: var(--text);
  cursor: default;
}
.chip b { color: var(--hot); font-variant-numeric: tabular-nums; }
.stats-row {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: .6rem; margin: .8rem 0 1.2rem;
}
.stat {
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: .65rem .75rem; text-align: center;
}
.stat .v { font-size: 1.35rem; font-weight: 800; font-variant-numeric: tabular-nums; color: var(--accent); }
.stat .k { font-size: .72rem; color: var(--muted); margin-top: .1rem; }
.scatter-box {
  background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
  padding: .75rem; position: relative;
}
.scatter-box canvas { width: 100%; height: auto; display: block; cursor: crosshair; }
.scatter-controls {
  display: flex; flex-wrap: wrap; gap: .6rem; align-items: center; margin: .6rem 0;
}
.scatter-controls label { font-size: .85rem; color: var(--muted); display: flex; align-items: center; gap: .35rem; }
.scatter-controls select, .scatter-controls input[type="search"],
.toolbar input, .toolbar select, .toolbar button {
  background: var(--bg2); color: var(--text); border: 1px solid var(--line);
  border-radius: 8px; padding: .4rem .65rem; font: inherit; font-size: .88rem;
}
.r-badge {
  display: inline-flex; align-items: center; gap: .4rem;
  background: #1a2e24; border: 1px solid #5ee1a444; color: var(--accent);
  padding: .35rem .75rem; border-radius: 999px; font-weight: 700; font-size: .9rem;
  font-variant-numeric: tabular-nums;
}
.tooltip {
  position: fixed; z-index: 50; pointer-events: none;
  background: #0e1628ee; border: 1px solid var(--line); border-radius: 10px;
  padding: .55rem .75rem; font-size: .8rem; max-width: 280px;
  box-shadow: 0 8px 24px #0008; display: none; line-height: 1.4;
}
.tooltip.show { display: block; }
.tooltip .t { font-weight: 700; margin-bottom: .2rem; }
table.tbl {
  width: 100%; border-collapse: collapse; font-size: .85rem;
  background: var(--card); border-radius: var(--radius); overflow: hidden;
  border: 1px solid var(--line);
}
table.tbl th, table.tbl td {
  text-align: left; padding: .45rem .55rem; border-bottom: 1px solid var(--line);
  font-variant-numeric: tabular-nums;
}
table.tbl th { color: var(--muted); font-weight: 600; font-size: .75rem; text-transform: uppercase; letter-spacing: .03em; background: var(--bg2); }
table.tbl tr:hover td { background: #ffffff08; }
table.tbl tr.sel td { background: #5ee1a418; }
.toolbar {
  display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; margin: .8rem 0;
}
.toolbar input[type="search"] { flex: 1; min-width: 160px; }
.btn {
  background: var(--accent); color: #0b1020; border: none; font-weight: 700;
  cursor: pointer; border-radius: 8px; padding: .45rem .8rem; font-size: .85rem;
}
.btn.ghost {
  background: transparent; color: var(--accent2); border: 1px solid var(--line);
}
.btn:disabled { opacity: .45; cursor: wait; }
.tabs { display: flex; gap: .4rem; flex-wrap: wrap; margin: .6rem 0; }
.tab {
  background: var(--bg2); border: 1px solid var(--line); color: var(--muted);
  border-radius: 999px; padding: .35rem .8rem; font-size: .82rem; cursor: pointer;
}
.tab.active { background: var(--accent); color: #0b1020; border-color: transparent; font-weight: 700; }
.scroll-table { max-height: 380px; overflow: auto; border-radius: var(--radius); border: 1px solid var(--line); }
.scroll-table table.tbl { border: none; border-radius: 0; }
.pill-yes { color: var(--hot); font-weight: 700; }
.pill-no { color: var(--muted); }
footer {
  margin-top: 3rem; padding-top: 1.2rem; border-top: 1px solid var(--line);
  color: var(--muted); font-size: .82rem;
}
.step-explain {
  display: grid; gap: .6rem; margin: 1rem 0;
}
.step-explain .s {
  display: flex; gap: .75rem; align-items: flex-start;
  background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: .75rem 1rem;
}
.step-explain .s .n {
  flex-shrink: 0; width: 1.6rem; height: 1.6rem; border-radius: 50%;
  background: var(--accent2); color: #0b1020; font-weight: 800; font-size: .85rem;
  display: flex; align-items: center; justify-content: center;
}
.two-col-nums {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: .6rem; margin: 1rem 0;
}
.legend-row .bio::before { background: #5ee1a4; }
.legend-row .nao::before { background: #f0a05a; }
.bio-stack { margin: .6rem 0 1rem; }
.bio-compare {
  display: grid; gap: .75rem; grid-template-columns: 1fr;
  margin: 1rem 0;
}
@media (min-width: 700px) {
  .bio-compare { grid-template-columns: 1fr 1fr 1fr; }
}
.bio-compare .stat .v.bio { color: #5ee1a4; }
.bio-compare .stat .v.nao { color: #f0a05a; }
.bio-compare .stat .v.neutral { color: var(--accent2); }
"""

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="description" content="Aula visual: concentração no fim do dia, biometria na habilitação (logs de urna) e discrepância ideológica BA+CE — 1º turno 2026." />
<title>Concentração + biometria — aula 2026</title>
<style>/*__CSS__*/</style>
</head>
<body>
<main>
  <span class="tag">1º turno 2026 · TSE · aula didática</span>
  <h1>Concentração + biometria — aula 2026</h1>
  <p class="lead">Aula visual com dados oficiais: cauda de votos depois das 16h/17h no <em>log</em> da urna, o que o log revela sobre <strong>habilitação biométrica vs manual</strong>, e discrepância ideológica BA+CE.</p>

  <div class="note">
    <strong>Como ler.</strong> (1) Método com duas urnas reais. (2) Amostra (~99 seções com log).
    (3) Biometria como variável metodológica no log — não obrigatória; fallback após 4 tentativas.
    (4) Discrepância ideológica BA+CE (só boletim — sem timestamps).
    Nada aqui prova fraude.
  </div>

  <!-- ========== 1. AULINHA ========== -->
  <h2><span class="num">1</span>Aulinha visual — o que é concentração no fim do dia</h2>

  <div class="step-explain">
    <div class="s"><span class="n">1</span><div>Cada voto no <strong>log da urna</strong> tem um horário de relógio (ex.: 14:32:11).</div></div>
    <div class="s"><span class="n">2</span><div>Contamos quantos votos caem em cada hora do dia (8h, 9h, …, 19h).</div></div>
    <div class="s"><span class="n">3</span><div>Se a <strong>direita do gráfico</strong> (depois das 16h/17h) fica gorda, há concentração no fim do dia.</div></div>
  </div>

  <div class="def-box">
    Métrica principal<br>
    <div class="formula">concentração₁₆ = votos com horário ≥ 16:00 &nbsp;/&nbsp; total de votos no log</div>
    Secundária: <code>concentração₁₇</code> (mesmo, com ≥ 17:00). Valores entre 0 e 1 (ou em %).
  </div>

  <p class="muted" style="margin-bottom:.5rem">Duas seções <strong>reais</strong> da amostra — mesma escala de barras. Compare a “barriga” à direita.</p>
  <div class="legend-row">
    <span class="norm">antes das 16h</span>
    <span class="late">≥ 16h (cauda)</span>
  </div>

  <div class="grid2" id="pair-charts">
    <!-- filled by JS -->
  </div>

  <!-- ========== 2. MAPA DA AMOSTRA ========== -->
  <h2><span class="num">2</span>Da urna para o mapa da amostra</h2>
  <p class="muted">Nas <strong id="n-logs">~99</strong> seções com log (amostra deliberada: interior BA/CE + contraste), a distribuição de <code>concentração₁₆</code>:</p>

  <div class="stats-row" id="dist-stats"></div>

  <p style="margin:.4rem 0 .3rem"><strong>Top seções mais “tardias”</strong> (clique para destacar no scatter):</p>
  <div class="chips" id="top-chips"></div>

  <div class="scatter-controls">
    <label>Eixo Y:
      <select id="y-metric">
        <option value="lula">Lula (13) — share</option>
        <option value="flavio">Flávio (22, PL / campo Bolsonaro) — share</option>
      </select>
    </label>
    <label>Eixo X:
      <select id="x-metric">
        <option value="c16">concentração₁₆</option>
        <option value="c17">concentração₁₇</option>
      </select>
    </label>
    <span class="r-badge" id="r-badge">r = —</span>
  </div>

  <div class="scatter-box">
    <canvas id="scatter" width="900" height="480"></canvas>
  </div>
  <p class="muted" style="font-size:.85rem;margin:.4rem 0 0">Passe o mouse nos pontos. Cada ponto = uma seção com log. Correlação de Pearson recalculada na montagem da página.</p>

  <div class="caveat" id="caveat-sample">
    <strong>Caveat honesto.</strong> Amostra deliberada (~100 seções), <em>não</em> o Brasil.
    Correlação moderada (r ≈ 0,3) <strong>≠ fraude</strong>.
    Fila às 17h no interior explica cauda longa — quem está na fila tem direito de votar.
  </div>

  <!-- ========== 3. BIOMETRIA ========== -->
  <h2><span class="num">3</span>Biometria na habilitação (o que o log mostra)</h2>
  <p class="muted">No <code>logd.dat</code> oficial, cada sessão de eleitor termina em <code>Eleitor foi habilitado</code>.
  O modo aparece como <code>Tipo de habilitação do eleitor [biométrica]</code> — ou, se a digital falhar (até 4 tentativas),
  cai para habilitação manual / ano de nascimento. O log <strong>não</strong> identifica o eleitor nem a escolha de voto.</p>

  <div class="step-explain">
    <div class="s"><span class="n">1</span><div>Sucesso bio: linha <code>Tipo de habilitação… [biométrica]</code> → classificado como <strong>bio</strong>.</div></div>
    <div class="s"><span class="n">2</span><div>Fallback: <code>Solicitação de dado pessoal… habilitação manual</code> e/ou <code>Ano de nascimento digitado…</code> → <strong>não-bio</strong>.</div></div>
    <div class="s"><span class="n">3</span><div>Sem tipo biométrica após tentativas → também <strong>não-bio</strong>. Variável metodológica, não prova de fraude.</div></div>
  </div>

  <div class="stats-row" id="bio-stats"></div>

  <div class="note" id="bio-enrichment-note"></div>

  <p style="margin:1rem 0 .4rem"><strong id="bio-extreme-title">Exemplo extremo (concentração alta)</strong> — barras empilhadas bio vs não-bio por hora:</p>
  <div class="legend-row">
    <span class="bio">biométrica</span>
    <span class="nao">não-bio (manual/nascimento)</span>
  </div>
  <div class="card hot bio-stack" id="bio-extreme-card"></div>

  <div class="bio-compare" id="bio-compare"></div>

  <div class="caveat">
    <strong>Leitura honesta.</strong> Na amostra, a fração não-bio entre votos tardios é praticamente a mesma que de manhã
    (enriquecimento ≈ 1). Correlação seção-a-seção entre <code>share_nao_bio</code> e <code>concentração₁₆</code> é fraca/nula.
    Cauda longa no fim do dia <em>não</em> aparece enriquecida em habilitação manual nesta amostra.
  </div>

  <!-- ========== 4. DISCREPÂNCIA ========== -->
  <h2><span class="num">4</span>Discrepância ideológica (BA + CE completo)</h2>
  <p class="muted">Aqui usamos o <strong>boletim de urna</strong> (votos, sem horário) de <strong>todas</strong> as seções de Bahia e Ceará com ≥30 votos válidos em presidente e dep. federal.</p>
  <p>Pergunta: dá para ter <strong>PL alto no deputado federal</strong> e <strong>Lula alto no presidente</strong> na mesma seção? Sim — chama-se voto dividido (ticket-splitting).</p>

  <div class="two-col-nums" id="disc-stats"></div>

  <div class="note" id="disc-lead"></div>

  <p><strong>Top 10</strong> — maior PL<sub>dep</sub> − Flávio<sub>pres</sub> (direita local × Lula presidente):</p>
  <div class="scroll-table" style="max-height:320px">
    <table class="tbl" id="top-disc-table">
      <thead>
        <tr><th>#</th><th>UF</th><th>Município</th><th>Seção</th><th>Lula</th><th>Flávio</th><th>PL dep</th><th>PL−Flávio</th></tr>
      </thead>
      <tbody></tbody>
    </table>
  </div>
  <p class="muted" style="font-size:.85rem;margin-top:.5rem">
    Flávio = candidato <strong>22</strong> (PL) a presidente — campo Bolsonaro.
    Lula = <strong>13</strong>. PL dep. = votos no partido 22 (nominal+legenda) no cargo de deputado federal.
  </p>

  <!-- ========== 5. EXPLORADOR ========== -->
  <h2><span class="num">5</span>Explorador interativo</h2>
  <div class="tabs">
    <button class="tab active" data-tab="logs">Amostra com logs (n≈99)</button>
    <button class="tab" data-tab="bace">BA+CE discrepância (n=59&nbsp;224)</button>
  </div>

  <div id="panel-logs">
    <div class="toolbar">
      <input type="search" id="search-logs" placeholder="Buscar município…" />
      <select id="uf-logs">
        <option value="">Todas as UF</option>
      </select>
      <select id="sort-logs">
        <option value="c16_desc">concentração₁₆ ↓</option>
        <option value="c16_asc">concentração₁₆ ↑</option>
        <option value="c17_desc">concentração₁₇ ↓</option>
        <option value="nao_bio_desc">% não-bio ↓</option>
        <option value="nao16_desc">% não-bio ≥16h ↓</option>
        <option value="lula_desc">Lula ↓</option>
        <option value="flavio_desc">Flávio ↓</option>
      </select>
      <a class="btn ghost" id="dl-logs" href="data/secoes_logs.json" download>Baixar JSON logs</a>
    </div>
    <div class="scroll-table">
      <table class="tbl" id="table-logs">
        <thead>
          <tr>
            <th>UF</th><th>Município</th><th>Z/S</th><th>n votos</th>
            <th>conc.₁₆</th><th>conc.₁₇</th>
            <th>% bio</th><th>% não-bio</th><th>% não-bio≥16h</th>
            <th>Lula</th><th>Flávio</th><th>1º–último</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div id="panel-bace" hidden>
    <div class="toolbar">
      <input type="search" id="search-bace" placeholder="Buscar município…" />
      <select id="uf-bace">
        <option value="">BA + CE</option>
        <option value="BA">BA</option>
        <option value="CE">CE</option>
      </select>
      <select id="sort-bace">
        <option value="g_desc">PL−Flávio ↓</option>
        <option value="g_asc">PL−Flávio ↑</option>
        <option value="l_desc">Lula ↓</option>
        <option value="pl_desc">PL dep ↓</option>
      </select>
      <label style="font-size:.85rem;color:var(--muted)">
        <input type="checkbox" id="only-flag" /> só flag PL∧Lula
      </label>
      <button class="btn ghost" id="dl-bace" type="button">Baixar JSON BA+CE</button>
    </div>
    <p class="muted" style="font-size:.82rem" id="bace-status">Carregando 59&nbsp;224 seções…</p>
    <div class="scroll-table">
      <table class="tbl" id="table-bace">
        <thead>
          <tr>
            <th>UF</th><th>Município</th><th>Z/S</th><th>Lula</th><th>Flávio</th>
            <th>PL dep</th><th>PT dep</th><th>PL−Flávio</th><th>flag</th>
          </tr>
        </thead>
        <tbody></tbody>
      </table>
    </div>
    <p class="muted" style="font-size:.8rem">Mostrando até 500 linhas filtradas (arquivo completo no download).</p>
  </div>

  <footer>
    Fonte: logs e boletins de urna oficiais (TSE / dadosabertos.tse.jus.br), 1º turno 2026.
    Concentração = timestamps do log; biometria = modo de habilitação no log; discrepância = presidente × dep. federal.
    Página didática — não é laudo pericial.
  </footer>
</main>

<div class="tooltip" id="tip"></div>

<script>window.EMBED = __EMBED__;</script>
<script src="app.js"></script>
</body>
</html>
"""

APP_JS = r"""
(function () {
  "use strict";
  const EMBED = window.EMBED;
  const meta = EMBED.meta;
  const logs = EMBED.logs;
  const tip = document.getElementById("tip");

  const pct = (x, d = 1) => (x == null ? "—" : (100 * x).toFixed(d) + "%");
  const pctN = (x, d = 1) => (x == null ? null : +(100 * x).toFixed(d));

  document.getElementById("n-logs").textContent = String(meta.n_logs);

  /* ---- pair bar charts ---- */
  function barSVG(hours, titleClass) {
    const order = [];
    for (let h = 8; h <= 19; h++) order.push(String(h).padStart(2, "0"));
    const vals = order.map((h) => hours[h] || 0);
    const maxV = Math.max(40, ...vals);
    const W = 420, H = 200, padL = 28, padR = 8, padT = 12, padB = 28;
    const iw = W - padL - padR, ih = H - padT - padB;
    const bw = iw / order.length;
    let bars = "";
    order.forEach((h, i) => {
      const v = vals[i];
      const bh = (v / maxV) * ih;
      const x = padL + i * bw + 2;
      const y = padT + ih - bh;
      const late = parseInt(h, 10) >= 16;
      const fill = late ? "#ff8a6a" : "#5b8def";
      bars += `<rect x="${x}" y="${y}" width="${bw - 4}" height="${Math.max(bh, 0)}" rx="3" fill="${fill}" opacity="0.92"/>`;
      if (v > 0) {
        bars += `<text x="${x + (bw - 4) / 2}" y="${y - 3}" text-anchor="middle" fill="#c5d0e8" font-size="9" font-family="ui-monospace,monospace">${v}</text>`;
      }
      bars += `<text x="${x + (bw - 4) / 2}" y="${H - 8}" text-anchor="middle" fill="#9aa8c7" font-size="10">${parseInt(h, 10)}h</text>`;
    });
    // 16h marker
    const x16 = padL + (16 - 8) * bw;
    bars += `<line x1="${x16}" y1="${padT}" x2="${x16}" y2="${padT + ih}" stroke="#f5c542" stroke-dasharray="3 3" stroke-width="1.2" opacity="0.7"/>`;
    bars += `<text x="${x16 + 4}" y="${padT + 10}" fill="#f5c542" font-size="9">≥16h</text>`;
    return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Barras por hora">${bars}</svg>`;
  }

  function cardExample(ex, kind) {
    const hot = kind === "extrema";
    const cls = hot ? "hot" : "cool";
    const label = hot ? "Concentração alta (cauda gorda)" : "Perfil plano (sem cauda)";
    const v16cls = hot ? "hot" : "cool";
    return `<div class="card ${cls}">
      <div class="label">${label}</div>
      <div class="place">${ex.nm_mun} / ${ex.uf}</div>
      <div class="meta-line">zona ${ex.zona} · seção ${ex.secao} · ${ex.n_votos_log} votos no log · ${ex.first_ts} → ${ex.last_ts}</div>
      <div class="chart-wrap">${barSVG(ex.hours)}</div>
      <div class="metric-big">
        <div class="m"><div class="v ${v16cls}">${pct(ex.concentracao_16, 1)}</div><div class="k">concentração₁₆</div></div>
        <div class="m"><div class="v ${v16cls}">${pct(ex.concentracao_17, 1)}</div><div class="k">concentração₁₇</div></div>
        <div class="m"><div class="v">${pct(ex.lula_share, 1)}</div><div class="k">Lula (13)</div></div>
        <div class="m"><div class="v">${pct(ex.flavio_share, 1)}</div><div class="k">Flávio (22)</div></div>
      </div>
    </div>`;
  }

  document.getElementById("pair-charts").innerHTML =
    cardExample(meta.exemplos.extrema, "extrema") +
    cardExample(meta.exemplos.plana, "plana");

  /* ---- dist stats ---- */
  const d16 = meta.dist_16;
  document.getElementById("dist-stats").innerHTML = [
    ["n seções", d16.n, ""],
    ["média c₁₆", pct(d16.mean, 1), ""],
    ["mediana c₁₆", pct(d16.median, 1), ""],
    ["máx c₁₆", pct(d16.max, 1), ""],
    ["média c₁₇", pct(meta.dist_17.mean, 1), ""],
    ["máx c₁₇", pct(meta.dist_17.max, 1), ""],
  ].map(([k, v]) => `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");

  /* ---- top chips ---- */
  const chips = document.getElementById("top-chips");
  meta.top_late.slice(0, 10).forEach((r, i) => {
    const el = document.createElement("span");
    el.className = "chip";
    el.innerHTML = `${i + 1}. ${r.nm_mun}/${r.uf} <b>${pct(r.concentracao_16, 1)}</b>`;
    el.title = `z${r.zona} s${r.secao} · c17=${pct(r.concentracao_17,1)} · Lula=${pct(r.lula_share,1)} · último ${r.last_ts}`;
    el.addEventListener("click", () => {
      highlightKey = `${r.uf}-${r.zona}-${r.secao}`;
      drawScatter();
      // scroll table
      const tr = document.querySelector(`#table-logs tr[data-key="${highlightKey}"]`);
      if (tr) { tr.classList.add("sel"); tr.scrollIntoView({ block: "nearest", behavior: "smooth" }); }
    });
    chips.appendChild(el);
  });

  /* ---- Pearson (client recompute for display consistency) ---- */
  function pearson(xs, ys) {
    const n = xs.length;
    if (n < 3) return null;
    let mx = 0, my = 0;
    for (let i = 0; i < n; i++) { mx += xs[i]; my += ys[i]; }
    mx /= n; my /= n;
    let num = 0, dx = 0, dy = 0;
    for (let i = 0; i < n; i++) {
      const a = xs[i] - mx, b = ys[i] - my;
      num += a * b; dx += a * a; dy += b * b;
    }
    if (dx === 0 || dy === 0) return null;
    return num / Math.sqrt(dx * dy);
  }

  let highlightKey = null;

  function currentXY() {
    const yKey = document.getElementById("y-metric").value;
    const xKey = document.getElementById("x-metric").value;
    const xField = xKey === "c17" ? "concentracao_17" : "concentracao_16";
    const yField = yKey === "flavio" ? "flavio_share" : "lula_share";
    const pts = [];
    for (const r of logs) {
      if (r[xField] == null || r[yField] == null) continue;
      pts.push({
        x: r[xField], y: r[yField], r,
        key: `${r.uf}-${r.zona}-${r.secao}`,
      });
    }
    return { pts, xField, yField, yKey, xKey };
  }

  function updateR() {
    const { pts, yKey, xKey } = currentXY();
    const r = pearson(pts.map((p) => p.x), pts.map((p) => p.y));
    const labelY = yKey === "flavio" ? "Flávio" : "Lula";
    const labelX = xKey === "c17" ? "c₁₇" : "c₁₆";
    const el = document.getElementById("r-badge");
    el.textContent = r == null ? `r(${labelY}, ${labelX}) = —` : `r(${labelY}, ${labelX}) = ${r.toFixed(2)}  (n=${pts.length})`;
    // also show server-side for default
    if (yKey === "lula" && xKey === "c16" && meta.corr.r_lula_concentracao_16 != null) {
      el.title = `recomputado no build: ${meta.corr.r_lula_concentracao_16}`;
    }
  }

  function drawScatter() {
    const canvas = document.getElementById("scatter");
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 900;
    const cssH = Math.round(cssW * 0.52);
    canvas.width = cssW * dpr;
    canvas.height = cssH * dpr;
    canvas.style.height = cssH + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const { pts, yKey } = currentXY();
    updateR();

    const pad = { l: 48, r: 16, t: 16, b: 40 };
    const W = cssW, H = cssH;
    const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;

    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#162038";
    ctx.fillRect(0, 0, W, H);

    // axes ranges
    let xMax = 0.45;
    for (const p of pts) xMax = Math.max(xMax, p.x * 1.05);
    xMax = Math.ceil(xMax * 20) / 20;
    const yMin = 0, yMax = 1;

    const sx = (x) => pad.l + (x / xMax) * iw;
    const sy = (y) => pad.t + ih - ((y - yMin) / (yMax - yMin)) * ih;

    // grid
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const y = yMin + (i / 5) * (yMax - yMin);
      ctx.beginPath(); ctx.moveTo(pad.l, sy(y)); ctx.lineTo(pad.l + iw, sy(y)); ctx.stroke();
      ctx.fillStyle = "#9aa8c7"; ctx.font = "11px system-ui"; ctx.textAlign = "right";
      ctx.fillText(Math.round(y * 100) + "%", pad.l - 6, sy(y) + 4);
    }
    for (let i = 0; i <= 4; i++) {
      const x = (i / 4) * xMax;
      ctx.beginPath(); ctx.moveTo(sx(x), pad.t); ctx.lineTo(sx(x), pad.t + ih); ctx.stroke();
      ctx.fillStyle = "#9aa8c7"; ctx.font = "11px system-ui"; ctx.textAlign = "center";
      ctx.fillText(Math.round(x * 100) + "%", sx(x), pad.t + ih + 18);
    }

    // regression line (simple)
    if (pts.length >= 3) {
      const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
      const n = xs.length;
      let mx = 0, my = 0;
      for (let i = 0; i < n; i++) { mx += xs[i]; my += ys[i]; }
      mx /= n; my /= n;
      let num = 0, den = 0;
      for (let i = 0; i < n; i++) { num += (xs[i] - mx) * (ys[i] - my); den += (xs[i] - mx) ** 2; }
      if (den > 0) {
        const b = num / den, a = my - b * mx;
        ctx.strokeStyle = "#5ee1a466"; ctx.lineWidth = 2; ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(sx(0), sy(a));
        ctx.lineTo(sx(xMax), sy(a + b * xMax));
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }

    // points
    for (const p of pts) {
      const hi = p.key === highlightKey;
      ctx.beginPath();
      ctx.arc(sx(p.x), sy(p.y), hi ? 7 : 4.5, 0, Math.PI * 2);
      ctx.fillStyle = yKey === "flavio" ? "#f0a05a" : (hi ? "#5ee1a4" : "#7eb6ff");
      ctx.globalAlpha = hi ? 1 : 0.85;
      ctx.fill();
      if (hi) {
        ctx.strokeStyle = "#fff"; ctx.lineWidth = 2; ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // axis labels
    ctx.fillStyle = "#9aa8c7"; ctx.font = "12px system-ui"; ctx.textAlign = "center";
    ctx.fillText(document.getElementById("x-metric").selectedOptions[0].text, pad.l + iw / 2, H - 6);
    ctx.save();
    ctx.translate(14, pad.t + ih / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(document.getElementById("y-metric").selectedOptions[0].text, 0, 0);
    ctx.restore();

    // hit testing store
    canvas._hit = { pts, sx, sy, xMax };
  }

  document.getElementById("y-metric").addEventListener("change", drawScatter);
  document.getElementById("x-metric").addEventListener("change", drawScatter);
  window.addEventListener("resize", drawScatter);

  const canvas = document.getElementById("scatter");
  canvas.addEventListener("mousemove", (ev) => {
    const hit = canvas._hit;
    if (!hit) return;
    const rect = canvas.getBoundingClientRect();
    const mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
    let best = null, bestD = 12;
    for (const p of hit.pts) {
      const dx = hit.sx(p.x) - mx, dy = hit.sy(p.y) - my;
      const d = Math.hypot(dx, dy);
      if (d < bestD) { bestD = d; best = p; }
    }
    if (!best) { tip.classList.remove("show"); return; }
    const r = best.r;
    tip.innerHTML = `<div class="t">${r.nm_mun}/${r.uf} · z${r.zona} s${r.secao}</div>
      concentração₁₆: <b>${pct(r.concentracao_16,1)}</b> ·₁₇: <b>${pct(r.concentracao_17,1)}</b><br>
      bio: ${pct(r.share_bio,1)} · não-bio: ${pct(r.share_nao_bio,1)} · ≥16h não-bio: ${pct(r.share_nao_bio_after16,1)}<br>
      Lula: ${pct(r.lula_share,1)} · Flávio: ${pct(r.flavio_share,1)}<br>
      ${r.n_votos_log} votos · ${r.first_ts} → ${r.last_ts}<br>
      estrato: ${r.estrato || "—"}`;
    tip.classList.add("show");
    tip.style.left = Math.min(ev.clientX + 14, window.innerWidth - 290) + "px";
    tip.style.top = Math.min(ev.clientY + 14, window.innerHeight - 120) + "px";
  });
  canvas.addEventListener("mouseleave", () => tip.classList.remove("show"));

  /* ---- biometria section ---- */
  const B = meta.biometria;
  if (B && B.overall) {
    const ov = B.overall;
    document.getElementById("bio-stats").innerHTML = [
      ["seções com bio", ov.n_sections, ""],
      ["habilitações", ov.n_hab.toLocaleString("pt-BR"), ""],
      ["% bio (pool)", pct(ov.share_bio, 1), "bio"],
      ["% não-bio (pool)", pct(ov.share_nao_bio, 1), "nao"],
      ["% não-bio <16h", pct(ov.early_before16.share_nao_bio, 1), ""],
      ["% não-bio ≥16h", pct(ov.after16.share_nao_bio, 1), ""],
      ["% não-bio ≥17h", pct(ov.after17.share_nao_bio, 1), ""],
      ["enriquecimento", (ov.late_vs_early_enrichment_nao_bio != null ? ov.late_vs_early_enrichment_nao_bio.toFixed(2) : "—"), ""],
    ].map(([k, v, cls]) => `<div class="stat"><div class="v ${cls || ""}">${v}</div><div class="k">${k}</div></div>`).join("");

    const enr = ov.late_vs_early_enrichment_nao_bio;
    const corrC = B.correlation || {};
    const rNaoC16 = corrC.share_nao_bio_vs_concentracao_16;
    const rNaoLula = corrC.share_nao_bio_vs_lula_share;
    let enrTxt = "sem enriquecimento";
    if (enr != null && enr > 1.15) enrTxt = "leve enriquecimento tardio";
    else if (enr != null && enr < 0.85) enrTxt = "tarde até menos não-bio";
    document.getElementById("bio-enrichment-note").innerHTML =
      `<strong>Amostra (pool).</strong> ${pct(ov.share_bio, 1)} das habilitações foram biométricas;
       ${pct(ov.share_nao_bio, 1)} foram não-bio (manual/nascimento).
       Entre votos ≥16h, não-bio = ${pct(ov.after16.share_nao_bio, 1)} vs ${pct(ov.early_before16.share_nao_bio, 1)} antes das 16h
       (razão ${enr != null ? enr.toFixed(2) : "—"} → <em>${enrTxt}</em>).
       Correlação seção-a-seção: r(share_nao_bio, c₁₆) = <b>${rNaoC16 != null ? rNaoC16.toFixed(2) : "—"}</b>;
       r(share_nao_bio, Lula) = <b>${rNaoLula != null ? rNaoLula.toFixed(2) : "—"}</b>
       — fraca/nula nesta amostra.`;

    function stackedBioSVG(hoursBio, hoursNao) {
      const order = [];
      for (let h = 8; h <= 19; h++) order.push(String(h).padStart(2, "0"));
      const totals = order.map((h) => (hoursBio[h] || 0) + (hoursNao[h] || 0));
      const maxV = Math.max(40, ...totals);
      const W = 640, H = 220, padL = 28, padR = 8, padT = 14, padB = 28;
      const iw = W - padL - padR, ih = H - padT - padB;
      const bw = iw / order.length;
      let bars = "";
      order.forEach((h, i) => {
        const bio = hoursBio[h] || 0;
        const nao = hoursNao[h] || 0;
        const tot = bio + nao;
        const x = padL + i * bw + 2;
        const bhTot = (tot / maxV) * ih;
        const bhNao = tot ? (nao / tot) * bhTot : 0;
        const bhBio = bhTot - bhNao;
        const yBase = padT + ih;
        // bio (bottom)
        bars += `<rect x="${x}" y="${yBase - bhBio}" width="${bw - 4}" height="${Math.max(bhBio, 0)}" rx="2" fill="#5ee1a4" opacity="0.92"/>`;
        // nao (top)
        bars += `<rect x="${x}" y="${yBase - bhTot}" width="${bw - 4}" height="${Math.max(bhNao, 0)}" rx="2" fill="#f0a05a" opacity="0.95"/>`;
        if (tot > 0) {
          bars += `<text x="${x + (bw - 4) / 2}" y="${yBase - bhTot - 3}" text-anchor="middle" fill="#c5d0e8" font-size="9" font-family="ui-monospace,monospace">${tot}</text>`;
        }
        bars += `<text x="${x + (bw - 4) / 2}" y="${H - 8}" text-anchor="middle" fill="#9aa8c7" font-size="10">${parseInt(h, 10)}h</text>`;
      });
      const x16 = padL + (16 - 8) * bw;
      bars += `<line x1="${x16}" y1="${padT}" x2="${x16}" y2="${padT + ih}" stroke="#f5c542" stroke-dasharray="3 3" stroke-width="1.2" opacity="0.7"/>`;
      bars += `<text x="${x16 + 4}" y="${padT + 10}" fill="#f5c542" font-size="9">≥16h</text>`;
      return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Barras empilhadas bio vs não-bio">${bars}</svg>`;
    }

    const ex = B.extreme;
    document.getElementById("bio-extreme-title").textContent =
      `${ex.nm_mun}/${ex.uf} (z${ex.zona} s${ex.secao}) — concentração₁₆ = ${pct(ex.concentracao_16, 1)}`;
    const late16 = ex.after16 || {};
    const early = ex.early_before16 || {};
    document.getElementById("bio-extreme-card").innerHTML = `
      <div class="label">Biometria vs não-bio por hora do voto</div>
      <div class="place">${ex.nm_mun} / ${ex.uf}</div>
      <div class="meta-line">${ex.n_hab} habilitações · ${pct(ex.share_bio,1)} bio · ${pct(ex.share_nao_bio,1)} não-bio
        · ≥16h: ${late16.n_bio || 0} bio / ${late16.n_nao_bio || 0} não-bio (${pct(late16.share_nao_bio,1)} não-bio)</div>
      <div class="chart-wrap">${stackedBioSVG(ex.hours_bio || {}, ex.hours_nao_bio || {})}</div>
      <div class="metric-big">
        <div class="m"><div class="v" style="color:#5ee1a4">${pct(ex.share_bio,1)}</div><div class="k">bio (seção)</div></div>
        <div class="m"><div class="v" style="color:#f0a05a">${pct(ex.share_nao_bio,1)}</div><div class="k">não-bio</div></div>
        <div class="m"><div class="v hot">${pct(ex.concentracao_16,1)}</div><div class="k">concentração₁₆</div></div>
        <div class="m"><div class="v">${pct(late16.share_nao_bio,1)}</div><div class="k">não-bio ≥16h</div></div>
      </div>`;

    document.getElementById("bio-compare").innerHTML = [
      ["Antes das 16h (pool)", pct(ov.early_before16.share_nao_bio, 1), `${ov.early_before16.n_nao_bio.toLocaleString("pt-BR")} / ${ov.early_before16.n.toLocaleString("pt-BR")}`, "nao"],
      ["≥ 16h (pool)", pct(ov.after16.share_nao_bio, 1), `${ov.after16.n_nao_bio.toLocaleString("pt-BR")} / ${ov.after16.n.toLocaleString("pt-BR")}`, "nao"],
      ["≥ 17h (pool)", pct(ov.after17.share_nao_bio, 1), `${ov.after17.n_nao_bio.toLocaleString("pt-BR")} / ${ov.after17.n.toLocaleString("pt-BR")}`, "nao"],
    ].map(([title, big, sub, cls]) =>
      `<div class="stat"><div class="k">${title}</div><div class="v ${cls}" style="font-size:1.5rem">${big}</div>
       <div class="k" style="margin-top:.25rem">não-bio · ${sub}</div></div>`
    ).join("");
  }

  /* ---- discrepancy section ---- */
  const D = meta.discrepancia;
  document.getElementById("disc-stats").innerHTML = [
    ["seções BA+CE", D.n_sections.toLocaleString("pt-BR")],
    ["flag PL∧Lula", D.n_flag_PL_Lula.toLocaleString("pt-BR") + ` (${D.pct_flag_PL_Lula}%)`],
    ["mediana PL−Flávio", (D.PL_minus_Flavio.median * 100).toFixed(1) + " pp"],
    ["máx PL−Flávio", "+" + (D.PL_minus_Flavio.max * 100).toFixed(1) + " pp"],
    ["PL > Flávio", D.n_PL_gt_Flavio.toLocaleString("pt-BR")],
    ["flag PT∧Flávio", D.n_flag_PT_Flavio.toLocaleString("pt-BR")],
  ].map(([k, v]) => `<div class="stat"><div class="v" style="font-size:1.15rem">${v}</div><div class="k">${k}</div></div>`).join("");

  const aiu = D.aiuaba_focus || {};
  const aiuPct = D.aiuaba_percentile;
  document.getElementById("disc-lead").innerHTML =
    `<strong>Aiuaba/CE</strong> ilustra bem o fenômeno: Lula alto + PL dep. alto, com Flávio baixo.
     Flag binário (PL≥15% ∧ Lula≥55%) = <b>${D.pct_flag_PL_Lula}%</b> de ${D.n_sections.toLocaleString("pt-BR")} seções — frequente no CE, não é outlier.
     Na <em>magnitude</em> PL−Flávio, Aiuaba fica na cauda (pctl ${(aiuPct != null ? Number(aiuPct).toFixed(2) : "≈99,5")});
     Quijingue/BA e Boa Viagem/CE são ainda mais extremos. Leitura: ticket-splitting / máquina local PL — <strong>não prova fraude</strong>.`;

  const tb = document.querySelector("#top-disc-table tbody");
  (D.top10 || []).forEach((row, i) => {
    const tr = document.createElement("tr");
    const l = row.lula_share ?? row.lula;
    const f = row.flavio_share ?? row.flavio;
    const pl = row.pl_share_dep ?? row.pl;
    const g = row.score_PL_minus_Flavio ?? row.gap ?? row.PL_minus_Flavio;
    tr.innerHTML = `<td>${i + 1}</td><td>${row.uf}</td><td>${row.nm_mun || row.m}</td>
      <td>z${row.zona ?? row.z} s${row.secao ?? row.s}</td>
      <td>${pct(l,1)}</td><td>${pct(f,1)}</td><td>${pct(pl,1)}</td>
      <td><b>${g >= 0 ? "+" : ""}${(g * 100).toFixed(1)} pp</b></td>`;
    tb.appendChild(tr);
  });

  /* ---- explorer: logs ---- */
  const ufSet = [...new Set(logs.map((r) => r.uf))].sort();
  const ufSel = document.getElementById("uf-logs");
  ufSet.forEach((u) => {
    const o = document.createElement("option");
    o.value = u; o.textContent = u; ufSel.appendChild(o);
  });

  function renderLogsTable() {
    const q = document.getElementById("search-logs").value.trim().toLowerCase();
    const uf = document.getElementById("uf-logs").value;
    const sort = document.getElementById("sort-logs").value;
    let rows = logs.filter((r) => {
      if (uf && r.uf !== uf) return false;
      if (q && !(r.nm_mun || "").toLowerCase().includes(q)) return false;
      return true;
    });
    const sorters = {
      c16_desc: (a, b) => b.concentracao_16 - a.concentracao_16,
      c16_asc: (a, b) => a.concentracao_16 - b.concentracao_16,
      c17_desc: (a, b) => b.concentracao_17 - a.concentracao_17,
      nao_bio_desc: (a, b) => (b.share_nao_bio || 0) - (a.share_nao_bio || 0),
      nao16_desc: (a, b) => (b.share_nao_bio_after16 || 0) - (a.share_nao_bio_after16 || 0),
      lula_desc: (a, b) => (b.lula_share || 0) - (a.lula_share || 0),
      flavio_desc: (a, b) => (b.flavio_share || 0) - (a.flavio_share || 0),
    };
    rows.sort(sorters[sort] || sorters.c16_desc);
    const body = document.querySelector("#table-logs tbody");
    body.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      const key = `${r.uf}-${r.zona}-${r.secao}`;
      tr.dataset.key = key;
      if (key === highlightKey) tr.classList.add("sel");
      tr.innerHTML = `<td>${r.uf}</td><td>${r.nm_mun}</td><td>z${r.zona} s${r.secao}</td>
        <td>${r.n_votos_log}</td><td><b>${pct(r.concentracao_16,1)}</b></td><td>${pct(r.concentracao_17,1)}</td>
        <td>${pct(r.share_bio,1)}</td><td>${pct(r.share_nao_bio,1)}</td><td>${pct(r.share_nao_bio_after16,1)}</td>
        <td>${pct(r.lula_share,1)}</td><td>${pct(r.flavio_share,1)}</td>
        <td>${r.first_ts || "—"} → ${r.last_ts || "—"}</td>`;
      tr.addEventListener("mouseenter", (ev) => {
        tip.innerHTML = `<div class="t">${r.nm_mun}/${r.uf}</div>
          horas (trecho 16–19): ${(r.hours["16"]||0)} / ${(r.hours["17"]||0)} / ${(r.hours["18"]||0)} / ${(r.hours["19"]||0)}<br>
          bio ${pct(r.share_bio,1)} · não-bio ${pct(r.share_nao_bio,1)}
          · ≥16h não-bio ${pct(r.share_nao_bio_after16,1)}<br>
          estrato: ${r.estrato || "—"}`;
        tip.classList.add("show");
        tip.style.left = Math.min(ev.clientX + 14, window.innerWidth - 280) + "px";
        tip.style.top = Math.min(ev.clientY + 14, window.innerHeight - 100) + "px";
      });
      tr.addEventListener("mouseleave", () => tip.classList.remove("show"));
      tr.addEventListener("click", () => {
        highlightKey = key;
        drawScatter();
        renderLogsTable();
      });
      body.appendChild(tr);
    });
  }
  document.getElementById("search-logs").addEventListener("input", renderLogsTable);
  document.getElementById("uf-logs").addEventListener("change", renderLogsTable);
  document.getElementById("sort-logs").addEventListener("change", renderLogsTable);
  renderLogsTable();

  /* ---- tabs + BA/CE ---- */
  let baceData = null;
  let baceLoading = false;

  document.querySelectorAll(".tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const tab = btn.dataset.tab;
      document.getElementById("panel-logs").hidden = tab !== "logs";
      document.getElementById("panel-bace").hidden = tab !== "bace";
      if (tab === "bace") loadBace();
    });
  });

  async function loadBace() {
    if (baceData || baceLoading) {
      if (baceData) renderBace();
      return;
    }
    baceLoading = true;
    const st = document.getElementById("bace-status");
    st.textContent = "Baixando secoes_ba_ce.json (~6 MB)…";
    try {
      const res = await fetch("data/secoes_ba_ce.json");
      if (!res.ok) throw new Error("HTTP " + res.status);
      baceData = await res.json();
      st.textContent = `${baceData.length.toLocaleString("pt-BR")} seções carregadas.`;
      renderBace();
    } catch (e) {
      st.textContent = "Falha ao carregar BA+CE: " + e.message;
    } finally {
      baceLoading = false;
    }
  }

  function renderBace() {
    if (!baceData) return;
    const q = document.getElementById("search-bace").value.trim().toLowerCase();
    const uf = document.getElementById("uf-bace").value;
    const sort = document.getElementById("sort-bace").value;
    const only = document.getElementById("only-flag").checked;
    let rows = baceData.filter((r) => {
      if (uf && r.uf !== uf) return false;
      if (only && !r.fl) return false;
      if (q && !(r.m || "").toLowerCase().includes(q)) return false;
      return true;
    });
    const sorters = {
      g_desc: (a, b) => b.g - a.g,
      g_asc: (a, b) => a.g - b.g,
      l_desc: (a, b) => b.l - a.l,
      pl_desc: (a, b) => b.pl - a.pl,
    };
    rows.sort(sorters[sort] || sorters.g_desc);
    const total = rows.length;
    rows = rows.slice(0, 500);
    document.getElementById("bace-status").textContent =
      `${total.toLocaleString("pt-BR")} seções no filtro · mostrando ${rows.length}.`;
    const body = document.querySelector("#table-bace tbody");
    body.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.uf}</td><td>${r.m}</td><td>z${r.z} s${r.s}</td>
        <td>${pct(r.l,1)}</td><td>${pct(r.f,1)}</td><td>${pct(r.pl,1)}</td><td>${pct(r.pt,1)}</td>
        <td><b>${r.g >= 0 ? "+" : ""}${(r.g * 100).toFixed(1)} pp</b></td>
        <td class="${r.fl ? "pill-yes" : "pill-no"}">${r.fl ? "sim" : "—"}</td>`;
      tr.addEventListener("mouseenter", (ev) => {
        tip.innerHTML = `<div class="t">${r.m}/${r.uf} · z${r.z} s${r.s}</div>
          Lula ${pct(r.l,1)} · Flávio ${pct(r.f,1)}<br>
          PL dep ${pct(r.pl,1)} · PT dep ${pct(r.pt,1)}<br>
          PL−Flávio: <b>${r.g >= 0 ? "+" : ""}${(r.g * 100).toFixed(1)} pp</b>
          ${r.fl ? " · flag PL∧Lula" : ""}`;
        tip.classList.add("show");
        tip.style.left = Math.min(ev.clientX + 14, window.innerWidth - 280) + "px";
        tip.style.top = Math.min(ev.clientY + 14, window.innerHeight - 100) + "px";
      });
      tr.addEventListener("mouseleave", () => tip.classList.remove("show"));
      body.appendChild(tr);
    });
  }
  ["search-bace", "uf-bace", "sort-bace", "only-flag"].forEach((id) => {
    document.getElementById(id).addEventListener("input", renderBace);
    document.getElementById(id).addEventListener("change", renderBace);
  });

  document.getElementById("dl-bace").addEventListener("click", () => {
    const a = document.createElement("a");
    a.href = "data/secoes_ba_ce.json";
    a.download = "secoes_ba_ce.json";
    a.click();
  });

  // init scatter after layout
  requestAnimationFrame(drawScatter);
})();
"""


if __name__ == "__main__":
    main()
