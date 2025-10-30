/**
 * Smart Playback Engine with Time-Variable Correction
 * 
 * Applies real-time sync corrections during audio playback to preview
 * how repairs would sound before actually processing the files.
 */

class SmartPlaybackEngine {
    constructor() {
        this.audioContext = null;
        this.masterSource = null;
        this.dubSource = null;
        this.masterBuffer = null;
        this.dubBuffer = null;
        
        // Correction data
        this.correctionSegments = [];
        this.repairType = 'none';
        this.overallOffset = 0;
        this.isPlaying = false;
        this.startTime = 0;
        this.pauseTime = 0;
        
        // Audio nodes
        this.masterGainNode = null;
        this.dubGainNode = null;
        this.masterPanNode = null;
        this.dubPanNode = null;
        
        // State tracking
        this.playbackMode = 'original'; // 'original', 'corrected', 'preview'
        this.currentSegmentIndex = 0;
        
        this.initializeAudioContext();
    }
    
    async initializeAudioContext() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            
            // Create master audio chain: source -> gain -> pan -> destination
            this.masterGainNode = this.audioContext.createGain();
            this.masterPanNode = this.audioContext.createStereoPanner();
            this.masterGainNode.connect(this.masterPanNode);
            this.masterPanNode.connect(this.audioContext.destination);
            
            // Create dub audio chain: source -> gain -> pan -> destination  
            this.dubGainNode = this.audioContext.createGain();
            this.dubPanNode = this.audioContext.createStereoPanner();
            this.dubGainNode.connect(this.dubPanNode);
            this.dubPanNode.connect(this.audioContext.destination);
            
            // Set initial panning (master left, dub right for comparison)
            this.masterPanNode.pan.value = -0.5;
            this.dubPanNode.pan.value = 0.5;
            
