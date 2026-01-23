/**
 * Waveform QC Player - Multi-track audio player using waveform-playlist
 *
 * A robust, professional audio player for QC sync comparison
 * Built on waveform-playlist (https://github.com/naomiaro/waveform-playlist)
 */

class WaveformQCPlayer {
    constructor(options = {}) {
        this.container = options.container || document.getElementById('waveform-playlist-container');
        this.playlist = null;
        this.ee = null; // EventEmitter

        // Track state
        this.masterUrl = null;
        this.dubUrl = null;
        this.offsetSeconds = 0;
        this.isPlaying = false;
        this.isCorrectedMode = false;
        this.duration = 0;

        // Volume state
        this.masterVolume = 0.8;
        this.dubVolume = 0.8;
        this.masterMuted = false;
        this.dubMuted = false;

        // Callbacks
        this.onTimeUpdate = null;
        this.onReady = null;
        this.onError = null;
        this.onStatusChange = null;

        // Colors for tracks
        this.colors = {
            master: {
                waveOutlineColor: '#3b82f6',
                waveformColor: '#60a5fa'
            },
            dub: {
                waveOutlineColor: '#22c55e',
                waveformColor: '#4ade80'
            }
        };

        // Track loading state
        this._tracksLoaded = false;
    }

    /**
     * Initialize the waveform playlist
     */
    async initialize() {
        if (!this.container) {
            console.error('WaveformQCPlayer: No container element provided');
            return false;
        }

        // Check if WaveformPlaylist is available
        if (typeof WaveformPlaylist === 'undefined') {
            console.error('WaveformQCPlayer: waveform-playlist library not loaded');
            this._updateStatus('Waveform library not loaded', 'error');
            return false;
        }

        try {
            console.log('WaveformQCPlayer: Creating playlist instance, container:', this.container);

            // Create playlist instance with visible colors for dark theme
            this.playlist = WaveformPlaylist({
                container: this.container,
                samplesPerPixel: 500,
                mono: true,
                waveHeight: 80,
                state: 'cursor',
                timescale: true,
                isAutomaticScroll: true,
                colors: {
                    // Bright colors for visibility on dark background
                    waveOutlineColor: '#60a5fa',
                    timeColor: '#94a3b8',
                    fadeColor: 'rgba(96, 165, 250, 0.3)'
                },
                controls: {
                    show: true,
                    width: 150
                },
                zoomLevels: [250, 500, 1000, 2000, 3000],
                seekStyle: 'line'
            });

            console.log('WaveformQCPlayer: Playlist object created:', this.playlist);

            // Get event emitter
            this.ee = this.playlist.getEventEmitter();
            console.log('WaveformQCPlayer: Event emitter obtained:', !!this.ee);

            // Set up event listeners
            this._setupEventListeners();

            console.log('WaveformQCPlayer: Initialized successfully');
            return true;

        } catch (error) {
            console.error('WaveformQCPlayer: Initialization failed:', error);
            this._updateStatus(`Init failed: ${error.message}`, 'error');
            return false;
        }
    }

    /**
     * Set up event listeners for playlist events
     */
    _setupEventListeners() {
        if (!this.ee) return;

        // Playback events
        this.ee.on('play', () => {
            this.isPlaying = true;
            console.log('WaveformQCPlayer: Playing');
        });

        this.ee.on('pause', () => {
            this.isPlaying = false;
            console.log('WaveformQCPlayer: Paused');
        });

        this.ee.on('stop', () => {
            this.isPlaying = false;
            console.log('WaveformQCPlayer: Stopped');
        });

        // Time update (fires during playback)
        this.ee.on('timeupdate', (currentTime) => {
            if (this.onTimeUpdate) {
                this.onTimeUpdate({
                    currentTime: currentTime,
                    duration: this.duration,
                    isPlaying: this.isPlaying,
                    isCorrectedMode: this.isCorrectedMode
                });
            }
        });

        // Finished loading
        this.ee.on('finished', () => {
            this.isPlaying = false;
            console.log('WaveformQCPlayer: Playback finished');
        });

        // Audio loaded
        this.ee.on('audiorenderingfinished', (type, data) => {
            console.log('WaveformQCPlayer: Audio rendering finished');
            if (this.onReady) {
                this.onReady();
            }
        });

        // Error handling
        this.ee.on('error', (error) => {
            console.error('WaveformQCPlayer: Error:', error);
            if (this.onError) {
                this.onError(error);
            }
        });
    }

