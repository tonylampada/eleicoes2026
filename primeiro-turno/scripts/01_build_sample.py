#!/usr/bin/env python3
"""Build ~100-section sample from votacao_secao_2026_BR.csv (president only)."""
import csv, json, random, os
from collections import defaultdict
from pathlib import Path

# Input CSV path (outside repo); override via ELEICOES2026_BR env if desired
BR = Path(os.getenv("ELEICOES2026_BR", "/tmp/vsBR/votacao_secao_2026_BR.csv"))

# Resolve project layout relative to this script (default) or via env var.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

# Capitals to EXCLUDE for "interior" strata (TSE CD_MUNICIPIO, no leading zeros as in CSV)
CAPITALS = {
    "AC": {"1392"},  # Rio Branco - confirm later
    "AL": {"27855"},
    "AM": {"2550"},
    "AP": {"6050"},
    "BA": {"38490"},  # Salvador
    "CE": {"13897"},  # Fortaleza
    "DF": {"97012"},
    "ES": {"57053"},
    "GO": {"93734"},
    "MA": {"9210"},
    "MG": {"41238"},
    "MS": {"90514"},
    "MT": {"90670"},
    "PA": {"4278"},
    "PB": {"20516"},
    "PE": {"25313"},
    "PI": {"12100"},
    "PR": {"75353"},
    "RJ": {"60011"},
    "RN": {"17612"},
    "RO": {"35"},
    "RR": {"3018"},
    "RS": {"88013"},
    "SC": {"81051"},
    "SE": {"31054"},
    "SP": {"71072"},  # São Paulo
    "TO": {"73440"},
}

# Valid candidate numbers for president (exclude 95 branco, 96 nulo)
LULA, FLAVIO = "13", "22"

# Aggregate per section
# key: (uf, mun, zona, secao) -> votes dict
sec = defaultdict(lambda: defaultdict(int))
meta = {}  # mun name

with open(BR, "r", encoding="latin-1", newline="") as f:
    r = csv.DictReader(f, delimiter=";")
    for row in r:
        uf = row["SG_UF"]
        mun = row["CD_MUNICIPIO"].lstrip("0") or "0"
        # keep zero-stripped for capital match; also store padded
        zona = int(row["NR_ZONA"])
        secao = int(row["NR_SECAO"])
        nv = row["NR_VOTAVEL"]
        q = int(row["QT_VOTOS"] or 0)
        k = (uf, mun, zona, secao)
        sec[k][nv] += q
        if k not in meta:
            meta[k] = row["NM_MUNICIPIO"]

rows = []
for k, votes in sec.items():
    uf, mun, zona, secao = k
    total = sum(votes.values())
    valid = total - votes.get("95", 0) - votes.get("96", 0)
    if valid < 50:
        continue
    lula = votes.get(LULA, 0)
    flavio = votes.get(FLAVIO, 0)
    lula_share = lula / valid if valid else 0
    flavio_share = flavio / valid if valid else 0
    is_cap = mun in CAPITALS.get(uf, set())
    rows.append({
        "uf": uf,
        "cd_mun": mun,
        "cd_mun5": mun.zfill(5),
        "nm_mun": meta[k],
        "zona": zona,
        "secao": secao,
        "valid": valid,
        "lula": lula,
        "flavio": flavio,
        "lula_share": round(lula_share, 4),
        "flavio_share": round(flavio_share, 4),
        "is_capital": is_cap,
    })

print(f"eligible sections (≥50 valid): {len(rows)}")

