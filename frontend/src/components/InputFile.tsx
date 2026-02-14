import React from 'react';
import "./styles.css"

interface Props {
    file: File | null;
    setFile: (file: File | null) => void;
    handleFileUpload: (file: any) => Promise<void>;
}

function InputFile({ file, setFile, handleFileUpload }: Props) {
    // return <form className="input-form">
    //     <input type="text" placeholder="Enter product name" className="input-field" />
    // </form>

    // File upload field

    return <form className="input-form">
        <input type="file" className="input-field" onChange={(e) => handleFileUpload(e.target.files ? e.target.files[0] : null)} />
    </form>
}

export default InputFile;