/**
 * Integration layer for vanilla JS to React Repair Interface
 * This allows existing code to use the React Repair component with editing features
 */

import { SyncData } from './types';

/**
 * Open Repair Interface from vanilla JS
 * Opens the DAW-style editor with clip dragging, splitting, and export
 */
export function openRepairInterface(syncData: SyncData) {
  // Dispatch custom event that React component listens to
  const event = new CustomEvent('openRepairInterface', { detail: syncData });
  window.dispatchEvent(event);
  
  // Show React root element
  const root = document.getElementById('repair-react-root');
  if (root) {
    root.style.display = 'block';
  }
}

/**
 * Close Repair Interface from vanilla JS
 */
export function closeRepairInterface() {
  // Dispatch close event
  window.dispatchEvent(new Event('closeRepairInterface'));
  
  // Hide React root element
  const root = document.getElementById('repair-react-root');
  if (root) {
    root.style.display = 'none';
  }
}

// Expose to window for vanilla JS access
if (typeof window !== 'undefined') {
  (window as any).openRepairInterface = openRepairInterface;
  (window as any).closeRepairInterface = closeRepairInterface;
}
