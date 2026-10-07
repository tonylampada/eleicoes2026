#!/usr/bin/env python3
"""Download per-section aux + log.jez for the 100-sample. Cap ~500MB total."""
import csv, json, time, zipfile, io, os, sys
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
PLEITO = "3220"
P = "003220"

# Resolve project layout relative to this script (default) or via env var.
# With this, you can run from the repo root using: python primeiro-turno/scripts/02_download_logs.py
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
LOGS = ROOT / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
BUDGET = 450_000_000  # leave headroom under 500MB
downloaded = 0
stats = {"ok": 0, "fail": 0, "bytes": 0, "errors": []}

def get(url, retries=3):
    global downloaded
    for i in range(retries):
        try:
            req = Request(url, headers={
                "Referer": "https://resultados.tse.jus.br/oficial/app/index.html",
                "User-Agent": "GrokBot-eleicoes26-audit/1.0",
            })
            with urlopen(req, timeout=60) as r:
                data = r.read()
            downloaded += len(data)
            stats["bytes"] += len(data)
            time.sleep(0.05)  # ~20 rps, well under 100
            return data
        except HTTPError as e:
            if e.code == 404:
                raise
            time.sleep(1 + i)
            last = e
        except Exception as e:
            time.sleep(1 + i)
            last = e
    raise last

def ensure_cs(uf):
    uf = uf.lower()
    path = SAMPLE_DIR / f"{uf}-p{P}-cs.json"
    if path.exists() and path.stat().st_size > 1000:
        return json.loads(path.read_text(encoding="utf-8"))
    url = f"{BASE}/arquivo-urna/{PLEITO}/config/{uf}/{uf}-p{P}-cs.json"
    data = get(url)
    path.write_bytes(data)
    return json.loads(data.decode("utf-8"))

def has_aux_flag(cs, mun5, zona4, secao4):
    """Return True if cs.json marks da/ha for this section."""
    for abr in cs.get("abr", []):
        for mu in abr.get("mu", []):
            if mu.get("cd") != mun5:
                continue
            for z in mu.get("zon", []):
                if z.get("cd") != zona4:
                    continue
                for s in z.get("sec", []):
                    if s.get("ns") == secao4:
                        return bool(s.get("da") or s.get("ha"))
    return False

