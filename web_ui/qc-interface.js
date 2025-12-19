/**
 * Quality Control Interface for Audio Sync Analysis
 * Dedicated interface for reviewing and playing back sync analysis results
 */

class QCInterface {
    constructor() {
        this.audioEngine = null;
        this.currentData = null;
        this.isVisible = false;

        this.initializeModal();
        this.setupEventListeners();
    }

    /**
     * Convert seconds to SMPTE timecode format HH:MM:SS:FF
     * @param {number} seconds - Time in seconds
     * @param {number} fps - Frame rate (default: 23.976)
     * @returns {string} Timecode string
     */
    formatTimecode(seconds, fps = 23.976) {
        const sign = seconds < 0 ? '-' : '';
        const absSeconds = Math.abs(seconds);

        const hours = Math.floor(absSeconds / 3600);
        const minutes = Math.floor((absSeconds % 3600) / 60);
        const secs = Math.floor(absSeconds % 60);
        const frames = Math.floor((absSeconds % 1) * fps);

        return `${sign}${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
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
                            <div class="qc-view-toggle">
                                <button class="qc-toggle-btn active" data-view="before" title="Show waveforms with detected sync offset">
                                    <i class="fas fa-exclamation-triangle"></i> Before Fix
                                </button>
                                <button class="qc-toggle-btn" data-view="after" title="Show waveforms aligned and synchronized">
                                    <i class="fas fa-check-circle"></i> After Fix
                                </button>
                            </div>
                        </div>
                        
                        <div class="qc-waveform-display" style="position:relative;">
                            <canvas id="qc-waveform-canvas" width="800" height="300"></canvas>
                            <div class="qc-waveform-overlay" style="position:absolute;left:0;top:0;right:0;bottom:0;z-index:5;pointer-events:auto;">
                                <div class="qc-scene-bands" id="qc-scene-bands" style="position:absolute;left:0;top:0;right:0;bottom:0;display:flex;gap:2px;z-index:6;"></div>
                                <div class="qc-drift-markers" id="qc-drift-markers" style="position:absolute;left:0;bottom:0;right:0;height:100%;z-index:6;"></div>
                                <div class="qc-playhead" id="qc-playhead"></div>
                                <div class="qc-offset-marker" id="qc-offset-marker"></div>
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
            this.audioEngine = new CoreAudioEngine();
            this.audioEngine.onProgress = (message, percentage) => {
                this.updateStatus(`${message} (${percentage}%)`);
            };
            this.audioEngine.onError = (error) => {
                console.error('QC Audio Engine Error:', error);
                this.updateStatus(`Audio Error: ${error}`, 'error');
            };
            this.audioEngine.onAudioLoaded = (type, data) => {
                console.log(`QC Interface: ${type} audio loaded`, data);
                this.updateWaveform();
                this.updateStatus(`${type} audio ready`);
            };
            
            console.log('QC Interface: Audio engine initialized');
        } catch (error) {
            console.error('Failed to initialize QC audio engine:', error);
            this.updateStatus('Audio engine initialization failed - visual review only', 'error');
        }
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

        // View toggle buttons
        document.addEventListener('click', (e) => {
            const toggleBtn = e.target.closest('.qc-toggle-btn');
            if (toggleBtn) {
                document.querySelectorAll('.qc-toggle-btn').forEach(btn => btn.classList.remove('active'));
                toggleBtn.classList.add('active');
                this.updateWaveform();
            }
        });

        // Volume controls
        document.addEventListener('input', (e) => {
            if (e.target.classList.contains('qc-volume-slider')) {
                const track = e.target.dataset.track;
                const value = parseFloat(e.target.value);
                this.audioEngine?.setVolume(track, value);
                e.target.nextElementSibling.textContent = Math.round(value * 100) + '%';
            } else if (e.target.classList.contains('qc-balance-slider')) {
                const value = parseFloat(e.target.value);
                this.audioEngine?.setBalance(value);
                const label = value < -0.1 ? 'Left' : value > 0.1 ? 'Right' : 'Center';
                e.target.nextElementSibling.textContent = label;
            }
        });

        // Mute toggles
        document.addEventListener('change', (e) => {
            if (e.target.classList.contains('qc-mute-toggle')) {
                const track = e.target.dataset.track;
                const muted = e.target.checked;
                this.audioEngine?.setMute(track, muted);
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
    }

    async open(syncData) {
        console.log('QC Interface opening with data:', syncData);
        this.currentData = syncData;
        this.isVisible = true;
        
        // Show modal immediately
        document.getElementById('qc-modal').style.display = 'flex';
        this.updateStatus('Opening QC Interface...');
        
        // Update UI with sync data
        this.updateFileInfo(syncData);
        
        // Load audio files asynchronously (don't block modal opening)
        this.loadAudioFilesAsync(syncData);
        
        console.log('QC Interface modal opened');
    }

    close() {
        this.isVisible = false;
        this.stopPlayback();
        const modal = document.getElementById('qc-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        this.currentData = null;
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

    updateFileInfo(syncData) {
        document.getElementById('qc-master-file').textContent = syncData.masterFile || 'Unknown';
        document.getElementById('qc-dub-file').textContent = syncData.dubFile || 'Unknown';

        const offset = syncData.detectedOffset || 0;
        const fps = syncData.frameRate || 23.976;
        const frames = Math.round(Math.abs(offset) * fps);
        const frameSign = offset < 0 ? '-' : '+';
        const timecode = this.formatTimecode(offset, fps);
        document.getElementById('qc-offset-value').textContent = `${timecode} (${frameSign}${frames}f @ ${fps}fps)`;

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
            this.updateStatus('No audio URLs provided - QC interface ready for visual review only', 'warning');
            return;
        }

        try {
            // Show loading state
            this.updateStatus('Loading audio files...');
            console.log('Loading audio from URLs:', {
                masterUrl: syncData.masterUrl,
                dubUrl: syncData.dubUrl
            });
            
            // Check if using proxy (video files) - give user heads up
            const usingProxy = syncData.masterUrl?.includes('proxy-audio') || syncData.dubUrl?.includes('proxy-audio');
            if (usingProxy) {
                this.updateStatus('Extracting audio from video files - this may take a moment...');
            }
            
            // Create loading promises with timeout (longer for video files)
            // Note: proxy-audio now limits to 10 min max, so 120s should be plenty
            const timeoutMs = usingProxy ? 120000 : 60000; // 120s for video, 60s for audio
            const loadWithTimeout = (url, type) => {
                const loadPromise = this.audioEngine.loadAudioUrl(url, type);
                const timeoutPromise = new Promise((_, reject) => 
                    setTimeout(() => reject(new Error(`${type} loading timeout after ${timeoutMs/1000}s`)), timeoutMs)
                );
                return Promise.race([loadPromise, timeoutPromise]);
            };
            
            // Load files in background with timeout
            const masterPromise = loadWithTimeout(syncData.masterUrl, 'master').catch(e => {
                console.warn('Master audio load failed:', e);
                return null;
            });
            
            const dubPromise = loadWithTimeout(syncData.dubUrl, 'dub').catch(e => {
                console.warn('Dub audio load failed:', e);
                return null;
            });
            
            // Update status during loading
            const updateInterval = setInterval(() => {
                this.updateStatus('Still loading audio files...');
            }, 3000);
            
            // Wait for both (or their failures)
            const [masterResult, dubResult] = await Promise.allSettled([masterPromise, dubPromise]);
            clearInterval(updateInterval);
            
            let loadedCount = 0;
            let loadedFiles = [];
            if (masterResult.status === 'fulfilled' && masterResult.value !== null) {
                loadedCount++;
                loadedFiles.push('master');
            }
            if (dubResult.status === 'fulfilled' && dubResult.value !== null) {
                loadedCount++;
                loadedFiles.push('dub');
            }
            
            if (loadedCount === 2) {
                this.updateStatus('Audio files loaded successfully - ready for playback');
            } else if (loadedCount === 1) {
                this.updateStatus(`${loadedFiles[0]} audio loaded - limited playback available`, 'warning');
            } else {
                this.updateStatus('Audio loading failed - visual review only', 'error');
            }
            
            console.log('Audio loading completed:', {
                loadedCount,
                loadedFiles,
                masterSuccess: masterResult.status === 'fulfilled',
                dubSuccess: dubResult.status === 'fulfilled'
            });
            
        } catch (error) {
            console.error('Audio loading error:', error);
            this.updateStatus('Audio loading failed - visual review only', 'error');
        }
        // Render drift markers once data is known
        try { this.renderDriftMarkers(); } catch {}
        try { this.renderSceneBands(); } catch {}
    }

    updateWaveform() {
        const canvas = document.getElementById('qc-waveform-canvas');
        const ctx = canvas.getContext('2d');
        const isAfterView = document.querySelector('.qc-toggle-btn[data-view="after"]').classList.contains('active');
        
        // Clear canvas
        ctx.fillStyle = '#1a1a1a';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Draw waveforms with offset visualization
        if (this.audioEngine?.masterWaveformData && this.audioEngine?.dubWaveformData) {
            this.drawWaveformComparison(ctx, canvas, isAfterView);
        } else {
            // Draw placeholder
            ctx.fillStyle = '#666';
            ctx.font = '16px Arial';
            ctx.textAlign = 'center';
            ctx.fillText('Load audio files to view waveforms', canvas.width / 2, canvas.height / 2);
        }
        // Update overlays to match current width
        this.renderDriftMarkers();
        this.renderSceneBands();
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
        
        // Use natural audio (Before) and simulate correction for After by applying detected offset
        const visualOffset = isAfterView ? offset : 0;
        
        // Use consistent time scale for both waveforms
        const maxDuration = Math.max(masterData.duration, dubData.duration);
        const offsetPixels = (visualOffset / maxDuration) * width;
        
        // Draw master waveform (top half - always starts at 0)
        ctx.strokeStyle = '#4ade80'; // green
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < masterData.peaks.length; i++) {
            // Scale master waveform based on its actual duration relative to max duration
            const x = (i / masterData.peaks.length) * (masterData.duration / maxDuration) * width;
            const y = centerY - (masterData.peaks[i] * waveHeight);
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
            const y = centerY + (dubData.peaks[i] * waveHeight);
            
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
                const fps = this.currentData?.frameRate || 23.976;
                const frames = Math.round(Math.abs(offset) * fps);
                const frameSign = offset < 0 ? '-' : '+';
                const timecode = this.formatTimecode(offset, fps);
                const offsetText = `Sync Problem: ${timecode} (${frameSign}${frames}f @ ${fps}fps) ${offset > 0 ? 'dub early' : 'dub late'}`;
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

    playComparison(corrected = false) {
        if (!this.audioEngine) {
            this.updateStatus('Audio engine not available', 'error');
            return;
        }

        const detectedOffset = this.currentData?.detectedOffset || 0;
        const fps = this.currentData?.frameRate || 23.976;
        const frames = Math.round(Math.abs(detectedOffset) * fps);
        const frameSign = detectedOffset < 0 ? '-' : '+';
        const timecode = this.formatTimecode(detectedOffset, fps);
        const offsetDisplay = `${timecode} (${frameSign}${frames}f @ ${fps}fps)`;

        // Play button logic (normal - not reversed):
        // Before Fix button: Play natural sync problem
        // After Fix button: Play corrected/synchronized version

        if (corrected) {
            // After Fix button pressed - play corrected version
            this.updateStatus('Playing with correction applied - synchronized (After Fix)');
        } else {
            // Before Fix button pressed - play natural problem
            if (detectedOffset > 0) {
                this.updateStatus(`Playing natural sync problem: dub is ${offsetDisplay} early (Before Fix)`);
            } else if (detectedOffset < 0) {
                this.updateStatus(`Playing natural sync problem: dub is ${offsetDisplay} late (Before Fix)`);
            } else {
                this.updateStatus('Playing - no sync offset detected (Before Fix)');
            }
        }
        
        try {
            this.audioEngine.playComparison(detectedOffset, corrected);
        } catch (error) {
            console.error('Playback error:', error);
            this.updateStatus(`Playback error: ${error.message}`, 'error');
        }
    }

    stopPlayback() {
        if (this.audioEngine) {
            this.audioEngine.stopPlayback();
            this.updateStatus('Playback stopped');
        }
    }

    togglePlayback() {
        if (this.audioEngine?.isPlaying) {
            this.stopPlayback();
        } else {
            const isAfterView = document.querySelector('.qc-toggle-btn[data-view="after"]').classList.contains('active');
            this.playComparison(isAfterView);
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
            const fps = this.currentData?.frameRate || 23.976;
            const frames = Math.round(Math.abs(offset) * fps);
            const frameSign = offset < 0 ? '-' : '+';
            const timecode = this.formatTimecode(offset, fps);
            m.title = `${start.toFixed(2)}s → ${end.toFixed(2)}s • ${timecode} (${frameSign}${frames}f @ ${fps}fps)` + (seg.reliable ? ' • reliable' : '');
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
