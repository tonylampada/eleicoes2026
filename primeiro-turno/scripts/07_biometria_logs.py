#!/usr/bin/env python3
"""Parse habilitação biométrica vs manual from per-section log.jez (sample n≈100).

Stream-downloads each log, parses in memory, does NOT keep raw .jez on disk.
Budget: keep under ~200MB download.
"""
from __future__ import annotations

import csv
import io
import json
import math
import statistics as st
import time
import zipfile
import os
from collections import Counter
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://resultados.tse.jus.br/oficial/ele2026"
PLEITO = "3220"
P = "003220"
# Resolve project layout relative to this script (default) or via env var.
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = Path(os.getenv("ELEICOES2026_ROOT", SCRIPT_DIR.parent))  # points to primeiro-turno/
DATA_DIR = ROOT / "data"
SAMPLE_DIR = DATA_DIR / "sample"
DERIVED_DIR = DATA_DIR / "derived"
SAMPLE = SAMPLE_DIR
BUDGET = 200_000_000
ELECTION_DAY = "04/10/2026"

downloaded = 0
stats = {"ok": 0, "fail": 0, "bytes": 0, "errors": []}


def get(url, retries=3):
    global downloaded
    last = None
    for i in range(retries):
        try:
            req = Request(
                url,
                headers={
                    "Referer": "https://resultados.tse.jus.br/oficial/app/index.html",
                    "User-Agent": "GrokBot-eleicoes26-audit/1.0",
                },
            )
            with urlopen(req, timeout=90) as r:
                data = r.read()
            downloaded += len(data)
            stats["bytes"] += len(data)
            time.sleep(0.05)
            return data
        except HTTPError as e:
            if e.code == 404:
                raise
            last = e
            time.sleep(1 + i)
        except Exception as e:
            last = e
            time.sleep(1 + i)
    raise last


def pearson(xs, ys):
    xs, ys = list(xs), list(ys)
    n = len(xs)
    if n < 3:
        return None
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = (sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys)) ** 0.5
    return round(num / den, 4) if den else None


def parse_sessions(txt: str):
    """Segment voter sessions ending at 'Eleitor foi habilitado'.

    Classification (privacy-preserving — mode only, no voter/vote ID):
      bio     — Tipo de habilitação [biométrica] and NOT on manual path
      nao_bio — manual solicitação OR nascimento OR habilitado without tipo biométrica
    """
    sessions = []
    cur = {
        "tipo_bio": False,
        "manual": False,
        "nascimento": False,
        "dig_attempts": 0,
        "start": None,
    }

    def new_cur():
        return {
            "tipo_bio": False,
            "manual": False,
            "nascimento": False,
            "dig_attempts": 0,
            "start": None,
        }

    def finalize(hab_ts, c):
        if c["manual"] or c["nascimento"]:
            mode = "nao_bio"
        elif c["tipo_bio"]:
            mode = "bio"
        else:
            mode = "nao_bio"
        return {
            "hab_ts": hab_ts,
            "mode": mode,
            "tipo_bio": c["tipo_bio"],
            "manual": c["manual"],
            "nascimento": c["nascimento"],
            "dig_attempts": c["dig_attempts"],
        }

    for line in txt.splitlines():
        if not line.startswith(ELECTION_DAY):
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            continue
        if parts[3] != "VOTA":
            continue
        ts = parts[0].split()[1]
        msg = parts[4]
        # mesário biometrics are unrelated to voter habilitação
        if "mesário" in msg or "mesario" in msg.lower():
            continue

        if msg.startswith("Solicita digital. Tentativa"):
            if cur["start"] is None:
                cur["start"] = ts
            try:
                n = int(msg.split("[")[1].split("]")[0])
                cur["dig_attempts"] = max(cur["dig_attempts"], n)
            except (IndexError, ValueError):
                pass
        elif "Tipo de habilitação do eleitor [biométrica]" in msg:
            cur["tipo_bio"] = True
        elif "Solicitação de dado pessoal do eleitor para habilitação manual" in msg:
            cur["manual"] = True
        elif "Ano de nascimento digitado é igual ao do cadastro" in msg:
            cur["nascimento"] = True
        elif "Habilitação cancelada" in msg:
            cur = new_cur()
        elif msg == "Eleitor foi habilitado":
            sessions.append(finalize(ts, cur))
            cur = new_cur()
        elif msg == "O voto do eleitor foi computado":
            for s in reversed(sessions):
                if "voto_ts" not in s:
                    s["voto_ts"] = ts
                    break

    return sessions


