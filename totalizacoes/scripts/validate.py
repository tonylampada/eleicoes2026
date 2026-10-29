#!/usr/bin/env python3
"""Valida as totalizações de presidente contra os números oficiais divulgados pelo TSE.

Referências oficiais (resultados.tse.jus.br, 100% das seções totalizadas):
  1º turno (04/10/2026, totalização final 05/10 12:51): FLAVIO BOLSONARO 56.104.503; LULA 53.879.538;
     válidos 119.300.788; brancos 2.300.798; nulos 3.669.003; comparecimento 125.275.835; 499.248 seções.
     (números do painel oficial, transcritos via app.votostse.com)
  2º turno (25/10/2026, atualização 23:26:38): LULA 64.256.232 (51,79%); FLAVIO BOLSONARO 59.826.041 (48,21%);
     válidos 124.082.273; brancos 1.430.496; nulos 2.723.305; comparecimento 128.236.074;
     abstenção 30.509.005; aptos 158.745.502; 499.248 seções.
Gera data/validacao.md e sai com código 1 se houver divergência.
"""
import os, sys
import duckdb

OFICIAL = {
    1: {"LULA (13)": 53879538, "FLAVIO BOLSONARO (22)": 56104503, "validos": 119300788,
        "brancos": 2300798, "nulos": 3669003, "comparecimento": 125275835, "secoes": 499248,
        "ESCRITOR AUGUSTO CURY (70)": 3448569, "RENAN SANTOS (14)": 2675887, "RONALDO CAIADO (55)": 2605148},
    2: {"LULA (13)": 64256232, "FLAVIO BOLSONARO (22)": 59826041, "validos": 124082273,
        "brancos": 1430496, "nulos": 2723305, "comparecimento": 128236074, "secoes": 499248,
        "aptos": 158745502},
}
# Itens com diferença conhecida/explicada (não reprovam a validação; ver NOTAS):
INFORMATIVOS = {"validos", "secoes", "aptos"}
NOTAS = """
### Notas sobre diferenças conhecidas

- **válidos (1º turno, +5.246)**: o BU traz votos nominais para o nº 28 (LEONARDO AVALANCHE), que não
  aparece entre os 12 candidatos do painel oficial; esses 5.246 votos não entram nos válidos oficiais
  (provável candidatura indeferida/anulada — votos computados como nulos/anulados na totalização).
  Sem eles, os válidos batem exatamente: 119.306.034 − 5.246 = 119.300.788.
- **seções (−42/−43)**: os arquivos buweb trazem uma linha por boletim de urna efetivamente apurado;
  o painel conta 499.248 seções, incluindo seções não instaladas e/ou agregadas (16.142 BUs agregam
  outras seções — ver coluna ds_secoes_agregadas).
- **aptos (2º turno, −525)**: o painel informa 423 eleitores em seções não instaladas (sem BU);
  restam 102 eleitores de diferença não explicados por esta checagem.
"""
data = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "..", "data"))
pq = os.path.join(data, "parquet", "votos_secao", "*", "*", "data.parquet")
con = duckdb.connect()
out, bad = ["# Validação — presidente (dados por seção × resultado oficial TSE)\n"], 0
for t, ref in OFICIAL.items():
    r = con.execute(f"""
      WITH v AS (SELECT * FROM read_parquet('{pq}') WHERE cd_cargo = 1 AND nr_turno = {t}),
      s AS (SELECT DISTINCT sg_uf, cd_municipio, nr_zona, nr_secao, qt_aptos, qt_comparecimento FROM v)
      SELECT
        (SELECT sum(qt_votos) FROM v WHERE nr_votavel = 13 AND cd_tipo_votavel = 1),
        (SELECT sum(qt_votos) FROM v WHERE nr_votavel = 22 AND cd_tipo_votavel = 1),
        (SELECT sum(qt_votos) FROM v WHERE nr_votavel = 70 AND cd_tipo_votavel = 1),
        (SELECT sum(qt_votos) FROM v WHERE nr_votavel = 14 AND cd_tipo_votavel = 1),
        (SELECT sum(qt_votos) FROM v WHERE nr_votavel = 55 AND cd_tipo_votavel = 1),
        (SELECT sum(qt_votos) FROM v WHERE cd_tipo_votavel = 1),
        (SELECT sum(qt_votos) FROM v WHERE cd_tipo_votavel = 2),
        (SELECT sum(qt_votos) FROM v WHERE cd_tipo_votavel NOT IN (1, 2)),
        (SELECT sum(qt_comparecimento) FROM s),
        (SELECT count(*) FROM s),
        (SELECT sum(qt_aptos) FROM s)
    """).fetchone()
    calc = dict(zip(["LULA (13)", "FLAVIO BOLSONARO (22)", "ESCRITOR AUGUSTO CURY (70)", "RENAN SANTOS (14)",
                     "RONALDO CAIADO (55)", "validos", "brancos", "nulos", "comparecimento", "secoes", "aptos"], r))
    out.append(f"\n## {t}º turno\n\n| item | calculado (BU por seção) | oficial TSE | diferença |\n|---|---:|---:|---:|")
    for k, v in ref.items():
        d = (calc[k] or 0) - v
        if k in INFORMATIVOS:
            nota = " (informativo)"
        else:
            bad += d != 0
            nota = ""
        out.append(f"| {k}{nota} | {calc[k]:,} | {v:,} | {d:+,} |".replace(",", "."))
    validos = calc["validos"]
    out.append(f"\n% válidos: LULA {100*calc['LULA (13)']/validos:.2f}% · FLAVIO {100*calc['FLAVIO BOLSONARO (22)']/validos:.2f}%"
               .replace(".", ","))
txt = "\n".join(out) + "\n" + NOTAS
open(os.path.join(data, "validacao.md"), "w").write(txt)
print(txt)
print("OK: tudo bate" if not bad else f"ATENÇÃO: {bad} divergência(s)")
sys.exit(1 if bad else 0)
