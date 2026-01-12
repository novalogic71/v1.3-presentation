/**
 * QC Player - Simple, reliable dual-audio player for sync comparison
 * Uses native HTML5 audio elements for maximum compatibility
 */

class QCPlayer {
    constructor() {
        this.masterAudio = null;
        this.dubAudio = null;
        this.offsetSeconds = 0;
        this.isPlaying = false;
        this.isCorrectedMode = false;
        this.syncInterval = null;
        
        // Volume/mute state
        this.masterVolume = 0.8;
        this.dubVolume = 0.8;
        this.masterMuted = false;
        this.dubMuted = false;
        
        // Callbacks
        this.onTimeUpdate = null;
        this.onStatusChange = null;
        this.onLoadProgress = null;
    }
    
    /**
     * Initialize player with audio URLs
     */
    async initialize(masterUrl, dubUrl, offsetSeconds = 0) {
        this.offsetSeconds = offsetSeconds;
        
        // Clean up any existing elements
        this.dispose();
        
        // Create audio elements
        this.masterAudio = this._createAudioElement('qc-master-audio');
        this.dubAudio = this._createAudioElement('qc-dub-audio');
        
        // Set up event listeners
        this._setupEventListeners();
        
        // Load audio
        const loadPromises = [];
        
        if (masterUrl) {
            this.masterAudio.src = masterUrl;
            loadPromises.push(this._waitForLoadedMetadata(this.masterAudio, 'master'));
        }
        
        if (dubUrl) {
            this.dubAudio.src = dubUrl;
            loadPromises.push(this._waitForLoadedMetadata(this.dubAudio, 'dub'));
        }
        
        try {
            await Promise.all(loadPromises);
            this._updateStatus('Audio loaded - ready for playback');
            return true;
        } catch (error) {
            console.error('QCPlayer: Failed to load audio:', error);
            this._updateStatus(`Load failed: ${error.message}`, 'error');
            return false;
        }
    }
    
    _createAudioElement(id) {
        // Remove existing element if any
        const existing = document.getElementById(id);
        if (existing) existing.remove();
        
        const audio = document.createElement('audio');
        audio.id = id;
        audio.preload = 'auto';
        // Don't set crossOrigin for same-origin requests (UI served from same server)
        // Setting it can cause CORS issues with streaming responses
        // audio.crossOrigin = 'anonymous';
        audio.style.display = 'none';
        document.body.appendChild(audio);
        return audio;
    }
    
