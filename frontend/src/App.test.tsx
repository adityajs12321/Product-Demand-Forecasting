import React from 'react';
import { render, screen } from '@testing-library/react';
import App from './App';

test('renders Product Demand Forecasting title', () => {
  render(<App />);
  const titleElement = screen.getByText(/Product Demand Forecasting/i);
  expect(titleElement).toBeInTheDocument();
});
