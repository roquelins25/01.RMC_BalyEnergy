"""Tratamento da camada gold: rmc_gold.

Entrada: parquets mensais de medalion/silver/dre_cliente (gerados por transform_silver.py)
         + selects do Oracle em src/selects (via oracle.py).
Saida:   medalion/gold/rmc_tratado.parquet  (linha a linha, so com as mesclagens, para validacao)
         medalion/gold/rmc_gold.parquet     (agregado por UF e produto)
         medalion/gold/rmc_gold.xlsx        (mesmo agregado, para quem usa Excel)
         Com --mes, os nomes ganham o sufixo do mes (ex.: rmc_gold_2026-09.parquet).

Passo 1 - mesclagem (ETAPAS): para cada select, left join da silver com as colunas
          escolhidas. Linhas sem correspondencia ficam com nulo, nao somem.
          Em seguida, regras de negocio (tratar_regras):
          - Saidas com codproduto informado e usu_codfamday nulo recebem
            usu_desfamday = 'Outros Produtos'
Passo 2 - agregacao: somatoria das colunas de valores por UF e seus produtos.
          - mes_ano e operacao separam o mes e Entradas/Saidas
            (mes_ano sai como inteiro AAAAMM, ex.: 202609)
          - cliente: sigufs (UF), xregsenha, usu_codram, usu_desram
          - produto: codagc, usu_claman, usu_codfamday, usu_desfamday,
                     produto_zero, classificacao_bi, codclc
          - cod_cliente, nota_fiscal e codproduto somem; os clientes viram qtd_clientes

Para adicionar uma mesclagem, inclua um dicionario em ETAPAS:
    {
        'select': 'TB_CLIENTE',                 # arquivo src/selects/TB_CLIENTE.SQL
        'chave_silver': 'cod_cliente',          # coluna da silver usada na juncao
        'chave_select': 'codcli',               # coluna do select usada na juncao
        'colunas': {'nomcli': 'nome_cliente'},  # colunas trazidas do select: {origem: nome_no_gold}
    }
e, se a coluna nova for uma quebra do agregado, acrescente-a em QUEBRAS.
"""

import sys
from pathlib import Path

import pandas as pd

from .oracle import executar_select, ler_select_bronze
from .transform_silver import GOLD, ler_silver

NOME_GOLD = 'rmc_gold'
NOME_TRATADO = 'rmc_tratado'

# ---------------------------------------------------------------------------
# Passo 1: mesclagens com os selects do Oracle, aplicadas em ordem
# ---------------------------------------------------------------------------
ETAPAS: list[dict] = [
    {
        'select': 'TB_CLIENTE',
        'chave_silver': 'cod_cliente',
        'chave_select': 'codcli',
        'colunas': {
            'sigufs': 'sigufs',
            'usu_codram': 'usu_codram',
            'usu_desram': 'usu_desram',
            'xregsenha': 'xregsenha',
        },
    },
    {
        'select': 'TB_PRODUTO',
        'chave_silver': 'codproduto',
        'chave_select': 'codpro',
        'colunas': {
            'codagc': 'codagc',
            'usu_claman': 'usu_claman',
            'qtdpct': 'qtdpct',
            'volpro_un': 'volpro_un',
            'usu_codfamday': 'usu_codfamday',
            'usu_desfamday': 'usu_desfamday',
            'produto_zero': 'produto_zero',
            'classificacao_bi': 'classificacao_bi',
            'codclc': 'codclc',
        },
    },
]

# ---------------------------------------------------------------------------
# Passo 2: agregacao
# ---------------------------------------------------------------------------
# colunas de quebra, na ordem em que saem no arquivo
QUEBRAS = [
    'mes_ano', 'operacao',
    'sigufs', 'xregsenha', 'usu_codram', 'usu_desram',
    'codagc', 'usu_claman',
    'usu_codfamday', 'usu_desfamday', 'produto_zero', 'classificacao_bi', 'codclc',
]

# colunas de valores que sao somadas
VALORES = [
    'qtd_item', 'cpv_item_venda', 'valor_venda', 'valor_cpv_bonif', 'valor_desconto', 'valor_outras',
    'valor_ipi', 'valor_icms', 'valor_fcp', 'valor_st', 'valor_pis_venda', 'valor_cofins',
    'total_impostos', 'valor_comissao', 'cpv_proc_fixo', 'desp_oper_fixa', 'cred_impostos',
    'verba_fixa', 'verba_variavel', 'frete',
]


