#!/usr/bin/env python3
"""Download + parse ALL BA+CE urna LOGS (lean JSONL shards).

- Enumerate sections from cs.json where ha or da is set.
- Fetch aux.json → log.jez, unzip logd.dat in memory, parse votes + biometria.
- Append lean rows to logs_ba_ce/{uf}.jsonl; checkpoint progress.json.
- Join lula_share / flavio_share from discrepancia_BA_CE_secoes.csv.
- Resume-safe; rate-limited; does NOT keep raw .jez on disk.
"""
from __future__ import annotations

import csv
import io
import json
import math
import statistics as st
import threading
import time
import zipfile
import os
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
PLEITO = "3220"
P = "003220"
ELECTION_DAY = "04/10/2026"
# Resolve project layout relative to this script (default) or via env var.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
SAMPLE = SAMPLE_DIR
OUT = ROOT / "logs_ba_ce"
OUT.mkdir(parents=True, exist_ok=True)

UFS = ("ba", "ce")
WORKERS = 12
TARGET_RPS = 18.0  # requests/sec across all workers
PROGRESS_EVERY = 100
PRINT_EVERY = 50

# --- shared state ---
_rate_lock = threading.Lock()
_next_slot = 0.0
_io_lock = threading.Lock()
_done_lock = threading.Lock()
_stats_lock = threading.Lock()

stats = {
    "ok": 0,
    "fail": 0,
    "skip": 0,
    "bytes": 0,
    "started_at": None,
    "updated_at": None,
    "total": 0,
    "done_keys": 0,
}


def rate_limit():
    """Global token spacing ≈ TARGET_RPS."""
    global _next_slot
    with _rate_lock:
        now = time.monotonic()
        slot = max(now, _next_slot)
        _next_slot = slot + (1.0 / TARGET_RPS)
    delay = slot - now
    if delay > 0:
        time.sleep(delay)


def http_get(url: str, retries: int = 4) -> bytes:
    last = None
    for i in range(retries):
        rate_limit()
        try:
            req = Request(
                url,
                headers={
                    "Referer": "https://resultados.tse.jus.br/oficial/app/index.html",
                    "User-Agent": "GrokBot-eleicoes26-audit/1.0",
                    "Accept": "*/*",
                },
            )
            with urlopen(req, timeout=90) as r:
                data = r.read()
            with _stats_lock:
                stats["bytes"] += len(data)
            return data
        except HTTPError as e:
            if e.code == 404:
                raise
            last = e
            time.sleep(0.8 * (2 ** i))
        except (URLError, TimeoutError, OSError) as e:
            last = e
            time.sleep(0.8 * (2 ** i))
    raise last


def load_shares() -> dict:
    """key -> {lula_share, flavio_share, nm_mun, cd_mun} from BU-derived CSV."""
    path = SAMPLE / "discrepancia_BA_CE_secoes.csv"
    out = {}
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            uf = r["uf"].lower()
            mun5 = f"{int(r['cd_mun']):05d}"
            zona4 = f"{int(r['zona']):04d}"
            secao4 = f"{int(r['secao']):04d}"
            key = f"{uf}_{mun5}_{zona4}_{secao4}"
            try:
                lula = float(r["lula_share"]) if r.get("lula_share") not in (None, "") else None
            except ValueError:
                lula = None
            try:
                flavio = float(r["flavio_share"]) if r.get("flavio_share") not in (None, "") else None
            except ValueError:
                flavio = None
            out[key] = {
                "lula_share": lula,
                "flavio_share": flavio,
                "nm_mun": r.get("nm_mun"),
                "cd_mun": mun5,
            }
    return out


def enumerate_sections(shares: dict) -> list[dict]:
    sections = []
    for uf in UFS:
        cs = json.loads((SAMPLE / f"{uf}-p{P}-cs.json").read_text(encoding="utf-8"))
        for abr in cs.get("abr", []):
            for mu in abr.get("mu", []):
                mun5 = f"{int(mu['cd']):05d}"
                nm_mun = mu.get("nm")
                for z in mu.get("zon", []):
                    zona4 = f"{int(z['cd']):04d}"
                    for s in z.get("sec", []):
                        if not (s.get("ha") or s.get("da")):
                            continue
                        secao4 = f"{int(s['ns']):04d}"
                        key = f"{uf}_{mun5}_{zona4}_{secao4}"
                        sh = shares.get(key, {})
                        sections.append({
                            "key": key,
                            "uf": uf,
                            "mun5": mun5,
                            "zona4": zona4,
                            "secao4": secao4,
                            "nm_mun": sh.get("nm_mun") or nm_mun,
                            "lula_share": sh.get("lula_share"),
                            "flavio_share": sh.get("flavio_share"),
                        })
    return sections


