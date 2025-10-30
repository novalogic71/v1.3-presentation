/**
 * Repair Preview Interface
 * 
 * Provides UI components for previewing sync corrections before applying repairs.
 * Integrates with SmartPlaybackEngine for real-time correction preview.
 */

class RepairPreviewInterface {
    constructor() {
        this.playbackEngine = null;
        this.analysisData = null;
        this.isInitialized = false;
        this.currentMode = 'original';
        
        // UI state
        this.isPlaying = false;
        this.currentTime = 0;
        this.duration = 0;
        
        // Visualization
        this.waveformCanvas = null;
        this.waveformContext = null;
        this.segmentMarkers = [];
        
        this.setupEventListeners();
    }
    
    async initialize(masterUrl, dubUrl, analysisData) {
        /**
         * Initialize the repair preview interface
         * 
         * @param {string} masterUrl - URL to master audio file
         * @param {string} dubUrl - URL to dub audio file  
         * @param {Object} analysisData - Sync analysis results
         */
        try {
            console.log('Initializing repair preview interface...');
            
            // Store analysis data
            this.analysisData = analysisData;
            
            // Initialize playback engine
            this.playbackEngine = new SmartPlaybackEngine();
            
            // Load audio files
            const audioInfo = await this.playbackEngine.loadAudioFiles(masterUrl, dubUrl);
            this.duration = Math.max(audioInfo.masterDuration, audioInfo.dubDuration);
            
            // Load correction data
            const correctionInfo = this.playbackEngine.loadCorrectionData(analysisData);
            
            // Create UI components
            this.createInterface();
            
            // Setup waveform visualization
            this.setupWaveformVisualization();
            
            // Update UI with correction info
            this.updateCorrectionInfo(correctionInfo);
            
            this.isInitialized = true;
            console.log('Repair preview interface initialized successfully');
            
        } catch (error) {
            console.error('Failed to initialize repair preview interface:', error);
            throw error;
        }
    }
    
    createInterface() {
        /**
         * Create the UI components for repair preview
         */
        const container = document.getElementById('repair-preview-container');
        if (!container) {
            console.error('Repair preview container not found');
            return;
        }
        
        container.innerHTML = `
            <div class="repair-preview-interface">
                <div class="preview-header">
                    <h3>🔧 Repair Preview</h3>
                    <div class="correction-info">
                        <span id="repair-type">Analyzing...</span>
                        <span id="offset-info">Offset: --</span>
                    </div>
                </div>
                
                <div class="playback-controls">
                    <div class="mode-selector">
                        <label>Playback Mode:</label>
                        <select id="playback-mode-select">
                            <option value="original">Original (No Correction)</option>
                            <option value="corrected">Corrected (Preview Repair)</option>
                            <option value="preview">Preview (With Indicators)</option>
                        </select>
                    </div>
                    
                    <div class="transport-controls">
                        <button id="play-pause-btn" class="transport-btn">
                            <span class="play-icon">▶️</span>
                        </button>
                        <button id="stop-btn" class="transport-btn">⏹️</button>
                        <div class="time-display">
                            <span id="current-time">00:00</span> / <span id="total-time">00:00</span>
                        </div>
                    </div>
                </div>
                
                <div class="waveform-container">
                    <canvas id="waveform-canvas" width="800" height="200"></canvas>
                    <div class="playhead" id="playhead"></div>
                    <div class="segment-overlay" id="segment-overlay"></div>
                </div>
                
                <div class="audio-controls">
                    <div class="volume-controls">
                        <div class="volume-control">
                            <label>Master Volume:</label>
                            <input type="range" id="master-volume" min="0" max="1" step="0.1" value="0.8">
                            <span id="master-volume-value">80%</span>
                        </div>
                        <div class="volume-control">
                            <label>Dub Volume:</label>
                            <input type="range" id="dub-volume" min="0" max="1" step="0.1" value="0.8">
                            <span id="dub-volume-value">80%</span>
                        </div>
                    </div>
                    
                    <div class="pan-controls">
                        <div class="pan-control">
                            <label>Master Pan:</label>
                            <input type="range" id="master-pan" min="-1" max="1" step="0.1" value="-0.5">
                            <span id="master-pan-value">L50%</span>
                        </div>
                        <div class="pan-control">
                            <label>Dub Pan:</label>
                            <input type="range" id="dub-pan" min="-1" max="1" step="0.1" value="0.5">
                            <span id="dub-pan-value">R50%</span>
                        </div>
                    </div>
                </div>
                
                <div class="segment-info" id="segment-info">
                    <h4>Current Segment</h4>
                    <div class="segment-details">
                        <span id="segment-time">--</span>
                        <span id="segment-offset">--</span>
                        <span id="segment-quality">--</span>
                    </div>
                </div>
                
                <div class="correction-timeline" id="correction-timeline">
                    <h4>Correction Timeline</h4>
                    <div class="timeline-legend">
                        <span class="legend-item"><span class="marker excellent"></span> Excellent</span>
                        <span class="legend-item"><span class="marker good"></span> Good</span>
                        <span class="legend-item"><span class="marker fair"></span> Fair</span>
                        <span class="legend-item"><span class="marker poor"></span> Poor</span>
                    </div>
                </div>
                
                <div class="preview-actions">
                    <button id="apply-repair-btn" class="action-btn primary">Apply Repair</button>
                    <button id="export-package-btn" class="action-btn">Create Package</button>
                    <button id="close-preview-btn" class="action-btn secondary">Close Preview</button>
                </div>
            </div>
        `;
        
        this.setupUIEventListeners();
    }
    
