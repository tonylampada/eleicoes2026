# Totalizações das Eleições 2026 por seção — Parquet + DuckDB

Banco de dados consultável com **todos os votos, de todos os cargos, por seção eleitoral**, do
1º turno (04/10/2026) e do 2º turno (25/10/2026), montado a partir dos **boletins de urna (BU)
publicados pelo TSE** no Portal de Dados Abertos. Formato: Parquet (zstd) particionado por
turno/UF + arquivos DuckDB prontos para consulta.

> Os votos de presidente somados aqui batem **exatamente** com o resultado oficial do TSE
> nos dois turnos (2º turno: LULA 64.256.232 = 51,79% × FLAVIO BOLSONARO 59.826.041 = 48,21%).
> Detalhes em [`validacao.md`](validacao.md).

## O que tem aqui

| caminho | o que é | no git? |
|---|---|---|
| `scripts/download.py` | baixa os zips `buweb` do TSE (retomável, confere SHA-512, manifesto) | sim |
| `scripts/build_parquet.py` | CSV → Parquet tipado por turno/UF (retomável) | sim |
| `scripts/build_db.py` | Parquet → `eleicoes2026.duckdb`, versão compacta | sim |
| `scripts/validate.py` | confere presidente × números oficiais do TSE | sim |
| `consultas_exemplo.sql` | consultas de exemplo (todas testadas) | sim |
| `fontes_manifest.json` | URL, versão, bytes e SHA-512 de cada arquivo-fonte | sim |
| `dist/majoritarios_secao.parquet` | **compacto**: presidente+governador+senador por seção | sim, **Git LFS** |
| `dist/eleicoes2026_compacto.duckdb` | **compacto** em DuckDB, com tabelas agregadas | sim, **Git LFS** |
| `data/raw/` | zips brutos do TSE (5,2 GB) | não (`.gitignore`) |
| `data/parquet/votos_secao/` | Parquet completo, todos os cargos (339 MB) | não — reconstrua |
| `data/db/eleicoes2026.duckdb` | banco completo (477 MB) | não — reconstrua |

## Como rodar do zero

Requisitos: Python 3.9+, `curl`, `unzip`, ~12 GB livres em disco (5,2 GB de zips + CSV
temporário de até 8,3 GB, um por vez; ou ~9 GB com `BUILD_FLAGS=--delete-raw`).

```bash
cd totalizacoes
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
make all          # = make download && make build && make db
# sem make:  ./run.sh all   (ou ./run.sh download | build | db | validate | dist | sizes)
```

Variáveis úteis: `DATA=/outro/disco` (onde ficam os dados), `JOBS=4` (downloads paralelos),
`MEM=3GB` e `THREADS=6` (limites do DuckDB), `BUILD_FLAGS=--delete-raw` (apaga cada zip depois
de convertido, para pouco disco).

Tempos medidos neste box (8 vCPU, 16 GB RAM, rede de datacenter), em 28/10/2026:

| etapa | tempo |
|---|---|
| `download` (56 zips, 5,2 GB) | ~25 s (a CDN do TSE estava rápida; em banda doméstica conte minutos a horas) |
| `build` (32,4 GB de CSV → 339 MB de Parquet) | ~10 min (SP 1º turno sozinho: ~3,5 min) |
| `db` (bancos + compacto + validação) | ~40 s |
| **`./run.sh all` do zero, num diretório vazio** | **10 min 53 s**, validação OK, `majoritarios_secao.parquet` byte a byte idêntico (mesmo SHA-256) |

### Como retomar

Tudo é idempotente — se algo parar no meio, **rode o mesmo comando de novo**:

- **download**: cada arquivo baixa para `<nome>.zip.part` com `curl -C -` (HTTP Range), então
  um download interrompido continua do byte onde parou. Só vira `.zip` depois de conferir o SHA-512
  publicado pelo TSE (`.zip.sha512`). Arquivos já íntegros são pulados. Se o hash não bater, refaz
  do zero (até 3 tentativas). O estado de cada arquivo fica em `data/manifest.json`
  (`estado: ok | baixando | erro`, bytes, sha512, versão, data).
- **build**: cada partição `turno=N/uf=XX` ganha um `_OK.json` (fonte, SHA-512 da fonte, nº de linhas,
  soma de votos). Partições com marcador válido são puladas; a escrita é atômica (`.tmp` + rename).
  Se o TSE publicar uma versão nova de uma UF, o SHA-512 muda e só aquela partição é refeita.
- **db**: reconstruído em `.tmp` e trocado no final; só refaz se algum Parquet for mais novo
  (`--force` para obrigar).

### Escolha de versão

O script consulta a API CKAN (`package_show` e `package_search` do dataset
`resultados-2026-boletim-de-urna`) e, por turno/UF, usa o arquivo com o **carimbo mais recente**
no nome (`bweb_<turno>t_<UF>_<DDMMAAAAHHMM>.zip`). Em 28/10/2026 havia uma versão só por
turno/UF: `051020261403` (1º turno) e `261020260742` (2º turno). Peculiaridade encontrada: no CKAN,
o recurso do zip de **RR 2º turno** aparece duplicado como `.sha512` (sem o `.zip`); o script deriva a
URL do zip a partir do `.sha512` e funcionou. `package_show` às vezes devolve só os 56 recursos do 1º
turno (cache); por isso o script une os dois endpoints.

