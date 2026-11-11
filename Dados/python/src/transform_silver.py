"""Tratamento da camada silver.

Entrada: medalion/bronze/dre_cliente.parquet (gerado por transform_bronze.py).
Saida:   medalion/silver/dre_cliente/AAAA-MM.parquet (um arquivo por mes)

Regras:
  1. Quebrar em um parquet por mes, pela coluna mes_ano
  2. Manter somente as colunas de COLUNAS_SILVER

Ao reprocessar, somente os meses presentes no Excel atual sao sobrescritos.
Linhas duplicadas na origem sao mantidas.
"""

from pathlib import Path

import pandas as pd

from .extract import MEDALION
from .transform_bronze import ler_parquet_bronze

SILVER = MEDALION / 'silver'
GOLD = MEDALION / 'gold'
PASTA_MENSAL = SILVER / 'dre_cliente'

# Regra 2: colunas mantidas (nomes ja em minusculo, como saem de transform_bronze.tratar)
COLUNAS_SILVER = [
    'operacao', 'filial', 'mes_ano', 'data_nf', 'tipo_nota', 'codigo_repres_nf', 'nota_fiscal',
    'cod_cliente', 'cfop', 'codproduto', 'qtd_item', 'cpv_item_venda', 'valor_venda',
    'valor_cpv_bonif', 'valor_desconto', 'valor_outras', 'valor_ipi', 'valor_icms', 'valor_fcp',
    'valor_st', 'valor_pis_venda', 'valor_cofins', 'total_impostos', 'valor_comissao',
    'cpv_proc_fixo', 'desp_oper_fixa', 'cred_impostos', 'verba_fixa', 'verba_variavel', 'frete',
    'motivo_devolucao',
]


def selecionar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Regra 2: mantem apenas as colunas da silver, na ordem definida."""
    faltando = [c for c in COLUNAS_SILVER if c not in df.columns]
    if faltando:
        raise KeyError(f'Colunas esperadas nao encontradas nos dados tratados: {faltando}')
    return df[COLUNAS_SILVER]


def salvar_por_mes(df: pd.DataFrame, pasta: Path = PASTA_MENSAL) -> list[Path]:
    """Regra 1: grava um parquet por mes de mes_ano, sobrescrevendo so os meses presentes."""
    if df['mes_ano'].isna().any():
        qtd = int(df['mes_ano'].isna().sum())
        raise ValueError(f'{qtd} linhas sem mes_ano; nao e possivel particionar por mes.')

    pasta.mkdir(parents=True, exist_ok=True)
    gravados = []
    for periodo, grupo in df.groupby(df['mes_ano'].dt.to_period('M'), sort=True):
        destino = pasta / f'{periodo}.parquet'
        grupo.to_parquet(destino, index=False)
        gravados.append(destino)
        print(f'  {destino.name}: {len(grupo):>8,} linhas  valor_venda={grupo["valor_venda"].sum():>18,.2f}')
    return gravados


def ler_silver(pasta: Path = PASTA_MENSAL, meses: list[str] | None = None) -> pd.DataFrame:
    """Le os parquets mensais da silver em um unico DataFrame.

    meses: lista no formato 'AAAA-MM' para ler so alguns meses; None le todos.
    """
    if meses:
        arquivos = [pasta / f'{m}.parquet' for m in meses]
        inexistentes = [a.name for a in arquivos if not a.is_file()]
        if inexistentes:
            raise FileNotFoundError(f'Meses sem parquet na silver: {inexistentes}')
    else:
        arquivos = sorted(pasta.glob('*.parquet'))
    if not arquivos:
        raise FileNotFoundError(f'Nenhum parquet mensal em {pasta}. Rode a etapa silver antes.')
    return pd.concat((pd.read_parquet(a) for a in arquivos), ignore_index=True)


def executar() -> list[Path]:
    """Etapa silver completa: le o parquet da bronze, seleciona colunas e grava por mes."""
    df = selecionar_colunas(ler_parquet_bronze())
    print(f'Gravando {len(df):,} linhas x {df.shape[1]} colunas em {PASTA_MENSAL}:')
    arquivos = salvar_por_mes(df)
    total_mb = sum(a.stat().st_size for a in arquivos) / 1024**2
    print(f'\n{len(arquivos)} arquivos gravados ({total_mb:.1f} MB no total)')
    return arquivos


def main() -> None:
    """Uso: python -m src.transform_silver"""
    executar()


if __name__ == '__main__':
    main()
