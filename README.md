# Product Demand Forecasting

A demand forecasting application for retail products using historical sales data.

Some key features include:

- A FastAPI backend for data upload, preprocessing, and forecasting
- An intuitive and simple frontend for uploading files, selecting products, and visualizing forecasts
- GenAI integration to dynamically adjust and adapt each model with the dataset
- Multiple forecasting models (SARIMA, TBATS, and Temporal Fusion Transformer)
- Chart visualization of forecasts
- Jupyter notebooks for experimentation and model development

## How It Works

1. Upload a retail Excel file from the frontend.
2. Backend reads all sheets, concatenates data, and preprocesses columns into:
	 - unique_id: product description
	 - ds: datetime index
	 - y: quantity sold
     - Other relevant exogenous features (Only supported on Temporal Fusion Transformer model)
3. User enters product name and selects forecasting model.
4. Backend filters product history, resamples to daily frequency, and forecasts 21 days ahead.
5. Frontend displays predicted demand as an interactive chart.

## Local Setup

### 1. Clone Repository

```bash
git clone https://github.com/adityajs12321/Product-Demand-Forecasting.git Product-Demand-Forecasting
cd Product-Demand-Forecasting
```

### 2. Backend Setup

Create and activate a Python virtual environment, then install dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Start the backend server:

```bash
cd backend
uvicorn server:app --reload
```

Backend runs on http://localhost:8000

### 3. Frontend Setup

In a separate terminal:

```bash
cd frontend
npm install
npm start
```

Frontend runs on http://localhost:3000

## API Endpoints

### POST /upload

Uploads Excel file for preprocessing.

Form-data:

- file: .xlsx file

Response example:

```json
{
	"message": "Data processed successfully",
	"rows": 12345
}
```

### POST /process

Runs selected model forecast.

Request body:

```json
{
	"product": "WHITE HANGING HEART T-LIGHT HOLDER",
	"forecast_model": 1
}
```

Model mapping:

- 1 = ARIMA
- 2 = TBATS
- 3 = TFT

Response example:

```json
{
	"sales": [10.4, 11.2, 13.1],
	"timerange": ["2026-04-01", "2026-04-02", "2026-04-03"]
}
```

## License

MIT Licence