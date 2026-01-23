/**
 * Integration layer for vanilla JS to React QC Interface
 * This allows existing code to use the React QC component
 */

import { SyncData } from './types';

/**
 * Open QC Interface from vanilla JS
 * This replaces the old QCInterface.open() method
 */
export function openQCInterface(syncData: SyncData) {
  // Dispatch custom event that React component listens to
  const event = new CustomEvent('openQCInterface', { detail: syncData });
  window.dispatchEvent(event);
  
  // Show React root element
  const root = document.getElementById('qc-react-root');
  if (root) {
    root.style.display = 'block';
  }
}

/**
 * Close QC Interface from vanilla JS
 */
export function closeQCInterface() {
  // Dispatch close event
  window.dispatchEvent(new Event('closeQCInterface'));
  
  // Hide React root element
  const root = document.getElementById('qc-react-root');
  if (root) {
    root.style.display = 'none';
  }
}

// Expose to window for vanilla JS access
if (typeof window !== 'undefined') {
  (window as any).openQCInterface = openQCInterface;
  (window as any).closeQCInterface = closeQCInterface;
}
