import React, { useState } from 'react';
import "./styles.css"

interface Props {
    product: string;
    setProduct: React.Dispatch<React.SetStateAction<string>>;
    forecastModel: number;
    setForecastModel: React.Dispatch<React.SetStateAction<number>>;
    handleFileProcess: (e: React.FormEvent, _product:string) => void;
    processing: boolean;
}

function InputField({ product, setProduct, forecastModel, setForecastModel, handleFileProcess, processing }: Props) {

    const [temp, setTemp] = useState("");
    return (
        <form className="prediction-form" onSubmit={(e) => handleFileProcess(e, temp)}>
            <div className="form-group">
                <input 
                    id="product-input"
                    type="text" 
                    placeholder="Enter the product name to predict demand for" 
                    className="input-field"
                    value={temp}
                    onChange={(e) => setTemp(e.target.value)}
                    disabled={processing}
                    required
                />
            </div>
            <div className="form-group">
                <p className="form-label">Select Forecast Model:</p>
                <select
                    id="model-select"
                    className="input-field"
                    value={forecastModel}
                    onChange={(e) => setForecastModel(Number(e.target.value))}
                    disabled={processing}
                >
                    <option value={1}>ARIMA</option>
                    <option value={2}>TBATS</option>
                    <option value={3}>TFT</option>
                </select>
            </div>
            <button 
                type="submit" 
                className={`predict-button ${processing ? 'processing' : ''}`}
                disabled={processing || !temp.trim()}
            >
                {processing ? (
                    <>
                        <div className="button-spinner"></div>
                        Processing...
                    </>
                ) : (
                    <>
                        Predict Demand
                    </>
                )}
            </button>
        </form>
    );
}

export default InputField;