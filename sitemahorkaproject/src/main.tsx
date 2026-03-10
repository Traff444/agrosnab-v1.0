import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import posthog from 'posthog-js';
import App from './App.tsx';
import './index.css';

posthog.init('phc_aycG7BYsQyyAO8N6NVCRnXrgjeMpw1BtCZD8SzpqZZB', {
  api_host: 'https://eu.i.posthog.com',
  person_profiles: 'identified_only',
  autocapture: true,
  capture_pageview: true,
  capture_pageleave: true,
  enable_recording_console_log: true,
  session_recording: {
    maskAllInputs: false,
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