## Fonte dos dados

- Dataset: <https://dadosabertos.tse.jus.br/dataset/resultados-2026-boletim-de-urna>
  (API: `https://dadosabertos.tse.jus.br/api/3/action/package_search?q=name:resultados-2026-boletim-de-urna`)
- Arquivos: `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/buweb/bweb_{1t,2t}_<UF>_<versão>.zip`
  — 28 "UFs" por turno: 26 estados + DF + **ZZ (exterior)**. Todas têm 2º turno (presidente é
  nacional); nas UFs com 2º turno de governador o arquivo traz também o cargo 3.
- Cada zip tem um CSV (Latin-1, `;`, tudo entre aspas, `#NULO#` = vazio, `-1` = nulo numérico) e o
  `_leiame-boletimurnaweb.pdf` com o dicionário. Granularidade: **uma linha por seção × cargo × votável**
  (candidato, legenda, branco, nulo), com os dados da urna (aptos, comparecimento, horários, nº da urna,
  códigos de carga). É o conteúdo do BU impresso, não o arquivo binário `.bu`.
- **Não** usamos os pacotes `arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_*` (BU binário, imagem do BU,
  logs, RDV; BA 9,2 GB) — não são necessários para totalização.
- Download feito em **28/10/2026, 21:57 (BRT, UTC−3)**. Os zips de BA e CE do 1º turno foram reaproveitados
  de um download anterior (23/10/2026) e conferidos contra o SHA-512 do TSE.

Hashes SHA-512 de todos os 56 arquivos-fonte: [`fontes_manifest.json`](fontes_manifest.json) (tabela no fim).

## Tamanhos reais

| artefato | tamanho | linhas |
|---|---:|---:|
| zips brutos TSE (56) | 5,22 GB | — |
| CSVs descompactados | 32,4 GB (1t 31,5 GB; 2t 0,92 GB) | 69.947.081 |
| **Parquet completo** `votos_secao/` (zstd 9, 56 partições) | **339 MB** (1t 312 MB; 2t 28 MB) | 69.947.081 |
| **`eleicoes2026.duckdb`** (completo, normalizado + agregados) | **477 MB** | — |
| **`majoritarios_secao.parquet`** (pres+gov+sen, zstd 19) | **37 MB** | 14.252.760 |
| **`eleicoes2026_compacto.duckdb`** | **117 MB** | — |

A estimativa inicial era 1,5–3 GB para todos os cargos por seção; o real ficou **~5–10× menor**:
ordenando por cargo/município/zona/seção, quase todas as colunas viram runs repetidos
(dicionário + RLE), e o Parquet fica ~1% do CSV. (Antes de normalizar, um DuckDB com a tabela
larga de 45 colunas tinha 1,77 GB.)

## Esquema

### Parquet completo — `data/parquet/votos_secao/turno=<1|2>/uf=<UF>/data.parquet`

Todas as 45 colunas do CSV, com nomes em minúsculas e tipadas (`DATE`, `TIMESTAMP`, inteiros); o
cargo vira `cd_cargo`/`ds_cargo`. Ordenado por `cd_cargo, cd_municipio, nr_zona, nr_secao,
cd_tipo_votavel, nr_votavel`. Colunas principais:

`nr_turno, sg_uf, cd_municipio, nm_municipio, nr_zona, nr_secao, nr_local_votacao, cd_cargo,
ds_cargo, nr_partido, sg_partido, nm_partido, cd_tipo_votavel, ds_tipo_votavel, nr_votavel,
nm_votavel, qt_votos, qt_aptos, qt_comparecimento, qt_abstencoes, cd_tipo_urna, ds_tipo_urna,
nr_urna_efetivada, cd_carga_1_urna_efetivada, cd_carga_2_urna_efetivada, cd_flashcard_urna_efetivada,
dt_carga_urna_efetivada, ds_secoes_agregadas, dt_abertura, dt_encerramento, dt_emissao_bu,
dt_bu_recebido, qt_elei_biom_sem_habilitacao, nr_junta_apuradora, nr_turma_apuradora`
(+ metadados constantes: `dt_geracao, hh_geracao, ano_eleicao, cd_pleito, cd_eleicao, ...`).

Códigos: `cd_cargo` 1 Presidente, 3 Governador, 5 Senador, 6 Dep. Federal, 7 Dep. Estadual,
8 Dep. Distrital. `cd_tipo_votavel` 1 Nominal, 2 Branco, 3 Nulo, 4 Legenda (e anulados, se houver).
`nr_votavel` 95 = branco, 96 = nulo. Em 2026 elegem-se 2 senadores (cada eleitor dá 2 votos).

### Banco DuckDB (`eleicoes2026.duckdb` e `eleicoes2026_compacto.duckdb`, mesmo esquema)