    /**
     * Load audio tracks for comparison
     * @param {string} masterUrl - URL to master audio file
     * @param {string} dubUrl - URL to dub audio file
     * @param {number} offsetSeconds - Detected offset in seconds
     */
    async loadTracks(masterUrl, dubUrl, offsetSeconds = 0) {
        // Wait a tick for container to be fully visible and have dimensions
        await new Promise(resolve => setTimeout(resolve, 100));

        if (!this.playlist || !this.ee) {
            const ok = await this.initialize();
            if (!ok) return false;
        }

        // Check container dimensions
        const rect = this.container?.getBoundingClientRect();
        console.log('WaveformQCPlayer: Container dimensions:', rect?.width, 'x', rect?.height);
        if (!rect || rect.width === 0 || rect.height === 0) {
            console.warn('WaveformQCPlayer: Container has no dimensions!');
        }

        this.masterUrl = masterUrl;
        this.dubUrl = dubUrl;
        this.offsetSeconds = offsetSeconds;
        this._tracksLoaded = false;
        this.isCorrectedMode = false; // Start in "before fix" mode

        console.log('WaveformQCPlayer: Loading tracks', { masterUrl, dubUrl, offsetSeconds });
        this._updateStatus('Loading audio tracks...');

        try {
            // Clear existing tracks
            console.log('WaveformQCPlayer: Clearing existing tracks');
            this.ee.emit('clear');
            
            // Also clear container content directly to prevent duplicate waveforms
            if (this.container) {
                this.container.innerHTML = '';
            }
            
            // Wait for clear to complete
            await new Promise(resolve => setTimeout(resolve, 50));
            
            // Reinitialize playlist after clear
            if (!this.playlist || !this.ee) {
                const ok = await this.initialize();
                if (!ok) return false;
            }

            // Build track list - for "Before Fix" mode, both start at 0
            // The offset is applied dynamically when switching to "After Fix" mode
            const tracks = [
                {
                    src: masterUrl,
                    name: 'Master',
                    gain: this.masterVolume,
                    muted: this.masterMuted,
                    start: 0,
                    // Bright blue for master track
                    customClass: 'master-track',
                    waveOutlineColor: '#3b82f6'
                },
                {
                    src: dubUrl,
                    name: 'Dub',
                    gain: this.dubVolume,
                    muted: this.dubMuted,
                    start: 0, // Will be adjusted for After Fix mode
                    // Bright green for dub track
                    customClass: 'dub-track',
                    waveOutlineColor: '#22c55e'
                }
            ];

            console.log('WaveformQCPlayer: Loading tracks:', tracks);

            // Load tracks
            await this.playlist.load(tracks);

            // Get duration from loaded tracks
            this.duration = this.playlist.getDuration ? this.playlist.getDuration() : 0;
            this._tracksLoaded = true;

            console.log('WaveformQCPlayer: Tracks loaded successfully, duration:', this.duration);
            this._updateStatus('Ready for playback');

            // Check if waveforms rendered (container should have children)
            setTimeout(() => {
                const hasContent = this.container.querySelector('.playlist-tracks') ||
                                   this.container.querySelector('canvas') ||
                                   this.container.children.length > 0;
                console.log('WaveformQCPlayer: Container has content:', hasContent);
                console.log('WaveformQCPlayer: Container children:', this.container.children.length);
                console.log('WaveformQCPlayer: Container innerHTML length:', this.container.innerHTML.length);

                if (!hasContent || this.container.innerHTML.length < 100) {
                    console.warn('WaveformQCPlayer: Waveforms may not have rendered properly');
                    this._showFallbackMessage();
                }
            }, 1000);

            return true;

        } catch (error) {
            console.error('WaveformQCPlayer: Failed to load tracks:', error);
            console.error('WaveformQCPlayer: Error details:', error.stack);
            this._updateStatus(`Load failed: ${error.message}`, 'error');
            return false;
        }
    }