def hours_hist(sessions, mode_filter=None):
    hours = {f"{h:02d}": 0 for h in range(6, 20)}
    for s in sessions:
        ts = s.get("voto_ts") or s.get("hab_ts")
        if not ts:
            continue
        if mode_filter is not None and s["mode"] != mode_filter:
            continue
        hh = int(ts[:2])
        key = f"{hh:02d}"
        hours[key] = hours.get(key, 0) + 1
    return hours


def metrics_from_sessions(sessions):
    n_hab = len(sessions)
    voted = [s for s in sessions if "voto_ts" in s]
    n_voto = len(voted)
    n_bio = sum(1 for s in sessions if s["mode"] == "bio")
    n_nao_bio = sum(1 for s in sessions if s["mode"] == "nao_bio")
    n_manual = sum(1 for s in sessions if s["manual"])
    n_nascimento = sum(1 for s in sessions if s["nascimento"])
    n_tipo_bio = sum(1 for s in sessions if s["tipo_bio"])

    def late_counts(hh_min):
        late = [s for s in voted if int(s["voto_ts"][:2]) >= hh_min]
        nb = sum(1 for s in late if s["mode"] == "bio")
        nn = sum(1 for s in late if s["mode"] == "nao_bio")
        return {
            "n": len(late),
            "n_bio": nb,
            "n_nao_bio": nn,
            "share_nao_bio": round(nn / len(late), 4) if late else None,
            "share_bio": round(nb / len(late), 4) if late else None,
        }

    after16 = late_counts(16)
    after17 = late_counts(17)
    early = [s for s in voted if int(s["voto_ts"][:2]) < 16]
    early_nao = sum(1 for s in early if s["mode"] == "nao_bio")
    early_share_nao = round(early_nao / len(early), 4) if early else None

    return {
        "n_hab": n_hab,
        "n_voto": n_voto,
        "n_bio": n_bio,
        "n_nao_bio": n_nao_bio,
        "n_tipo_bio": n_tipo_bio,
        "n_manual": n_manual,
        "n_nascimento": n_nascimento,
        "share_bio": round(n_bio / n_hab, 4) if n_hab else None,
        "share_nao_bio": round(n_nao_bio / n_hab, 4) if n_hab else None,
        "after16": after16,
        "after17": after17,
        "early_before16": {
            "n": len(early),
            "n_nao_bio": early_nao,
            "share_nao_bio": early_share_nao,
        },
        "hours": hours_hist(sessions),
        "hours_bio": hours_hist(sessions, "bio"),
        "hours_nao_bio": hours_hist(sessions, "nao_bio"),
    }


def resolve_log_url(uf, mun5, zona, secao, known=None):
    uf = uf.lower()
    zona4 = f"{int(zona):04d}"
    secao4 = f"{int(secao):04d}"
    key = f"{uf}_{mun5}_{zona4}_{secao4}"

    if known and known.get("hash") and known.get("log_nm"):
        hsh, log_nm = known["hash"], known["log_nm"]
        log_url = (
            f"{BASE}/arquivo-urna/{PLEITO}/dados/{uf}/{mun5}/{zona4}/{secao4}/"
            f"{hsh}/{log_nm}"
        )
        return key, log_url, hsh, log_nm

    aux_url = (
        f"{BASE}/arquivo-urna/{PLEITO}/dados/{uf}/{mun5}/{zona4}/{secao4}/"
        f"p{P}-{uf}-m{mun5}-z{zona4}-s{secao4}-aux.json"
    )
    aux = json.loads(get(aux_url).decode("utf-8"))
    hashes = aux.get("hashes") or []
    if not hashes:
        raise RuntimeError(f"no_hashes st={aux.get('st')}")
    h = hashes[0]
    hsh = h["hash"]
    log_nm = None
    for a in h.get("arq") or []:
        if a.get("tp") in ("log", "logsa"):
            log_nm = a["nm"]
            break
    if not log_nm:
        raise RuntimeError("no_log_in_aux")
    log_url = (
        f"{BASE}/arquivo-urna/{PLEITO}/dados/{uf}/{mun5}/{zona4}/{secao4}/"
        f"{hsh}/{log_nm}"
    )
    return key, log_url, hsh, log_nm


