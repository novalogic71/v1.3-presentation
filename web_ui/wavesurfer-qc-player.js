/**
 * WaveSurfer Multitrack QC Player
 * Uses wavesurfer-multitrack for perfectly synchronized dual-track playback
 */

class WaveSurferQCPlayer {
    constructor(options = {}) {
        this.container = options.container || '#qc-wavesurfer-container';
        this.multitrack = null;
        this.offsetSeconds = 0;
        this.isCorrectedMode = false;
        this.isReady = false;
        this.masterUrl = null;
        this.dubUrl = null;
        
        // Track IDs
        this.MASTER_ID = 0;
        this.DUB_ID = 1;
        
        // Colors
        this.masterColor = '#4a90d9';
        this.masterProgressColor = '#2d5a87';
        this.dubColor = '#e94e77';
        this.dubProgressColor = '#8b2e47';
        
        // Volume state
        this.masterVolume = 1.0;
        this.dubVolume = 1.0;
        this.masterMuted = false;
        this.dubMuted = false;
        
        console.log('WaveSurferQCPlayer (multitrack) initialized');
    }
    
    /**
     * Initialize with audio URLs
     */
    async initialize(masterUrl, dubUrl, offsetSeconds = 0) {
        console.log('=== WaveSurfer Multitrack Initialize ===');
        console.log('  Master:', masterUrl);
        console.log('  Dub:', dubUrl);
        console.log('  Offset:', offsetSeconds);
        
        this.masterUrl = masterUrl;
        this.dubUrl = dubUrl;
        this.offsetSeconds = offsetSeconds;
        this.isReady = false;
        this.isCorrectedMode = false; // Start in "Before Fix" mode
        
        // Build with "Before Fix" view (both at 0)
        return await this._buildMultitrack(false);
    }
    
    /**
     * Wait for container element
     */
    async _waitForContainer() {
        const selector = typeof this.container === 'string' ? this.container : null;
        
        for (let i = 0; i < 50; i++) {
            const el = selector ? document.querySelector(selector) : this.container;
            if (el) return el;
            await new Promise(r => setTimeout(r, 100));
        }
        return null;
    }
    
    /**
     * Set corrected mode (adjusts dub track position visually)
     * Rebuilds the multitrack to show the offset
     */
    async setCorrectedMode(corrected) {
        if (this.isCorrectedMode === corrected && this.isReady) {
            return; // No change needed
        }
        
        this.isCorrectedMode = corrected;
        console.log('Mode:', corrected ? 'AFTER FIX (offset applied)' : 'BEFORE FIX (raw)');
        
        // Rebuild multitrack with new offset to show visual difference
        if (this.masterUrl && this.dubUrl) {
            await this._buildMultitrack(corrected);
        }
    }
    
    /**
     * Build/rebuild the multitrack with specified mode
     */
    async _buildMultitrack(corrected) {
        // Destroy existing
        if (this.multitrack) {
            try {
                this.multitrack.destroy();
            } catch (e) {}
            this.multitrack = null;
        }
        
        const container = await this._waitForContainer();
        if (!container) return false;
        
        container.innerHTML = '';
        
        if (typeof Multitrack === 'undefined') {
            console.error('Multitrack not loaded!');
            return false;
        }
        
        // Calculate dub start position based on mode
        // AFTER FIX: offset the dub so it aligns with master
        // BEFORE FIX: both start at 0 (shows the problem)
        const dubStartPosition = corrected ? this.offsetSeconds : 0;
        
        console.log(`Building multitrack: corrected=${corrected}, dubStart=${dubStartPosition.toFixed(3)}s`);
        
        try {
            this.multitrack = Multitrack.create(
                [
                    {
                        id: this.MASTER_ID,
                        url: this.masterUrl,
                        draggable: false,
                        startPosition: 0,
                        volume: this.masterMuted ? 0 : this.masterVolume,
                        options: {
                            waveColor: this.masterColor,
                            progressColor: this.masterProgressColor,
                            height: 80,
                        },
                    },
                    {
                        id: this.DUB_ID,
                        url: this.dubUrl,
                        draggable: false,
                        startPosition: dubStartPosition,
                        volume: this.dubMuted ? 0 : this.dubVolume,
                        options: {
                            waveColor: this.dubColor,
                            progressColor: this.dubProgressColor,
                            height: 80,
                        },
                    },
                ],
                {
                    container: container,
                    minPxPerSec: 50,
                    cursorWidth: 2,
                    cursorColor: '#fff',
                    trackBackground: '#1a1a2e',
                    trackBorderColor: '#333',
                }
            );
            
            return new Promise((resolve) => {
                this.multitrack.once('canplay', () => {
                    console.log('Multitrack rebuilt and ready');
                    this.isReady = true;
                    resolve(true);
                });
                
                setTimeout(() => {
                    if (!this.isReady) resolve(false);
                }, 10000);
            });
            
        } catch (error) {
            console.error('Multitrack build failed:', error);
            return false;
        }
    }
    
