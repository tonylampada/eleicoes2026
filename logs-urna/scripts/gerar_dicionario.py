#!/usr/bin/env python3
"""Gera docs/dicionario_eventos_<t>t.md: os modelos de mensagem VISTOS nos logs (dígitos trocados por '#').

Fontes:
  - data/db/eventos.duckdb, tabela eventos_dicionario: população completa das UFs processadas, mas só para
    eventos de nível != INFO e mensagens INFO da lista INFO_EVENTOS do parser (fora o app GAP).
  - data/inspecao/catalogo_<t>t_<UF>_amostra*.json (scripts/inspecionar_eventos.py): amostra de seções com TODOS
    os modelos, inclusive a rotina INFO.
Nada aqui é inventado: só entra modelo que apareceu em pelo menos uma seção.
"""
import argparse, glob, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parser_log as P

AQUI = os.path.dirname(os.path.abspath(__file__))

# mensagem -> como entra nas métricas de eventos_secao (lido do próprio parser quando possível)
USO = {
    "Urna pronta para receber votos": "hr_abertura_log (1ª no dia) / n_urna_pronta",
    "Procedimento de encerramento confirmado": "hr_encerramento_log",
    "Inicio do Encerramento": "hr_inicio_encerramento_log",
    "O voto do eleitor foi computado": "n_votos_log, horários e intervalos",
    "Voto confirmado para [Presidente]": "n_voto_confirmado_presidente",
    "Eleitor foi habilitado": "n_habilitados, tempo_cabine_mediano_s",
    "Tipo de habilitação do eleitor [biométrica]": "n_hab_biometrica",
    "Solicitação de dado pessoal do eleitor para habilitação manual": "n_hab_manual",
    "Ano de nascimento digitado é igual ao do cadastro": "n_hab_ano_nascimento (sem biometria nem habilitação manual)",
    "Aguardando digitação do identificador do eleitor": "início de uma sessão de habilitação",
}


def regras_contagens():
    """(coluna, app, regra) lidos do código-fonte de CONTAGENS em parser_log.py (a regra é o lambda literal)."""
    import re
    src = open(os.path.join(AQUI, "parser_log.py"), encoding="utf-8").read()
    bloco = src[src.index("CONTAGENS = {"):]
    bloco = bloco[:bloco.index("\n}")]
    return re.findall(r'"(n_\w+)": \("(\w+)", lambda m: (.+)\),\s*$', bloco, re.M)


def md(s):
    return s.replace("|", "\\|")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(AQUI, "..", "data"))
    ap.add_argument("--turno", type=int, default=2)
    ap.add_argument("--min-secoes-pct", type=float, default=1.0, help="corte da amostra para a rotina INFO")
    ap.add_argument("--top-gap", type=int, default=40)
    a = ap.parse_args()
    import duckdb
    out = os.path.join(AQUI, "..", "docs", f"dicionario_eventos_{a.turno}t.md")
    L = [f"# Dicionário de eventos dos logs de urna — {a.turno}º turno 2026", "",
         "Gerado por `scripts/gerar_dicionario.py`. Só lista mensagens efetivamente vistas. Dígitos (horários, "
         "contagens, títulos de mesário, números de urna) foram trocados por `#`. Apps: VOTA (votação), GAP "
         "(gerenciador da aplicação), LOGD (serviço de log), INITJE (inicialização), ATUE/SCUE (raros).", ""]
    # contadores do parser
    L += ["## Mensagens usadas nas métricas", "", "| mensagem (prefixo) | coluna em `eventos_secao` |", "|---|---|"]
    for k, v in USO.items():
        L.append(f"| {md(k)} | `{v}` |")
    for col, app, regra in regras_contagens():
        L.append(f"| {app}: `{md(regra)}` | `{col}` |")
    L.append("")
    # amostras
    cats = sorted(glob.glob(os.path.join(a.data, "inspecao", f"catalogo_{a.turno}t_*_amostra*.json")))
    for c in cats:
        j = json.load(open(c))
        n = j["n_amostra"]
        L += [f"## Rotina (todos os níveis) — amostra {j['uf']}: {n} de {j['n_logs_no_zip']:,} seções",
              "", f"Modelos presentes em ≥ {a.min_secoes_pct}% das seções da amostra (GAP: só os {a.top_gap} mais comuns). "
              f"Total de modelos distintos na amostra: {len(j['modelos']):,}.", "",
              "| app | nível | modelo | ocorrências | % seções |", "|---|---|---|--:|--:|"]
        gap = 0
        for m in j["modelos"]:
            pct = 100 * m["secoes"] / n
            if pct < a.min_secoes_pct:
                continue
            if m["app"] == "GAP":
                gap += 1
                if gap > a.top_gap:
                    continue
            L.append(f"| {m['app']} | {m['nivel']} | {md(m['modelo'])} | {m['ocorrencias']:,} | {pct:.1f} |")
        L.append("")
    db = os.path.join(a.data, "db", "eventos.duckdb")
    con = duckdb.connect(db, read_only=True)
    tot = dict(con.execute("SELECT sg_uf, count(*) FROM eventos_secao WHERE nr_turno=? GROUP BY 1", [a.turno]).fetchall())
    ntot = sum(tot.values())
    L += [f"## Eventos fora da rotina — população completa ({', '.join(f'{u}: {n:,}' for u, n in sorted(tot.items()))} seções)", "",
          "Nível ≠ INFO, mais as mensagens INFO de interesse (fora do GAP). Ordenado por nº de seções; "
          "mostrando modelos em ≥ 0,1% das seções ou com nível ERRO/ALERTA em ≥ 10 seções.", "",
          "| app | nível | modelo | ocorrências | seções | % seções |", "|---|---|---|--:|--:|--:|"]
    rows = con.execute("""SELECT app, nivel, modelo, sum(ocorrencias), sum(secoes) FROM eventos_dicionario
                          WHERE nr_turno=? GROUP BY ALL ORDER BY 5 DESC, 4 DESC""", [a.turno]).fetchall()
    for app, niv, mod, oc, se in rows:
        if se / ntot >= 0.001 or (niv in ("ERRO", "ALERTA") and se >= 10):
            L.append(f"| {app} | {niv} | {md(mod)} | {oc:,} | {se:,} | {100*se/ntot:.2f} |")
    L += ["", f"Modelos distintos na tabela `eventos_dicionario`: {len(rows):,} (lista completa: `SELECT * FROM eventos_dicionario`).", ""]
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write("\n".join(L))
    print(out, len(L), "linhas")


if __name__ == "__main__":
    main()