def download_log(uf, mun5, zona, secao):
    uf = uf.lower()
    zona4 = f"{int(zona):04d}"
    secao4 = f"{int(secao):04d}"
    key = f"{uf}_{mun5}_{zona4}_{secao4}"
    out_agg = LOGS / f"{key}.json"
    if out_agg.exists():
        return json.loads(out_agg.read_text(encoding="utf-8"))

    if downloaded > BUDGET:
        return {"key": key, "erro": "budget"}

    aux_url = (f"{BASE}/arquivo-urna/{PLEITO}/dados/{uf}/{mun5}/{zona4}/{secao4}/"
               f"p{P}-{uf}-m{mun5}-z{zona4}-s{secao4}-aux.json")
    try:
        aux = json.loads(get(aux_url).decode("utf-8"))
    except Exception as e:
        return {"key": key, "erro": f"aux:{e}"}

    hashes = aux.get("hashes") or []
    if not hashes:
        return {"key": key, "erro": "no_hashes", "st": aux.get("st")}
    h = hashes[0]
    hsh = h["hash"]
    arqs = h.get("arq") or []
    log_nm = None
    for a in arqs:
        if a.get("tp") in ("log", "logsa"):
            log_nm = a["nm"]
            break
    if not log_nm:
        return {"key": key, "erro": "no_log_in_aux", "arq": arqs}

    log_url = (f"{BASE}/arquivo-urna/{PLEITO}/dados/{uf}/{mun5}/{zona4}/{secao4}/"
               f"{hsh}/{log_nm}")
    try:
        blob = get(log_url)
    except Exception as e:
        return {"key": key, "erro": f"log:{e}"}

    # Parse in-memory: zip -> logd.dat -> vote timestamps only
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            name = z.namelist()[0]
            txt = z.read(name).decode("latin-1")
    except Exception as e:
        return {"key": key, "erro": f"unzip:{e}"}

    hours = {f"{h:02d}": 0 for h in range(6, 18)}
    n_votos = 0
    after16 = 0
    after17 = 0
    first_ts = None
    last_ts = None
    enc = None
    for line in txt.splitlines():
        if not line.startswith("04/10/2026"):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        ts_full = parts[0]  # 04/10/2026 HH:MM:SS
        app = parts[3]
        msg = parts[4]
        if app != "VOTA":
            continue
        if msg == "O voto do eleitor foi computado":
            hhmmss = ts_full.split()[1]
            hh = int(hhmmss[:2])
            n_votos += 1
            if first_ts is None:
                first_ts = hhmmss
            last_ts = hhmmss
            keyh = f"{hh:02d}"
            if keyh in hours:
                hours[keyh] += 1
            else:
                hours[keyh] = hours.get(keyh, 0) + 1
            if hh >= 16:
                after16 += 1
            if hh >= 17:
                after17 += 1
        elif "encerramento" in msg.lower() or msg.startswith("Inicio do Encerramento") or msg == "Código de encerramento digitado":
            if enc is None:
                enc = ts_full.split()[1]

    agg = {
        "key": key,
        "uf": uf.upper(),
        "mun5": mun5,
        "zona": int(zona),
        "secao": int(secao),
        "n_votos_log": n_votos,
        "after16": after16,
        "after17": after17,
        "share_after16": round(after16 / n_votos, 4) if n_votos else None,
        "share_after17": round(after17 / n_votos, 4) if n_votos else None,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "enc_ts": enc,
        "hours": hours,
        "log_bytes": len(blob),
        "st": aux.get("st"),
        "hash": hsh,
        "log_nm": log_nm,
    }
    out_agg.write_text(json.dumps(agg, ensure_ascii=False), encoding="utf-8")
    # do NOT keep raw log on disk
    return agg

def main():
    rows = list(csv.DictReader(open(SAMPLE_DIR / "amostra100.csv", encoding="utf-8")))
    ufs = sorted(set(r["uf"] for r in rows))
    print("UFs:", ufs, flush=True)
    cs_cache = {}
    for uf in ufs:
        print(f"cs {uf}...", flush=True)
        cs_cache[uf] = ensure_cs(uf)

    results = []
    for i, r in enumerate(rows):
        uf = r["uf"]
        mun5 = r["cd_mun5"]
        zona = r["zona"]
        secao = r["secao"]
        # skip if no aux flag (optional check)
        ok_flag = has_aux_flag(cs_cache[uf], mun5, f"{int(zona):04d}", f"{int(secao):04d}")
        agg = download_log(uf, mun5, zona, secao)
        agg["estrato"] = r["estrato"]
        agg["nm_mun"] = r["nm_mun"]
        agg["lula_share"] = float(r["lula_share"])
        agg["valid_csv"] = int(r["valid"])
        agg["cs_has_aux"] = ok_flag
        if "erro" in agg:
            stats["fail"] += 1
            stats["errors"].append(agg)
            print(f"[{i+1}/100] FAIL {agg['key']}: {agg['erro']}", flush=True)
        else:
            stats["ok"] += 1
            print(f"[{i+1}/100] OK {agg['key']} votos={agg['n_votos_log']} after16={agg['share_after16']} after17={agg['share_after17']}", flush=True)
        results.append(agg)
        if downloaded > BUDGET:
            print("BUDGET hit", downloaded, flush=True)
            break

    out = SAMPLE_DIR / "log_aggregates.json"
    out.write_text(json.dumps({"stats": stats, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DONE bytes", stats["bytes"], "ok", stats["ok"], "fail", stats["fail"], flush=True)
    print("wrote", out)

if __name__ == "__main__":
    main()
