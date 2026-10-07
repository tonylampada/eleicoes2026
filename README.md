# eleicoes2026

Análises reprodutíveis das Eleições 2026 (TSE / dados abertos), organizadas por turno.

**Status:** privado. Ainda não há decisão de publicação; a estrutura já assume que o repo *pode* virar público depois (scripts + derivados compactos + Git LFS).

## Layout

```
primeiro-turno/          # 1º turno (04/10/2026)
  scripts/               # pipeline: amostra → download streaming → agregados → site
  data/
    sample/              # derivados da amostra ~100 seções (pequenos, no git normal)
    derived/             # agregados por UF (JSONL / JSONL.gz) — candidatos a Git LFS
  docs/                  # schema dos agregados, notas metodológicas
  site/                  # página didática estática (voto tardio)
```

## Princípio de disco (streaming)

Não versionamos boletim de urna bruto (`.zip`) nem `log.jez` / `logd.dat`.

Fluxo por seção:

1. Baixa `aux.json` + `log.jez` do CDN do TSE
2. Extrai `logd.dat` **em memória**
3. Agrega métricas (horário, concentração após 16h/17h, biometria)
4. Acrescenta uma linha JSONL por seção
5. Descarta o bruto

Assim o disco (e quem for reproduzir) só precisa dos **derivados compactos**, não de terabytes de logs.

## Git LFS

Arquivos grandes derivados (ex.: `primeiro-turno/data/derived/*.jsonl.gz`) devem ir via [Git LFS](https://git-lfs.com/). Ver `.gitattributes`.

## Scripts (ordem típica)

| Script | Função |
|--------|--------|
| `01_build_sample.py` | Amostra ~100 seções |
| `02_download_logs.py` | Logs da amostra |
| `03_discrepancia_ideologica.py` | PL dep × Lula (amostra) |
| `04_analise_logs_tarde.py` | Resumo concentração amostra |
| `05_discrepancia_BA_CE_full.py` | Discrepância BA+CE via BU |
| `07_biometria_logs.py` | Habilitação biométrica na amostra |
| `08_download_logs_BA_CE.py` | **Streaming** logs BA+CE → JSONL |
| `09_build_site_voto_tardio.py` | Site didático só voto tardio |

## Fonte

CDN: `https://resultados.tse.jus.br/oficial/ele2026` · pleito `3220`.
