import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { WaveformPlaylistProvider, ClipTrack } from '@waveform-playlist/browser';
import { useAudioTracks } from '@waveform-playlist/browser';
import RepairModal from './RepairModal';
import { SyncData } from '../types';

/**
 * Main Repair Interface Component
 * Wraps the Repair Modal with waveform-playlist provider and editing capabilities
 */
const RepairInterface: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [syncData, setSyncData] = useState<SyncData | null>(null);
  
  // Editable tracks state - this allows tracks to be modified by editing operations
  const [editableTracks, setEditableTracks] = useState<ClipTrack[]>([]);
  const [tracksInitialized, setTracksInitialized] = useState(false);

  // Listen for Repair interface open events from vanilla JS
  useEffect(() => {
    const handleOpenRepair = (event: CustomEvent<SyncData>) => {
      setSyncData(event.detail);
      setIsOpen(true);
      setTracksInitialized(false);
      setEditableTracks([]);
    };

    window.addEventListener('openRepairInterface', handleOpenRepair as EventListener);
    
    return () => {
      window.removeEventListener('openRepairInterface', handleOpenRepair as EventListener);
    };
  }, []);

  // Also listen for close events
  useEffect(() => {
    const handleCloseRepair = () => {
      setIsOpen(false);
      setSyncData(null);
      setEditableTracks([]);
      setTracksInitialized(false);
    };

    window.addEventListener('closeRepairInterface', handleCloseRepair);
    
    return () => {
      window.removeEventListener('closeRepairInterface', handleCloseRepair);
    };
  }, []);

  // Build track configs from syncData - always apply offset correction for repair
  const trackConfigs = useMemo(() => {
    if (!syncData) return [];
    return buildTrackConfigs(syncData);
  }, [syncData]);

  // Load audio tracks
  const { tracks: loadedTracks, loading, error: trackError } = useAudioTracks(trackConfigs);
  
  // Initialize editable tracks when loaded tracks are ready
  useEffect(() => {
    if (loadedTracks.length > 0 && !tracksInitialized && !loading) {
      setEditableTracks(loadedTracks);
      setTracksInitialized(true);
    }
  }, [loadedTracks, loading, tracksInitialized]);

  // Convert error to Error object if it's a string
  const error: Error | null = trackError && typeof trackError === 'object' && 'message' in trackError 
    ? trackError as Error 
    : trackError 
      ? new Error(String(trackError)) 
      : null;

  const handleClose = useCallback(() => {
    setIsOpen(false);
    setSyncData(null);
    setEditableTracks([]);
    setTracksInitialized(false);
    // Dispatch close event for bridge
    window.dispatchEvent(new Event('closeRepairInterface'));
  }, []);

  // Handler for track changes from editing operations
  const handleTracksChange = useCallback((newTracks: ClipTrack[]) => {
    setEditableTracks(newTracks);
  }, []);

  if (!isOpen || !syncData) {
    return null;
  }

  // Use editable tracks if initialized, otherwise use loaded tracks
  const tracksToUse = tracksInitialized ? editableTracks : loadedTracks;

  // Waveform-playlist theme - Warmer dark style (matching QC interface)
  const theme = {
    // Waveform drawing mode: 'normal' = waveFillColor draws the peaks, waveOutlineColor is background
    waveformDrawMode: 'normal' as const,
    
    // Waveform colors - dark background with colored peaks
    waveOutlineColor: '#22272e',
    waveFillColor: '#58a6ff',
    waveProgressColor: '#3fb950',
    
    // Selected track waveform
    selectedWaveOutlineColor: '#2d333b',
    selectedWaveFillColor: '#79c0ff',
    selectedTrackControlsBackground: '#2d333b',
    
    // Timeline/Timescale
    timeColor: '#adbac7',
    timescaleBackgroundColor: '#2d333b',
    
    // Playhead and selection
    playheadColor: '#f85149',
    selectionColor: 'rgba(88, 166, 255, 0.3)',
    loopRegionColor: 'rgba(63, 185, 80, 0.2)',
    loopMarkerColor: '#3fb950',
    
    // Clip headers - important for editing
    clipHeaderBackgroundColor: '#2d333b',
    clipHeaderBorderColor: '#373e47',
    clipHeaderTextColor: '#adbac7',
    clipHeaderFontFamily: 'Inter, -apple-system, sans-serif',
    selectedClipHeaderBackgroundColor: '#58a6ff',
    
    // Fades
    fadeOverlayColor: 'rgba(0, 0, 0, 0.4)',
    
    // General UI colors
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
      key={`repair-${syncData?.analysisId || syncData?.analysis_id || 'default'}-${tracksInitialized ? 'edit' : 'load'}`}
      tracks={tracksToUse}
      timescale={true}
      controls={{
        show: true,
        width: 200
      }}
      waveHeight={80}
      theme={theme}
    >
      <RepairModal
        syncData={syncData}
        isOpen={isOpen}
        onClose={handleClose}
        loading={loading}
        error={error}
        tracks={editableTracks}
        onTracksChange={handleTracksChange}
      />
    </WaveformPlaylistProvider>
  );
};

/**
 * Build track configurations from sync data with offset correction applied
 */
function buildTrackConfigs(syncData: SyncData): Array<{ 
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
      color: '#ef4444'
    });
  }

  // Add dub track or component tracks - Blue color, with offset applied
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
          // Apply offset correction for repair
          startTime: Math.max(0, compOffset),
          volume: 0.8,
          color: '#58a6ff'
        });
      }
    });
  } else if (syncData.dubUrl) {
    configs.push({
      src: syncData.dubUrl,
      name: syncData.dubFile?.split('/').pop() || 'Dub',
      // Apply offset correction for repair
      startTime: Math.max(0, offset),
      volume: 0.8,
      color: '#58a6ff'
    });
  }

  return configs;
}

export default RepairInterface;
