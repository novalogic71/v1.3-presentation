/**
 * NativeAudioPlayer - Simple, reliable playback using browser's native audio elements
 * 
 * Uses HTML5 <audio> elements directly for best performance and reliability.
 * The browser handles all buffering, seeking, and streaming automatically.
 */

class NativeAudioPlayer {
    constructor() {
        this.tracks = [];  // Array of {id, name, audio, offset, volume, muted}
        this.masterTrack = null;
        this.isPlaying = false;
        this.correctedMode = true;
        this.onTimeUpdate = null;
        this.onStatusChange = null;
        this.animationId = null;
        
        console.log('NativeAudioPlayer initialized');
    }
    
    /**
     * Load a single audio track
     */
    async loadTrack(id, url, name, offset = 0) {
        // Remove existing track with same ID
        this.removeTrack(id);
        
        const audio = document.createElement('audio');
        audio.id = `native-audio-${id}`;
        audio.preload = 'metadata'; // Fast: just get duration
        // Don't set crossOrigin for same-origin requests
        // audio.crossOrigin = 'anonymous';
        audio.style.display = 'none';
        document.body.appendChild(audio);
        
        const track = {
            id,
            name,
            audio,
            offset,
            volume: 1.0,
            muted: false,
            solo: false,
            loaded: false,
            duration: 0
        };
        
        // Set source and wait for metadata
        return new Promise((resolve, reject) => {
            const timeout = setTimeout(() => {
                reject(new Error(`Timeout loading ${name}`));
            }, 30000);
            
            audio.onloadedmetadata = () => {
                clearTimeout(timeout);
                track.loaded = true;
                track.duration = audio.duration;
                console.log(`NativeAudioPlayer: "${name}" ready (${audio.duration.toFixed(1)}s)`);
                
                // First track becomes master
                if (this.tracks.length === 0 || id === 'master') {
                    this.masterTrack = track;
                }
                
                this.tracks.push(track);
                this._updateStatus(`${name} loaded`);
                resolve(track);
            };
            
            audio.onerror = () => {
                clearTimeout(timeout);
                const error = audio.error?.message || 'Load error';
                console.error(`NativeAudioPlayer: Failed to load "${name}":`, error);
                reject(new Error(error));
            };
            
            audio.src = url;
        });
    }
    
    /**
     * Load master and dub tracks (convenience method)
     */
    async loadPair(masterUrl, dubUrl, offset = 0, masterName = 'Master', dubName = 'Dub') {
        this.clear();
        
        const results = await Promise.allSettled([
            this.loadTrack('master', masterUrl, masterName, 0),
            this.loadTrack('dub', dubUrl, dubName, offset)
        ]);
        
        const loaded = results.filter(r => r.status === 'fulfilled').length;
        console.log(`NativeAudioPlayer: Loaded ${loaded}/2 tracks`);
        return loaded;
    }
    
    /**
     * Remove a track
     */
    removeTrack(id) {
        const idx = this.tracks.findIndex(t => t.id === id);
        if (idx >= 0) {
            const track = this.tracks[idx];
            track.audio.pause();
            track.audio.src = '';
            track.audio.remove();
            this.tracks.splice(idx, 1);
            
            if (this.masterTrack?.id === id) {
                this.masterTrack = this.tracks[0] || null;
            }
        }
    }
    
    /**
     * Clear all tracks
     */
    clear() {
        this.stop();
        while (this.tracks.length > 0) {
            this.removeTrack(this.tracks[0].id);
        }
        this.masterTrack = null;
    }
    
    /**
     * Play all tracks
     * @param {boolean} corrected - If true, apply offset correction
     * @param {number} startTime - Start time in seconds (on master timeline)
     */
    play(corrected = true, startTime = null) {
        if (this.tracks.length === 0) {
            this._updateStatus('No tracks loaded', 'error');
            return;
        }
        
        this.correctedMode = corrected;
        this.pause(); // Don't reset positions
        
        // Determine start position (guard against NaN)
        let masterTime = startTime ?? (this.masterTrack?.audio.currentTime || 0);
        if (!Number.isFinite(masterTime)) masterTime = 0;
        
        // Set all track positions
        this.tracks.forEach(track => {
            let trackTime = masterTime;
            
            // Apply offset if in corrected mode and this isn't master
            if (corrected && track.id !== 'master' && track.offset !== 0) {
                trackTime = masterTime + track.offset;
            }
            
            // Guard against invalid values
            if (!Number.isFinite(trackTime)) trackTime = 0;
            if (!Number.isFinite(track.duration) || track.duration <= 0) return;
            
            // Clamp to valid range
            trackTime = Math.max(0, Math.min(trackTime, track.duration - 0.1));
            
            try {
                track.audio.currentTime = trackTime;
                track.audio.volume = track.muted ? 0 : track.volume;
            } catch (e) {
                console.warn(`Failed to set time for ${track.name}:`, e.message);
            }
        });
        
        // Start all playback
        const playPromises = this.tracks.map(t => 
            t.audio.play().catch(e => console.warn(`Play blocked for ${t.name}:`, e.message))
        );
        
        Promise.all(playPromises).then(() => {
            this.isPlaying = true;
            this._startTimeUpdate();
            this._updateStatus(corrected ? 'Playing (corrected)' : 'Playing (raw)');
        });
    }
    
    /**
     * Play in "Before Fix" mode - raw positions to hear the sync problem
     */
    playBefore(startTime = null) {
        this.play(false, startTime);
    }
    
