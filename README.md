# eleicoes2026

Votos por seção eleitoral de **todos os cargos** das Eleições 2026 (1º e 2º turno), a partir dos boletins de
urna do TSE, em Parquet + DuckDB, com scripts reproduzíveis e retomáveis.

**Usar os dados sem reconstruir** (sem login, só `python3` + `curl`):

```bash
cd totalizacoes && ./run.sh fetch            # banco completo (~816 MB) do GitHub Release
cd totalizacoes && ./run.sh fetch --compacto # só presidente/governador/senador (~154 MB)
```

Os dados ficam no Release [`dados-2026-10-28`](https://github.com/tonylampada/eleicoes2026/releases/tag/dados-2026-10-28)
(não no git; sem Git LFS). Reconstruir do zero a partir do TSE é opcional: `./run.sh all` (~11 min, ~12 GB livres).

- [`AGENTS.md`](AGENTS.md) — guia curto para agentes de código: atalhos, esquema, exemplos, fuso dos horários, armadilhas.
- [`totalizacoes/README.md`](totalizacoes/README.md) — documentação completa: fontes, validação, tamanhos, consultas.
- [`micro-analises/`](micro-analises/) — análises prontas (ex.: transferência de votos 1º→2º turno).

## Escopo e limites

- Os dados são os boletins de urna publicados pelo TSE (Portal de Dados Abertos), reorganizados em
  Parquet/DuckDB sem alteração de valores. Não substituem o resultado oficial: confira em
  <https://resultados.tse.jus.br> e <https://dadosabertos.tse.jus.br>.
- As análises são aritmética e estatística descritiva sobre esses dados públicos. Correlações e
  decomposições agregadas não indicam causa nem mostram como cada eleitor votou (inferência ecológica).
- As pequenas diferenças em relação ao painel oficial (nº 28 no 1º turno, contagem de seções, aptos,
  seções sem horário de encerramento) estão documentadas em
  [`totalizacoes/validacao.md`](totalizacoes/validacao.md); têm explicações administrativas possíveis,
  não verificadas aqui.

## Como usar com um agente de IA

Cole isto no seu agente de código (Cursor, Claude Code, Codex…), trocando o final:

```text
Clone https://github.com/tonylampada/eleicoes2026 e leia o AGENTS.md na raiz. Baixe o banco pronto
com `cd totalizacoes && ./run.sh fetch` (não reconstrua a partir do TSE). Depois <reproduza a análise
micro-analises/transferencia-de-votos | crie uma micro-análise nova sobre: X>, seguindo a convenção de
micro-analises/ (gerar_dados.py → dados.json → index.html + README.md), validando os totais contra o
oficial e descrevendo só o que os dados mostram, e me mostre o resultado.
```

Convenção para novas análises: `micro-analises/<nome>/` com `gerar_dados.py` (lê o DuckDB em modo
somente leitura, aceita `--db`, valida contra o oficial e falha se não bater) → `dados.json` (agregado
pequeno, < 3–5 MB, pode ser commitado) → `index.html` (página única, JS puro, lê `dados.json`) + `README.md`
(o que mostra, metodologia, limites). Texto em tom descritivo: afirmar só o que os dados mostram, sem
atribuir causa ou intenção. Publicar a página (here.now, GitHub Pages…) é opcional e fica fora do git:
nunca commite chaves nem arquivos de estado (`.herenow-*`, `.env`). Detalhes em
[`micro-analises/README.md`](micro-analises/README.md).

