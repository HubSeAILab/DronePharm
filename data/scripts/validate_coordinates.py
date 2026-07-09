"""
Validates existing pharmacy coordinates by querying OpenStreetMap and comparing the returned coordinates with the spreadsheet values.
"""

import time

import pandas as pd
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim


# 1. Load the Excel file.
# Replace this with the correct file name.
df = pd.read_excel("data_with_coordinates.xlsx")

# 2. Initialize the OpenStreetMap geocoder.
# The user_agent parameter is required and identifies this application.
geolocator = Nominatim(user_agent="conferencia_farmacias_app")

# Add a rate limiter with a 1-second interval to respect OSM server limits.
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.0)

# Create columns to store the validation results.
df["OSM_Latitude"] = None
df["OSM_Longitude"] = None
df["Diferenca_Lat"] = None
df["Diferenca_Lon"] = None

# 3. Iterate over the spreadsheet rows and validate each pharmacy.
print("Starting OpenStreetMap validation...")
for index, row in df.iterrows():
    endereco_completo = row["EnderecoCompleto"]  # Uses the full address column.

    try:
        # Look up the address in OpenStreetMap.
        location = geocode(endereco_completo)

        if location:
            # Save the coordinates returned by the service.
            df.at[index, "OSM_Latitude"] = location.latitude
            df.at[index, "OSM_Longitude"] = location.longitude

            # Calculate the difference from the original coordinates.
            # Assumes the original columns are named 'Latitude' and 'Longitude'.
            df.at[index, "Diferenca_Lat"] = abs(row["Latitude"] - location.latitude)
            df.at[index, "Diferenca_Lon"] = abs(row["Longitude"] - location.longitude)
        else:
            print(f"Address not found: {endereco_completo}")

    except Exception as error:
        print(f"Error while querying row {index}: {error}")
        time.sleep(2)  # Extra pause after a connection failure.

# 4. Save the result with the new validation columns.
df.to_excel("validation_result.xlsx", index=False)
print("Validation complete! File 'validation_result.xlsx' saved successfully.")