def process_section(row, known=None):
    uf = row["uf"]
    mun5 = row["cd_mun5"]
    zona = row["zona"]
    secao = row["secao"]
    key, log_url, hsh, log_nm = resolve_log_url(uf, mun5, zona, secao, known=known)

    if downloaded > BUDGET:
        return {"key": key, "erro": "budget"}

    try:
        blob = get(log_url)
    except Exception as e:
        # fallback: re-resolve via aux if cached hash failed
        if known and known.get("hash"):
            key, log_url, hsh, log_nm = resolve_log_url(uf, mun5, zona, secao, known=None)
            blob = get(log_url)
        else:
            raise

    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        name = z.namelist()[0]
        txt = z.read(name).decode("latin-1")

    sessions = parse_sessions(txt)
    m = metrics_from_sessions(sessions)
    out = {
        "key": key,
        "uf": uf.upper(),
        "mun5": mun5,
        "zona": int(zona),
        "secao": int(secao),
        "nm_mun": row.get("nm_mun"),
        "estrato": row.get("estrato"),
        "lula_share": float(row["lula_share"]) if row.get("lula_share") not in (None, "") else None,
        "valid_csv": int(row["valid"]) if row.get("valid") not in (None, "") else None,
        "log_bytes": len(blob),
        "hash": hsh,
        "log_nm": log_nm,
        **m,
    }
    # convenience flat fields for site
    out["nao_bio_after16"] = m["after16"]["n_nao_bio"]
    out["bio_after16"] = m["after16"]["n_bio"]
    out["share_nao_bio_after16"] = m["after16"]["share_nao_bio"]
    out["nao_bio_after17"] = m["after17"]["n_nao_bio"]
    out["bio_after17"] = m["after17"]["n_bio"]
    out["share_nao_bio_after17"] = m["after17"]["share_nao_bio"]
    return out


