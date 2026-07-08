"""
Consolidates downloaded pharmacy spreadsheets into a single normalized Excel workbook.
"""

from pathlib import Path

import pandas as pd


def consolidar_planilhas(pasta_input, arquivo_output="consolidado_farmacias.xlsx"):
    """
    Consolidates all .xlsx tables from a folder into a single file,
    adding the 'Município' column from the file name and a fixed 'UF' value of 'MG'.
    """
    caminho_pasta = Path(pasta_input)

    # List used to store each file's DataFrame.
    lista_dataframes = []

    # Find all .xlsx files in the folder.
    arquivos_xlsx = list(caminho_pasta.glob("*.xlsx"))

    if not arquivos_xlsx:
        print(f"No .xlsx files found in folder: {caminho_pasta.absolute()}")
        return

    print(f"Found {len(arquivos_xlsx)} files to process.")

    for arquivo in arquivos_xlsx:
        # Skip the output file if it already exists in the same folder.
        if arquivo.name == arquivo_output:
            continue

        try:
            # Read the Excel spreadsheet.
            df = pd.read_excel(arquivo)

            # Check that the spreadsheet is not empty.
            if df.empty:
                print(f"Warning: file '{arquivo.name}' is empty and will be skipped.")
                continue

            # Extract the city name by removing the .xlsx extension.
            municipio = arquivo.stem

            # Add the new columns.
            df["Município"] = municipio
            df["UF"] = "MG"

            # Ensure the main columns exist and keep them in a consistent order.
            colunas_obrigatorias = ["CNPJ", "Farmácia", "Endereço", "Bairro", "Município", "UF"]
            for col in colunas_obrigatorias:
                if col not in df.columns:
                    df[col] = None  # Create an empty column if the original does not exist.

            # Keep only the relevant columns in the right order.
            df = df[colunas_obrigatorias]

            lista_dataframes.append(df)
            print(f"Processed successfully: {arquivo.name} -> City: {municipio}")

        except Exception as error:
            print(f"Error while processing file {arquivo.name}: {error}")

    if lista_dataframes:
        # Concatenate all DataFrames in the list.
        df_consolidado = pd.concat(lista_dataframes, ignore_index=True)

        # Save the final result to a new Excel file.
        caminho_saida = caminho_pasta / arquivo_output
        df_consolidado.to_excel(caminho_saida, index=False)
        print(f"\nSuccess! Consolidated file saved at: {caminho_saida.absolute()}")
    else:
        print("\nNo valid data was extracted for consolidation.")


if __name__ == "__main__":
    # "." means the script will look for spreadsheets in the folder where it is saved.
    PASTA_DAS_PLANILHAS = "./downloads_farmacias"
    ARQUIVO_FINAL = "consolidado_farmacias.xlsx"

    consolidar_planilhas(PASTA_DAS_PLANILHAS, ARQUIVO_FINAL)
