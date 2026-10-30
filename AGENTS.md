# AGENTS.md — eleicoes2026

**O que é:** votos de **todos os cargos, por seção eleitoral**, das Eleições 2026 (1º turno 04/10, 2º turno
25/10), a partir dos boletins de urna (arquivos `buweb`) do TSE, em Parquet + DuckDB. Presidente bate
exatamente com o oficial (2º turno: LULA 64.256.232 × FLAVIO BOLSONARO 59.826.041). Dados e scripts em
[`totalizacoes/`](totalizacoes/) (detalhes em [`totalizacoes/README.md`](totalizacoes/README.md)); análises prontas em
[`micro-analises/`](micro-analises/).

## ATALHO: usar os dados sem reconstruir

```bash
cd totalizacoes
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt   # duckdb>=1.4
./run.sh fetch              # completo (~816 MB, ~11 s em rede rápida)
./run.sh fetch --compacto   # leve: só presidente/governador/senador (~154 MB)
```

- **Sem login:** o repo é público. O script usa `gh` se estiver logado; senão baixa anônimo pela URL direta
  `https://github.com/tonylampada/eleicoes2026/releases/download/dados-2026-10-28/<asset>` com `curl -C -`.
- Baixa os assets do Release [`dados-2026-10-28`](https://github.com/tonylampada/eleicoes2026/releases/tag/dados-2026-10-28),
  confere SHA-256, extrai em `totalizacoes/data/`, é idempotente (rode de novo se cair) e valida no final.
- Resultado:
  - completo: `data/db/eleicoes2026.duckdb` (477 MB) e `data/parquet/votos_secao/turno=<1|2>/uf=<UF>/data.parquet` (339 MB, 69.947.081 linhas)
  - `--compacto`: `data/db/eleicoes2026_compacto.duckdb` (117 MB) e `data/parquet/majoritarios_secao.parquet` (37 MB, 14.252.760 linhas)
- **Não há mais Git LFS**: os dados não estão no git, só no Release. `git clone` normal basta.

## Como usar com um agente de IA

Cole isto no seu agente de código (Cursor, Claude Code, Codex…), trocando o final:

```text
Clone https://github.com/tonylampada/eleicoes2026 e leia o AGENTS.md na raiz. Baixe o banco pronto
com `cd totalizacoes && ./run.sh fetch` (não reconstrua a partir do TSE). Depois <reproduza a análise
micro-analises/transferencia-de-votos | crie uma micro-análise nova sobre: X>, seguindo a convenção de
micro-analises/ (gerar_dados.py → dados.json → index.html + README.md), validando os totais contra o
oficial, e me mostre o resultado.
```

Convenção para novas análises: `micro-analises/<nome>/` com `gerar_dados.py` (lê o DuckDB em modo
somente leitura, aceita `--db`, valida contra o oficial e falha se não bater) → `dados.json` (agregado
pequeno, < 3–5 MB, pode ser commitado) → `index.html` (página única, JS puro, lê `dados.json`) + `README.md`
(o que mostra, metodologia). Publicar a página (here.now, GitHub Pages…) é opcional e fica fora do git:
nunca commite chaves nem arquivos de estado (`.herenow-*`, `.env`). Detalhes em
[`micro-analises/README.md`](micro-analises/README.md).

## Reconstruir do zero (opcional)

`cd totalizacoes && ./run.sh all` (= `download` + `build` + `db`; também `make all`). Baixa 5,2 GB do TSE,
converte 32 GB de CSV. **~11 min** num box de 8 vCPU / 16 GB; precisa de **~12 GB livres** (ou ~9 GB com
`BUILD_FLAGS=--delete-raw`). Retomável: se parar, rode o mesmo comando. `DATA=/outro/dir` muda o destino.

## Esquema (principais)

**DuckDB** (`eleicoes2026.duckdb`; o compacto tem o mesmo esquema, só cargos 1/3/5 e sem as colunas de horário em `secoes`):

- `votos` — fato: `nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao, cd_cargo, cd_tipo_votavel, nr_votavel, qt_votos`
- `secoes` — 1 linha por turno × seção × cargo: `nr_turno, sg_uf, cd_municipio, nm_municipio, nr_zona, nr_secao,
  cd_cargo, nr_local_votacao, qt_aptos, qt_comparecimento, qt_abstencoes, cd_tipo_urna, qt_votos_total,
  nr_urna_efetivada, ds_secoes_agregadas, dt_abertura, dt_encerramento, dt_emissao_bu, dt_bu_recebido,
  qt_elei_biom_sem_habilitacao` (datas = `TIMESTAMP` sem fuso)
- `votos_secao` (view) — `votos` + nomes: `nm_municipio, nr_local_votacao, ds_cargo, ds_tipo_votavel, nm_votavel,
  nr_partido, sg_partido, nm_partido, qt_votos, qt_aptos, qt_comparecimento, qt_abstencoes, cd_tipo_urna`
- dimensões/agregados: `municipios, votaveis, candidatos, partidos, totais_municipio, totais_zona,
  totais_candidato_uf, totais_presidente_br` (view), `presidente_1t_2t_secao`, `cargos` (view)

**Parquet completo** (`votos_secao/…/data.parquet`): as 45 colunas do CSV do TSE em minúsculas e tipadas
(uma linha por seção × cargo × votável), incluindo todas as acima e `ds_tipo_urna, cd_carga_1_urna_efetivada,
cd_flashcard_urna_efetivada, dt_carga_urna_efetivada, nr_junta_apuradora, nr_turma_apuradora`.
Nomes conferidos em `totalizacoes/scripts/build_parquet.py`.

Códigos: `cd_cargo` 1 Presidente, 3 Governador, 5 Senador, 6 Dep. Federal, 7 Dep. Estadual, 8 Dep. Distrital.
`cd_tipo_votavel` 1 nominal, 2 branco, 3 nulo, 4 legenda. `nr_votavel` 13 = LULA, 22 = FLAVIO; 95 branco, 96 nulo.
`sg_uf = 'ZZ'` = exterior.

## Exemplos (DuckDB, testados no banco completo)

```sql
-- duckdb totalizacoes/data/db/eleicoes2026.duckdb   (ou duckdb.connect(..., read_only=True))

-- 1. Presidente 2º turno por UF
SELECT sg_uf, sum(qt_votos) FILTER (nr_votavel = 13) AS lula, sum(qt_votos) FILTER (nr_votavel = 22) AS flavio
FROM votos WHERE nr_turno = 2 AND cd_cargo = 1 AND cd_tipo_votavel = 1
GROUP BY sg_uf ORDER BY sg_uf;

-- 2. Hora de encerramento da urna por UF no 2º turno (hora LOCAL da seção — ver fuso abaixo)
PIVOT (SELECT sg_uf, hour(dt_encerramento) AS hora FROM secoes WHERE nr_turno = 2 AND cd_cargo = 1)
ON hora USING count(*) ORDER BY sg_uf;
-- AC: 2.269 seções às 15h; AM: 7.600 às 16h; SP: 101.894 às 17h, 1.571 às 19h
-- (27 seções do exterior têm dt_encerramento NULL e somem do PIVOT)
```

### Fuso dos horários (`dt_abertura`, `dt_encerramento`, `dt_emissao_bu`, `dt_bu_recebido`)

O `_leiame-boletimurnaweb.pdf` (dentro de cada zip do TSE) **não diz o fuso** dessas colunas; só diz que
`HH_GERACAO` é "horário de Brasília". Pelos dados (2º turno, votação 8h–17h de Brasília em todo o país):

- `dt_abertura` / `dt_encerramento` / `dt_emissao_bu` estão no **horário LOCAL da urna**: AC abre ~6h e fecha
  ~15h; AM/MS/MT/RO/RR ~7h e ~16h; demais UFs 8h e 17h; no exterior (ZZ) Sydney, Paris, Vancouver, Miami…
  todos 08:00 → 17:0x (hora local de cada cidade). Para Brasília, some 2h no AC e 1h em AM/MS/MT/RO/RR (sem
  horário de verão em 2026); no exterior depende do país.
- `dt_bu_recebido` parece estar em **horário de Brasília** (recebimento no TSE): mínimo 17:05:10 em todas as UFs,
  inclusive AC (cujas urnas fecham 15h local), e no exterior 46% dos BUs aparecem "recebidos" antes da emissão.
- É inferência a partir dos dados, não documentação oficial — trate como provável, não garantido.

## Armadilhas conhecidas

- **DuckDB ≥ 1.4** para abrir os `.duckdb` (gravados com `STORAGE_VERSION 'v1.4.0'`; testado 1.5.6 e 2.0.0).
- O leitor de CSV **paralelo** do DuckDB falha de forma intermitente no CSV de SP 1º turno (8,3 GB,
  "unterminated quote"); `build_parquet.py` detecta e refaz com `parallel=false` (SP leva ~3,5 min).
- **Candidato nº 28** (LEONARDO AVALANCHE) tem 5.246 votos nominais no 1º turno no BU, mas não está no painel
  oficial; os "válidos" oficiais excluem esses votos. Filtre se for comparar com o oficial.
- **RR 2º turno**: no CKAN o recurso do zip aparece duplicado como `.sha512`; o `download.py` deriva a URL do zip.
- `package_show` do CKAN às vezes devolve só o 1º turno (cache); o script une com `package_search`.
- Contagem de seções difere do painel (−42/−43): o BU traz uma linha por boletim apurado; seções agregadas em
  `ds_secoes_agregadas`.
- Senado 2026: 2 vagas — cada eleitor dá 2 votos para senador.
- **Git LFS**: não é mais usado. Commits antigos (antes de 29/10/2026) ainda têm `totalizacoes/dist/*` como
  ponteiros LFS; só quem fizer checkout deles precisa de git-lfs. Não commite dados (`data/` está no `.gitignore`).
- Para publicar novos dados: `./run.sh dist` → `gh release create <tag> totalizacoes/data/dist/*` e ajuste `TAG`
  em `totalizacoes/scripts/fetch_release.py`.
