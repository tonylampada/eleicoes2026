# logs-urna — métricas por seção a partir dos logs das urnas (TSE, Eleições 2026)

Cada seção eleitoral tem um **log da urna** (`*-log.jez`, dentro dos zips `bu_imgbu_logjez_rdv_vscmr_2026_<t>t_<UF>.zip`
do TSE): registro com hora, por segundo, de cada passo — urna ligada, abertura, cada eleitor identificado/habilitado,
cada voto computado, encerramento, impressão do BU, alertas e erros. Esta pasta transforma esses logs em
**uma linha por seção** com horários, ritmo dos votos, proximidade entre votos, tipo de habilitação e contagem de
incidentes, mais uma tabela longa de eventos fora da rotina. Os zips (124 GB no 2º turno) não ficam guardados:
cada UF é baixada, agregada em streaming e apagada; ficam só Parquets pequenos (~70 bytes por seção).

**Estado atual:** 2º turno **completo** — 27 UFs + exterior (ZZ): **499.177 seções com log** (de 499.205 seções no
banco principal; 28 sem log publicado: 1 em Guarulhos-SP e 27 no exterior), **128.235.225 votos** no log
(× 128.236.074 de comparecimento no BU), 1.822.179.359 linhas de log do dia lidas. Release:
[`logs-urna-2026-10-29`](https://github.com/tonylampada/eleicoes2026/releases/tag/logs-urna-2026-10-29).
O 1º turno ainda não foi processado (`TURNO=1`).

Tudo é estatística descritiva sobre arquivos públicos. Não substitui o resultado oficial nem indica fraude,
causa ou intenção (ver [Escopo e limites](#escopo-e-limites)).

## Atalho: usar os dados prontos (sem reprocessar)

```bash
cd logs-urna
python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt   # duckdb>=1.4, pyarrow
./run.sh fetch                 # eventos.duckdb (85,2 MB) + Parquets (tar de 38,2 MB), segundos
./run.sh fetch --so-parquet    # só os Parquets
```

- **Sem login.** Usa `gh release download` se o `gh` estiver logado; senão baixa anônimo pela URL direta
  `https://github.com/tonylampada/eleicoes2026/releases/download/<tag>/<asset>` com `curl -C -` (retomável).
- Assets do Release: `SHA256SUMS`, `manifest.json` (origem de cada lote), `eventos_parquet.tar`, `eventos.duckdb`.
- Confere SHA-256, é idempotente (rode de novo se cair) e no fim compara linhas e votos por turno/UF dos Parquets e
  do DuckDB com o `manifest.json`. A tag padrão está em `TAG` em [`scripts/fetch_release.py`](scripts/fetch_release.py)
  (`RELEASE_TAG=... ./run.sh fetch` para outra).
- Resultado: `data/db/eventos.duckdb` e `data/parquet/eventos_{secao,tipo}/turno=<t>/uf=<UF>/data.parquet`.

Juntar com o banco principal (`totalizacoes/`, aberto **somente leitura**): ver [`exemplo_attach.sql`](exemplo_attach.sql).

```sql
-- duckdb data/db/eventos.duckdb
ATTACH '../totalizacoes/data/db/eleicoes2026.duckdb' AS tse (READ_ONLY);
SELECT s.sg_uf, s.qt_comparecimento, e.n_votos_log, e.hr_abertura_log, s.dt_abertura
FROM eventos_secao e JOIN tse.secoes s USING (nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao)
WHERE s.cd_cargo = 1 LIMIT 5;
```

## Reconstruir do zero (opcional)

```bash
./run.sh all                         # = process + db (também: make all). Padrão: TURNO=2 UFS=BA,CE
UFS=TODAS JOBS=8 ./run.sh all        # Brasil inteiro (27 UFs + ZZ)
PROCESS_FLAGS=--keep-zip ./run.sh process   # não apagar os zips
```

| comando | o que faz |
|---|---|
| `./run.sh process` | para cada UF: `HEAD` (tamanho/ETag) → `curl -C -` para `data/raw/*.part` → SHA-256 do zip → lê cada `*-log.jez` direto do zip (sem extrair) em `JOBS` processos → grava Parquet (zstd) → **apaga o zip** → registra no `data/manifest.json` |
| `./run.sh db` | `data/db/eventos.duckdb` (tabelas `eventos_secao`, `eventos_tipo`, `eventos_dicionario`, `lotes`) e `data/validacao.md` (compara com o banco de `totalizacoes/`, se existir) |
| `./run.sh validate` | só a validação contra o BU |
| `./run.sh dist` | assets do Release em `data/dist/` + `SHA256SUMS`; copia `manifest.json` → `fontes_manifest.json` e `validacao.md` para esta pasta |
| `python scripts/gerar_dicionario.py` | `docs/dicionario_eventos_2t.md` |
| `python scripts/inspecionar_eventos.py` | catálogo de TODOS os modelos de mensagem numa amostra de seções (lê só pedaços do zip via HTTP Range) |

**Retomável:** se parar, rode o mesmo comando. UF já processada é pulada quando o ETag e o tamanho do zip no TSE,
a versão do parser e o hash dos Parquets de saída não mudaram (`--force` refaz). Download interrompido continua do `.part`.
Publicar novos dados: `./run.sh dist` → `gh release create <tag> data/dist/*` e ajustar `TAG` em `scripts/fetch_release.py`.

### Custo medido (box de 8 vCPU, 2º turno)

| UF | zip | seções | download | SHA-256 | agregação (parede / CPU) | `eventos_secao` | `eventos_tipo` |
|---|--:|--:|--:|--:|--:|--:|--:|
| BA | 9,21 GB | 35.476 | 47 s (196 MB/s) | 9 s | 76 s / 517 s | 2,43 MB | 0,33 MB (193.951 linhas) |
| CE | 5,91 GB | 23.765 | 168 s (35 MB/s) | 6 s | 41 s / 309 s | 1,63 MB | 0,21 MB (120.164 linhas) |

| **Brasil (27 UFs + ZZ)** | 124,1 GB | 499.177 | 30,7 min (soma) | 2,0 min | 16,3 min / 114 min | 33,7 MB | 4,4 MB (2.540.011 linhas) |

- Brasil inteiro (medido em 29–30/10/2026): soma dos tempos por UF ≈ 49 min (download 30,7 min, SHA-256 2,0 min,
  agregação 16,3 min); maior zip SP, 25,8 GB. `eventos.duckdb`: 85,2 MB; `eventos_parquet.tar`: 38,2 MB.
- BA+CE de ponta a ponta: 5 min 54 s (nesta execução o CDN do TSE variou de 35 a 215 MB/s). `eventos.duckdb`: 11,3 MB.
  Memória: < 350 MB por processo. Disco: só um zip por vez (+ ~0 depois de apagado).
- Por seção: ~69 bytes em `eventos_secao`, ~9 bytes em `eventos_tipo`, ~2 ms de agregação (8 processos).
- O **incremento** guardado é pequeno; o que custa é baixar os zips uma vez.

## Esquema

### `eventos_secao` — 1 linha por turno × seção (74 colunas)

Chave: `nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao` (mesmos tipos/valores de `totalizacoes`).
Todos os horários são `TIME` **do relógio da urna**, sem data e sem fuso (ver [Fuso](#fuso-e-relógio)).
Confiança: **A** = conferido contra o BU em ~100% das seções; **M** = definição própria e consistente, conferida em
parte; **B** = contagem de mensagem, útil para comparar seções, sem validação externa.

| coluna(s) | definição | conf. |
|---|---|:-:|
| `n_votos_log` | mensagens "O voto do eleitor foi computado" com data do dia da eleição, somando todos os logs da seção (urna original + urnas de contingência/substituição, sem duplicar linhas) | A |
| `hr_abertura_log` | 1ª "Urna pronta para receber votos" do dia. Igual ao `dt_abertura` do BU ou 1 s depois | A |
| `hr_encerramento_log` | "Procedimento de encerramento confirmado". Igual ao `dt_encerramento` do BU ou 1 s antes | A |
| `hr_inicio_encerramento_log`, `hr_impressao_bu_log` | "Inicio do Encerramento" (~110 s depois) e 1ª "Imprimindo relatório [BU] via nº [1]" (1–16 s após `dt_emissao_bu`) | M |
| `hr_primeiro_voto`, `hr_ultimo_voto`, `votos_por_hora` (lista de 24, índice 0 = 0h; em SQL `votos_por_hora[h+1]`) | horários dos votos computados | A |
| `intervalo_mediano_s`, `intervalo_medio_s`, `intervalo_min_s`, `intervalo_p10_s`, `intervalo_mediano_por_hora_s[24]` | intervalos, em segundos, entre votos computados consecutivos (todas as urnas da seção juntas, em ordem de hora) | A |
| `velocidade_media_votos_hora` | `n_votos_log / (último − primeiro voto em horas)` | A |
| `tempo_cabine_mediano_s` | mediana de "Eleitor foi habilitado" → "O voto do eleitor foi computado" | M |
| `n_pares_lt{5,10,20,30}s`, `pct_pares_lt…` | nº e **% (0–100)** de intervalos consecutivos menores que o limiar | A |
| `maior_rajada_lt{10,20}s` | maior sequência de votos seguidos com todos os intervalos < limiar (1 = nenhum par) | A |
| `n_hab_biometrica` | sessões com "Tipo de habilitação do eleitor [biométrica]" | M |
| `n_hab_manual` | sessões com "Solicitação de dado pessoal do eleitor para habilitação manual" (bate com `qt_elei_biom_sem_habilitacao` do BU em 99,7% das seções) | A |
| `n_hab_ano_nascimento` | habilitado só com "Ano de nascimento digitado é igual ao do cadastro" (eleitor sem biometria cadastrada) | M |
| `n_hab_outra`, `n_habilitados` | habilitado sem nenhum dos marcadores acima; soma das quatro | B |
| `n_id_titulo`, `n_id_cpf` | eleitor identificado por título ou CPF | M |
| `n_voto_confirmado_presidente` | "Voto confirmado para [Presidente]" (pode exceder `n_votos_log` se a urna desligou antes de computar) | A |
| `n_urna_ligada`, `n_desligada_chave`, `n_urna_pronta`, `n_votacao_suspensa`, `n_reinicio_votacao`, `n_bateria_interna`, `n_log_contingencia_validado`, `n_log_me_corrompido`, `n_impressora_problema`, `n_encerramento_cancelado`, `n_encerramento_antes_hora` | reinícios, contingência e incidentes (regra exata em [`docs/dicionario_eventos_2t.md`](docs/dicionario_eventos_2t.md)) | B |
| `n_identificador_invalido`, `n_eleitor_nao_encontrado`, `n_eleitor_ja_votou`, `n_eleitor_impedido`, `n_justificativa`, `n_eleitor_suspenso`, `n_hab_cancelada`, `n_digital_solicitada`, `n_digital_timeout`, `n_digital_nao_corresponde`, `n_ano_nasc_diferente`, `n_eleitor_corrigiu`, `n_tecla_indevida` | fluxo de identificação/habilitação | B |
| `n_erro`, `n_alerta` | linhas de nível ERRO / ALERTA no dia | B |
| `n_arquivos_log`, `n_urnas_log`, `n_urnas_com_voto`, `n_linhas_dia`, `n_votos_logs_arquivados`, `n_votos_fora_do_dia` | estrutura do log: arquivos `.jez` (inclui logs de outras urnas arquivados dentro), nº de urnas (serial), votos vindos de logs arquivados, votos com data ≠ dia da eleição (excluídos) | A |
| `parser_version` | versão de `scripts/parser_log.py` | — |

### `eventos_tipo` — tabela longa (seção × modelo de mensagem)

`nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao, app, nivel, modelo, n`. Só eventos de nível ≠ INFO (ALERTA, ERRO,
WHAT, EXTERNO) e um conjunto fixo de mensagens INFO de interesse (`INFO_EVENTOS` no parser; não inclui o app GAP).
`modelo` = mensagem com **todos os dígitos trocados por `#`** (some com horários, contagens, títulos de mesário e
seriais; nenhuma linha bruta é guardada). `eventos_dicionario` no DuckDB = `eventos_tipo` somado por UF
(ocorrências e seções). `lotes` = `manifest.json` (zip de origem, ETag, SHA-256, versão do parser, tempos).

## Dicionário de eventos

[`docs/dicionario_eventos_2t.md`](docs/dicionario_eventos_2t.md) lista só o que foi **visto**: a rotina completa numa
amostra (600 seções da BA, 400 do CE, via `inspecionar_eventos.py`; ~1.300–1.900 modelos distintos, a maioria do GAP)
e os eventos fora da rotina na população completa. Formato de cada linha do `logd.dat` (latin-1):
`DD/MM/AAAA HH:MM:SS <TAB> nível <TAB> serial da urna <TAB> app <TAB> mensagem <TAB> hash`.
Apps: VOTA (votação), GAP (gerenciador), LOGD (log), INITJE (inicialização), ATUE/SCUE (raros).

Mais frequentes fora da rotina (BA+CE, % das 59.241 seções): "Problema ao desmontar a MR" (GAP ERRO, ~100%),
"Identificador do eleitor digitado inválido" (VOTA ALERTA, 99,6%), "Digitado título inválido para o registro de
mesário" (56%), "Mesário indagado se eleitor está votando" (26%), "Habilitação cancelada durante reconhecimento
biométrico" (23%).

## Validação (2º turno, Brasil)

Detalhe por UF em [`validacao.md`](validacao.md) (gerado por `scripts/validate.py`).

- Cobertura: 499.177 seções com log e BU, de 499.205 seções no BU (cargo presidente). 28 seções estão só no BU
  (sem log publicado no zip do TSE): 1 em Guarulhos-SP (zona 395, seção 298) e 27 no exterior (ZZ). Nenhuma seção só
  no log; 0 erros de leitura; 0 votos com data diferente do dia da eleição.
- **Votos no log = comparecimento do BU** em 499.170 das 499.177 seções (99,9986%); 7 seções divergem (tabela em
  `validacao.md`). Σ votos no log 128.235.225 × Σ comparecimento 128.236.074 no BU (todas as 499.205 seções;
  128.234.975 nas 499.177 seções com log). Exemplos de divergência:
  - Conde (BA), zona 21, seção 178: log 233 × BU 234. A urna entrou na bateria interna e o log tem 234
    "Voto confirmado para [Presidente]" mas 233 "computado".
  - Ibotirama (BA), zona 173, seção 235: log 204 × BU 217. O BU registra abertura 08:48:54; os 3 arquivos de log
    (2 urnas) só têm abertura às 10:10:56 e nenhum voto do dia antes disso — os votos anteriores não estão nos logs publicados.
- Abertura do log = `dt_abertura`: 80,7% exatos (0 s; o resto quase todo +1 s); ≤ 60 s em 499.166 seções (99,998%).
- Encerramento ("Procedimento de encerramento confirmado") = `dt_encerramento`: 96,7% exatos, ≤ 60 s em 100% das
  seções com a mensagem.
- Habilitação manual = `qt_elei_biom_sem_habilitacao`: 99,78% das seções; as diferenças são quase todas de +1.
- `eventos_tipo`: 2.540.011 linhas.

## Fuso e relógio

Os horários são o **relógio interno da urna** (hora local da seção), sem fuso no arquivo, e coincidem com o
`dt_abertura`/`dt_encerramento` do BU. Por isso a abertura aparece às 8h na maioria das UFs, às 7h em AM, MS, MT, RO e
RR (e parte do AM às 6h) e às 6h no AC; no exterior, hora local do país. Algumas urnas têm a **data** do relógio errada (ex.: 02/01/2026, 09/11/2026);
por isso o parser filtra pelo dia da eleição e conta à parte (`n_votos_fora_do_dia`, 0 em todas as UFs no 2º turno).

## Escopo e limites

- Descritivo. Ritmo, proximidade ou incidentes não dizem nada sobre em quem se votou nem sobre causa ou intenção.
- O log registra o que a urna gravou e o TSE publicou. Pode faltar trecho (queda de energia, log de urna substituída
  não arquivado) — ver Ibotirama — e pode haver voto confirmado sem "computado" se a urna desligou (Conde).
- Contagens de habilitação são reconstruídas a partir da sequência de mensagens e podem diferir de ±1 em ~0,3% das seções.
- Intervalos juntam todas as urnas da seção; numa troca de urna aparece um intervalo longo.
- 28 seções do 2º turno não têm log no zip do TSE (ver Validação); para elas não há linha em `eventos_secao`.
- Só o 2º turno foi processado até agora. Os limiares (5/10/20/30 s) e a lista `INFO_EVENTOS` são escolhas
  desta pasta; mudá-los exige reprocessar os zips (a versão do parser fica no `manifest.json`).
- O leiame do TSE descreve o `.jez` como 7-Zip; na prática é ZIP contendo `logd.dat`.

## Arquivos

```
logs-urna/
  run.sh, Makefile, requirements.txt, .gitignore
  exemplo_attach.sql          exemplos de consulta junto com o banco principal
  fontes_manifest.json        cópia do data/manifest.json do último `dist` (origem e hashes de cada lote)
  validacao.md                cópia do data/validacao.md do último `dist`
  docs/dicionario_eventos_2t.md
  scripts/parser_log.py       leitura de um log de seção -> linha de métricas + eventos
  scripts/baixar_agregar.py   download retomável + agregação em streaming + manifest
  scripts/build_db.py         Parquets -> data/db/eventos.duckdb
  scripts/validate.py         log × BU (lê o banco de totalizacoes/ somente leitura)
  scripts/fetch_release.py    baixa os agregados prontos de um GitHub Release
  scripts/inspecionar_eventos.py, scripts/gerar_dicionario.py
  data/                       (fora do git) raw/, parquet/, db/, dist/, logs/, inspecao/, manifest.json
```