def caminho_gold(meses: list[str] | None = None, nome: str = NOME_GOLD) -> Path:
    """<nome>.parquet, ou <nome>_<meses>.parquet quando e uma amostra de meses."""
    return GOLD / f'{nome}_{"_".join(meses)}.parquet' if meses else GOLD / f'{nome}.parquet'


def carregar_select(nome: str, consultar_banco: bool) -> pd.DataFrame:
    """Executa o select no Oracle ou, se ja foi salvo na bronze, reaproveita o parquet."""
    if consultar_banco:
        return executar_select(nome)
    try:
        return ler_select_bronze(nome)
    except FileNotFoundError:
        return executar_select(nome)


def mesclar(df: pd.DataFrame, etapa: dict, consultar_banco: bool = False) -> pd.DataFrame:
    """Aplica uma etapa: left join da silver com as colunas escolhidas do select."""
    tabela = carregar_select(etapa['select'], consultar_banco)
    chave_s, chave_t = etapa['chave_silver'], etapa['chave_select']
    colunas = etapa['colunas']

    faltando = [c for c in [chave_t, *colunas] if c not in tabela.columns]
    if faltando:
        raise KeyError(f"{etapa['select']}: colunas nao encontradas no select: {faltando}")

    lado = tabela[[chave_t, *colunas]].rename(columns=colunas)
    # inteiros viram Int64 para nao virar float quando o left join gerar nulos
    for col in lado.columns:
        if pd.api.types.is_integer_dtype(lado[col]):
            lado[col] = lado[col].astype('Int64')
    duplicadas = lado[chave_t].duplicated().sum()
    if duplicadas:
        print(f"  aviso: {etapa['select']} tem {duplicadas:,} chaves repetidas em {chave_t}; mantendo a primeira")
        lado = lado.drop_duplicates(chave_t)

    # chaves com o mesmo tipo dos dois lados para o merge nao falhar silenciosamente
    if pd.api.types.is_numeric_dtype(df[chave_s]):
        lado[chave_t] = pd.to_numeric(lado[chave_t], errors='coerce').astype('Int64')
        df[chave_s] = df[chave_s].astype('Int64')
    else:
        lado[chave_t] = lado[chave_t].astype('string').str.strip()
        df[chave_s] = df[chave_s].astype('string').str.strip()

    antes = len(df)
    df = df.merge(lado, how='left', left_on=chave_s, right_on=chave_t)
    if chave_t != chave_s:
        df = df.drop(columns=chave_t)
    assert len(df) == antes, 'merge alterou a quantidade de linhas'

    sem_par = df[list(colunas.values())[0]].isna().sum()
    print(f"  {etapa['select']}: +{len(colunas)} colunas, {sem_par:,} linhas sem correspondencia em {chave_s}")
    return df


def tratar_regras(df: pd.DataFrame) -> pd.DataFrame:
    """Ajustes de negocio aplicados apos as mesclagens, ainda linha a linha.

    Regra 1: saidas com produto informado mas sem familia no cadastro (usu_codfamday nulo)
             recebem usu_desfamday = 'Outros Produtos'.
    """
    df = df.copy()

    outros = (
        df['operacao'].str.strip().str.lower().eq('saidas')
        & df['codproduto'].notna()
        & df['usu_codfamday'].isna()
    )
    df.loc[outros, 'usu_desfamday'] = 'Outros Produtos'
    print(f"  regra Outros Produtos: {int(outros.sum()):,} linhas de saida sem familia marcadas")

    return df


def montar_linhas(consultar_banco: bool = False, meses: list[str] | None = None) -> pd.DataFrame:
    """Passo 1: silver + todas as mesclagens + regras de negocio, ainda linha a linha."""
    df = ler_silver(meses=meses)
    print(f'Silver ({", ".join(meses) if meses else "todos os meses"}): {len(df):,} linhas x {df.shape[1]} colunas')
    for etapa in ETAPAS:
        df = mesclar(df, etapa, consultar_banco)
    return tratar_regras(df)


