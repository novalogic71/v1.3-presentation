import React, { useState, useEffect, useCallback } from 'react';
import { 
  Waveform,
  usePlaylistControls, 
  usePlaylistData,
  usePlaybackAnimation,
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
import { SyncData } from '../types';
import './QCModal.css';

interface QCModalProps {
  syncData: SyncData;
  isOpen: boolean;
  onClose: () => void;
  loading: boolean;
  error: Error | null;
  isCorrectedMode: boolean;
  onCorrectedModeChange: (corrected: boolean) => void;
}

const QCModal: React.FC<QCModalProps> = ({ 
  syncData, 
  isOpen, 
  onClose, 
  loading, 
  error,
  isCorrectedMode,
  onCorrectedModeChange
}) => {
  const { 
    play, 
    stop, 
    seekTo, 
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

  // Handle Before/After fix mode toggle with debouncing to prevent rate limits
  const handleToggleMode = useCallback((corrected: boolean) => {
    // Prevent rapid switching while loading
    if (loading) {
      return;
    }
    // Prevent switching if already in the requested mode
    if (isCorrectedMode === corrected) {
      return;
    }
    onCorrectedModeChange(corrected);
    // Stop playback when switching modes
    stop();
  }, [onCorrectedModeChange, stop, loading, isCorrectedMode]);

  // Handle Before Fix playback
  const handlePlayBefore = useCallback(() => {
    if (isCorrectedMode) {
      onCorrectedModeChange(false);
    }
    stop();
    setTimeout(() => {
      seekTo(0);
      play();
    }, 100);
  }, [isCorrectedMode, onCorrectedModeChange, stop, seekTo, play]);

  // Handle After Fix playback
  const handlePlayAfter = useCallback(() => {
    if (!isCorrectedMode) {
      onCorrectedModeChange(true);
    }
    stop();
    setTimeout(() => {
      seekTo(0);
      play();
    }, 100);
  }, [isCorrectedMode, onCorrectedModeChange, stop, seekTo, play]);

  if (!isOpen) return null;

  const offset = syncData.detectedOffset || 0;
  const confidence = syncData.confidence || 0;

  return (
    <div className="qc-modal-overlay" onClick={onClose}>
      <div className="qc-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="qc-header">
          <h3>
            <i className="fas fa-microscope"></i> Quality Control Review
          </h3>
          <button className="qc-close-btn" onClick={onClose}>
            <i className="fas fa-times"></i>
          </button>
        </div>

        {/* File Info */}
        <div className="qc-file-info">
          <div className="qc-file-pair">
            <div className="qc-file-item master-file">
              <label>Master File:</label>
              <span>{syncData.masterFile || 'No file selected'}</span>
            </div>
            <div className="qc-file-item dub-file">
              <label>Dub File:</label>
              <span>{syncData.dubFile || 'No file selected'}</span>
            </div>
          </div>
          <div className="qc-sync-info">
            <div className="qc-offset-display">
              <label>Detected Offset:</label>
              <span>{formatOffset(offset, syncData.frameRate || 23.976)}</span>
            </div>
            <div className="qc-confidence-display">
              <label>Confidence:</label>
              <span>{Math.round(confidence * 100)}%</span>
            </div>
          </div>
        </div>

        {/* Waveform Display with Integrated Track Controls */}
        <div className="qc-waveform-container">
          <div className="qc-waveform-header">
            <h4><i className="fas fa-chart-area"></i> Waveform Comparison</h4>
            <div className="qc-view-controls">
              <div className="qc-zoom-controls">
                <ZoomOutButton className="qc-zoom-btn" disabled={!playlistData.canZoomOut} />
                <ZoomInButton className="qc-zoom-btn" disabled={!playlistData.canZoomIn} />
              </div>
              <div className="qc-view-toggle">
                <button
                  className={`qc-toggle-btn ${!isCorrectedMode ? 'active' : ''}`}
                  onClick={() => handleToggleMode(false)}
                  disabled={loading}
                  title={loading ? 'Please wait for tracks to finish loading' : 'View before fix'}
                >
                  <i className="fas fa-exclamation-triangle"></i> Before Fix
                </button>
                <button
                  className={`qc-toggle-btn ${isCorrectedMode ? 'active' : ''}`}
                  onClick={() => handleToggleMode(true)}
                  disabled={loading}
                  title={loading ? 'Please wait for tracks to finish loading' : 'View after fix'}
                >
                  <i className="fas fa-check-circle"></i> After Fix
                </button>
              </div>
            </div>
          </div>

          <div className="qc-waveform-display">
            {loading && <div className="qc-loading">Loading waveforms...</div>}
            {error && (
              <div className="qc-error">
                <div className="qc-error-title">Error Loading Audio</div>
                <div className="qc-error-message">
                  {error.message.includes('Rate limit') || error.message.includes('429') ? (
                    <>
                      <p><strong>Rate limit exceeded.</strong> Please wait a moment and try again.</p>
                      <p className="qc-error-hint">The server is temporarily limiting requests. Wait a few seconds before switching modes or reloading.</p>
                    </>
                  ) : (
                    error.message
                  )}
                </div>
              </div>
            )}
            {!loading && !error && (
              <Waveform 
                renderTrackControls={(trackIndex: number) => {
                  const trackState = trackStates[trackIndex] || { volume: 0.8, muted: false, soloed: false, pan: 0 };
                  const volume = trackVolumes[trackIndex] ?? trackState.volume ?? 0.8;
                  const muted = trackMutes[trackIndex] ?? trackState.muted ?? false;
                  const soloed = trackSolos[trackIndex] ?? trackState.soloed ?? false;
                  const track = playlistData.tracks?.[trackIndex];
                  
                  // Master track is index 0, Dub tracks are index 1+
                  const isMasterTrack = trackIndex === 0;
                  
                  return (
                    <div className={`qc-track-controls-panel ${isMasterTrack ? 'master-track' : 'dub-track'}`}>
                      <div 
                        className={`qc-track-label ${isMasterTrack ? 'master-track' : 'dub-track'}`} 
                        title={track?.name || `Track ${trackIndex + 1}`}
                      >
                        {track?.name || `Track ${trackIndex + 1}`}
                      </div>
                      <div className="qc-track-controls-grid">
                        <div className="qc-track-buttons-row">
                          <button
                            className={`qc-track-btn qc-mute-btn ${muted ? 'active' : ''}`}
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
                            className={`qc-track-btn qc-solo-btn ${soloed ? 'active' : ''}`}
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
                        <div className="qc-track-control-group">
                          <div className="qc-track-slider-row">
                            <input
                              type="range"
                              className="qc-track-control-slider"
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
                            <span className="qc-track-control-value">{Math.round(volume * 100)}%</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                }}
              />
            )}
          </div>
        </div>

        {/* Transport Controls */}
        <div className="qc-transport-controls">
          <h4><i className="fas fa-play"></i> Transport Controls</h4>
          
          <div className="qc-transport-row">
            <div className="qc-transport-buttons">
              <RewindButton className="qc-transport-btn" />
              <SkipBackwardButton className="qc-transport-btn" />
              {playbackAnimation.isPlaying ? (
                <PauseButton className="qc-transport-btn qc-transport-btn-primary" />
              ) : (
                <PlayButton className="qc-transport-btn qc-transport-btn-primary" />
              )}
              <StopButton className="qc-transport-btn" />
              <SkipForwardButton className="qc-transport-btn" />
              <FastForwardButton className="qc-transport-btn" />
            </div>
            
            <div className="qc-mode-buttons">
              <button
                className={`qc-mode-btn primary ${!isCorrectedMode && playbackAnimation.isPlaying ? 'active' : ''}`}
                onClick={handlePlayBefore}
                disabled={loading}
                title="Play Before Fix (with offset problem)"
              >
                <i className="fas fa-exclamation-triangle"></i> Play Problem
              </button>
              <button
                className={`qc-mode-btn success ${isCorrectedMode && playbackAnimation.isPlaying ? 'active' : ''}`}
                onClick={handlePlayAfter}
                disabled={loading}
                title="Play After Fix (with offset correction)"
              >
                <i className="fas fa-check-circle"></i> Play Fixed
              </button>
            </div>
          </div>

          <div className="qc-playback-info">
            <div className="qc-time-display">
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
            <div className="qc-playback-status">
              <span>{playbackAnimation.isPlaying ? 'Playing' : loading ? 'Loading...' : 'Stopped'}</span>
            </div>
          </div>
        </div>

        {/* Master Volume Control */}
        <div className="qc-master-volume">
          <h4><i className="fas fa-volume-up"></i> Master Volume</h4>
          <div className="qc-master-volume-control">
            <input
              type="range"
              className="qc-volume-slider"
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
            <span className="qc-volume-value">{Math.round(masterVolume * 100)}%</span>
          </div>
        </div>

        {/* Actions */}
        <div className="qc-actions">
          <button className="qc-action-btn success">
            <i className="fas fa-thumbs-up"></i> Approve Sync
          </button>
          <button className="qc-action-btn warning">
            <i className="fas fa-flag"></i> Flag for Review
          </button>
          <button className="qc-action-btn danger">
            <i className="fas fa-thumbs-down"></i> Reject Sync
          </button>
          <button className="qc-action-btn">
            <i className="fas fa-download"></i> Export Results
          </button>
        </div>
      </div>
    </div>
  );
};

function formatOffset(offset: number, fps: number = 23.976): string {
  const sign = offset < 0 ? '-' : '';
  const absSeconds = Math.abs(offset);
  const hours = Math.floor(absSeconds / 3600);
  const minutes = Math.floor((absSeconds % 3600) / 60);
  const secs = Math.floor(absSeconds % 60);
  const frames = Math.floor((absSeconds % 1) * fps);
  return `${sign}${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
}


export default QCModal;
