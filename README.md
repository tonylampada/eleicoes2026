# eleicoes2026

Votos por seção eleitoral de **todos os cargos** das Eleições 2026 (1º e 2º turno), a partir dos boletins de
urna do TSE, em Parquet + DuckDB, com scripts reproduzíveis e retomáveis.

**Usar os dados sem reconstruir** (repo privado: precisa de `gh auth login` ou `GITHUB_TOKEN`):

```bash
cd totalizacoes && ./run.sh fetch            # banco completo (~816 MB) do GitHub Release
cd totalizacoes && ./run.sh fetch --compacto # só presidente/governador/senador (~154 MB)
```

Os dados ficam no Release [`dados-2026-10-28`](https://github.com/tonylampada/eleicoes2026/releases/tag/dados-2026-10-28)
(não no git; sem Git LFS). Reconstruir do zero a partir do TSE é opcional: `./run.sh all` (~11 min, ~12 GB livres).

- [`AGENTS.md`](AGENTS.md) — guia curto para agentes de código: atalhos, esquema, exemplos, fuso dos horários, armadilhas.
- [`totalizacoes/README.md`](totalizacoes/README.md) — documentação completa: fontes, validação, tamanhos, consultas.
