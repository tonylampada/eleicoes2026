#!/usr/bin/env python3
"""Build late-vote-only didactic site (NO ideological discrepancy).

Reads logs_ba_ce/{ba,ce}.jsonl + sample/analise_tarde_BA_CE.json
Writes site-didatico/ (overwrites index/app/styles/data for late-only lesson).
"""
from __future__ import annotations

import json
import math
import statistics as st
import time
import os
from collections import Counter
from pathlib import Path

# Resolve project layout relative to this script (default) or via env var.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
SAMPLE = SAMPLE_DIR
LOGS = ROOT / "logs_ba_ce"
OUT = ROOT / "site-didatico"
DATA = OUT / "data"


def pearson(xs, ys):
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def linreg(xs, ys):
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    varx = sum((x - mx) ** 2 for x in xs)
    if varx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / varx
    intercept = my - slope * mx
    return {"slope": round(slope, 6), "intercept": round(intercept, 6), "n": n}


def load_rows():
    rows = []
    for uf in ("ba", "ce"):
        path = LOGS / f"{uf}.jsonl"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "erro" in r or not r.get("n_votos_log"):
                    continue
                rows.append(r)
    by_key = {r["key"]: r for r in rows}
    return list(by_key.values())


def lean(r, with_hours=True):
    o = {
        "k": r["key"],
        "uf": r["uf"],
        "m": r.get("nm_mun") or "",
        "z": int(r["zona"]),
        "s": int(r["secao"]),
        "n": int(r["n_votos_log"]),
        "c16": r.get("concentracao_16"),
        "c17": r.get("concentracao_17"),
        "l": round(float(r["lula_share"]), 4) if r.get("lula_share") is not None else None,
        "f": round(float(r["flavio_share"]), 4) if r.get("flavio_share") is not None else None,
        "sb": r.get("share_bio"),
        "b16": r.get("bio_after16"),
        "nb16": r.get("nao_bio_after16"),
        "b17": r.get("bio_after17"),
        "nb17": r.get("nao_bio_after17"),
        "ft": r.get("first_ts"),
        "lt": r.get("last_ts"),
        "et": r.get("enc_ts"),
        "nh": r.get("n_hab"),
        "nb": r.get("n_bio"),
        "nn": r.get("n_nao_bio"),
    }
    if with_hours:
        o["h"] = r.get("hours") or {}
    return o


def pick_examples(rows):
    """Extreme late vs flat/typical for didactic hour bars."""
    ranked = sorted(
        [r for r in rows if r.get("concentracao_16") is not None and r["n_votos_log"] >= 80],
        key=lambda r: (r.get("concentracao_17") or 0, r.get("concentracao_16") or 0),
        reverse=True,
    )
    extreme = ranked[0] if ranked else None
    # flat: low c16, decent turnout, prefers last_ts before 17
    flat_cands = [
        r for r in rows
        if r.get("concentracao_16") is not None
        and r["n_votos_log"] >= 120
        and (r.get("concentracao_16") or 0) <= 0.08
        and (r.get("last_ts") or "99") < "17:10:00"
    ]
    flat_cands.sort(key=lambda r: (r.get("concentracao_16") or 0, r.get("concentracao_17") or 0))
    flat = flat_cands[0] if flat_cands else (ranked[-1] if ranked else None)
    return extreme, flat