def parse_log(txt: str) -> dict:
    """Single-pass: vote hours + biometria sessions (same rules as 07)."""
    hours = {f"{h:02d}": 0 for h in range(6, 20)}
    n_votos = 0
    after16 = 0
    after17 = 0
    first_ts = None
    last_ts = None
    enc = None

    sessions = []
    cur = {
        "tipo_bio": False,
        "manual": False,
        "nascimento": False,
        "start": None,
    }

    def new_cur():
        return {"tipo_bio": False, "manual": False, "nascimento": False, "start": None}

    def finalize(hab_ts, c):
        if c["manual"] or c["nascimento"]:
            mode = "nao_bio"
        elif c["tipo_bio"]:
            mode = "bio"
        else:
            mode = "nao_bio"
        return {"hab_ts": hab_ts, "mode": mode}

    for line in txt.splitlines():
        if not line.startswith(ELECTION_DAY):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        ts_full = parts[0]
        app = parts[3]
        msg = parts[4]
        if app != "VOTA":
            continue
        hhmmss = ts_full.split()[1]

        # --- encerramento ---
        if enc is None and (
            "encerramento" in msg.lower()
            or msg.startswith("Inicio do Encerramento")
            or msg == "Código de encerramento digitado"
        ):
            enc = hhmmss

        # --- biometria session tracking (skip mesário) ---
        if "mesário" in msg or "mesario" in msg.lower():
            pass
        elif msg.startswith("Solicita digital. Tentativa"):
            if cur["start"] is None:
                cur["start"] = hhmmss
        elif "Tipo de habilitação do eleitor [biométrica]" in msg:
            cur["tipo_bio"] = True
        elif "Solicitação de dado pessoal do eleitor para habilitação manual" in msg:
            cur["manual"] = True
        elif "Ano de nascimento digitado é igual ao do cadastro" in msg:
            cur["nascimento"] = True
        elif "Habilitação cancelada" in msg:
            cur = new_cur()
        elif msg == "Eleitor foi habilitado":
            sessions.append(finalize(hhmmss, cur))
            cur = new_cur()
        elif msg == "O voto do eleitor foi computado":
            hh = int(hhmmss[:2])
            n_votos += 1
            if first_ts is None:
                first_ts = hhmmss
            last_ts = hhmmss
            keyh = f"{hh:02d}"
            hours[keyh] = hours.get(keyh, 0) + 1
            if hh >= 16:
                after16 += 1
            if hh >= 17:
                after17 += 1
            for s in reversed(sessions):
                if "voto_ts" not in s:
                    s["voto_ts"] = hhmmss
                    break

    n_hab = len(sessions)
    n_bio = sum(1 for s in sessions if s["mode"] == "bio")
    n_nao_bio = n_hab - n_bio
    voted = [s for s in sessions if "voto_ts" in s]

    def late_bio(hh_min):
        late = [s for s in voted if int(s["voto_ts"][:2]) >= hh_min]
        nb = sum(1 for s in late if s["mode"] == "bio")
        nn = len(late) - nb
        return nb, nn

    bio16, nao16 = late_bio(16)
    bio17, nao17 = late_bio(17)
    early = [s for s in voted if int(s["voto_ts"][:2]) < 16]
    early_nao = sum(1 for s in early if s["mode"] == "nao_bio")

    return {
        "n_votos_log": n_votos,
        "after16": after16,
        "after17": after17,
        "share_after16": round(after16 / n_votos, 4) if n_votos else None,
        "share_after17": round(after17 / n_votos, 4) if n_votos else None,
        "concentracao_16": round(after16 / n_votos, 4) if n_votos else None,
        "concentracao_17": round(after17 / n_votos, 4) if n_votos else None,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "enc_ts": enc,
        "hours": hours,
        "n_hab": n_hab,
        "n_bio": n_bio,
        "n_nao_bio": n_nao_bio,
        "share_bio": round(n_bio / n_hab, 4) if n_hab else None,
        "share_nao_bio": round(n_nao_bio / n_hab, 4) if n_hab else None,
        "bio_after16": bio16,
        "nao_bio_after16": nao16,
        "bio_after17": bio17,
        "nao_bio_after17": nao17,
        "early_n": len(early),
        "early_nao_bio": early_nao,
    }


