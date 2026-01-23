import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { WaveformPlaylistProvider } from '@waveform-playlist/browser';
import { useAudioTracks } from '@waveform-playlist/browser';
import QCModal from './QCModal';
import { SyncData } from '../types';

/**
 * Main QC Interface Component
 * Wraps the QC Modal with waveform-playlist provider
 */
const QCInterface: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [syncData, setSyncData] = useState<SyncData | null>(null);
  const [isCorrectedMode, setIsCorrectedMode] = useState(false);

  // Listen for QC interface open events from vanilla JS
  useEffect(() => {
    const handleOpenQC = (event: CustomEvent<SyncData>) => {
      setSyncData(event.detail);
      setIsOpen(true);
      setIsCorrectedMode(false); // Reset to "Before Fix" when opening
    };

    window.addEventListener('openQCInterface', handleOpenQC as EventListener);
    
    return () => {
      window.removeEventListener('openQCInterface', handleOpenQC as EventListener);
    };
  }, []);

  // Also listen for close events
  useEffect(() => {
    const handleCloseQC = () => {
      setIsOpen(false);
      setSyncData(null);
      setIsCorrectedMode(false);
    };

    window.addEventListener('closeQCInterface', handleCloseQC);
    
    return () => {
      window.removeEventListener('closeQCInterface', handleCloseQC);
    };
  }, []);

  // Build track configs from syncData with offset correction
  const trackConfigs = useMemo(() => {
    if (!syncData) return [];
    return buildTrackConfigs(syncData, isCorrectedMode);
  }, [syncData, isCorrectedMode]);

  // Load audio tracks when syncData or corrected mode changes
  const { tracks, loading, error: trackError } = useAudioTracks(trackConfigs);
  
  // Convert error to Error object if it's a string
  const error: Error | null = trackError && typeof trackError === 'object' && 'message' in trackError 
    ? trackError as Error 
    : trackError 
      ? new Error(String(trackError)) 
      : null;

  const handleClose = useCallback(() => {
    setIsOpen(false);
    setSyncData(null);
    setIsCorrectedMode(false);
    // Dispatch close event for bridge
    window.dispatchEvent(new Event('closeQCInterface'));
  }, []);

  if (!isOpen || !syncData) {
    return null;
  }

  // Waveform-playlist theme - Warmer dark style (like flexible API example)
  const theme = {
    // Waveform drawing mode: 'normal' = waveFillColor draws the peaks, waveOutlineColor is background
    waveformDrawMode: 'normal' as const,
    
    // Waveform colors - dark background with colored peaks
    waveOutlineColor: '#22272e',    // Dark background behind waveform
    waveFillColor: '#58a6ff',       // Blue waveform peaks
    waveProgressColor: '#3fb950',   // Green for played portion
    
    // Selected track waveform
    selectedWaveOutlineColor: '#2d333b',
    selectedWaveFillColor: '#79c0ff',
    selectedTrackControlsBackground: '#2d333b',
    
    // Timeline/Timescale - slightly lighter for visibility
    timeColor: '#adbac7',
    timescaleBackgroundColor: '#2d333b',
    
    // Playhead and selection
    playheadColor: '#f85149',
    selectionColor: 'rgba(88, 166, 255, 0.3)',
    loopRegionColor: 'rgba(63, 185, 80, 0.2)',
    loopMarkerColor: '#3fb950',
    
    // Clip headers - warmer tones
    clipHeaderBackgroundColor: '#2d333b',
    clipHeaderBorderColor: '#373e47',
    clipHeaderTextColor: '#adbac7',
    clipHeaderFontFamily: 'Inter, -apple-system, sans-serif',
    selectedClipHeaderBackgroundColor: '#373e47',
    
    // Fades
    fadeOverlayColor: 'rgba(0, 0, 0, 0.4)',
    
    // General UI colors - warmer dark palette
    backgroundColor: '#1c2128',
    surfaceColor: '#22272e',
    borderColor: '#373e47',
    textColor: '#adbac7',
    textColorMuted: '#768390',
    
    // Inputs
    inputBackground: '#22272e',
    inputBorder: '#373e47',
    inputText: '#adbac7',
    inputPlaceholder: '#768390',
    inputFocusBorder: '#58a6ff',
    
    // Buttons
    buttonBackground: '#2d333b',
  };

  return (
    <WaveformPlaylistProvider 
      key={`qc-${isCorrectedMode ? 'corrected' : 'before'}-${syncData?.analysisId || syncData?.analysis_id || 'default'}`}
      tracks={tracks}
      controls={{
        show: true,
        width: 200
      }}
      waveHeight={80}
      theme={theme}
    >
      <QCModal
        syncData={syncData}
        isOpen={isOpen}
        onClose={handleClose}
        loading={loading}
        error={error}
        isCorrectedMode={isCorrectedMode}
        onCorrectedModeChange={setIsCorrectedMode}
      />
    </WaveformPlaylistProvider>
  );
};

/**
 * Build track configurations from sync data with offset correction
 */
function buildTrackConfigs(syncData: SyncData, isCorrectedMode: boolean): Array<{ 
  src: string; 
  name: string; 
  startTime?: number;
  volume?: number;
  color?: string;
}> {
  const configs: Array<{ 
    src: string; 
    name: string; 
    startTime?: number; 
    volume?: number; 
    color?: string;
  }> = [];
  const offset = syncData.detectedOffset || 0;

  // Add master track (always starts at 0) - Red/Coral color
  if (syncData.masterUrl) {
    configs.push({
      src: syncData.masterUrl,
      name: syncData.masterFile?.split('/').pop() || 'Master',
      startTime: 0,
      volume: 0.8,
      color: '#ef4444'  // Red color for Master track
    });
  }

  // Add dub track or component tracks - Blue color
  const components = syncData.components || syncData.componentResults || [];
  if (components.length > 0) {
    components.forEach((comp, index) => {
      const url = comp.dubUrl || comp.dub_url || comp.audioUrl;
      const name = comp.name || comp.dubFile?.split('/').pop() || `Component ${index + 1}`;
      const compOffset = comp.detectedOffset || comp.detected_offset || offset;
      
      if (url) {
        configs.push({ 
          src: url, 
          name,
          // After Fix: Apply offset correction (shift dub to align with master)
          // Before Fix: Start at 0 to show the mismatch
          startTime: isCorrectedMode ? Math.max(0, compOffset) : 0,
          volume: 0.8,
          color: '#58a6ff'  // Blue color for Dub tracks
        });
      }
    });
  } else if (syncData.dubUrl) {
    configs.push({
      src: syncData.dubUrl,
      name: syncData.dubFile?.split('/').pop() || 'Dub',
      // After Fix: Apply offset correction
      // Before Fix: Start at 0 to show the mismatch
      startTime: isCorrectedMode ? Math.max(0, offset) : 0,
      volume: 0.8,
      color: '#58a6ff'  // Blue color for Dub tracks
    });
  }

  return configs;
}

export default QCInterface;