    /**
     * Play "Before Fix" - both tracks at same position (shows the sync problem)
     */
    async playBefore(startTime = 0) {
        console.log('WaveSurfer: playBefore - showing problem');
        await this.setCorrectedMode(false);
        this._play(startTime);
    }
    
    /**
     * Play "After Fix" - dub offset to show corrected alignment
     */
    async playAfter(startTime = 0) {
        console.log('WaveSurfer: playAfter - showing fix');
        await this.setCorrectedMode(true);
        this._play(startTime);
    }
    
    /**
     * Internal play
     */
    _play(startTime = 0) {
        if (!this.multitrack || !this.isReady) {
            console.error('Multitrack not ready');
            return;
        }
        
        // Stop first
        if (this.multitrack.isPlaying()) {
            this.multitrack.pause();
        }
        
        this.multitrack.setTime(startTime);
        this.multitrack.play();
        console.log('Playback started');
    }
    
    /**
     * Pause playback
     */
    pause() {
        if (this.multitrack) {
            this.multitrack.pause();
        }
    }
    
    /**
     * Stop playback
     */
    stop() {
        if (this.multitrack) {
            this.multitrack.pause();
            this.multitrack.setTime(0);
        }
    }
    
    /**
     * Seek to time
     */
    seek(timeSeconds) {
        if (this.multitrack) {
            this.multitrack.setTime(timeSeconds);
        }
    }
    
    /**
     * Get current time
     */
    getCurrentTime() {
        return this.multitrack ? this.multitrack.getCurrentTime() : 0;
    }
    
    /**
     * Get duration
     */
    getDuration() {
        // Return longest track duration
        return this.multitrack ? this.multitrack.getDuration() : 0;
    }
    
    /**
     * Is playing
     */
    isPlaying() {
        return this.multitrack ? this.multitrack.isPlaying() : false;
    }
    
    // Volume controls
    setMasterVolume(volume) {
        this.masterVolume = volume;
        this._applyVolumes();
    }
    
    setDubVolume(volume) {
        this.dubVolume = volume;
        this._applyVolumes();
    }
    
    setMasterMuted(muted) {
        this.masterMuted = muted;
        this._applyVolumes();
    }
    
    setDubMuted(muted) {
        this.dubMuted = muted;
        this._applyVolumes();
    }
    
    _applyVolumes() {
        if (!this.multitrack) return;
        
        // wavesurfer-multitrack volume control via tracks
        // The volume is set per-track in the initial config
        // For dynamic volume changes, we need to access the underlying wavesurfer instances
        try {
            const tracks = this.multitrack.wavesurfers || [];
            if (tracks[this.MASTER_ID]) {
                tracks[this.MASTER_ID].setVolume(this.masterMuted ? 0 : this.masterVolume);
            }
            if (tracks[this.DUB_ID]) {
                tracks[this.DUB_ID].setVolume(this.dubMuted ? 0 : this.dubVolume);
            }
        } catch (e) {
            console.warn('Could not apply volumes:', e);
        }
    }
    
    /**
     * Destroy player
     */
    destroy() {
        if (this.multitrack) {
            this.multitrack.destroy();
            this.multitrack = null;
        }
        this.isReady = false;
    }
}

// Export for use
if (typeof window !== 'undefined') {
    window.WaveSurferQCPlayer = WaveSurferQCPlayer;
}