    _waitForLoadedMetadata(audio, label) {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error(`${label} audio load timeout`));
            }, 60000); // 60s timeout for video files
            
            const onLoaded = () => {
                clearTimeout(timeout);
                console.log(`QCPlayer: ${label} loaded - duration: ${audio.duration?.toFixed(2)}s`);
                resolve();
            };
            
            const onError = (e) => {
                clearTimeout(timeout);
                reject(new Error(`${label} audio error: ${audio.error?.message || 'unknown'}`));
            };
            
            if (audio.readyState >= 1) {
                onLoaded();
            } else {
                audio.addEventListener('loadedmetadata', onLoaded, { once: true });
                audio.addEventListener('error', onError, { once: true });
                audio.load();
            }
        });
    }
    
    _setupEventListeners() {
        // Time update for playhead
        const onTimeUpdate = () => {
            if (this.onTimeUpdate) {
                this.onTimeUpdate({
                    masterTime: this.masterAudio?.currentTime || 0,
                    dubTime: this.dubAudio?.currentTime || 0,
                    masterDuration: this.masterAudio?.duration || 0,
                    dubDuration: this.dubAudio?.duration || 0,
                    isPlaying: this.isPlaying,
                    isCorrectedMode: this.isCorrectedMode
                });
            }
        };
        
        this.masterAudio?.addEventListener('timeupdate', onTimeUpdate);
        this.dubAudio?.addEventListener('timeupdate', onTimeUpdate);
        
        // Ended event
        const onEnded = () => {
            this.stop();
        };
        this.masterAudio?.addEventListener('ended', onEnded);
        this.dubAudio?.addEventListener('ended', onEnded);
    }
    
    /**
     * Play in "Before Fix" mode - shows the sync problem
     * Both files play from the same file position, so content is misaligned
     */
    playBefore(startTime = 0) {
        this.isCorrectedMode = false;
        this._play(startTime, false);
        this._updateStatus('Playing BEFORE fix - listen for sync problem');
    }
    
    /**
     * Play in "After Fix" mode - shows corrected sync
     * Dub is offset so content aligns with master
     */
    playAfter(startTime = 0) {
        this.isCorrectedMode = true;
        this._play(startTime, true);
        this._updateStatus('Playing AFTER fix - audio should be synchronized');
    }
    
    _play(startTime, corrected) {
        if (!this.masterAudio || !this.dubAudio) {
            this._updateStatus('Audio not loaded', 'error');
            return;
        }
        
        // Stop any current playback
        this.stop();
        
        const masterTime = Math.max(0, startTime);
        let dubTime = masterTime;
        
        if (corrected && this.offsetSeconds !== 0) {
            // Apply offset correction
            // If offset > 0: dub content at t=0 matches master at t=offset
            // So to align: dub should play from t+offset when master plays from t
            dubTime = masterTime + this.offsetSeconds;
            
            // Clamp to valid range
            dubTime = Math.max(0, Math.min(dubTime, (this.dubAudio.duration || 0) - 0.1));
        }
        
        console.log(`QCPlayer: Playing ${corrected ? 'AFTER' : 'BEFORE'} fix - master@${masterTime.toFixed(2)}s, dub@${dubTime.toFixed(2)}s (offset: ${this.offsetSeconds}s)`);
        
        // Set positions
        this.masterAudio.currentTime = masterTime;
        this.dubAudio.currentTime = dubTime;
        
        // Apply volume/mute
        this._applyVolumes();
        
        // Start playback
        const playMaster = this.masterAudio.play().catch(e => {
            console.warn('QCPlayer: Master play failed:', e);
            this._updateStatus('Master playback blocked - click to enable', 'warning');
        });
        
        const playDub = this.dubAudio.play().catch(e => {
            console.warn('QCPlayer: Dub play failed:', e);
            this._updateStatus('Dub playback blocked - click to enable', 'warning');
        });
        
        Promise.all([playMaster, playDub]).then(() => {
            this.isPlaying = true;
            this._startSyncMonitor(corrected);
            console.log('QCPlayer: Playback started successfully');
        }).catch(error => {
            console.error('QCPlayer: Playback failed:', error);
            this.isPlaying = false;
            this._updateStatus('Playback failed - try clicking play again', 'error');
        });
    }
    
    /**
     * Keep tracks synchronized during playback (for After Fix mode)
     */
    _startSyncMonitor(corrected) {
        this._stopSyncMonitor();
        
        if (!corrected) return; // No sync needed for Before mode
        
        this.syncInterval = setInterval(() => {
            if (!this.isPlaying || !this.masterAudio || !this.dubAudio) {
                this._stopSyncMonitor();
                return;
            }
            
            // Check sync drift and correct if needed
            const masterTime = this.masterAudio.currentTime;
            const expectedDubTime = masterTime + this.offsetSeconds;
            const actualDubTime = this.dubAudio.currentTime;
            const drift = Math.abs(expectedDubTime - actualDubTime);
            
            // Resync if drift exceeds 100ms
            if (drift > 0.1 && expectedDubTime > 0 && expectedDubTime < this.dubAudio.duration) {
                console.log(`QCPlayer: Resyncing - drift: ${(drift * 1000).toFixed(0)}ms`);
                this.dubAudio.currentTime = expectedDubTime;
            }
        }, 500); // Check every 500ms
    }
    
    _stopSyncMonitor() {
        if (this.syncInterval) {
            clearInterval(this.syncInterval);
            this.syncInterval = null;
        }
    }
    
    /**
     * Stop playback
     */
    stop() {
        this._stopSyncMonitor();
        
        if (this.masterAudio) {
            this.masterAudio.pause();
        }
        if (this.dubAudio) {
            this.dubAudio.pause();
        }
        
        this.isPlaying = false;
        this._updateStatus('Playback stopped');
    }
    
    /**
     * Seek to specific time
     */
    seek(time) {
        const masterTime = Math.max(0, time);
        let dubTime = masterTime;
        
        if (this.isCorrectedMode && this.offsetSeconds !== 0) {
            dubTime = masterTime + this.offsetSeconds;
            dubTime = Math.max(0, Math.min(dubTime, (this.dubAudio?.duration || 0) - 0.1));
        }
        
        if (this.masterAudio) {
            this.masterAudio.currentTime = masterTime;
        }
        if (this.dubAudio) {
            this.dubAudio.currentTime = dubTime;
        }
        
        // Trigger time update
        if (this.onTimeUpdate) {
            this.onTimeUpdate({
                masterTime: this.masterAudio?.currentTime || 0,
                dubTime: this.dubAudio?.currentTime || 0,
                masterDuration: this.masterAudio?.duration || 0,
                dubDuration: this.dubAudio?.duration || 0,
                isPlaying: this.isPlaying,
                isCorrectedMode: this.isCorrectedMode
            });
        }
    }
    
    /**
     * Set master volume (0-1)
     */
    setMasterVolume(value) {
        this.masterVolume = Math.max(0, Math.min(1, value));
        this._applyVolumes();
    }
    
    /**
     * Set dub volume (0-1)
     */
    setDubVolume(value) {
        this.dubVolume = Math.max(0, Math.min(1, value));
        this._applyVolumes();
    }
    
    /**
     * Toggle master mute
     */
    setMasterMuted(muted) {
        this.masterMuted = muted;
        this._applyVolumes();
    }
    
    /**
     * Toggle dub mute
     */
    setDubMuted(muted) {
        this.dubMuted = muted;
        this._applyVolumes();
    }
    
    _applyVolumes() {
        console.log(`QCPlayer._applyVolumes: master=${this.masterVolume} (muted=${this.masterMuted}), dub=${this.dubVolume} (muted=${this.dubMuted})`);
        if (this.masterAudio) {
            const masterVol = this.masterMuted ? 0 : this.masterVolume;
            this.masterAudio.volume = masterVol;
            console.log(`QCPlayer: Set master volume to ${masterVol}`);
        } else {
            console.warn('QCPlayer: masterAudio not available');
        }
        if (this.dubAudio) {
            const dubVol = this.dubMuted ? 0 : this.dubVolume;
            this.dubAudio.volume = dubVol;
            console.log(`QCPlayer: Set dub volume to ${dubVol}`);
        } else {
            console.warn('QCPlayer: dubAudio not available');
        }
    }
    
    /**
     * Get current playback info
     */
    getStatus() {
        return {
            isPlaying: this.isPlaying,
            isCorrectedMode: this.isCorrectedMode,
            masterTime: this.masterAudio?.currentTime || 0,
            dubTime: this.dubAudio?.currentTime || 0,
            masterDuration: this.masterAudio?.duration || 0,
            dubDuration: this.dubAudio?.duration || 0,
            offsetSeconds: this.offsetSeconds
        };
    }
    
    /**
     * Get duration (max of master and dub)
     */
    getDuration() {
        return Math.max(
            this.masterAudio?.duration || 0,
            this.dubAudio?.duration || 0
        );
    }
    
    _updateStatus(message, type = 'info') {
        console.log(`QCPlayer: ${message}`);
        if (this.onStatusChange) {
            this.onStatusChange(message, type);
        }
    }
    
    /**
     * Clean up resources
     */
    dispose() {
        this.stop();
        
        if (this.masterAudio) {
            this.masterAudio.pause();
            this.masterAudio.src = '';
            this.masterAudio.remove();
            this.masterAudio = null;
        }
        
        if (this.dubAudio) {
            this.dubAudio.pause();
            this.dubAudio.src = '';
            this.dubAudio.remove();
            this.dubAudio = null;
        }
    }
}

// Export for use
window.QCPlayer = QCPlayer;

