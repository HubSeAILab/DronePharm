"""
Prints the exact column names from the generated coordinate spreadsheet so other scripts can reference them safely.
"""

import pandas as pd


df = pd.read_excel("data_with_coordinates.xlsx")
print("Exact column names in your spreadsheet:")
print(list(df.columns))