| objeto | tipo | grão / conteúdo |
|---|---|---|
| `votos` | tabela | fato enxuto: `nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao, cd_cargo, cd_tipo_votavel, nr_votavel, qt_votos` |
| `votos_secao` | **view** | granular, "amigável": `votos` + nomes de município/candidato/partido + aptos/comparecimento da seção |
| `secoes` | tabela | 1 linha por turno × seção × cargo: aptos, comparecimento, abstenções, tipo de urna, total de votos (no completo também nº da urna, seções agregadas, abertura/encerramento, emissão do BU, biometria) |
| `municipios` | tabela | `sg_uf, cd_municipio, nm_municipio` (inclui cidades do exterior em `ZZ`) |
| `votaveis` | tabela | dimensão turno × UF × cargo × votável: nome, partido |
| `candidatos` | tabela | candidatos e legendas com total de votos; `abrangencia` = BR (presidente) ou UF |
| `partidos` | tabela | `nr_partido, sg_partido, nm_partido` |
| `totais_municipio` | tabela | votos por turno × município × cargo × votável |
| `totais_zona` | tabela | idem por zona eleitoral |
| `totais_candidato_uf` | tabela | votos por turno × UF × cargo × votável + `pct_validos` (nominal+legenda) |
| `totais_presidente_br` | view | resultado nacional de presidente por turno |
| `presidente_1t_2t_secao` | tabela | 1 linha por seção: aptos, comparecimento, LULA/FLAVIO/outros/brancos/nulos no 1º e no 2º turno, `delta_margem_lula` = (Lula−Flávio)₂ − (Lula−Flávio)₁, `tem_1t`, `tem_2t` |
| `cargos` | view | cargos presentes por turno |

O compacto tem só os cargos 1, 3 e 5 (presidente, governador, senador). Os arquivos `.duckdb` são
gravados com `STORAGE_VERSION 'v1.4.0'` e abrem com DuckDB ≥ 1.4 (testado com 1.5.6 e 2.0.0).

## Consultas de exemplo

Abra com `duckdb dist/eleicoes2026_compacto.duckdb` (ou `data/db/eleicoes2026.duckdb`) ou em Python
`duckdb.connect('...', read_only=True)`. Todas estão em [`consultas_exemplo.sql`](consultas_exemplo.sql)
e foram executadas contra o banco completo (a 9 precisa do completo; as demais rodam nos dois).

```sql
-- 1. Resultado nacional de presidente nos dois turnos
SELECT * FROM totais_presidente_br;

-- 2. Presidente 2º turno por UF (% dos válidos de Lula)
SELECT sg_uf,
       sum(votos) FILTER (WHERE nr_votavel = 13) AS lula,
       sum(votos) FILTER (WHERE nr_votavel = 22) AS flavio,
       round(100.0 * lula / (lula + flavio), 2) AS pct_lula
FROM totais_candidato_uf WHERE nr_turno = 2 AND cd_cargo = 1
GROUP BY sg_uf ORDER BY pct_lula DESC;

-- 3. Votos de presidente por município (2º turno), os 10 maiores colégios
SELECT sg_uf, nm_municipio,
       sum(votos) FILTER (WHERE nr_votavel = 13) AS lula,
       sum(votos) FILTER (WHERE nr_votavel = 22) AS flavio,
       sum(votos) AS total
FROM totais_municipio WHERE nr_turno = 2 AND cd_cargo = 1
GROUP BY ALL ORDER BY total DESC LIMIT 10;

-- 4. Seções com maior virada a favor de Lula entre 1º e 2º turno
SELECT sg_uf, nm_municipio, nr_zona, nr_secao,
       lula_1t, flavio_1t, outros_1t, lula_2t, flavio_2t, delta_margem_lula
FROM presidente_1t_2t_secao WHERE tem_1t AND tem_2t
ORDER BY delta_margem_lula DESC LIMIT 10;   -- ASC para as maiores viradas pró-Flávio

-- 5. Votos de terceiros no 1º turno × ganho de cada lado no 2º, por seção
SELECT round(corr(outros_1t, lula_2t - lula_1t), 3)     AS corr_outros_ganho_lula,
       round(corr(outros_1t, flavio_2t - flavio_1t), 3) AS corr_outros_ganho_flavio,
       sum(lula_2t - lula_1t) AS ganho_lula, sum(flavio_2t - flavio_1t) AS ganho_flavio,
       sum(outros_1t) AS outros_1t
FROM presidente_1t_2t_secao WHERE tem_1t AND tem_2t;

-- 6. Municípios onde o vencedor de presidente mudou do 1º para o 2º turno
WITH m AS (
  SELECT nr_turno, sg_uf, cd_municipio, any_value(nm_municipio) AS nm_municipio,
         arg_max(nm_votavel, votos) AS vencedor
  FROM totais_municipio WHERE cd_cargo = 1 AND cd_tipo_votavel = 1 GROUP BY ALL)
SELECT a.sg_uf, a.nm_municipio, a.vencedor AS vencedor_1t, b.vencedor AS vencedor_2t
FROM m a JOIN m b USING (sg_uf, cd_municipio)
WHERE a.nr_turno = 1 AND b.nr_turno = 2 AND a.vencedor <> b.vencedor
ORDER BY a.sg_uf, a.nm_municipio;

-- 7. Governador: dois mais votados por UF em cada turno
SELECT nr_turno, sg_uf, nm_votavel, sg_partido, votos, pct_validos
FROM totais_candidato_uf WHERE cd_cargo = 3 AND cd_tipo_votavel = 1
QUALIFY row_number() OVER (PARTITION BY nr_turno, sg_uf ORDER BY votos DESC) <= 2
ORDER BY sg_uf, nr_turno, votos DESC;

-- 8. Os 2 senadores mais votados por UF
SELECT sg_uf, nm_votavel, sg_partido, votos
FROM totais_candidato_uf WHERE nr_turno = 1 AND cd_cargo = 5 AND cd_tipo_votavel = 1
QUALIFY row_number() OVER (PARTITION BY sg_uf ORDER BY votos DESC) <= 2
ORDER BY sg_uf, votos DESC;

-- 9. Deputados federais mais votados do Brasil (só no banco completo)
SELECT sg_uf, nm_votavel, sg_partido, votos
FROM totais_candidato_uf WHERE cd_cargo = 6 AND cd_tipo_votavel = 1
ORDER BY votos DESC LIMIT 15;

-- 10. Maiores taxas de abstenção no 2º turno (municípios com 10 mil+ aptos, sem exterior)
SELECT sg_uf, nm_municipio, sum(qt_aptos) AS aptos, sum(qt_comparecimento) AS comparecimento,
       round(100 - 100.0 * sum(qt_comparecimento) / sum(qt_aptos), 2) AS pct_abstencao
FROM secoes WHERE nr_turno = 2 AND cd_cargo = 1 AND sg_uf <> 'ZZ'
GROUP BY ALL HAVING sum(qt_aptos) >= 10000
ORDER BY pct_abstencao DESC LIMIT 10;

-- 11. Granular: presidente numa seção específica, nos dois turnos
SELECT nr_turno, nm_votavel, sg_partido, qt_votos, qt_aptos, qt_comparecimento
FROM votos_secao
WHERE sg_uf = 'SP' AND nm_municipio = 'SÃO PAULO' AND nr_zona = 1 AND nr_secao = 1 AND cd_cargo = 1
ORDER BY nr_turno, qt_votos DESC;

-- 12. Direto do Parquet, sem banco (a partir de totalizacoes/)
SELECT nr_turno, ds_cargo, count(*) AS linhas, sum(qt_votos) AS votos
FROM read_parquet('data/parquet/votos_secao/*/*/data.parquet', hive_partitioning = true)
WHERE uf = 'RJ' GROUP BY ALL ORDER BY ALL;
```

