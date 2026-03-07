import pandas as pd
from statsforecast import StatsForecast
from statsforecast.models import Naive, AutoARIMA, HistoricAverage, WindowAverage, SeasonalNaive, TSB, AutoTheta, AutoTBATS
# from utilsforecast.evaluation import evaluate
# from utilsforecast.losses import mae
import lightning.pytorch as pl
import torch
from pytorch_forecasting import Baseline, TemporalFusionTransformer, TimeSeriesDataSet
from pytorch_forecasting.data import GroupNormalizer
from pytorch_forecasting.metrics import MAE, QuantileLoss
from lightning.pytorch.callbacks import EarlyStopping
import warnings
import matplotlib
matplotlib.use("Agg")

warnings.filterwarnings("ignore")

def read_data(fileName: str) -> pd.DataFrame:
    data = pd.read_excel(fileName, sheet_name=None, dtype={"Description": str})
    data = pd.concat(data.values(), ignore_index=True)
    return data

def pre_process_data(data: pd.DataFrame) -> pd.DataFrame:
    # Handle missing values
    data = data[data['Quantity'] > 0]
    data["Description"] = data["Description"].apply(lambda x: x.strip() if isinstance(x, str) else x)
    data.drop(columns=["Invoice", "StockCode", "Price", "Customer ID", "Country"], inplace=True)
    data = data[["Description", "InvoiceDate", "Quantity"]].reset_index(drop=True)
    data.rename(columns={"Description": "unique_id", "InvoiceDate": "ds", "Quantity": "y"}, inplace=True)
    return data

def filtered_data(data: pd.DataFrame, product: str) -> pd.DataFrame:
    filtered_data = data[data['unique_id'] == product]
    return filtered_data

def forecast(X: pd.DataFrame, horizon: int) -> pd.DataFrame:
    models = [
        Naive(),
        HistoricAverage(),
        WindowAverage(window_size=horizon),
        SeasonalNaive(season_length=horizon)
    ]

    sf= StatsForecast(models=models, freq='D')
    sf.fit(df=X)
    preds = sf.predict(h=horizon)

    return preds["ds"], preds["SeasonalNaive"]

def tbats_forecast(X: pd.DataFrame, horizon: int) -> pd.DataFrame:
    models = [
        TSB(0.01, 0.01),
        AutoTheta(season_length=14),
        AutoTBATS(season_length=2)
    ]

    sf= StatsForecast(models=models, freq='D')
    sf.fit(df=X)
    preds = sf.predict(h=horizon)

    return preds["ds"], preds["TSB"]

def arima_forecast(X: pd.DataFrame, horizon: int) -> pd.DataFrame:
    models = [
        AutoARIMA(seasonal=False, alias="ARIMA"),
        AutoARIMA(season_length=14, alias="SARIMA")
    ]

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
        group_ids=["unique_id"],
        min_encoder_length=max_encoder_length // 2,
        max_encoder_length=max_encoder_length,
        min_prediction_length=1,
        max_prediction_length=max_prediction_length,
        # Static features help the model distinguish between IDs
        static_categoricals=["unique_id"], 
        # Known future variables (add calendar features here)
        time_varying_known_reals=["time_idx", "relative_time_idx"],
        time_varying_known_categoricals=["day_of_week", "month"], 
        time_varying_unknown_reals=["y"],
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