/**
 * MultiTrackPlayer - Professional multi-track audio player for QC interface
 * Supports N tracks with synchronized playback, per-track controls, and offset handling
 */

class MultiTrackPlayer {
    constructor(options = {}) {
        this.tracks = new Map(); // trackId -> track info
        this.masterTime = 0;
        this.isPlaying = false;
        this.isCorrectedMode = true; // Apply offsets by default
        this.syncInterval = null;
        this.animationFrameId = null;
        this.balanceValue = 0;
        
        // Container for audio elements
        this.container = options.container || document.body;
        
        // Callbacks
        this.onTimeUpdate = options.onTimeUpdate || null;
        this.onStatusChange = options.onStatusChange || null;
        this.onTrackLoaded = options.onTrackLoaded || null;
        this.onPlaybackEnd = options.onPlaybackEnd || null;
        
        // Settings
        this.syncThresholdMs = options.syncThresholdMs || 50; // Resync if drift > 50ms
        this.syncCheckIntervalMs = options.syncCheckIntervalMs || 200;
        
        console.log('MultiTrackPlayer initialized');
    }
    
    /**
     * Add a track to the player (fast metadata-only load)
     * @param {string} trackId - Unique identifier for the track
     * @param {object} config - Track configuration
     * @param {string} config.url - Audio URL
     * @param {string} config.name - Display name
     * @param {string} config.type - 'master' or 'component'
     * @param {number} config.offset - Offset in seconds (positive = early, negative = late)
     * @param {string} config.color - Track color for UI
     */
    async addTrack(trackId, config) {
        const { url, name, type = 'component', offset = 0, color = '#4ade80' } = config;
        
        if (!url) {
            console.warn(`MultiTrackPlayer: No URL for track ${trackId}`);
            return false;
        }
        
        // Remove existing track with same ID
        if (this.tracks.has(trackId)) {
            this.removeTrack(trackId);
        }
        
        // Create audio element with metadata-only preload for fast initial load
        const audio = document.createElement('audio');
        audio.id = `mtp-audio-${trackId}`;
        audio.preload = 'metadata'; // Fast: only load metadata, not full audio
        // Don't set crossOrigin for same-origin requests
        // audio.crossOrigin = 'anonymous';
        audio.style.display = 'none';
        this.container.appendChild(audio);
        
        // Track state
        const track = {
            id: trackId,
            name: name || trackId,
            type,
            url,
            offset,
            color,
            audio,
            volume: 1.0,
            muted: false,
            solo: false,
            loaded: false,
            buffered: false, // True when full audio is buffered
            duration: 0,
            error: null
        };
        
        this.tracks.set(trackId, track);
        
        // Fast metadata load
        try {
            await this._loadTrackMetadata(track);
            this._updateStatus(`Track "${name}" ready`);
            if (this.onTrackLoaded) {
                this.onTrackLoaded(track);
            }
            return true;
        } catch (error) {
            track.error = error.message;
            console.error(`MultiTrackPlayer: Failed to load track ${trackId}:`, error);
            this._updateStatus(`Failed to load "${name}"`, 'error');
            return false;
        }
    }
    
    /**
     * Add multiple tracks in PARALLEL (much faster!)
     * @param {Array<{id: string, config: object}>} tracks - Array of track configs
     * @returns {Promise<number>} - Number of successfully loaded tracks
     */
    async addTracksParallel(tracksToAdd) {
        console.log(`MultiTrackPlayer: Loading ${tracksToAdd.length} tracks in parallel...`);
        const startTime = performance.now();
        
        // Create all tracks and start loading in parallel
        const loadPromises = tracksToAdd.map(({ id, config }) => 
            this.addTrack(id, config).catch(err => {
                console.warn(`MultiTrackPlayer: Track ${id} failed:`, err);
                return false;
            })
        );
        
        const results = await Promise.all(loadPromises);
        const successCount = results.filter(Boolean).length;
        
        const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
        console.log(`MultiTrackPlayer: Loaded ${successCount}/${tracksToAdd.length} tracks in ${elapsed}s`);
        this._updateStatus(`${successCount} tracks loaded in ${elapsed}s`);
        
        return successCount;
    }
    
