/**
 * Quality Control Interface for Audio Sync Analysis
 * Dedicated interface for reviewing and playing back sync analysis results
 */

class QCInterface {
    constructor() {
        this.audioEngine = null;
        this.qcPlayer = null;
        this.nativePlayer = null;
        this.multiTrackPlayer = null;
        // NOTE: WaveSurfer experiments removed; QC uses QCPlayer + canvas again.
        this.wavesurferPlayer = null;
        this.currentData = null;
        this.isVisible = false;
        this.playheadUpdateInterval = null;
        this.canvasWidth = 0;
        this.totalDuration = 0;
        this.lastSeekTime = 0;
        
        // Multi-track view state
        this.viewMode = localStorage.getItem('qc-view-mode') || 'simple'; // 'simple' or 'multitrack'
        this.applyOffset = localStorage.getItem('qc-apply-offset') !== 'false'; // Default true
        this.trackWaveforms = []; // For componentized analyses: [{name, type, waveformData, color}, ...]
        this.playheadAnimationId = null; // For requestAnimationFrame
        
        // Playback progress for waveform highlight (0-1)
        this.currentProgress = 0;
        this.progressAnimationId = null;

        this.initializeModal();
        this.setupEventListeners();
    }

    initializeModal() {
        // Create modal HTML structure
        const modalHTML = `
            <div id="qc-modal" class="qc-modal" style="display: none;">
                <div class="qc-modal-content">
                    <div class="qc-header">
                        <h3><i class="fas fa-microscope"></i> Quality Control Review</h3>
                        <button class="qc-close-btn" id="qc-close-btn">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                    
                    <div class="qc-file-info">
                        <div class="qc-file-pair">
                            <div class="qc-file-item master-file">
                                <label>Master File:</label>
                                <span id="qc-master-file">No file selected</span>
                            </div>
                            <div class="qc-file-item dub-file">
                                <label>Dub File:</label>
                                <span id="qc-dub-file">No file selected</span>
                            </div>
                        </div>
                        <div class="qc-sync-info">
                            <div class="qc-offset-display">
                                <label>Detected Offset:</label>
                                <span id="qc-offset-value">0.000s</span>
                            </div>
                            <div class="qc-confidence-display">
                                <label>Confidence:</label>
                                <span id="qc-confidence-value">0%</span>
                            </div>
                        </div>
                    </div>

                    <div class="qc-waveform-container">
                        <div class="qc-waveform-header">
                            <h4><i class="fas fa-chart-area"></i> Waveform Comparison</h4>
                            <div class="qc-view-controls">
                                <!-- View Mode Toggle: Simple vs Multi-track -->
                                <div class="qc-mode-toggle">
                                    <button class="qc-mode-btn ${this.viewMode === 'simple' ? 'active' : ''}" data-mode="simple" title="Simple before/after split view">
                                        <i class="fas fa-columns"></i> Simple
                                    </button>
                                    <button class="qc-mode-btn ${this.viewMode === 'multitrack' ? 'active' : ''}" data-mode="multitrack" title="Multi-track DAW-style view">
                                        <i class="fas fa-bars"></i> Multi-track
                                    </button>
                                </div>
                                <!-- Before/After toggle (Simple mode) -->
                                <div class="qc-view-toggle" id="qc-simple-toggle" style="${this.viewMode === 'multitrack' ? 'display:none;' : ''}">
                                    <button class="qc-toggle-btn active" data-view="before" title="Show waveforms with detected sync offset">
                                        <i class="fas fa-exclamation-triangle"></i> Before Fix
                                    </button>
                                    <button class="qc-toggle-btn" data-view="after" title="Show waveforms aligned and synchronized">
                                        <i class="fas fa-check-circle"></i> After Fix
                                    </button>
                                </div>
                                <!-- Apply Offset toggle (Multi-track mode) -->
                                <div class="qc-offset-toggle" id="qc-offset-toggle" style="${this.viewMode === 'simple' ? 'display:none;' : ''}">
                                    <label class="qc-offset-switch">
                                        <input type="checkbox" id="qc-apply-offset-checkbox" ${this.applyOffset ? 'checked' : ''}>
                                        <span class="qc-offset-slider-toggle"></span>
                                        <span class="qc-offset-label">Apply Offset</span>
                                    </label>
                                </div>
                            </div>
                        </div>
                        
                        <div class="qc-waveform-display" style="position:relative;">
                            <canvas id="qc-waveform-canvas" width="900" height="320"></canvas>
                            <div class="qc-waveform-overlay" style="position:absolute;left:0;top:0;right:0;bottom:0;z-index:5;pointer-events:none;">
                                <div class="qc-scene-bands" id="qc-scene-bands" style="position:absolute;left:0;top:0;right:0;bottom:0;display:flex;gap:2px;z-index:6;"></div>
                                <div class="qc-drift-markers" id="qc-drift-markers" style="position:absolute;left:0;bottom:0;right:0;height:100%;z-index:6;"></div>
                            </div>
                        </div>

                        <!-- Drift Timeline Legend and Guide -->
                        <div class="qc-timeline-info" id="qc-timeline-info" style="display: none;">
                            <div class="qc-drift-legend">
                                <div class="legend-header">
                                    <span><i class="fas fa-timeline"></i> Timeline: <span id="qc-drift-count">0</span> drift points</span>
                                </div>
                            </div>
                            <div class="qc-severity-guide">
                                <div class="guide-title">🎯 Sync Quality Guide</div>
                                <div class="severity-items">
                                    <div class="severity-item">
                                        <div class="severity-marker severity-insync"></div>
                                        <span>✅ In Sync (≤30ms)</span>
                                    </div>
                                    <div class="severity-item">
                                        <div class="severity-marker severity-minor"></div>
                                        <span>⚠️ Minor Drift (≤100ms)</span>
                                    </div>
                                    <div class="severity-item">
                                        <div class="severity-marker severity-issue"></div>
                                        <span>🟠 Sync Issue (≤250ms)</span>
                                    </div>
                                    <div class="severity-item">
                                        <div class="severity-marker severity-major"></div>
                                        <span>🔴 Major Problem (>250ms)</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Multi-Track Mixer Panel -->
                    <div class="qc-track-mixer" id="qc-track-mixer" style="display: none;">
                        <div class="qc-track-mixer-header">
                            <h4><i class="fas fa-sliders-h"></i> Track Mixer</h4>
                            <span class="qc-track-count" id="qc-track-count">0 tracks</span>
                        </div>
                        <div class="qc-track-list" id="qc-track-list">
                            <div class="qc-track-list-empty">No tracks loaded</div>
                        </div>
                    </div>

                    <div class="qc-audio-controls">
                        <div class="qc-playback-section">
                            <h4><i class="fas fa-play"></i> Audio Playback</h4>
                            
                            <div class="qc-play-buttons">
                                <button class="qc-play-btn primary" id="qc-play-before" title="Play with detected sync problem (Before Fix)">
                                    <i class="fas fa-exclamation-triangle"></i> Play Problem
                                </button>
                                <button class="qc-play-btn success" id="qc-play-after" title="Play with sync correction applied (After Fix)">
                                    <i class="fas fa-check-circle"></i> Play Fixed
                                </button>
                                <button class="qc-play-btn" id="qc-stop-playback">
                                    <i class="fas fa-stop"></i> Stop
                                </button>
                            </div>
                            
                            <div class="qc-playback-info">
                                <div class="qc-time-display">
                                    <span id="qc-current-time">0:00</span> / <span id="qc-total-time">0:00</span>
                                </div>
                                <div class="qc-timeline-scrubber">
                                    <input type="range" id="qc-timeline-slider" min="0" max="1000" value="0" 
                                           style="width:100%;cursor:pointer;accent-color:#60a5fa;">
                                </div>
                                <div class="qc-playback-status">
                                    <span id="qc-playback-status">Ready</span>
                                </div>
                            </div>
                        </div>

                        <div class="qc-volume-controls">
                            <h4><i class="fas fa-volume-up"></i> Volume Controls</h4>
                            
                            <div class="qc-volume-grid">
                                <div class="qc-volume-item">
                                    <label>Master</label>
                                    <input type="range" class="qc-volume-slider" data-track="master" 
                                           min="0" max="1" step="0.01" value="0.8">
                                    <span class="qc-volume-value">80%</span>
                                </div>
                                
                                <div class="qc-volume-item">
                                    <label>Dub</label>
                                    <input type="range" class="qc-volume-slider" data-track="dub" 
                                           min="0" max="1" step="0.01" value="0.8">
                                    <span class="qc-volume-value">80%</span>
                                </div>
                                
                                <div class="qc-volume-item">
                                    <label>Balance</label>
                                    <input type="range" class="qc-balance-slider" 
                                           min="-1" max="1" step="0.01" value="0">
                                    <span class="qc-balance-value">Center</span>
                                </div>
                            </div>
                            
                            <div class="qc-mute-controls">
                                <label class="qc-mute-label">
                                    <input type="checkbox" class="qc-mute-toggle" data-track="master">
                                    <i class="fas fa-volume-mute"></i> Mute Master
                                </label>
                                <label class="qc-mute-label">
                                    <input type="checkbox" class="qc-mute-toggle" data-track="dub">
                                    <i class="fas fa-volume-mute"></i> Mute Dub
                                </label>
                            </div>
                        </div>
                    </div>

                    <div class="qc-actions">
                        <button class="qc-action-btn success" id="qc-approve-btn">
                            <i class="fas fa-thumbs-up"></i> Approve Sync
                        </button>
                        <button class="qc-action-btn warning" id="qc-flag-btn">
                            <i class="fas fa-flag"></i> Flag for Review
                        </button>
                        <button class="qc-action-btn danger" id="qc-reject-btn">
                            <i class="fas fa-thumbs-down"></i> Reject Sync
                        </button>
                        <button class="qc-action-btn" id="qc-export-btn">
                            <i class="fas fa-download"></i> Export Results
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Add modal to page
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // Initialize audio engine for QC interface
        this.initializeAudioEngine();
    }

    initializeAudioEngine() {
        try {
            // Core waveform extraction (canvas rendering)
            this.audioEngine = new CoreAudioEngine();
            this.audioEngine.onProgress = (message, percentage) => {
                this.updateStatus(`${message} (${percentage}%)`);
            };
            this.audioEngine.onError = (error) => {
                console.error('QC Audio Engine Error:', error);
                this.updateStatus(`Audio Error: ${error}`, 'error');
            };
            this.audioEngine.onAudioLoaded = () => {
                this.updateWaveform();
                this.renderDriftMarkers();
                this.renderSceneBands();
            };

            // Primary playback: QCPlayer (simple, reliable)
            if (typeof QCPlayer !== 'undefined') {
                this.qcPlayer = new QCPlayer();
                this.qcPlayer.onTimeUpdate = (info) => this.updatePlayheadFromPlayer(info);
                this.qcPlayer.onStatusChange = (msg, type) => this.updateStatus(msg, type);
            }

            // Optional fallback players (kept for other modes/features in this file)
            if (typeof NativeAudioPlayer !== 'undefined') {
                this.nativePlayer = new NativeAudioPlayer();
                this.nativePlayer.onTimeUpdate = (info) => this.updatePlayheadFromNativePlayer(info);
                this.nativePlayer.onStatusChange = (msg, type) => this.updateStatus(msg, type);
            }

            if (typeof MultiTrackPlayer !== 'undefined') {
                this.multiTrackPlayer = new MultiTrackPlayer({ container: document.body });
                this.multiTrackPlayer.onTimeUpdate = (info) => this.updatePlayheadFromMultiTrackPlayer(info);
                this.multiTrackPlayer.onTrackLoaded = () => this.updateTrackMixerUI();
            }

            console.log('QC Interface: Audio engine initialized (QCPlayer + canvas)');
        } catch (error) {
            console.error('Failed to initialize QC audio engine:', error);
            this.updateStatus('Audio engine initialization failed', 'error');
        }
    }
    
    /**
     * Update playhead from WaveSurfer
     */
    updatePlayheadFromWaveSurfer(info) {
        const duration = info.duration || this.getDurationFromTracks();
        if (duration <= 0) return;
        
        // Update progress ratio for overlay
        this.currentProgress = info.currentTime / duration;
        
        // Update the timeline slider
        const slider = document.getElementById('qc-timeline-slider');
        if (slider && !this.isSeeking) {
            slider.value = (info.currentTime / duration) * 1000;
        }
        
        // Update time display
        const currentTimeEl = document.getElementById('qc-current-time');
        const totalTimeEl = document.getElementById('qc-total-time');
        if (currentTimeEl) currentTimeEl.textContent = this.formatTime(info.currentTime);
        if (totalTimeEl) totalTimeEl.textContent = this.formatTime(duration);
        
        // Update playback status
        const statusEl = document.querySelector('.qc-playback-status');
        if (statusEl) {
            statusEl.textContent = info.isPlaying ? 'Playing' : 'Stopped';
        }
    }
    
    /**
     * Update UI after WaveSurfer is ready
     */
    updateWaveformFromWaveSurfer() {
        // Update time display
        const duration = this.wavesurferPlayer?.getDuration() || 0;
        const totalTimeEl = document.getElementById('qc-total-time');
        if (totalTimeEl && duration > 0) {
            totalTimeEl.textContent = this.formatTime(duration);
        }
        
        // Show WaveSurfer container, hide canvas
        const wsContainer = document.getElementById('qc-wavesurfer-container');
        const canvas = document.getElementById('qc-waveform-canvas');
        if (wsContainer) wsContainer.style.display = 'block';
        if (canvas) canvas.style.display = 'none';
    }
    
    /**
     * Update timeline slider from NativeAudioPlayer
     */
    updatePlayheadFromNativePlayer(info) {
        const duration = info.duration || this.getDurationFromTracks();
        if (duration <= 0) return;
        
        // Update progress ratio for waveform highlight
        this.currentProgress = info.currentTime / duration;
        
        // Update the timeline slider (native range input - no jumping!)
        const slider = document.getElementById('qc-timeline-slider');
        if (slider && !this.isSeeking) {
            slider.value = (info.currentTime / duration) * 1000;
        }
        
        // Update time display
        const currentTimeEl = document.getElementById('qc-current-time');
        const totalTimeEl = document.getElementById('qc-total-time');
        if (currentTimeEl) currentTimeEl.textContent = this.formatTime(info.currentTime);
        if (totalTimeEl) totalTimeEl.textContent = this.formatTime(duration);
        
        // Update waveform progress overlay
        this.updateProgressOverlay();
    }
    
    /**
     * Update timeline slider from MultiTrackPlayer time info
     */
    updatePlayheadFromMultiTrackPlayer(info) {
        const duration = info.duration || this.getDurationFromTracks();
        if (duration <= 0) return;
        
        // Update progress ratio for waveform highlight
        this.currentProgress = info.masterTime / duration;
        
        // Update the timeline slider (native range input - no jumping!)
        const slider = document.getElementById('qc-timeline-slider');
        if (slider && !this.isSeeking) {
            slider.value = (info.masterTime / duration) * 1000;
        }
        
        // Update time display
        const currentTimeEl = document.getElementById('qc-current-time');
        const totalTimeEl = document.getElementById('qc-total-time');
        if (currentTimeEl) currentTimeEl.textContent = this.formatTime(info.masterTime);
        if (totalTimeEl) totalTimeEl.textContent = this.formatTime(duration);
        
        // Update playing indicators in track mixer
        this.updateTrackPlayingIndicators(info.tracks);
        
        // Update waveform progress overlay
        this.updateProgressOverlay();
    }
    
    /**
     * Get total duration from all loaded tracks
     */
    getDurationFromTracks() {
        if (this.trackWaveforms.length > 0) {
            return Math.max(...this.trackWaveforms.map(t => t.waveformData?.duration || 0));
        }
        return Math.max(
            this.audioEngine?.masterWaveformData?.duration || 0,
            this.audioEngine?.dubWaveformData?.duration || 0
        );
    }
    
    /**
     * Update track mixer UI to reflect current tracks
     */
    updateTrackMixerUI() {
        const container = document.getElementById('qc-track-list');
        const countEl = document.getElementById('qc-track-count');
        const mixerPanel = document.getElementById('qc-track-mixer');
        
        if (!container) return;
        
        // Get tracks from MultiTrackPlayer if available, otherwise from trackWaveforms
        let tracks = [];
        if (this.multiTrackPlayer) {
            tracks = this.multiTrackPlayer.getTracks();
        }
        if (tracks.length === 0 && this.trackWaveforms.length > 0) {
            // Create pseudo-track info from waveform data
            tracks = this.trackWaveforms.map((t, i) => ({
                id: `track-${i}`,
                name: t.name,
                type: t.type,
                color: t.color,
                offset: t.offset || 0,
                volume: 1.0,
                muted: false,
                solo: false,
                duration: t.waveformData?.duration || 0
            }));
        }
        
        // Update count
        if (countEl) {
            countEl.textContent = `${tracks.length} track${tracks.length !== 1 ? 's' : ''}`;
        }
        
        // Show/hide mixer panel based on track count
        if (mixerPanel) {
            mixerPanel.style.display = tracks.length > 0 ? '' : 'none';
        }
        
        if (tracks.length === 0) {
            container.innerHTML = '<div class="qc-track-list-empty">No tracks loaded</div>';
            return;
        }
        
        // Build track list HTML
        container.innerHTML = tracks.map(track => {
            const isMaster = track.type === 'master';
            const offsetDisplay = track.offset ? 
                (track.offset > 0 ? `+${track.offset.toFixed(3)}s` : `${track.offset.toFixed(3)}s`) : 
                '0.000s';
            const offsetClass = track.offset > 0 ? 'positive' : track.offset < 0 ? 'negative' : '';
            
            return `
                <div class="qc-track-item ${isMaster ? 'master' : ''}" 
                     data-track-id="${track.id}" 
                     style="--track-color: ${track.color || (isMaster ? '#60a5fa' : '#4ade80')}">
                    <div class="qc-track-indicator" id="track-indicator-${track.id}"></div>
                    <span class="qc-track-name" title="${track.name}">${track.name}</span>
                    <div class="qc-track-volume">
                        <input type="range" class="qc-track-volume-slider" 
                               data-track-id="${track.id}"
                               min="0" max="1" step="0.01" value="${track.volume || 1}"
                               style="--track-color: ${track.color || '#4ade80'}">
                        <span class="qc-track-volume-value">${Math.round((track.volume || 1) * 100)}%</span>
                    </div>
                    <button class="qc-track-btn mute-btn ${track.muted ? 'active' : ''}" 
                            data-track-id="${track.id}" data-action="mute" title="Mute">M</button>
                    <button class="qc-track-btn solo-btn ${track.solo ? 'active' : ''}" 
                            data-track-id="${track.id}" data-action="solo" title="Solo">S</button>
                    <span class="qc-track-offset ${offsetClass}">${offsetDisplay}</span>
                </div>
            `;
        }).join('');
        
        // Add event listeners for track controls
        this.setupTrackControlListeners();
    }
    
    /**
     * Setup event listeners for track mixer controls
     */
    setupTrackControlListeners() {
        const container = document.getElementById('qc-track-list');
        if (!container) return;
        
        // Volume sliders
        container.querySelectorAll('.qc-track-volume-slider').forEach(slider => {
            slider.addEventListener('input', (e) => {
                const trackId = e.target.dataset.trackId;
                const value = parseFloat(e.target.value);
                
                if (this.multiTrackPlayer) {
                    this.multiTrackPlayer.setTrackVolume(trackId, value);
                }
                
                // Update display
                const valueEl = e.target.nextElementSibling;
                if (valueEl) {
                    valueEl.textContent = `${Math.round(value * 100)}%`;
                }
            });
        });
        
        // Mute/Solo buttons
        container.querySelectorAll('.qc-track-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const trackId = e.target.dataset.trackId;
                const action = e.target.dataset.action;
                
                if (action === 'mute') {
                    const muted = !e.target.classList.contains('active');
                    e.target.classList.toggle('active', muted);
                    if (this.multiTrackPlayer) {
                        this.multiTrackPlayer.setTrackMuted(trackId, muted);
                    }
                } else if (action === 'solo') {
                    const solo = !e.target.classList.contains('active');
                    e.target.classList.toggle('active', solo);
                    if (this.multiTrackPlayer) {
                        this.multiTrackPlayer.setTrackSolo(trackId, solo);
                    }
                }
            });
        });
    }
    
    /**
     * Update playing indicators in track mixer
     */
    updateTrackPlayingIndicators(trackInfos) {
        if (!trackInfos) return;
        
        trackInfos.forEach(info => {
            const indicator = document.getElementById(`track-indicator-${info.id}`);
            if (indicator) {
                indicator.classList.toggle('playing', this.multiTrackPlayer?.isPlaying);
            }
        });
    }
    
    updatePlayheadFromPlayer(info) {
        // Get duration from all available sources
        let duration = Math.max(info.masterDuration || 0, info.dubDuration || 0);
        if (this.trackWaveforms.length > 0) {
            duration = Math.max(duration, ...this.trackWaveforms.map(t => t.waveformData?.duration || 0));
        }
        if (duration <= 0) return;
        
        // Update timeline slider (native range input - no jumping!)
        const slider = document.getElementById('qc-timeline-slider');
        if (slider && !this.isSeeking) {
            slider.value = (info.masterTime / duration) * 1000;
        }
        
        // Update time display
        const currentTimeEl = document.getElementById('qc-current-time');
        const totalTimeEl = document.getElementById('qc-total-time');
        if (currentTimeEl) currentTimeEl.textContent = this.formatTime(info.masterTime);
        if (totalTimeEl) totalTimeEl.textContent = this.formatTime(duration);
    }

    /**
     * Start smooth playhead animation using requestAnimationFrame
     */
    startPlayheadAnimation() {
        this.stopPlayheadAnimation();
        
        const animate = () => {
            // Check which player is playing
            const nativePlaying = this.nativePlayer?.isPlaying;
            const multiTrackPlaying = this.multiTrackPlayer?.isPlaying;
            const qcPlaying = this.qcPlayer?.isPlaying;
            
            if (!nativePlaying && !multiTrackPlaying && !qcPlaying) {
                this.playheadAnimationId = null;
                return;
            }
            
            // Use NativeAudioPlayer (preferred)
            if (nativePlaying && this.nativePlayer) {
                const status = this.nativePlayer.getStatus();
                this.updatePlayheadFromNativePlayer({
                    currentTime: status.currentTime,
                    duration: status.duration,
                    isPlaying: status.isPlaying
                });
            } else if (multiTrackPlaying && this.multiTrackPlayer) {
                const status = this.multiTrackPlayer.getStatus();
                this.updatePlayheadFromMultiTrackPlayer({
                    masterTime: status.masterTime,
                    duration: status.duration,
                    tracks: status.tracks
                });
            } else if (qcPlaying && this.qcPlayer) {
                const status = this.qcPlayer.getStatus?.();
                if (status) {
                    this.updatePlayheadFromPlayer({
                        masterTime: status.masterTime,
                        dubTime: status.dubTime,
                        masterDuration: status.masterDuration,
                        dubDuration: status.dubDuration
                    });
                }
            }
            
            this.playheadAnimationId = requestAnimationFrame(animate);
        };
        
        this.playheadAnimationId = requestAnimationFrame(animate);
    }

    /**
     * Stop playhead animation
     */
    stopPlayheadAnimation() {
        if (this.playheadAnimationId) {
            cancelAnimationFrame(this.playheadAnimationId);
            this.playheadAnimationId = null;
        }
    }
    
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * Set the view mode (simple or multitrack)
     */
    setViewMode(mode) {
        this.viewMode = mode;
        localStorage.setItem('qc-view-mode', mode);

        // Update button states
        document.querySelectorAll('.qc-mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        // Show/hide appropriate controls
        const simpleToggle = document.getElementById('qc-simple-toggle');
        const offsetToggle = document.getElementById('qc-offset-toggle');
        const trackMixer = document.getElementById('qc-track-mixer');
        
        if (simpleToggle) simpleToggle.style.display = mode === 'simple' ? '' : 'none';
        if (offsetToggle) offsetToggle.style.display = mode === 'multitrack' ? '' : 'none';
        if (trackMixer) trackMixer.style.display = (mode === 'multitrack' && this.trackWaveforms.length > 0) ? '' : 'none';

        // Resize canvas for multi-track mode (taller)
        const canvas = document.getElementById('qc-waveform-canvas');
        if (canvas) {
            const trackCount = this.getTrackCount();
            const baseHeight = mode === 'multitrack' ? Math.max(300, trackCount * 80 + 40) : 300;
            canvas.height = baseHeight;
            canvas.style.height = `${baseHeight}px`;
        }

        console.log(`QC View Mode changed to: ${mode}`);
        this.updateWaveform();
        
        // Update track mixer UI when switching to multi-track mode
        if (mode === 'multitrack') {
            this.updateTrackMixerUI();
        }
    }

    /**
     * Get the number of tracks to display
     */
    getTrackCount() {
        // If we have componentized waveforms, use that count
        if (this.trackWaveforms.length > 0) {
            return this.trackWaveforms.length;
        }
        // Default: master + dub = 2 tracks
        return 2;
    }

    setupEventListeners() {
        // Close button
        document.addEventListener('click', (e) => {
            if (e.target.closest('#qc-close-btn')) {
                this.close();
            }
        });

        // Play buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('#qc-play-before')) {
                this.playComparison(false);
            } else if (e.target.closest('#qc-play-after')) {
                this.playComparison(true);
            } else if (e.target.closest('#qc-stop-playback')) {
                this.stopPlayback();
            }
        });

        // View toggle buttons (Before/After in Simple mode) — affects CANVAS view only
        document.addEventListener('click', (e) => {
            const toggleBtn = e.target.closest('.qc-toggle-btn');
            if (toggleBtn) {
                document.querySelectorAll('.qc-toggle-btn').forEach(btn => btn.classList.remove('active'));
                toggleBtn.classList.add('active');
                this.updateWaveform();
            }
        });

        // View Mode toggle (Simple vs Multi-track)
        document.addEventListener('click', (e) => {
            const modeBtn = e.target.closest('.qc-mode-btn');
            if (modeBtn) {
                const mode = modeBtn.dataset.mode;
                if (mode && mode !== this.viewMode) {
                    this.setViewMode(mode);
                }
            }
        });

        // Apply Offset checkbox (Multi-track mode)
        document.addEventListener('change', (e) => {
            if (e.target.id === 'qc-apply-offset-checkbox') {
                this.applyOffset = e.target.checked;
                localStorage.setItem('qc-apply-offset', this.applyOffset);
                this.updateWaveform();
            }
        });

        // Volume controls (QCPlayer + fallbacks)
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('qc-volume-slider')) {
                const track = e.target.dataset.track;
                const value = parseFloat(e.target.value);
                console.log(`[QC Volume] track=${track}, value=${value}, qcPlayer=${!!this.qcPlayer}, nativePlayer=${!!this.nativePlayer}`);

                if (this.qcPlayer) {
                    console.log('[QC Volume] Calling qcPlayer method...');
                    if (track === 'master') this.qcPlayer.setMasterVolume(value);
                    if (track === 'dub') this.qcPlayer.setDubVolume(value);
                } else {
                    console.warn('[QC Volume] qcPlayer not available!');
                }
                if (this.nativePlayer) this.nativePlayer.setVolume(track, value);
                if (this.multiTrackPlayer) this.multiTrackPlayer.setTrackVolume(track, value);

                // Update display
                const valueSpan = e.target.nextElementSibling;
                if (valueSpan) {
                    valueSpan.textContent = Math.round(value * 100) + '%';
                }
            } else if (e.target.classList.contains('qc-balance-slider')) {
                const value = parseFloat(e.target.value);
                this.audioEngine?.setBalance(value);
                const label = value < -0.1 ? 'Left' : value > 0.1 ? 'Right' : 'Center';
                const valueSpan = e.target.nextElementSibling;
                if (valueSpan) {
                    valueSpan.textContent = label;
                }
            }
        });

        // Mute toggles (QCPlayer + fallbacks)
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('qc-mute-toggle')) {
                const track = e.target.dataset.track;
                const muted = e.target.checked;
                console.log(`[QC Mute] track=${track}, muted=${muted}, qcPlayer=${!!this.qcPlayer}`);

                if (this.qcPlayer) {
                    console.log('[QC Mute] Calling qcPlayer method...');
                    if (track === 'master') this.qcPlayer.setMasterMuted(muted);
                    if (track === 'dub') this.qcPlayer.setDubMuted(muted);
                } else {
                    console.warn('[QC Mute] qcPlayer not available!');
                }
                if (this.nativePlayer) this.nativePlayer.setMuted(track, muted);
                if (this.multiTrackPlayer) this.multiTrackPlayer.setTrackMuted(track, muted);
                
                // Visual feedback
                const label = e.target.closest('.qc-mute-label');
                if (label) {
                    label.classList.toggle('active', muted);
                }
            }
        });

        // Timeline slider (native seek - no jumping!)
        this.isSeeking = false;
        document.addEventListener('input', (e) => {
            if (e.target.id === 'qc-timeline-slider') {
                this.isSeeking = true;
                const slider = e.target;
                const duration = this.qcPlayer?.getDuration?.() || this.nativePlayer?.getDuration() || this.getDurationFromTracks() || 0;
                if (Number.isFinite(duration) && duration > 0) {
                    const seekTime = (slider.value / 1000) * duration;
                    if (Number.isFinite(seekTime)) {
                        document.getElementById('qc-current-time').textContent = this.formatTime(seekTime);
                    }
                }
            }
        });
        
        document.addEventListener('change', (e) => {
            if (e.target.id === 'qc-timeline-slider') {
                const slider = e.target;
                const duration = this.qcPlayer?.getDuration?.() || this.nativePlayer?.getDuration() || this.getDurationFromTracks() || 0;
                if (Number.isFinite(duration) && duration > 0) {
                    const seekTime = (slider.value / 1000) * duration;
                    if (Number.isFinite(seekTime)) {
                        this.lastSeekTime = seekTime;
                        // Seek on all available players
                        if (this.qcPlayer) this.qcPlayer.seek(seekTime);
                        if (this.nativePlayer) {
                            this.nativePlayer.seek(seekTime);
                        }
                        if (this.multiTrackPlayer) this.multiTrackPlayer.seek(seekTime);
                    }
                }
                this.isSeeking = false;
            }
        });

        // QC Action buttons
        document.addEventListener('click', (e) => {
            if (e.target.closest('#qc-approve-btn')) {
                this.approveSync();
            } else if (e.target.closest('#qc-flag-btn')) {
                this.flagForReview();
            } else if (e.target.closest('#qc-reject-btn')) {
                this.rejectSync();
            } else if (e.target.closest('#qc-export-btn')) {
                this.exportResults();
            }
        });

        // Close modal on outside click
        document.addEventListener('click', (e) => {
            if (e.target.id === 'qc-modal') {
                this.close();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (!this.isVisible) return;

            switch (e.code) {
                case 'Space':
                    e.preventDefault();
                    this.togglePlayback();
                    break;
                case 'Escape':
                    this.close();
                    break;
                case 'KeyB':
                    this.playComparison(false);
                    break;
                case 'KeyA':
                    this.playComparison(true);
                    break;
            }
        });

        // Click-to-seek on waveform
        document.addEventListener('click', (e) => {
            // Check if click is in QC waveform area
            const waveformDisplay = e.target.closest('.qc-waveform-display');
            const waveformOverlay = e.target.closest('.qc-waveform-overlay');
            
            if (!waveformDisplay && !waveformOverlay) return;
            if (!this.isVisible) return;

            const canvas = document.getElementById('qc-waveform-canvas');
            if (!canvas) return;

            const rect = canvas.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            
            // In multi-track mode, account for label width
            let effectiveClickX = clickX;
            let effectiveWidth = rect.width;
            
            if (this.viewMode === 'multitrack') {
                const labelWidth = 80; // Must match drawMultiTrackView
                // Ignore clicks in label area
                if (clickX < labelWidth) {
                    console.log('[QC Seek] Click in label area, ignoring');
                    return;
                }
                effectiveClickX = clickX - labelWidth;
                effectiveWidth = rect.width - labelWidth;
            }
            
            const progress = Math.max(0, Math.min(1, effectiveClickX / effectiveWidth));

            // Get duration from all available sources
            let totalDuration = 0;
            if (this.trackWaveforms.length > 0) {
                totalDuration = Math.max(...this.trackWaveforms.map(t => t.waveformData?.duration || 0));
            } else {
                totalDuration = Math.max(
                    this.audioEngine?.masterWaveformData?.duration || 0,
                    this.audioEngine?.dubWaveformData?.duration || 0,
                    this.audioEngine?.getDuration?.() || 0
                );
            }

            console.log('[QC Seek] clickX:', clickX, 'effectiveClickX:', effectiveClickX, 'progress:', progress, 'totalDuration:', totalDuration);

            if (totalDuration > 0) {
                const seekTime = progress * totalDuration;
                console.log('[QC Seek] Seeking to:', seekTime);
                this.seekTo(seekTime);
            } else {
                console.log('[QC Seek] No duration available');
            }
        });
    }

    async open(syncData) {
        console.log('QC Interface opening with data:', syncData);
        this.currentData = syncData;
        this.isVisible = true;
        this.trackWaveforms = []; // Reset tracks
        
        // Show modal immediately
        document.getElementById('qc-modal').style.display = 'flex';
        this.updateStatus('Opening QC Interface...');
        
        // Update UI with sync data
        this.updateFileInfo(syncData);
        
        // Check if this is a componentized analysis with multiple components
        const components = syncData.components || syncData.componentResults || [];
        const isComponentized = components.length > 0;
        
        console.log('QC Interface: isComponentized:', isComponentized, 'components:', components.length);
        
        // Try to load pre-generated waveforms first (fast), then fall back to audio loading
        const analysisId = syncData.analysisId || syncData.analysis_id;
        if (analysisId) {
            const loaded = await this.loadPreGeneratedWaveforms(analysisId);
            if (loaded) {
                console.log('QC Interface: Using pre-generated waveforms');
                this.updateWaveform();
            } else if (isComponentized) {
                console.log('QC Interface: Loading componentized audio files');
                await this.loadComponentizedAudioFiles(syncData, components);
            } else {
                console.log('QC Interface: Falling back to audio file loading');
                this.loadAudioFilesAsync(syncData);
            }
        } else if (isComponentized) {
            await this.loadComponentizedAudioFiles(syncData, components);
        } else {
            // No analysis ID, load audio files directly
            this.loadAudioFilesAsync(syncData);
        }
        
        // Auto-switch to multi-track mode if we have more than 2 tracks
        if (this.trackWaveforms.length > 2) {
            this.setViewMode('multitrack');
        }
        
        console.log('QC Interface modal opened with', this.trackWaveforms.length, 'tracks');
    }

    /**
     * Load audio files for componentized analysis with multiple tracks
     * Loads waveforms AND audio in parallel for fast load times
     */
    async loadComponentizedAudioFiles(syncData, components) {
        const startTime = performance.now();
        this.updateStatus('Loading componentized audio tracks...');
        this.trackWaveforms = [];
        
        // Assign colors - blue for master, greens for components
        const componentColors = ['#4ade80', '#22c55e', '#86efac', '#34d399', '#10b981', '#059669', '#6ee7b7', '#a7f3d0'];
        
        // Clear existing tracks from MultiTrackPlayer
        if (this.multiTrackPlayer) {
            this.multiTrackPlayer.clearTracks();
        }
        
        // Build list of all tracks to load for MultiTrackPlayer (audio playback)
        const tracksToLoad = [];
        
        // ====== LOAD MASTER TRACK (waveform + audio) ======
        if (syncData.masterUrl) {
            const masterName = syncData.masterFile?.split('/').pop() || 'Master';
            
            // Add to audio playback list
            tracksToLoad.push({
                id: 'master',
                config: { url: syncData.masterUrl, name: masterName, type: 'master', offset: 0, color: '#60a5fa' }
            });
            
            // Load waveform data through CoreAudioEngine
            try {
                this.updateStatus('Loading master waveform...');
                await this.audioEngine.loadAudioUrl(syncData.masterUrl, 'master');
                
                if (this.audioEngine.masterWaveformData?.peaks?.length > 0) {
                    this.trackWaveforms.push({
                        name: masterName,
                        type: 'master',
                        waveformData: this.cloneWaveformData(this.audioEngine.masterWaveformData),
                        color: '#60a5fa',
                        offset: 0
                    });
                    // Show waveform immediately
                    this.updateWaveform();
                } else {
                    console.warn('Master waveform data is empty');
                }
            } catch (e) {
                console.warn('Failed to load master waveform:', e);
                // Don't add tracks with null waveform data
            }
        }
        
        // ====== LOAD COMPONENT TRACKS (waveforms sequentially due to audioEngine limitation, audio in parallel) ======
        for (let i = 0; i < components.length; i++) {
            const comp = components[i];
            const compUrl = comp.dubUrl || comp.dub_url || comp.audioUrl;
            const compName = comp.name || comp.dubFile?.split('/').pop() || comp.dub_file?.split('/').pop() || `Component ${i + 1}`;
            const compOffset = comp.detectedOffset || comp.detected_offset || 0;
            const compColor = componentColors[i % componentColors.length];
            
            if (compUrl) {
                // Add to audio playback list
                tracksToLoad.push({
                    id: `component-${i}`,
                    config: { url: compUrl, name: compName, type: 'component', offset: compOffset, color: compColor }
                });
                
                // Load waveform (audioEngine can only hold one dub at a time, so we clone immediately)
                try {
                    this.updateStatus(`Loading waveform ${i + 1}/${components.length}: ${compName}...`);
                    await this.audioEngine.loadAudioUrl(compUrl, 'dub');
                    
                    if (this.audioEngine.dubWaveformData?.peaks?.length > 0) {
                        this.trackWaveforms.push({
                            name: compName,
                            type: 'component',
                            waveformData: this.cloneWaveformData(this.audioEngine.dubWaveformData),
                            color: compColor,
                            offset: compOffset
                        });
                        console.log(`Waveform loaded: ${compName}, duration: ${this.audioEngine.dubWaveformData.duration?.toFixed(1)}s`);
                        // Show waveform immediately as each loads
                        this.updateWaveform();
                    } else {
                        console.warn(`Component ${i + 1} waveform data is empty`);
                    }
                } catch (e) {
                    console.warn(`Failed to load component ${i + 1} waveform:`, e);
                    // Don't add tracks with null waveform data
                }
            }
        }
        
        // If no components but we have a dub URL, load it
        if (this.trackWaveforms.length === 1 && syncData.dubUrl) {
            const dubOffset = syncData.detectedOffset || 0;
            const dubName = syncData.dubFile?.split('/').pop() || 'Dub';
            
            tracksToLoad.push({
                id: 'dub',
                config: { url: syncData.dubUrl, name: dubName, type: 'component', offset: dubOffset, color: '#4ade80' }
            });
            
            try {
                this.updateStatus('Loading dub waveform...');
                await this.audioEngine.loadAudioUrl(syncData.dubUrl, 'dub');
                if (this.audioEngine.dubWaveformData?.peaks?.length > 0) {
                    this.trackWaveforms.push({
                        name: dubName, type: 'dub',
                        waveformData: this.cloneWaveformData(this.audioEngine.dubWaveformData),
                        color: '#4ade80', offset: dubOffset
                    });
                    this.updateWaveform();
                }
            } catch (e) {
                console.warn('Failed to load dub waveform:', e);
            }
        }
        
        // Update waveform display immediately with what we have
        this.updateWaveform();
        
        // ====== PARALLEL AUDIO LOAD for MultiTrackPlayer (fast, metadata-only) ======
        if (this.multiTrackPlayer && tracksToLoad.length > 0) {
            this.updateStatus(`Loading ${tracksToLoad.length} audio tracks...`);
            const loadedCount = await this.multiTrackPlayer.addTracksParallel(tracksToLoad);
            console.log(`Audio tracks loaded: ${loadedCount}/${tracksToLoad.length}`);
        }
        
        const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
        const trackCount = this.trackWaveforms.length;
        this.updateStatus(`${trackCount} tracks ready in ${elapsed}s`);
        console.log('Componentized tracks:', this.trackWaveforms.map(t => `${t.name} (${t.waveformData?.duration?.toFixed(1) || '?'}s)`));
        
        // Update track mixer UI
        this.updateTrackMixerUI();
        
        // Initialize NativeAudioPlayer for playback
        if (this.nativePlayer && syncData.masterUrl) {
            const firstComponent = components[0];
            const dubUrl = firstComponent?.dubUrl || firstComponent?.dub_url || syncData.dubUrl;
            const offset = firstComponent?.detectedOffset || firstComponent?.detected_offset || syncData.detectedOffset || 0;
            
            if (dubUrl) {
                this.nativePlayer.loadPair(syncData.masterUrl, dubUrl, offset).catch(err => {
                    console.warn('NativeAudioPlayer load failed:', err);
                });
            }
        }
    }

    /**
     * Clone waveform data to avoid reference issues when loading multiple tracks
     */
    cloneWaveformData(waveformData) {
        if (!waveformData) return null;
        return {
            peaks: waveformData.peaks ? new Float32Array(waveformData.peaks) : null,
            rms: waveformData.rms ? new Float32Array(waveformData.rms) : null,
            duration: waveformData.duration,
            sampleRate: waveformData.sampleRate,
            width: waveformData.width
        };
    }
    
    async loadPreGeneratedWaveforms(analysisId) {
        /**
         * Try to load pre-generated waveform data from the API.
         * First tries componentized endpoint, then falls back to standard.
         * Returns true if successful, false if waveforms need to be generated.
         */
        try {
            this.updateStatus('Loading pre-generated waveforms...');
            
            // First, try componentized waveforms endpoint
            const componentizedLoaded = await this.loadComponentizedWaveforms(analysisId);
            if (componentizedLoaded) {
                return true;
            }
            
            // Fall back to standard master/dub endpoint
            const response = await fetch(`/api/v1/waveforms/analysis/${analysisId}`);
            
            if (!response.ok) {
                console.log(`No pre-generated waveforms for ${analysisId}`);
                return false;
            }
            
            const data = await response.json();
            
            if (!data.master || !data.dub) {
                console.warn('Waveform data missing master or dub');
                return false;
            }
            
            // Convert to the format expected by the audio engine
            this.audioEngine.masterWaveformData = {
                peaks: new Float32Array(data.master.peaks),
                rms: new Float32Array(data.master.rms),
                duration: data.master.duration,
                sampleRate: data.master.sample_rate,
                width: data.master.width
            };
            
            this.audioEngine.dubWaveformData = {
                peaks: new Float32Array(data.dub.peaks),
                rms: new Float32Array(data.dub.rms),
                duration: data.dub.duration,
                sampleRate: data.dub.sample_rate,
                width: data.dub.width
            };
            
            // Also populate trackWaveforms for multi-track view
            this.trackWaveforms = [
                { 
                    name: 'Master', 
                    type: 'master', 
                    waveformData: this.audioEngine.masterWaveformData, 
                    color: '#60a5fa' 
                },
                { 
                    name: 'Dub', 
                    type: 'dub', 
                    waveformData: this.audioEngine.dubWaveformData, 
                    color: '#4ade80' 
                }
            ];
            
            this.updateStatus('Waveforms loaded - ready for playback');
            console.log('Pre-generated waveforms loaded:', {
                master: `${data.master.width} points, ${data.master.duration.toFixed(2)}s`,
                dub: `${data.dub.width} points, ${data.dub.duration.toFixed(2)}s`
            });
            
            // Resize canvas if in multi-track mode
            if (this.viewMode === 'multitrack') {
                this.setViewMode('multitrack');
            }
            
            // Initialize audio players for playback
            const masterUrl = this.currentData?.masterUrl;
            const dubUrl = this.currentData?.dubUrl;
            const offset = this.currentData?.detectedOffset || 0;
            
            if (masterUrl && dubUrl) {
                // Use WaveSurfer player (primary - best visualization)
                if (this.wavesurferPlayer) {
                    try {
                        this.updateStatus('Loading audio into WaveSurfer...');
                        await this.wavesurferPlayer.initialize(masterUrl, dubUrl, offset);
                        this.updateStatus('Ready for playback');
                    } catch (e) {
                        console.warn('WaveSurfer load failed:', e);
                        // Fall back to NativeAudioPlayer
                        if (this.nativePlayer) {
                            try {
                                await this.nativePlayer.loadPair(masterUrl, dubUrl, offset);
                                this.updateStatus('Ready for playback (fallback)');
                            } catch (e2) {
                                console.warn('NativeAudioPlayer load failed:', e2);
                            }
                        }
                    }
                } else if (this.nativePlayer) {
                    // No WaveSurfer, use NativeAudioPlayer
                    try {
                        await this.nativePlayer.loadPair(masterUrl, dubUrl, offset);
                        this.updateStatus('Ready for playback');
                    } catch (e) {
                        console.warn('NativeAudioPlayer load failed:', e);
                    }
                }
                
                // Also initialize track mixer UI
                this.updateTrackMixerUI();
            } else {
                console.warn('No audio URLs for playback');
                this.updateStatus('Waveforms loaded - no audio for playback', 'warning');
            }
            
            return true;
            
        } catch (error) {
            console.warn('Failed to load pre-generated waveforms:', error);
            return false;
        }
    }

    /**
     * Load componentized waveforms (master + multiple dub components)
     */
    async loadComponentizedWaveforms(analysisId) {
        try {
            const response = await fetch(`/api/v1/waveforms/componentized/${analysisId}`);
            
            if (!response.ok) {
                return false;
            }
            
            const data = await response.json();
            
            if (!data.tracks || data.tracks.length === 0) {
                return false;
            }
            
            // Build track list from componentized data
            this.trackWaveforms = [];
            
            // Assign colors - blue for master, greens for components
            const componentColors = ['#4ade80', '#22c55e', '#86efac', '#34d399', '#10b981', '#059669'];
            let componentIndex = 0;
            
            for (const track of data.tracks) {
                const ismaster = track.type === 'master';
                const color = ismaster ? '#60a5fa' : componentColors[componentIndex++ % componentColors.length];
                
                const waveformData = {
                    peaks: new Float32Array(track.peaks),
                    rms: track.rms ? new Float32Array(track.rms) : null,
                    duration: track.duration,
                    sampleRate: track.sample_rate || 22050,
                    width: track.width || track.peaks.length
                };
                
                this.trackWaveforms.push({
                    name: track.name || (ismaster ? 'Master' : `Component ${componentIndex}`),
                    type: track.type || (ismaster ? 'master' : 'component'),
                    waveformData,
                    color
                });
                
                // Also set audioEngine data for compatibility
                if (ismaster) {
                    this.audioEngine.masterWaveformData = waveformData;
                } else if (!this.audioEngine.dubWaveformData) {
                    this.audioEngine.dubWaveformData = waveformData;
                }
            }
            
            this.updateStatus(`Loaded ${this.trackWaveforms.length} tracks - ready for multi-track view`);
            console.log('Componentized waveforms loaded:', this.trackWaveforms.map(t => t.name));
            
            // Auto-switch to multi-track mode for componentized data
            if (this.trackWaveforms.length > 2) {
                this.setViewMode('multitrack');
            }
            
            return true;
            
        } catch (error) {
            console.warn('Failed to load componentized waveforms:', error);
            return false;
        }
    }

    close() {
        this.isVisible = false;
        this.stopPlayback();
        this.stopPlayheadAnimation();
        
        // Clear all players
        if (this.nativePlayer) {
            this.nativePlayer.clear();
        }
        if (this.multiTrackPlayer) {
            this.multiTrackPlayer.clearTracks();
        }
        
        const modal = document.getElementById('qc-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        this.currentData = null;
        this.lastSeekTime = 0;
        this.trackWaveforms = [];
        console.log('QC Interface closed');
    }

    // Debug method to check interface state
    getDebugInfo() {
        const modal = document.getElementById('qc-modal');
        return {
            isVisible: this.isVisible,
            modalExists: !!modal,
            modalDisplay: modal?.style.display,
            audioEngineExists: !!this.audioEngine,
            audioEngineState: this.audioEngine?.getStatus?.() || 'No status available',
            currentData: this.currentData
        };
    }

    formatTimecode(seconds, fps = 23.976) {
        /**
         * Convert seconds to SMPTE timecode format HH:MM:SS:FF
         * Matches formatTimecode from app.js
         */
        const sign = seconds < 0 ? '-' : '';
        const absSeconds = Math.abs(seconds);

        const hours = Math.floor(absSeconds / 3600);
        const minutes = Math.floor((absSeconds % 3600) / 60);
        const secs = Math.floor(absSeconds % 60);
        const frames = Math.floor((absSeconds % 1) * fps);

        return `${sign}${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
    }

    updateFileInfo(syncData) {
        document.getElementById('qc-master-file').textContent = syncData.masterFile || 'Unknown';
        document.getElementById('qc-dub-file').textContent = syncData.dubFile || 'Unknown';

        const offset = syncData.detectedOffset || 0;
        const fps = syncData.frameRate || 23.976;
        
        // Display offset in timecode format: -00:00:15:00
        if (typeof offset !== 'number' || isNaN(offset)) {
            document.getElementById('qc-offset-value').textContent = 'N/A';
        } else {
            const timecode = this.formatTimecode(offset, fps);
            document.getElementById('qc-offset-value').textContent = timecode;
        }

        const confidence = syncData.confidence || 0;
        document.getElementById('qc-confidence-value').textContent = `${Math.round(confidence * 100)}%`;
    }

    async loadAudioFiles(syncData) {
        if (!syncData.masterUrl || !syncData.dubUrl) {
            this.updateStatus('No audio URLs provided', 'error');
            return;
        }

        try {
            this.updateStatus('Loading master audio...');
            await this.audioEngine.loadAudioUrl(syncData.masterUrl, 'master');
            
            this.updateStatus('Loading dub audio...');
            await this.audioEngine.loadAudioUrl(syncData.dubUrl, 'dub');
            
            this.updateStatus('Audio files loaded successfully');
        } catch (error) {
            console.error('Failed to load audio files:', error);
            this.updateStatus(`Failed to load audio: ${error.message}`, 'error');
        }
    }

    async loadAudioFilesAsync(syncData) {
        if (!syncData.masterUrl || !syncData.dubUrl) {
            this.updateStatus(
                'No audio URLs provided - QC interface ready for visual review only',
                'warning'
            );
            return;
        }

        const offset = this.currentData?.detectedOffset || 0;
        console.log('QC: Loading audio', { masterUrl: syncData.masterUrl, dubUrl: syncData.dubUrl, offset });

        try {
            this.updateStatus('Loading audio for QC...');

            // Load waveforms (for canvas visualization)
            if (this.audioEngine) {
                const usingProxy =
                    syncData.masterUrl?.includes('proxy-audio') ||
                    syncData.dubUrl?.includes('proxy-audio');
                const timeoutMs = usingProxy ? 60000 : 30000;

                const loadWithTimeout = (url, type) => {
                    const loadPromise = this.audioEngine.loadAudioUrl(url, type);
                    const timeoutPromise = new Promise((_, reject) =>
                        setTimeout(
                            () => reject(new Error(`${type} loading timeout after ${timeoutMs / 1000}s`)),
                            timeoutMs
                        )
                    );
                    return Promise.race([loadPromise, timeoutPromise]);
                };

                await Promise.allSettled([
                    loadWithTimeout(syncData.masterUrl, 'master'),
                    loadWithTimeout(syncData.dubUrl, 'dub'),
                ]);
            }

            // Initialize QCPlayer for playback (Before/After uses offset)
            if (this.qcPlayer) {
                const ok = await this.qcPlayer.initialize(syncData.masterUrl, syncData.dubUrl, offset);
                if (!ok) {
                    this.updateStatus('Audio loaded (waveform ok) but playback init failed', 'warning');
                }
            } else if (this.nativePlayer) {
                // Fallback: NativeAudioPlayer
                await this.nativePlayer.loadPair(syncData.masterUrl, syncData.dubUrl, offset);
            }

            this.updateWaveform();
            this.renderDriftMarkers();
            this.renderSceneBands();
            this.updateStatus('Ready');
        } catch (error) {
            console.error('QC: Audio loading error:', error);
            this.updateStatus(`Audio loading failed: ${error.message}`, 'error');
        }
    }

    updateWaveform() {
        const canvas = document.getElementById('qc-waveform-canvas');
        const ctx = canvas.getContext('2d');
        
        // Clear canvas
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Check if we have ACTUAL waveform data (not just empty entries)
        const hasEngineWaveforms = this.audioEngine?.masterWaveformData?.peaks?.length > 0 && 
                                   this.audioEngine?.dubWaveformData?.peaks?.length > 0;
        const hasTrackWaveforms = this.trackWaveforms.some(t => t.waveformData?.peaks?.length > 0);
        const hasWaveformData = hasEngineWaveforms || hasTrackWaveforms;
        
        if (!hasWaveformData) {
            // Draw placeholder
            ctx.fillStyle = '#666';
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('Loading waveforms...', canvas.width / 2, canvas.height / 2);
            return;
        }
        
        // Draw based on view mode
        if (this.viewMode === 'multitrack') {
            this.drawMultiTrackView(ctx, canvas);
        } else {
            // Simple mode - use before/after toggle
            const isAfterView = document.querySelector('.qc-toggle-btn[data-view="after"]')?.classList.contains('active') ?? false;
            this.drawWaveformComparison(ctx, canvas, isAfterView);
        }
        
        // Update overlays to match current width
        this.renderDriftMarkers();
        this.renderSceneBands();
        
        // Draw initial progress overlay
        this.drawProgressOverlay(ctx, canvas);
    }

    /**
     * Update progress overlay without full waveform redraw
     * Uses a dedicated overlay canvas for smooth animation
     */
    updateProgressOverlay() {
        const canvas = document.getElementById('qc-waveform-canvas');
        if (!canvas) return;
        
        // Get or create overlay canvas
        let overlay = document.getElementById('qc-progress-overlay');
        if (!overlay) {
            overlay = document.createElement('canvas');
            overlay.id = 'qc-progress-overlay';
            overlay.style.cssText = 'position:absolute;left:0;top:0;pointer-events:none;z-index:10;';
            canvas.parentElement.style.position = 'relative';
            canvas.parentElement.appendChild(overlay);
        }
        
        // Match canvas size
        if (overlay.width !== canvas.width || overlay.height !== canvas.height) {
            overlay.width = canvas.width;
            overlay.height = canvas.height;
        }
        
        const ctx = overlay.getContext('2d');
        ctx.clearRect(0, 0, overlay.width, overlay.height);
        
        if (this.currentProgress <= 0 || this.currentProgress >= 1) return;
        
        // Calculate progress width
        const labelWidth = this.viewMode === 'multitrack' ? 80 : 0;
        const waveformWidth = overlay.width - labelWidth;
        const progressX = labelWidth + (this.currentProgress * waveformWidth);
        
        // Draw played region highlight (semi-transparent green)
        ctx.fillStyle = 'rgba(74, 222, 128, 0.15)';
        ctx.fillRect(labelWidth, 0, progressX - labelWidth, overlay.height);
        
        // Draw playhead line
        ctx.strokeStyle = '#4ade80';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(progressX, 0);
        ctx.lineTo(progressX, overlay.height);
        ctx.stroke();
        
        // Draw time indicator at playhead
        const duration = this.getDurationFromTracks();
        if (duration > 0) {
            const currentTime = this.currentProgress * duration;
            const timeText = this.formatTime(currentTime);
            
            ctx.font = '11px monospace';
            ctx.textAlign = 'center';
            
            // Background for time text
            const textWidth = ctx.measureText(timeText).width + 8;
            const textX = Math.min(Math.max(progressX, labelWidth + textWidth/2), overlay.width - textWidth/2);
            
            ctx.fillStyle = 'rgba(26, 26, 26, 0.9)';
            ctx.fillRect(textX - textWidth/2, 2, textWidth, 16);
            
            ctx.fillStyle = '#4ade80';
            ctx.fillText(timeText, textX, 14);
        }
    }

    /**
     * Draw progress overlay on waveform (called during waveform render)
     */
    drawProgressOverlay(ctx, canvas) {
        if (this.currentProgress <= 0) return;
        
        const labelWidth = this.viewMode === 'multitrack' ? 80 : 0;
        const waveformWidth = canvas.width - labelWidth;
        const progressX = labelWidth + (this.currentProgress * waveformWidth);
        
        // Draw played region highlight
        ctx.save();
        ctx.fillStyle = 'rgba(74, 222, 128, 0.1)';
        ctx.fillRect(labelWidth, 0, progressX - labelWidth, canvas.height);
        ctx.restore();
    }

    drawWaveformComparison(ctx, canvas, isAfterView) {
        const masterData = this.audioEngine.masterWaveformData;
        const dubData = this.audioEngine.dubWaveformData;
        const offset = this.currentData?.detectedOffset || 0;
        try { console.log('[QC] drawWaveformComparison:', { isAfterView, offset }); } catch {}
        
        const width = canvas.width;
        const height = canvas.height;
        const centerY = height / 2;
        const waveHeight = height / 4;
        
        // After Fix: Show aligned waveforms - shift dub by detected offset so content aligns
        //   If offset > 0, dub content at t=0 matches master content at t=offset
        //   So we shift dub RIGHT by offset to align the audio content
        // Before Fix: Show natural positions (both at x=0) to visualize the mismatch
        const visualOffset = isAfterView ? offset : 0;
        
        // Use consistent time scale for both waveforms
        const maxDuration = Math.max(masterData.duration, dubData.duration);
        const offsetPixels = (visualOffset / maxDuration) * width;
        
        // Auto-normalize: find the max peak across both waveforms to scale properly
        let maxPeak = 0;
        for (let i = 0; i < masterData.peaks.length; i++) {
            maxPeak = Math.max(maxPeak, masterData.peaks[i]);
        }
        for (let i = 0; i < dubData.peaks.length; i++) {
            maxPeak = Math.max(maxPeak, dubData.peaks[i]);
        }
        
        // Check if we have placeholder/zero data
        if (maxPeak < 0.0001) {
            console.warn('[QC] Waveform data appears to be placeholder (all zeros)');
            ctx.fillStyle = '#94a3b8';
            ctx.font = '14px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('Waveform data unavailable - audio extraction may have failed', width / 2, centerY - 20);
            ctx.fillText('The offset visualization is still accurate based on analysis results', width / 2, centerY + 20);
            // Draw basic offset indicator anyway
            this.drawOffsetIndicator(ctx, canvas, offset, isAfterView);
            return;
        }
        
        const normalizeScale = 1.0 / maxPeak; // Scale factor to make peaks use full height
        console.log('[QC] Waveform normalization: maxPeak=', maxPeak.toFixed(4), 'scale=', normalizeScale.toFixed(2));
        
        // Draw master waveform (top half - always starts at 0)
        ctx.strokeStyle = '#4ade80'; // green
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < masterData.peaks.length; i++) {
            // Scale master waveform based on its actual duration relative to max duration
            const x = (i / masterData.peaks.length) * (masterData.duration / maxDuration) * width;
            // Apply normalization to make quiet audio visible
            const normalizedPeak = masterData.peaks[i] * normalizeScale;
            const y = centerY - (normalizedPeak * waveHeight);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
        
        // Draw master label
        ctx.fillStyle = '#4ade80';
        ctx.font = '12px Arial';
        ctx.fillText('Master', 10, 20);
        
        // Draw dub waveform (bottom half - offset based on sync)
        ctx.strokeStyle = '#f87171'; // red
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        for (let i = 0; i < dubData.peaks.length; i++) {
            // Scale dub waveform based on its actual duration relative to max duration, then apply offset
            const baseX = (i / dubData.peaks.length) * (dubData.duration / maxDuration) * width;
            const x = baseX + offsetPixels;
            // Apply same normalization as master
            const normalizedPeak = dubData.peaks[i] * normalizeScale;
            const y = centerY + (normalizedPeak * waveHeight);
            
            // Only draw if within canvas bounds
            if (x >= 0 && x <= width) {
                if (i === 0 || (i > 0 && baseX + offsetPixels < 0)) {
                    ctx.moveTo(x, y);
                } else {
                    ctx.lineTo(x, y);
                }
            }
        }
        ctx.stroke();
        
        // Draw dub label
        ctx.fillStyle = '#f87171';
        ctx.font = '12px Arial';
        const dubLabelX = Math.max(10, Math.min(width - 50, offsetPixels + 10));
        ctx.fillText('Dub', dubLabelX, height - 10);
        
        // Draw center line
        ctx.strokeStyle = '#666';
        ctx.lineWidth = 1;
        ctx.setLineDash([5, 5]);
        ctx.beginPath();
        ctx.moveTo(0, centerY);
        ctx.lineTo(width, centerY);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Draw offset marker and info in Before Fix view to indicate the problem
        if (!isAfterView && Math.abs(offset) > 0.001) {
            // Vertical offset line showing correction needed
            if (Math.abs(offsetPixels) > 5) {
                ctx.strokeStyle = '#fbbf24'; // yellow
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.moveTo(Math.abs(offsetPixels), 0);
                ctx.lineTo(Math.abs(offsetPixels), height);
                ctx.stroke();
                
                // Offset label - describe the natural sync problem
                ctx.fillStyle = '#fbbf24';
                ctx.font = 'bold 14px Arial';
                const fps = this.currentData?.frameRate || 24;
                const frames = Math.round(Math.abs(offset) * fps);
                const frameSign = offset < 0 ? '-' : '+';
                const offsetText = `Sync Problem: ${offset >= 0 ? '+' : ''}${offset.toFixed(3)}s (${frameSign}${frames}f @ ${fps}fps) ${offset > 0 ? 'dub early' : 'dub late'}`;
                const textX = Math.abs(offsetPixels) + 10;
                const textY = height / 2;
                ctx.fillText(offsetText, textX > width - 100 ? textX - 120 : textX, textY);
            }
        }
        
        // Draw view mode indicator
        ctx.fillStyle = '#9ca3af';
        ctx.font = 'bold 16px Arial';
        ctx.textAlign = 'right';
            const modeText = isAfterView ? 'After Fix (Aligned)' : 'Before Fix (With Offset)';
        ctx.fillText(modeText, width - 10, 25);
        ctx.textAlign = 'left';
    }

    /**
     * Draw multi-track DAW-style waveform view with stacked tracks
     */
    drawMultiTrackView(ctx, canvas) {
        const width = canvas.width;
        const height = canvas.height;
        const offset = this.currentData?.detectedOffset || 0;
        const applyOffset = this.applyOffset;

        // Build track list: use componentized tracks if available, otherwise master + dub
        let tracks = [];
        if (this.trackWaveforms.length > 0) {
            tracks = this.trackWaveforms;
        } else if (this.audioEngine?.masterWaveformData && this.audioEngine?.dubWaveformData) {
            tracks = [
                { name: 'Master', type: 'master', waveformData: this.audioEngine.masterWaveformData, color: '#60a5fa' },
                { name: 'Dub', type: 'dub', waveformData: this.audioEngine.dubWaveformData, color: '#4ade80' }
            ];
        }

        if (tracks.length === 0) return;

        // Layout constants
        const timelineHeight = 30;
        const trackPadding = 4;
        const labelWidth = 80;
        const availableHeight = height - timelineHeight;
        const trackHeight = Math.floor(availableHeight / tracks.length) - trackPadding;
        const waveformWidth = width - labelWidth;

        // Calculate max duration across all tracks
        const maxDuration = Math.max(...tracks.map(t => t.waveformData?.duration || 0));
        if (maxDuration <= 0) return;

        // Draw timeline ruler at top
        this.drawTimelineRuler(ctx, labelWidth, 0, waveformWidth, timelineHeight, maxDuration);

        // Draw each track
        tracks.forEach((track, index) => {
            const y = timelineHeight + index * (trackHeight + trackPadding);
            
            // Determine if this track should be offset
            const isOffsetTrack = track.type === 'dub' || track.type === 'component';
            const trackOffset = (applyOffset && isOffsetTrack) ? offset : 0;

            this.drawTrack(ctx, track, 0, y, labelWidth, waveformWidth, trackHeight, maxDuration, trackOffset);
        });

        // Draw mode indicator
        ctx.fillStyle = '#9ca3af';
        ctx.font = 'bold 12px Arial';
        ctx.textAlign = 'right';
        const modeText = applyOffset ? 'Offset Applied' : 'Raw Positions';
        ctx.fillText(modeText, width - 10, timelineHeight - 8);
        ctx.textAlign = 'left';
    }

    /**
     * Draw timeline ruler with time markers
     */
    drawTimelineRuler(ctx, x, y, width, height, duration) {
        const bgGradient = ctx.createLinearGradient(x, y, x, y + height);
        bgGradient.addColorStop(0, '#1e293b');
        bgGradient.addColorStop(1, '#0f172a');
        ctx.fillStyle = bgGradient;
        ctx.fillRect(x, y, width, height);

        // Draw border
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, width, height);

        // Calculate tick interval based on duration
        let tickInterval;
        if (duration <= 30) tickInterval = 5;
        else if (duration <= 60) tickInterval = 10;
        else if (duration <= 300) tickInterval = 30;
        else if (duration <= 600) tickInterval = 60;
        else tickInterval = 120;

        const pxPerSecond = width / duration;

        // Draw tick marks and labels
        ctx.fillStyle = '#94a3b8';
        ctx.font = '10px JetBrains Mono, monospace';
        ctx.textAlign = 'center';

        for (let t = 0; t <= duration; t += tickInterval) {
            const tickX = x + t * pxPerSecond;
            
            // Draw tick mark
            ctx.strokeStyle = '#475569';
            ctx.beginPath();
            ctx.moveTo(tickX, y + height - 8);
            ctx.lineTo(tickX, y + height);
            ctx.stroke();

            // Draw time label
            const mins = Math.floor(t / 60);
            const secs = Math.floor(t % 60);
            const label = `${mins}:${secs.toString().padStart(2, '0')}`;
            ctx.fillText(label, tickX, y + height - 12);
        }

        // Draw minor ticks
        const minorInterval = tickInterval / 5;
        ctx.strokeStyle = '#334155';
        for (let t = 0; t <= duration; t += minorInterval) {
            if (t % tickInterval === 0) continue; // Skip major ticks
            const tickX = x + t * pxPerSecond;
            ctx.beginPath();
            ctx.moveTo(tickX, y + height - 4);
            ctx.lineTo(tickX, y + height);
            ctx.stroke();
        }
    }

