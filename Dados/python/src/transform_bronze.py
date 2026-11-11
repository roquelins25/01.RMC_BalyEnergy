"""Tratamento da camada bronze: leitura e limpeza do Excel bruto.

Le o Excel salvo em medalion/bronze (aba 'DRE_Geral - Jan26 a Set26'), limpa e
tipa as colunas e grava o resultado completo em medalion/bronze/dre_cliente.parquet.
Esse parquet e a entrada de transform_silver.py.

Estrutura da aba de origem:
  - linhas 1 a 26: bloco de resumo do DRE (ignorado)
  - linha 27: cabecalho das colunas
  - linha 28 em diante: dados (uma linha por item de nota fiscal)

Particularidades da origem tratadas aqui:
  - numeros como texto no padrao BR ('15603,98'), em meses inteiros
  - datas como texto 'dd/mm/aaaa', 'mm/aaaa', ISO ou serial do Excel (46113)
  - cabecalho 'pode' no lugar de 'Supervisor'
"""

import sys
import time
from pathlib import Path

import pandas as pd

from .extract import BRONZE

PARQUET_BRONZE = BRONZE / 'dre_cliente.parquet'
ABA = 'DRE_Geral - Jan26 a Set26'
LINHA_CABECALHO = 26  # indice zero-based: cabecalho esta na linha 27 do Excel

# Cabecalhos da origem que vem com nome errado/fora do padrao
RENOMEAR = {
    'pode': 'Supervisor',
    'valor_COFINS': 'Valor_COFINS',
}

COLUNAS_DATA = ['Mes_Ano', 'Data_NF']

COLUNAS_CODIGO = [
    'Filial', 'Codigo_repres_NF', 'Nota_Fiscal', 'Cod_Cliente', 'Cod_Grupo', 'CFOP', 'CodProduto',
]

COLUNAS_TEXTO = [
    'Operacao', 'Tipo_Nota', 'Regiao', 'UF', 'Representante', 'Supervisor', 'Key_Account',
    'Gerente_Regional', 'Gerente_Nacional', 'Razao_Social', 'Grupo_Empresa', 'Descricao_CFOP',
    'Produto', 'Classificacao', 'Classificacao_BI', 'Segmento', 'Motivo_Devolucao',
]

COLUNAS_VALOR = [
    'Volume_Embalagem', 'Qtd_Item', 'CPV_Item_Venda', 'Valor_Venda', 'Valor_CPV_Bonif',
    'Valor_Desconto', 'Valor_Outras', 'Valor_IPI', 'Valor_ICMS', 'Valor_FCP', 'Valor_ST',
    'Valor_PIS_Venda', 'Valor_COFINS', 'Total_Impostos', 'Valor_Comissao', 'CPV_Proc_Fixo',
    'DESP_Oper_Fixa', 'CRED_Impostos', 'Verba_Fixa', 'Verba_Variavel', 'Frete',
]


def excel_bronze_mais_recente(pasta: Path = BRONZE) -> Path:
    """O .xlsx mais recente copiado para a bronze."""
    arquivos = [p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() == '.xlsx']
    if not arquivos:
        raise FileNotFoundError(f'Nenhum .xlsx em {pasta}. Rode a extracao antes.')
    return max(arquivos, key=lambda p: p.stat().st_mtime)


def ler_bronze(nome_arquivo: str | None = None, aba: str = ABA) -> pd.DataFrame:
    """Le a aba de dados do Excel bruto, pulando o bloco de resumo do topo.

    Sem nome, usa o .xlsx mais recente da bronze.
    """
    caminho = BRONZE / nome_arquivo if nome_arquivo else excel_bronze_mais_recente()
    if not caminho.is_file():
        raise FileNotFoundError(f'Arquivo nao encontrado na bronze: {caminho}. Rode a extracao antes.')

    print(f'Lendo {caminho.name} / aba "{aba}" (cerca de 30s com calamine)...')
    inicio = time.perf_counter()
    df = pd.read_excel(caminho, sheet_name=aba, header=LINHA_CABECALHO, engine='calamine')
    print(f'  {len(df):,} linhas x {df.shape[1]} colunas lidas em {time.perf_counter() - inicio:.0f}s')
    return df


