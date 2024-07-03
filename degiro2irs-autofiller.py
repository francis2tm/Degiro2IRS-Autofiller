import queue
from string import printable
import numpy as np
import pandas as pd
import datetime
import time
import sys
import math
import pycountry
import os
import arg_parser

OUTPUT_FILE_DIR = "output/irs_com_J-9.2a.xml"

BUY = 0
SELL = 1

IRS_COLUMN_LIST = ['NLinha', 'CodPais', 'Codigo', 'AnoRealizacao', 'MesRealizacao', 'DiaRealizacao', 'ValorRealizacao', 'AnoAquisicao', 'MesAquisicao', 'DiaAquisicao', 'ValorAquisicao', 'DespesasEncargos']

IRS_CODIGO = 'G01'
IRS_TABLE_NAME = "AnexoJq092AT01"

def createIRSEntry(irs_isin_df, nline_offset, amount, trans_cost, buy_row, sell_row):
    nline = len(irs_isin_df) + nline_offset
    country_code = pycountry.countries.get(alpha_2=buy_row["ISIN"][0:2]).numeric
    codigo = IRS_CODIGO
    ano_realizacao = sell_row["date"].split('-')[-1]
    mes_realizacao = sell_row["date"].split('-')[-2]
    dia_realizacao = sell_row["date"].split('-')[-3]
    valor_realizacao = amount*sell_row["price"]
    ano_aquisicao = buy_row["date"].split('-')[-1]
    mes_aquisicao = buy_row["date"].split('-')[-2]
    dia_aquisicao = buy_row["date"].split('-')[-3]
    valor_aquisicao = amount*buy_row["price"]
    despesas_encargo = trans_cost

    new_row = {
        IRS_COLUMN_LIST[0]: nline,
        IRS_COLUMN_LIST[1]: country_code,
        IRS_COLUMN_LIST[2]: codigo,
        IRS_COLUMN_LIST[3]: ano_realizacao,
        IRS_COLUMN_LIST[4]: mes_realizacao,
        IRS_COLUMN_LIST[5]: dia_realizacao,
        IRS_COLUMN_LIST[6]: valor_realizacao,
        IRS_COLUMN_LIST[7]: ano_aquisicao,
        IRS_COLUMN_LIST[8]: mes_aquisicao,
        IRS_COLUMN_LIST[9]: dia_aquisicao,
        IRS_COLUMN_LIST[10]: valor_aquisicao,
        IRS_COLUMN_LIST[11]: despesas_encargo
    }
    irs_isin_df.append(new_row)