    /**
     * Play in "Before Fix" mode - both tracks aligned, shows sync problem
     */
    async playBefore(startTime = 0) {
        console.log('WaveformQCPlayer: playBefore called, startTime:', startTime);

        // If mode changed, reload tracks with new offset
        if (this.isCorrectedMode || !this._tracksLoaded) {
            this.isCorrectedMode = false;
            await this._reloadTracksWithOffset(0, 0);
        }

        this._updateStatus('Playing BEFORE fix (problem audible)');

        // Start playback
        if (this.ee) {
            if (startTime > 0) {
                this.ee.emit('play', startTime);
            } else {
                this.ee.emit('play');
            }
        }
    }

    /**
     * Play in "After Fix" mode - dub offset applied to show corrected sync
     */
    async playAfter(startTime = 0) {
        console.log('WaveformQCPlayer: playAfter called, startTime:', startTime, 'offset:', this.offsetSeconds);

        // If mode changed or not loaded, reload tracks with offset applied
        if (!this.isCorrectedMode || !this._tracksLoaded) {
            this.isCorrectedMode = true;

            // Apply offset to correct the sync
            // Positive offset = dub is early, shift dub start later
            // Negative offset = dub is late, shift master start later
            let masterStart = 0;
            let dubStart = 0;

            if (this.offsetSeconds > 0) {
                // Dub is early - delay dub
                dubStart = this.offsetSeconds;
            } else if (this.offsetSeconds < 0) {
                // Dub is late - delay master
                masterStart = Math.abs(this.offsetSeconds);
            }

            await this._reloadTracksWithOffset(masterStart, dubStart);
        }

        this._updateStatus('Playing AFTER fix (sync corrected)');

        // Start playback
        if (this.ee) {
            if (startTime > 0) {
                this.ee.emit('play', startTime);
            } else {
                this.ee.emit('play');
            }
        }
    }

    /**
     * Reload tracks with specific start offsets
     */
    async _reloadTracksWithOffset(masterStart, dubStart) {
        if (!this.masterUrl || !this.dubUrl) {
            console.warn('WaveformQCPlayer: No URLs to reload');
            return false;
        }

        console.log('WaveformQCPlayer: Reloading tracks with offset - master:', masterStart, 'dub:', dubStart);
        this._updateStatus('Applying sync correction...');

        try {
            // Clear existing tracks
            if (this.ee) {
                this.ee.emit('clear');
            }

            // Wait for clear to complete
            await new Promise(resolve => setTimeout(resolve, 50));

            // Build track list with offsets
            const tracks = [
                {
                    src: this.masterUrl,
                    name: 'Master',
                    gain: this.masterVolume,
                    muted: this.masterMuted,
                    start: masterStart,
                    customClass: 'master-track',
                    waveOutlineColor: '#3b82f6'
                },
                {
                    src: this.dubUrl,
                    name: 'Dub',
                    gain: this.dubVolume,
                    muted: this.dubMuted,
                    start: dubStart,
                    customClass: 'dub-track',
                    waveOutlineColor: '#22c55e'
                }
            ];

            console.log('WaveformQCPlayer: Loading tracks with offsets:', tracks.map(t => ({name: t.name, start: t.start})));

            // Load tracks with new offsets
            await this.playlist.load(tracks);

            // Update duration
            this.duration = this.playlist.getDuration ? this.playlist.getDuration() : 0;
            this._tracksLoaded = true;

            console.log('WaveformQCPlayer: Tracks reloaded successfully');
            return true;

        } catch (error) {
            console.error('WaveformQCPlayer: Failed to reload tracks:', error);
            this._updateStatus(`Reload failed: ${error.message}`, 'error');
            return false;
        }
    }

    /**
     * Stop playback
     */
    stop() {
        if (this.ee) {
            this.ee.emit('stop');
        }
        this.isPlaying = false;
    }

    /**
     * Pause playback
     */
    pause() {
        if (this.ee) {
            this.ee.emit('pause');
        }
        this.isPlaying = false;
    }

    /**
     * Seek to specific time
     */
    seek(time) {
        if (this.ee) {
            this.ee.emit('select', time, time); // Set cursor position
        }
    }

