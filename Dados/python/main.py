"""Pipeline RMC: Excel do DRE Cliente (rede) -> bronze -> silver -> gold.

Uso:
    uv run python main.py                                   roda tudo com o Excel mais recente da rede
    uv run python main.py --arquivo "DRE CLIENTE_10112026.xlsx"
    uv run python main.py --etapas silver gold              roda so algumas etapas
    uv run python main.py --mes 2026-09                     gold so de um mes (amostra em arquivo separado)
    uv run python main.py --banco                           reconsulta o Oracle em vez de usar os selects salvos

Etapas, em ordem:
    extract  copia o Excel da pasta de rede para medalion/bronze
    bronze   le o Excel, limpa e tipa, grava medalion/bronze/dre_cliente.parquet
    silver   seleciona colunas e grava um parquet por mes em medalion/silver/dre_cliente
    gold     mescla com os cadastros do Oracle, agrega por UF/produto e grava medalion/gold/rmc_gold.parquet
"""

import argparse
import sys
import time

from src import extract, transform_bronze, transform_gold, transform_silver

ETAPAS = ['extract', 'bronze', 'silver', 'gold']


def main() -> int:
    parser = argparse.ArgumentParser(description='Pipeline RMC: Excel -> bronze -> silver -> gold')
    parser.add_argument('--arquivo', help='nome do .xlsx na pasta de rede (padrao: o mais recente)')
    parser.add_argument('--etapas', nargs='+', choices=ETAPAS, default=ETAPAS, metavar='ETAPA',
                        help=f'etapas a executar, em ordem: {" ".join(ETAPAS)} (padrao: todas)')
    parser.add_argument('--mes', nargs='+', metavar='AAAA-MM',
                        help='na gold, processa so esses meses e grava rmc_gold_<mes>.parquet')
    parser.add_argument('--banco', action='store_true', help='reconsulta o Oracle em vez de usar os selects salvos')
    args = parser.parse_args()

    etapas = [e for e in ETAPAS if e in args.etapas]
    inicio_total = time.perf_counter()
    nome_arquivo = args.arquivo

    for etapa in etapas:
        print(f'\n{"=" * 70}\n  ETAPA {etapa.upper()}\n{"=" * 70}')
        inicio = time.perf_counter()
        try:
            if etapa == 'extract':
                nome_arquivo = extract.extrair_para_bronze(nome_arquivo).name
            elif etapa == 'bronze':
                transform_bronze.executar(nome_arquivo)
            elif etapa == 'silver':
                transform_silver.executar()
            elif etapa == 'gold':
                transform_gold.executar(consultar_banco=args.banco, meses=args.mes)
        except Exception as erro:  # noqa: BLE001 - qualquer falha interrompe o pipeline com mensagem clara
            print(f'\nERRO na etapa {etapa}: {erro}', file=sys.stderr)
            return 1
        print(f'\n  etapa {etapa} concluida em {time.perf_counter() - inicio:.0f}s')

    print(f'\nPipeline concluido em {time.perf_counter() - inicio_total:.0f}s ({", ".join(etapas)})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
