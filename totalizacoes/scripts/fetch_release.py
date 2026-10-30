#!/usr/bin/env python3
"""Baixa o banco PRONTO de um GitHub Release (sem reconstruir a partir do TSE).

  python3 scripts/fetch_release.py [--completo] [--compacto] [--data data] [--tag dados-2026-10-28]

Modos (mesma estrutura de pastas que `./run.sh all` produziria):
  --completo (padrão, ~816 MB): todos os cargos por seção
      <data>/db/eleicoes2026.duckdb                                    (477 MB)
      <data>/parquet/votos_secao/turno=<1|2>/uf=<UF>/data.parquet      (339 MB, 56 partições)
  --compacto (~154 MB): só presidente, governador e senador por seção
      <data>/db/eleicoes2026_compacto.duckdb                           (117 MB)
      <data>/parquet/majoritarios_secao.parquet                        (37 MB)
  Os dois juntos: --completo --compacto.

- Download (o repo é PÚBLICO: não precisa de login):
    gh   — `gh release download`, se o `gh` estiver instalado e logado;
    api  — API de assets do GitHub com GITHUB_TOKEN/GH_TOKEN + `curl -C -` (retomável);
    url  — anônimo, URL direta https://github.com/<repo>/releases/download/<tag>/<asset> + `curl -C -`
           (retomável). É o padrão quando não há gh logado nem token.
  Forçar um modo: --method gh|api|url (ou FETCH_METHOD=...). Se o gh falhar, cai para `url`.
- Confere SHA-256 de cada asset contra o SHA256SUMS do release. Arquivo corrompido é baixado de novo.
- Idempotente: o que já está íntegro no destino é pulado. Rode de novo se algo for interrompido.
- No fim faz uma validação rápida (linhas e presidente 2º turno) se o módulo `duckdb` existir.
"""
import argparse, hashlib, json, os, shutil, subprocess, sys, tarfile, time, urllib.request

REPO = "tonylampada/eleicoes2026"
TAG = "dados-2026-10-28"
DUCKDB_ASSET = "eleicoes2026.duckdb"
PARQUET_ASSET = "votos_secao_parquet.tar"
# compacto: asset -> caminho relativo a <data>
COMPACTO = {"eleicoes2026_compacto.duckdb": "db/eleicoes2026_compacto.duckdb",
            "majoritarios_secao.parquet": "parquet/majoritarios_secao.parquet"}
LINHAS = 69_947_081
LINHAS_COMPACTO = 14_252_760  # majoritarios_secao.parquet e tabela votos do compacto
PRES_2T = {13: 64_256_232, 22: 59_826_041}  # LULA, FLAVIO BOLSONARO
N_PARTICOES = 56


def log(*a):
    print("[fetch]", *a, flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 22), b""):
            h.update(b)
    return h.hexdigest()


def have_gh():
    if not shutil.which("gh"):
        return False
    return subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0


def token():
    t = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not t and shutil.which("gh"):
        r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
        t = r.stdout.strip() if r.returncode == 0 else None
    if not t:
        sys.exit("ERRO: --method api precisa de GITHUB_TOKEN/GH_TOKEN (ou use --method url, anônimo)")
    return t