    /**
     * Play in "After Fix" mode - with offset correction applied
     */
    playAfter(startTime = null) {
        this.play(true, startTime);
    }
    
    /**
     * Pause playback
     */
    pause() {
        this.tracks.forEach(t => t.audio.pause());
        this.isPlaying = false;
        this._stopTimeUpdate();
        this._updateStatus('Paused');
    }
    
    /**
     * Stop playback and reset to beginning
     */
    stop() {
        this.pause();
        this.tracks.forEach(t => {
            try {
                t.audio.currentTime = 0;
            } catch (e) {
                // Ignore errors when resetting
            }
        });
    }
    
    /**
     * Seek to a specific time (master timeline)
     */
    seek(time) {
        // Guard against invalid time values
        if (!Number.isFinite(time)) {
            console.warn('NativeAudioPlayer: Invalid seek time:', time);
            return;
        }
        
        const wasPlaying = this.isPlaying;
        this.pause();
        
        this.tracks.forEach(track => {
            let trackTime = time;
            
            if (this.correctedMode && track.id !== 'master' && track.offset !== 0) {
                trackTime = time + track.offset;
            }
            
            // Guard against invalid values
            if (!Number.isFinite(trackTime)) trackTime = 0;
            if (!Number.isFinite(track.duration) || track.duration <= 0) return;
            
            trackTime = Math.max(0, Math.min(trackTime, track.duration - 0.1));
            
            try {
                track.audio.currentTime = trackTime;
            } catch (e) {
                console.warn(`Failed to seek ${track.name}:`, e.message);
            }
        });
        
        this._fireTimeUpdate();
        
        if (wasPlaying) {
            this.play(this.correctedMode);
        }
    }
    
    /**
     * Get current master time
     */
    getCurrentTime() {
        return this.masterTrack?.audio.currentTime || 0;
    }
    
    /**
     * Get total duration (max across all tracks)
     */
    getDuration() {
        return Math.max(...this.tracks.map(t => t.duration), 0);
    }
    
    /**
     * Set track volume
     */
    setVolume(trackId, volume) {
        const track = this.tracks.find(t => t.id === trackId);
        if (track) {
            track.volume = Math.max(0, Math.min(1, volume));
            if (!track.muted) {
                track.audio.volume = track.volume;
            }
            console.log(`NativeAudioPlayer: Volume ${trackId} = ${(track.volume * 100).toFixed(0)}%`);
        } else {
            console.warn(`NativeAudioPlayer: Track "${trackId}" not found for volume change`);
        }
    }
    
    /**
     * Set track mute
     */
    setMuted(trackId, muted) {
        const track = this.tracks.find(t => t.id === trackId);
        if (track) {
            track.muted = muted;
            track.audio.volume = muted ? 0 : track.volume;
            console.log(`NativeAudioPlayer: Mute ${trackId} = ${muted}`);
        } else {
            console.warn(`NativeAudioPlayer: Track "${trackId}" not found for mute change`);
        }
    }
    
    /**
     * Set track solo (mutes other tracks)
     */
    setSolo(trackId, solo) {
        const track = this.tracks.find(t => t.id === trackId);
        if (!track) {
            console.warn(`NativeAudioPlayer: Track "${trackId}" not found for solo`);
            return;
        }
        
        track.solo = solo;
        
        // Recalculate all volumes based on solo state
        const anySolo = this.tracks.some(t => t.solo);
        
        this.tracks.forEach(t => {
            if (anySolo) {
                // If any track is soloed, only play soloed tracks
                t.audio.volume = t.solo && !t.muted ? t.volume : 0;
            } else {
                // No solo - normal mute behavior
                t.audio.volume = t.muted ? 0 : t.volume;
            }
        });
        
        console.log(`NativeAudioPlayer: Solo ${trackId} = ${solo}`);
    }
    
    /**
     * Get player status
     */
    getStatus() {
        return {
            isPlaying: this.isPlaying,
            correctedMode: this.correctedMode,
            currentTime: this.getCurrentTime(),
            duration: this.getDuration(),
            trackCount: this.tracks.length,
            tracks: this.tracks.map(t => ({
                id: t.id,
                name: t.name,
                duration: t.duration,
                currentTime: t.audio.currentTime,
                offset: t.offset,
                volume: t.volume,
                muted: t.muted
            }))
        };
    }
    
    _startTimeUpdate() {
        this._stopTimeUpdate();
        
        const update = () => {
            if (!this.isPlaying) return;
            
            this._fireTimeUpdate();
            
            // Check if playback ended
            if (this.masterTrack && this.masterTrack.audio.ended) {
                this.stop();
                this._updateStatus('Playback complete');
                return;
            }
            
            this.animationId = requestAnimationFrame(update);
        };
        
        this.animationId = requestAnimationFrame(update);
    }
    
    _stopTimeUpdate() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
            this.animationId = null;
        }
    }
    
    _fireTimeUpdate() {
        if (this.onTimeUpdate) {
            this.onTimeUpdate({
                currentTime: this.getCurrentTime(),
                duration: this.getDuration(),
                isPlaying: this.isPlaying
            });
        }
    }
    
    _updateStatus(message, type = 'info') {
        console.log(`NativeAudioPlayer: ${message}`);
        if (this.onStatusChange) {
            this.onStatusChange(message, type);
        }
    }
    
    /**
     * Dispose
     */
    dispose() {
        this.clear();
        console.log('NativeAudioPlayer disposed');
    }
}

// Export
window.NativeAudioPlayer = NativeAudioPlayer;

