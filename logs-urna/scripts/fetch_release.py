#!/usr/bin/env python3
"""Baixa os agregados PRONTOS dos logs de urna de um GitHub Release (sem baixar nem reprocessar os zips do TSE).

  python3 scripts/fetch_release.py [--data data] [--tag logs-urna-2026-10-29] [--method auto|gh|url] [--so-parquet]

Assets do release:
  SHA256SUMS            hashes de todos os assets
  manifest.json         um registro por turno/UF processado (zip de origem, ETag, SHA-256, versão do parser, contagens)
  eventos_parquet.tar   parquet/eventos_secao/turno=<t>/uf=<UF>/data.parquet e parquet/eventos_tipo/...
  eventos.duckdb        as mesmas tabelas + eventos_dicionario + lotes (omitido com --so-parquet)

- Repo público: sem login. Usa `gh release download` se o gh estiver logado; senão baixa anônimo pela URL direta
  https://github.com/<repo>/releases/download/<tag>/<asset> com `curl -C -` (retomável).
- Confere SHA-256 de cada asset; arquivo corrompido é apagado e baixado de novo (até 3 vezes).
- Idempotente: o que já está íntegro é pulado. Rode de novo se algo for interrompido.
- Validação rápida no fim (se o módulo duckdb existir): linhas e votos por turno/UF nos Parquets e no DuckDB
  conferem com o manifest.json.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tarfile, time

REPO = "tonylampada/eleicoes2026"
TAG = "logs-urna-2026-10-29"   # ajuste ao publicar um release novo
TAR = "eventos_parquet.tar"
DB = "eventos.duckdb"


def log(*a):
    print("[fetch]", *a, flush=True)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def have_gh():
    return bool(shutil.which("gh")) and subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0


def curl_resume(url, dest):
    part = dest + ".part"
    if os.path.exists(dest):
        os.replace(dest, part)
    r = subprocess.run(["curl", "-fL", "--retry", "5", "--retry-delay", "3", "-C", "-", "-o", part, url])
    if r.returncode != 0 and not (r.returncode in (22, 33) and os.path.exists(part) and os.path.getsize(part) > 0):
        sys.exit(f"ERRO: curl falhou ({r.returncode}) em {url}")
    os.replace(part, dest)
    return dest


def download(name, d, a):
    dest = os.path.join(d, name)
    if a.method == "gh":
        if subprocess.run(["gh", "release", "download", a.tag, "-R", a.repo, "-p", name, "-D", d, "--skip-existing"]).returncode == 0:
            return dest
        log(f"gh falhou para {name}; tentando URL direta")
    return curl_resume(f"https://github.com/{a.repo}/releases/download/{a.tag}/{name}", dest)


def verified(name, d, exp, a):
    for i in range(1, 4):
        p = download(name, d, a)
        if sha256(p) == exp[name]:
            log(f"{name}: SHA-256 OK ({os.path.getsize(p):,} bytes)")
            return p
        log(f"{name}: SHA-256 não confere (tentativa {i}); baixando de novo")
        os.remove(p)
    sys.exit(f"ERRO: {name} com hash errado após 3 tentativas")


def validar(data, man, com_db):
    try:
        import duckdb
    except ImportError:
        log("AVISO: módulo duckdb ausente — validação pulada (pip install 'duckdb>=1.4')")
        return True
    esp = {(v["turno"], v["uf"]): (v["n_logs"], v["n_votos_log"]) for v in man.values() if v.get("estado") == "ok"}
    pq = os.path.join(data, "parquet", "eventos_secao", "*", "*", "data.parquet")
    fontes = [("parquet", duckdb.connect(), f"read_parquet('{pq}', hive_partitioning=false)")]
    if com_db:
        fontes.append(("duckdb", duckdb.connect(os.path.join(data, "db", DB), read_only=True), "eventos_secao"))
    ok = True
    for rot, con, src in fontes:
        got = {(t, u): (n, v) for t, u, n, v in con.execute(
            f"SELECT nr_turno, sg_uf, count(*), sum(n_votos_log) FROM {src} GROUP BY ALL").fetchall()}
        r = got == esp
        ok &= r
        log(f"{rot}: {len(got)} turno/UF, {sum(n for n, _ in got.values()):,} seções, "
            f"{sum(v for _, v in got.values()):,} votos no log -> {'OK' if r else 'DIVERGE do manifest'}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
    ap.add_argument("--repo", default=os.environ.get("RELEASE_REPO", REPO))
    ap.add_argument("--tag", default=os.environ.get("RELEASE_TAG", TAG))
    ap.add_argument("--method", choices=["auto", "gh", "url"], default=os.environ.get("FETCH_METHOD", "auto"))
    ap.add_argument("--so-parquet", action="store_true", help="não baixar o eventos.duckdb")
    ap.add_argument("--keep", action="store_true", help="manter o .tar depois de extrair")
    ap.add_argument("--no-validate", action="store_true")
    a = ap.parse_args()
    if a.method == "auto":
        a.method = "gh" if have_gh() else "url"
    t0 = time.time()
    data = os.path.abspath(a.data)
    dl = os.path.join(data, "release", a.tag)
    os.makedirs(dl, exist_ok=True)
    log(f"release {a.repo}@{a.tag} -> {data} (método: {a.method})")
    sums = os.path.join(dl, "SHA256SUMS")
    if os.path.exists(sums):
        os.remove(sums)
    download("SHA256SUMS", dl, a)
    exp = {l.split()[1].lstrip("*"): l.split()[0] for l in open(sums) if l.strip()}

    mpath = os.path.join(data, "manifest.json")
    if not (os.path.exists(mpath) and sha256(mpath) == exp["manifest.json"]):
        os.replace(verified("manifest.json", dl, exp, a), mpath)
    man = json.load(open(mpath))

    if not a.so_parquet:
        alvo = os.path.join(data, "db", DB)
        if os.path.exists(alvo) and sha256(alvo) == exp[DB]:
            log(f"{DB}: já íntegro, pulando")
        else:
            os.makedirs(os.path.dirname(alvo), exist_ok=True)
            os.replace(verified(DB, dl, exp, a), alvo)

    marker = os.path.join(data, "parquet", "_RELEASE.json")
    if os.path.exists(marker) and json.load(open(marker)).get("sha256") == exp[TAR]:
        log("parquet/: já extraído deste release, pulando")
    else:
        p = verified(TAR, dl, exp, a)
        with tarfile.open(p) as tf:
            for m in tf.getmembers():
                if not (m.isfile() or m.isdir()) or m.name.startswith("/") or ".." in m.name.split("/"):
                    sys.exit(f"ERRO: entrada suspeita no tar: {m.name}")
            for sub in ("eventos_secao", "eventos_tipo"):
                shutil.rmtree(os.path.join(data, "parquet", sub), ignore_errors=True)
            tf.extractall(data, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
        json.dump({"repo": a.repo, "tag": a.tag, "asset": TAR, "sha256": exp[TAR]}, open(marker, "w"), indent=1)
        if not a.keep:
            os.remove(p)
        log("parquet/: extraído")
    if not a.no_validate and not validar(data, man, not a.so_parquet):
        sys.exit("ERRO: validação rápida falhou")
    log(f"pronto em {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
