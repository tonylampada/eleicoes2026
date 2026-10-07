#!/usr/bin/env python3
"""Summarize late-vote concentration from log aggregates."""
import json, statistics as st, os
from pathlib import Path
from collections import Counter

# Resolve project layout relative to this script (default) or via env var.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
d = json.load(open(SAMPLE_DIR / "log_aggregates.json"))
ok = [r for r in d["results"] if "erro" not in r and (r.get("n_votos_log") or 0) > 0]

def summ(vals):
    vals = list(vals)
    return {
        "n": len(vals),
        "mean": round(st.mean(vals), 4),
        "median": round(st.median(vals), 4),
        "stdev": round(st.pstdev(vals), 4) if len(vals) > 1 else 0,
        "min": round(min(vals), 4),
        "max": round(max(vals), 4),
        "p90": round(sorted(vals)[min(len(vals) - 1, int(0.9 * len(vals)))], 4),
        "p95": round(sorted(vals)[min(len(vals) - 1, int(0.95 * len(vals)))], 4),
    }

def pearson(xs, ys):
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return round(num / den, 4) if den else None

overall = {
    "n": len(ok),
    "after16": summ(r["share_after16"] for r in ok),
    "after17": summ(r["share_after17"] for r in ok),
    "n_votos_log": summ(r["n_votos_log"] for r in ok),
}
by_est = {}
for e in sorted(set(r["estrato"] for r in ok)):
    sub = [r for r in ok if r["estrato"] == e]
    by_est[e] = {
        "n": len(sub),
        "after16": summ(r["share_after16"] for r in sub),
        "after17": summ(r["share_after17"] for r in sub),
    }
by_uf = {}
for u in sorted(set(r["uf"] for r in ok)):
    sub = [r for r in ok if r["uf"] == u]
    by_uf[u] = {
        "n": len(sub),
        "after16": summ(r["share_after16"] for r in sub),
        "after17": summ(r["share_after17"] for r in sub),
    }
flags = {
    "after16_ge_20pct": sum(1 for r in ok if r["share_after16"] >= 0.20),
    "after16_ge_30pct": sum(1 for r in ok if r["share_after16"] >= 0.30),
    "after17_ge_10pct": sum(1 for r in ok if r["share_after17"] >= 0.10),
    "after17_ge_20pct": sum(1 for r in ok if r["share_after17"] >= 0.20),
    "last_after_18h": sum(1 for r in ok if r.get("last_ts") and r["last_ts"] >= "18:00:00"),
    "last_after_19h": sum(1 for r in ok if r.get("last_ts") and r["last_ts"] >= "19:00:00"),
}
corr_lula_16 = pearson((r["lula_share"] for r in ok), (r["share_after16"] for r in ok))
corr_lula_17 = pearson((r["lula_share"] for r in ok), (r["share_after17"] for r in ok))
anoms = sorted(ok, key=lambda r: (r["share_after17"], r["share_after16"]), reverse=True)[:20]
anoms_out = [{
    "key": r["key"], "uf": r["uf"], "nm_mun": r["nm_mun"], "estrato": r["estrato"],
    "n_votos_log": r["n_votos_log"], "share_after16": r["share_after16"],
    "share_after17": r["share_after17"], "first_ts": r["first_ts"], "last_ts": r["last_ts"],
    "enc_ts": r["enc_ts"], "lula_share": r["lula_share"], "hours": r["hours"],
} for r in anoms]
hours = Counter()
for r in ok:
    for h, c in r["hours"].items():
        hours[h] += c
total_v = sum(hours.values())
hour_share = {h: round(hours[h] / total_v, 4) for h in sorted(hours)}
out = {
    "overall": overall, "by_estrato": by_est, "by_uf": by_uf, "flags": flags,
    "corr_lula_share_vs_after16": corr_lula_16, "corr_lula_share_vs_after17": corr_lula_17,
    "pooled_hour_share": hour_share, "pooled_n_votos": total_v, "top20_late": anoms_out,
}
(SAMPLE_DIR / "analise_logs_tarde.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps({
    "overall": overall, "flags": flags,
    "corr16": corr_lula_16, "corr17": corr_lula_17,
    "hours": hour_share,
}, indent=2, ensure_ascii=False))
