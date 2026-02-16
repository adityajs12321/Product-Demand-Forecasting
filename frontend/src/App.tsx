import React, {useState} from 'react';
import './App.css';
import InputFile from './components/InputFile';
import api from './api';
import InputField from './components/InputField';

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [uploaded, setUploaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [product, setProduct] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  // function to handle file upload to the backend (fastapi with UploadFile class) and axios
  async function handleFileUpload(file: File) {
    if (!file) return;
    
    setUploading(true);
    setError(null);
    
    try {
      // Create FormData to properly send file to FastAPI UploadFile
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await api.post('/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      
      console.log('Upload successful:', response.data);
      setUploaded(true);
      setFile(file);
      setSuccess('File uploaded successfully!');
      return response.data;
    }
    catch (error) {
      console.error('Upload failed:', error);
      setError('Failed to upload file. Please try again.');
      throw error;
    } finally {
      setUploading(false);
    }
  }

  const handleFileProcess = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!product.trim()) {
      setError('Please enter a product name.');
      return;
    }

    setProcessing(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await api.post('/process', {product: product});
      console.log('Process successful:', response.data);
      setSuccess('Prediction completed successfully!');
    }
    catch (error) {
      console.error('Error processing file:', error);
      setError('Failed to process prediction. Please try again.');
    } finally {
      setProcessing(false);
    }
  }

  const resetApp = () => {
    setFile(null);
    setUploaded(false);
    setProduct("");
    setError(null);
    setSuccess(null);
  }

  return (
    <div className="App">
      <header className="app-header">
        <h1>Product Demand Forecasting</h1>
        <p>Upload your sales data and predict future product demand</p>
      </header>
      
      <main className="app-main">
        {error && <div className="message error-message">{error}</div>}
        {success && <div className="message success-message">{success}</div>}
        
        <div className="upload-section">
          <h2>Step 1: Upload Sales Data</h2>
          <InputFile 
            file={file} 
            setFile={setFile} 
            handleFileUpload={handleFileUpload}
            uploading={uploading}
          />
          {uploaded && file && (
            <div className="file-info">
              ✅ Uploaded: <strong>{file.name}</strong>
            </div>
          )}
        </div>
        
        {uploaded && (
          <div className="predict-section">
            <h2>Step 2: Enter Product Details</h2>
            <InputField 
              product={product} 
              setProduct={setProduct} 
              handleFileProcess={handleFileProcess}
              processing={processing}
            />
          </div>
        )}
        
        {uploaded && (
          <button className="reset-button" onClick={resetApp}>
            🔄 Start Over
          </button>
        )}
      </main>
    </div>
  );
}

export default App;