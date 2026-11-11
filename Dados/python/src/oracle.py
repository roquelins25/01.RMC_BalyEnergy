"""Conexao com o Oracle e execucao dos selects da pasta src/selects.

Credenciais vem do arquivo .env na raiz do projeto:
    ORACLE_USER=usuario
    ORACLE_PASSWORD=senha
    ORACLE_DSN=host:porta/servico

O servidor exige criptografia nativa de rede, que o python-oracledb so suporta em
modo thick. Por isso e carregado o Oracle Client instalado junto com o Power BI
("Oracle Client for Microsoft Tools"). Outro caminho pode ser indicado no .env:
    ORACLE_CLIENT_DIR=C:/caminho/do/instantclient

Cada select executado e salvo como parquet em medalion/bronze/oracle/<nome>.parquet,
para que a gold possa ser remontada sem reconsultar o banco.
"""

import os
import time
from pathlib import Path

import oracledb
import pandas as pd
from dotenv import load_dotenv

from .extract import BRONZE

RAIZ = Path(__file__).resolve().parent.parent
PASTA_SELECTS = Path(__file__).resolve().parent / 'selects'
PASTA_ORACLE_BRONZE = BRONZE / 'oracle'

load_dotenv(RAIZ / '.env')

CLIENT_DIR_PADRAO = r'C:\Program Files\Oracle Client for Microsoft Tools'


def ativar_modo_thick() -> None:
    """Carrega o Oracle Client (modo thick). Ignorado se ja foi carregado."""
    if oracledb.is_thin_mode() is False:
        return
    lib_dir = os.getenv('ORACLE_CLIENT_DIR') or CLIENT_DIR_PADRAO
    if not Path(lib_dir).is_dir():
        raise OSError(
            f'Oracle Client nao encontrado em {lib_dir}. '
            'Instale o Instant Client ou informe ORACLE_CLIENT_DIR no .env.'
        )
    oracledb.init_oracle_client(lib_dir=lib_dir)


def listar_selects(pasta: Path = PASTA_SELECTS) -> list[str]:
    """Nomes dos selects disponiveis (sem extensao), ex.: ['TB_CLIENTE', 'TB_PRODUTO']."""
    return sorted(p.stem for p in pasta.iterdir() if p.suffix.lower() == '.sql')


def ler_select(nome: str, pasta: Path = PASTA_SELECTS) -> str:
    """Le o texto do select <nome>.SQL e remove o ';' final, que o oracledb nao aceita."""
    candidatos = [p for p in pasta.iterdir() if p.stem.upper() == nome.upper() and p.suffix.lower() == '.sql']
    if not candidatos:
        raise FileNotFoundError(f'Select {nome} nao encontrado em {pasta}. Disponiveis: {listar_selects(pasta)}')
    return candidatos[0].read_text(encoding='utf-8').strip().rstrip(';')


def conectar() -> oracledb.Connection:
    usuario = os.getenv('ORACLE_USER')
    senha = os.getenv('ORACLE_PASSWORD')
    dsn = os.getenv('ORACLE_DSN')
    faltando = [k for k, v in [('ORACLE_USER', usuario), ('ORACLE_PASSWORD', senha), ('ORACLE_DSN', dsn)] if not v]
    if faltando:
        raise OSError(f'Variaveis ausentes no .env: {faltando}')
    ativar_modo_thick()
    return oracledb.connect(user=usuario, password=senha, dsn=dsn)


def executar_select(nome: str, salvar: bool = True) -> pd.DataFrame:
    """Executa o select <nome> no Oracle e devolve um DataFrame com colunas em minusculo."""
    sql = ler_select(nome)
    print(f'Executando {nome} no Oracle...')
    inicio = time.perf_counter()
    with conectar() as conexao, conexao.cursor() as cursor:
        cursor.arraysize = 10_000
        cursor.execute(sql)
        colunas = [c[0].lower() for c in cursor.description]
        df = pd.DataFrame(cursor.fetchall(), columns=colunas)
    print(f'  {len(df):,} linhas x {df.shape[1]} colunas em {time.perf_counter() - inicio:.1f}s')

    if salvar:
        PASTA_ORACLE_BRONZE.mkdir(parents=True, exist_ok=True)
        destino = PASTA_ORACLE_BRONZE / f'{nome.lower()}.parquet'
        df.to_parquet(destino, index=False)
        print(f'  salvo em {destino}')
    return df


def ler_select_bronze(nome: str) -> pd.DataFrame:
    """Le o resultado de um select ja salvo na bronze, sem consultar o banco."""
    caminho = PASTA_ORACLE_BRONZE / f'{nome.lower()}.parquet'
    if not caminho.is_file():
        raise FileNotFoundError(f'{caminho} nao existe. Rode executar_select("{nome}") antes.')
    return pd.read_parquet(caminho)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print('Uso: python -m src.oracle <NOME_DO_SELECT>')
        print('Disponiveis:', listar_selects())
        sys.exit(1)
    df = executar_select(sys.argv[1])
    print(df.head(10).to_string())
    print()
    print(df.dtypes.to_string())
