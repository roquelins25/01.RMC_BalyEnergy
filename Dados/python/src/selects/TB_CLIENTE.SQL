select 
	   e085cli.codcli,
       e085cli.nomcli,
	   e085cli.codcli || ' - ' || UPPER(e085cli.nomcli) as xNOMCLI,
	   e085cli.cgccpf,
	   e085cli.apecli,
	   replace(cast((e085hcl.usu_perdup/100) AS VARCHAR2(4000)),'.',',') usu_perdup,
	   e085cli.marcli,
	   e085cli.codgre,
	   e085cli.cepcli,
	   e085cli.endcli,
	   e085cli.cidcli,
	   e085cli.sigufs,
	   e085cli.foncli,
	   e085cli.datcad,
	   e085cli.sitcli,
	   e085hcl.codrep,
	   e090rep.nomrep,
	   e085cli.codpai,
	   e006pai.nompai,
	   e085cli.codram,
	   e085cli.usu_codram,
	   upper(usu_tcanais.usu_desram) as usu_desram,
	   case when SitFinanceira.codcli is null then NULL
		     else 'PENDÊNCIA FINANCEIRA'
	   end SitFinanceiro,
	   case when SitInadimplencia.codcli is null then 'NAO'
		     else 'SIM'
	   end SitInadimplencia,
       e085hcl.codcpg,
	   e028cpg.abrcpg,
	   e085hcl.vlrlim,
	   e085hcl.exiage,
       case when exists(select 1 from e085ccl where e085ccl.codcli = e085cli.codcli and e085cli.sigufs='SC') then 'TORNADO-SC'
	        when (e085cli.sigufs='PR') then 'TORNADO-PR'
	        when (e085cli.sigufs='RS') then 'CLICK-RS'
			else 'PADRAO' end as Dep_Padrao,
		e085hcl.codrve codreve,
		e017rve.nomrve nomrve,
		e017rve.abrrve abrrve,
		CASE
			WHEN e017rve.abrrve IN ('SPI','SPA','SPC') THEN e017rve.abrrve
			ELSE e085cli.sigufs
		END xREGSenha,
		
		e085hcl.codtpr codtpr
from e085cli
  join e085hcl  on e085cli.codcli = e085hcl.codcli and e085hcl.codfil = 1
  LEFT OUTER JOIN e017rve ON e017rve.codrve = e085hcl.codrve AND e017rve.codemp = e085hcl.codemp
  left outer join e006pai  on e085cli.codpai = e006pai.codpai
  left outer join usu_tcanais  on e085cli.usu_codram = usu_tcanais.usu_codram
  left outer join e090rep  on e085hcl.codrep =  e090rep.codrep
  left outer JOIN e081tab   on e085hcl.codemp = e081tab.codemp and e085hcl.codtpr = e081tab.codtpr
  left outer JOIN e028cpg   on e085hcl.codemp = e028cpg.codemp and e085hcl.codcpg = e028cpg.codcpg
  left outer join(select codcli
	     from e301tcr
		where sittit = 'AB'
		  and codtpt = '01'
		  and vctpro < (SYSDATE - 7)
		group by codcli) SitFinanceira
				on SitFinanceira.codcli = e085cli.codcli
  left outer join (select tcr.codcli
                     from e301tcr tcr
                     join e039por por on por.codpor=tcr.codpor
                    where por.codpor IN ('ADV','ANGE','CART','CNTH','EXCE','GBNT','PERD','PLCB','REN')
                      AND TCR.VLRABE>0
                 group by tcr.codcli) SitInadimplencia
				       on SitInadimplencia.codcli = e085cli.codcli