"""Extracao: copia o Excel bruto do DRE Cliente da pasta de rede para medalion/bronze.

Na camada bronze o arquivo fica exatamente como veio da origem, sem transformacao.
"""

import shutil
import sys
from pathlib import Path

PASTA_DRE = Path(r'\\dados\Financeiro\Controladoria\BD_BI\DRE CLIENTE CONSOLIDADO')

RAIZ = Path(__file__).resolve().parent.parent
MEDALION = RAIZ / 'medalion'
BRONZE = MEDALION / 'bronze'


def listar_arquivos(pasta: Path = PASTA_DRE) -> list[Path]:
    """Lista os .xlsx da pasta, ignorando subpastas (ex.: old)."""
    return sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() == '.xlsx')


def arquivo_mais_recente(pasta: Path = PASTA_DRE) -> Path:
    """O .xlsx com data de modificacao mais recente na pasta."""
    arquivos = listar_arquivos(pasta)
    if not arquivos:
        raise FileNotFoundError(f'Nenhum .xlsx em {pasta}')
    return max(arquivos, key=lambda p: p.stat().st_mtime)


def extrair_para_bronze(nome_arquivo: str | None = None, origem: Path = PASTA_DRE, destino: Path = BRONZE) -> Path:
    """Copia o Excel bruto da origem para a bronze. Sem nome, usa o mais recente da origem."""
    arquivo_origem = origem / nome_arquivo if nome_arquivo else arquivo_mais_recente(origem)
    if not arquivo_origem.is_file():
        raise FileNotFoundError(f'Arquivo nao encontrado na origem: {arquivo_origem}')

    destino.mkdir(parents=True, exist_ok=True)
    arquivo_destino = destino / arquivo_origem.name

    print(f'Copiando {arquivo_origem.name} ({arquivo_origem.stat().st_size / 1024**2:.1f} MB)...')
    shutil.copy2(arquivo_origem, arquivo_destino)
    print(f'Salvo em: {arquivo_destino}')
    return arquivo_destino


def main() -> None:
    """Uso: python -m src.extract [NOME_DO_ARQUIVO.xlsx]"""
    print('Arquivos na origem:')
    for arquivo in listar_arquivos():
        print(f'  - {arquivo.name}')
    extrair_para_bronze(sys.argv[1] if len(sys.argv) > 1 else None)


if __name__ == '__main__':
    main()
