SELECT 
PRO.*,
PRO.CODPRO || ' - ' || UPPER(PRO.CPLPRO) AS xDESPRO,
           CASE
               WHEN (pro.codfam = '17' AND pro.volpro = 2)     THEN 'ENERGÉTICO 2L'
               WHEN (pro.codfam = '17' AND pro.volpro = 0.473) THEN 'ENERGÉTICO 473ML'
               WHEN (pro.codfam = '17' AND pro.volpro = 0.250) THEN 'ENERGÉTICO 250ML'
               WHEN (pro.codfam = '17' AND pro.volpro = 1)     THEN 'ENERGÉTICO 1L'
               WHEN (pro.codfam = '17' AND pro.volpro = 0.750) THEN 'ENERGÉTICO 750ML'
               WHEN (pro.codfam = '17' AND pro.volpro = 2.5)   THEN 'ENERGÉTICO 2.5L'
               WHEN pro.usu_codfamday = '10002' THEN 'VODKA'
               WHEN pro.usu_codfamday = '10003' THEN 'CERVEJA'
               WHEN pro.usu_codfamday = '10004' THEN 'GIN'
               WHEN pro.usu_codfamday = '10005' THEN 'WHISKY'
               WHEN pro.usu_codfamday = '10006' THEN 'KIDS'
               WHEN pro.usu_codfamday = '10008' THEN 'OUTROS ALCOOLICOS'
               WHEN pro.usu_codfamday = '10009' THEN 'OUTROS NÃO ALCOOLICOS'
               WHEN pro.usu_codfamday = '10001' THEN 'OUTROS ALCOOLICOS'
               WHEN pro.usu_codfamday = '10011' THEN 'OUTROS ALCOOLICOS'
               WHEN pro.usu_codfamday = '10012' THEN 'SAFADAO'
               WHEN pro.usu_codfamday = '10013' THEN 'OUTROS ALCOOLICOS'
               WHEN pro.usu_codfamday = '10014' THEN 'OUTROS NÃO ALCOOLICOS'
               WHEN pro.usu_codfamday = '10015' THEN 'ISOTONICOS'
               ELSE 'OUTROS'
           END AS classificacao_bi
FROM I260220090255_ERPP.USU_V075PRO2 PRO