    /**
     * Set master volume (0-1)
     */
    setMasterVolume(value) {
        this.masterVolume = Math.max(0, Math.min(1, value));
        if (this.ee) {
            this.ee.emit('volumechange', 0, this.masterVolume); // track 0 = master
        }
    }

    /**
     * Set dub volume (0-1)
     */
    setDubVolume(value) {
        this.dubVolume = Math.max(0, Math.min(1, value));
        if (this.ee) {
            this.ee.emit('volumechange', 1, this.dubVolume); // track 1 = dub
        }
    }

    /**
     * Mute/unmute master track
     */
    setMasterMuted(muted) {
        this.masterMuted = muted;
        if (this.ee) {
            this.ee.emit('mute', 0); // Toggle mute on track 0
        }
    }

    /**
     * Mute/unmute dub track
     */
    setDubMuted(muted) {
        this.dubMuted = muted;
        if (this.ee) {
            this.ee.emit('mute', 1); // Toggle mute on track 1
        }
    }

    /**
     * Solo master track
     */
    soloMaster() {
        if (this.ee) {
            this.ee.emit('solo', 0);
        }
    }

    /**
     * Solo dub track
     */
    soloDub() {
        if (this.ee) {
            this.ee.emit('solo', 1);
        }
    }

    /**
     * Zoom in
     */
    zoomIn() {
        if (this.ee) {
            this.ee.emit('zoomin');
        }
    }

    /**
     * Zoom out
     */
    zoomOut() {
        if (this.ee) {
            this.ee.emit('zoomout');
        }
    }

    /**
     * Get current playback status
     */
    getStatus() {
        return {
            isPlaying: this.isPlaying,
            isCorrectedMode: this.isCorrectedMode,
            duration: this.duration,
            masterVolume: this.masterVolume,
            dubVolume: this.dubVolume,
            masterMuted: this.masterMuted,
            dubMuted: this.dubMuted,
            offsetSeconds: this.offsetSeconds
        };
    }

    /**
     * Get duration
     */
    getDuration() {
        return this.duration;
    }

    /**
     * Update status callback
     */
    _updateStatus(message, type = 'info') {
        console.log(`WaveformQCPlayer: ${message}`);
        if (this.onStatusChange) {
            this.onStatusChange(message, type);
        }
    }

    /**
     * Show fallback message if waveforms don't render
     */
    _showFallbackMessage() {
        if (!this.container) return;

        // Check if already has proper content
        if (this.container.querySelector('.playlist-tracks')) return;

        // Add a fallback display
        const fallback = document.createElement('div');
        fallback.className = 'waveform-fallback';
        fallback.style.cssText = `
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            height: 100%;
            min-height: 200px;
            color: #94a3b8;
            font-size: 14px;
            text-align: center;
            padding: 20px;
        `;
        fallback.innerHTML = `
            <div style="margin-bottom: 12px;">
                <i class="fas fa-waveform" style="font-size: 32px; color: #60a5fa;"></i>
            </div>
            <div style="margin-bottom: 8px; font-weight: 600;">Audio Loaded</div>
            <div style="font-size: 12px; color: #64748b;">
                Master: ${this.masterUrl ? this.masterUrl.split('/').pop() : 'N/A'}<br>
                Dub: ${this.dubUrl ? this.dubUrl.split('/').pop() : 'N/A'}<br>
                Duration: ${this.duration.toFixed(1)}s
            </div>
            <div style="margin-top: 12px; font-size: 11px; color: #475569;">
                Click "Play Problem" or "Play Fixed" to listen
            </div>
        `;

        // Only add if container is empty or has minimal content
        if (this.container.innerHTML.length < 100) {
            this.container.appendChild(fallback);
        }
    }

    /**
     * Dispose and clean up
     */
    dispose() {
        this.stop();
        if (this.ee) {
            this.ee.emit('clear');
        }
        // Clear container content to prevent duplicate waveforms on reinit
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.playlist = null;
        this.ee = null;
        this._tracksLoaded = false;
        this.masterUrl = null;
        this.dubUrl = null;
    }
}

// Export for use
window.WaveformQCPlayer = WaveformQCPlayer;
