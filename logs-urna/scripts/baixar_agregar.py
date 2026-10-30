#!/usr/bin/env python3
"""Baixa o zip de arquivos de urna do TSE (BU + imagem do BU + LOG + RDV + assinaturas) de uma UF,
lê os logs (<seção>-log.jez) direto do zip, agrega por seção e grava só Parquet pequeno.

  python3 scripts/baixar_agregar.py --turno 2 --ufs BA,CE [--data data] [--jobs 8] [--keep-zip]

Por UF, em sequência (um zip por vez em disco):
  1. HEAD no CDN do TSE (tamanho, ETag, Last-Modified);
  2. download retomável: <zip>.part com `curl -C -`, renomeado quando o tamanho bate;
  3. SHA-256 do zip (o TSE não publica hash desses zips; o nosso fica no manifest);
  4. agregação em paralelo (--jobs processos, cada um abre o zip e lê seus membros em memória);
  5. grava data/parquet/eventos_secao/turno=<t>/uf=<UF>/data.parquet e
          data/parquet/eventos_tipo/turno=<t>/uf=<UF>/data.parquet (via .tmp + rename);
  6. atualiza data/manifest.json (hash do zip, ETag, versão do parser, hash dos scripts, tempos, tamanhos);
  7. apaga o zip (a não ser com --keep-zip).
Retomável: UF com entrada "ok" no manifest com o mesmo ETag/tamanho e a mesma versão do parser, e Parquets
presentes com o hash registrado, é pulada (use --force para refazer).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import resource
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parser_log  # noqa: E402

URL = "https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_{t}t_{uf}.zip"
UFS_TODAS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ").split()
RX = re.compile(r"^o(\d{5})([a-z]{2})(\d{5})(\d{4})(\d{4})-log\.jez$")
SCRIPTS = ("baixar_agregar.py", "parser_log.py")


def log(*a):
    print(dt.datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def sha256_file(p, bs=1 << 22):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(bs), b""):
            h.update(b)
    return h.hexdigest()


def scripts_hash():
    d = os.path.dirname(os.path.abspath(__file__))
    h = hashlib.sha256()
    for s in SCRIPTS:
        h.update(open(os.path.join(d, s), "rb").read())
    return h.hexdigest()[:16]


def head(url):
    r = subprocess.run(["curl", "-sSfI", "--retry", "5", url], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"HEAD falhou ({r.returncode}) {url}: {r.stderr.strip()}")
    h = {}
    for line in r.stdout.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            h[k.strip().lower()] = v.strip()
    return {"bytes": int(h["content-length"]), "etag": h.get("etag", "").strip('"'),
            "last_modified": h.get("last-modified")}


def baixar(url, dest, size):
    """curl -C - em <dest>.part; devolve (segundos, bytes baixados nesta execução)."""
    if os.path.exists(dest) and os.path.getsize(dest) == size:
        return 0.0, 0
    part = dest + ".part"
    antes = os.path.getsize(part) if os.path.exists(part) else 0
    if antes > size:
        os.remove(part)
        antes = 0
    t0 = time.time()
    for tentativa in range(1, 6):
        r = subprocess.run(["curl", "-sSfL", "--retry", "5", "--retry-delay", "5", "-C", "-", "-o", part, url])
        got = os.path.getsize(part) if os.path.exists(part) else 0
        if got == size:
            break
        log(f"  curl terminou com {r.returncode} e {got:,}/{size:,} bytes; tentativa {tentativa}, retomando")
        time.sleep(5)
    else:
        raise RuntimeError(f"download incompleto: {url}")
    os.replace(part, dest)
    return time.time() - t0, size - antes


# ---------- agregação (processos) ----------
_Z = None
_T = None


def _init(zpath, turno):
    global _Z, _T
    _Z = zipfile.ZipFile(zpath)
    _T = turno


def _trabalho(nomes):
    linhas, eventos = [], []
    for nome in nomes:
        m = RX.match(nome)
        chave = {"cd_municipio": int(m[3]), "nr_zona": int(m[4]), "nr_secao": int(m[5])}
        try:
            blob = _Z.read(nome)
            r, ev = parser_log.parse_secao(blob, _T)
            r["log_bytes"] = len(blob)
            r["erro"] = None
        except Exception as e:  # registra e segue; a seção fica com erro preenchido
            r, ev = {"erro": f"{type(e).__name__}: {e}"[:300]}, {}
        linhas.append({**chave, "arquivo_log": nome, **r})
        for (app, niv, mod), n in ev.items():
            eventos.append({**chave, "app": app, "nivel": niv, "modelo": mod, "n": n})
    return linhas, eventos


def schema_secao(pa):
    i16, i32, f32, tm = pa.int16(), pa.int32(), pa.float32(), pa.time32("s")
    campos = [("nr_turno", pa.int8()), ("sg_uf", pa.string()), ("cd_municipio", i32), ("nr_zona", i16),
              ("nr_secao", i16), ("arquivo_log", pa.string()), ("log_bytes", i32), ("erro", pa.string()),
              ("parser_version", pa.string()),
              ("n_arquivos_log", i16), ("n_urnas_log", i16), ("n_urnas_com_voto", i16), ("n_linhas_dia", i32),
              ("hr_abertura_log", tm), ("hr_encerramento_log", tm), ("hr_inicio_encerramento_log", tm),
              ("hr_impressao_bu_log", tm), ("n_votos_log", i16), ("n_votos_logs_arquivados", i16),
              ("n_votos_fora_do_dia", i16), ("hr_primeiro_voto", tm), ("hr_ultimo_voto", tm),
              ("votos_por_hora", pa.list_(i16)), ("intervalo_mediano_s", f32), ("intervalo_medio_s", f32),
              ("intervalo_min_s", i32), ("intervalo_p10_s", f32), ("intervalo_mediano_por_hora_s", pa.list_(f32)),
              ("velocidade_media_votos_hora", f32), ("tempo_cabine_mediano_s", f32)]
    for lim in parser_log.LIMIARES_S:
        campos += [(f"n_pares_lt{lim}s", i16), (f"pct_pares_lt{lim}s", f32)]
    for lim in parser_log.RAJADA_S:
        campos.append((f"maior_rajada_lt{lim}s", i16))
    campos += [(k, i16) for k in ("n_hab_biometrica", "n_hab_manual", "n_hab_ano_nascimento", "n_hab_outra",
                                  "n_id_titulo", "n_id_cpf", "n_habilitados")]
    campos += [(k, i32 if k in ("n_digital_solicitada", "n_tecla_indevida") else i16) for k in parser_log.CONTAGENS]
    campos += [("n_erro", i32), ("n_alerta", i32)]
    return pa.schema(campos)


def _hms_to_time(v):
    if v is None:
        return None
    return dt.time(int(v[:2]), int(v[3:5]), int(v[6:8]))


def gravar(pa, pq, linhas, eventos, out_sec, out_ev, turno, uf):
    sch = schema_secao(pa)
    cols = {}
    for f in sch:
        if f.name == "nr_turno":
            cols[f.name] = [turno] * len(linhas)
        elif f.name == "sg_uf":
            cols[f.name] = [uf] * len(linhas)
        elif pa.types.is_time(f.type):
            cols[f.name] = [_hms_to_time(r.get(f.name)) for r in linhas]
        else:
            cols[f.name] = [r.get(f.name) for r in linhas]
    t = pa.Table.from_pydict(cols, schema=sch).sort_by([("cd_municipio", "ascending"), ("nr_zona", "ascending"),
                                                        ("nr_secao", "ascending")])
    te = pa.Table.from_pylist(
        [{"nr_turno": turno, "sg_uf": uf, **e} for e in eventos],
        schema=pa.schema([("nr_turno", pa.int8()), ("sg_uf", pa.string()), ("cd_municipio", pa.int32()),
                          ("nr_zona", pa.int16()), ("nr_secao", pa.int16()), ("app", pa.string()),
                          ("nivel", pa.string()), ("modelo", pa.string()), ("n", pa.int32())]))
    te = te.sort_by([("cd_municipio", "ascending"), ("nr_zona", "ascending"), ("nr_secao", "ascending"),
                     ("app", "ascending"), ("modelo", "ascending")])
    res = {}
    for tab, out in ((t, out_sec), (te, out_ev)):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        pq.write_table(tab, out + ".tmp", compression="zstd", compression_level=9)
        os.replace(out + ".tmp", out)
        res[out] = {"linhas": tab.num_rows, "bytes": os.path.getsize(out), "sha256": sha256_file(out)}
    return res


def processar_uf(args, uf, man):
    import pyarrow as pa
    import pyarrow.parquet as pq

    t, data = args.turno, args.data
    url = URL.format(t=t, uf=uf)
    chave = f"{t}t_{uf}"
    rel_sec = f"parquet/eventos_secao/turno={t}/uf={uf}/data.parquet"
    rel_ev = f"parquet/eventos_tipo/turno={t}/uf={uf}/data.parquet"
    out_sec, out_ev = os.path.join(data, rel_sec), os.path.join(data, rel_ev)
    h = head(url)
    ent = man.get(chave)
    if (not args.force and ent and ent.get("estado") == "ok" and ent.get("etag") == h["etag"]
            and ent.get("zip_bytes") == h["bytes"] and ent.get("parser_version") == parser_log.PARSER_VERSION
            and all(os.path.exists(os.path.join(data, r)) and sha256_file(os.path.join(data, r)) == ent["saidas"][r]["sha256"]
                    for r in (rel_sec, rel_ev))):
        log(f"{chave}: já processado (ETag {h['etag']}, parser {parser_log.PARSER_VERSION}); pulando")
        return
    os.makedirs(os.path.join(data, "raw"), exist_ok=True)
    zpath = os.path.join(data, "raw", os.path.basename(url))
    esperar_disco(os.path.join(data, "raw"), h["bytes"], args.margem_gb)
    log(f"{chave}: baixando {h['bytes']/1e9:.2f} GB de {url}")
    t_dl, b_dl = baixar(url, zpath, h["bytes"])
    if t_dl:
        log(f"{chave}: download {b_dl/1e9:.2f} GB em {t_dl:.0f}s ({b_dl/1e6/max(t_dl,1e-9):.0f} MB/s)")
    t0 = time.time()
    zsha = sha256_file(zpath)
    t_hash = time.time() - t0
    log(f"{chave}: SHA-256 do zip {zsha[:16]}… ({t_hash:.0f}s)")

    with zipfile.ZipFile(zpath) as z:
        nomes = [i.filename for i in z.infolist() if RX.match(i.filename)]
        n_bu = sum(1 for i in z.infolist() if i.filename.endswith("-bu.dat"))
        ufs_nome = {RX.match(n)[2].upper() for n in nomes}
    if ufs_nome - {uf}:
        raise RuntimeError(f"zip de {uf} contém logs de outra UF: {ufs_nome}")
    log(f"{chave}: {len(nomes):,} logs de seção ({n_bu:,} BUs) — agregando com {args.jobs} processos")
    ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
    t0 = time.time()
    lotes = [nomes[i:i + 200] for i in range(0, len(nomes), 200)]
    linhas, eventos = [], []
    with ProcessPoolExecutor(args.jobs, initializer=_init, initargs=(zpath, t)) as ex:
        for k, (l, e) in enumerate(ex.map(_trabalho, lotes), 1):
            linhas += l
            eventos += e
            if k % 25 == 0 or k == len(lotes):
                el = time.time() - t0
                log(f"  {len(linhas):,}/{len(nomes):,} seções ({len(linhas)/el:.0f}/s)")
    t_proc = time.time() - t0
    ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = (ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime)
    n_err = sum(1 for r in linhas if r.get("erro"))
    saidas_abs = gravar(pa, pq, linhas, eventos, out_sec, out_ev, t, uf)
    saidas = {os.path.relpath(k, data): v for k, v in saidas_abs.items()}
    man[chave] = {
        "turno": t, "uf": uf, "zip_url": url, "zip_bytes": h["bytes"], "etag": h["etag"],
        "last_modified": h["last_modified"], "zip_sha256": zsha, "n_logs": len(nomes), "n_bu_no_zip": n_bu,
        "n_erros_parse": n_err, "n_votos_log": sum(r.get("n_votos_log") or 0 for r in linhas),
        "parser_version": parser_log.PARSER_VERSION, "scripts_sha256_16": scripts_hash(),
        "tempos_s": {"download": round(t_dl, 1), "hash_zip": round(t_hash, 1), "agregacao": round(t_proc, 1)},
        "download_mb_s": round(b_dl / 1e6 / t_dl, 1) if t_dl else None,
        "cpu_s_agregacao": round(cpu, 1), "jobs": args.jobs,
        "rss_max_mb_processo_filho": round(ru1.ru_maxrss / 1024, 1),
        "saidas": saidas, "estado": "ok",
        "processado_em": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    salvar_manifest(data, man)
    log(f"{chave}: agregado em {t_proc:.0f}s (CPU {cpu:.0f}s), erros de parse {n_err}; "
        + "; ".join(f"{os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(k))))}: {v['linhas']:,} linhas, {v['bytes']/1e6:.2f} MB" for k, v in saidas.items()))
    if not args.keep_zip:
        os.remove(zpath)
        log(f"{chave}: zip apagado")


def esperar_disco(raw, precisa, margem_gb, max_espera_s=3600):
    """Antes de baixar: espera sumirem cópias temporárias (*.box-store-snap-*) de zips já apagados e exige
    livre >= tamanho do zip + margem. Depois de max_espera_s segue se o espaço bastar mesmo com snapshot."""
    import glob, shutil
    t0 = time.time()
    while True:
        snaps = glob.glob(os.path.join(raw, "*.box-store-snap-*"))
        livre = shutil.disk_usage(raw).free
        ok_esp = livre >= precisa + margem_gb * 1e9
        if ok_esp and (not snaps or time.time() - t0 > max_espera_s):
            log(f"disco: {livre/1e9:.1f} GB livres, zip {precisa/1e9:.2f} GB, snapshots pendentes {len(snaps)}"
                + (f" (esperou {time.time()-t0:.0f}s)" if time.time() - t0 > 1 else ""))
            return
        log(f"disco: aguardando — {livre/1e9:.1f} GB livres, precisa {precisa/1e9:.2f}+{margem_gb} GB, snapshots {len(snaps)}")
        time.sleep(20)


def salvar_manifest(data, man):
    p = os.path.join(data, "manifest.json")
    json.dump(man, open(p + ".tmp", "w"), indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(p + ".tmp", p)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
    ap.add_argument("--turno", type=int, default=2, choices=(1, 2))
    ap.add_argument("--ufs", default="BA,CE", help="lista separada por vírgula, ou TODAS")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--keep-zip", action="store_true", help="não apagar o zip depois de agregar")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--margem-gb", type=float, default=15, help="espaço livre exigido além do tamanho do zip")
    args = ap.parse_args()
    args.data = os.path.abspath(args.data)
    ufs = UFS_TODAS if args.ufs.upper() == "TODAS" else [u.strip().upper() for u in args.ufs.split(",") if u.strip()]
    p = os.path.join(args.data, "manifest.json")
    man = json.load(open(p)) if os.path.exists(p) else {}
    falhas = []
    for uf in ufs:
        try:
            processar_uf(args, uf, man)
        except Exception as e:  # segue para a próxima UF; rodar de novo retoma
            log(f"{args.turno}t_{uf}: FALHOU: {e!r}")
            falhas.append(uf)
    if falhas:
        sys.exit(f"UFs com falha: {','.join(falhas)} (rode de novo para retomar)")


if __name__ == "__main__":
    main()