def build_resumo(rows, analise):
    extreme, flat = pick_examples(rows)
    by_uf = {}
    for uf in ("BA", "CE"):
        sub = [r for r in rows if r["uf"] == uf]
        with_l = [r for r in sub if r.get("concentracao_16") is not None and r.get("lula_share") is not None]
        with_f = [r for r in sub if r.get("concentracao_16") is not None and r.get("flavio_share") is not None]
        c16 = [r["concentracao_16"] for r in sub if r.get("concentracao_16") is not None]
        by_uf[uf] = {
            "n": len(sub),
            "c16_mean": round(st.mean(c16), 4) if c16 else None,
            "c16_median": round(st.median(c16), 4) if c16 else None,
            "corr_lula": pearson([r["concentracao_16"] for r in with_l], [r["lula_share"] for r in with_l]),
            "corr_flavio": pearson([r["concentracao_16"] for r in with_f], [r["flavio_share"] for r in with_f]),
            "reg_lula": linreg([r["concentracao_16"] for r in with_l], [r["lula_share"] for r in with_l]),
            "reg_flavio": linreg([r["concentracao_16"] for r in with_f], [r["flavio_share"] for r in with_f]),
        }

    overall = analise.get("overall") or {}
    bio = overall.get("biometria") or {}

    hours_pool = Counter()
    for r in rows:
        for h, c in (r.get("hours") or {}).items():
            hours_pool[h] += c
    tot = sum(hours_pool.values())

    return {
        "title": "Voto tardio BA+CE — aula 2026",
        "election_day": "04/10/2026",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_secoes": len(rows),
        "n_votos": sum(r["n_votos_log"] for r in rows),
        "definition": {
            "concentracao_16": "votos com horário ≥ 16:00 ÷ total de votos no log (dia 04/10/2026)",
            "concentracao_17": "votos com horário ≥ 17:00 ÷ total de votos no log",
        },
        "overall": {
            "c16": overall.get("concentracao_16"),
            "c17": overall.get("concentracao_17"),
            "flags": overall.get("flags"),
            "corr_c16_lula": overall.get("corr_c16_lula"),
            "corr_c16_flavio": overall.get("corr_c16_flavio"),
            "pooled_hour_share": overall.get("pooled_hour_share") or {
                h: round(hours_pool[h] / tot, 4) for h in sorted(hours_pool)
            } if tot else {},
            "biometria": {
                "share_bio": bio.get("share_bio"),
                "share_nao_bio": bio.get("share_nao_bio"),
                "early_share_nao_bio": (bio.get("early_before16") or {}).get("share_nao_bio"),
                "late16_share_nao_bio": (bio.get("after16") or {}).get("share_nao_bio"),
                "enrichment": bio.get("late_vs_early_enrichment_nao_bio"),
                "n_hab": bio.get("n_hab"),
            },
        },
        "by_uf": by_uf,
        "examples": {
            "extreme": lean(extreme) if extreme else None,
            "flat": lean(flat) if flat else None,
        },
        "top_municipios": (overall.get("top20_late_municipios") or [])[:12],
        "top_secoes": (overall.get("top20_late_secoes") or [])[:10],
        "limits": [
            "Logs cobrem seções com flag ha/da no cs.json do TSE (quase todas totalizadas).",
            "concentracao_16 descreve o horário do voto no log — não prova irregularidade.",
            "Correlação ≠ causalidade: r(c16, Lula%) é descriptivo ao nível de seção.",
            "Biometria classifica modo de habilitação (bio vs não-bio); o log não liga eleitor à escolha de voto.",
            "Shares Lula/Flávio vêm do BU (boletim), cruzados por UF+município+zona+seção.",
        ],
    }


CSS = r'''
:root {
  --bg: #0b1020; --bg2: #121a2e; --card: #162038;
  --line: rgba(255,255,255,0.08); --text: #eef3ff; --muted: #9aa8c7;
  --accent: #5ee1a4; --accent2: #7eb6ff; --warn: #f5c542;
  --hot: #ff7a7a; --cool: #6ec8ff; --flavio: #f0a05a; --lula: #6ad0a0;
  --bar-late: #ff8a6a; --bar-norm: #5b8def;
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
  padding: .85rem 1rem; border-radius: 0 12px 12px 0; margin: 1rem 0 1.4rem; font-size: .95rem;
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
  flex: 1; min-width: 100px; text-align: center;
  background: var(--bg2); border-radius: 10px; padding: .55rem .4rem;
}
.metric-big .m .v {
  font-size: 1.55rem; font-weight: 800; font-variant-numeric: tabular-nums; line-height: 1.1;
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
.scatter-controls select, .toolbar input, .toolbar select, .toolbar button {
  background: var(--bg2); color: var(--text); border: 1px solid var(--line);
  border-radius: 8px; padding: .4rem .65rem; font: inherit; font-size: .88rem;
}
.r-badge {
  display: inline-flex; align-items: center; gap: .4rem;
  background: #1a2e24; border: 1px solid #5ee1a444; color: var(--accent);
  padding: .35rem .75rem; border-radius: 999px; font-weight: 700; font-size: .9rem;
  font-variant-numeric: tabular-nums;
}
.toolbar { display: flex; flex-wrap: wrap; gap: .5rem; margin: .6rem 0 0.8rem; align-items: center; }
.table-wrap { overflow: auto; max-height: 420px; border: 1px solid var(--line); border-radius: 12px; }
table { width: 100%; border-collapse: collapse; font-size: .82rem; }
th, td { padding: .4rem .55rem; text-align: left; border-bottom: 1px solid var(--line); white-space: nowrap; }
th { position: sticky; top: 0; background: var(--bg2); color: var(--muted); font-weight: 600; z-index: 1; }
tr:hover td { background: #1a2740; }
.pct { font-variant-numeric: tabular-nums; }
footer { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--line); font-size: .85rem; color: var(--muted); }
.tabs { display: flex; gap: .4rem; margin: .8rem 0; flex-wrap: wrap; }
.tabs button {
  background: var(--bg2); color: var(--muted); border: 1px solid var(--line);
  border-radius: 999px; padding: .35rem .85rem; cursor: pointer; font: inherit; font-size: .85rem;
}
.tabs button.active { color: #0b1020; background: var(--accent); border-color: var(--accent); font-weight: 700; }
ul.limits { margin: .4rem 0 0; padding-left: 1.1rem; color: var(--muted); font-size: .9rem; }
ul.limits li { margin: .25rem 0; }
.chip-row { display: flex; flex-wrap: wrap; gap: .4rem; margin: .5rem 0 1rem; }
.chip {
  font-size: .78rem; padding: .28rem .6rem; border-radius: 999px;
  background: var(--bg2); border: 1px solid var(--line); color: var(--text);
}
.chip b { color: var(--hot); font-variant-numeric: tabular-nums; }
'''

