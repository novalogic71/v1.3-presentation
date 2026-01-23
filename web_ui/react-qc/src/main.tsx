import React from 'react';
import ReactDOM from 'react-dom/client';
import QCInterface from './components/QCInterface';
import RepairInterface from './components/RepairInterface';
import './styles/global.css';
import './integration';
import './repair-integration';

// Mount React QC Interface to existing DOM element
const mountQCInterface = () => {
  let rootElement = document.getElementById('qc-react-root');
  
  if (!rootElement) {
    // Create mount point if it doesn't exist
    rootElement = document.createElement('div');
    rootElement.id = 'qc-react-root';
    rootElement.style.display = 'none'; // Hidden by default
    document.body.appendChild(rootElement);
  }

  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <QCInterface />
    </React.StrictMode>
  );
};

// Mount React Repair Interface to existing DOM element
const mountRepairInterface = () => {
  let rootElement = document.getElementById('repair-react-root');
  
  if (!rootElement) {
    // Create mount point if it doesn't exist
    rootElement = document.createElement('div');
    rootElement.id = 'repair-react-root';
    rootElement.style.display = 'none'; // Hidden by default
    document.body.appendChild(rootElement);
  }

  const root = ReactDOM.createRoot(rootElement);
  root.render(
    <React.StrictMode>
      <RepairInterface />
    </React.StrictMode>
  );
};

// Mount all interfaces
const mountAllInterfaces = () => {
  mountQCInterface();
  mountRepairInterface();
};

// Auto-mount when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', mountAllInterfaces);
} else {
  mountAllInterfaces();
}

// Export for manual mounting from vanilla JS
(window as any).mountQCInterface = mountQCInterface;
(window as any).mountRepairInterface = mountRepairInterface;