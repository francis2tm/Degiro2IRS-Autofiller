import argparse
def getArgs():
    parser = argparse.ArgumentParser(description='Degiro2IRS-Autofiller')

    parser.add_argument(
        "-i",
        "--irs_file",
        dest="irs_file",
        default=None,
        help="Ficheiro IRS .xml pre-preenchido gerado na plataforma IRS da AT.",
        required=True,
    )

    parser.add_argument(
        "-t",
        "--transactions_file",
        dest="transactions_file",
        default='Transactions.csv',
        help="Ficheiro .csv com todas as transações da degiro até ao final do ano fiscal pretendido.",
        required=False,
    )

    parser.add_argument(
        "-y",
        "--year",
        dest="irs_year",
        help="Ano fiscal pretendido.",
        required=True,
    )

    parser.add_argument(
        "-l",
        "--line_offset",
        dest="line_offset",
        help="Primeira linha da tabela 9.2-A do Anexo J (lá diz \"Nº Linha (XXX a ...)\"",
        required=True,
    )

    args = parser.parse_args()

    return args