HTML = r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<meta name="description" content="Aula visual: concentração de votos no fim do dia (voto tardio) e biometria na habilitação — logs de urna BA+CE, 1º turno 2026." />
<title>Voto tardio BA+CE — aula 2026</title>
<link rel="stylesheet" href="styles.css" />
</head>
<body>
<main>
  <div class="tag">1º turno · 04/10/2026 · logs de urna BA + CE</div>
  <h1>Voto tardio: o que o log da urna mostra</h1>
  <p class="lead">
    Esta página ensina <strong>só</strong> a métrica de concentração no fim do dia
    (<code>concentracao_16</code>) a partir dos logs de urna de Bahia e Ceará —
    com biometria como variável relacionada. Sem misturar discrepância ideológica.
  </p>

  <div class="stats-row" id="top-stats">
    <div class="stat"><div class="v" id="st-n">—</div><div class="k">seções (log OK)</div></div>
    <div class="stat"><div class="v" id="st-med">—</div><div class="k">mediana c16</div></div>
    <div class="stat"><div class="v" id="st-r">—</div><div class="k">r(c16, Lula%)</div></div>
    <div class="stat"><div class="v" id="st-bio">—</div><div class="k">enriquec. não-bio tarde</div></div>
  </div>

  <h2><span class="num">1</span>O que é concentração no fim do dia</h2>
  <p>
    Cada linha do log da urna traz o horário em que o voto foi computado.
    A métrica <strong>concentracao_16</strong> é a fração de votos da seção
    registrados a partir das 16h (horário de eleição).
  </p>
  <div class="def-box">
    <div>definição</div>
    <div class="formula">concentracao_16 = votos_com_hora ≥ 16:00 / n_votos_log</div>
    <div class="muted">Analogamente, concentracao_17 usa o corte ≥ 17:00. Dia = 04/10/2026.</div>
  </div>
  <div class="note">
    <strong>Lição visual:</strong> seções “chatas” espalham votos ao longo do dia;
    seções extremas empilham uma fatia grande depois das 16h/17h. Isso é um
    <em>padrão descritivo</em> — não é, por si só, prova de fraude.
  </div>

  <div class="legend-row">
    <span class="norm">antes das 16h</span>
    <span class="late">16h ou depois</span>
  </div>
  <div class="grid2" id="pair-charts">
    <div class="card hot" id="card-extreme">
      <div class="label">extremo — muita concentração</div>
      <div class="place" id="ex-place">…</div>
      <div class="meta-line" id="ex-meta">…</div>
      <div class="chart-wrap" id="ex-chart"></div>
      <div class="metric-big">
        <div class="m"><div class="v hot" id="ex-c16">—</div><div class="k">c16</div></div>
        <div class="m"><div class="v hot" id="ex-c17">—</div><div class="k">c17</div></div>
        <div class="m"><div class="v" id="ex-n">—</div><div class="k">votos log</div></div>
      </div>
    </div>
    <div class="card cool" id="card-flat">
      <div class="label">plano — pouca concentração</div>
      <div class="place" id="fl-place">…</div>
      <div class="meta-line" id="fl-meta">…</div>
      <div class="chart-wrap" id="fl-chart"></div>
      <div class="metric-big">
        <div class="m"><div class="v cool" id="fl-c16">—</div><div class="k">c16</div></div>
        <div class="m"><div class="v cool" id="fl-c17">—</div><div class="k">c17</div></div>
        <div class="m"><div class="v" id="fl-n">—</div><div class="k">votos log</div></div>
      </div>
    </div>
  </div>

  <h2><span class="num">2</span>Panorama BA + CE (todas as seções com log)</h2>
  <p class="muted" id="panorama-lead">Carregando resumo…</p>
  <div class="chip-row" id="flag-chips"></div>
  <div class="card">
    <h3>Distribuição horária agregada (pool de votos)</h3>
    <div class="chart-wrap" id="pool-chart"></div>
  </div>
  <div class="grid2" style="margin-top:1rem">
    <div class="card">
      <h3>Bahia</h3>
      <div id="ba-stats" class="muted">…</div>
    </div>
    <div class="card">
      <h3>Ceará</h3>
      <div id="ce-stats" class="muted">…</div>
    </div>
  </div>

  <h2><span class="num">3</span>Scatter: concentracao_16 × voto no 1º turno</h2>
  <p>
    Cada ponto é uma seção. Eixo X = concentracao_16; eixo Y = share do candidato
    (Lula ou Flávio, no BU). A linha é regressão linear simples; <strong>r</strong> é Pearson.
  </p>
  <div class="scatter-controls">
    <label>UF
      <select id="uf-filter">
        <option value="ALL">BA + CE</option>
        <option value="BA">Só Bahia</option>
        <option value="CE">Só Ceará</option>
      </select>
    </label>
    <label>Y
      <select id="y-metric">
        <option value="l">Lula %</option>
        <option value="f">Flávio %</option>
      </select>
    </label>
    <span class="r-badge" id="r-badge">r = —</span>
    <span class="muted" id="scatter-n" style="font-size:.85rem"></span>
  </div>
  <div class="scatter-box">
    <canvas id="scatter" width="900" height="520"></canvas>
  </div>
  <div class="caveat" id="scatter-tip">
    Passe o mouse para ver município / zona / seção. Pontos com c16 alto e Lula% alto
    puxam r para cima — mas correlação no nível de seção não implica causalidade.
  </div>

  <h2><span class="num">4</span>Biometria (variável relacionada)</h2>
  <p>
    O log registra o <em>modo de habilitação</em> (biométrica vs manual/nascimento),
    sem identificar o eleitor nem a escolha de voto. Comparar a fatia não-bio
    <em>antes</em> das 16h com a fatia <em>depois</em> das 16h mostra se o fim do dia
    está enriquecido em habilitação não-biométrica.
  </p>
  <div class="stats-row" id="bio-stats"></div>
  <div class="note" id="bio-note">…</div>

  <h2><span class="num">5</span>Explorador de seções</h2>
  <div class="tabs" id="expl-tabs">
    <button type="button" class="active" data-uf="BA">Bahia</button>
    <button type="button" data-uf="CE">Ceará</button>
  </div>
  <div class="toolbar">
    <input type="search" id="search" placeholder="município, zona, seção…" />
    <select id="sort">
      <option value="c16_desc">c16 ↓</option>
      <option value="c16_asc">c16 ↑</option>
      <option value="c17_desc">c17 ↓</option>
      <option value="l_desc">Lula% ↓</option>
      <option value="n_desc">votos ↓</option>
    </select>
    <span class="muted" id="expl-status" style="font-size:.85rem"></span>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>Município</th><th>Z</th><th>S</th><th>votos</th>
          <th>c16</th><th>c17</th><th>Lula%</th><th>Flávio%</th>
          <th>bio%</th><th>último</th>
        </tr>
      </thead>
      <tbody id="expl-body"></tbody>
    </table>
  </div>

  <h2><span class="num">6</span>Limites honestos</h2>
  <ul class="limits" id="limits-list"></ul>

  <footer>
    Fonte: logs de urna (arquivo-urna TSE, pleito 3220) + BU para shares.
    Página didática — voto tardio apenas. Publicado via here.now.
  </footer>
