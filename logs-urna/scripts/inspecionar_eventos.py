#!/usr/bin/env python3
"""Lista os modelos de mensagem que aparecem nos logs de uma amostra de seções (dicionário de eventos).

  python3 scripts/inspecionar_eventos.py --turno 2 --uf BA --n 600 [--zip caminho/local.zip] [--out docs/...json]

Sem --zip, lê só os membros sorteados direto do CDN do TSE com HTTP Range (pacote `remotezip`), sem baixar
o zip inteiro. Amostra sistemática (1 a cada len/n logs, na ordem do zip). Considera só linhas datadas do dia
da votação do turno, do log principal e dos logs arquivados. Dígitos viram '#', então números de título,
CPF ou série não aparecem na saída.
"""
import argparse, collections, json, os, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parser_log as P  # noqa: E402
from baixar_agregar import URL, RX  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--turno", type=int, default=2)
    ap.add_argument("--uf", default="BA")
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--zip")
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.zip:
        z = zipfile.ZipFile(a.zip)
    else:
        from remotezip import RemoteZip
        z = RemoteZip(URL.format(t=a.turno, uf=a.uf.upper()))
    nomes = [n for n in z.namelist() if RX.match(n)]
    passo = max(1, len(nomes) // a.n)
    amostra = nomes[::passo][: a.n]
    dia = P.TURNOS[a.turno]["dia"]
    ocorr, secoes = collections.Counter(), collections.Counter()
    for k, nome in enumerate(amostra, 1):
        vistos = set()
        for _, txt in P.ler_jez(z.read(nome)):
            for l in txt.splitlines():
                p = l.split("\t")
                if len(p) < 5 or p[0][:10] != dia:
                    continue
                key = (p[3], p[1], P.modelo(p[4]))
                ocorr[key] += 1
                vistos.add(key)
        secoes.update(vistos)
        if k % 100 == 0:
            print(f"{k}/{len(amostra)}", file=sys.stderr, flush=True)
    rows = [{"app": k[0], "nivel": k[1], "modelo": k[2], "ocorrencias": v, "secoes": secoes[k]}
            for k, v in sorted(ocorr.items(), key=lambda x: (-secoes[x[0]], -x[1]))]
    res = {"turno": a.turno, "uf": a.uf.upper(), "dia": dia, "n_amostra": len(amostra), "n_logs_no_zip": len(nomes),
           "parser_version": P.PARSER_VERSION, "modelos": rows}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"{len(rows)} modelos em {len(amostra)} seções; por aplicação:",
          dict(collections.Counter(r["app"] for r in rows)), "; por nível:", dict(collections.Counter(r["nivel"] for r in rows)))


if __name__ == "__main__":
    main()
