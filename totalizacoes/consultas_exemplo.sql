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

-- 4. Seções com maior variação da margem (Lula − Flávio) entre 1º e 2º turno
SELECT sg_uf, nm_municipio, nr_zona, nr_secao,
       lula_1t, flavio_1t, outros_1t, lula_2t, flavio_2t, delta_margem_lula
FROM presidente_1t_2t_secao WHERE tem_1t AND tem_2t
ORDER BY delta_margem_lula DESC LIMIT 10;

-- 5. Correlação, entre seções, de votos de outros candidatos no 1º turno com o ganho de cada candidato
--    no 2º (descritiva: não indica como cada eleitor votou)
SELECT round(corr(outros_1t, lula_2t - lula_1t), 3)     AS corr_outros_ganho_lula,
       round(corr(outros_1t, flavio_2t - flavio_1t), 3) AS corr_outros_ganho_flavio,
       sum(lula_2t - lula_1t)     AS ganho_lula,
       sum(flavio_2t - flavio_1t) AS ganho_flavio,
       sum(outros_1t)             AS outros_1t
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

-- 7. Governador: resultado por UF no 1º turno (top 2) e quem foi ao 2º turno
SELECT nr_turno, sg_uf, nm_votavel, sg_partido, votos, pct_validos
FROM totais_candidato_uf
WHERE cd_cargo = 3 AND cd_tipo_votavel = 1
QUALIFY row_number() OVER (PARTITION BY nr_turno, sg_uf ORDER BY votos DESC) <= 2
ORDER BY sg_uf, nr_turno, votos DESC;

-- 8. Senadores mais votados por UF (cada eleitor vota em 2 nesta eleição)
SELECT sg_uf, nm_votavel, sg_partido, votos
FROM totais_candidato_uf WHERE nr_turno = 1 AND cd_cargo = 5 AND cd_tipo_votavel = 1
QUALIFY row_number() OVER (PARTITION BY sg_uf ORDER BY votos DESC) <= 2
ORDER BY sg_uf, votos DESC;

-- 9. Deputados federais mais votados do Brasil (só no banco completo)
SELECT sg_uf, nm_votavel, sg_partido, votos
FROM totais_candidato_uf WHERE cd_cargo = 6 AND cd_tipo_votavel = 1
ORDER BY votos DESC LIMIT 15;

-- 10. Abstenção por município no 2º turno (presidente), maiores taxas entre municípios com 10 mil+ aptos
SELECT sg_uf, nm_municipio, sum(qt_aptos) AS aptos, sum(qt_comparecimento) AS comparecimento,
       round(100 - 100.0 * sum(qt_comparecimento) / sum(qt_aptos), 2) AS pct_abstencao
FROM secoes WHERE nr_turno = 2 AND cd_cargo = 1 AND sg_uf <> 'ZZ'
GROUP BY ALL HAVING sum(qt_aptos) >= 10000
ORDER BY pct_abstencao DESC LIMIT 10;

-- 11. Granular: votos de cada candidato a presidente numa seção específica
SELECT nr_turno, nm_votavel, sg_partido, qt_votos, qt_aptos, qt_comparecimento
FROM votos_secao
WHERE sg_uf = 'SP' AND nm_municipio = 'SÃO PAULO' AND nr_zona = 1 AND nr_secao = 1 AND cd_cargo = 1
ORDER BY nr_turno, qt_votos DESC;

-- 12. Direto do Parquet, sem banco (rode a partir de totalizacoes/)
SELECT nr_turno, ds_cargo, count(*) AS linhas, sum(qt_votos) AS votos
FROM read_parquet('data/parquet/votos_secao/*/*/data.parquet', hive_partitioning = true)
WHERE uf = 'RJ' GROUP BY ALL ORDER BY ALL;