    setupUIEventListeners() {
        /**
         * Setup event listeners for UI components
         */
        // Playback mode selector
        document.getElementById('playback-mode-select').addEventListener('change', (e) => {
            this.switchPlaybackMode(e.target.value);
        });
        
        // Transport controls
        document.getElementById('play-pause-btn').addEventListener('click', () => {
            this.togglePlayPause();
        });
        
        document.getElementById('stop-btn').addEventListener('click', () => {
            this.stopPlayback();
        });
        
        // Volume controls
        document.getElementById('master-volume').addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.setMasterVolume(value);
            document.getElementById('master-volume-value').textContent = `${Math.round(value * 100)}%`;
        });
        
        document.getElementById('dub-volume').addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.setDubVolume(value);
            document.getElementById('dub-volume-value').textContent = `${Math.round(value * 100)}%`;
        });
        
        // Pan controls
        document.getElementById('master-pan').addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.setMasterPan(value);
            this.updatePanDisplay('master-pan-value', value);
        });
        
        document.getElementById('dub-pan').addEventListener('input', (e) => {
            const value = parseFloat(e.target.value);
            this.setDubPan(value);
            this.updatePanDisplay('dub-pan-value', value);
        });
        
        // Action buttons
        document.getElementById('apply-repair-btn').addEventListener('click', () => {
            this.applyRepair();
        });
        
        document.getElementById('export-package-btn').addEventListener('click', () => {
            this.exportPackage();
        });
        
        document.getElementById('close-preview-btn').addEventListener('click', () => {
            this.closePreview();
        });
        
        // Waveform canvas click for seeking
        const canvas = document.getElementById('waveform-canvas');
        if (canvas) {
            canvas.addEventListener('click', (e) => {
                this.handleWaveformClick(e);
            });
        }
    }
    
    setupEventListeners() {
        /**
         * Setup global event listeners for playback engine events
         */
        document.addEventListener('segmentTransition', (e) => {
            this.handleSegmentTransition(e.detail);
        });
        
        document.addEventListener('previewUpdate', (e) => {
            this.handlePreviewUpdate(e.detail);
        });
    }
    
    setupWaveformVisualization() {
        /**
         * Setup waveform visualization canvas
         */
        const canvas = document.getElementById('waveform-canvas');
        if (!canvas) return;
        
        this.waveformCanvas = canvas;
        this.waveformContext = canvas.getContext('2d');
        
        // Draw basic timeline
        this.drawWaveform();
        
        // Draw correction segments
        this.drawCorrectionSegments();
    }
    
    drawWaveform() {
        /**
         * Draw basic waveform visualization
         */
        const ctx = this.waveformContext;
        const canvas = this.waveformCanvas;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // Draw time grid
        ctx.strokeStyle = '#e0e0e0';
        ctx.lineWidth = 1;
        
        const timeInterval = this.duration > 300 ? 60 : 30; // 1min or 30s intervals
        const pixelsPerSecond = canvas.width / this.duration;
        
        for (let time = 0; time <= this.duration; time += timeInterval) {
            const x = time * pixelsPerSecond;
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, canvas.height);
            ctx.stroke();
            
            // Time labels
            ctx.fillStyle = '#666';
            ctx.font = '10px Arial';
            ctx.fillText(this.formatTime(time), x + 2, 12);
        }
        
        // Draw center line
        ctx.strokeStyle = '#ccc';
        ctx.beginPath();
        ctx.moveTo(0, canvas.height / 2);
        ctx.lineTo(canvas.width, canvas.height / 2);
        ctx.stroke();
    }
    
    drawCorrectionSegments() {
        /**
         * Draw correction segments on the waveform
         */
        if (!this.analysisData || !this.analysisData.timeline) return;
        
        const ctx = this.waveformContext;
        const canvas = this.waveformCanvas;
        const pixelsPerSecond = canvas.width / this.duration;
        
        // Clear segment overlay
        const segmentOverlay = document.getElementById('segment-overlay');
        if (segmentOverlay) {
            segmentOverlay.innerHTML = '';
        }
        
        // Draw segments
        this.analysisData.timeline.forEach((segment, index) => {
            const startX = segment.start_time * pixelsPerSecond;
            const endX = segment.end_time * pixelsPerSecond;
            const width = endX - startX;
            
            // Determine color based on quality
            let color = '#ff6b6b'; // Poor - red
            if (segment.quality === 'Excellent') color = '#51cf66';
            else if (segment.quality === 'Good') color = '#69db7c';
            else if (segment.quality === 'Fair') color = '#ffd43b';
            
            // Draw segment background
            ctx.fillStyle = color + '40'; // 25% opacity
            ctx.fillRect(startX, 0, width, canvas.height);
            
            // Draw segment border
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.strokeRect(startX, 0, width, canvas.height);
            
            // Add interactive segment marker
            if (segmentOverlay && width > 20) { // Only show markers for visible segments
                const marker = document.createElement('div');
                marker.className = `segment-marker ${segment.quality.toLowerCase()}`;
                marker.style.left = `${startX}px`;
                marker.style.width = `${width}px`;
                marker.title = `${this.formatTime(segment.start_time)}-${this.formatTime(segment.end_time)}: ${segment.offset_seconds.toFixed(3)}s offset (${segment.quality})`;
                marker.addEventListener('click', () => {
                    this.seekToTime(segment.start_time);
                });
                segmentOverlay.appendChild(marker);
            }
        });
    }
    
    updateCorrectionInfo(correctionInfo) {
        /**
         * Update the correction information display
         */
        const repairTypeEl = document.getElementById('repair-type');
        const offsetInfoEl = document.getElementById('offset-info');
        
        if (repairTypeEl) {
            let repairTypeText = 'No Correction';
            switch (correctionInfo.repairType) {
                case 'simple_offset':
                    repairTypeText = 'Simple Offset';
                    break;
                case 'gradual':
                    repairTypeText = 'Gradual Correction';
                    break;
                case 'time_variable':
                    repairTypeText = 'Time-Variable Correction';
                    break;
            }
            repairTypeEl.textContent = repairTypeText;
        }
        
        if (offsetInfoEl) {
            const fps = this.syncData?.frameRate || 24;
            const frames = Math.round(Math.abs(correctionInfo.overallOffset) * fps);
            const frameSign = correctionInfo.overallOffset < 0 ? '-' : '+';
            offsetInfoEl.textContent = `Offset: ${correctionInfo.overallOffset >= 0 ? '+' : ''}${correctionInfo.overallOffset.toFixed(3)}s (${frameSign}${frames}f @ ${fps}fps)`;
        }
        
        // Update total time display
        const totalTimeEl = document.getElementById('total-time');
        if (totalTimeEl) {
            totalTimeEl.textContent = this.formatTime(this.duration);
        }
    }
    
    async switchPlaybackMode(mode) {
        /**
         * Switch between playback modes
         */
        const wasPlaying = this.isPlaying;
        const currentTime = this.currentTime;
        
        if (wasPlaying) {
            await this.playbackEngine.stopPlayback();
        }
        
        this.currentMode = mode;
        
        if (wasPlaying) {
            await this.playbackEngine.startPlayback(mode, currentTime);
        }
        
        console.log(`Switched to ${mode} playback mode`);
    }
    
    async togglePlayPause() {
        /**
         * Toggle between play and pause
         */
        if (!this.playbackEngine) return;
        
        try {
            if (this.isPlaying) {
                this.playbackEngine.pausePlayback();
                this.isPlaying = false;
                this.updatePlayButton(false);
            } else {
                await this.playbackEngine.startPlayback(this.currentMode, this.currentTime);
                this.isPlaying = true;
                this.updatePlayButton(true);
                this.startTimeUpdates();
            }
        } catch (error) {
            console.error('Failed to toggle playback:', error);
        }
    }
    
    async stopPlayback() {
        /**
         * Stop playback and reset position
         */
        if (!this.playbackEngine) return;
        
        this.playbackEngine.stopPlayback();
        this.isPlaying = false;
        this.currentTime = 0;
        this.updatePlayButton(false);
        this.updateTimeDisplay(0);
        this.updatePlayhead(0);
    }
    
    async seekToTime(timeSeconds) {
        /**
         * Seek to specific time
         */
        if (!this.playbackEngine) return;
        
        this.currentTime = timeSeconds;
        this.playbackEngine.seekTo(timeSeconds);
        this.updateTimeDisplay(timeSeconds);
        this.updatePlayhead(timeSeconds);
    }
    
    handleWaveformClick(event) {
        /**
         * Handle clicks on waveform for seeking
         */
        const canvas = this.waveformCanvas;
        const rect = canvas.getBoundingClientRect();
        const x = event.clientX - rect.left;
        const timeSeconds = (x / canvas.width) * this.duration;
        
        this.seekToTime(timeSeconds);
    }
    
    setMasterVolume(volume) {
        if (this.playbackEngine) {
            const dubVolume = parseFloat(document.getElementById('dub-volume').value);
            this.playbackEngine.setVolume(volume, dubVolume);
        }
    }
    
    setDubVolume(volume) {
        if (this.playbackEngine) {
            const masterVolume = parseFloat(document.getElementById('master-volume').value);
            this.playbackEngine.setVolume(masterVolume, volume);
        }
    }
    
    setMasterPan(pan) {
        if (this.playbackEngine) {
            const dubPan = parseFloat(document.getElementById('dub-pan').value);
            this.playbackEngine.setPanning(pan, dubPan);
        }
    }
    
    setDubPan(pan) {
        if (this.playbackEngine) {
            const masterPan = parseFloat(document.getElementById('master-pan').value);
            this.playbackEngine.setPanning(masterPan, pan);
        }
    }
    
    updatePanDisplay(elementId, value) {
        /**
         * Update pan control display
         */
        const element = document.getElementById(elementId);
        if (element) {
            if (value < -0.05) {
                element.textContent = `L${Math.round(Math.abs(value) * 100)}%`;
            } else if (value > 0.05) {
                element.textContent = `R${Math.round(value * 100)}%`;
            } else {
                element.textContent = 'Center';
            }
        }
    }
    
    updatePlayButton(isPlaying) {
        /**
         * Update play/pause button appearance
         */
        const playIcon = document.querySelector('#play-pause-btn .play-icon');
        if (playIcon) {
            playIcon.textContent = isPlaying ? '⏸️' : '▶️';
        }
    }
    
    updateTimeDisplay(timeSeconds) {
        /**
         * Update current time display
         */
        const currentTimeEl = document.getElementById('current-time');
        if (currentTimeEl) {
            currentTimeEl.textContent = this.formatTime(timeSeconds);
        }
    }
    
    updatePlayhead(timeSeconds) {
        /**
         * Update playhead position
         */
        const playhead = document.getElementById('playhead');
        if (playhead && this.waveformCanvas) {
            const progress = timeSeconds / this.duration;
            const x = progress * this.waveformCanvas.width;
            playhead.style.left = `${x}px`;
        }
    }
    
    startTimeUpdates() {
        /**
         * Start periodic time updates during playback
         */
        const updateInterval = setInterval(() => {
            if (!this.isPlaying) {
                clearInterval(updateInterval);
                return;
            }
            
            if (this.playbackEngine) {
                this.currentTime = this.playbackEngine.getCurrentTime();
                this.updateTimeDisplay(this.currentTime);
                this.updatePlayhead(this.currentTime);
                this.updateSegmentInfo();
            }
        }, 100);
    }
    
    updateSegmentInfo() {
        /**
         * Update current segment information display
         */
        if (!this.playbackEngine) return;
        
        const currentSegment = this.playbackEngine.getCurrentSegment(this.currentTime);
        const segmentTimeEl = document.getElementById('segment-time');
        const segmentOffsetEl = document.getElementById('segment-offset');
        const segmentQualityEl = document.getElementById('segment-quality');
        
        if (currentSegment) {
            if (segmentTimeEl) {
                segmentTimeEl.textContent = `${this.formatTime(currentSegment.startTime)} - ${this.formatTime(currentSegment.endTime)}`;
            }
            if (segmentOffsetEl) {
                const fps = this.syncData?.frameRate || 24;
                const frames = Math.round(Math.abs(currentSegment.offsetSeconds) * fps);
                const frameSign = currentSegment.offsetSeconds < 0 ? '-' : '+';
                segmentOffsetEl.textContent = `Offset: ${currentSegment.offsetSeconds >= 0 ? '+' : ''}${currentSegment.offsetSeconds.toFixed(3)}s (${frameSign}${frames}f @ ${fps}fps)`;
            }
            if (segmentQualityEl) {
                segmentQualityEl.textContent = `Quality: ${currentSegment.quality}`;
                segmentQualityEl.className = `quality ${currentSegment.quality.toLowerCase()}`;
            }
        } else {
            if (segmentTimeEl) segmentTimeEl.textContent = '--';
            if (segmentOffsetEl) segmentOffsetEl.textContent = '--';
            if (segmentQualityEl) segmentQualityEl.textContent = '--';
        }
    }
    
    handleSegmentTransition(detail) {
        /**
         * Handle segment transition events
         */
        console.log('Segment transition:', detail);
        this.updateSegmentInfo();
        
        // Visual feedback for segment transitions
        const segmentInfo = document.getElementById('segment-info');
        if (segmentInfo) {
            segmentInfo.classList.add('transition-highlight');
            setTimeout(() => {
                segmentInfo.classList.remove('transition-highlight');
            }, 500);
        }
    }
    
    handlePreviewUpdate(detail) {
        /**
         * Handle preview update events
         */
        // Update any preview-specific visualizations
        this.updatePlayhead(detail.currentTime);
    }
    
    async applyRepair() {
        /**
         * Apply the repair to the actual files
         */
        console.log('Applying repair...');
        
        // This would trigger the actual repair process
        // For now, just show a confirmation
        if (confirm('Apply sync repair to the file? This will create a new corrected version.')) {
            // Emit event for parent to handle repair
            const event = new CustomEvent('applyRepair', {
                detail: {
                    analysisData: this.analysisData,
                    repairType: this.playbackEngine.repairType
                }
            });
            document.dispatchEvent(event);
        }
    }
    
    async exportPackage() {
        /**
         * Export comprehensive repair package
         */
        console.log('Exporting package...');
        
        // Emit event for parent to handle package creation
        const event = new CustomEvent('exportPackage', {
            detail: {
                analysisData: this.analysisData,
                includePreview: true
            }
        });
        document.dispatchEvent(event);
    }
    
    closePreview() {
        /**
         * Close the repair preview interface
         */
        if (this.playbackEngine) {
            this.playbackEngine.stopPlayback();
        }
        
        // Hide the preview interface
        const container = document.getElementById('repair-preview-container');
        if (container) {
            container.style.display = 'none';
        }
        
        // Emit close event
        const event = new CustomEvent('closeRepairPreview');
        document.dispatchEvent(event);
    }
    
    formatTime(seconds) {
        /**
         * Format time in MM:SS format
         */
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
    }
    
    destroy() {
        /**
         * Clean up resources
         */
        if (this.playbackEngine) {
            this.playbackEngine.destroy();
        }
        
        console.log('Repair Preview Interface destroyed');
    }
}

// Export for use in other modules
window.RepairPreviewInterface = RepairPreviewInterface;