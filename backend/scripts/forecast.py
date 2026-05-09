"""
Standalone forecasting script called from Node.js via python-shell.
Reads JSON input from stdin, runs the requested model, returns JSON to stdout.

Input JSON:
{
  "model": 1|2|3,         # 1=ARIMA, 2=TBATS, 3=TFT
  "data_path": "path.xlsx",
  "product": "product name",
  "horizon": 21
}

Output JSON:
{
  "sales": [...],
  "timerange": [...]
}
"""

import sys
import os
import json
import warnings
import io
import pandas as pd
import numpy as np
from contextlib import contextmanager

warnings.filterwarnings("ignore")

# Unique marker so Node.js can find the JSON result among all the noise
RESULT_MARKER = "__FORECAST_RESULT__"


@contextmanager
def redirect_stdout_to_stderr():
    """Temporarily redirect stdout to stderr so PyTorch/Lightning logs
    don't pollute the JSON output channel."""
    old_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        yield
    finally:
        sys.stdout = old_stdout


def read_data(file_path: str) -> pd.DataFrame:
    data = pd.read_excel(file_path, sheet_name=None)
    data = pd.concat(data.values(), ignore_index=True)
    return data


def filtered_data(data: pd.DataFrame, product: str) -> pd.DataFrame:
    return data[data['unique_id'] == product]


def prepare_data(data: pd.DataFrame, product: str) -> pd.DataFrame:
    """Filter and resample data for forecasting."""
    fdata = filtered_data(data, product)
    fdata = fdata.set_index("ds").resample("D")["y"].sum().replace(0, None).ffill()
    X = pd.DataFrame()
    desc_df = pd.DataFrame([product] * fdata.shape[0], columns=["unique_id"])
    test_data = pd.concat([desc_df, fdata.reset_index()], axis=1)
    X = pd.concat([X, test_data], ignore_index=True)
    return X


def arima_forecast(X: pd.DataFrame, horizon: int):
    from statsforecast import StatsForecast
    from statsforecast.models import AutoARIMA

    models = [
        AutoARIMA(seasonal=False, alias="ARIMA"),
        AutoARIMA(season_length=14, alias="SARIMA")
    ]
    X_input = X[["unique_id", "ds", "y"]]
    sf = StatsForecast(models=models, freq='D')
    sf.fit(df=X_input)
    preds = sf.predict(h=horizon)
    return preds["ds"], preds["SARIMA"]


def tbats_forecast(X: pd.DataFrame, horizon: int):
    from statsforecast import StatsForecast
    from statsforecast.models import TSB, AutoTheta, AutoTBATS

    models = [
        TSB(0.01, 0.01),
        AutoTheta(season_length=14),
        AutoTBATS(season_length=2)
    ]
    X_input = X[["unique_id", "ds", "y"]]
    sf = StatsForecast(models=models, freq='D')
    sf.fit(df=X_input)
    preds = sf.predict(h=horizon)
    return preds["ds"], preds["TSB"]


def tft_forecast(X: pd.DataFrame, horizon: int):
    import lightning.pytorch as pl
    from pytorch_forecasting import TemporalFusionTransformer, TimeSeriesDataSet
    from pytorch_forecasting.data import GroupNormalizer
    from pytorch_forecasting.metrics import QuantileLoss
    from lightning.pytorch.callbacks import EarlyStopping
    import matplotlib
    matplotlib.use("Agg")

    pl.seed_everything(42)
    tft_data = X.copy()
    tft_data["y"] = tft_data["y"].astype(float)
    tft_data["time_idx"] = tft_data["ds"].dt.dayofyear + 365 + tft_data["ds"].dt.year * 365
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
        static_categoricals=["unique_id"],
        time_varying_known_reals=["time_idx", "relative_time_idx"],
        time_varying_known_categoricals=["day_of_week", "month"],
        time_varying_unknown_reals=X.columns.difference(
            ["unique_id", "ds", "time_idx", "month", "day_of_week"]
        ).to_list(),
        target_normalizer=GroupNormalizer(groups=["unique_id"], transformation="softplus"),
        add_relative_time_idx=True,
        add_target_scales=True,
        add_encoder_length=True,
    )

    validation = TimeSeriesDataSet.from_dataset(training, tft_data, predict=True, stop_randomization=True)

    batch_size = 128
    train_dataloader = training.to_dataloader(train=True, batch_size=batch_size, num_workers=0)
    val_dataloader = validation.to_dataloader(train=False, batch_size=batch_size * 10, num_workers=0)

    early_stop_callback = EarlyStopping(
        monitor="val_loss", min_delta=1e-4, patience=10, verbose=False, mode="min"
    )

    trainer = pl.Trainer(
        max_epochs=50,
        accelerator="cpu",
        enable_model_summary=True,
        gradient_clip_val=0.1,
        limit_train_batches=50,
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
        log_interval=10,
        optimizer="ranger",
        reduce_on_plateau_patience=4,
    )

    trainer.fit(tft, train_dataloaders=train_dataloader, val_dataloaders=val_dataloader)

    best_model_path = trainer.checkpoint_callback.best_model_path
    best_tft = TemporalFusionTransformer.load_from_checkpoint(best_model_path)

    predictions = best_tft.predict(
        val_dataloader, return_y=True, trainer_kwargs=dict(accelerator="cpu")
    )

    dat_range = pd.date_range(
        start=tft_data[lambda x: x.time_idx > training_cutoff]["ds"].min(),
        periods=max_prediction_length,
        freq="D"
    )

    return dat_range, predictions.output[0]


FORECAST_MODELS = {
    1: arima_forecast,
    2: tbats_forecast,
    3: tft_forecast,
}


def main():
    # Read JSON input from stdin
    input_data = json.loads(sys.stdin.read())

    model_id = input_data["model"]
    data_path = input_data["data_path"]
    product = input_data["product"]
    horizon = input_data.get("horizon", 21)

    # All heavy lifting runs with stdout→stderr so PyTorch/Lightning
    # log noise doesn't mix with our JSON output.
    with redirect_stdout_to_stderr():
        # Read and prepare data
        raw_data = read_data(data_path)

        # The data should already be preprocessed (columns renamed) —
        # column mapping JSON is passed alongside the data path
        column_map = input_data.get("column_map")
        if column_map:
            raw_data = raw_data[raw_data[column_map["y"]] > 0]
            raw_data[column_map["unique_id"]] = raw_data[column_map["unique_id"]].apply(
                lambda x: str(x).strip() if isinstance(x, str) else str(x)
            )
            dropped = column_map.get("dropped_columns", [])
            raw_data.drop(columns=[c for c in dropped if c in raw_data.columns], inplace=True)
            raw_data.reset_index(drop=True, inplace=True)
            raw_data.rename(columns={
                column_map["unique_id"]: "unique_id",
                column_map["ds"]: "ds",
                column_map["y"]: "y",
            }, inplace=True)

        # Prepare and forecast
        X = prepare_data(raw_data, product)
        forecast_fn = FORECAST_MODELS[model_id]
        timerange, sales = forecast_fn(X, horizon=horizon)

        # Convert to JSON-serializable
        timerange_list = pd.Series(timerange).astype(str).tolist()

        if hasattr(sales, 'numpy'):
            # PyTorch tensor
            sales_list = sales.numpy().flatten().tolist()
        elif hasattr(sales, 'tolist'):
            sales_list = sales.tolist()
        else:
            sales_list = list(sales)

    # Print the result with a marker — stdout is restored here
    result = {
        "sales": sales_list,
        "timerange": timerange_list,
    }
    print(RESULT_MARKER + json.dumps(result))


if __name__ == "__main__":
    main()
