import React, {useState, useRef, useEffect} from 'react';
import './App.css';
import InputFile from './components/InputFile';
import api from './api';
import InputField from './components/InputField';
import { Analytics } from '@vercel/analytics/react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
  Title,
  Tooltip,
  Legend
);

function App() {
  const [file, setFile] = useState<File | null>(null);
  const [uploaded, setUploaded] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [product, setProduct] = useState("");
  const [forecastModel, setForecastModel] = useState(1);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [chartData, setChartData] = useState<any>(null);
  const [showChart, setShowChart] = useState(false);
  const [isDarkMode, setIsDarkMode] = useState(true);
  const chartRef = useRef<HTMLCanvasElement>(null);
  const chartInstance = useRef<ChartJS | null>(null);

  useEffect(() => {
    if (isDarkMode) {
      document.body.classList.add('dark-mode');
    } else {
      document.body.classList.remove('dark-mode');
    }
  }, [isDarkMode]);
  
  // Create chart when chartData changes
  useEffect(() => {
    if (chartData && chartRef.current) {
      // Destroy existing chart if it exists
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
      
      const ctx = chartRef.current.getContext('2d');
      if (ctx) {
        const textColor = isDarkMode ? '#e0e0e0' : '#333';
        const gridColor = isDarkMode ? '#444' : '#e9ecef';

        chartInstance.current = new ChartJS(ctx, {
          type: 'line',
          data: chartData,
          options: {
            responsive: true,
            maintainAspectRatio: false,
            color: textColor,
            plugins: {
              legend: {
                position: 'top' as const,
                labels: {
                  color: textColor
                }
              },
              title: {
                display: true,
                text: `Demand Forecast for ${product}`,
                color: textColor
              },
            },
            scales: {
              y: {
                beginAtZero: true,
                grid: {
                  color: gridColor
                },
                ticks: {
                  color: textColor
                },
                title: {
                  display: true,
                  text: 'Demand (Units)',
                  color: textColor
                }
              },
              x: {
                grid: {
                  color: gridColor
                },
                ticks: {
                  color: textColor
                },
                title: {
                  display: true,
                  text: 'Time Period',
                  color: textColor
                }
              }
            }
          }
        });
      }
    }
    
    // Cleanup on unmount
    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
    };
  }, [chartData, product, isDarkMode]);
  
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

  const handleFileProcess = async (e: React.FormEvent, _product: string) => {
    e.preventDefault();
    setProduct(_product);
    console.log('Processing product:', _product);
    if (!_product.trim()) {
      setError('Please enter a product name.');
      return;
    }

    setProcessing(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await api.post('/process', {product: _product, forecast_model: forecastModel});
      // console.log('Process successful:', response.data);
      setSuccess('Prediction completed successfully!');
      
      // Generate sample forecast data for demonstration
      const monthLabels = response.data.timerange.map((date: string) => {
        const d = new Date(date);
        return `${d.getDate()}/${d.getMonth()+1}`;
      });

      // console.log('Month Labels:', monthLabels);
      // console.log('Sales Data:', response.data.sales);
      
      // Sample historical and predicted data - replace with actual API response
      const sales = response.data.sales;
      
      const data = {
        labels: monthLabels,
        datasets: [
          {
            label: 'Predicted Demand',
            data: sales,
            borderColor: 'rgb(75, 192, 192)',
            backgroundColor: 'rgba(75, 192, 192, 0.2)',
            tension: 0.1
          },
        ]
      };
      
      setChartData(data);
      setShowChart(true);
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
    setUploading(false);
    setProcessing(false);
    setProduct("");
    setForecastModel(1);
    setError(null);
    setSuccess(null);
    setChartData(null);
    setShowChart(false);
  }

  return (
    <>
      <div className="App">
        <div className="app-header">
          <header className="header-copy">
            <h1>Product Demand Forecasting</h1>
            <p className="hero-subtext">Upload retail data, choose a model, and visualize future demand.</p>
          </header>
          <button className="mode-toggle" onClick={() => setIsDarkMode(!isDarkMode)}>
            {isDarkMode ? 'Light Mode' : 'Dark Mode'}
          </button>
        </div>
        
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
                Uploaded: <strong>{file.name}</strong>
              </div>
            )}
          </div>
          
          {uploaded && (
            <div className="predict-section">
              <h2>Step 2: Enter Product Details</h2>
              <p className="form-label">Product Name & Forecast Model</p>
              <InputField 
                product={product} 
                setProduct={setProduct} 
                forecastModel={forecastModel}
                setForecastModel={setForecastModel}
                handleFileProcess={handleFileProcess}
                processing={processing}
              />
            </div>
          )}
          
          {showChart && chartData && (
            <div className="chart-section">
              <h2>Step 3: Demand Forecast Results</h2>
              <div className="chart-container">
                <canvas ref={chartRef}></canvas>
              </div>
            </div>
          )}
          
          {uploaded && (
            <button className="reset-button" onClick={resetApp}>
              Start New Forecast
            </button>
          )}
        </main>
      </div>
      <Analytics />
    </>
  );
}

export default App;