    /**
     * Fast metadata-only load (gets duration without downloading full audio)
     */
    async _loadTrackMetadata(track) {
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error(`Metadata timeout for ${track.name}`));
            }, 15000); // 15s timeout for metadata (should be very fast)
            
            const onLoaded = () => {
                clearTimeout(timeout);
                track.loaded = true;
                track.duration = track.audio.duration || 0;
                console.log(`MultiTrackPlayer: "${track.name}" metadata loaded - ${track.duration.toFixed(2)}s`);
                resolve();
            };
            
            const onError = () => {
                clearTimeout(timeout);
                const errorMsg = track.audio.error?.message || 'Unknown error';
                reject(new Error(errorMsg));
            };
            
            if (track.audio.readyState >= 1) {
                onLoaded();
            } else {
                track.audio.addEventListener('loadedmetadata', onLoaded, { once: true });
                track.audio.addEventListener('error', onError, { once: true });
                track.audio.src = track.url;
                track.audio.load();
            }
        });
    }
    
    /**
     * Ensure a track is fully buffered for playback
     * Called automatically before play, but can be called manually for preloading
     */
    async _ensureBuffered(track) {
        if (track.buffered) return true;
        if (!track.loaded) return false;
        
        return new Promise((resolve) => {
            const audio = track.audio;
            
            // Check if already buffered enough
            if (audio.readyState >= 4) { // HAVE_ENOUGH_DATA
                track.buffered = true;
                resolve(true);
                return;
            }
            
            // Switch to auto preload to start buffering
            audio.preload = 'auto';
            
            const onCanPlayThrough = () => {
                track.buffered = true;
                console.log(`MultiTrackPlayer: "${track.name}" fully buffered`);
                resolve(true);
            };
            
            const onError = () => {
                console.warn(`MultiTrackPlayer: "${track.name}" buffer error`);
                resolve(false);
            };
            
            // Set timeout - don't block forever
            const timeout = setTimeout(() => {
                // Even if not fully buffered, we can still try to play
                console.log(`MultiTrackPlayer: "${track.name}" buffer timeout, continuing...`);
                resolve(true);
            }, 10000); // 10s max wait for buffering
            
            audio.addEventListener('canplaythrough', () => {
                clearTimeout(timeout);
                onCanPlayThrough();
            }, { once: true });
            
            audio.addEventListener('error', () => {
                clearTimeout(timeout);
                onError();
            }, { once: true });
            
            // Trigger load if not already loading
            if (audio.networkState === 0) { // NETWORK_EMPTY
                audio.load();
            }
        });
    }
    
    /**
     * Buffer all tracks in parallel before playback
     */
    async _bufferAllTracks() {
        const startTime = performance.now();
        this._updateStatus('Buffering audio...');
        
        const bufferPromises = Array.from(this.tracks.values())
            .filter(t => t.loaded && !t.buffered)
            .map(t => this._ensureBuffered(t));
        
        await Promise.all(bufferPromises);
        
        const elapsed = ((performance.now() - startTime) / 1000).toFixed(2);
        console.log(`MultiTrackPlayer: All tracks buffered in ${elapsed}s`);
    }
    
    /**
     * Remove a track
     */
    removeTrack(trackId) {
        const track = this.tracks.get(trackId);
        if (track) {
            track.audio.pause();
            track.audio.src = '';
            track.audio.remove();
            this.tracks.delete(trackId);
            console.log(`MultiTrackPlayer: Removed track ${trackId}`);
        }
    }
    
    /**
     * Remove all tracks
     */
    clearTracks() {
        for (const trackId of this.tracks.keys()) {
            this.removeTrack(trackId);
        }
    }
    
    /**
     * Get all tracks
     */
    getTracks() {
        return Array.from(this.tracks.values());
    }
    
    /**
     * Get a specific track
     */
    getTrack(trackId) {
        return this.tracks.get(trackId);
    }
    
    /**
     * Get max duration across all tracks
     */
    getDuration() {
        let maxDuration = 0;
        for (const track of this.tracks.values()) {
            if (track.duration > maxDuration) {
                maxDuration = track.duration;
            }
        }
        return maxDuration;
    }
    
    /**
     * Play all tracks from a specific time
     * @param {number} startTime - Start time in seconds (master timeline)
     * @param {boolean} corrected - Apply offset corrections
     */
    async play(startTime = 0, corrected = true) {
        console.log(`MultiTrackPlayer.play(startTime=${startTime}, corrected=${corrected})`);
        
        this.isCorrectedMode = corrected;
        
        // Stop any current playback (use pause to avoid resetting masterTime)
        this.pause();
        
        // Set master time AFTER pause (stop() would reset it to 0)
        this.masterTime = Math.max(0, startTime);
        console.log(`MultiTrackPlayer.play: masterTime set to ${this.masterTime}`);
        
        // Quick buffer check - start buffering in background, don't wait too long
        const unbufferedTracks = Array.from(this.tracks.values()).filter(t => t.loaded && !t.buffered);
        if (unbufferedTracks.length > 0) {
            this._updateStatus('Buffering...');
            // Start buffering all tracks in parallel, but only wait briefly
            const bufferPromise = Promise.all(unbufferedTracks.map(t => this._ensureBuffered(t)));
            // Wait max 2s for initial buffer, then start playing anyway
            await Promise.race([
                bufferPromise,
                new Promise(r => setTimeout(r, 2000))
            ]);
        }
        
        const playPromises = [];
        
        for (const track of this.tracks.values()) {
            if (!track.loaded || track.error) continue;
            
            // Calculate track time based on offset
            let trackTime = this.masterTime;
            if (corrected && track.offset !== 0) {
                // If offset > 0: track content at t=0 matches master at t=offset
                // So to align: track plays from t+offset when master plays from t
                trackTime = this.masterTime + track.offset;
            }
            
            // Clamp to valid range
            trackTime = Math.max(0, Math.min(trackTime, track.duration - 0.1));
            
            // Set position and volume
            track.audio.currentTime = trackTime;
            this._applyTrackVolume(track);
            
            // Start playback
            const playPromise = track.audio.play().catch(e => {
                console.warn(`MultiTrackPlayer: Play blocked for "${track.name}":`, e.message);
            });
            playPromises.push(playPromise);
        }
        
        await Promise.all(playPromises);
        
        this.isPlaying = true;
        this._startSyncMonitor();
        this._startTimeUpdate();
        
        const mode = corrected ? 'CORRECTED (offsets applied)' : 'RAW (no offsets)';
        this._updateStatus(`Playing - ${mode}`);
        console.log(`MultiTrackPlayer: Playing from ${startTime.toFixed(2)}s - ${mode}`);
    }
    
    /**
     * Play in "Before Fix" mode - raw positions, hear the sync problem
     */
    playBefore(startTime = 0) {
        return this.play(startTime, false);
    }
    
    /**
     * Play in "After Fix" mode - corrected positions, synced audio
     */
    playAfter(startTime = 0) {
        return this.play(startTime, true);
    }
    
    /**
     * Pause playback
     */
    pause() {
        for (const track of this.tracks.values()) {
            track.audio.pause();
        }
        this.isPlaying = false;
        this._stopSyncMonitor();
        this._stopTimeUpdate();
        this._updateStatus('Paused');
    }
    
    /**
     * Stop playback and reset to beginning
     */
    stop() {
        this.pause();
        this.masterTime = 0;
        for (const track of this.tracks.values()) {
            track.audio.currentTime = 0;
        }
        this._updateStatus('Stopped');
    }
    
    /**
     * Seek to a specific time
     */
    seek(time) {
        console.log(`MultiTrackPlayer.seek(${time}) - wasPlaying: ${this.isPlaying}, duration: ${this.getDuration()}`);
        
        const wasPlaying = this.isPlaying;
        if (wasPlaying) {
            this.pause();
        }
        
        this.masterTime = Math.max(0, Math.min(time, this.getDuration()));
        console.log(`MultiTrackPlayer.seek: masterTime set to ${this.masterTime}`);
        
        for (const track of this.tracks.values()) {
            if (!track.loaded) continue;
            
            let trackTime = this.masterTime;
            if (this.isCorrectedMode && track.offset !== 0) {
                trackTime = this.masterTime + track.offset;
            }
            trackTime = Math.max(0, Math.min(trackTime, track.duration - 0.1));
            track.audio.currentTime = trackTime;
            console.log(`MultiTrackPlayer.seek: ${track.name} -> ${trackTime.toFixed(2)}s`);
        }
        
        // Trigger time update
        this._fireTimeUpdate();
        
        if (wasPlaying) {
            console.log(`MultiTrackPlayer.seek: resuming playback from ${this.masterTime}`);
            this.play(this.masterTime, this.isCorrectedMode);
        }
    }
    
    /**
     * Set track volume (0-1)
     */
    setTrackVolume(trackId, volume) {
        const track = this.tracks.get(trackId);
        if (track) {
            track.volume = Math.max(0, Math.min(1, volume));
            this._applyTrackVolume(track);
        }
    }
    
    /**
     * Set track mute state
     */
    setTrackMuted(trackId, muted) {
        const track = this.tracks.get(trackId);
        if (track) {
            track.muted = muted;
            this._applyTrackVolume(track);
        }
    }
    
    /**
     * Set track solo state
     */
    setTrackSolo(trackId, solo) {
        const track = this.tracks.get(trackId);
        if (track) {
            track.solo = solo;
            this._applyAllVolumes();
        }
    }

    /**
     * Balance between master (-1) and dub/components (+1)
     */
    setBalance(value) {
        const v = Number(value) || 0;
        this.balanceValue = Math.max(-1, Math.min(1, v));
        this._applyAllVolumes();
    }
    
    /**
     * Set track offset
     */
    setTrackOffset(trackId, offset) {
        const track = this.tracks.get(trackId);
        if (track) {
            track.offset = offset;
        }
    }
    
    /**
     * Apply volume to a single track (considering mute and solo states)
     */
    _applyTrackVolume(track) {
        const anySolo = Array.from(this.tracks.values()).some(t => t.solo);
        
        let effectiveVolume = track.volume;
        
        // If any track is soloed, mute non-soloed tracks
        if (anySolo && !track.solo) {
            effectiveVolume = 0;
        }
        
        // Apply mute
        if (track.muted) {
            effectiveVolume = 0;
        }

        // Apply balance between master and non-master tracks
        const balance = this.balanceValue ?? 0;
        const masterScale = 1 - Math.max(0, balance);
        const dubScale = 1 - Math.max(0, -balance);
        const isMaster = track.type === 'master' || track.id === 'master';
        effectiveVolume *= isMaster ? masterScale : dubScale;
        
        track.audio.volume = effectiveVolume;
    }
    
    /**
     * Apply volumes to all tracks
     */
    _applyAllVolumes() {
        for (const track of this.tracks.values()) {
            this._applyTrackVolume(track);
        }
    }
    
    /**
     * Start sync monitoring to prevent drift
     */
    _startSyncMonitor() {
        this._stopSyncMonitor();
        
        this.syncInterval = setInterval(() => {
            if (!this.isPlaying) {
                this._stopSyncMonitor();
                return;
            }
            
            // Get master track time (use first track or calculate from any playing track)
            let masterTrack = null;
            for (const track of this.tracks.values()) {
                if (track.type === 'master' && track.loaded) {
                    masterTrack = track;
                    break;
                }
            }
            
            if (!masterTrack) {
                // Use first loaded track as reference
                for (const track of this.tracks.values()) {
                    if (track.loaded) {
                        masterTrack = track;
                        break;
                    }
                }
            }
            
            if (!masterTrack) return;
            
            // Update master time
            this.masterTime = masterTrack.audio.currentTime - (this.isCorrectedMode ? masterTrack.offset : 0);
            
            // Check and correct drift on other tracks
            for (const track of this.tracks.values()) {
                if (track === masterTrack || !track.loaded) continue;
                
                let expectedTime = this.masterTime;
                if (this.isCorrectedMode && track.offset !== 0) {
                    expectedTime = this.masterTime + track.offset;
                }
                expectedTime = Math.max(0, Math.min(expectedTime, track.duration - 0.1));
                
                const actualTime = track.audio.currentTime;
                const driftMs = Math.abs(expectedTime - actualTime) * 1000;
                
                if (driftMs > this.syncThresholdMs) {
                    console.log(`MultiTrackPlayer: Resyncing "${track.name}" - drift: ${driftMs.toFixed(0)}ms`);
                    track.audio.currentTime = expectedTime;
                }
            }
            
            // Check for playback end
            const duration = this.getDuration();
            if (this.masterTime >= duration - 0.1) {
                this.stop();
                if (this.onPlaybackEnd) {
                    this.onPlaybackEnd();
                }
            }
        }, this.syncCheckIntervalMs);
    }
    
    _stopSyncMonitor() {
        if (this.syncInterval) {
            clearInterval(this.syncInterval);
            this.syncInterval = null;
        }
    }
    
    /**
     * Start time update animation
     */
    _startTimeUpdate() {
        this._stopTimeUpdate();
        
        const update = () => {
            if (!this.isPlaying) {
                this.animationFrameId = null;
                return;
            }
            
            this._fireTimeUpdate();
            this.animationFrameId = requestAnimationFrame(update);
        };
        
        this.animationFrameId = requestAnimationFrame(update);
    }
    
    _stopTimeUpdate() {
        if (this.animationFrameId) {
            cancelAnimationFrame(this.animationFrameId);
            this.animationFrameId = null;
        }
    }
    
    _fireTimeUpdate() {
        if (this.onTimeUpdate) {
            this.onTimeUpdate({
                masterTime: this.masterTime,
                duration: this.getDuration(),
                isPlaying: this.isPlaying,
                isCorrectedMode: this.isCorrectedMode,
                tracks: this.getTracks().map(t => ({
                    id: t.id,
                    name: t.name,
                    currentTime: t.audio?.currentTime || 0,
                    duration: t.duration,
                    offset: t.offset
                }))
            });
        }
    }
    
    _updateStatus(message, type = 'info') {
        console.log(`MultiTrackPlayer: ${message}`);
        if (this.onStatusChange) {
            this.onStatusChange(message, type);
        }
    }
    
    /**
     * Get current status
     */
    getStatus() {
        return {
            isPlaying: this.isPlaying,
            isCorrectedMode: this.isCorrectedMode,
            masterTime: this.masterTime,
            duration: this.getDuration(),
            trackCount: this.tracks.size,
            tracks: this.getTracks().map(t => ({
                id: t.id,
                name: t.name,
                type: t.type,
                loaded: t.loaded,
                duration: t.duration,
                offset: t.offset,
                volume: t.volume,
                muted: t.muted,
                solo: t.solo,
                currentTime: t.audio?.currentTime || 0
            }))
        };
    }
    
    /**
     * Dispose of all resources
     */
    dispose() {
        this.stop();
        this.clearTracks();
        console.log('MultiTrackPlayer disposed');
    }
}

// Export for use
window.MultiTrackPlayer = MultiTrackPlayer;
