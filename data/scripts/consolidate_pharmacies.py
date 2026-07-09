"""
Consolidates downloaded pharmacy spreadsheets into a single normalized Excel workbook.
"""

from pathlib import Path

import pandas as pd


def consolidar_planilhas(pasta_input, arquivo_output="consolidated_pharmacies.xlsx"):
    """
    Consolidates all .xlsx tables from a folder into a single file,
    adding the 'MunicÃ­pio' column from the file name and a fixed 'UF' value of 'MG'.
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
            df["MunicÃ­pio"] = municipio
            df["UF"] = "MG"

            # Ensure the main columns exist and keep them in a consistent order.
            colunas_obrigatorias = ["CNPJ", "FarmÃ¡cia", "EndereÃ§o", "Bairro", "MunicÃ­pio", "UF"]
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
        caminho_output = caminho_pasta / arquivo_output
        df_consolidado.to_excel(caminho_output, index=False)
        print(f"\nSuccess! Consolidated file saved at: {caminho_output.absolute()}")
    else:
        print("\nNo valid data was extracted for consolidation.")


if __name__ == "__main__":
    # "." means the script will look for spreadsheets in the folder where it is saved.
    PASTA_DAS_PLANILHAS = "./pharmacy_downloads"
    ARQUIVO_FINAL = "consolidated_pharmacies.xlsx"

    consolidar_planilhas(PASTA_DAS_PLANILHAS, ARQUIVO_FINAL)
