# Transferência de votos 1º → 2º turno (Presidente 2026)

Sankey que decompõe o ganho de votos de **13 (Lula)** e **22 (Flávio Bolsonaro)** entre os turnos, com filtros de UF,
município e hora de fechamento da urna.

Antes do Sankey, duas barras 100%: votos de 13 × 22 no 2º turno (% dos nominais; brancos/nulos à parte) e o
split do ganho líquido entre 13 e 22. Se um ganho for negativo no recorte, a barra usa |ganho| com a perda listrada e um aviso.

**Metodologia.** Somente seções com boletim nos dois turnos (499.205; 1 seção do exterior só tem 1º turno e fica de fora).
Em toda urna, `comparecimento = nominais + brancos + nulos`. Subtraindo 1º do 2º turno, para qualquer conjunto de seções:

```
ganho13 + ganho22 = Δcomparecimento − Δbrancos − Δnulos + votos_1t_dos_eliminados
```

Termos positivos viram fontes (esquerda), negativos viram destinos (direita: "queda do comparecimento",
"aumento de brancos", "perda do candidato X"), então bruto (Σ fontes) = líquido (Σ destinos) sempre.
É atribuição aritmética agregada: **não** diz como cada eleitor votou (falácia/inferência ecológica).
"Sem classificação" não existe no banco (só nominal/branco/nulo); o nº 28 (votos nominais no BU, nulos no oficial)
entra entre os eliminados com asterisco.

**Hora de fechamento**: `hour(dt_encerramento)` do BU do **2º turno**, em hora local da urna. A página também oferece
"Brasília", convertendo com fuso estimado por município (`8 − moda(hour(dt_abertura))`, já que as urnas abrem às 8h de
Brasília); exterior (ZZ) fica "sem hora" nesse modo.

**Validações** (o script falha se não passarem): 2º turno Lula 64.256.232 e Flávio 59.826.041 (= oficial);
identidade fecha em cada agrupamento; soma por candidato = `outros_1t`.

```bash
python gerar_dados.py [--db ../../totalizacoes/data/db/eleicoes2026.duckdb] [--out dados.json]
./publicar-herenow.sh   # publica index.html + dados.json no here.now (chave lida de ~/.herenow/credentials)
```