def main():
    #Read arguments
    args = arg_parser.getArgs()
    irs_year = int(args.irs_year)
    irs_file = args.irs_file
    transactions_file = args.transactions_file
    line_offset = int(args.line_offset)

    #Create the irs rows list
    irs_list = []

    #main----------------------------------------------------------
    org_df = pd.read_csv(transactions_file)
    org_df.rename(columns={'Data': 'date', 'Hora': 'hour', 'Valor': 'value', 'Custos de transação': 'trans_cost', 'Quantidade': 'amount', 'Preços': 'price'}, inplace=True)

    #Create a timestamp column, instead of relying on 'date' and 'hour' for temporal determination.
    def calcNewTimestampColumn(row):
        timestamp = time.mktime(time.strptime(row["date"] + " " + row["hour"], "%d-%m-%Y %H:%M"))
        return timestamp
    org_df["timestamp"] = org_df.apply(calcNewTimestampColumn, axis=1) #axis=1 makes sure that function is applied to each row

    #Create year column
    def calcNewYearColumn(row):
        year = int(row["date"][6:10])
        return year
    org_df["year"] = org_df.apply(calcNewYearColumn, axis=1) #axis=1 makes sure that function is applied to each row

    #Sort dateframe rows based on a 'ISIN' & 'timestamp' columns
    #if duplicate value is present in 'ISIN' column then sorting will be done according to 'timestamp' column
    org_df = org_df.sort_values(by=["ISIN", "timestamp"])

    #Replace NaNs with 0 in trans_cost column
    org_df["trans_cost"].fillna(0, inplace=True)
    #org_df.to_csv("sorted.csv", sep=',')

    #Seperate dataframe into a list of dataframes oraganized by unique ISINs
    isin_unique_list = org_df["ISIN"].unique()  #Get unique ISINs

    df_list = []
    for isin_unique in isin_unique_list:
        isin_df = org_df[org_df["ISIN"] == isin_unique]
        df_list.append(isin_df)

    print("Metrics by financial product---------------------------------------------------------------------------------------")

    #Perform FIFO in each isin_df
    for isin_df in df_list:
        #if isin_df.iloc[0]["ISIN"] != "IE00B4L5Y983":
        #    continue
        buys_list = []  #List that holds every purchase of stock, resets when changing product
        irs_isin_list = []
        for index, row in isin_df.iterrows():
            action = BUY if row["amount"] > 0 else SELL
            row["amount"] = abs(row["amount"])
            row["trans_cost"] = abs(row["trans_cost"])

            if action == BUY:
                buys_list.insert(0, row)    #Insert at the beginning of the list
            elif action == SELL:
                sell_row = row
                while(sell_row["amount"] != 0):
                    buy_row = buys_list[-1]
                    
                    #If last buy's amount is not enough to 100% consume the sell
                    if sell_row["amount"] > buy_row["amount"]:
                        usage_ratio = 1-((sell_row["amount"]-buy_row["amount"])/sell_row["amount"])
                        trans_cost = sell_row["trans_cost"]*usage_ratio + buy_row["trans_cost"]

                        if sell_row["year"] == irs_year:
                            createIRSEntry(irs_isin_list, len(irs_list) + line_offset, buy_row["amount"], trans_cost, buy_row, sell_row)

                        sell_row["trans_cost"] *= 1-usage_ratio
                        sell_row["amount"] -= buy_row["amount"]
                        buys_list.pop() #Remove last buy, since it has been 100% consumed
                    #If last buy's amount is is more than enough to 100% consume the sell
                    elif sell_row["amount"] < buy_row["amount"]:
                        usage_ratio = 1-((buy_row["amount"]-sell_row["amount"])/buy_row["amount"])
                        trans_cost = buy_row["trans_cost"]*usage_ratio + sell_row["trans_cost"]

                        if sell_row["year"] == irs_year:
                            createIRSEntry(irs_isin_list, len(irs_list) + line_offset, sell_row["amount"], trans_cost, buy_row, sell_row)

                        buy_row["trans_cost"] *= 1-usage_ratio
                        buy_row["amount"] -= sell_row["amount"]
                        sell_row["amount"] = 0 #Sell has been 100% consumed
                    #If last buy's amount is exactly enough to 100% consume the sell
                    else:
                        trans_cost = buy_row["trans_cost"] + sell_row["trans_cost"]
                        
                        if sell_row["year"] == irs_year:
                            createIRSEntry(irs_isin_list, len(irs_list) + line_offset, buy_row["amount"], trans_cost, buy_row, sell_row)

                        sell_row["amount"] = 0 #Sell has been 100% consumed
                        buys_list.pop() #Remove last buy, since it has been 100% consumed

        #Print product metrics
        irs_isin_df = pd.DataFrame.from_dict(irs_isin_list, orient='columns')
        ValorRealizacao = 0
        ValorAquisicao = 0
        commissions = 0
        for index, row in irs_isin_df.iterrows():
            ValorRealizacao += row["ValorRealizacao"]
            ValorAquisicao += row["ValorAquisicao"]
            commissions += row["DespesasEncargos"]
        print("%s | ValorRealizacao:%.2f, ValorAquisicao:%.2f, gains:%.2f, commissions:%.2f" % (isin_df.iloc[0]['ISIN'], ValorRealizacao, ValorAquisicao, ValorRealizacao-ValorAquisicao, commissions))

        #Append this product's irs_isin list into global irs list
        irs_list += irs_isin_list

    #Get overall gains
    irs_df = pd.DataFrame.from_dict(irs_list, orient='columns')
    irs_df = irs_df.round(2)            #Round every cell to 2 decimal places
    total_gains = 0
    total_valor_realizacao = 0
    total_valor_aquisicao = 0
    commissions = 0
    irs_df = irs_df.reset_index()  #Make sure indexes pair with number of rows
    for index, row in irs_df.iterrows():
        total_valor_realizacao += row["ValorRealizacao"]
        total_valor_aquisicao += row["ValorAquisicao"]
        commissions += row["DespesasEncargos"]
    total_valor_realizacao = round(total_valor_realizacao, 2)
    total_valor_aquisicao = round(total_valor_aquisicao, 2)
    commissions = round(commissions, 2)
    total_gains = total_valor_realizacao-total_valor_aquisicao

    print("\nTotal %d metrics-------------------------------------------------------------------------------------------------" % (irs_year))
    print("Total gains:%.2f, Total commissions:%.2f" % (total_gains, commissions))

    #Generate string with contents of irs table 
    irs_xml_str = irs_df.to_xml(index=False, root_name=IRS_TABLE_NAME, row_name=IRS_TABLE_NAME+"-Linha", xml_declaration=False)
    irs_xml_str = '\t\t\t'.join(irs_xml_str.splitlines(True))       #add 3 tabs to each line (except the first one)

    #Fill irs_file with computed table contents
    with open(irs_file, 'r') as file :
        irs_file_str = file.read()          #read irs file
    
    irs_file_str = irs_file_str.replace('<'+IRS_TABLE_NAME+'/>', irs_xml_str)   #Fill table contents

    irs_file_str = irs_file_str.replace('<'+IRS_TABLE_NAME+'SomaC01>0.00</'+IRS_TABLE_NAME+'SomaC01>', '<'+IRS_TABLE_NAME+'SomaC01>'+str(total_valor_realizacao)+'</'+IRS_TABLE_NAME+'SomaC01>')        #Fill soma controlo valor realizacao
    irs_file_str = irs_file_str.replace('<'+IRS_TABLE_NAME+'SomaC02>0.00</'+IRS_TABLE_NAME+'SomaC02>', '<'+IRS_TABLE_NAME+'SomaC02>'+str(total_valor_aquisicao)+'</'+IRS_TABLE_NAME+'SomaC02>')        #Fill soma controlo valor aquisicao
    irs_file_str = irs_file_str.replace('<'+IRS_TABLE_NAME+'SomaC03>0.00</'+IRS_TABLE_NAME+'SomaC03>', '<'+IRS_TABLE_NAME+'SomaC03>'+str(commissions)+'</'+IRS_TABLE_NAME+'SomaC03>')                       #Fill soma controlo respesas e encargos

    #Write output xml file
    os.makedirs(os.path.dirname(OUTPUT_FILE_DIR), exist_ok=True)  #Create file writing directory
    with open(OUTPUT_FILE_DIR, 'w') as file:
        file.write(irs_file_str)

    print("\nIRS preenchido gerado na diretoria %s" % (OUTPUT_FILE_DIR))


if __name__ == "__main__":
    main()