## Validação

`make validate` soma os votos de presidente por seção e compara com o painel oficial do TSE
(resultados.tse.jus.br, 100% das 499.248 seções). Resultado (ver [`validacao.md`](validacao.md)):

- **Bate exatamente nos dois turnos**: votos de cada candidato (todos os 12 do 1º turno), brancos,
  nulos e comparecimento.
- Diferenças conhecidas: (a) no 1º turno os BUs têm 5.246 votos para o nº 28 (LEONARDO AVALANCHE),
  que não figura entre os 12 candidatos do painel oficial — sem eles os válidos batem
  (119.300.788); (b) há 499.206 BUs (1t) / 499.205 (2t) contra 499.248 seções do painel —
  seções não instaladas/agregadas não têm BU próprio; (c) aptos no 2º turno: −525 (423 são eleitores
  de seções não instaladas, informados pelo painel; 102 não explicados).
- Durante o build, cada partição confere nº de linhas do CSV (contagem independente de `\n`) =
  nº de linhas do Parquet.

Cuidado encontrado: o leitor de CSV **paralelo** do DuckDB 2.0 falhou de forma não determinística no
CSV de SP 1º turno (8,3 GB; "unterminated quote" em linhas diferentes a cada execução, embora todas
as 17,9 milhões de linhas tenham 45 campos). O script detecta e refaz automaticamente com
`parallel=false`.

## Hospedagem dos dados no GitHub (Git LFS)

Regras atuais do GitHub (consultadas em 28/10/2026):

- Arquivo comum no git: aviso acima de 50 MiB, **bloqueio acima de 100 MiB**; repositório
  idealmente < 1 GB, fortemente recomendado < 5 GB
  ([docs](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)).