def agregar(df: pd.DataFrame) -> pd.DataFrame:
    """Passo 2: soma os valores por quebra e conta clientes distintos."""
    faltando = [c for c in [*QUEBRAS, *VALORES, 'cod_cliente'] if c not in df.columns]
    if faltando:
        raise KeyError(f'Colunas esperadas nao encontradas apos as mesclagens: {faltando}')

    agregacoes = {col: 'sum' for col in VALORES}
    agregacoes['cod_cliente'] = 'nunique'

    # dropna=False mantem grupos com canal ou produto nulos
    final = df.groupby(QUEBRAS, dropna=False, sort=True).agg(agregacoes).reset_index()
    final = final.rename(columns={'cod_cliente': 'qtd_clientes'})

    # mes_ano sai como inteiro AAAAMM (ex.: 202609), chave de periodo para o BI
    final['mes_ano'] = (final['mes_ano'].dt.year * 100 + final['mes_ano'].dt.month).astype('Int64')

    # qtd_clientes logo apos as quebras, antes dos valores
    return final[[*QUEBRAS, 'qtd_clientes', *VALORES]]


def conferir(df: pd.DataFrame, final: pd.DataFrame) -> None:
    """Garante que a soma dos valores nao mudou com a agregacao."""
    for col in VALORES:
        origem, agregado = df[col].sum(), final[col].sum()
        if abs(origem - agregado) > 0.01:
            raise AssertionError(f'{col}: soma na origem {origem:,.2f} difere do agregado {agregado:,.2f}')
    print(f'Conferido: {len(VALORES)} colunas de valores com soma identica a origem.')


def salvar_tratado(linhas: pd.DataFrame, meses: list[str] | None = None) -> Path:
    """Grava a base linha a linha com as mesclagens, sem agregacao, para validacao."""
    GOLD.mkdir(parents=True, exist_ok=True)
    destino = caminho_gold(meses, NOME_TRATADO)
    linhas.to_parquet(destino, index=False)
    print(f'\nSalvo em: {destino} ({destino.stat().st_size / 1024**2:.1f} MB)')
    print(f'{destino.stem}: {len(linhas):,} linhas x {linhas.shape[1]} colunas')
    return destino


def salvar_gold(final: pd.DataFrame, meses: list[str] | None = None) -> Path:
    GOLD.mkdir(parents=True, exist_ok=True)
    destino = caminho_gold(meses)
    final.to_parquet(destino, index=False)
    print(f'\nSalvo em: {destino} ({destino.stat().st_size / 1024**2:.1f} MB)')
    print(f'{destino.stem}: {len(final):,} linhas x {final.shape[1]} colunas')
    salvar_excel(final, destino.with_suffix('.xlsx'))
    return destino


def salvar_excel(final: pd.DataFrame, destino: Path) -> Path:
    """Grava o mesmo agregado em .xlsx, ja que o Excel nao le parquet.

    Valores com duas casas e cabecalho fixo com filtro.
    """
    with pd.ExcelWriter(destino, engine='openpyxl') as escritor:
        final.to_excel(escritor, sheet_name=NOME_GOLD, index=False)
        planilha = escritor.sheets[NOME_GOLD]
        planilha.freeze_panes = 'A2'
        planilha.auto_filter.ref = planilha.dimensions

        colunas = list(final.columns)
        for idx, nome in enumerate(colunas, start=1):
            letra = planilha.cell(row=1, column=idx).column_letter
            if nome in VALORES:
                for celula in planilha[letra][1:]:
                    celula.number_format = '#,##0.00'
            largura = max(len(str(nome)), 12 if nome in VALORES else 10)
            planilha.column_dimensions[letra].width = min(largura + 2, 40)

    print(f'Salvo em: {destino} ({destino.stat().st_size / 1024**2:.1f} MB)')
    return destino


def executar(consultar_banco: bool = False, meses: list[str] | None = None) -> Path:
    """Etapa gold completa: mescla (rmc_tratado), agrega, confere e grava o rmc_gold."""
    linhas = montar_linhas(consultar_banco, meses)
    salvar_tratado(linhas, meses)
    final = agregar(linhas)
    print(f'Agregado: {len(linhas):,} linhas -> {len(final):,} grupos')
    conferir(linhas, final)
    return salvar_gold(final, meses)


def main() -> None:
    """Uso: python -m src.transform_gold [--banco] [--mes AAAA-MM ...]

    --banco  forca reconsultar o Oracle mesmo que o select ja esteja salvo na bronze
    --mes    processa so os meses informados (amostra), gravando em arquivo separado
    """
    args = sys.argv[1:]
    consultar_banco = '--banco' in args
    meses = [a for a in args if a[:1].isdigit()] or None
    executar(consultar_banco, meses)


if __name__ == '__main__':
    main()