</main>
<script src="app.js"></script>
</body>
</html>
'''

APP_JS = r'''
(() => {
  const $ = (id) => document.getElementById(id);
  const pct = (x, d = 1) => x == null ? "—" : (100 * x).toFixed(d) + "%";
  const fmt = (x, d = 1) => x == null ? "—" : Number(x).toFixed(d);

  let resumo = null;
  let ba = [];
  let ce = [];
  let explUF = "BA";

  function hourBarsSVG(hours, w = 420, h = 160) {
    const keys = [];
    for (let i = 8; i <= 19; i++) keys.push(String(i).padStart(2, "0"));
    const vals = keys.map((k) => (hours && hours[k]) || 0);
    const max = Math.max(1, ...vals);
    const padL = 28, padR = 8, padT = 12, padB = 28;
    const bw = (w - padL - padR) / keys.length;
    let bars = "";
    keys.forEach((k, i) => {
      const v = vals[i];
      const bh = (v / max) * (h - padT - padB);
      const x = padL + i * bw + 2;
      const y = h - padB - bh;
      const late = parseInt(k, 10) >= 16;
      const fill = late ? "#ff8a6a" : "#5b8def";
      bars += `<rect x="${x}" y="${y}" width="${bw - 4}" height="${bh}" rx="3" fill="${fill}" opacity="0.92"/>`;
      bars += `<text x="${x + (bw - 4) / 2}" y="${h - 10}" text-anchor="middle" fill="#9aa8c7" font-size="10">${parseInt(k, 10)}</text>`;
    });
    return `<svg viewBox="0 0 ${w} ${h}" role="img">${bars}</svg>`;
  }

  function fillExample(prefix, row) {
    if (!row) return;
    $(prefix === "ex" ? "ex-place" : "fl-place").textContent =
      `${row.m || "—"} (${row.uf})`;
    $(prefix === "ex" ? "ex-meta" : "fl-meta").textContent =
      `zona ${row.z} · seção ${row.s} · ${row.ft || "?"} → ${row.lt || "?"} · enc ${row.et || "—"}`;
    $(prefix === "ex" ? "ex-chart" : "fl-chart").innerHTML = hourBarsSVG(row.h || {});
    $(prefix === "ex" ? "ex-c16" : "fl-c16").textContent = pct(row.c16);
    $(prefix === "ex" ? "ex-c17" : "fl-c17").textContent = pct(row.c17);
    $(prefix === "ex" ? "ex-n" : "fl-n").textContent = row.n ?? "—";
  }

  function renderResumo() {
    const o = resumo.overall || {};
    const c16 = o.c16 || {};
    $("st-n").textContent = (resumo.n_secoes || 0).toLocaleString("pt-BR");
    $("st-med").textContent = pct(c16.median);
    $("st-r").textContent = o.corr_c16_lula == null ? "—" : fmt(o.corr_c16_lula, 3);
    const enr = (o.biometria || {}).enrichment;
    $("st-bio").textContent = enr == null ? "—" : fmt(enr, 2) + "×";

    $("panorama-lead").textContent =
      `${(resumo.n_secoes || 0).toLocaleString("pt-BR")} seções · ` +
      `${(resumo.n_votos || 0).toLocaleString("pt-BR")} votos no log · ` +
      `mediana c16 = ${pct(c16.median)} · média = ${pct(c16.mean)}`;

    const flags = o.flags || {};
    const chips = [
      ["c16 ≥ 20%", flags.c16_ge_20pct],
      ["c16 ≥ 30%", flags.c16_ge_30pct],
      ["c17 ≥ 10%", flags.c17_ge_10pct],
      ["último ≥ 18h", flags.last_after_18h],
      ["último ≥ 19h", flags.last_after_19h],
    ];
    $("flag-chips").innerHTML = chips.map(([k, v]) =>
      `<span class="chip">${k}: <b>${(v ?? 0).toLocaleString("pt-BR")}</b></span>`
    ).join("");

    $("pool-chart").innerHTML = hourBarsSVG(
      Object.fromEntries(
        Object.entries(o.pooled_hour_share || {}).map(([h, s]) => [h, Math.round(s * 10000)])
      ),
      520, 170
    );

    for (const uf of ["BA", "CE"]) {
      const u = (resumo.by_uf || {})[uf] || {};
      $(uf === "BA" ? "ba-stats" : "ce-stats").innerHTML =
        `<div>seções: <b>${(u.n || 0).toLocaleString("pt-BR")}</b></div>` +
        `<div>mediana c16: <b>${pct(u.c16_median)}</b> · média: <b>${pct(u.c16_mean)}</b></div>` +
        `<div>r(c16, Lula%): <b>${u.corr_lula == null ? "—" : fmt(u.corr_lula, 3)}</b></div>` +
        `<div>r(c16, Flávio%): <b>${u.corr_flavio == null ? "—" : fmt(u.corr_flavio, 3)}</b></div>`;
    }

    fillExample("ex", (resumo.examples || {}).extreme);
    fillExample("fl", (resumo.examples || {}).flat);

    const bio = o.biometria || {};
    $("bio-stats").innerHTML = [
      ["share bio", pct(bio.share_bio)],
      ["não-bio cedo", pct(bio.early_share_nao_bio)],
      ["não-bio ≥16h", pct(bio.late16_share_nao_bio)],
      ["enriquecimento", bio.enrichment == null ? "—" : fmt(bio.enrichment, 2) + "×"],
    ].map(([k, v]) => `<div class="stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join("");
    $("bio-note").innerHTML =
      `<strong>Leitura:</strong> enriquecimento ≈ (share não-bio após 16h) / (share não-bio antes das 16h). ` +
      `Valor ≈ 1 = sem diferença de horário; &gt; 1 = fim do dia um pouco mais não-biométrico. ` +
      `Pool: ${(bio.n_hab || 0).toLocaleString("pt-BR")} habilitações.`;

    $("limits-list").innerHTML = (resumo.limits || []).map((t) => `<li>${t}</li>`).join("");
  }

  function currentPoints() {
    const uf = $("uf-filter").value;
    let rows = uf === "BA" ? ba : uf === "CE" ? ce : ba.concat(ce);
    const yKey = $("y-metric").value;
    return rows.filter((r) => r.c16 != null && r[yKey] != null);
  }

  function pearson(pts, yKey) {
    const n = pts.length;
    if (n < 3) return null;
    let mx = 0, my = 0;
    for (const p of pts) { mx += p.c16; my += p[yKey]; }
    mx /= n; my /= n;
    let num = 0, dx = 0, dy = 0;
    for (const p of pts) {
      const a = p.c16 - mx, b = p[yKey] - my;
      num += a * b; dx += a * a; dy += b * b;
    }
    if (!dx || !dy) return null;
    return num / Math.sqrt(dx * dy);
  }

  function linreg(pts, yKey) {
    const n = pts.length;
    if (n < 3) return null;
    let mx = 0, my = 0;
    for (const p of pts) { mx += p.c16; my += p[yKey]; }
    mx /= n; my /= n;
    let varx = 0, cov = 0;
    for (const p of pts) {
      const a = p.c16 - mx;
      varx += a * a;
      cov += a * (p[yKey] - my);
    }
    if (!varx) return null;
    const slope = cov / varx;
    return { slope, intercept: my - slope * mx };
  }

  function drawScatter() {
    const canvas = $("scatter");
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || 900;
    const cssH = 520;
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const W = cssW, H = cssH;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#162038";
    ctx.fillRect(0, 0, W, H);

    const yKey = $("y-metric").value;
    const pts = currentPoints();
    const r = pearson(pts, yKey);
    const reg = linreg(pts, yKey);
    $("r-badge").textContent = r == null ? "r = —" : `r = ${r.toFixed(3)}`;
    $("scatter-n").textContent = `${pts.length.toLocaleString("pt-BR")} seções`;

    const pad = { l: 52, r: 16, t: 16, b: 42 };
    const x0 = pad.l, y0 = pad.t, x1 = W - pad.r, y1 = H - pad.b;
    const xmin = 0, xmax = Math.max(0.05, ...pts.map((p) => p.c16), 0.5);
    const ymin = 0, ymax = 1;

    const X = (v) => x0 + ((v - xmin) / (xmax - xmin || 1)) * (x1 - x0);
    const Y = (v) => y1 - ((v - ymin) / (ymax - ymin || 1)) * (y1 - y0);

    // grid
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 5; i++) {
      const yv = i / 5;
      ctx.beginPath(); ctx.moveTo(x0, Y(yv)); ctx.lineTo(x1, Y(yv)); ctx.stroke();
      ctx.fillStyle = "#9aa8c7"; ctx.font = "11px system-ui";
      ctx.fillText((yv * 100).toFixed(0) + "%", 8, Y(yv) + 4);
    }
    for (let i = 0; i <= 5; i++) {
      const xv = xmin + (i / 5) * (xmax - xmin);
      ctx.beginPath(); ctx.moveTo(X(xv), y0); ctx.lineTo(X(xv), y1); ctx.stroke();
      ctx.fillStyle = "#9aa8c7";
      ctx.fillText((xv * 100).toFixed(0) + "%", X(xv) - 10, y1 + 18);
    }
    ctx.fillStyle = "#9aa8c7";
    ctx.fillText("concentracao_16 →", x0, H - 8);
    ctx.save();
    ctx.translate(14, (y0 + y1) / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText(yKey === "l" ? "Lula % ↑" : "Flávio % ↑", 0, 0);
    ctx.restore();

    // points (subsample if huge for draw speed, but keep all for r)
    const MAX_DRAW = 12000;
    let draw = pts;
    if (pts.length > MAX_DRAW) {
      draw = [];
      const step = pts.length / MAX_DRAW;
      for (let i = 0; i < MAX_DRAW; i++) draw.push(pts[Math.floor(i * step)]);
    }
    const color = yKey === "l" ? "rgba(106,208,160,0.35)" : "rgba(240,160,90,0.35)";
    ctx.fillStyle = color;
    for (const p of draw) {
      ctx.beginPath();
      ctx.arc(X(p.c16), Y(p[yKey]), 2.2, 0, Math.PI * 2);
      ctx.fill();
    }

    if (reg) {
      ctx.strokeStyle = "#5ee1a4";
      ctx.lineWidth = 2;
      ctx.beginPath();
      const xA = xmin, xB = xmax;
      ctx.moveTo(X(xA), Y(reg.intercept + reg.slope * xA));
      ctx.lineTo(X(xB), Y(reg.intercept + reg.slope * xB));
      ctx.stroke();
    }

    canvas._scatter = { pts, X, Y, yKey, x0, y0, x1, y1 };
  }

  function nearest(mx, my) {
    const s = $("scatter")._scatter;
    if (!s) return null;
    let best = null, bestD = 12;
    for (const p of s.pts) {
      const dx = s.X(p.c16) - mx;
      const dy = s.Y(p[s.yKey]) - my;
      const d = Math.hypot(dx, dy);
      if (d < bestD) { bestD = d; best = p; }
    }
    return best;
  }

  function renderExplorer() {
    const q = ($("search").value || "").trim().toLowerCase();
    const sort = $("sort").value;
    let rows = explUF === "BA" ? ba.slice() : ce.slice();
    if (q) {
      rows = rows.filter((r) =>
        (r.m || "").toLowerCase().includes(q) ||
        String(r.z).includes(q) ||
        String(r.s).includes(q) ||
        (r.k || "").includes(q)
      );
    }
    const sorters = {
      c16_desc: (a, b) => (b.c16 || 0) - (a.c16 || 0),
      c16_asc: (a, b) => (a.c16 || 0) - (b.c16 || 0),
      c17_desc: (a, b) => (b.c17 || 0) - (a.c17 || 0),
      l_desc: (a, b) => (b.l || 0) - (a.l || 0),
      n_desc: (a, b) => (b.n || 0) - (a.n || 0),
    };
    rows.sort(sorters[sort] || sorters.c16_desc);
    const show = rows.slice(0, 400);
    $("expl-status").textContent =
      `mostrando ${show.length.toLocaleString("pt-BR")} de ${rows.length.toLocaleString("pt-BR")}`;
    $("expl-body").innerHTML = show.map((r) =>
      `<tr>
        <td>${r.m || "—"}</td><td>${r.z}</td><td>${r.s}</td><td>${r.n}</td>
        <td class="pct">${pct(r.c16)}</td><td class="pct">${pct(r.c17)}</td>
        <td class="pct">${pct(r.l)}</td><td class="pct">${pct(r.f)}</td>
        <td class="pct">${pct(r.sb)}</td><td>${r.lt || "—"}</td>
      </tr>`
    ).join("");
  }

  async function boot() {
    const [r, b, c] = await Promise.all([
      fetch("data/resumo.json").then((x) => x.json()),
      fetch("data/ba.json").then((x) => x.json()),
      fetch("data/ce.json").then((x) => x.json()),
    ]);
    resumo = r;
    ba = b;
    ce = c;
    renderResumo();
    drawScatter();
    renderExplorer();

    $("uf-filter").addEventListener("change", drawScatter);
    $("y-metric").addEventListener("change", drawScatter);
    window.addEventListener("resize", drawScatter);

    const canvas = $("scatter");
    canvas.addEventListener("mousemove", (ev) => {
      const rect = canvas.getBoundingClientRect();
      const mx = ev.clientX - rect.left;
      const my = ev.clientY - rect.top;
      const p = nearest(mx, my);
      if (p) {
        $("scatter-tip").textContent =
          `${p.m} (${p.uf}) · z${p.z}/s${p.s} · c16=${pct(p.c16)} · ` +
          `Lula=${pct(p.l)} · Flávio=${pct(p.f)} · votos=${p.n} · último=${p.lt || "—"}`;
      }
    });

    document.querySelectorAll("#expl-tabs button").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#expl-tabs button").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        explUF = btn.dataset.uf;
        renderExplorer();
      });
    });
    $("search").addEventListener("input", renderExplorer);
    $("sort").addEventListener("change", renderExplorer);
  }

  boot().catch((e) => {
    document.body.insertAdjacentHTML(
      "afterbegin",
      `<pre style="color:#ff7a7a;padding:1rem">Erro ao carregar dados: ${e}</pre>`
    );
  });
})();
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    DATA.mkdir(parents=True, exist_ok=True)

    print("Loading rows from JSONL...", flush=True)
    rows = load_rows()
    print(f"  n={len(rows)}", flush=True)
    if len(rows) < 100:
        raise SystemExit(f"too few rows ({len(rows)}); wait for download")

    analise_path = SAMPLE / "analise_tarde_BA_CE.json"
    if analise_path.exists():
        analise = json.loads(analise_path.read_text(encoding="utf-8"))
    else:
        print("WARNING: analise_tarde_BA_CE.json missing — building minimal resumo", flush=True)
        analise = {"overall": {}}

    resumo = build_resumo(rows, analise)

    ba_lean = [lean(r) for r in rows if r["uf"] == "BA"]
    ce_lean = [lean(r) for r in rows if r["uf"] == "CE"]
    # explorer files: drop hours to shrink (hours kept in examples inside resumo)
    def lean_expl(r):
        o = lean(r, with_hours=False)
        return o

    ba_expl = [lean_expl(r) for r in rows if r["uf"] == "BA"]
    ce_expl = [lean_expl(r) for r in rows if r["uf"] == "CE"]

    meta = {
        "displayName": "Voto tardio BA+CE — aula 2026",
        "generated_at": resumo["generated_at"],
        "n_secoes": resumo["n_secoes"],
        "n_ba": len(ba_expl),
        "n_ce": len(ce_expl),
        "files": ["index.html", "app.js", "styles.css", "data/resumo.json", "data/ba.json", "data/ce.json", "data/meta.json"],
        "scope": "late-vote only (no ideological discrepancy)",
        "corr_c16_lula": resumo["overall"].get("corr_c16_lula"),
        "median_c16": (resumo["overall"].get("c16") or {}).get("median"),
    }

    (DATA / "resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (DATA / "ba.json").write_text(
        json.dumps(ba_expl, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (DATA / "ce.json").write_text(
        json.dumps(ce_expl, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    (DATA / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # remove old discrepancy explorer payload if present
    for stale in ("secoes_ba_ce.json", "secoes_logs.json"):
        p = DATA / stale
        if p.exists():
            p.unlink()
            print("removed stale", p.name, flush=True)

    (OUT / "styles.css").write_text(CSS.strip() + "\n", encoding="utf-8")
    (OUT / "index.html").write_text(HTML.strip() + "\n", encoding="utf-8")
    (OUT / "app.js").write_text(APP_JS.strip() + "\n", encoding="utf-8")

    # update publish displayName
    pub = OUT / "publish-herenow.sh"
    if pub.exists():
        txt = pub.read_text(encoding="utf-8")
        txt2 = txt.replace(
            'DISPLAY_NAME="Concentração + biometria — aula 2026"',
            'DISPLAY_NAME="Voto tardio BA+CE — aula 2026"',
        )
        # also handle if already updated or other old name
        if 'DISPLAY_NAME="Voto tardio BA+CE — aula 2026"' not in txt2:
            import re
            txt2 = re.sub(
                r'DISPLAY_NAME="[^"]*"',
                'DISPLAY_NAME="Voto tardio BA+CE — aula 2026"',
                txt,
                count=1,
            )
        pub.write_text(txt2, encoding="utf-8")

    print("WROTE site:", flush=True)
    for p in sorted(OUT.rglob("*")):
        if p.is_file() and ".herenow" not in str(p):
            print(f"  {p.relative_to(OUT)}  {p.stat().st_size/1e6:.2f} MB", flush=True)
    print(json.dumps({
        "n": resumo["n_secoes"],
        "median_c16": (resumo["overall"].get("c16") or {}).get("median"),
        "corr_lula": resumo["overall"].get("corr_c16_lula"),
        "BA": resumo["by_uf"].get("BA"),
        "CE": resumo["by_uf"].get("CE"),
    }, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