def main():
    rows = list(csv.DictReader(open(SAMPLE / "amostra100.csv", encoding="utf-8")))
    known_by_key = {}
    agg_path = SAMPLE / "log_aggregates.json"
    if agg_path.exists():
        agg = json.loads(agg_path.read_text(encoding="utf-8"))
        for r in agg.get("results") or []:
            if r.get("key") and r.get("hash"):
                known_by_key[r["key"]] = r

    results = []
    for i, row in enumerate(rows):
        uf = row["uf"].lower()
        mun5 = row["cd_mun5"]
        zona4 = f"{int(row['zona']):04d}"
        secao4 = f"{int(row['secao']):04d}"
        key = f"{uf}_{mun5}_{zona4}_{secao4}"
        known = known_by_key.get(key)
        try:
            if downloaded > BUDGET:
                out = {"key": key, "erro": "budget"}
            else:
                out = process_section(row, known=known)
            if "erro" in out:
                stats["fail"] += 1
                stats["errors"].append(out)
                print(f"[{i+1}/{len(rows)}] FAIL {out['key']}: {out['erro']}", flush=True)
            else:
                stats["ok"] += 1
                print(
                    f"[{i+1}/{len(rows)}] OK {out['key']} hab={out['n_hab']} "
                    f"bio={out['n_bio']} nao={out['n_nao_bio']} "
                    f"share_bio={out['share_bio']} late16_nao={out['share_nao_bio_after16']}",
                    flush=True,
                )
            results.append(out)
        except Exception as e:
            stats["fail"] += 1
            err = {"key": key, "erro": str(e)}
            stats["errors"].append(err)
            results.append(err)
            print(f"[{i+1}/{len(rows)}] FAIL {key}: {e}", flush=True)

        if downloaded > BUDGET:
            print("BUDGET hit", downloaded, flush=True)
            break

    ok = [r for r in results if "erro" not in r and (r.get("n_hab") or 0) > 0]

    # pooled overall
    tot_hab = sum(r["n_hab"] for r in ok)
    tot_bio = sum(r["n_bio"] for r in ok)
    tot_nao = sum(r["n_nao_bio"] for r in ok)
    tot_voto = sum(r["n_voto"] for r in ok)
    tot16_bio = sum(r["bio_after16"] for r in ok)
    tot16_nao = sum(r["nao_bio_after16"] for r in ok)
    tot17_bio = sum(r["bio_after17"] for r in ok)
    tot17_nao = sum(r["nao_bio_after17"] for r in ok)
    tot_early = sum(r["early_before16"]["n"] for r in ok)
    tot_early_nao = sum(r["early_before16"]["n_nao_bio"] for r in ok)

    hours_bio = Counter()
    hours_nao = Counter()
    hours_all = Counter()
    for r in ok:
        for h, c in (r.get("hours_bio") or {}).items():
            hours_bio[h] += c
        for h, c in (r.get("hours_nao_bio") or {}).items():
            hours_nao[h] += c
        for h, c in (r.get("hours") or {}).items():
            hours_all[h] += c

    # join concentracao_16 from aggregates
    conc_by_key = {}
    if agg_path.exists():
        for r in agg.get("results") or []:
            if r.get("key") and r.get("share_after16") is not None:
                conc_by_key[r["key"]] = {
                    "concentracao_16": r["share_after16"],
                    "concentracao_17": r.get("share_after17"),
                    "n_votos_log": r.get("n_votos_log"),
                }
    for r in ok:
        extra = conc_by_key.get(r["key"], {})
        r["concentracao_16"] = extra.get("concentracao_16")
        r["concentracao_17"] = extra.get("concentracao_17")

    # correlations (section-level shares)
    with_conc = [r for r in ok if r.get("concentracao_16") is not None and r.get("share_nao_bio") is not None]
    with_lula = [r for r in ok if r.get("lula_share") is not None and r.get("share_nao_bio") is not None]
    with_late = [r for r in ok if r.get("share_nao_bio_after16") is not None and r.get("concentracao_16") is not None]

    corr = {
        "share_nao_bio_vs_concentracao_16": pearson(
            (r["share_nao_bio"] for r in with_conc),
            (r["concentracao_16"] for r in with_conc),
        ),
        "share_nao_bio_vs_lula_share": pearson(
            (r["share_nao_bio"] for r in with_lula),
            (r["lula_share"] for r in with_lula),
        ),
        "share_nao_bio_after16_vs_concentracao_16": pearson(
            (r["share_nao_bio_after16"] for r in with_late),
            (r["concentracao_16"] for r in with_late),
        ),
        "n_for_conc": len(with_conc),
        "n_for_lula": len(with_lula),
        "n_for_late": len(with_late),
    }

    # Is late concentration enriched in non-bio?
    # Compare pooled share_nao_bio early (<16) vs after16
    pooled_early_nao = round(tot_early_nao / tot_early, 4) if tot_early else None
    pooled_late16_nao = round(tot16_nao / (tot16_bio + tot16_nao), 4) if (tot16_bio + tot16_nao) else None
    pooled_late17_nao = round(tot17_nao / (tot17_bio + tot17_nao), 4) if (tot17_bio + tot17_nao) else None
    enrichment = None
    if pooled_early_nao is not None and pooled_late16_nao is not None and pooled_early_nao > 0:
        enrichment = round(pooled_late16_nao / pooled_early_nao, 3)

    # extreme example (Tremedal preferred if present)
    trem = next((r for r in ok if r["key"] == "ba_39357_0177_0008"), None)
    extreme = trem or max(ok, key=lambda r: r.get("concentracao_16") or 0)

    overall = {
        "n_sections": len(ok),
        "n_hab": tot_hab,
        "n_voto": tot_voto,
        "n_bio": tot_bio,
        "n_nao_bio": tot_nao,
        "share_bio": round(tot_bio / tot_hab, 4) if tot_hab else None,
        "share_nao_bio": round(tot_nao / tot_hab, 4) if tot_hab else None,
        "after16": {
            "n_bio": tot16_bio,
            "n_nao_bio": tot16_nao,
            "n": tot16_bio + tot16_nao,
            "share_nao_bio": pooled_late16_nao,
            "share_bio": round(tot16_bio / (tot16_bio + tot16_nao), 4) if (tot16_bio + tot16_nao) else None,
        },
        "after17": {
            "n_bio": tot17_bio,
            "n_nao_bio": tot17_nao,
            "n": tot17_bio + tot17_nao,
            "share_nao_bio": pooled_late17_nao,
            "share_bio": round(tot17_bio / (tot17_bio + tot17_nao), 4) if (tot17_bio + tot17_nao) else None,
        },
        "early_before16": {
            "n": tot_early,
            "n_nao_bio": tot_early_nao,
            "share_nao_bio": pooled_early_nao,
        },
        "late_vs_early_enrichment_nao_bio": enrichment,
        "note_enrichment": (
            "Razão (share_nao_bio após 16h) / (share_nao_bio antes das 16h) no pool da amostra. "
            "≈1 = sem enriquecimento; >1 = tarde um pouco mais não-bio."
        ),
        "hours_bio": {h: hours_bio[h] for h in sorted(hours_bio)},
        "hours_nao_bio": {h: hours_nao[h] for h in sorted(hours_nao)},
        "hours": {h: hours_all[h] for h in sorted(hours_all)},
        "section_share_nao_bio": {
            "mean": round(st.mean(r["share_nao_bio"] for r in ok), 4),
            "median": round(st.median(r["share_nao_bio"] for r in ok), 4),
            "min": round(min(r["share_nao_bio"] for r in ok), 4),
            "max": round(max(r["share_nao_bio"] for r in ok), 4),
        },
    }

    out = {
        "stats": stats,
        "method": {
            "election_day": ELECTION_DAY,
            "bio": "Tipo de habilitação do eleitor [biométrica] e sem caminho manual",
            "nao_bio": (
                "Solicitação de dado pessoal… habilitação manual "
                "OU Ano de nascimento digitado… "
                "OU habilitado sem tipo biométrica"
            ),
            "privacy": "Log não identifica o eleitor nem a escolha de voto — só o modo de habilitação.",
            "attempts": "Até 4 tentativas de digital; fallback manual/nascimento.",
        },
        "overall": overall,
        "correlation": corr,
        "extreme_example": {
            "key": extreme["key"],
            "uf": extreme["uf"],
            "nm_mun": extreme["nm_mun"],
            "zona": extreme["zona"],
            "secao": extreme["secao"],
            "n_hab": extreme["n_hab"],
            "n_bio": extreme["n_bio"],
            "n_nao_bio": extreme["n_nao_bio"],
            "share_bio": extreme["share_bio"],
            "share_nao_bio": extreme["share_nao_bio"],
            "concentracao_16": extreme.get("concentracao_16"),
            "concentracao_17": extreme.get("concentracao_17"),
            "after16": extreme["after16"],
            "after17": extreme["after17"],
            "early_before16": extreme["early_before16"],
            "hours_bio": extreme["hours_bio"],
            "hours_nao_bio": extreme["hours_nao_bio"],
            "lula_share": extreme.get("lula_share"),
        },
        "results": results,
    }

    out_path = SAMPLE / "biometria_logs.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # lean merge into log_aggregates for site convenience
    lean_path = SAMPLE / "biometria_secoes_lean.json"
    lean = []
    for r in ok:
        lean.append({
            "key": r["key"],
            "uf": r["uf"],
            "nm_mun": r["nm_mun"],
            "zona": r["zona"],
            "secao": r["secao"],
            "n_hab": r["n_hab"],
            "n_voto": r["n_voto"],
            "n_bio": r["n_bio"],
            "n_nao_bio": r["n_nao_bio"],
            "share_bio": r["share_bio"],
            "share_nao_bio": r["share_nao_bio"],
            "bio_after16": r["bio_after16"],
            "nao_bio_after16": r["nao_bio_after16"],
            "share_nao_bio_after16": r["share_nao_bio_after16"],
            "bio_after17": r["bio_after17"],
            "nao_bio_after17": r["nao_bio_after17"],
            "share_nao_bio_after17": r["share_nao_bio_after17"],
            "concentracao_16": r.get("concentracao_16"),
            "concentracao_17": r.get("concentracao_17"),
            "lula_share": r.get("lula_share"),
            "estrato": r.get("estrato"),
            "hours_bio": r["hours_bio"],
            "hours_nao_bio": r["hours_nao_bio"],
        })
    lean_path.write_text(json.dumps(lean, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    print("=== DONE ===", flush=True)
    print(json.dumps({
        "bytes": stats["bytes"],
        "ok": stats["ok"],
        "fail": stats["fail"],
        "overall_share_bio": overall["share_bio"],
        "overall_share_nao_bio": overall["share_nao_bio"],
        "late16_share_nao_bio": overall["after16"]["share_nao_bio"],
        "early_share_nao_bio": overall["early_before16"]["share_nao_bio"],
        "enrichment": enrichment,
        "corr": corr,
        "extreme": out["extreme_example"]["nm_mun"],
        "wrote": str(out_path),
        "lean": str(lean_path),
    }, indent=2, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
