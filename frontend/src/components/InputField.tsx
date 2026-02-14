import React from 'react';
import "./styles.css"
import InputFile from './InputFile';

interface Props {
    product: string;
    setProduct: React.Dispatch<React.SetStateAction<string>>;
    handleFileProcess: (e: React.FormEvent) => void;
}

function InputField({ product, setProduct, handleFileProcess }: Props) {
    return <form className="input-form" onSubmit={(e) => handleFileProcess(e)}>
        <input type="text" placeholder="Enter product name" className="input-field" value={product} onChange={(e) => setProduct(e.target.value)}/>
    </form>
}

export default InputField;