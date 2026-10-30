# Micro-análises

Cada subpasta é uma "fatia" de análise autocontida sobre o banco das eleições 2026:

```
micro-analises/<nome>/
  gerar_dados.py   # consulta o DuckDB (somente leitura) e grava dados.json
  dados.json       # agregado compacto (arrays colunares), versionável/publicável
  index.html       # página única, JS puro, sem build e sem dependências externas; lê dados.json
  README.md        # o que a análise mostra e como foi calculada
```

Convenções:

- **Requisito**: o banco completo em `totalizacoes/data/db/eleicoes2026.duckdb`
  (baixe pronto com `cd totalizacoes && ./run.sh fetch`, sem login; veja `totalizacoes/README.md`). Todo `gerar_dados.py` aceita `--db` para outro caminho
  e abre o banco com `read_only=True`.
- **Filtros padrão** na página: Estado (UF), cidade (município) e hora de fechamento da urna. Por isso o JSON é
  agregado por (município, hora) com medidas *somáveis*; o navegador soma as linhas que passam no filtro.
- O JSON deve ficar pequeno (alvo < 3–5 MB).
- O script valida os totais contra o resultado oficial e falha (exit ≠ 0) se algo não bater.
- Texto (README e página) em tom descritivo: afirmar só o que os dados mostram, deixar claro que é
  estatística descritiva sobre dados públicos (agregados não indicam causa nem voto individual) e indicar
  as fontes oficiais do TSE para conferência.

Como rodar (exemplo):

```bash
pip install duckdb
cd micro-analises/transferencia-de-votos
python gerar_dados.py                 # ou: python gerar_dados.py --db /caminho/eleicoes2026.duckdb
python -m http.server 8000            # abra http://localhost:8000 (fetch de arquivo local não funciona via file://)
```

Análises:

- [`transferencia-de-votos/`](transferencia-de-votos/) — decomposição aritmética da variação de votos de 13 e 22 entre o 1º e o 2º turno.