def process_one(sec: dict) -> dict:
    uf = sec["uf"]
    mun5 = sec["mun5"]
    zona4 = sec["zona4"]
    secao4 = sec["secao4"]
    key = sec["key"]

    aux_url = (
        f"{BASE}/arquivo-urna/{PLEITO}/dados/{uf}/{mun5}/{zona4}/{secao4}/"
        f"p{P}-{uf}-m{mun5}-z{zona4}-s{secao4}-aux.json"
    )
    try:
        aux = json.loads(http_get(aux_url).decode("utf-8"))
    except Exception as e:
        return {"key": key, "uf": uf.upper(), "erro": f"aux:{e}"}

    hashes = aux.get("hashes") or []
    if not hashes:
        return {"key": key, "uf": uf.upper(), "erro": f"no_hashes st={aux.get('st')}"}
    h = hashes[0]
    hsh = h["hash"]
    log_nm = None
    for a in h.get("arq") or []:
        if a.get("tp") in ("log", "logsa"):
            log_nm = a["nm"]
            break
    if not log_nm:
        return {"key": key, "uf": uf.upper(), "erro": "no_log_in_aux"}

    log_url = (
        f"{BASE}/arquivo-urna/{PLEITO}/dados/{uf}/{mun5}/{zona4}/{secao4}/"
        f"{hsh}/{log_nm}"
    )
    try:
        blob = http_get(log_url)
    except Exception as e:
        return {"key": key, "uf": uf.upper(), "erro": f"log:{e}"}

    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as z:
            name = z.namelist()[0]
            txt = z.read(name).decode("latin-1")
    except Exception as e:
        return {"key": key, "uf": uf.upper(), "erro": f"unzip:{e}"}

    m = parse_log(txt)
    row = {
        "key": key,
        "uf": uf.upper(),
        "cd_mun": mun5,
        "mun5": mun5,
        "nm_mun": sec.get("nm_mun"),
        "zona": int(zona4),
        "secao": int(secao4),
        "lula_share": sec.get("lula_share"),
        "flavio_share": sec.get("flavio_share"),
        "log_bytes": len(blob),
        **m,
    }
    return row


def load_done_keys() -> set[str]:
    done = set()
    for uf in UFS:
        path = OUT / f"{uf}.jsonl"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if obj.get("key") and "erro" not in obj:
                    done.add(obj["key"])
    # also skip keys that permanently failed? keep retrying fails — only track in errors
    return done


def append_jsonl(uf: str, row: dict):
    path = OUT / f"{uf.lower()}.jsonl"
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    with _io_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def append_error(row: dict):
    path = OUT / "errors.jsonl"
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    with _io_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)