    /**
     * Draw a single track (label + waveform)
     */
    drawTrack(ctx, track, x, y, labelWidth, waveformWidth, trackHeight, maxDuration, trackOffset) {
        const waveformData = track.waveformData;
        const color = track.color || '#4ade80';
        const name = track.name || 'Track';

        // Draw track background
        const bgGradient = ctx.createLinearGradient(x, y, x, y + trackHeight);
        bgGradient.addColorStop(0, '#0f172a');
        bgGradient.addColorStop(0.5, '#1e293b');
        bgGradient.addColorStop(1, '#0f172a');
        ctx.fillStyle = bgGradient;
        ctx.fillRect(x, y, labelWidth + waveformWidth, trackHeight);

        // Draw track border
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, labelWidth + waveformWidth, trackHeight);

        // Draw label background
        ctx.fillStyle = track.type === 'master' ? 'rgba(96, 165, 250, 0.1)' : 'rgba(74, 222, 128, 0.1)';
        ctx.fillRect(x, y, labelWidth, trackHeight);

        // Draw label text
        ctx.fillStyle = color;
        ctx.font = 'bold 11px JetBrains Mono, monospace';
        ctx.textAlign = 'left';
        ctx.fillText(name, x + 8, y + trackHeight / 2 + 4);

        // Draw separator line between label and waveform
        ctx.strokeStyle = '#334155';
        ctx.beginPath();
        ctx.moveTo(x + labelWidth, y);
        ctx.lineTo(x + labelWidth, y + trackHeight);
        ctx.stroke();

