-- Exemplo: juntar as métricas do log (eventos.duckdb) ao banco principal de totalizacoes/, sem alterá-lo.
-- Rode a partir de logs-urna/:   duckdb data/db/eventos.duckdb < exemplo_attach.sql
-- (ou em Python: duckdb.connect('data/db/eventos.duckdb', read_only=True) e os mesmos comandos)

ATTACH '../totalizacoes/data/db/eleicoes2026.duckdb' AS tse (READ_ONLY);

-- view temporária: 1 linha por seção com BU (cargo presidente) + métricas do log
CREATE OR REPLACE TEMP VIEW secao_log AS
SELECT s.nr_turno, s.sg_uf, s.cd_municipio, s.nm_municipio, s.nr_zona, s.nr_secao, s.qt_aptos, s.qt_comparecimento,
       s.qt_elei_biom_sem_habilitacao, s.dt_abertura, s.dt_encerramento,
       e.* EXCLUDE (nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao)
FROM tse.secoes s
JOIN eventos_secao e USING (nr_turno, sg_uf, cd_municipio, nr_zona, nr_secao)
WHERE s.cd_cargo = 1;

-- 1. concordância votos no log × comparecimento do BU, por UF
SELECT sg_uf, count(*) AS secoes,
       count(*) FILTER (n_votos_log = qt_comparecimento) AS iguais,
       sum(qt_comparecimento) AS comparecimento_bu, sum(n_votos_log) AS votos_log
FROM secao_log GROUP BY ALL ORDER BY ALL;

-- 2. votos por hora do dia (hora local da urna), somando as seções de cada UF
SELECT sg_uf, h AS hora, sum(votos_por_hora[h + 1]) AS votos
FROM secao_log, range(0, 24) t(h)
GROUP BY ALL HAVING sum(votos_por_hora[h + 1]) > 0 ORDER BY ALL;

-- 3. proximidade: seções com maior % de pares de votos consecutivos a menos de 20 s
SELECT sg_uf, nm_municipio, nr_zona, nr_secao, n_votos_log, n_pares_lt20s, pct_pares_lt20s,
       maior_rajada_lt20s, intervalo_mediano_s
FROM secao_log WHERE n_votos_log >= 50
ORDER BY pct_pares_lt20s DESC LIMIT 10;

-- 4. resultado do 2º turno por seção (tabela pronta do banco principal) junto com métricas do log
SELECT p.sg_uf, p.nm_municipio, p.nr_zona, p.nr_secao, p.lula_2t, p.flavio_2t,
       e.n_votos_log, e.intervalo_mediano_s, e.n_hab_manual, e.hr_abertura_log
FROM tse.presidente_1t_2t_secao p
JOIN eventos_secao e ON e.nr_turno = 2 AND (e.sg_uf, e.cd_municipio, e.nr_zona, e.nr_secao) = (p.sg_uf, p.cd_municipio, p.nr_zona, p.nr_secao)
LIMIT 5;

-- 5. eventos fora da rotina mais frequentes (tabela longa)
SELECT app, nivel, modelo, sum(ocorrencias) AS ocorrencias, sum(secoes) AS secoes
FROM eventos_dicionario GROUP BY ALL ORDER BY secoes DESC LIMIT 20;
