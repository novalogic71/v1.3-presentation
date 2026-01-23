import React, { useState, useEffect, useCallback } from 'react';
import { 
  Waveform,
  usePlaylistControls, 
  usePlaylistData,
  usePlaybackAnimation,
  useClipDragHandlers,
  useClipSplitting,
  useDragSensors,
  useExportWav,
  ClipTrack,
  RewindButton,
  PlayButton,
  PauseButton,
  StopButton,
  FastForwardButton,
  SkipBackwardButton,
  SkipForwardButton,
  ZoomInButton,
  ZoomOutButton
} from '@waveform-playlist/browser';
import { DndContext } from '@dnd-kit/core';
import { restrictToHorizontalAxis } from '@dnd-kit/modifiers';
import { SyncData, RepairResponse } from '../types';
import { 
  applyStandardRepair, 
  applyPerChannelRepair, 
  calculateAdjustedOffsets,
  generateOutputPath,
  isPerChannelMode 
} from '../services/repairApi';
import './RepairModal.css';

interface RepairModalProps {
  syncData: SyncData;
  isOpen: boolean;
  onClose: () => void;
  loading: boolean;
  error: Error | null;
  tracks: ClipTrack[];
  onTracksChange: (tracks: ClipTrack[]) => void;
}

const RepairModal: React.FC<RepairModalProps> = ({ 
  syncData, 
  isOpen, 
  onClose, 
  loading, 
  error,
  tracks,
  onTracksChange
}) => {
  const { 
    play, 
    stop,
    formatTime,
    setTrackVolume,
    setTrackMute,
    setTrackSolo,
    setMasterVolume: setMasterVolumeControl
  } = usePlaylistControls();
  const playlistData = usePlaylistData();
  const playbackAnimation = usePlaybackAnimation();
  const [masterVolume, setMasterVolumeState] = useState(0.8);
  const [trackVolumes, setTrackVolumes] = useState<Record<number, number>>({});
  const [trackMutes, setTrackMutes] = useState<Record<number, boolean>>({});
  const [trackSolos, setTrackSolos] = useState<Record<number, boolean>>({});
  
  // Undo history for editing operations
  const [history, setHistory] = useState<ClipTrack[][]>([]);
  const maxHistorySize = 50;

  // FFmpeg repair state
  const [isRepairing, setIsRepairing] = useState(false);
  const [repairProgress, setRepairProgress] = useState('');
  const [repairResult, setRepairResult] = useState<RepairResponse | null>(null);
  const [repairError, setRepairError] = useState<string | null>(null);
  const [showOutputDialog, setShowOutputDialog] = useState(false);
  const [outputPath, setOutputPath] = useState('');
  const [keepDuration, setKeepDuration] = useState(true);

  // Manual offset override state
  const [manualOffset, setManualOffset] = useState<number | null>(null);
  const [offsetInputValue, setOffsetInputValue] = useState('');

  // Export functionality
  const { exportWav, isExporting, progress: exportProgress } = useExportWav();

  // Get samples per pixel and sample rate for editing hooks
  const samplesPerPixel = playlistData.samplesPerPixel || 1000;
  const sampleRate = playlistData.sampleRate || 44100;

  // Drag sensors for clip editing
  const sensors = useDragSensors();

  // Clip drag handlers for moving and trimming clips
  const { 
    onDragStart, 
    onDragMove, 
    onDragEnd, 
    collisionModifier 
  } = useClipDragHandlers({
    tracks,
    onTracksChange: handleTracksChangeWithHistory,
    samplesPerPixel,
    sampleRate,
  });

  // Clip splitting functionality
  const { splitClipAtPlayhead } = useClipSplitting({
    tracks,
    onTracksChange: handleTracksChangeWithHistory,
    sampleRate,
    samplesPerPixel,
  });

  // Handle tracks change with undo history
  function handleTracksChangeWithHistory(newTracks: ClipTrack[]) {
    // Add current state to history before making change
    setHistory(prev => {
      const newHistory = [...prev, tracks];
      // Limit history size
      if (newHistory.length > maxHistorySize) {
        return newHistory.slice(-maxHistorySize);
      }
      return newHistory;
    });
    onTracksChange(newTracks);
  }

  // Undo last edit
  const handleUndo = useCallback(() => {
    if (history.length > 0) {
      const previousState = history[history.length - 1];
      setHistory(prev => prev.slice(0, -1));
      onTracksChange(previousState);
    }
  }, [history, onTracksChange]);

  // Handle split at playhead
  const handleSplit = useCallback(() => {
    if (playlistData.isReady) {
      const success = splitClipAtPlayhead();
      if (success) {
        console.log('Split clip at playhead');
      }
    }
  }, [splitClipAtPlayhead, playlistData.isReady]);

  // Handle export to WAV (client-side preview)
  const handleExport = useCallback(async () => {
    if (!playlistData.isReady) return;
    
    try {
      const trackStates = playlistData.trackStates || [];
      const filename = `repaired-${syncData.dubFile?.split('/').pop()?.replace(/\.[^/.]+$/, '') || 'audio'}`;
      const result = await exportWav(tracks, trackStates, {
        filename,
        mode: 'master',
      });
      
      // ExportResult contains audioBuffer, blob, and duration
      if (result.blob) {
        console.log('Export successful, duration:', result.duration);
        // Trigger download
        const url = URL.createObjectURL(result.blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${filename}.wav`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        // Dispatch event for parent to handle
        window.dispatchEvent(new CustomEvent('repairExported', {
          detail: { filename: `${filename}.wav`, blob: result.blob, duration: result.duration }
        }));
      }
    } catch (err) {
      console.error('Export error:', err);
    }
  }, [exportWav, tracks, playlistData.trackStates, playlistData.isReady, syncData.dubFile]);

  // Initialize output path when dialog opens
  useEffect(() => {
    if (showOutputDialog && syncData.dubPath) {
      setOutputPath(generateOutputPath(syncData.dubPath, '_repaired'));
    }
  }, [showOutputDialog, syncData.dubPath]);

  // Initialize offset input value from detected offset
  useEffect(() => {
    const initialOffset = syncData.detectedOffset || 0;
    setOffsetInputValue(initialOffset.toFixed(3));
    setManualOffset(null); // Reset manual override when new data loads
  }, [syncData.detectedOffset]);

  // Get the effective offset (manual override or detected)
  const effectiveOffset = manualOffset !== null ? manualOffset : (syncData.detectedOffset || 0);

  // Parse timecode input (supports HH:MM:SS:FF or seconds)
  const parseOffsetInput = (input: string): number | null => {
    const trimmed = input.trim();
    
    // Try parsing as seconds (e.g., "89.068" or "-89.068")
    const asSeconds = parseFloat(trimmed);
    if (!isNaN(asSeconds)) {
      return asSeconds;
    }
    
    // Try parsing as timecode HH:MM:SS:FF or HH:MM:SS.mmm
    const tcMatch = trimmed.match(/^([+-])?(\d{1,2}):(\d{2}):(\d{2})[:.](\d{1,3})$/);
    if (tcMatch) {
      const sign = tcMatch[1] === '-' ? -1 : 1;
      const hours = parseInt(tcMatch[2], 10);
      const minutes = parseInt(tcMatch[3], 10);
      const seconds = parseInt(tcMatch[4], 10);
      const framesOrMs = parseInt(tcMatch[5], 10);
      
      // If it has 3 digits after the last separator, treat as milliseconds
      // Otherwise treat as frames
      let totalSeconds = hours * 3600 + minutes * 60 + seconds;
      if (tcMatch[5].length === 3) {
        totalSeconds += framesOrMs / 1000;
      } else {
        const fps = syncData.frameRate || 23.976;
        totalSeconds += framesOrMs / fps;
      }
      
      return sign * totalSeconds;
    }
    
    return null;
  };

  // Apply manual offset to the dub track
  const handleApplyManualOffset = useCallback(() => {
    const newOffset = parseOffsetInput(offsetInputValue);
    if (newOffset === null) {
      alert('Invalid offset format. Use seconds (e.g., 89.068) or timecode (e.g., 00:01:29:01)');
      return;
    }
    
    setManualOffset(newOffset);
    
    // Update the dub track's start position based on the new offset
    if (tracks.length > 1 && playlistData.isReady) {
      const dubTrack = tracks[1];
      if (dubTrack && dubTrack.clips.length > 0) {
        const newStartSample = Math.round(newOffset * (dubTrack.clips[0].sampleRate || sampleRate || 48000));
        
        const updatedTracks = tracks.map((track, index) => {
          if (index === 1) { // Dub track
            return {
              ...track,
              clips: track.clips.map((clip, clipIndex) => {
                if (clipIndex === 0) {
                  return { ...clip, startSample: Math.max(0, newStartSample) };
                }
                return clip;
              })
            };
          }
          return track;
        });
        
        onTracksChange(updatedTracks);
        console.log(`Applied manual offset: ${newOffset}s (${newStartSample} samples)`);
      }
    }
  }, [offsetInputValue, tracks, playlistData.isReady, sampleRate, onTracksChange, syncData.frameRate]);

  // Open the output path dialog for FFmpeg repair
  const handleOpenRepairDialog = useCallback(() => {
    if (!syncData.dubPath) {
      setRepairError('No dub file path available for repair');
      return;
    }
    setRepairError(null);
    setRepairResult(null);
    setShowOutputDialog(true);
  }, [syncData.dubPath]);

  // Apply FFmpeg repair to source file
  const handleApplyRepair = useCallback(async () => {
    if (!syncData.dubPath) {
      setRepairError('No dub file path available for repair');
      return;
    }

    setIsRepairing(true);
    setRepairProgress('Preparing repair...');
    setRepairError(null);
    setRepairResult(null);

    try {
      let result: RepairResponse;

      if (isPerChannelMode(syncData)) {
        // Componentized/Per-channel repair
        setRepairProgress('Calculating adjusted offsets from track positions...');
        
        // Convert tracks to the format expected by calculateAdjustedOffsets
        // AudioClip uses startSample in samples, so we convert to seconds
        const trackData = tracks.map(t => ({
          name: t.name,
          clips: t.clips.map(c => ({ 
            startTime: c.startSample / (c.sampleRate || sampleRate || 48000) 
          }))
        }));
        
        const adjustedOffsets = calculateAdjustedOffsets(
          trackData,
          syncData.perChannel || null,
          syncData.detectedOffset || 0
        );

        console.log('Applying per-channel repair with offsets:', adjustedOffsets);
        setRepairProgress('Applying per-channel offsets via FFmpeg...');

        result = await applyPerChannelRepair(
          syncData.dubPath,
          adjustedOffsets,
          outputPath || undefined,
          keepDuration
        );
      } else {
        // Standard single-offset repair
        // Calculate the offset from the dub track position (index 1)
        // AudioClip uses startSample in samples, so we convert to seconds
        const dubTrack = tracks[1];
        const dubClip = dubTrack?.clips?.[0];
        const adjustedOffset = dubClip 
          ? dubClip.startSample / (dubClip.sampleRate || sampleRate || 48000)
          : syncData.detectedOffset || 0;

        console.log('Applying standard repair with offset:', adjustedOffset);
        setRepairProgress('Applying offset correction via FFmpeg...');

        result = await applyStandardRepair(
          syncData.dubPath,
          adjustedOffset,
          outputPath || undefined,
          keepDuration
        );
      }

      setRepairResult(result);
      setRepairProgress('');
      setShowOutputDialog(false);

      // Dispatch success event
      window.dispatchEvent(new CustomEvent('repairApplied', {
        detail: {
          success: result.success,
          outputFile: result.output_file,
          outputSize: result.output_size,
        }
      }));

      // Show success message via toast (if available)
      if ((window as any).app?.showToast) {
        (window as any).app.showToast('success', `Repair completed: ${result.output_file}`, 'FFmpeg Repair');
      }

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error during repair';
      setRepairError(errorMessage);
      setRepairProgress('');
      console.error('Repair error:', err);
    } finally {
      setIsRepairing(false);
    }
  }, [syncData, tracks, outputPath, keepDuration]);

  // Keyboard shortcuts for editing
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if typing in an input
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return;
      }

      switch (e.key.toLowerCase()) {
        case 's':
          // Split at playhead
          if (!e.ctrlKey && !e.metaKey) {
            e.preventDefault();
            handleSplit();
          }
          break;
        case 'z':
          // Undo
          if (e.ctrlKey || e.metaKey) {
            e.preventDefault();
            handleUndo();
          }
          break;
        case ' ':
          // Space for play/pause
          e.preventDefault();
          if (playbackAnimation.isPlaying) {
            stop();
          } else {
            play();
          }
          break;
      }
    };

    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, handleSplit, handleUndo, play, stop, playbackAnimation.isPlaying]);

  useEffect(() => {
    if (!isOpen) {
      stop();
    }
  }, [isOpen, stop]);

  // Get track states from playlist data
  const trackStates = playlistData.trackStates || [];

  // Initialize track volumes from track states
  useEffect(() => {
    if (!playlistData.isReady || !playlistData.tracks) return;
    
    const volumes: Record<number, number> = {};
    const mutes: Record<number, boolean> = {};
    const solos: Record<number, boolean> = {};
    
    playlistData.tracks.forEach((_, index) => {
      volumes[index] = trackStates[index]?.volume ?? 0.8;
      mutes[index] = trackStates[index]?.muted ?? false;
      solos[index] = trackStates[index]?.soloed ?? false;
    });
    
    setTrackVolumes(volumes);
    setTrackMutes(mutes);
    setTrackSolos(solos);
  }, [playlistData.isReady, playlistData.tracks, trackStates]);

  // Update track volumes when sliders change
  useEffect(() => {
    if (!playlistData.isReady) return;
    
    Object.entries(trackVolumes).forEach(([index, volume]) => {
      setTrackVolume(parseInt(index), volume);
    });
  }, [trackVolumes, setTrackVolume, playlistData.isReady]);

  // Update track mutes
  useEffect(() => {
    if (!playlistData.isReady) return;
    
    Object.entries(trackMutes).forEach(([index, muted]) => {
      setTrackMute(parseInt(index), muted);
    });
  }, [trackMutes, setTrackMute, playlistData.isReady]);

  // Update track solos
  useEffect(() => {
    if (!playlistData.isReady) return;
    
    Object.entries(trackSolos).forEach(([index, soloed]) => {
      setTrackSolo(parseInt(index), soloed);
    });
  }, [trackSolos, setTrackSolo, playlistData.isReady]);

  if (!isOpen) return null;

  const confidence = syncData.confidence || 0;

  return (
    <div className="repair-modal-overlay" onClick={onClose}>
      <div className="repair-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="repair-header">
          <h3>
            <i className="fas fa-wrench"></i> Repair Editor
          </h3>
          <button className="repair-close-btn" onClick={onClose}>
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* File Info */}
        <div className="repair-file-info">
          <div className="repair-file-pair">
            <div className="repair-file-item master-file">
              <label>Master File:</label>
              <span>{syncData.masterFile || 'No file selected'}</span>
            </div>
            <div className="repair-file-item dub-file">
              <label>Dub File:</label>
              <span>{syncData.dubFile || 'No file selected'}</span>
            </div>
          </div>
          <div className="repair-sync-info">
            <div className="repair-offset-editor">
              <label>Offset:</label>
              <div className="repair-offset-input-group">
                <input
                  type="text"
                  className="repair-offset-input"
                  value={offsetInputValue}
                  onChange={(e) => setOffsetInputValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleApplyManualOffset();
                    }
                  }}
                  placeholder="Seconds or HH:MM:SS:FF"
                  title="Enter offset in seconds (e.g., 89.068) or timecode (e.g., 00:01:29:01)"
                />
                <button 
                  className="repair-offset-apply-btn"
                  onClick={handleApplyManualOffset}
                  title="Apply offset to dub track"
                >
                  <i className="fas fa-check"></i>
                </button>
              </div>
              <span className="repair-offset-timecode">
                {formatOffset(effectiveOffset, syncData.frameRate || 23.976)}
                {manualOffset !== null && <span className="repair-offset-override"> (override)</span>}
              </span>
            </div>
            <div className="repair-confidence-display">
              <label>Confidence:</label>
              <span>{Math.round(confidence * 100)}%</span>
            </div>
          </div>
        </div>

        {/* Editing Toolbar */}
        <div className="repair-editing-toolbar">
          <h4><i className="fas fa-edit"></i> Editing Tools</h4>
          <div className="repair-toolbar-buttons">
            <button 
              className="repair-toolbar-btn"
              onClick={handleSplit}
              disabled={!playlistData.isReady}
              title="Split clip at playhead (S)"
            >
              <i className="fas fa-cut"></i> Split (S)
            </button>
            <button 
              className="repair-toolbar-btn"
              onClick={handleUndo}
              disabled={history.length === 0}
              title="Undo last edit (Ctrl+Z)"
            >
              <i className="fas fa-undo"></i> Undo ({history.length})
            </button>
            <div className="repair-toolbar-separator"></div>
            <button 
              className="repair-toolbar-btn export-btn"
              onClick={handleExport}
              disabled={!playlistData.isReady || isExporting}
              title="Export repaired audio to WAV"
            >
              {isExporting ? (
                <>
                  <i className="fas fa-spinner fa-spin"></i> Exporting ({Math.round(exportProgress * 100)}%)
                </>
              ) : (
                <>
                  <i className="fas fa-download"></i> Export WAV
                </>
              )}
            </button>
          </div>
          <div className="repair-toolbar-hints">
            <span><kbd>Drag</kbd> clips to move</span>
            <span><kbd>Drag edges</kbd> to trim</span>
            <span><kbd>Space</kbd> play/pause</span>
          </div>
        </div>

        {/* Waveform Display with Editing */}
        <div className="repair-waveform-container">
          <div className="repair-waveform-header">
            <h4><i className="fas fa-chart-area"></i> Waveform Editor</h4>
            <div className="repair-view-controls">
              <div className="repair-zoom-controls">
                <ZoomOutButton className="repair-zoom-btn" disabled={!playlistData.canZoomOut} />
                <ZoomInButton className="repair-zoom-btn" disabled={!playlistData.canZoomIn} />
              </div>
            </div>
          </div>

          <div className="repair-waveform-display">
            {loading && <div className="repair-loading">Loading waveforms...</div>}
            {error && (
              <div className="repair-error">
                <div className="repair-error-title">Error Loading Audio</div>
                <div className="repair-error-message">
                  {error.message.includes('Rate limit') || error.message.includes('429') ? (
                    <>
                      <p><strong>Rate limit exceeded.</strong> Please wait a moment and try again.</p>
                      <p className="repair-error-hint">The server is temporarily limiting requests.</p>
                    </>
                  ) : (
                    error.message
                  )}
                </div>
              </div>
            )}
            {!loading && !error && (
              <DndContext
                sensors={sensors}
                onDragStart={onDragStart}
                onDragMove={onDragMove}
                onDragEnd={onDragEnd}
                modifiers={[restrictToHorizontalAxis, collisionModifier]}
              >
                <Waveform 
                  showClipHeaders={true}
                  interactiveClips={true}
                  renderTrackControls={(trackIndex: number) => {
                    const trackState = trackStates[trackIndex] || { volume: 0.8, muted: false, soloed: false, pan: 0 };
                    const volume = trackVolumes[trackIndex] ?? trackState.volume ?? 0.8;
                    const muted = trackMutes[trackIndex] ?? trackState.muted ?? false;
                    const soloed = trackSolos[trackIndex] ?? trackState.soloed ?? false;
                    const track = playlistData.tracks?.[trackIndex];
                    
                    // Master track is index 0, Dub tracks are index 1+
                    const isMasterTrack = trackIndex === 0;
                    
                    return (
                      <div className={`repair-track-controls-panel ${isMasterTrack ? 'master-track' : 'dub-track'}`}>
                        <div 
                          className={`repair-track-label ${isMasterTrack ? 'master-track' : 'dub-track'}`} 
                          title={track?.name || `Track ${trackIndex + 1}`}
                        >
                          {track?.name || `Track ${trackIndex + 1}`}
                        </div>
                        <div className="repair-track-controls-grid">
                          <div className="repair-track-buttons-row">
                            <button
                              className={`repair-track-btn repair-mute-btn ${muted ? 'active' : ''}`}
                              onClick={() => {
                                const newMuted = !muted;
                                setTrackMutes(prev => ({ ...prev, [trackIndex]: newMuted }));
                                setTrackMute(trackIndex, newMuted);
                              }}
                              title="Mute"
                            >
                              M
                            </button>
                            <button
                              className={`repair-track-btn repair-solo-btn ${soloed ? 'active' : ''}`}
                              onClick={() => {
                                const newSoloed = !soloed;
                                setTrackSolos(prev => ({ ...prev, [trackIndex]: newSoloed }));
                                setTrackSolo(trackIndex, newSoloed);
                              }}
                              title="Solo"
                            >
                              S
                            </button>
                          </div>
                          <div className="repair-track-control-group">
                            <div className="repair-track-slider-row">
                              <input
                                type="range"
                                className="repair-track-control-slider"
                                min="0"
                                max="1"
                                step="0.01"
                                value={volume}
                                onChange={(e) => {
                                  const newVolume = parseFloat(e.target.value);
                                  setTrackVolumes(prev => ({ ...prev, [trackIndex]: newVolume }));
                                  setTrackVolume(trackIndex, newVolume);
                                }}
                              />
                              <span className="repair-track-control-value">{Math.round(volume * 100)}%</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  }}
                />
              </DndContext>
            )}
          </div>
        </div>

        {/* Transport Controls */}
        <div className="repair-transport-controls">
          <h4><i className="fas fa-play"></i> Transport Controls</h4>
          
          <div className="repair-transport-row">
            <div className="repair-transport-buttons">
              <RewindButton className="repair-transport-btn" />
              <SkipBackwardButton className="repair-transport-btn" />
              {playbackAnimation.isPlaying ? (
                <PauseButton className="repair-transport-btn repair-transport-btn-primary" />
              ) : (
                <PlayButton className="repair-transport-btn repair-transport-btn-primary" />
              )}
              <StopButton className="repair-transport-btn" />
              <SkipForwardButton className="repair-transport-btn" />
              <FastForwardButton className="repair-transport-btn" />
            </div>
          </div>

          <div className="repair-playback-info">
            <div className="repair-time-display">
              <span>
                {playbackAnimation.currentTime !== undefined 
                  ? formatTime(playbackAnimation.currentTime) 
                  : '0:00'}
              </span>
              {' / '}
              <span>
                {playlistData.duration !== undefined 
                  ? formatTime(playlistData.duration) 
                  : '0:00'}
              </span>
            </div>
            <div className="repair-playback-status">
              <span>{playbackAnimation.isPlaying ? 'Playing' : loading ? 'Loading...' : 'Stopped'}</span>
            </div>
          </div>
        </div>

        {/* Master Volume Control */}
        <div className="repair-master-volume">
          <h4><i className="fas fa-volume-up"></i> Master Volume</h4>
          <div className="repair-master-volume-control">
            <input
              type="range"
              className="repair-volume-slider"
              min="0"
              max="1"
              step="0.01"
              value={masterVolume}
              onChange={(e) => {
                const value = parseFloat(e.target.value);
                setMasterVolumeState(value);
                setMasterVolumeControl(value);
              }}
            />
            <span className="repair-volume-value">{Math.round(masterVolume * 100)}%</span>
          </div>
        </div>

        {/* Actions */}
        <div className="repair-actions">
          <button 
            className="repair-action-btn primary"
            onClick={handleOpenRepairDialog}
            disabled={isRepairing || !playlistData.isReady || !syncData.dubPath}
            title={!syncData.dubPath ? 'No dub file path available' : 'Apply repair via FFmpeg'}
          >
            <i className="fas fa-magic"></i> Apply Repair (FFmpeg)
          </button>
          <button 
            className="repair-action-btn success"
            onClick={handleExport}
            disabled={isExporting || !playlistData.isReady}
            title="Export mixed audio as WAV (preview)"
          >
            <i className="fas fa-download"></i> Export WAV Preview
          </button>
          <button className="repair-action-btn" onClick={onClose}>
            <i className="fas fa-times"></i> Close
          </button>
        </div>

        {/* Repair Status */}
        {(repairResult || repairError) && (
          <div className={`repair-status ${repairError ? 'error' : 'success'}`}>
            {repairError ? (
              <>
                <i className="fas fa-exclamation-triangle"></i>
                <span>Repair failed: {repairError}</span>
                <button onClick={() => setRepairError(null)} className="repair-status-close">
                  <i className="fas fa-times"></i>
                </button>
              </>
            ) : repairResult ? (
              <>
                <i className="fas fa-check-circle"></i>
                <span>
                  Repair completed! Output: {repairResult.output_file}
                  {repairResult.output_size && ` (${(repairResult.output_size / 1024 / 1024).toFixed(1)} MB)`}
                </span>
                <button onClick={() => setRepairResult(null)} className="repair-status-close">
                  <i className="fas fa-times"></i>
                </button>
              </>
            ) : null}
          </div>
        )}

        {/* Output Path Dialog */}
        {showOutputDialog && (
          <div className="repair-dialog-overlay" onClick={() => setShowOutputDialog(false)}>
            <div className="repair-dialog" onClick={(e) => e.stopPropagation()}>
              <div className="repair-dialog-header">
                <h4><i className="fas fa-cog"></i> FFmpeg Repair Settings</h4>
                <button onClick={() => setShowOutputDialog(false)} className="repair-dialog-close">
                  <i className="fas fa-times"></i>
                </button>
              </div>
              <div className="repair-dialog-content">
                <div className="repair-dialog-info">
                  <p>
                    <strong>Mode:</strong> {isPerChannelMode(syncData) ? 'Per-Channel (Componentized)' : 'Standard (Single Offset)'}
                  </p>
                  <p>
                    <strong>Source:</strong> {syncData.dubPath}
                  </p>
                  {isPerChannelMode(syncData) ? (
                    <p className="repair-dialog-hint">
                      <i className="fas fa-info-circle"></i>
                      Each channel will be adjusted based on its track position in the editor.
                    </p>
                  ) : (
                    <p className="repair-dialog-hint">
                      <i className="fas fa-info-circle"></i>
                      The dub track offset will be applied to the entire file.
                    </p>
                  )}
                </div>
                <div className="repair-dialog-field">
                  <label htmlFor="outputPath">Output Path:</label>
                  <input
                    type="text"
                    id="outputPath"
                    value={outputPath}
                    onChange={(e) => setOutputPath(e.target.value)}
                    placeholder="Leave empty for default (_repaired suffix)"
                  />
                </div>
                <div className="repair-dialog-field">
                  <label className="repair-dialog-checkbox">
                    <input
                      type="checkbox"
                      checked={keepDuration}
                      onChange={(e) => setKeepDuration(e.target.checked)}
                    />
                    Keep original duration (pad/trim to match)
                  </label>
                </div>
                {repairProgress && (
                  <div className="repair-dialog-progress">
                    <i className="fas fa-spinner fa-spin"></i> {repairProgress}
                  </div>
                )}
              </div>
              <div className="repair-dialog-actions">
                <button 
                  className="repair-dialog-btn cancel"
                  onClick={() => setShowOutputDialog(false)}
                  disabled={isRepairing}
                >
                  Cancel
                </button>
                <button 
                  className="repair-dialog-btn primary"
                  onClick={handleApplyRepair}
                  disabled={isRepairing}
                >
                  {isRepairing ? (
                    <>
                      <i className="fas fa-spinner fa-spin"></i> Repairing...
                    </>
                  ) : (
                    <>
                      <i className="fas fa-check"></i> Apply Repair
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

function formatOffset(offset: number, fps: number = 23.976): string {
  const sign = offset < 0 ? '-' : '+';
  const absSeconds = Math.abs(offset);
  const hours = Math.floor(absSeconds / 3600);
  const minutes = Math.floor((absSeconds % 3600) / 60);
  const secs = Math.floor(absSeconds % 60);
  const frames = Math.floor((absSeconds % 1) * fps);
  return `${sign}${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
}

export default RepairModal;
