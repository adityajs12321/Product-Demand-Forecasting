import ollama
from pydantic import BaseModel
import lightning.pytorch as pl
from pytorch_forecasting import Baseline, TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.data import GroupNormalizer
from pytorch_forecasting.metrics import MAE, QuantileLoss
from lightning.pytorch.callbacks import EarlyStopping
import warnings
import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import Naive, AutoARIMA, HistoricAverage, WindowAverage, SeasonalNaive, TSB, AutoTheta, AutoTBATS
from typing import List
import matplotlib
matplotlib.use("Agg")

warnings.filterwarnings("ignore")

class Response(BaseModel):
    unique_id: str
    ds: str
    y: str
    dropped_columns: List[str]

def read_data(fileName: str) -> pd.DataFrame:
    data = pd.read_excel(fileName, sheet_name=None)
    data = pd.concat(data.values(), ignore_index=True)
    return data

def pre_process_data(data: pd.DataFrame) -> pd.DataFrame | Response:
    # Handle missing values
    SYSTEM_PROMPT = "You are a helpful assistant that reads columns of a dataframe and returns the column that corresponds to unique_id, ds and y. The column names may not be exactly unique_id, ds and y but they will be similar. For example, unique_id may be called Description, ds may be called date or time-index and y may be called Quantity, number of items sold. You must also return a list of columns that must be dropped from the dataframe because they were not relevant for forecasting. Ex: Invoice, UserID, Region. DO NOT DROP COLUMNS THAT CAN BE USED AS EXOGENOUS FEATURES, Ex: Price, Calendar Events, etc."
    response = ollama.chat(
        model="gemma3:4b",
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": f"Here are the columns of the dataframe: {data.columns.to_list()}"}],
        format=Response.model_json_schema(),
        think=False
    ).message
    response = Response.model_validate_json(response.content)
    data = data[data[response.y] > 0]
    data[response.unique_id] = data[response.unique_id].apply(lambda x: str(x))
    data[response.unique_id] = data[response.unique_id].apply(lambda x: x.strip() if isinstance(x, str) else x)
    data.drop(columns=response.dropped_columns, inplace=True)
    data = data.reset_index(drop=True)
    data.rename(columns={response.unique_id: "unique_id", response.ds: "ds", response.y: "y"}, inplace=True)
    return data, response

def filtered_data(data: pd.DataFrame, product: str) -> pd.DataFrame:
    filtered_data = data[data['unique_id'] == product]
    return filtered_data

def tbats_forecast(X: pd.DataFrame, horizon: int) -> pd.DataFrame:
    models = [
        TSB(0.01, 0.01),
        AutoTheta(season_length=14),
        AutoTBATS(season_length=2)
    ]

    X = X[["unique_id", "ds", "y"]]

    sf= StatsForecast(models=models, freq='D')
    sf.fit(df=X)
    preds = sf.predict(h=horizon)

    return preds["ds"], preds["TSB"]

def arima_forecast(X: pd.DataFrame, horizon: int) -> pd.DataFrame:
    models = [
        AutoARIMA(seasonal=False, alias="ARIMA"),
        AutoARIMA(season_length=14, alias="SARIMA")
    ]

    X = X[["unique_id", "ds", "y"]]

    sf= StatsForecast(models=models, freq='D')
    sf.fit(df=X)
    preds = sf.predict(h=horizon)

    return preds["ds"], preds["SARIMA"]

def tft_forecast(X: pd.DataFrame, horizon: int) -> pd.DataFrame:
    pl.seed_everything(42)
    tft_data = X.copy()
    tft_data["y"] = tft_data["y"].astype(float)
    tft_data["time_idx"] = tft_data["ds"].dt.dayofyear + 365 + tft_data["ds"].dt.year*365
    tft_data["time_idx"] -= tft_data["time_idx"].min()
    tft_data["month"] = tft_data.ds.dt.month.astype(str).astype("category")
    tft_data["day_of_week"] = tft_data.ds.dt.dayofweek.astype(str).astype("category")

    max_prediction_length = horizon
    max_encoder_length = 90

    training_cutoff = tft_data["time_idx"].max() - max_prediction_length

    training = TimeSeriesDataSet(
        tft_data[lambda x: x.time_idx <= training_cutoff],
        time_idx="time_idx",
        target="y",
        group_ids=X.columns.difference(["ds", "y", "time_idx", "month", "day_of_week"]).to_list(),
        min_encoder_length=max_encoder_length // 2,
        max_encoder_length=max_encoder_length,
        min_prediction_length=1,
        max_prediction_length=max_prediction_length,
        # Static features help the model distinguish between IDs
        static_categoricals=["unique_id"], 
        # Known future variables (add calendar features here)
        time_varying_known_reals=["time_idx", "relative_time_idx"],
        time_varying_known_categoricals=["day_of_week", "month"], 
        time_varying_unknown_reals=X.columns.difference(["unique_id", "ds", "time_idx", "month", "day_of_week"]).to_list(),
        # CRITICAL: Re-enable this to handle different scales
        target_normalizer=GroupNormalizer(
            groups=["unique_id"], transformation="softplus"
        ),
        add_relative_time_idx=True,
        add_target_scales=True,
        add_encoder_length=True,
    )

    # create validation set (predict=True) which means to predict the last max_prediction_length points in time
    # for each series
    validation = TimeSeriesDataSet.from_dataset(
        training, tft_data, predict=True, stop_randomization=True
    )

    # create dataloaders for model
    batch_size = 128  # set this between 32 to 128
    train_dataloader = training.to_dataloader(
        train=True, batch_size=batch_size, num_workers=0
    )
    val_dataloader = validation.to_dataloader(
        train=False, batch_size=batch_size * 10, num_workers=0
    )

    early_stop_callback = EarlyStopping(
        monitor="val_loss", min_delta=1e-4, patience=10, verbose=False, mode="min"
    )

    trainer = pl.Trainer(
        max_epochs=50,
        accelerator="cpu",
        enable_model_summary=True,
        gradient_clip_val=0.1,
        limit_train_batches=50,  # comment in for training, running validation every 30 batches
        # fast_dev_run=True,  # comment in to check that networkor dataset has no serious bugs
        callbacks=[early_stop_callback],
    )

    tft = TemporalFusionTransformer.from_dataset(
        training,
        learning_rate=0.05,
        hidden_size=16,
        attention_head_size=2,
        dropout=0.1,
        hidden_continuous_size=8,
        loss=QuantileLoss(),
        log_interval=10,  # uncomment for learning rate finder and otherwise, e.g. to 10 for logging every 10 batches
        optimizer="ranger",
        reduce_on_plateau_patience=4,
    )

    trainer.fit(
        tft,
        train_dataloaders=train_dataloader,
        val_dataloaders=val_dataloader,
    )

    best_model_path = trainer.checkpoint_callback.best_model_path
    best_tft = TemporalFusionTransformer.load_from_checkpoint(best_model_path)

    predictions = best_tft.predict(
        val_dataloader, return_y=True, trainer_kwargs=dict(accelerator="cpu")
    )

    dat_range = pd.date_range(start=tft_data[lambda x: x.time_idx > training_cutoff]["ds"].min(), periods=max_prediction_length, freq="D")

    return dat_range, predictions.output[0]

def main():
    data = read_data('/Users/adityajs/Product Demand Forecasting/online_retail_III.xlsx')
    data, response = pre_process_data(data)
    print(data)

if __name__ == "__main__":
    main()