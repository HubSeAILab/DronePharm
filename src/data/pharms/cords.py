"""
Geocodes consolidated pharmacy spreadsheets and writes latitude/longitude columns to a new Excel file.
"""

import time

import pandas as pd
from geopy.geocoders import Nominatim


def geocodificar_farmacias(arquivo_entrada, arquivo_saida):
    """Geocode each pharmacy address from an Excel workbook and save coordinates."""
    print(f"Reading file: {arquivo_entrada}")

    try:
        # Read the file while keeping CNPJ values as text.
        df = pd.read_excel(arquivo_entrada, dtype={"CNPJ": str})
    except FileNotFoundError:
        print(f"Error: file '{arquivo_entrada}' was not found.")
        return

    # Create a full-address column to improve lookup accuracy.
    # Ideal format: "Street X, District, City - State, Brazil".
    df["Endereco_Busca"] = (
        df["Endereço"].astype(str)
        + ", "
        + df["Bairro"].astype(str)
        + ", "
        + df["Município"].astype(str)
        + " - "
        + df["UF"].astype(str)
        + ", Brasil"
    )

    # Initialize the OpenStreetMap geocoder (Nominatim).
    # The API requires a descriptive user_agent for the application making requests.
    geolocator = Nominatim(user_agent="drone_routing_logistics_app")

    latitudes = []
    longitudes = []

    total = len(df)
    print(f"Starting geocoding for {total} addresses. This may take a few minutes...\n")

    for index, row in df.iterrows():
        endereco = row["Endereco_Busca"]
        print(f"[{index + 1}/{total}] Searching: {endereco}")

        try:
            # Nominatim rule of thumb: no more than 1 request per second.
            # The time.sleep(1.2) call helps prevent temporary IP bans.
            time.sleep(1.2)

            # Run the lookup with a reasonable timeout to avoid hanging.
            location = geolocator.geocode(endereco, timeout=10)

            if location:
                latitudes.append(location.latitude)
                longitudes.append(location.longitude)
                print(f"    -> Found: {location.latitude}, {location.longitude}")
            else:
                latitudes.append(None)
                longitudes.append(None)
                print("    -> Coordinates not found. The address may be incomplete.")

        except Exception as error:
            print(f"    -> Request error (timeout or network failure): {error}")
            latitudes.append(None)
            longitudes.append(None)

    # Add the new spatial columns to the original DataFrame.
    df["Latitude"] = latitudes
    df["Longitude"] = longitudes

    # Remove the temporary lookup column to keep the output table clean.
    df = df.drop(columns=["Endereco_Busca"])

    # Save the result as an Excel file.
    with pd.ExcelWriter(arquivo_saida, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    print(f"\nFinished successfully! Spreadsheet generated: {arquivo_saida}")


if __name__ == "__main__":
    # Name of the spreadsheet generated in the previous step.
    ARQUIVO_INPUT = "consolidado_farmacias.xlsx"

    # Name of the new spreadsheet that will contain coordinates.
    ARQUIVO_OUTPUT = "farmacias_com_coordenadas.xlsx"

    geocodificar_farmacias(ARQUIVO_INPUT, ARQUIVO_OUTPUT)
