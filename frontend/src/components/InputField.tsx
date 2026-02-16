import React from 'react';
import "./styles.css"

interface Props {
    product: string;
    setProduct: React.Dispatch<React.SetStateAction<string>>;
    handleFileProcess: (e: React.FormEvent) => void;
    processing: boolean;
}

function InputField({ product, setProduct, handleFileProcess, processing }: Props) {
    return (
        <form className="prediction-form" onSubmit={handleFileProcess}>
            <div className="form-group">
                <label htmlFor="product-input" className="form-label">
                    Product Name
                </label>
                <input 
                    id="product-input"
                    type="text" 
                    placeholder="Enter the product name to predict demand for" 
                    className="input-field" 
                    value={product} 
                    onChange={(e) => setProduct(e.target.value)}
                    disabled={processing}
                    required
                />
            </div>
            <button 
                type="submit" 
                className={`predict-button ${processing ? 'processing' : ''}`}
                disabled={processing || !product.trim()}
            >
                {processing ? (
                    <>
                        <div className="button-spinner"></div>
                        Processing...
                    </>
                ) : (
                    <>
                        🔮 Predict Demand
                    </>
                )}
            </button>
        </form>
    );
}

export default InputField;