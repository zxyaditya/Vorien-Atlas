import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';
import { ErrorBoundary } from './components/ErrorBoundary';

// Suppress benign lightweight-charts unmount/canvas teardown errors
window.addEventListener("error", (e) => {
  if (e.message && (e.message.includes("Object is disposed") || e.message.includes("DevicePixelContentBoxBinding"))) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});

window.addEventListener("unhandledrejection", (e) => {
  if (e.reason && typeof e.reason.message === "string" && e.reason.message.includes("Object is disposed")) {
    e.stopImmediatePropagation();
    e.preventDefault();
  }
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <ErrorBoundary>
    <App />
  </ErrorBoundary>
);
