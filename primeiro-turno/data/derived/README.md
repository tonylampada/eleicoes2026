Este diretório conterá os derivados compactos (JSONL / JSONL.gz) gerados pelos scripts de pipeline.

- Arquivos grandes como `*.jsonl.gz` de BA e CE serão versionados via Git LFS (ver `.gitattributes`).
- Não commitamos blobs brutos do TSE (`.jez`, BU zips, `logd.dat`).
- Os dados aqui são o produto final enxuto, streamado a partir dos logs.

Estrutura típica (exemplos; não gerados automaticamente):

```
primeiro-turno/data/derived/
  ba.jsonl.gz     # logs BA → agregados linha-a-linha (LFS)
  ce.jsonl.gz     # logs CE → agregados (LFS)
```

Para reproduzir, execute os scripts em `primeiro-turno/scripts/` a partir da raiz do repositório.
