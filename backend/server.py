from itertools import product
from fastapi import FastAPI, UploadFile, File
import sys
import os

from pydantic import BaseModel
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from Model import model
import tempfile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

data = None

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

class ProductRequest(BaseModel):
    product: str

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
        processed_data = model.pre_process_data(data)
        return {"message": "Data processed successfully", "rows": len(processed_data)}
    finally:
        print("Cleaning up temporary file...")

@app.post("/process")
def filter_data(request: ProductRequest):
    global data
    if data is None:
        return {"message": "No data to process"}
    
    processed_data = model.filtered_data(data, request.product)
    return {"message": "Data pre-processed successfully", "rows": len(processed_data)}