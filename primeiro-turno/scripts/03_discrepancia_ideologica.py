#!/usr/bin/env python3
"""Ideological discrepancy: president Lula/Flávio vs federal deputy PL/PT shares per section.
Only BA+CE+SC (deputy zips downloaded). Signature of ticket-splitting, NOT proof of fraud.
"""
import csv, json, zipfile, io, os
from pathlib import Path
from collections import defaultdict

# Resolve project layout relative to this script (default) or via env var.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
DEPS = ROOT / "deps"
SAMPLE = list(csv.DictReader(open(SAMPLE_DIR / "amostra100.csv", encoding="utf-8")))
# restrict to UFs with deputy data
UFS = {"BA", "CE", "SC"}
sample = [r for r in SAMPLE if r["uf"] in UFS]
keys = {(r["uf"], r["cd_mun"].lstrip("0") or "0", int(r["zona"]), int(r["secao"])): r for r in sample}
print("sample sections in BA/CE/SC:", len(keys))

# Party numbers: PL=22, PT=13 (also check party legend votes NR_VOTAVEL length)
# For federal deputy (CD_CARGO=6): candidate numbers are 4 digits starting with party,
# legend votes are 2-digit party number.
PL, PT = "22", "13"

def party_of(nr):
    nr = str(nr).strip()
    if nr in ("95", "96"):  # branco/nulo
        return None
    if len(nr) <= 2:
        return nr.zfill(2)
    return nr[:2]

# Aggregate deputy votes for sampled sections only
dep = defaultdict(lambda: defaultdict(int))  # key -> party -> votes
meta_cargo = set()

for uf in sorted(UFS):
    zpath = DEPS / f"votacao_secao_2026_{uf}.zip"
    print(f"scanning {zpath.name}...", flush=True)
    with zipfile.ZipFile(zpath) as z:
        # find csv
        names = [n for n in z.namelist() if n.lower().endswith(".csv")]
        print("  csvs", names)
        name = names[0]
        with z.open(name) as fh:
            # wrap text
            text = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            reader = csv.DictReader(text, delimiter=";")
            n = 0
            for row in reader:
                n += 1
                if row.get("CD_CARGO") not in ("6", "06"):
                    continue
                mun = (row["CD_MUNICIPIO"] or "").lstrip("0") or "0"
                zona = int(row["NR_ZONA"])
                secao = int(row["NR_SECAO"])
                k = (uf, mun, zona, secao)
                if k not in keys:
                    continue
                meta_cargo.add(row.get("DS_CARGO"))
                p = party_of(row["NR_VOTAVEL"])
                if p is None:
                    # still count toward total via special
                    dep[k]["_branco_nulo"] += int(row["QT_VOTOS"] or 0)
                    continue
                q = int(row["QT_VOTOS"] or 0)
                dep[k][p] += q
                dep[k]["_total"] += q
            print(f"  rows scanned {n}, sections hit {sum(1 for k in dep if k[0]==uf)}")

print("cargo labels", meta_cargo)
print("sections with dep data", len(dep))

# Join with president shares from sample
out_rows = []
for k, srow in keys.items():
    d = dep.get(k)
    if not d or d.get("_total", 0) < 30:
        continue
    total = d["_total"]
    # valid dep = total (already excluding? we put branco/nulo in _branco_nulo and also may be in _total)
    # Recompute carefully: _total includes all non-95/96; branco/nulo separate
    pl = d.get(PL, 0)
    pt = d.get(PT, 0)
    pl_share = pl / total
    pt_share = pt / total
    lula_share = float(srow["lula_share"])
    flavio_share = float(srow["flavio_share"])
    # Discrepancy scores (ticket splitting signatures)
    # A: high PL dep but high Lula president  -> pl_share - flavio_share  or pl_share - (1-lula) 
    # User asked: (PL_share_dep - Lula_share_pres) or (PL_share_dep - Flávio_share)
    score_pl_minus_lula = pl_share - lula_share
    score_pl_minus_flavio = pl_share - flavio_share
    score_pt_minus_lula = pt_share - lula_share
    # "cross" inconsistency: PL deputies strong while Lula president strong
    cross_pl_lula = pl_share + lula_share  # high means both high (inconsistent if ideology assumed aligned)
    # better: residual of PL vs Flávio alignment
    # expected: PL_dep ≈ Flávio_pres in right-leaning; PT_dep ≈ Lula in left-leaning
    align_right = pl_share - flavio_share
    align_left = pt_share - lula_share
    out_rows.append({
        "uf": k[0],
        "cd_mun": k[1],
        "nm_mun": srow["nm_mun"],
        "zona": k[2],
        "secao": k[3],
        "estrato": srow["estrato"],
        "lula_share": round(lula_share, 4),
        "flavio_share": round(flavio_share, 4),
        "pl_share_dep": round(pl_share, 4),
        "pt_share_dep": round(pt_share, 4),
        "dep_total": total,
        "score_PL_minus_Lula": round(score_pl_minus_lula, 4),
        "score_PL_minus_Flavio": round(score_pl_minus_flavio, 4),
        "score_PT_minus_Lula": round(score_pt_minus_lula, 4),
        "cross_PL_and_Lula": round(pl_share * lula_share, 4),  # product high => both elevated
    })