def api_assets(repo, tag):
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{tag}",
                                 headers={"Authorization": f"Bearer {token()}",
                                          "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            rel = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"ERRO {e.code} ao ler o release {repo}@{tag} (token inválido? tente --method url)")
    return {a["name"]: a for a in rel["assets"]}


def download(name, dest_dir, args, assets_cache):
    """Baixa um asset para dest_dir/name (sem verificar hash)."""
    dest = os.path.join(dest_dir, name)
    if args.method == "gh":
        # --skip-existing: não rebaixa o que já está lá (o hash é conferido depois)
        r = subprocess.run(["gh", "release", "download", args.tag, "-R", args.repo, "-p", name,
                            "-D", dest_dir, "--skip-existing"])
        if r.returncode == 0:
            return dest
        log(f"gh falhou para {name}; tentando download anônimo por URL direta")
        return curl_resume(f"https://github.com/{args.repo}/releases/download/{args.tag}/{name}", dest, None, [])
    if args.method == "url":
        return curl_resume(f"https://github.com/{args.repo}/releases/download/{args.tag}/{name}", dest, None, [])
    if "a" not in assets_cache:
        assets_cache["a"] = api_assets(args.repo, args.tag)
    a = assets_cache["a"].get(name) or sys.exit(f"ERRO: asset {name} não existe no release {args.tag}")
    return curl_resume(a["url"], dest, a["size"],
                       ["-H", f"Authorization: Bearer {token()}", "-H", "Accept: application/octet-stream"])


def curl_resume(url, dest, size, headers):
    """Baixa para <dest>.part com `curl -C -` (retoma do byte onde parou) e renomeia no fim."""
    part = dest + ".part"
    if os.path.exists(dest):
        os.replace(dest, part)  # o hash é conferido depois; se estiver errado, é apagado e rebaixado
    if size is not None and os.path.exists(part) and os.path.getsize(part) > size:
        os.remove(part)
    if not (size is not None and os.path.exists(part) and os.path.getsize(part) == size):
        r = subprocess.run(["curl", "-fL", "--retry", "5", "--retry-delay", "3", "-C", "-", "-o", part,
                            *headers, url])
        # 416 = Range além do fim: o .part já está completo
        partial = os.path.exists(part) and os.path.getsize(part) > 0
        if r.returncode != 0 and not (r.returncode in (22, 33) and partial):
            sys.exit(f"ERRO: curl falhou ({r.returncode}) em {url}")
    os.replace(part, dest)
    return dest


def get_verified(name, dest_dir, expected, args, cache):
    for tentativa in range(1, 4):
        path = download(name, dest_dir, args, cache)
        t0 = time.time()
        h = sha256(path)
        if h == expected[name]:
            log(f"{name}: SHA-256 OK ({os.path.getsize(path):,} bytes, hash em {time.time()-t0:.1f}s)")
            return path
        log(f"{name}: SHA-256 NÃO confere (tentativa {tentativa}); apagando e baixando de novo")
        os.remove(path)
    sys.exit(f"ERRO: {name} continua com hash errado depois de 3 tentativas")


def parquet_ok(pq_dir, tar_sha):
    marker = os.path.join(pq_dir, "_RELEASE.json")
    if not os.path.exists(marker):
        return False
    try:
        m = json.load(open(marker))
    except Exception:
        return False
    n = sum(1 for r, _, fs in os.walk(pq_dir) for f in fs if f == "data.parquet")
    return m.get("sha256") == tar_sha and n == m.get("particoes") == N_PARTICOES


def _check(rotulo, con, src, linhas):
    n = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    p = dict(con.execute(f"SELECT nr_votavel, sum(qt_votos) FROM {src} WHERE nr_turno=2 AND cd_cargo=1 "
                         "AND cd_tipo_votavel=1 GROUP BY 1").fetchall())
    r = n == linhas and all(p.get(k) == v for k, v in PRES_2T.items())
    log(f"{rotulo}: {n:,} linhas (esperado {linhas:,}); pres. 2º turno LULA {p.get(13) or 0:,} × "
        f"FLAVIO {p.get(22) or 0:,} -> {'OK' if r else 'DIVERGE'}")
    return r


def validar(data, completo, compacto):
    try:
        import duckdb
    except ImportError:
        log("AVISO: módulo duckdb ausente — validação pulada (pip install 'duckdb>=1.4')")
        return True
    ok, mem = True, duckdb.connect()
    if completo:
        pq = os.path.join(data, "parquet", "votos_secao", "*", "*", "data.parquet")
        ok &= _check("parquet completo", mem, f"read_parquet('{pq}')", LINHAS)
        ok &= _check("duckdb completo  ", duckdb.connect(os.path.join(data, "db", DUCKDB_ASSET), read_only=True),
                     "votos", LINHAS)
    if compacto:
        pq = os.path.join(data, COMPACTO["majoritarios_secao.parquet"])
        ok &= _check("parquet compacto ", mem, f"read_parquet('{pq}')", LINHAS_COMPACTO)
        ok &= _check("duckdb compacto  ", duckdb.connect(os.path.join(data, COMPACTO["eleicoes2026_compacto.duckdb"]),
                                                         read_only=True), "votos", LINHAS_COMPACTO)
    return ok


def fetch_file(name, alvo, dl, expected, args, cache):
    if os.path.exists(alvo) and sha256(alvo) == expected[name]:
        log(f"{name}: já íntegro em {alvo}, pulando")
        return
    p = get_verified(name, dl, expected, args, cache)
    os.makedirs(os.path.dirname(alvo), exist_ok=True)
    os.replace(p, alvo)
    log(f"{name} -> {alvo}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
    ap.add_argument("--repo", default=os.environ.get("RELEASE_REPO", REPO))
    ap.add_argument("--tag", default=os.environ.get("RELEASE_TAG", TAG))
    ap.add_argument("--completo", action="store_true", help="banco completo, todos os cargos (padrão)")
    ap.add_argument("--compacto", action="store_true", help="só presidente/governador/senador (~154 MB)")
    ap.add_argument("--method", choices=["auto", "gh", "api", "url"], default=os.environ.get("FETCH_METHOD", "auto"))
    ap.add_argument("--keep", action="store_true", help="manter o .tar em <data>/release/ depois de extrair")
    ap.add_argument("--force", action="store_true", help="substituir votos_secao/ existente que não veio do release")
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args()
    if not (args.completo or args.compacto):
        args.completo = True
    if args.method == "auto":
        if have_gh():
            args.method = "gh"
        elif os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"):
            args.method = "api"
        else:
            args.method = "url"
    if args.method != "gh" and not shutil.which("curl"):
        sys.exit("ERRO: precisa de `curl` (ou do `gh` logado)")
    t_inicio = time.time()
    data = os.path.abspath(args.data)
    dl = os.path.join(data, "release", args.tag)
    os.makedirs(dl, exist_ok=True)
    modos = " + ".join(m for m, on in (("completo", args.completo), ("compacto", args.compacto)) if on)
    log(f"release {args.repo}@{args.tag} -> {data} (modo: {modos}; método: {args.method})")

    cache = {}
    sums = os.path.join(dl, "SHA256SUMS")
    if os.path.exists(sums):
        os.remove(sums)  # sempre pega o SHA256SUMS atual do release (pequeno)
    download("SHA256SUMS", dl, args, cache)
    expected = {l.split()[1].lstrip("*"): l.split()[0] for l in open(sums) if l.strip()}

    if args.compacto:
        for name, rel in COMPACTO.items():
            fetch_file(name, os.path.join(data, rel), dl, expected, args, cache)

    if args.completo:
        fetch_file(DUCKDB_ASSET, os.path.join(data, "db", DUCKDB_ASSET), dl, expected, args, cache)
        pq_root = os.path.join(data, "parquet")
        pq_dir = os.path.join(pq_root, "votos_secao")
        tar_sha = expected[PARQUET_ASSET]
        if parquet_ok(pq_dir, tar_sha):
            log("votos_secao/: já extraído deste release, pulando")
        else:
            local = [r for r, _, fs in os.walk(pq_dir) if "data.parquet" in fs and "_OK.json" in fs]
            if not os.path.exists(os.path.join(pq_dir, "_RELEASE.json")) and len(local) == N_PARTICOES and not args.force:
                log(f"votos_secao/: build local completo ({N_PARTICOES} partições com _OK.json); pulando (--force substitui)")
                pq_dir = None
        if pq_dir and not parquet_ok(pq_dir, tar_sha):
            p = get_verified(PARQUET_ASSET, dl, expected, args, cache)
            tmp = os.path.join(pq_root, ".votos_secao.extraindo")
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp)
            with tarfile.open(p) as tf:
                membros = tf.getmembers()
                for m in membros:  # só arquivos/pastas comuns, sem caminhos absolutos ou ".."
                    if not (m.isfile() or m.isdir()) or m.name.startswith("/") or ".." in m.name.split("/"):
                        sys.exit(f"ERRO: entrada suspeita no tar: {m.name}")
                tf.extractall(tmp, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
            novo = os.path.join(tmp, "votos_secao")
            n = sum(1 for r, _, fs in os.walk(novo) for f in fs if f == "data.parquet")
            if n != N_PARTICOES:
                sys.exit(f"ERRO: esperava {N_PARTICOES} partições, achei {n}")
            json.dump({"repo": args.repo, "tag": args.tag, "asset": PARQUET_ASSET, "sha256": tar_sha,
                       "particoes": n}, open(os.path.join(novo, "_RELEASE.json"), "w"), indent=1)
            if os.path.exists(pq_dir):
                shutil.rmtree(pq_dir)
            os.replace(novo, pq_dir)
            os.rmdir(tmp)
            log(f"votos_secao/: {n} partições extraídas em {pq_dir}")
            if not args.keep:
                os.remove(p)

    log(f"downloads/extração em {time.time()-t_inicio:.1f}s")
    if not args.no_validate and not validar(data, args.completo, args.compacto):
        sys.exit("ERRO: validação rápida falhou")
    log(f"pronto em {time.time()-t_inicio:.1f}s")


if __name__ == "__main__":
    main()
