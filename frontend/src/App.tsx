import React, {useState} from 'react';
import './App.css';
import InputFile from './components/InputFile';
import api from './api';
import InputField from './components/InputField';

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [uploaded, setUploaded] = useState(false);
  const [product, setProduct] = useState("");
  
  // function to handle file upload to the backend (fastapi with UploadFile class) and axios
  async function handleFileUpload(file: File) {
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
      return response.data;
    }
    catch (error) {
      console.error('Upload failed:', error);
      throw error;
    }
  }

  const handleFileProcess = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      const response = await api.post('/process', {product: product});
      console.log('Process successful:', response.data);
    }
    catch (error) {
      console.error('Error processing file:', error);
    }
  }

  return (
    <div className="App">
      Predict Future Sales
      <InputFile file={file} setFile={setFile} handleFileUpload={handleFileUpload}/>
      {uploaded ? <InputField product={product} setProduct={setProduct} handleFileProcess={handleFileProcess}/> : null}
    </div>
  );
}

export default App;