- **Git LFS, plano Free/Pro: 10 GiB de armazenamento + 10 GiB de banda por mês grátis**; arquivo
  máximo de 2 GB (Team 4 GB, Enterprise 5 GB). Os antigos "data packs" pré-pagos foram extintos: agora é
  cobrança medida — US$ 0,07/GiB·mês de armazenamento e US$ 0,0875/GiB de banda além da cota. Sem
  meio de pagamento (ou orçamento US$ 0), o excesso não é cobrado: o LFS fica bloqueado até o mês
  seguinte. Downloads/clones de qualquer pessoa contam na banda do **dono** do repositório
  ([billing](https://docs.github.com/en/billing/concepts/product-billing/git-lfs),
  [limites](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage),
  [calculadora](https://github.com/pricing/calculator)).
- **Releases**: até 1000 assets por release, **cada arquivo < 2 GiB, sem limite de tamanho total nem de
  banda** e sem consumir cota de LFS
  ([docs](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)).
- Plano Free: repositórios privados ilimitados ([pricing](https://github.com/pricing)).

O que está versionado: só a **versão compacta** em `dist/` via LFS (`.gitattributes` na raiz:
`*.parquet` e `*.duckdb`), ~154 MB — 1,5% da cota grátis de armazenamento; cada clone completo
gasta ~154 MB de banda (≈ 65 clones/mês na cota grátis). Para clonar só os scripts:
`GIT_LFS_SKIP_SMUDGE=1 git clone ...` e depois `git lfs pull --include "totalizacoes/dist/*.parquet"`.

Para os dados completos (Parquet 339 MB e DuckDB 477 MB) a recomendação é **GitHub Release**
(grátis, cada arquivo bem abaixo de 2 GiB, banda sem cota) — ou simplesmente reconstruir com
`make all` (~11 min).

## Tabela de arquivos-fonte (SHA-512 conferido contra o `.sha512` do TSE)

<details><summary>56 arquivos</summary>

| arquivo | turno | UF | versão | bytes | baixado em | sha512 |
|---|---|---|---|---:|---|---|
| bweb_1t_AC_051020261403.zip | 1 | AC | 051020261403 | 16,959,055 | 2026-10-28T21:57 | `c095164588a0ad4f46717e081f51eab226f78365325629124672ba8ea044c8e2266028e8456a9e5188ab763c1556160cc8d175b2aab361c5f81544e393c99ab1` |
| bweb_1t_AL_051020261403.zip | 1 | AL | 051020261403 | 48,253,491 | 2026-10-28T21:57 | `dc4340c5d6ff227b6398bd0ed5416a42fac6f182f5775b236e4e5be6358d9eab82ded3ecfe33c8326f0a4caee38bd048635e8f14aff8893fe498de6c641e2b7f` |
| bweb_1t_AM_051020261403.zip | 1 | AM | 051020261403 | 77,017,934 | 2026-10-28T21:57 | `143619aaf27787f27435bc6b78961d289ac0bc9ec6683a678cc319fa1d68eef0611aad9e608d7493a100bafe83f46516e3155dc4b3e62717c5870fb992239f5d` |
| bweb_1t_AP_051020261403.zip | 1 | AP | 051020261403 | 16,659,046 | 2026-10-28T21:57 | `bd40faf189a3ba0462d8efc73216bf60480fda36b3e7d6e144b49d05e54e0415494d06a7858ccf4926cd2570059cdf6518b976e6129c243f44cb9708107b0769` |
| bweb_1t_BA_051020261403.zip | 1 | BA | 051020261403 | 324,997,821 | (cópia local ver | `8fc0b0c6e926af2c9554de33d5ed1f7c4d376cc2e1655970e78aa8498c71c7caef3d4a4adfcc2f3c4989c9783d2917f8478404a9789bcccbb9bdc366a8024e5e` |
| bweb_1t_CE_051020261403.zip | 1 | CE | 051020261403 | 203,005,857 | (cópia local ver | `0ac4f8dbcd6eb06ed3e67b71d64fdb36909a885da32e765c9ae966c02ed48dcee57f82b3a95dfa3b1dd586e7f057ed556a991fe9e2dc4ae117e72caa2359fabf` |
| bweb_1t_DF_051020261403.zip | 1 | DF | 051020261403 | 77,026,962 | 2026-10-28T21:57 | `10916bdfc73018dab34d21dbb1f7fa49d33921a6d8de9e283a2b4b6d8d7ce6c02af4e5cff948f17cab726195b372ee84f2177ab5756dff04e0f2d71c759d4572` |
| bweb_1t_ES_051020261403.zip | 1 | ES | 051020261403 | 81,978,606 | 2026-10-28T21:57 | `fb3dc71fccd1528f091ead2caa11a6182e25d581aaaf565519bcd6884e5827d868a60dad74a77df51593a2bcba692a0bc4dc777e6fa6782a27cf19782d8c7f31` |
| bweb_1t_GO_051020261403.zip | 1 | GO | 051020261403 | 157,210,218 | 2026-10-28T21:57 | `995aa51719659a4f22f4e9a9a904f545be3e57112fd204ca35dc697a76950222c244477284b28fb74bde65d45df3f20855f2c40fe436f33afc885917fc73c394` |
| bweb_1t_MA_051020261403.zip | 1 | MA | 051020261403 | 142,453,462 | 2026-10-28T21:57 | `28eda5cc72f2d7f29b32282e72461fd93baa7f4da430e1f624128aeb3d83326f25b26efda431c2669e9a23d9d9b76a8f62e27f7a616b54ae5f8e1630a1775134` |
| bweb_1t_MG_051020261403.zip | 1 | MG | 051020261403 | 489,306,781 | 2026-10-28T21:57 | `c0d4a82adb1fa1c89447c8a19448c588bad2597d4509c04a1b1671b835b9160e9c835091b1000180d1ad3a329dd36ce3bee1d57f4589a4e96d8c2601a99a80c6` |
| bweb_1t_MS_051020261403.zip | 1 | MS | 051020261403 | 51,978,602 | 2026-10-28T21:57 | `e62c150f16fff1a4e6a08ba36e3f7d5b3820a01bb2cf5131df8426c462bb8edac5cb01584770271e356a9e56a8f2d59edf7516f795ce955928b53e3a853361a4` |
| bweb_1t_MT_051020261403.zip | 1 | MT | 051020261403 | 63,492,478 | 2026-10-28T21:57 | `0b97fc665251f8a82d5b43938245bbc2b39b680c6053626abf5d94cc67b0105aed3d3c9bc97a6366507e7e409d81b8d5c1f5c15b2f95542e8d6e3e788818ab1d` |
| bweb_1t_PA_051020261403.zip | 1 | PA | 051020261403 | 172,050,487 | 2026-10-28T21:57 | `7ec84395ef9ce10fcfeedc9236b9fb93de80d7d278b56b074d0538009ed53e4fff695a627dd848028e91ef8cd1a5a36a1e6fe2318b0adac909c741739371d788` |
| bweb_1t_PB_051020261403.zip | 1 | PB | 051020261403 | 77,916,707 | 2026-10-28T21:57 | `22784224b1e752b10371a22cc5cdb381b78c9a3b694da02a71867db116adf39d6b08e52f9cd69888fa708c2be12a3a35d24acf78a3b2f601e2c98561ae496812` |
| bweb_1t_PE_051020261403.zip | 1 | PE | 051020261403 | 204,972,135 | 2026-10-28T21:57 | `8d01dd88ba42adf623d3ec23a934691b3cd9ae4e90a7093877592d425d5f79aafc20f1cc419e9de73265116f1c908555c7c8b42015b1f72dadb4a09378da7cfa` |
| bweb_1t_PI_051020261403.zip | 1 | PI | 051020261403 | 66,216,824 | 2026-10-28T21:57 | `c77cafd73117432124f789dc75fcb2401338a82dfae707ea4626639c980c318c25555b53fd5a2ad3604aec8bce76012de3ef7102c0cd9e1460b1d7f8f05f8c8a` |
| bweb_1t_PR_051020261403.zip | 1 | PR | 051020261403 | 270,246,858 | 2026-10-28T21:57 | `762372bbafff59673da579e81a31536fe990b90e81dd92277af12e395dcb23784e7b6eccdb8826b214c9772edf997bd6747ff8ab87bd40b17049bafca1c5b10b` |
| bweb_1t_RJ_051020261403.zip | 1 | RJ | 051020261403 | 536,375,038 | 2026-10-28T21:57 | `15fec8c7104496cb39379030cf3fc732801e80405fe0efac7985164bdf72a5decdac3a34ae3fcd7d39e44a9be12674bc5961685a67a9d1c0c38c0c7e1d45719d` |
| bweb_1t_RN_051020261403.zip | 1 | RN | 051020261403 | 54,412,606 | 2026-10-28T21:57 | `8c306c4501a9c5f9bdaa17f416c07280a24563f68f65d64e51843bc0b5377bacd534417396200772c471e412f9e4981273432f104ee1e2f7f3681399fd95b820` |
| bweb_1t_RO_051020261403.zip | 1 | RO | 051020261403 | 36,216,443 | 2026-10-28T21:57 | `883b0c3cdf8047d9776b2409abecc0ed287a8a6a7f3657a860701a2b9999664a8a6c8012db96238ed1476899120dd2dc62167a3e8924e9d4b1db686c2302fcaf` |
| bweb_1t_RR_051020261403.zip | 1 | RR | 051020261403 | 11,931,936 | 2026-10-28T21:57 | `4cde1919c20ba0940a9b5fc83422e93248b28fb494510205ae3862b61340a9e8d5d297444af84618c84ec7bb7f1dbc7c487b51e22377c3cde3f71bc39a8dc5c6` |
| bweb_1t_RS_051020261403.zip | 1 | RS | 051020261403 | 270,859,776 | 2026-10-28T21:57 | `b6dd056af20ce8768b2a439b1929102a077f0931f966c5314f706b4c98eb6e39549f8b143aee3808c22490a9d9e3f7dc24af925ea421fa1ae2d896283ff45732` |
| bweb_1t_SC_051020261403.zip | 1 | SC | 051020261403 | 153,178,332 | 2026-10-28T21:57 | `618c1cacf80bc2964d3bb5e6274ba3e2adeed853077083bc01004e5110e79615868cf3c39b490e283c181c716275d4473da35d11f407111f4170fc91a8a93db7` |
| bweb_1t_SE_051020261403.zip | 1 | SE | 051020261403 | 46,931,962 | 2026-10-28T21:57 | `dd1afedc6867ca7828becbe52178cda4e9104d2966fd3cad8c28d4f4ff7c86270dcc5c24cb3904b02a0f0f5a4f7308bb2b7d9f9d60775092f55de136204b9d40` |
| bweb_1t_SP_051020261403.zip | 1 | SP | 051020261403 | 1,395,007,777 | 2026-10-28T21:57 | `00c8b12de9077c8263c87ba91d1300e230719bd1ad27e7f37131478d8e3b4bc9c66b727b3e30c73c89799e136c329db45b85e6d037874ea8fa166d74f26ca403` |
| bweb_1t_TO_051020261403.zip | 1 | TO | 051020261403 | 29,667,347 | 2026-10-28T21:57 | `b936b450693c00741226bd1b6c09843c6671e41abafa393ef31606a7038272011b9030ec8d62a8f61d7ff31f532b7979321cac456bef3b44925e0b00026bc614` |
| bweb_1t_ZZ_051020261403.zip | 1 | ZZ | 051020261403 | 1,039,125 | 2026-10-28T21:57 | `001ae12d79a7d5f9471c0a8bb3e09b5cb6633be598683db74b0ab08c0002f2c764cb9fde9c0470c6414985ce47cd01b00c343438d9c914f3f792a1975b400a55` |
| bweb_2t_AC_261020260742.zip | 2 | AC | 261020260742 | 1,254,611 | 2026-10-28T21:57 | `95f19aad9534d21ea703670030ea1d51b5a89c2b40f3ba5466d60de2765b9067f225fd863000c282fe47fb6457a9f43df5fd536dec7753f3813667c99b3efa3b` |
| bweb_2t_AL_261020260742.zip | 2 | AL | 261020260742 | 1,945,168 | 2026-10-28T21:57 | `392ebb110ac066be0bc1113b1cd4f15feadac11deb97c1786a2a9bc824affa5abce5fdfad051a6a3d4bf2b42909ba4b27b87af586dc888c17f8319401b24a848` |
| bweb_2t_AM_261020260742.zip | 2 | AM | 261020260742 | 4,276,454 | 2026-10-28T21:57 | `c87f558d88f478afaed40d452855e34eb99772fb4214b2c913824fd5adb816d324c6c040ab35d5e17e953e0d752b882c27304bd3c9139a9f96a765e2356c5ce8` |
| bweb_2t_AP_261020260742.zip | 2 | AP | 261020260742 | 596,704 | 2026-10-28T21:57 | `66f56ba91e90cd715994bba078014e57a9124e5667d5047b84cedeaf67dfbfc86a0c85537d65c49810817a73d0eaab6222fecdbb57d9077cc6a1da18a6d21cd6` |
| bweb_2t_BA_261020260742.zip | 2 | BA | 261020260742 | 9,513,048 | 2026-10-28T21:57 | `15db0c47b3b445ccbc1dd15ef77291e1bb5fe1af20a3e444381f7c32057794ed97e0c901cb46ea09cc7172a5d3d25cfe6435910e3f3fbdb8479c0c599f46e5c3` |
| bweb_2t_CE_261020260742.zip | 2 | CE | 261020260742 | 6,151,144 | 2026-10-28T21:57 | `4d0abf43322e353074782f533a728513924e7820898b8b3ef1ebbe45771dd61504e031f0efc62071442632669a11e1523890b5b49a196a04cc25884124e76357` |
| bweb_2t_DF_261020260742.zip | 2 | DF | 261020260742 | 3,846,786 | 2026-10-28T21:57 | `204e65d5d3eff30f7bbb27f3f21547d0146da31edaf15c27848452a245462144e2bf53ba520a0dfc09493231f2a43218d967cda1b6633af112ef3b1ac1a6c823` |
| bweb_2t_ES_261020260742.zip | 2 | ES | 261020260742 | 5,275,706 | 2026-10-28T21:57 | `e8805337ab66ffa5effea88a28ce74cc0fe1e856bcf58c2dad09f71cc04837d2113830aa6e1f4a4a17c14d1092a2cc2a6d88d578f64780e0a99627c0912f8883` |
| bweb_2t_GO_261020260742.zip | 2 | GO | 261020260742 | 4,248,869 | 2026-10-28T21:57 | `e5b6635dc3a05b7f6c175bdbe8a23e4daa3f4029f79cf3b7c82ac2cc48a43c315b00cac68162dd134f3187ba973bd3ddea5a26cb6f91c44449945bb094f93e0e` |
| bweb_2t_MA_261020260742.zip | 2 | MA | 261020260742 | 4,609,442 | 2026-10-28T21:57 | `90c1c9d2d1d0635c9e6900ee51dbb81b4a1f2dee113ed3a5145a2dacbe8d2da97bec55c78caa74fb635412cd29c413f2204a05d22ae6e0516ef249811c9d075c` |
| bweb_2t_MG_261020260742.zip | 2 | MG | 261020260742 | 14,071,007 | 2026-10-28T21:57 | `b2123700c7a520ccfb0e1be9aa3bab205c9c5f5b64cd537c80a1eaca69a9b96a67c440c88ca2a0f30f63aeed72a1c9dfca0e5ede8358eca1c64698e0c8054bb9` |
| bweb_2t_MS_261020260742.zip | 2 | MS | 261020260742 | 1,863,398 | 2026-10-28T21:57 | `c16d211246f35c9d1e7dfef39e6f718522987873d5304144744d9ba98783320710060844ca212800204c53d144d7cdea777aead343d817033fb5b49ada518db1` |
| bweb_2t_MT_261020260742.zip | 2 | MT | 261020260742 | 2,204,666 | 2026-10-28T21:57 | `cf0e1bf1c0af0af4326e9db2532d8ae0f3d28287d0c5ba48229e484696ef27d4e848922f73b1b7126847d2841b3bdea5ee36327c12a23d207860549640c5ce72` |
| bweb_2t_PA_261020260742.zip | 2 | PA | 261020260742 | 5,158,441 | 2026-10-28T21:57 | `5908978e998fc61b505c42971b3a29c7ffd858624e64b864e1c8dc8248172373bb59f5be3d27ad1d93703c73d9b11bc836eb9875c55180470b6e68061d773d9e` |
| bweb_2t_PB_261020260742.zip | 2 | PB | 261020260742 | 2,871,353 | 2026-10-28T21:57 | `79ec2b52387a8a1ac6f71cc330b54ce97fbefa49dfb925c15daa32e1f4a466cfd65c67eeef7e064d41231504afe5573d0fcd1a906b2856ad04dee0000ac15c7f` |
| bweb_2t_PE_261020260742.zip | 2 | PE | 261020260742 | 5,761,723 | 2026-10-28T21:57 | `5002c264cf9fff1b27bbbbc75d89b5aec5856b59a2888fef2b8c1577fe041bf60bcd6a4d8943023382579921d7f89926608aa7e550beb8581718cea1873f645a` |
| bweb_2t_PI_261020260742.zip | 2 | PI | 261020260742 | 2,648,710 | 2026-10-28T21:57 | `d864c6f671daf94d0c3a8464b74052f1827fe6ac43a7666bc1d4cd37f3a4375ccb51ccc83ef04832487349a40e1d73b72e2ab0934b99d62465422b80c4499b54` |
| bweb_2t_PR_261020260742.zip | 2 | PR | 261020260742 | 7,189,112 | 2026-10-28T21:57 | `949659949df4605749afdd1842d0f628bb4563d41f73578786702f679ee81276d7a4f5a4e52fe5292e681a75a7662d7925c1a15e76f0118b5870c29dbd20b3f5` |
| bweb_2t_RJ_261020260742.zip | 2 | RJ | 261020260742 | 10,004,912 | 2026-10-28T21:57 | `dcb3131b618b9c394b50576ead626a85ebb115c9f984f9b464d21a64eb69a735f11123fb189a3f8b906c29f9511557f46565cc1d4adc10a68fa0ebf69a70a205` |
| bweb_2t_RN_261020260742.zip | 2 | RN | 261020260742 | 4,424,654 | 2026-10-28T21:57 | `3da1a65ad338f6ef0596de91e2c65f8fd1c0ee916c4ed26f2e1c64d4583603caa344482bfbda4e00142926244a79d7df63c1acb52dea56fc83d67b355feaf3a5` |
| bweb_2t_RO_261020260742.zip | 2 | RO | 261020260742 | 1,250,142 | 2026-10-28T21:57 | `4e25932384114f73eacfc0555234fd5cc31f2cde025404f9aed97286879e15571925d544ca83b744d2fe21e5711ec20b4bf7281011007d777b9a354c8fd1b577` |
| bweb_2t_RR_261020260742.zip | 2 | RR | 261020260742 | 500,520 | 2026-10-28T21:57 | `3986628e101b7a9fc24ab5377e0ed8b2eb94fa735b5999aa408df37d3be91d1c4d8ab11c8bec03398dcc0005b76782617a5045cb170e0efafdeabd1602d6d4cf` |
| bweb_2t_RS_261020260742.zip | 2 | RS | 261020260742 | 7,410,270 | 2026-10-28T21:57 | `39f0c7e216972216d52a1868c2396d72115453953227aa301cb92692421c171e5a24e8493a57f125ddf2096a7ea6d6b34ce1aa7a042ef26a4c550e3336a27cee` |
| bweb_2t_SC_261020260742.zip | 2 | SC | 261020260742 | 4,487,185 | 2026-10-28T21:57 | `01b1e9638654fa6914ad4d8a9001de33cb4fc5386d280ccdea7576d7c993c04e9162075db0a1fed8f571e87ce5349151e6a44bc4d5300b3e828a0123c6b90c8e` |
| bweb_2t_SE_261020260742.zip | 2 | SE | 261020260742 | 1,645,477 | 2026-10-28T21:57 | `ea1460385ab222e82ec7560eb3932bb3dc198333296876435d99c2755150ce1a9d703f21ca259279de610f1e31d2dbc8d3a5090c6c3f9e762de8d98f0fd73f0f` |
| bweb_2t_SP_261020260742.zip | 2 | SP | 261020260742 | 28,188,300 | 2026-10-28T21:57 | `3078f38754ced92476fd0e9c6661ecf5237774fc210d5e7eee1b55db9b8ddb321843f591440c2d350679326e1f1b86e60ac723c8ac65a92ca94b74ce674ecffe` |
| bweb_2t_TO_261020260742.zip | 2 | TO | 261020260742 | 2,383,586 | 2026-10-28T21:57 | `e667f9b68bb71065fec219cbf18b4621b0062ced6b09dec227d32f8621c9b6697b55d216bce0920de30eea37c16bc42a3a684d71bdb49051c68d850f1f74b0ef` |
| bweb_2t_ZZ_261020260742.zip | 2 | ZZ | 261020260742 | 502,322 | 2026-10-28T21:57 | `e024547f7d2c6e21e53c8a4f47823d7c76684976271ef395f7c66fe953caf49aa2c585b104f724cc2c39eb67f682e05a7e479f9558c3e38244036a3f90b429f1` |

</details>

Hashes SHA-256 dos artefatos versionados: [`dist/SHA256SUMS`](dist/SHA256SUMS).