        // Draw center line
        const centerY = y + trackHeight / 2;
        ctx.strokeStyle = '#334155';
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(x + labelWidth, centerY);
        ctx.lineTo(x + labelWidth + waveformWidth, centerY);
        ctx.stroke();
        ctx.setLineDash([]);

        // Calculate waveform scaling
        if (!waveformData?.peaks || waveformData.peaks.length === 0) return;

        const peaks = waveformData.peaks;
        const trackDuration = waveformData.duration || maxDuration;
        const pxPerSecond = waveformWidth / maxDuration;
        const offsetPx = trackOffset * pxPerSecond;
        const waveHeight = (trackHeight - 8) / 2;

        // Find max peak for normalization
        let maxPeak = 0;
        for (let i = 0; i < peaks.length; i++) {
            maxPeak = Math.max(maxPeak, peaks[i]);
        }
        const normalizeScale = maxPeak > 0.0001 ? 1.0 / maxPeak : 1;

        // Draw waveform
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.beginPath();

        let firstPoint = true;
        for (let i = 0; i < peaks.length; i++) {
            const sampleTime = (i / peaks.length) * trackDuration;
            const drawX = x + labelWidth + sampleTime * pxPerSecond + offsetPx;

            // Skip if outside visible area
            if (drawX < x + labelWidth || drawX > x + labelWidth + waveformWidth) continue;

            const normalizedPeak = peaks[i] * normalizeScale;
            const drawY = centerY - normalizedPeak * waveHeight;

            if (firstPoint) {
                ctx.moveTo(drawX, drawY);
                firstPoint = false;
            } else {
                ctx.lineTo(drawX, drawY);
            }
        }
        ctx.stroke();

