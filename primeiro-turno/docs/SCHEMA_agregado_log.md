# Schema — linha JSONL por seção (log de urna)

Uma linha = uma seção. Produzido por `scripts/08_download_logs_BA_CE.py` (streaming).

Campos típicos (podem evoluir; scripts são a fonte da verdade):

| Campo | Tipo | Significado |
|-------|------|-------------|
| `uf` | str | UF |
| `mun5` / `cd_mun` | str | Código município TSE |
| `nm_mun` | str | Nome município |
| `zona` | int | Zona |
| `secao` | int | Seção |
| `n_votos_log` | int | Votos com timestamp no log (dia 04/10/2026) |
| `share_after16` / `concentracao_16` | float | Fração de votos ≥ 16:00 |
| `share_after17` / `concentracao_17` | float | Fração ≥ 17:00 |
| `first_ts` / `last_ts` / `enc_ts` | str | Horários |
| `hours` | object | Contagem por hora |
| `n_hab` / `n_bio` / `n_nao_bio` / `share_bio` | | Habilitação biométrica vs manual |
| `lula_share` / `flavio_share` | float | Shares presidente (cruzados do BU) |

**Não** inclui: título de eleitor, digital, nem voto escolhido.
