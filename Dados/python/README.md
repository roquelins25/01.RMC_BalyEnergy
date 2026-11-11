# Pipeline RMC

Transforma o Excel **DRE Cliente Consolidado** (pasta de rede da Controladoria) em parquets
organizados em camadas medalhão (bronze, silver, gold), enriquecidos com cadastros do Oracle,
para consumo no Power BI.

```
rede (\\dados\...\DRE CLIENTE CONSOLIDADO)
   │  extract
   ▼
medalion/bronze/   DRE CLIENTE_<data>.xlsx   (cópia bruta)
   │  bronze       dre_cliente.parquet       (Excel completo, limpo e tipado)
   ▼               oracle/<select>.parquet   (resultado de cada select do Oracle)
medalion/silver/   dre_cliente/AAAA-MM.parquet   (um por mês, 31 colunas)
   │  gold
   ▼
medalion/gold/     rmc_tratado.parquet       (linha a linha, só com as mesclagens, para validação)
                   rmc_gold.parquet          (agregado por UF e produto, fonte do Power BI)
                   rmc_gold.xlsx             (mesmo agregado, para quem usa Excel)
```

## Como atualizar

Com um Excel novo na pasta de rede, basta:

```
uv run python main.py
```

O `main.py` pega o `.xlsx` mais recente da rede e roda as quatro etapas em ordem.
Opções:

| opção | efeito |
|---|---|
| `--arquivo "DRE CLIENTE_10112026.xlsx"` | usa um arquivo específico em vez do mais recente |
| `--etapas silver gold` | roda só as etapas informadas (ordem: `extract bronze silver gold`) |
| `--mes 2026-09` | na gold, processa só esse mês e grava `rmc_gold_2026-09.parquet` (amostra) |
| `--banco` | reconsulta o Oracle; sem isso reaproveita os selects já salvos em `bronze/oracle` |

Cada etapa também roda sozinha como módulo, por exemplo `uv run python -m src.transform_silver`.
Para testar um select no Oracle: `uv run python -m src.oracle TB_CLIENTE`.

## Instalação

1. Python 3.14 e [uv](https://docs.astral.sh/uv/). Na pasta do projeto: `uv sync`.
2. Preencher o `.env` na raiz (não vai para o git):
   ```
   ORACLE_USER=
   ORACLE_PASSWORD=
   ORACLE_DSN=host:porta/servico
   ```
3. Oracle Client. O servidor exige criptografia nativa de rede, que o `python-oracledb` só
   suporta em modo thick. O pipeline carrega automaticamente o
   `C:\Program Files\Oracle Client for Microsoft Tools`, instalado junto com o Power BI.
   Para usar outro Instant Client, informe `ORACLE_CLIENT_DIR` no `.env`.

Dependências: pandas, pyarrow, python-calamine (leitura rápida do Excel), oracledb, python-dotenv.

## Camadas e regras

### extract (`src/extract.py`)
Copia o `.xlsx` da rede para `medalion/bronze` sem alteração.

### bronze (`src/transform_bronze.py`)
Lê a aba `DRE_Geral - Jan26 a Set26`, pulando as 26 linhas de resumo do topo (o cabeçalho
está na linha 27), e grava `bronze/dre_cliente.parquet` com todas as 48 colunas.
Tratamentos aplicados, todos por causa de como o Excel vem da origem:

- números como texto no padrão brasileiro (`15603,98`), em meses inteiros;
- datas como texto `dd/mm/aaaa`, `mm/aaaa`, ISO ou serial do Excel (`46113`);
- cabeçalho `pode` renomeado para `Supervisor`;
- nomes de colunas em minúsculo, códigos como inteiro, valores como float com zero no lugar de nulo;
- colunas derivadas `ano` e `mes` a partir de `mes_ano`, que é a data de referência.

### silver (`src/transform_silver.py`)
- **Regra 1**: um parquet por mês de `mes_ano` em `silver/dre_cliente/AAAA-MM.parquet`.
  Ao reprocessar, só os meses presentes no Excel atual são sobrescritos.
- **Regra 2**: mantém 31 colunas (lista `COLUNAS_SILVER`).
- Linhas duplicadas na origem são mantidas.

### gold (`src/transform_gold.py`)
**Passo 1, mesclagens** (lista `ETAPAS`), com left join a partir da silver:

| select | junção | colunas trazidas |
|---|---|---|
| `TB_CLIENTE` | `cod_cliente` = `codcli` | `sigufs`, `usu_codram`, `usu_desram`, `xregsenha` |
| `TB_PRODUTO` | `codproduto` = `codpro` | `codagc`, `usu_claman`, `qtdpct`, `volpro_un`, `usu_codfamday`, `usu_desfamday`, `produto_zero`, `classificacao_bi`, `codclc` |

Linhas sem correspondência ficam com nulo, não são descartadas.

Depois das mesclagens, regras de negócio (`tratar_regras`):

- saídas com `codproduto` informado mas sem família no cadastro (`usu_codfamday` nulo)
  recebem `usu_desfamday = 'Outros Produtos'`.

O resultado desse passo,
ainda linha a linha (uma por item de nota fiscal, com as colunas da silver mais as mescladas),
é gravado em `rmc_tratado.parquet` para validação.

**Passo 2, agregação**: somatória das 20 colunas de valores por

- `mes_ano`, `operacao`;
- cliente: `sigufs`, `xregsenha`, `usu_codram`, `usu_desram`;
- produto: `codagc`, `usu_claman`, `usu_codfamday`, `usu_desfamday`, `produto_zero`, `classificacao_bi`, `codclc`.

No resultado, `mes_ano` deixa de ser data e vira inteiro `AAAAMM`, por exemplo `202609`.
`cod_cliente`, `nota_fiscal` e `codproduto` somem. Os clientes viram `qtd_clientes`, contagem
de clientes distintos em cada grupo (somar essa coluna entre grupos não dá o total da UF).
Antes de gravar, o script confere que a soma de cada coluna de valor é igual à da base linha a linha.

A gold grava o mesmo agregado em dois formatos: `rmc_gold.parquet`, lido pelo Power BI, e
`rmc_gold.xlsx`, porque o Excel não lê parquet. No `.xlsx`, as colunas de valor saem com duas
casas decimais e a primeira linha fica congelada com filtro.

Para incluir outro select: colocar o `.SQL` em `src/selects`, adicionar um item em `ETAPAS` e,
se a coluna nova for uma quebra, acrescentá-la em `QUEBRAS`.

## Estrutura do projeto

```
main.py                   ponto de entrada do pipeline
src/
  extract.py              rede -> bronze
  transform_bronze.py     xlsx -> dre_cliente.parquet
  transform_silver.py     parquets mensais
  transform_gold.py       mesclagens + agregação -> rmc_gold.parquet
  oracle.py               conexão e execução dos selects
  selects/*.SQL           consultas do Oracle
medalion/                 dados (ignorado pelo git)
.env                      credenciais (ignorado pelo git)
```

## Pontos de atenção

- A pasta está dentro do Google Drive; os parquets e o Excel de 236 MB são sincronizados.
- A leitura do Excel leva cerca de 30 s com o calamine (2 min com openpyxl).
- Em setembro de 2026, 698 linhas (0,15% do valor) têm `codproduto` fora da view `USU_V075PRO2`.
  Elas seguem no `rmc_gold` com os atributos de produto nulos.
- 517 linhas por mês, aproximadamente, têm cliente sem descrição de canal (`usu_desram` nulo).