        // Draw mirrored waveform (bottom half)
        ctx.beginPath();
        firstPoint = true;
        for (let i = 0; i < peaks.length; i++) {
            const sampleTime = (i / peaks.length) * trackDuration;
            const drawX = x + labelWidth + sampleTime * pxPerSecond + offsetPx;

            if (drawX < x + labelWidth || drawX > x + labelWidth + waveformWidth) continue;

            const normalizedPeak = peaks[i] * normalizeScale;
            const drawY = centerY + normalizedPeak * waveHeight;

            if (firstPoint) {
                ctx.moveTo(drawX, drawY);
                firstPoint = false;
            } else {
                ctx.lineTo(drawX, drawY);
            }
        }
        ctx.stroke();

        // Fill waveform area with semi-transparent color
        ctx.fillStyle = color.replace(')', ', 0.15)').replace('rgb', 'rgba');
        if (color.startsWith('#')) {
            const r = parseInt(color.slice(1, 3), 16);
            const g = parseInt(color.slice(3, 5), 16);
            const b = parseInt(color.slice(5, 7), 16);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.15)`;
        }

        ctx.beginPath();
        for (let i = 0; i < peaks.length; i++) {
            const sampleTime = (i / peaks.length) * trackDuration;
            const drawX = x + labelWidth + sampleTime * pxPerSecond + offsetPx;

            if (drawX < x + labelWidth || drawX > x + labelWidth + waveformWidth) continue;

            const normalizedPeak = peaks[i] * normalizeScale;
            const topY = centerY - normalizedPeak * waveHeight;
            const bottomY = centerY + normalizedPeak * waveHeight;

            if (i === 0) {
                ctx.moveTo(drawX, topY);
            } else {
                ctx.lineTo(drawX, topY);
            }
        }
        // Close path through bottom
        for (let i = peaks.length - 1; i >= 0; i--) {
            const sampleTime = (i / peaks.length) * trackDuration;
            const drawX = x + labelWidth + sampleTime * pxPerSecond + offsetPx;

            if (drawX < x + labelWidth || drawX > x + labelWidth + waveformWidth) continue;

            const normalizedPeak = peaks[i] * normalizeScale;
            const bottomY = centerY + normalizedPeak * waveHeight;
            ctx.lineTo(drawX, bottomY);
        }
        ctx.closePath();
        ctx.fill();
    }

    playComparison(corrected = false) {
        console.log('[QC playComparison] corrected:', corrected);

        try {
            const startAt = this.lastSeekTime || 0;

            // Update UI immediately
            this.updateStatus(corrected ? 'Playing (After Fix)' : 'Playing (Before Fix)');
            document.getElementById('qc-play-before')?.classList.toggle('active', !corrected);
            document.getElementById('qc-play-after')?.classList.toggle('active', corrected);

            // Preferred: QCPlayer
            if (this.qcPlayer) {
                if (corrected) this.qcPlayer.playAfter(startAt);
                else this.qcPlayer.playBefore(startAt);
                return;
            }

            // Fallback: NativeAudioPlayer
            if (this.nativePlayer) {
                this.nativePlayer.play(corrected, startAt);
                return;
            }

            // Fallback: MultiTrackPlayer
            if (this.multiTrackPlayer) {
                if (corrected) this.multiTrackPlayer.playAfter(startAt);
                else this.multiTrackPlayer.playBefore(startAt);
                return;
            }

            this.updateStatus('No audio player available', 'error');
        } catch (error) {
            console.error('Playback error:', error);
            this.updateStatus(`Playback error: ${error.message}`, 'error');
        }
    }

    stopPlayback() {
        console.log('[QC] stopPlayback called');

        try {
            this.qcPlayer?.stop();
        } catch {}
        try {
            this.nativePlayer?.stop();
        } catch {}
        try {
            this.multiTrackPlayer?.stop();
        } catch {}

        this.updateStatus('Stopped');
        
        // Update button states
        document.getElementById('qc-play-before')?.classList.remove('active');
        document.getElementById('qc-play-after')?.classList.remove('active');
    }

    startPlayheadUpdate() {
        this.stopPlayheadUpdate(); // Clear any existing interval

        const canvas = document.getElementById('qc-waveform-canvas');
        if (!canvas) return;

        this.canvasWidth = canvas.width;
        this.totalDuration = Math.max(
            this.audioEngine?.masterWaveformData?.duration || 0,
            this.audioEngine?.dubWaveformData?.duration || 0
        );

        if (this.totalDuration === 0) return;

        // Update playhead at 60fps for smooth animation
        this.playheadUpdateInterval = setInterval(() => {
            this.updatePlayheadPosition();
        }, 1000 / 60);
    }

    stopPlayheadUpdate() {
        if (this.playheadUpdateInterval) {
            clearInterval(this.playheadUpdateInterval);
            this.playheadUpdateInterval = null;
        }
    }

    updatePlayheadPosition() {
        if (!this.audioEngine) return;

        const times = this.audioEngine.getCurrentTimes();
        const currentTime = Math.max(times.master || 0, times.dub || 0);

        if (this.totalDuration === 0) return;

        // Update timeline slider
        const slider = document.getElementById('qc-timeline-slider');
        if (slider && !this.isSeeking) {
            slider.value = (currentTime / this.totalDuration) * 1000;
        }

        // Stop updating if playback finished
        if (currentTime >= this.totalDuration || !this.audioEngine.isPlaying) {
            this.stopPlayheadUpdate();
        }
    }

    seekTo(time) {
        try {
            // Guard against invalid time
            if (!Number.isFinite(time) || time < 0) {
                console.warn('QC seekTo: invalid time', time);
                return;
            }

            // Seek using all available players
            if (this.nativePlayer) {
                this.nativePlayer.seek(time);
            }

            if (this.multiTrackPlayer) {
                this.multiTrackPlayer.seek(time);
            }

            if (this.audioEngine) {
                this.audioEngine.seekTo?.(time);
            }

            if (this.qcPlayer) {
                this.qcPlayer.seek?.(time);
            }

            // Store for playback resume
            this.lastSeekTime = time;

            // Update timeline slider
            const duration = this.nativePlayer?.getDuration() || this.getDurationFromTracks() || 0;
            if (duration > 0) {
                const slider = document.getElementById('qc-timeline-slider');
                if (slider) {
                    slider.value = (time / duration) * 1000;
                }
            }

            // Update time display
            const currentTimeEl = document.getElementById('qc-current-time');
            if (currentTimeEl) currentTimeEl.textContent = this.formatTime(time);

        } catch (error) {
            console.error('[QC seekTo] Error:', error);
        }
    }

    togglePlayback() {
        const isPlaying = this.nativePlayer?.isPlaying || this.multiTrackPlayer?.isPlaying || this.qcPlayer?.isPlaying;
        if (isPlaying) {
            this.stopPlayback();
        } else {
            // Determine corrected mode based on view
            let corrected = false;
            if (this.viewMode === 'multitrack') {
                corrected = this.applyOffset;
            } else {
                corrected = document.querySelector('.qc-toggle-btn[data-view="after"]')?.classList.contains('active') || false;
            }
            this.playComparison(corrected);
        }
    }

    updateStatus(message, type = 'info') {
        const statusElement = document.getElementById('qc-playback-status');
        if (statusElement) {
            statusElement.textContent = message;
            statusElement.className = `qc-status-${type}`;
        }
        console.log(`QC Interface: ${message}`);
    }

    renderDriftMarkers() {
        const container = document.getElementById('qc-drift-markers');
        const canvas = document.getElementById('qc-waveform-canvas');
        const timelineInfo = document.getElementById('qc-timeline-info');
        const driftCount = document.getElementById('qc-drift-count');

        if (!container || !canvas) return;
        container.innerHTML = '';

        const timeline = Array.isArray(this.currentData?.timeline) ? this.currentData.timeline : [];

        // Show/hide timeline info based on whether we have drift data
        if (timelineInfo) {
            if (timeline.length > 0) {
                timelineInfo.style.display = 'block';
                if (driftCount) driftCount.textContent = timeline.length;
            } else {
                timelineInfo.style.display = 'none';
            }
        }

        if (!timeline.length) return;

        const masterDur = this.audioEngine?.masterWaveformData?.duration || null;
        const dubDur = this.audioEngine?.dubWaveformData?.duration || null;
        const maxDur = Math.max(masterDur || 0, dubDur || 0) || 0;
        if (!maxDur) return;

        const width = canvas.width;
        const pxPerSec = width / maxDur;

        timeline.forEach(seg => {
            const offset = typeof seg.offset_seconds === 'number' ? seg.offset_seconds : 0;
            const start = typeof seg.start_time === 'number' ? seg.start_time : 0;
            const end = typeof seg.end_time === 'number' ? seg.end_time : start;
            const x = start * pxPerSec;
            const w = Math.max(2, (end - start) * pxPerSec);

            const mag = Math.abs(offset);
            let cls = 'minor';
            if (mag >= 0.25) cls = 'major';
            else if (mag >= 0.10) cls = 'issue';
            else if (mag < 0.03) cls = 'insync';

            const m = document.createElement('div');
            m.className = `qc-drift-marker severity-${cls}`;
            m.style.position = 'absolute';
            m.style.left = `${x}px`;
            m.style.bottom = '0px';
            m.style.width = `${w}px`;
            m.style.top = '0px';
            m.style.pointerEvents = 'auto';
            const fps = this.currentData?.frameRate || 24;
            const frames = Math.round(Math.abs(offset) * fps);
            const frameSign = offset < 0 ? '-' : '+';
            m.title = `${start.toFixed(2)}s → ${end.toFixed(2)}s • ${offset >= 0 ? '+' : ''}${offset.toFixed(3)}s (${frameSign}${frames}f @ ${fps}fps)` + (seg.reliable ? ' • reliable' : '');
            m.style.background = 'transparent';

            const line = document.createElement('div');
            line.style.position = 'absolute';
            line.style.left = '0';
            line.style.top = '0';
            line.style.bottom = '0';
            line.style.width = '2px';
            line.style.background = cls === 'major' ? '#ef4444' : cls === 'issue' ? '#f59e0b' : cls === 'insync' ? '#10b981' : '#fbbf24';
            line.style.opacity = '0.9';
            m.appendChild(line);

            m.addEventListener('click', (e) => {
                e.stopPropagation();
                if (this.audioEngine && typeof this.audioEngine.seekTo === 'function') {
                    this.audioEngine.seekTo(start);
                }
            });

            container.appendChild(m);
        });
    }

    renderSceneBands() {
        const container = document.getElementById('qc-scene-bands');
        const canvas = document.getElementById('qc-waveform-canvas');
        if (!container || !canvas) return;
        container.innerHTML = '';

        const op = this.currentData?.operatorTimeline || this.currentData?.operator_timeline;
        const scenes = Array.isArray(op?.scenes) ? op.scenes : [];
        const timeline = Array.isArray(this.currentData?.timeline) ? this.currentData.timeline : [];

        const masterDur = this.audioEngine?.masterWaveformData?.duration || null;
        const dubDur = this.audioEngine?.dubWaveformData?.duration || null;
        const maxDur = Math.max(masterDur || 0, dubDur || 0) || 0;
        if (!maxDur) return;
        const pxPerSec = canvas.width / maxDur;

        const bands = scenes.length ? scenes.map(s => ({
            start: s.start_time ?? s.start ?? 0,
            end: s.end_time ?? s.end ?? 0,
            label: s.scene_type || s.label || 'Scene',
            severity: (s.severity || 'NO_DATA').toString().toUpperCase(),
            description: s.description || ''
        })) : timeline.map(seg => ({
            start: seg.start_time || 0,
            end: seg.end_time || (seg.start_time || 0),
            label: seg.content_type || 'Segment',
            severity: (Math.abs(seg.offset_seconds || 0) >= 0.25) ? 'MAJOR_DRIFT' : (Math.abs(seg.offset_seconds || 0) >= 0.10) ? 'SYNC_ISSUE' : (Math.abs(seg.offset_seconds || 0) < 0.03 ? 'IN_SYNC' : 'MINOR_DRIFT'),
            description: ''
        }));

        const colorFor = sev => ({
            'MAJOR_DRIFT': '#ef4444',
            'SYNC_ISSUE': '#f59e0b',
            'MINOR_DRIFT': '#fbbf24',
            'IN_SYNC': '#10b981',
            'NO_DATA': '#6b7280'
        }[sev] || '#6b7280');

        bands.forEach(b => {
            const x = Math.max(0, b.start * pxPerSec);
            const w = Math.max(2, (b.end - b.start) * pxPerSec);
            const el = document.createElement('div');
            el.style.position = 'absolute';
            el.style.left = `${x}px`;
            el.style.width = `${w}px`;
            el.style.top = '0';
            el.style.bottom = '0';
            el.style.background = colorFor(b.severity);
            el.style.opacity = '0.12';
            el.style.borderLeft = '2px solid rgba(0,0,0,0.3)';
            el.style.borderRight = '2px solid rgba(0,0,0,0.3)';
            el.style.pointerEvents = 'auto';
            el.title = `${b.label} • ${b.severity.replace('_',' ')}${b.description ? ' • ' + b.description : ''}`;

            // Small label chip
            const chip = document.createElement('div');
            chip.style.position = 'absolute';
            chip.style.left = '4px';
            chip.style.top = '2px';
            chip.style.fontSize = '10px';
            chip.style.fontWeight = '600';
            chip.style.color = '#e5e7eb';
            chip.style.textShadow = '0 1px 1px rgba(0,0,0,0.6)';
            chip.textContent = `${b.severity.replace('_',' ')}${b.label ? ' · ' + b.label : ''}`;
            el.appendChild(chip);

            el.addEventListener('click', (e) => {
                e.stopPropagation();
                if (this.audioEngine && typeof this.audioEngine.seekTo === 'function') {
                    this.audioEngine.seekTo(b.start);
                }
            });

            container.appendChild(el);
        });
    }

    approveSync() {
        this.updateStatus('Sync approved');
        // TODO: Implement approval logic
        if (this.onApprove) this.onApprove(this.currentData);
    }

    flagForReview() {
        this.updateStatus('Flagged for review');
        // TODO: Implement flagging logic
        if (this.onFlag) this.onFlag(this.currentData);
    }

    rejectSync() {
        this.updateStatus('Sync rejected');
        // TODO: Implement rejection logic
        if (this.onReject) this.onReject(this.currentData);
    }

    exportResults() {
        if (!this.currentData) return;
        
        const results = {
            masterFile: this.currentData.masterFile,
            dubFile: this.currentData.dubFile,
            detectedOffset: this.currentData.detectedOffset,
            confidence: this.currentData.confidence,
            timestamp: new Date().toISOString(),
            status: 'exported'
        };
        
        const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `qc-results-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.updateStatus('Results exported');
    }
    
    /**
     * Draw a basic offset indicator when waveform data is unavailable
     */
    drawOffsetIndicator(ctx, canvas, offset, isAfterView) {
        const width = canvas.width;
        const height = canvas.height;
        const centerY = height / 2;
        
        // Draw timeline
        ctx.strokeStyle = '#4b5563';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, centerY);
        ctx.lineTo(width, centerY);
        ctx.stroke();
        
        // Draw master indicator (at center)
        ctx.fillStyle = '#4ade80';
        ctx.fillRect(width / 2 - 2, centerY - 40, 4, 80);
        ctx.font = '12px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('MASTER', width / 2, centerY - 50);
        
        // Calculate dub position based on offset
        const visualOffset = isAfterView ? 0 : offset;
        const dubX = width / 2 + (visualOffset * 20); // Scale factor for visibility
        
        // Draw dub indicator
        ctx.fillStyle = '#f87171';
        ctx.fillRect(Math.max(10, Math.min(width - 10, dubX)) - 2, centerY - 40, 4, 80);
        ctx.fillText('DUB', Math.max(30, Math.min(width - 30, dubX)), centerY + 60);
        
        // Draw offset label
        if (!isAfterView && Math.abs(offset) > 0.001) {
            ctx.fillStyle = '#fbbf24';
            ctx.font = 'bold 14px Arial';
            ctx.fillText(`Offset: ${offset.toFixed(3)}s`, width / 2, height - 20);
        }
    }
}

// Export for global access
window.QCInterface = QCInterface;

// Add a simple test function
window.testQCModal = () => {
    console.log('Testing QC modal opening...');
    const testData = {
        masterFile: 'test-master.wav',
        dubFile: 'test-dub.wav',
        detectedOffset: 0.5,
        confidence: 0.85,
        masterUrl: null, // No audio files for test
        dubUrl: null
    };
    
    if (window.app && window.app.qcInterface) {
        window.app.qcInterface.open(testData);
    } else {
        console.error('QC Interface not found');
    }
};
