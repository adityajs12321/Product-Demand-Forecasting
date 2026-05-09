import axios from 'axios';

const api = axios.create({
  // Use Vercel environment variable in production, fallback to local backend for development.
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:10000',
});

export default api;