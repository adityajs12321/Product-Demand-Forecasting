import React, { useRef } from 'react';
import "./styles.css"

interface Props {
    file: File | null;
    setFile: (file: File | null) => void;
    handleFileUpload: (file: File) => Promise<void>;
    uploading: boolean;
}

function InputFile({ file, setFile, handleFileUpload, uploading }: Props) {
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const selectedFile = e.target.files?.[0];
        if (selectedFile) {
            // Validate file type
            const allowedTypes = ['.csv', '.xlsx', '.xls'];
            const fileExtension = selectedFile.name.toLowerCase().substring(selectedFile.name.lastIndexOf('.'));
            
            if (!allowedTypes.includes(fileExtension)) {
                alert('Please select a CSV or Excel file (.csv, .xlsx, .xls)');
                return;
            }
            
            // Validate file size (max 10MB)
            if (selectedFile.size > 10 * 1024 * 1024) {
                alert('File size must be less than 10MB');
                return;
            }
            
            await handleFileUpload(selectedFile);
        }
    };

    const handleDragOver = (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
    };

    const handleDrop = async (e: React.DragEvent) => {
        e.preventDefault();
        e.stopPropagation();
        
        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile) {
            if (fileInputRef.current) {
                // Create a new FileList with the dropped file
                const dataTransfer = new DataTransfer();
                dataTransfer.items.add(droppedFile);
                fileInputRef.current.files = dataTransfer.files;
            }
            await handleFileUpload(droppedFile);
        }
    };

    return (
        <div className="file-upload-container">
            <div 
                className={`drop-zone ${uploading ? 'uploading' : ''}`}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
            >
                <div className="drop-zone-content">
                    {uploading ? (
                        <>
                            <div className="spinner"></div>
                            <p>Uploading...</p>
                        </>
                    ) : (
                        <>
                            <div className="upload-icon">📁</div>
                            <p className="drop-text">
                                <strong>Click to browse</strong> or drag and drop your file here
                            </p>
                            <p className="file-types">Supported: CSV, Excel (.csv, .xlsx, .xls) • Max 10MB</p>
                        </>
                    )}
                </div>
                <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFileChange}
                    disabled={uploading}
                    style={{ display: 'none' }}
                />
            </div>
        </div>
    );
}

export default InputFile;