# Verify capitals by name too (in case codes wrong)
by_name_cap = {
    "SALVADOR": "BA", "FORTALEZA": "CE", "SÃO PAULO": "SP", "SAO PAULO": "SP",
    "FLORIANÓPOLIS": "SC", "FLORIANOPOLIS": "SC", "PORTO ALEGRE": "RS",
    "RIO DE JANEIRO": "RJ", "BELO HORIZONTE": "MG", "RECIFE": "PE",
    "CURITIBA": "PR", "BELÉM": "PA", "BELEM": "PA", "MANAUS": "AM",
    "GOIÂNIA": "GO", "GOIANIA": "GO", "BRASILIA": "DF", "BRASÍLIA": "DF",
}
# fix capital flags by name
for r in rows:
    nm = (r["nm_mun"] or "").upper()
    if nm in by_name_cap and by_name_cap[nm] == r["uf"]:
        r["is_capital"] = True
    # also capture actual capital codes for reporting
# print discovered capital codes
cap_codes = defaultdict(set)
for r in rows:
    nm = (r["nm_mun"] or "").upper()
    if nm in by_name_cap and by_name_cap[nm] == r["uf"]:
        cap_codes[r["uf"]].add((r["cd_mun"], r["nm_mun"]))
print("capital codes discovered:", dict(cap_codes))

rng = random.Random(20261006)

def pick(pool, n, label):
    pool = list(pool)
    if len(pool) <= n:
        chosen = pool
    else:
        chosen = rng.sample(pool, n)
    for r in chosen:
        r = dict(r)
        r["estrato"] = label
        yield r

# Strata targets: ~40 BA interior, ~30 CE interior, ~30 rest
ba_int = [r for r in rows if r["uf"] == "BA" and not r["is_capital"]]
ce_int = [r for r in rows if r["uf"] == "CE" and not r["is_capital"]]
# Prefer high-Lula for half of BA/CE
ba_hi = [r for r in ba_int if r["lula_share"] >= 0.55]
ba_lo = [r for r in ba_int if r["lula_share"] < 0.55]
ce_hi = [r for r in ce_int if r["lula_share"] >= 0.55]
ce_lo = [r for r in ce_int if r["lula_share"] < 0.55]

sample = []
sample += list(pick(ba_hi, 28, "BA_int_altoLula"))
sample += list(pick(ba_lo, 12, "BA_int_resto"))
sample += list(pick(ce_hi, 20, "CE_int_altoLula"))
sample += list(pick(ce_lo, 10, "CE_int_resto"))

# Rest of Brazil ~30: mix SP capital, SC, RS, interior SE, AC
sp_cap = [r for r in rows if r["uf"] == "SP" and r["is_capital"]]
sc_all = [r for r in rows if r["uf"] == "SC"]
rs_int = [r for r in rows if r["uf"] == "RS" and not r["is_capital"]]
mg_int = [r for r in rows if r["uf"] == "MG" and not r["is_capital"]]
ac_all = [r for r in rows if r["uf"] == "AC"]
rj_cap = [r for r in rows if r["uf"] == "RJ" and r["is_capital"]]

sample += list(pick(sp_cap, 6, "SP_capital"))
sample += list(pick(sc_all, 8, "SC_mix"))
sample += list(pick(rs_int, 5, "RS_interior"))
sample += list(pick(mg_int, 5, "MG_interior"))
sample += list(pick(ac_all, 3, "AC_mix"))
sample += list(pick(rj_cap, 3, "RJ_capital"))

# Deduplicate by key, keep first estrato
seen = set()
uniq = []
for r in sample:
    k = (r["uf"], r["cd_mun"], r["zona"], r["secao"])
    if k in seen:
        continue
    seen.add(k)
    uniq.append(r)

print(f"sample n={len(uniq)}")
from collections import Counter
print("estratos:", Counter(r["estrato"] for r in uniq))
print("ufs:", Counter(r["uf"] for r in uniq))

# Save
import csv as csvmod
fields = list(uniq[0].keys())
with open(SAMPLE_DIR / "amostra100.csv", "w", newline="", encoding="utf-8") as f:
    w = csvmod.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(uniq)
with open(SAMPLE_DIR / "amostra100.json", "w", encoding="utf-8") as f:
    json.dump(uniq, f, ensure_ascii=False, indent=2)
print("wrote", SAMPLE_DIR / "amostra100.csv")