def write_progress(extra: dict | None = None):
    now = time.time()
    with _stats_lock:
        s = dict(stats)
    started = s.get("started_at") or now
    elapsed = max(0.001, now - started)
    done = s["ok"] + s["fail"]
    remaining = max(0, s["total"] - s["done_keys"] - done)
    rate = done / elapsed
    eta = remaining / rate if rate > 0 else None
    prog = {
        "ok": s["ok"],
        "fail": s["fail"],
        "skip": s["skip"],
        "bytes": s["bytes"],
        "bytes_mb": round(s["bytes"] / 1e6, 1),
        "total": s["total"],
        "done_keys_at_start": s["done_keys"],
        "processed_this_run": done,
        "completed": s["done_keys"] + s["ok"],  # successful rows on disk+this run
        "remaining_est": remaining,
        "rate_per_sec": round(rate, 3),
        "eta_sec": round(eta) if eta is not None else None,
        "eta_min": round(eta / 60, 1) if eta is not None else None,
        "elapsed_sec": round(elapsed, 1),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "workers": WORKERS,
        "target_rps": TARGET_RPS,
        "status": "running",
    }
    if extra:
        prog.update(extra)
    with _io_lock:
        (OUT / "progress.json").write_text(
            json.dumps(prog, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def pearson(xs, ys):
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return round(num / den, 4) if den else None


def summ(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"n": 0}
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


def build_summary():
    """Read JSONL shards and write analise_tarde_BA_CE.json."""
    rows = []
    for uf in UFS:
        path = OUT / f"{uf}.jsonl"
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "erro" in obj:
                    continue
                if (obj.get("n_votos_log") or 0) <= 0:
                    continue
                rows.append(obj)

    # dedupe by key (keep last)
    by_key = {}
    for r in rows:
        by_key[r["key"]] = r
    rows = list(by_key.values())

    def subset(uf=None):
        return [r for r in rows if uf is None or r["uf"] == uf]

    def pack(sub):
        c16 = [r["concentracao_16"] for r in sub if r.get("concentracao_16") is not None]
        c17 = [r["concentracao_17"] for r in sub if r.get("concentracao_17") is not None]
        with_lula = [
            r for r in sub
            if r.get("concentracao_16") is not None and r.get("lula_share") is not None
        ]
        with_flavio = [
            r for r in sub
            if r.get("concentracao_16") is not None and r.get("flavio_share") is not None
        ]
        tot_hab = sum(r.get("n_hab") or 0 for r in sub)
        tot_bio = sum(r.get("n_bio") or 0 for r in sub)
        tot_nao = sum(r.get("n_nao_bio") or 0 for r in sub)
        tot16_bio = sum(r.get("bio_after16") or 0 for r in sub)
        tot16_nao = sum(r.get("nao_bio_after16") or 0 for r in sub)
        tot17_bio = sum(r.get("bio_after17") or 0 for r in sub)
        tot17_nao = sum(r.get("nao_bio_after17") or 0 for r in sub)
        tot_early = sum(r.get("early_n") or 0 for r in sub)
        tot_early_nao = sum(r.get("early_nao_bio") or 0 for r in sub)
        pooled_early_nao = round(tot_early_nao / tot_early, 4) if tot_early else None
        pooled_late16_nao = (
            round(tot16_nao / (tot16_bio + tot16_nao), 4) if (tot16_bio + tot16_nao) else None
        )
        enrichment = None
        if pooled_early_nao and pooled_late16_nao and pooled_early_nao > 0:
            enrichment = round(pooled_late16_nao / pooled_early_nao, 3)

        hours = Counter()
        for r in sub:
            for h, c in (r.get("hours") or {}).items():
                hours[h] += c
        total_v = sum(hours.values())

        # top late municipalities (mean c16, min 5 sections)
        by_mun = defaultdict(list)
        for r in sub:
            if r.get("concentracao_16") is not None:
                by_mun[(r["uf"], r.get("nm_mun") or r.get("mun5"))].append(r["concentracao_16"])
        mun_rank = []
        for (uf, nm), vals in by_mun.items():
            if len(vals) < 5:
                continue
            mun_rank.append({
                "uf": uf,
                "nm_mun": nm,
                "n_secoes": len(vals),
                "mean_c16": round(st.mean(vals), 4),
                "median_c16": round(st.median(vals), 4),
                "max_c16": round(max(vals), 4),
            })
        mun_rank.sort(key=lambda x: x["mean_c16"], reverse=True)

        return {
            "n_secoes": len(sub),
            "n_votos_log": sum(r.get("n_votos_log") or 0 for r in sub),
            "concentracao_16": summ(c16),
            "concentracao_17": summ(c17),
            "flags": {
                "c16_ge_20pct": sum(1 for v in c16 if v >= 0.20),
                "c16_ge_30pct": sum(1 for v in c16 if v >= 0.30),
                "c17_ge_10pct": sum(1 for v in c17 if v >= 0.10),
                "c17_ge_20pct": sum(1 for v in c17 if v >= 0.20),
                "last_after_18h": sum(
                    1 for r in sub if r.get("last_ts") and r["last_ts"] >= "18:00:00"
                ),
                "last_after_19h": sum(
                    1 for r in sub if r.get("last_ts") and r["last_ts"] >= "19:00:00"
                ),
            },
            "corr_c16_lula": pearson(
                (r["concentracao_16"] for r in with_lula),
                (r["lula_share"] for r in with_lula),
            ),
            "corr_c16_flavio": pearson(
                (r["concentracao_16"] for r in with_flavio),
                (r["flavio_share"] for r in with_flavio),
            ),
            "n_for_corr_lula": len(with_lula),
            "n_for_corr_flavio": len(with_flavio),
            "biometria": {
                "n_hab": tot_hab,
                "n_bio": tot_bio,
                "n_nao_bio": tot_nao,
                "share_bio": round(tot_bio / tot_hab, 4) if tot_hab else None,
                "share_nao_bio": round(tot_nao / tot_hab, 4) if tot_hab else None,
                "after16": {
                    "n_bio": tot16_bio,
                    "n_nao_bio": tot16_nao,
                    "share_nao_bio": pooled_late16_nao,
                },
                "after17": {
                    "n_bio": tot17_bio,
                    "n_nao_bio": tot17_nao,
                    "share_nao_bio": (
                        round(tot17_nao / (tot17_bio + tot17_nao), 4)
                        if (tot17_bio + tot17_nao)
                        else None
                    ),
                },
                "early_before16": {
                    "n": tot_early,
                    "n_nao_bio": tot_early_nao,
                    "share_nao_bio": pooled_early_nao,
                },
                "late_vs_early_enrichment_nao_bio": enrichment,
            },
            "pooled_hour_share": {
                h: round(hours[h] / total_v, 4) for h in sorted(hours)
            } if total_v else {},
            "pooled_n_votos": total_v,
            "top20_late_municipios": mun_rank[:20],
            "top20_late_secoes": [
                {
                    "key": r["key"],
                    "uf": r["uf"],
                    "nm_mun": r.get("nm_mun"),
                    "zona": r["zona"],
                    "secao": r["secao"],
                    "n_votos_log": r["n_votos_log"],
                    "concentracao_16": r.get("concentracao_16"),
                    "concentracao_17": r.get("concentracao_17"),
                    "first_ts": r.get("first_ts"),
                    "last_ts": r.get("last_ts"),
                    "enc_ts": r.get("enc_ts"),
                    "lula_share": r.get("lula_share"),
                    "flavio_share": r.get("flavio_share"),
                    "share_bio": r.get("share_bio"),
                    "hours": r.get("hours"),
                }
                for r in sorted(
                    sub,
                    key=lambda r: (r.get("concentracao_17") or 0, r.get("concentracao_16") or 0),
                    reverse=True,
                )[:20]
            ],
        }

    overall = pack(rows)
    by_uf = {uf.upper(): pack(subset(uf.upper())) for uf in UFS}

    # error count
    n_err = 0
    err_path = OUT / "errors.jsonl"
    if err_path.exists():
        with open(err_path, encoding="utf-8") as f:
            n_err = sum(1 for line in f if line.strip())

    out = {
        "election_day": ELECTION_DAY,
        "scope": "BA+CE all sections with ha/da in cs.json",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "n_ok": len(rows),
        "n_errors_logged": n_err,
        "overall": overall,
        "by_uf": by_uf,
        "method": {
            "concentracao_16": "votos com hora >= 16:00 / n_votos_log (dia 04/10/2026)",
            "bio": "Tipo de habilitação do eleitor [biométrica] e sem caminho manual",
            "nao_bio": "manual OU nascimento OU habilitado sem tipo biométrica",
            "shares": "lula_share/flavio_share joined from discrepancia_BA_CE_secoes.csv (BU)",
        },
        "paths": {
            "ba_jsonl": str(OUT / "ba.jsonl"),
            "ce_jsonl": str(OUT / "ce.jsonl"),
            "errors": str(OUT / "errors.jsonl"),
            "progress": str(OUT / "progress.json"),
        },
    }
    out_path = SAMPLE / "analise_tarde_BA_CE.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY wrote", out_path, "n_ok", len(rows), flush=True)
    return out


def main():
    print("Loading shares CSV...", flush=True)
    shares = load_shares()
    print(f"  shares keys: {len(shares)}", flush=True)
    print("Enumerating sections from cs.json...", flush=True)
    sections = enumerate_sections(shares)
    print(f"  sections with ha/da: {len(sections)}", flush=True)
    for uf in UFS:
        n = sum(1 for s in sections if s["uf"] == uf)
        print(f"    {uf.upper()}: {n}", flush=True)

    done = load_done_keys()
    print(f"  already done (resume): {len(done)}", flush=True)
    todo = [s for s in sections if s["key"] not in done]
    print(f"  todo: {len(todo)}", flush=True)

    stats["total"] = len(sections)
    stats["done_keys"] = len(done)
    stats["skip"] = len(done)
    stats["started_at"] = time.time()
    write_progress({"phase": "download"})

    if not todo:
        print("Nothing to download — building summary.", flush=True)
        summary = build_summary()
        write_progress({"status": "done", "phase": "summary"})
        print(json.dumps({
            "ok": stats["ok"],
            "fail": stats["fail"],
            "bytes": stats["bytes"],
            "n_summary": summary["n_ok"],
            "corr_c16_lula": summary["overall"]["corr_c16_lula"],
        }, indent=2), flush=True)
        return

    t0 = time.time()
    processed = 0

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(process_one, sec): sec for sec in todo}
        for fut in as_completed(futs):
            sec = futs[fut]
            try:
                row = fut.result()
            except Exception as e:
                row = {"key": sec["key"], "uf": sec["uf"].upper(), "erro": f"exc:{e}"}

            if "erro" in row:
                append_error(row)
                with _stats_lock:
                    stats["fail"] += 1
                ok = False
            else:
                append_jsonl(sec["uf"], row)
                with _stats_lock:
                    stats["ok"] += 1
                ok = True

            processed += 1
            if processed % PRINT_EVERY == 0 or processed == len(todo):
                with _stats_lock:
                    ok_n, fail_n, nbytes = stats["ok"], stats["fail"], stats["bytes"]
                elapsed = time.time() - t0
                rate = processed / max(0.001, elapsed)
                rem = len(todo) - processed
                eta = rem / rate if rate > 0 else 0
                print(
                    f"[{processed}/{len(todo)}] ok={ok_n} fail={fail_n} "
                    f"MB={nbytes/1e6:.1f} rate={rate:.2f}/s ETA={eta/60:.1f}min "
                    f"last={'OK' if ok else 'FAIL'} {row.get('key')}",
                    flush=True,
                )
            if processed % PROGRESS_EVERY == 0 or processed == len(todo):
                write_progress({"phase": "download"})

    elapsed = time.time() - t0
    print(
        f"DOWNLOAD DONE ok={stats['ok']} fail={stats['fail']} "
        f"bytes={stats['bytes']} ({stats['bytes']/1e6:.1f} MB) "
        f"duration={elapsed:.1f}s ({elapsed/60:.1f} min)",
        flush=True,
    )

    print("Building summary...", flush=True)
    summary = build_summary()
    write_progress({
        "status": "done",
        "phase": "summary",
        "duration_sec": round(elapsed, 1),
        "n_summary": summary["n_ok"],
        "corr_c16_lula_overall": summary["overall"]["corr_c16_lula"],
        "corr_c16_flavio_overall": summary["overall"]["corr_c16_flavio"],
        "median_c16_BA": summary["by_uf"]["BA"]["concentracao_16"].get("median"),
        "median_c16_CE": summary["by_uf"]["CE"]["concentracao_16"].get("median"),
        "bio_enrichment": summary["overall"]["biometria"].get("late_vs_early_enrichment_nao_bio"),
    })
    print("=== FINAL ===", flush=True)
    print(json.dumps({
        "ok": stats["ok"],
        "fail": stats["fail"],
        "skip_resume": stats["skip"],
        "bytes": stats["bytes"],
        "duration_sec": round(elapsed, 1),
        "n_summary": summary["n_ok"],
        "overall_median_c16": summary["overall"]["concentracao_16"].get("median"),
        "overall_mean_c16": summary["overall"]["concentracao_16"].get("mean"),
        "corr_c16_lula": summary["overall"]["corr_c16_lula"],
        "corr_c16_flavio": summary["overall"]["corr_c16_flavio"],
        "bio_enrichment": summary["overall"]["biometria"].get("late_vs_early_enrichment_nao_bio"),
        "BA_median_c16": summary["by_uf"]["BA"]["concentracao_16"].get("median"),
        "CE_median_c16": summary["by_uf"]["CE"]["concentracao_16"].get("median"),
    }, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