            console.log('Smart Playback Engine initialized');
        } catch (error) {
            console.error('Failed to initialize audio context:', error);
            throw error;
        }
    }
    
    async loadAudioFiles(masterUrl, dubUrl) {
        try {
            console.log('Loading audio files for smart playback...');
            
            // Load both files concurrently
            const [masterResponse, dubResponse] = await Promise.all([
                fetch(masterUrl),
                fetch(dubUrl)
            ]);
            
            if (!masterResponse.ok || !dubResponse.ok) {
                throw new Error('Failed to fetch audio files');
            }
            
            const [masterArrayBuffer, dubArrayBuffer] = await Promise.all([
                masterResponse.arrayBuffer(),
                dubResponse.arrayBuffer()
            ]);
            
            // Decode audio data
            [this.masterBuffer, this.dubBuffer] = await Promise.all([
                this.audioContext.decodeAudioData(masterArrayBuffer),
                this.audioContext.decodeAudioData(dubArrayBuffer)
            ]);
            
            console.log('Audio files loaded successfully');
            console.log(`Master duration: ${this.masterBuffer.duration.toFixed(2)}s`);
            console.log(`Dub duration: ${this.dubBuffer.duration.toFixed(2)}s`);
            
            return {
                masterDuration: this.masterBuffer.duration,
                dubDuration: this.dubBuffer.duration
            };
            
        } catch (error) {
            console.error('Failed to load audio files:', error);
            throw error;
        }
    }
    
    loadCorrectionData(analysisData) {
        /**
         * Load correction data from analysis results
         * 
         * @param {Object} analysisData - Analysis results with timeline and correction info
         */
        console.log('Loading correction data...');
        
        // Extract overall offset
        this.overallOffset = analysisData.offset_seconds || 0;
        
        // Extract timeline for segment-based corrections
        const timeline = analysisData.timeline || [];
        this.correctionSegments = timeline.map(chunk => ({
            startTime: chunk.start_time || 0,
            endTime: chunk.end_time || 0,
            offsetSeconds: chunk.offset_seconds || 0,
            reliable: chunk.reliable || false,
            quality: chunk.quality || 'unknown'
        }));
        
        // Determine repair type
        if (this.correctionSegments.length === 0) {
            this.repairType = 'none';
        } else if (this.correctionSegments.length < 3) {
            this.repairType = 'simple_offset';
        } else {
            // Check for drift variation
            const offsets = this.correctionSegments
                .filter(seg => seg.reliable)
                .map(seg => seg.offsetSeconds);
                
            if (offsets.length > 1) {
                const offsetVariation = Math.max(...offsets) - Math.min(...offsets);
                if (offsetVariation > 0.5) {
                    this.repairType = 'time_variable';
                } else if (offsetVariation > 0.1) {
                    this.repairType = 'gradual';
                } else {
                    this.repairType = 'simple_offset';
                }
            } else {
                this.repairType = 'simple_offset';
            }
        }
        
        console.log(`Correction type: ${this.repairType}`);
        console.log(`Overall offset: ${this.overallOffset.toFixed(3)}s`);
        console.log(`Correction segments: ${this.correctionSegments.length}`);
        
        return {
            repairType: this.repairType,
            overallOffset: this.overallOffset,
            segmentsCount: this.correctionSegments.length
        };
    }
    
    async startPlayback(playbackMode = 'original', startTimeSeconds = 0) {
        /**
         * Start playback with specified correction mode
         * 
         * @param {string} playbackMode - 'original', 'corrected', or 'preview' 
         * @param {number} startTimeSeconds - Start time in seconds
         */
        if (!this.masterBuffer || !this.dubBuffer) {
            throw new Error('Audio files not loaded');
        }
        
        await this.audioContext.resume();
        
        // Stop any existing playback
        this.stopPlayback();
        
        this.playbackMode = playbackMode;
        this.startTime = this.audioContext.currentTime;
        this.pauseTime = startTimeSeconds;
        this.isPlaying = true;
        
        // Create audio source nodes
        this.masterSource = this.audioContext.createBufferSource();
        this.dubSource = this.audioContext.createBufferSource();
        
        this.masterSource.buffer = this.masterBuffer;
        this.dubSource.buffer = this.dubBuffer;
        
        // Connect sources to gain nodes
        this.masterSource.connect(this.masterGainNode);
        this.dubSource.connect(this.dubGainNode);
        
        // Configure playback based on mode
        switch (playbackMode) {
            case 'original':
                this.playOriginal(startTimeSeconds);
                break;
            case 'corrected':
                this.playCorrected(startTimeSeconds);
                break;
            case 'preview':
                this.playPreview(startTimeSeconds);
                break;
            default:
                throw new Error(`Unknown playback mode: ${playbackMode}`);
        }
        
        console.log(`Started ${playbackMode} playback from ${startTimeSeconds.toFixed(2)}s`);
    }
    
    playOriginal(startTimeSeconds) {
        /**
         * Play original files without any correction
         */
        this.masterSource.start(0, startTimeSeconds);
        this.dubSource.start(0, startTimeSeconds);
    }
    
    playCorrected(startTimeSeconds) {
        /**
         * Play with corrections applied based on repair type
         */
        switch (this.repairType) {
            case 'simple_offset':
                this.playWithSimpleOffset(startTimeSeconds);
                break;
            case 'gradual':
            case 'time_variable':
                this.playWithTimeVariableCorrection(startTimeSeconds);
                break;
            default:
                // No correction needed
                this.playOriginal(startTimeSeconds);
        }
    }
    
    playWithSimpleOffset(startTimeSeconds) {
        /**
         * Apply simple fixed offset correction
         */
        const correctedDubStart = startTimeSeconds - this.overallOffset;
        
        this.masterSource.start(0, startTimeSeconds);
        this.dubSource.start(0, Math.max(0, correctedDubStart));
        
        console.log(`Applied simple offset: ${this.overallOffset.toFixed(3)}s`);
    }
    
    playWithTimeVariableCorrection(startTimeSeconds) {
        /**
         * Apply time-variable correction using segment-based approach
         * This is a simplified version - full implementation would require
         * real-time buffer manipulation
         */
        // Find the segment containing the start time
        const currentSegment = this.correctionSegments.find(seg => 
            startTimeSeconds >= seg.startTime && startTimeSeconds < seg.endTime
        );
        
        let offset = this.overallOffset; // Default fallback
        if (currentSegment && currentSegment.reliable) {
            offset = currentSegment.offsetSeconds;
        }
        
        const correctedDubStart = startTimeSeconds - offset;
        
        this.masterSource.start(0, startTimeSeconds);
        this.dubSource.start(0, Math.max(0, correctedDubStart));
        
        console.log(`Applied segment offset: ${offset.toFixed(3)}s for time ${startTimeSeconds.toFixed(2)}s`);
        
        // Schedule segment transitions (simplified)
        this.scheduleSegmentTransitions(startTimeSeconds);
    }
    
    scheduleSegmentTransitions(startTimeSeconds) {
        /**
         * Schedule transitions between correction segments
         * Note: This is a simplified implementation
         */
        const relevantSegments = this.correctionSegments
            .filter(seg => seg.startTime > startTimeSeconds)
            .slice(0, 5); // Only schedule next few segments
            
        relevantSegments.forEach(segment => {
            const timeToSegment = segment.startTime - startTimeSeconds;
            
            setTimeout(() => {
                if (this.isPlaying) {
                    console.log(`Segment transition at ${segment.startTime.toFixed(2)}s, offset: ${segment.offsetSeconds.toFixed(3)}s`);
                    // In a full implementation, we would adjust playback rate or create new sources
                    this.onSegmentTransition(segment);
                }
            }, timeToSegment * 1000);
        });
    }
    
    onSegmentTransition(segment) {
        /**
         * Handle transition to a new correction segment
         * This is where more advanced correction would be applied
         */
        console.log(`Transitioned to segment: ${segment.startTime}-${segment.endTime}s, quality: ${segment.quality}`);
        
        // Dispatch event for UI updates
        const event = new CustomEvent('segmentTransition', {
            detail: {
                segment: segment,
                currentTime: this.getCurrentTime()
            }
        });
        document.dispatchEvent(event);
    }
    
    playPreview(startTimeSeconds) {
        /**
         * Preview mode - show corrections with visual indicators
         */
        this.playCorrected(startTimeSeconds);
        
        // Enable preview visualization
        this.enablePreviewVisualization();
    }
    
    enablePreviewVisualization() {
        /**
         * Enable visual indicators for correction preview
         */
        const interval = setInterval(() => {
            if (!this.isPlaying) {
                clearInterval(interval);
                return;
            }
            
            const currentTime = this.getCurrentTime();
            const currentSegment = this.getCurrentSegment(currentTime);
            
            // Dispatch event for UI visualization updates
            const event = new CustomEvent('previewUpdate', {
                detail: {
                    currentTime: currentTime,
                    currentSegment: currentSegment,
                    playbackMode: this.playbackMode
                }
            });
            document.dispatchEvent(event);
        }, 100); // Update every 100ms
    }
    
    stopPlayback() {
        /**
         * Stop current playback
         */
        if (this.masterSource) {
            this.masterSource.stop();
            this.masterSource.disconnect();
            this.masterSource = null;
        }
        
        if (this.dubSource) {
            this.dubSource.stop();
            this.dubSource.disconnect();
            this.dubSource = null;
        }
        
        this.isPlaying = false;
        console.log('Playback stopped');
    }
    
    pausePlayback() {
        /**
         * Pause current playback
         */
        if (this.isPlaying) {
            this.pauseTime = this.getCurrentTime();
            this.stopPlayback();
            console.log(`Playback paused at ${this.pauseTime.toFixed(2)}s`);
        }
    }
    
    resumePlayback() {
        /**
         * Resume paused playback
         */
        if (!this.isPlaying && this.pauseTime !== null) {
            this.startPlayback(this.playbackMode, this.pauseTime);
            console.log(`Playback resumed from ${this.pauseTime.toFixed(2)}s`);
        }
    }
    
    seekTo(timeSeconds) {
        /**
         * Seek to specific time
         */
        const wasPlaying = this.isPlaying;
        if (wasPlaying) {
            this.stopPlayback();
        }
        
        this.pauseTime = timeSeconds;
        
        if (wasPlaying) {
            this.startPlayback(this.playbackMode, timeSeconds);
        }
        
        console.log(`Seeked to ${timeSeconds.toFixed(2)}s`);
    }
    
    getCurrentTime() {
        /**
         * Get current playback time in seconds
         */
        if (!this.isPlaying || !this.startTime) {
            return this.pauseTime || 0;
        }
        
        return this.pauseTime + (this.audioContext.currentTime - this.startTime);
    }
    
    getCurrentSegment(currentTime) {
        /**
         * Get the correction segment for the current time
         */
        return this.correctionSegments.find(seg => 
            currentTime >= seg.startTime && currentTime < seg.endTime
        );
    }
    
    setVolume(masterVolume, dubVolume) {
        /**
         * Set volume levels for master and dub tracks
         */
        if (this.masterGainNode) {
            this.masterGainNode.gain.value = masterVolume;
        }
        if (this.dubGainNode) {
            this.dubGainNode.gain.value = dubVolume;
        }
    }
    
    setPanning(masterPan, dubPan) {
        /**
         * Set panning for master and dub tracks (-1 to 1)
         */
        if (this.masterPanNode) {
            this.masterPanNode.pan.value = masterPan;
        }
        if (this.dubPanNode) {
            this.dubPanNode.pan.value = dubPan;
        }
    }
    
    getPlaybackInfo() {
        /**
         * Get current playback information
         */
        return {
            isPlaying: this.isPlaying,
            currentTime: this.getCurrentTime(),
            playbackMode: this.playbackMode,
            repairType: this.repairType,
            overallOffset: this.overallOffset,
            currentSegment: this.getCurrentSegment(this.getCurrentTime()),
            segmentCount: this.correctionSegments.length
        };
    }
    
    destroy() {
        /**
         * Clean up resources
         */
        this.stopPlayback();
        
        if (this.audioContext) {
            this.audioContext.close();
        }
        
        console.log('Smart Playback Engine destroyed');
    }
}

// Export for use in other modules
window.SmartPlaybackEngine = SmartPlaybackEngine;