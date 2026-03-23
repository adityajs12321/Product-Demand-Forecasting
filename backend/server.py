from itertools import product
from fastapi import FastAPI, UploadFile, File
import sys
import os
import pandas as pd

from pydantic import BaseModel
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from Model import model_v2 as model
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

data, processed_data = None, None

forecast_models = {
    1: model.arima_forecast,
    2: model.tbats_forecast,
    3: model.tft_forecast
}

origins = [
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from enum import IntEnum

class ForecastModel(IntEnum):
    arima = 1
    tbats = 2
    tft = 3

class ProductRequest(BaseModel):
    product: str
    forecast_model: ForecastModel

@app.get("/")
def read_root():
    return "Hello"

@app.post("/upload")
def input_data(file: UploadFile = File(...)):
    # Create a temporary file to save the uploaded content
    with open("tempfile.xlsx", "wb") as temp_file:
        # Read the uploaded file content and write to temporary file
        content = file.file.read()
        temp_file.write(content)
    
    try:
        # Pass the temporary file path to read_data
        global data
        data = model.read_data("tempfile.xlsx")
        data, response = model.pre_process_data(data)  # Store processed data back to global variable
        return {"message": "Data processed successfully", "rows": len(data)}
    finally:
        print("Cleaning up temporary file...")

@app.post("/process")
def filter_data(request: ProductRequest):
    global data
    if data is None:
        return {"message": "No data to process"}
    
    global processed_data
    processed_data = model.filtered_data(data, request.product)
    # sales = processed_data[processed_data["unique_id"] == request.product]["y"]
    # timerange = processed_data[processed_data["unique_id"] == request.product]["ds"]

    processed_data = processed_data.set_index("ds").resample("D")["y"].sum().replace(0, None).ffill()
    X = pd.DataFrame()
    desc_df = pd.DataFrame([request.product]*processed_data.shape[0], columns=["unique_id"])
    test_data = pd.concat([desc_df, processed_data.reset_index()], axis=1)
    X = pd.concat([X, test_data], ignore_index=True)

    # sales = X["y"]
    # timerange = X["ds"]
    processed_data = X

    timerange, sales = forecast_models[request.forecast_model](X, horizon=21)

    return {"sales": sales.tolist(), "timerange": timerange.astype(str).tolist()}

@app.post("/tftpredict")
def tftpredict(request: ProductRequest):
    global data
    if data is None:
        return {"message": "No data to process"}
    
    global processed_data
    processed_data = model.filtered_data(data, request.product)
    # sales = processed_data[processed_data["unique_id"] == request.product]["y"]
    # timerange = processed_data[processed_data["unique_id"] == request.product]["ds"]

    processed_data = processed_data.set_index("ds").resample("D")["y"].sum().replace(0, None).ffill()
    X = pd.DataFrame()
    desc_df = pd.DataFrame([request.product]*processed_data.shape[0], columns=["unique_id"])
    test_data = pd.concat([desc_df, processed_data.reset_index()], axis=1)
    X = pd.concat([X, test_data], ignore_index=True)

    # sales = X["y"]
    # timerange = X["ds"]
    processed_data = X

    timerange, sales = model.tft_forecast(X, horizon=21)

    return {"sales": sales.tolist(), "timerange": timerange.astype(str).tolist()}


# @app.post("/predict")
# def predict():
#     global processed_data
#     if processed_data is None:
#         return {"message": "No data to predict"}
    
#     # Here you would call your prediction function and return the results
#     # For example:
#     # predictions = model.predict(processed_data)
#     # return {"predictions": predictions.tolist()}
    
#     return {"message": "Prediction endpoint not implemented yet"}