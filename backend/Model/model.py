import pandas as pd

def read_data(fileName: str) -> pd.DataFrame:
    data = pd.read_excel(fileName, sheet_name=None)
    data = pd.concat(data.values(), ignore_index=True)
    return data

def pre_process_data(data: pd.DataFrame) -> pd.DataFrame:
    # Handle missing values
    data = data[data['Quantity'] > 0]
    data.Description = data.Description.apply(lambda x: x.strip() if isinstance(x, str) else x)
    data.drop(columns=["Invoice", "StockCode", "Price", "Customer ID", "Country"], inplace=True)
    data = data[["Description", "InvoiceDate", "Quantity"]].reset_index(drop=True)
    # data.rename(columns={"Description": "unique_id", "InvoiceDate": "ds", "Quantity": "y"}, inplace=True)
    return data

def filtered_data(data: pd.DataFrame, product: str) -> pd.DataFrame:
    filtered_data = data[data['Description'] == product]
    return filtered_data