#!/usr/bin/env python3
"""Baixa os boletins de urna (buweb) das Eleições 2026 do Portal de Dados Abertos do TSE.

- Descobre a lista de arquivos via API CKAN (package_show / package_search).
- Escolhe a versão mais recente (carimbo DDMMAAAAHHMM no nome) por turno/UF.
- Download retomável: grava em <arquivo>.part com `curl -C -` (HTTP Range).
- Verifica SHA-512 contra o .sha512 publicado pelo TSE; pula o que já está íntegro.
- Mantém um manifesto (data/manifest.json) com o estado de cada arquivo.

Uso: python3 scripts/download.py [--data DIR] [--turnos 1,2] [--ufs AC,SP] [--jobs 3]
Idempotente: pode ser executado quantas vezes quiser; retoma de onde parou.
"""
import argparse, concurrent.futures as cf, datetime as dt, hashlib, json, os, re, subprocess, sys, threading, urllib.request

CKAN = "https://dadosabertos.tse.jus.br/api/3/action"
DATASET = "resultados-2026-boletim-de-urna"
RX = re.compile(r"/bweb_(\d)t_([A-Z]{2})_(\d{12})\.zip(\.sha512)?$")
lock = threading.Lock()


def log(*a):
    with lock:
        print(dt.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def ckan_resources():
    urls = set()
    for ep in (f"{CKAN}/package_show?id={DATASET}",
               f"{CKAN}/package_search?q=name:{DATASET}&rows=5"):
        try:
            with urllib.request.urlopen(ep, timeout=60) as r:
                res = json.load(r)["result"]
            pkgs = res["results"] if "results" in res else [res]
            for p in pkgs:
                if p.get("name") == DATASET:
                    urls.update(x["url"] for x in p["resources"])
        except Exception as e:  # um endpoint pode estar com cache desatualizado
            log("aviso: falha em", ep, e)
    return urls


def pick_latest(urls):
    """Retorna {(turno, uf): {versao, zip_url, sha_url}} usando a versão mais recente.
    Se o CKAN só listar o .sha512 (aconteceu com RR 2t), deriva a URL do .zip."""
    best = {}
    for u in urls:
        m = RX.search(u)
        if not m:
            continue
        turno, uf, stamp, is_sha = m.groups()
        # carimbo DDMMAAAAHHMM -> AAAAMMDDHHMM para comparar
        key_ver = stamp[4:8] + stamp[2:4] + stamp[0:2] + stamp[8:]
        zip_url = u[:-7] if is_sha else u
        k = (int(turno), uf)
        cur = best.get(k)
        if cur is None or key_ver > cur["ordem"]:
            best[k] = {"turno": int(turno), "uf": uf, "versao": stamp, "ordem": key_ver,
                       "zip_url": zip_url, "sha_url": zip_url + ".sha512",
                       "arquivo": os.path.basename(zip_url)}
    return best


def sha512(path):
    h = hashlib.sha512()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(8 << 20), b""):
            h.update(b)
    return h.hexdigest()


def curl(url, dest, resume=True):
    cmd = ["curl", "-fsSL", "--retry", "8", "--retry-delay", "5", "--retry-all-errors",
           "--connect-timeout", "30", "-o", dest]
    if resume:
        cmd[1:1] = ["-C", "-"]
    return subprocess.run(cmd + [url]).returncode


def fetch(item, raw, manifest, save):
    name = item["arquivo"]
    zpath, spath = os.path.join(raw, name), os.path.join(raw, name + ".sha512")
    part = zpath + ".part"
    entry = manifest.setdefault(name, {})
    entry.update({k: item[k] for k in ("turno", "uf", "versao", "zip_url", "sha_url")})
    # 1) hash oficial (pequeno; sempre rebaixa se faltar)
    if not os.path.exists(spath) and curl(item["sha_url"], spath, resume=False) != 0:
        entry["estado"] = "erro_sha_download"; save(); return name, "erro_sha_download"
    expected = open(spath).read().split()[0].lower()
    entry["sha512_esperado"] = expected
    # 2) já íntegro?
    if os.path.exists(zpath):
        if entry.get("estado") == "ok" and entry.get("bytes") == os.path.getsize(zpath) \
                and entry.get("sha512") == expected:
            return name, "ok (já verificado)"
        if sha512(zpath) == expected:
            entry.update(estado="ok", bytes=os.path.getsize(zpath), sha512=expected)
            save(); return name, "ok (verificado)"
        os.replace(zpath, part)  # corrompido: tenta retomar/refazer via .part
    # 3) baixa / retoma
    for tentativa in range(3):
        entry["estado"] = "baixando"; save()
        rc = curl(item["zip_url"], part, resume=True)
        if rc == 0 and sha512(part) == expected:
            os.replace(part, zpath)
            entry.update(estado="ok", bytes=os.path.getsize(zpath), sha512=expected,
                         baixado_em=dt.datetime.now().astimezone().isoformat(timespec="seconds"))
            save(); return name, "ok (baixado)"
        log(f"{name}: tentativa {tentativa+1} falhou (rc={rc}); reiniciando do zero")
        if os.path.exists(part):
            os.remove(part)
    entry["estado"] = "erro"; save(); return name, "erro"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(__file__), "..", "data"))
    ap.add_argument("--turnos", default="1,2")
    ap.add_argument("--ufs", default="")
    ap.add_argument("--jobs", type=int, default=3)
    a = ap.parse_args()
    raw = os.path.join(a.data, "raw"); os.makedirs(raw, exist_ok=True)
    mpath = os.path.join(a.data, "manifest.json")
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}

    def save():
        with lock:
            tmp = mpath + ".tmp"
            json.dump(dict(sorted(manifest.items())), open(tmp, "w"), indent=1, ensure_ascii=False)
            os.replace(tmp, mpath)

    items = pick_latest(ckan_resources())
    turnos = {int(t) for t in a.turnos.split(",")}
    ufs = set(a.ufs.split(",")) if a.ufs else None
    todo = [v for k, v in sorted(items.items()) if k[0] in turnos and (ufs is None or k[1] in ufs)]
    log(f"{len(todo)} arquivos selecionados (turnos {sorted(turnos)})")
    for t in sorted(turnos):
        faltam = {uf for (tt, uf) in items if tt == 1} - {uf for (tt, uf) in items if tt == t}
        if faltam:
            log(f"aviso: turno {t} sem arquivo para: {sorted(faltam)}")
    # maiores primeiro para paralelizar melhor
    fails = 0
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for name, st in ex.map(lambda it: fetch(it, raw, manifest, save), todo):
            log(f"{name}: {st}")
            fails += st.startswith("erro")
    save()
    log(f"fim: {len(todo)-fails} ok, {fails} com erro. Manifesto: {mpath}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