print("joined", len(out_rows))

# Summary stats
import statistics as st
def summarize(vals):
    vals=list(vals)
    return {
        "n": len(vals),
        "mean": round(st.mean(vals), 4) if vals else None,
        "median": round(st.median(vals), 4) if vals else None,
        "stdev": round(st.pstdev(vals), 4) if len(vals)>1 else None,
        "min": round(min(vals), 4) if vals else None,
        "max": round(max(vals), 4) if vals else None,
        "p10": round(sorted(vals)[max(0,int(0.1*len(vals))-1)], 4) if vals else None,
        "p90": round(sorted(vals)[min(len(vals)-1,int(0.9*len(vals)))], 4) if vals else None,
    }

summary = {
    "n_joined": len(out_rows),
    "PL_minus_Lula": summarize(r["score_PL_minus_Lula"] for r in out_rows),
    "PL_minus_Flavio": summarize(r["score_PL_minus_Flavio"] for r in out_rows),
    "PT_minus_Lula": summarize(r["score_PT_minus_Lula"] for r in out_rows),
    "pl_share_dep": summarize(r["pl_share_dep"] for r in out_rows),
    "pt_share_dep": summarize(r["pt_share_dep"] for r in out_rows),
    "lula_share": summarize(r["lula_share"] for r in out_rows),
    "flavio_share": summarize(r["flavio_share"] for r in out_rows),
}

# Extreme sections: high PL dep + high Lula (cross-ticket)
# Define: pl_share_dep >= 0.20 and lula_share >= 0.55  OR top by PL_minus_Flavio when Lula high
cross = [r for r in out_rows if r["pl_share_dep"] >= 0.15 and r["lula_share"] >= 0.55]
cross_rev = [r for r in out_rows if r["pt_share_dep"] >= 0.15 and r["flavio_share"] >= 0.45]
extreme_pl_gt_flavio = sorted(out_rows, key=lambda r: r["score_PL_minus_Flavio"], reverse=True)[:15]
extreme_pl_gt_lula_neg = sorted(out_rows, key=lambda r: r["score_PL_minus_Lula"])[:10]  # most negative = Lula >> PL
extreme_pl_gt_lula_pos = sorted(out_rows, key=lambda r: r["score_PL_minus_Lula"], reverse=True)[:10]

# By estrato
by_est = defaultdict(list)
for r in out_rows:
    by_est[r["estrato"]].append(r["score_PL_minus_Flavio"])
estrato_summary = {e: summarize(v) for e,v in sorted(by_est.items())}

# By UF
by_uf = defaultdict(list)
for r in out_rows:
    by_uf[r["uf"]].append(r["score_PL_minus_Flavio"])
uf_summary = {u: summarize(v) for u,v in sorted(by_uf.items())}

result = {
    "summary": summary,
    "estrato_PL_minus_Flavio": estrato_summary,
    "uf_PL_minus_Flavio": uf_summary,
    "n_cross_PL_high_Lula": len(cross),
    "cross_PL_high_Lula": sorted(cross, key=lambda r: r["pl_share_dep"]*r["lula_share"], reverse=True)[:20],
    "n_cross_PT_high_Flavio": len(cross_rev),
    "cross_PT_high_Flavio": sorted(cross_rev, key=lambda r: r["pt_share_dep"]*r["flavio_share"], reverse=True)[:20],
    "top_PL_minus_Flavio": extreme_pl_gt_flavio,
    "top_PL_minus_Lula": extreme_pl_gt_lula_pos,
    "bottom_PL_minus_Lula": extreme_pl_gt_lula_neg,
    "all_rows": out_rows,
}
outp = SAMPLE_DIR / "discrepancia.json"
# save without all_rows in pretty, and csv separately
slim = {k:v for k,v in result.items() if k != "all_rows"}
outp.write_text(json.dumps(slim, ensure_ascii=False, indent=2), encoding="utf-8")
with open(SAMPLE_DIR / "discrepancia_secoes.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
    w.writeheader(); w.writerows(out_rows)
print(json.dumps(summary, indent=2))
print("cross PL+Lula", len(cross), "cross PT+Flavio", len(cross_rev))
print("wrote", outp)