def converter_data(serie: pd.Series) -> pd.Series:
    """Converte coluna de data que mistura formatos para datetime.

    Na origem aparecem: datetime, serial do Excel (46113), texto ISO
    ('2026-02-01 00:00:00'), texto 'dd/mm/aaaa' e texto 'mm/aaaa'.
    Texto e sempre lido com dia primeiro (padrao BR).
    """
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie.dt.normalize()

    eh_numero = serie.map(lambda v: isinstance(v, (int, float)) and not isinstance(v, bool))
    serial = pd.to_numeric(serie.where(eh_numero), errors='coerce')
    como_serial = pd.to_datetime(serial, unit='D', origin='1899-12-30', errors='coerce')

    texto = serie.where(~eh_numero).astype('string').str.strip()
    como_data = pd.to_datetime(texto, format='ISO8601', errors='coerce')
    como_data = como_data.fillna(pd.to_datetime(texto, format='%d/%m/%Y', errors='coerce'))
    como_data = como_data.fillna(pd.to_datetime(texto, format='%m/%Y', errors='coerce'))
    como_data = como_data.fillna(pd.to_datetime(texto, dayfirst=True, errors='coerce'))

    return como_serial.fillna(como_data).dt.normalize()


def converter_numero(serie: pd.Series) -> pd.Series:
    """Converte coluna numerica que mistura numero e texto no padrao BR ('1.234,56')."""
    if pd.api.types.is_numeric_dtype(serie):
        return serie.astype('float64')

    eh_texto = serie.map(lambda v: isinstance(v, str))
    texto = serie.where(eh_texto).astype('string').str.strip()
    tem_virgula = texto.str.contains(',', na=False)
    texto = texto.where(~tem_virgula, texto.str.replace('.', '', regex=False).str.replace(',', '.', regex=False))

    numero = pd.to_numeric(serie.where(~eh_texto), errors='coerce').astype('float64')
    de_texto = pd.to_numeric(texto, errors='coerce').astype('float64')
    return numero.fillna(de_texto)


def tratar(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa e tipa o DataFrame bruto."""
    df = df.copy()

    # colunas sem nome (Unnamed) e linhas totalmente vazias
    df = df.loc[:, ~df.columns.astype(str).str.startswith('Unnamed')]
    df = df.dropna(how='all')

    df = df.rename(columns=RENOMEAR)
    df.columns = df.columns.str.strip()

    # linhas sem Operacao sao rodape/lixo
    df = df[df['Operacao'].notna()]

    for col in COLUNAS_DATA:
        if col in df:
            df[col] = converter_data(df[col])

    for col in COLUNAS_TEXTO:
        if col in df:
            df[col] = df[col].astype('string').str.strip()

    for col in COLUNAS_CODIGO:
        if col in df:
            df[col] = converter_numero(df[col]).astype('Int64')

    for col in COLUNAS_VALOR:
        if col in df:
            df[col] = converter_numero(df[col]).fillna(0.0)

    # colunas derivadas uteis para o BI
    if 'Mes_Ano' in df:
        df['Ano'] = df['Mes_Ano'].dt.year.astype('Int64')
        df['Mes'] = df['Mes_Ano'].dt.month.astype('Int64')

    df.columns = df.columns.str.lower()
    return df.reset_index(drop=True)


def salvar_parquet_bronze(df: pd.DataFrame, destino: Path = PARQUET_BRONZE) -> Path:
    """Grava o Excel tratado, completo, como parquet na bronze (prova da conversao xlsx -> parquet)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(destino, index=False)
    print(f'Salvo em: {destino} ({destino.stat().st_size / 1024**2:.1f} MB)')
    return destino


def ler_parquet_bronze(caminho: Path = PARQUET_BRONZE) -> pd.DataFrame:
    """Le o parquet tratado da bronze. Entrada da camada silver."""
    if not caminho.is_file():
        raise FileNotFoundError(f'Parquet nao encontrado: {caminho}. Rode a etapa bronze antes.')
    return pd.read_parquet(caminho)


def resumo(df: pd.DataFrame) -> None:
    print('\nResumo dos dados tratados:')
    print(f'  linhas: {len(df):,}')
    print(f'  periodo: {df["mes_ano"].min():%Y-%m} a {df["mes_ano"].max():%Y-%m}')
    print(f'  datas nulas (data_nf): {df["data_nf"].isna().sum():,}')
    print('  valor_venda por mes x operacao:')
    tabela = df.pivot_table(index='mes_ano', columns='operacao', values='valor_venda', aggfunc='sum').round(2)
    tabela.index = tabela.index.strftime('%Y-%m')
    print(tabela.to_string(float_format='{:,.2f}'.format))


def executar(nome_arquivo: str | None = None) -> pd.DataFrame:
    """Etapa bronze completa: le o Excel, trata, grava o parquet e mostra o resumo."""
    df = tratar(ler_bronze(nome_arquivo))
    salvar_parquet_bronze(df)
    resumo(df)
    return df


def main() -> None:
    """Uso: python -m src.transform_bronze [NOME_DO_ARQUIVO.xlsx]"""
    executar(sys.argv[1] if len(sys.argv) > 1 else None)


if __name__ == '__main__':
    main()
