/**
 * Core Audio Engine for Real Waveform Analysis
 * Essential Web Audio API integration for actual audio file processing
 */

class CoreAudioEngine {
    constructor() {
        this.audioContext = null;
        this.masterBuffer = null;
        this.dubBuffer = null;
        this.masterElement = null;
        this.dubElement = null;
        this.masterSource = null;
        this.dubSource = null;
        this.masterGain = null;
        this.dubGain = null;
        this.masterPan = null;
        this.dubPan = null;
        this.masterElementSource = null;
        this.dubElementSource = null;
        this.outputGain = null; // not used; routing goes direct to destination for reliability
        this.masterWaveformData = null;
        this.dubWaveformData = null;
        
        // Callbacks
        this.onProgress = null;
        this.onAudioLoaded = null;
        this.onError = null;
        
        this.initializeAudioContext();
    }
    
    /**
     * Initialize Web Audio API context
     */
    async initializeAudioContext() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            // Route directly to destination for maximum compatibility
            
            console.log('Audio context initialized:', this.audioContext.state);
            
            // Ensure context is activated on first user interaction
            if (this.audioContext.state === 'suspended') {
                const activateAudio = async () => {
                    try {
                        await this.audioContext.resume();
                        console.log('AudioContext activated:', this.audioContext.state);
                        document.removeEventListener('click', activateAudio);
                        document.removeEventListener('touchstart', activateAudio);
                    } catch (e) {
                        console.warn('Failed to activate AudioContext:', e);
                    }
                };
                document.addEventListener('click', activateAudio, { once: true });
                document.addEventListener('touchstart', activateAudio, { once: true });
            }
            
        } catch (error) {
            console.error('Failed to initialize audio context:', error);
            if (this.onError) this.onError('Web Audio API not supported');
        }
    }
    ensureOutputGain() { /* no-op: using direct destination routing */ }
    
    /**
     * Load and process audio file into waveform data
     */
    async loadAudioFile(file, type = 'master') {
        if (!this.audioContext) {
            throw new Error('Audio context not initialized');
        }
        
        try {
            this.updateProgress(`Loading ${type} file...`, 10);
            
            // Read file as array buffer
            const arrayBuffer = await this.readFileAsArrayBuffer(file);
            this.updateProgress(`Decoding ${type} audio...`, 40);
            
            // Decode audio data
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            this.updateProgress(`Processing ${type} waveform...`, 70);
            
            // Generate waveform data
            const waveformData = this.generateWaveformData(audioBuffer);
            
            // Store results
            if (type === 'master') {
                this.masterBuffer = audioBuffer;
                this.masterWaveformData = waveformData;
            } else {
                this.dubBuffer = audioBuffer;
                this.dubWaveformData = waveformData;
            }
            
            this.updateProgress(`${type} file processed successfully`, 100);
            
            // Notify completion
            if (this.onAudioLoaded) {
                this.onAudioLoaded(type, {
                    buffer: audioBuffer,
                    waveformData: waveformData,
                    metadata: {
                        duration: audioBuffer.duration,
                        sampleRate: audioBuffer.sampleRate,
                        channels: audioBuffer.numberOfChannels,
                        length: audioBuffer.length
                    }
                });
            }
            
            return waveformData;
            
        } catch (error) {
            console.error(`Failed to load ${type} file:`, error);
            if (this.onError) this.onError(`Unable to load ${type} audio file: ${error.message}`);
            throw error;
        }
    }

    /**
     * Load and process audio from a URL
     */
    async loadAudioUrl(url, type = 'master') {
        if (!this.audioContext) {
            throw new Error('Audio context not initialized');
        }
        try {
            this.updateProgress(`Fetching ${type} from URL...`, 10);
            // Avoid 304 caching issues by bypassing cache
            let resp = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
            if (resp.status === 304) {
                try { resp = await fetch(url, { credentials: 'same-origin', cache: 'reload' }); } catch {}
            }
            if (!resp.ok) {
                try { window.showToast?.('error', `${type} fetch failed: HTTP ${resp.status} — ${url}`, 'Audio Load'); } catch {}
                throw new Error(`HTTP ${resp.status}`);
            }
            const arrayBuffer = await resp.arrayBuffer();
            this.updateProgress(`Decoding ${type} audio...`, 50);
            let audioBuffer = null;
            let usedProxy = false;
            const rawPath = this._extractPathFromRawUrl(url);
            try {
                audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            } catch (decodeErr) {
                console.warn('decodeAudioData failed:', decodeErr);
                // Try proxy first when loading from our raw endpoint
                if (rawPath) {
                    try {
                        this.updateProgress(`Transcoding ${type} via proxy...`, 60);
                        const proxyUrl = `/api/v1/files/proxy-audio?path=${encodeURIComponent(rawPath)}&format=wav`;
                        const pResp = await fetch(proxyUrl, { credentials: 'same-origin' });
                        if (!pResp.ok) {
                            try { window.showToast?.('error', `${type} proxy failed: HTTP ${pResp.status} — ${proxyUrl}`, 'Audio Proxy'); } catch {}
                            throw new Error(`Proxy HTTP ${pResp.status}`);
                        }
                        const pBuf = await pResp.arrayBuffer();
                        audioBuffer = await this.audioContext.decodeAudioData(pBuf);
                        usedProxy = true;
                        console.info('Proxy decode succeeded for', type);
                    } catch (proxyErr) {
                        console.warn('Proxy decode failed, falling back to media element:', proxyErr);
                        await this._loadViaMediaElement(url, type);
                        const el = type === 'master' ? this.masterElement : this.dubElement;
                        await new Promise((res) => {
                            if (el.readyState >= 1) return res();
                            el.addEventListener('loadedmetadata', () => res(), { once: true });
                        });
                        const duration = el.duration || 0;
                        const targetWidth = Math.min(4000, Math.max(800, Math.floor(duration * 100)));
                        const peaks = new Float32Array(targetWidth).fill(0); // placeholder
                        const waveformData = { peaks, rms: new Float32Array(targetWidth).fill(0), duration, sampleRate: 44100, width: targetWidth };
                        if (type === 'master') {
                            this.masterWaveformData = waveformData;
                        } else {
                            this.dubWaveformData = waveformData;
                        }
                        if (this.onAudioLoaded) {
                            this.onAudioLoaded(type, {
                                buffer: null,
                                waveformData,
                                metadata: { duration, sampleRate: 44100, source: 'media-element' }
                            });
                        }
                        return waveformData;
                    }
                } else {
                    // Not a raw URL; fall back directly to media element
                    try { await this._loadViaMediaElement(url, type); }
                    catch (me) {
                        try { window.showToast?.('error', `${type} media element load failed — ${url}`, 'Audio Load'); } catch {}
                        throw me;
                    }
                    const el = type === 'master' ? this.masterElement : this.dubElement;
                    await new Promise((res) => {
                        if (el.readyState >= 1) return res();
                        el.addEventListener('loadedmetadata', () => res(), { once: true });
                    });
                    const duration = el.duration || 0;
                    const targetWidth = Math.min(4000, Math.max(800, Math.floor(duration * 100)));
                    const peaks = new Float32Array(targetWidth).fill(0); // placeholder
                    const waveformData = { peaks, rms: new Float32Array(targetWidth).fill(0), duration, sampleRate: 44100, width: targetWidth };
                    if (type === 'master') {
                        this.masterWaveformData = waveformData;
                    } else {
                        this.dubWaveformData = waveformData;
                    }
                    if (this.onAudioLoaded) {
                        this.onAudioLoaded(type, {
                            buffer: null,
                            waveformData,
                            metadata: { duration, sampleRate: 44100, source: 'media-element' }
                        });
                    }
                    return waveformData;
                }
            }
            this.updateProgress(`Processing ${type} waveform...`, 80);
            const waveformData = this.generateWaveformData(audioBuffer);
            if (type === 'master') {
                this.masterBuffer = audioBuffer;
                this.masterWaveformData = waveformData;
            } else {
                this.dubBuffer = audioBuffer;
                this.dubWaveformData = waveformData;
            }
            this.updateProgress(`${type} URL processed successfully`, 100);
            if (this.onAudioLoaded) {
                this.onAudioLoaded(type, {
                    buffer: audioBuffer,
                    waveformData: waveformData,
                    metadata: {
                        duration: audioBuffer.duration,
                        sampleRate: audioBuffer.sampleRate,
                        channels: audioBuffer.numberOfChannels,
                        length: audioBuffer.length,
                        source: usedProxy ? 'proxy' : (rawPath ? 'raw' : 'url')
                    }
                });
            }
            return waveformData;
        } catch (e) {
            try { window.showToast?.('error', `Failed to load ${type}: ${e.message} — ${url}`, 'Audio Load'); } catch {}
            if (this.onError) this.onError(`Failed to load ${type} from URL: ${e.message}`);
            throw e;
        }
    }

    async _loadViaMediaElement(url, type) {
        // Choose element based on likely content type from URL
        const lower = (typeof url === 'string' ? url.split('?')[0].toLowerCase() : '').toString();
        const isVideo = lower.endsWith('.mp4') || lower.endsWith('.mov') || lower.endsWith('.mkv') || lower.endsWith('.avi');
        const el = document.createElement(isVideo ? 'video' : 'audio');
        el.style.display = 'none';
        // Don't set crossOrigin for same-origin requests (UI and API served from same server)
        // el.crossOrigin = 'use-credentials';
        el.preload = 'auto';
        el.playsInline = true;
        el.src = url;
        document.body.appendChild(el);
        await new Promise((resolve, reject) => {
            const onError = () => {
                try { window.showToast?.('error', `Media element error — ${url}`, 'Audio Load'); } catch {}
                reject(new Error('Media element failed to load'));
            };
            el.addEventListener('error', onError, { once: true });
            el.addEventListener('loadedmetadata', () => resolve(), { once: true });
        });
        if (type === 'master') this.masterElement = el; else this.dubElement = el;
        return el;
    }

    _extractPathFromRawUrl(url) {
        try {
            const u = new URL(url, window.location.origin);
            if (u.pathname.endsWith('/api/v1/files/raw')) {
                return u.searchParams.get('path');
            }
            return null;
        } catch (e) {
            if (typeof url === 'string' && url.startsWith('/api/v1/files/raw?')) {
                const q = url.split('?')[1] || '';
                const params = new URLSearchParams(q);
                return params.get('path');
            }
            return null;
        }
    }
    
    /**
     * Read file as array buffer
     */
    readFileAsArrayBuffer(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error('Failed to read file'));
            
            reader.onprogress = (event) => {
                if (event.lengthComputable) {
                    const progress = 10 + (event.loaded / event.total) * 30; // 10-40% of total
                    this.updateProgress('Reading file...', progress);
                }
            };
            
            reader.readAsArrayBuffer(file);
        });
    }
    
    /**
     * Generate waveform data from audio buffer
     */
    generateWaveformData(audioBuffer) {
        const channelData = audioBuffer.getChannelData(0); // Use first channel
        const sampleRate = audioBuffer.sampleRate;
        const duration = audioBuffer.duration;
        const length = channelData.length;
        
        // Calculate resolution - aim for 1-2 pixels per sample for good detail
        const targetWidth = Math.min(4000, Math.max(800, Math.floor(duration * 100)));
        const samplesPerPixel = Math.floor(length / targetWidth);
        
        const peaks = new Float32Array(targetWidth);
        const rms = new Float32Array(targetWidth);
        
        // Generate peak and RMS data
        for (let i = 0; i < targetWidth; i++) {
            const startSample = i * samplesPerPixel;
            const endSample = Math.min(startSample + samplesPerPixel, length);
            
            let peak = 0;
            let sum = 0;
            let count = 0;
            
            for (let j = startSample; j < endSample; j++) {
                const sample = Math.abs(channelData[j]);
                peak = Math.max(peak, sample);
                sum += sample * sample;
                count++;
            }
            
            peaks[i] = peak;
            rms[i] = count > 0 ? Math.sqrt(sum / count) : 0;
        }
        
        return {
            peaks: peaks,
            rms: rms,
            duration: duration,
            sampleRate: sampleRate,
            samplesPerPixel: samplesPerPixel,
            width: targetWidth,
            originalLength: length
        };
    }
    
    /**
     * Get waveform data for specific track
     */
    getWaveformData(type) {
        return type === 'master' ? this.masterWaveformData : this.dubWaveformData;
    }
    
    /**
     * Check if audio file type is supported
     */
    isAudioFile(file) {
        const supportedTypes = [
            'audio/wav', 'audio/wave', 'audio/x-wav',
            'audio/mp3', 'audio/mpeg',
            'audio/flac',
            'audio/m4a', 'audio/mp4',
            'audio/aiff', 'audio/x-aiff',
            'audio/aac',
            'audio/ogg'
        ];
        
        const supportedExtensions = ['.wav', '.mp3', '.flac', '.m4a', '.aiff', '.aac', '.ogg'];
        
        return supportedTypes.includes(file.type) || 
               supportedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    }
    
    /**
     * Update progress callback
     */
    updateProgress(message, percentage) {
        if (this.onProgress) {
            this.onProgress(message, Math.round(percentage));
        }
    }
    
    /**
     * Clean up resources
     */
    dispose() {
        this.stopPlayback();
        if (this.audioContext && this.audioContext.state !== 'closed') {
            this.audioContext.close();
        }
        this.masterBuffer = null;
        this.dubBuffer = null;
        this.masterWaveformData = null;
        this.dubWaveformData = null;
    }

    /**
     * Stop any active playback
     */
    stopPlayback() {
        try {
            if (this.masterSource) {
                this.masterSource.stop();
            }
        } catch {}
        try {
            if (this.dubSource) {
                this.dubSource.stop();
            }
        } catch {}
        this.masterSource = null;
        this.dubSource = null;
        this.isPlaying = false;
        // Pause media elements
        try { this.masterElement?.pause(); } catch {}
        try { this.dubElement?.pause(); } catch {}
        if (this.masterElement) this.masterElement.currentTime = 0;
        if (this.dubElement) this.dubElement.currentTime = 0;
        // Disconnect processing nodes (keep MediaElementSource instances for reuse)
        try { this.masterGain?.disconnect(); } catch {}
        try { this.dubGain?.disconnect(); } catch {}
        try { this.masterPan?.disconnect(); } catch {}
        try { this.dubPan?.disconnect(); } catch {}
        this.masterGain = null;
        this.dubGain = null;
        this.masterPan = null;
        this.dubPan = null;
    }

    /**
     * Play master and dub with specified offset. If corrected=true, align content.
     */
    playComparison(offsetSeconds = 0, corrected = false, startAt = 0) {
        const haveBuffers = !!(this.masterBuffer && this.dubBuffer);
        const haveElements = !!(this.masterElement && this.dubElement);
        if (!this.audioContext || (!haveBuffers && !haveElements)) {
            if (this.onError) this.onError('Load both Master and Dub audio to play');
            return;
        }

        // Store playback parameters for seek operations
        this.lastOffsetSeconds = offsetSeconds;
        this.lastCorrected = corrected;

        const run = async () => {
            // Ensure running state
            if (this.audioContext.state === 'suspended') {
                try {
                    await this.audioContext.resume();
                    console.log('AudioContext resumed for playback:', this.audioContext.state);
                } catch (e) {
                    console.warn('Failed to resume AudioContext:', e);
                    if (this.onError) this.onError('Audio playback requires user interaction. Please click a button first.');
                    return;
                }
            }

            // Stop any current playback
            this.stopPlayback();

            const now = this.audioContext.currentTime + 0.05; // small scheduling delay
            const safeStartAt = Math.max(0, Number(startAt) || 0);
            this.lastStartAt = safeStartAt;
            this.playStartClock = now;

            // Prepare pan nodes (L/R split) with safe fallback
            const createStereoChain = () => {
                const nodes = {};
                nodes.gain = this.audioContext.createGain();
                // Try StereoPanner for simple hard pan
                if (this.audioContext.createStereoPanner) {
                    nodes.panner = this.audioContext.createStereoPanner();
                } else {
                    // Fallback: emulate pan with channel splitter/merger
                    nodes.splitter = this.audioContext.createChannelSplitter(2);
                    nodes.leftGain = this.audioContext.createGain();
                    nodes.rightGain = this.audioContext.createGain();
                    nodes.merger = this.audioContext.createChannelMerger(2);
                }
                return nodes;
            };

            if (haveBuffers) {
                this.ensureOutputGain();
                // Create sources
                this.masterSource = this.audioContext.createBufferSource();
                this.masterSource.buffer = this.masterBuffer;
                this.dubSource = this.audioContext.createBufferSource();
                this.dubSource.buffer = this.dubBuffer;

                // Gains and panners
                const m = createStereoChain();
                const d = createStereoChain();
                this.masterGain = m.gain; this.dubGain = d.gain;
                this.masterPan = m.panner || m; this.dubPan = d.panner || d;

                // Preserve previous desired gains if set
                this.masterGainValue = this.masterGainValue ?? 0.8;
                this.dubGainValue = this.dubGainValue ?? 0.8;
                this.masterGain.gain.value = this.masterGainValue;
                this.dubGain.gain.value = this.dubGainValue;

                // Connect master chain
                const outNode = this.audioContext.destination;
                if (m.panner) {
                    try { m.panner.pan.value = -1; } catch {}
                    this.masterSource.connect(m.gain).connect(m.panner).connect(outNode);
                } else {
                    // Hard route to left only
                    this.masterSource.connect(m.gain).connect(m.splitter);
                    m.splitter.connect(m.leftGain, 0);
                    m.splitter.connect(m.rightGain, 1);
                    m.leftGain.gain.value = 1.0;
                    m.rightGain.gain.value = 0.0;
                    m.leftGain.connect(m.merger, 0, 0);
                    m.rightGain.connect(m.merger, 0, 1);
                    m.merger.connect(outNode);
                }

                // Connect dub chain
                if (d.panner) {
                    try { d.panner.pan.value = 1; } catch {}
                    this.dubSource.connect(d.gain).connect(d.panner).connect(outNode);
                } else {
                    // Hard route to right only
                    this.dubSource.connect(d.gain).connect(d.splitter);
                    d.splitter.connect(d.leftGain, 0);
                    d.splitter.connect(d.rightGain, 1);
                    d.leftGain.gain.value = 0.0;
                    d.rightGain.gain.value = 1.0;
                    d.leftGain.connect(d.merger, 0, 0);
                    d.rightGain.connect(d.merger, 0, 1);
                    d.merger.connect(outNode);
                }
                // Apply any balance/mute and pan defaults
                this.masterPanValue = (typeof this.masterPanValue === 'number') ? this.masterPanValue : -1;
                this.dubPanValue = (typeof this.dubPanValue === 'number') ? this.dubPanValue : 1;
                this.applyPan('master');
                this.applyPan('dub');
                this.updateTrackGains();
            }

            // Compute buffer offsets so playback aligns as requested
            let masterOffset = safeStartAt;
            let dubOffset = safeStartAt;
            let masterWhen = now;
            let dubWhen = now;

            if (haveBuffers) {
                if (!corrected) {
                    // BEFORE FIX: Play files as-is to hear the natural sync problem
                    // No timing adjustments - let the inherent offset be audible
                } else {
                    // AFTER FIX: Apply correction by offsetting buffer positions
                    if (offsetSeconds > 0) {
                        // Dub is early - skip ahead in dub buffer
                        dubOffset = Math.min(Math.max(0, safeStartAt + offsetSeconds), Math.max(0.01, this.dubBuffer.duration - 0.1));
                    } else if (offsetSeconds < 0) {
                        // Dub is late - skip ahead in master buffer  
                        masterOffset = Math.min(Math.max(0, safeStartAt + Math.abs(offsetSeconds)), Math.max(0.01, this.masterBuffer.duration - 0.1));
                    }
                }
            }

            if (haveBuffers) {
                try {
                    this.masterSource.start(masterWhen, masterOffset);
                    this.dubSource.start(dubWhen, dubOffset);
                } catch (e) {
                    if (this.onError) this.onError('Playback start failed: ' + e.message);
                }
            } else if (haveElements) {
                // Element-based playback using WebAudio graph for stereo split
                const mEl = this.masterElement;
                const dEl = this.dubElement;

                // Reset elements
                try { mEl.pause(); dEl.pause(); } catch {}
                mEl.currentTime = safeStartAt; dEl.currentTime = safeStartAt;

                // Create/reuse MediaElementSource (only allowed once per element)
                if (!this.masterElementSource) {
                    try { 
                        this.masterElementSource = this.audioContext.createMediaElementSource(mEl); 
                        console.log('Created MediaElementSource for master');
                    } catch (e) {
                        console.warn('Failed to create MediaElementSource for master:', e);
                    }
                }
                if (!this.dubElementSource) {
                    try { 
                        this.dubElementSource = this.audioContext.createMediaElementSource(dEl); 
                        console.log('Created MediaElementSource for dub');
                    } catch (e) {
                        console.warn('Failed to create MediaElementSource for dub:', e);
                    }
                }

                try {
                    // Gains and panners
                    this.ensureOutputGain();
                    const m = { gain: this.audioContext.createGain() };
                    const d = { gain: this.audioContext.createGain() };
                    if (this.audioContext.createStereoPanner) {
                        m.panner = this.audioContext.createStereoPanner();
                        d.panner = this.audioContext.createStereoPanner();
                    }
                    this.masterGain = m.gain; this.dubGain = d.gain;
                    this.masterPan = m.panner || null; this.dubPan = d.panner || null;

                    // Apply current volumes
                    this.masterGainValue = this.masterGainValue ?? (typeof mEl.volume === 'number' ? mEl.volume : 0.8);
                    this.dubGainValue = this.dubGainValue ?? (typeof dEl.volume === 'number' ? dEl.volume : 0.8);
                    this.masterGain.gain.value = this.masterGainValue;
                    this.dubGain.gain.value = this.dubGainValue;
                    // Max element volume; use GainNode for control
                    mEl.volume = 1.0;
                    dEl.volume = 1.0;

                    // Connect graph
                    if (!this.masterElementSource || !this.dubElementSource) throw new Error('MediaElementSource missing');
                const outNode2 = this.audioContext.destination;
                if (m.panner) {
                    try { m.panner.pan.value = -1; } catch {}
                    this.masterElementSource.connect(m.gain).connect(m.panner).connect(outNode2);
                } else {
                    // Fallback: emulate pan
                    m.splitter = this.audioContext.createChannelSplitter(2);
                    m.leftGain = this.audioContext.createGain();
                    m.rightGain = this.audioContext.createGain();
                    m.merger = this.audioContext.createChannelMerger(2);
                    this.masterElementSource.connect(m.gain).connect(m.splitter);
                    m.splitter.connect(m.leftGain, 0);
                    m.splitter.connect(m.rightGain, 1);
                    m.leftGain.connect(m.merger, 0, 0);
                    m.rightGain.connect(m.merger, 0, 1);
                    m.merger.connect(outNode2);
                    this.masterPan = m; // ensure applyPan() can adjust fallback gains
                }
                if (d.panner) {
                    try { d.panner.pan.value = 1; } catch {}
                    this.dubElementSource.connect(d.gain).connect(d.panner).connect(outNode2);
                } else {
                    // Fallback: emulate pan
                    d.splitter = this.audioContext.createChannelSplitter(2);
                    d.leftGain = this.audioContext.createGain();
                    d.rightGain = this.audioContext.createGain();
                    d.merger = this.audioContext.createChannelMerger(2);
                    this.dubElementSource.connect(d.gain).connect(d.splitter);
                    d.splitter.connect(d.leftGain, 0);
                    d.splitter.connect(d.rightGain, 1);
                    d.leftGain.connect(d.merger, 0, 0);
                    d.rightGain.connect(d.merger, 0, 1);
                    d.merger.connect(outNode2);
                    this.dubPan = d;
                }

                    // Apply pan and gains
                    this.masterPanValue = (typeof this.masterPanValue === 'number') ? this.masterPanValue : -1;
                    this.dubPanValue = (typeof this.dubPanValue === 'number') ? this.dubPanValue : 1;
                    this.applyPan('master');
                    this.applyPan('dub');
                    this.updateTrackGains();
                } catch (graphErr) {
                    console.warn('WebAudio graph failed; falling back to direct element playback:', graphErr);
                    try { window.showToast?.('warning', 'Audio engine fell back to direct playback (no pan)', 'Audio'); } catch {}
                    // Fall back: use HTML media elements directly (no pan), keep volumes
                    mEl.volume = this.masterGainValue ?? 0.8;
                    dEl.volume = this.dubGainValue ?? 0.8;
                }

                const startElements = () => {
                    console.log('[CoreAudioEngine] startElements - corrected:', corrected, 'offsetSeconds:', offsetSeconds, 'safeStartAt:', safeStartAt);
                    
                    if (!corrected) {
                        // BEFORE FIX: Play files as-is to hear the natural sync problem
                        // Both start at same position - natural offset in content will be audible
                        console.log('[CoreAudioEngine] BEFORE FIX mode - playing both at same position');
                        mEl.currentTime = safeStartAt;
                        dEl.currentTime = safeStartAt;
                        mEl.play().catch((e)=>{ try{ window.showToast?.('error', 'Master play blocked: '+e.message, 'Audio'); }catch{} });
                        dEl.play().catch((e)=>{ try{ window.showToast?.('error', 'Dub play blocked: '+e.message, 'Audio'); }catch{} });
                    } else {
                        // AFTER FIX: Apply correction by offsetting playback positions
                        console.log('[CoreAudioEngine] AFTER FIX mode - applying correction, offset:', offsetSeconds);
                        if (offsetSeconds > 0) {
                            // Dub is early (dub content is ahead of master)
                            // To fix: skip ahead in dub file by offset amount
                            const dubStartTime = Math.min(dEl.duration - 0.1, Math.max(0, safeStartAt + offsetSeconds));
                            console.log('[CoreAudioEngine] Dub is early by', offsetSeconds, 's - skipping dub to', dubStartTime);
                            mEl.currentTime = safeStartAt;
                            dEl.currentTime = dubStartTime;
                            mEl.play().catch((e)=>{ try{ window.showToast?.('error', 'Master play blocked: '+e.message, 'Audio'); }catch{} });
                            dEl.play().catch((e)=>{ try{ window.showToast?.('error', 'Dub play blocked: '+e.message, 'Audio'); }catch{} });
                        } else if (offsetSeconds < 0) {
                            // Dub is late (dub content is behind master)
                            // To fix: skip ahead in master file by |offset| amount
                            const masterStartTime = Math.min(mEl.duration - 0.1, Math.max(0, safeStartAt + Math.abs(offsetSeconds)));
                            console.log('[CoreAudioEngine] Dub is late by', Math.abs(offsetSeconds), 's - skipping master to', masterStartTime);
                            mEl.currentTime = masterStartTime;
                            dEl.currentTime = safeStartAt;
                            mEl.play().catch((e)=>{ try{ window.showToast?.('error', 'Master play blocked: '+e.message, 'Audio'); }catch{} });
                            dEl.play().catch((e)=>{ try{ window.showToast?.('error', 'Dub play blocked: '+e.message, 'Audio'); }catch{} });
                        } else {
                            // No offset - play synchronized
                            console.log('[CoreAudioEngine] No offset - playing synchronized');
                            mEl.currentTime = safeStartAt;
                            dEl.currentTime = safeStartAt;
                            mEl.play().catch((e)=>{ try{ window.showToast?.('error', 'Master play blocked: '+e.message, 'Audio'); }catch{} });
                            dEl.play().catch((e)=>{ try{ window.showToast?.('error', 'Dub play blocked: '+e.message, 'Audio'); }catch{} });
                        }
                    }
                };

                if ((mEl.readyState || 0) < 3 || (dEl.readyState || 0) < 3) {
                    const waitPromises = [];
                    if ((mEl.readyState || 0) < 3) waitPromises.push(new Promise(res => mEl.addEventListener('canplay', res, { once: true })));
                    if ((dEl.readyState || 0) < 3) waitPromises.push(new Promise(res => dEl.addEventListener('canplay', res, { once: true })));
                    Promise.all(waitPromises).then(startElements).catch(() => startElements());
                } else {
                    startElements();
                }
            }
            this.isPlaying = true;
        };
        run();
    }

    /**
     * Get current playback times (seconds)
     */
    getCurrentTimes() {
        const res = { master: 0, dub: 0, duration: 0 };
        if (this.masterBuffer) res.duration = Math.max(res.duration, this.masterBuffer.duration);
        if (this.dubBuffer) res.duration = Math.max(res.duration, this.dubBuffer.duration);
        if (this.masterElement) res.duration = Math.max(res.duration, this.masterElement.duration || 0);
        if (this.dubElement) res.duration = Math.max(res.duration, this.dubElement.duration || 0);
        if (this.masterElement || this.dubElement) {
            res.master = this.masterElement?.currentTime || 0;
            res.dub = this.dubElement?.currentTime || 0;
            return res;
        }
        if (this.masterBuffer && this.isPlaying) {
            const elapsed = Math.max(0, this.audioContext.currentTime - this.playStartClock);
            res.master = Math.min(this.masterBuffer.duration, this.lastStartAt + elapsed);
        }
        if (this.dubBuffer && this.isPlaying) {
            const elapsed = Math.max(0, this.audioContext.currentTime - this.playStartClock);
            res.dub = Math.min(this.dubBuffer.duration, this.lastStartAt + elapsed);
        }
        return res;
    }

    /**
     * Adjust volume of master or dub (0.0 - 1.0)
     */
    setVolume(track, value) {
        const v = Math.max(0, Math.min(1, Number(value) || 0));
        if (track === 'master') {
            this.masterGainValue = v;
            if (this.masterGain) this.updateTrackGains();
            if (this.masterElement && !this.masterElementSource) this.masterElement.volume = v;
        } else if (track === 'dub') {
            this.dubGainValue = v;
            if (this.dubGain) this.updateTrackGains();
            if (this.dubElement && !this.dubElementSource) this.dubElement.volume = v;
        }
    }

    // Overall output volume (0..1)
    setMasterOutputVolume(value) {
        const v = Math.max(0, Math.min(1, Number(value) || 0));
        this.masterOutputValue = v;
        this.updateTrackGains();
    }

    // Balance between master (-1) and dub (+1)
    setBalance(value) {
        const b = Math.max(-1, Math.min(1, Number(value) || 0));
        this.balanceValue = b;
        this.updateTrackGains();
    }

    // Per-track mute
    setMute(track, muted) {
        const on = !!muted;
        if (track === 'master') this.muteMaster = on;
        if (track === 'dub') this.muteDub = on;
        this.updateTrackGains();
    }

    // Per-track pan (-1..1)
    setPan(track, value) {
        const v = Math.max(-1, Math.min(1, Number(value) || 0));
        if (track === 'master') this.masterPanValue = v;
        if (track === 'dub') this.dubPanValue = v;
        this.applyPan(track);
    }

    applyPan(track) {
        const target = track === 'master' ? this.masterPan : this.dubPan;
        const v = track === 'master' ? (this.masterPanValue ?? 0) : (this.dubPanValue ?? 0);
        if (!target) return;
        if (target.pan && typeof target.pan.setValueAtTime === 'function') {
            try { target.pan.setValueAtTime(v, this.audioContext.currentTime); } catch { try { target.pan.value = v; } catch {} }
        } else {
            // Fallback chain object with leftGain/rightGain
            try {
                const left = Math.max(0, (1 - v) / 2);   // v=-1 =>1, v=1=>0
                const right = Math.max(0, (1 + v) / 2);  // v=-1 =>0, v=1=>1
                if (target.leftGain) target.leftGain.gain.value = left;
                if (target.rightGain) target.rightGain.gain.value = right;
            } catch {}
        }
    }

    updateTrackGains() {
        // Compute balance scales
        const b = this.balanceValue ?? 0; // -1..1
        const masterScale = 1 - Math.max(0, b);
        const dubScale = 1 - Math.max(0, -b);
        const masterBase = this.masterGainValue ?? 0.8;
        const dubBase = this.dubGainValue ?? 0.8;
        const mMute = this.muteMaster ? 0 : 1;
        const dMute = this.muteDub ? 0 : 1;
        const out = this.masterOutputValue ?? 1.0;
        const mVal = Math.max(0, Math.min(1, masterBase * masterScale * mMute * out));
        const dVal = Math.max(0, Math.min(1, dubBase * dubScale * dMute * out));
        
        console.log('Updating track gains:', { masterBase, dubBase, mVal, dVal, balance: b, output: out });
        
        try { if (this.masterGain) this.masterGain.gain.value = mVal; } catch {}
        try { if (this.dubGain) this.dubGain.gain.value = dVal; } catch {}
        // If we are not using MediaElementSource, also reflect on element volumes
        if (this.masterElement && !this.masterElementSource) this.masterElement.volume = mVal;
        if (this.dubElement && !this.dubElementSource) this.dubElement.volume = dVal;
    }
    
    /**
     * Seek to a specific time position (in seconds)
     * Works with both buffer-based and media element playback
     */
    seekTo(time) {
        const seekTime = Math.max(0, Number(time) || 0);
        console.log('CoreAudioEngine.seekTo:', seekTime);
        
        // For media elements - can seek directly
        if (this.masterElement) {
            const maxTime = this.masterElement.duration || 0;
            this.masterElement.currentTime = Math.min(seekTime, maxTime);
        }
        if (this.dubElement) {
            const maxTime = this.dubElement.duration || 0;
            this.dubElement.currentTime = Math.min(seekTime, maxTime);
        }
        
        // For buffer-based playback - need to restart from new position
        if ((this.masterBuffer || this.dubBuffer) && this.isPlaying) {
            // Get current offset setting
            const currentOffset = this.lastOffsetSeconds || 0;
            const corrected = this.lastCorrected || false;
            
            // Restart playback from new position
            this.playComparison(currentOffset, corrected, seekTime);
        }
        
        // Update tracking vars
        this.lastStartAt = seekTime;
        if (this.audioContext) {
            this.playStartClock = this.audioContext.currentTime;
        }
    }
    
    /**
     * Get current playback position (in seconds)
     */
    getCurrentTime() {
        // Media elements have direct currentTime
        if (this.masterElement) {
            return this.masterElement.currentTime || 0;
        }
        if (this.dubElement) {
            return this.dubElement.currentTime || 0;
        }
        
        // Buffer-based: calculate from start time
        if (this.isPlaying && this.audioContext && typeof this.playStartClock === 'number') {
            const elapsed = Math.max(0, this.audioContext.currentTime - this.playStartClock);
            return (this.lastStartAt || 0) + elapsed;
        }
        
        return this.lastStartAt || 0;
    }
    
    /**
     * Get total duration of loaded audio
     */
    getDuration() {
        let duration = 0;
        if (this.masterBuffer) duration = Math.max(duration, this.masterBuffer.duration);
        if (this.dubBuffer) duration = Math.max(duration, this.dubBuffer.duration);
        if (this.masterElement) duration = Math.max(duration, this.masterElement.duration || 0);
        if (this.dubElement) duration = Math.max(duration, this.dubElement.duration || 0);
        return duration;
    }

    /**
     * Get audio engine status for debugging
     */
    getStatus() {
        return {
            audioContextState: this.audioContext?.state,
            masterBufferLoaded: !!this.masterBuffer,
            dubBufferLoaded: !!this.dubBuffer,
            masterElementLoaded: !!this.masterElement,
            dubElementLoaded: !!this.dubElement,
            masterGainValue: this.masterGainValue,
            dubGainValue: this.dubGainValue,
            isPlaying: this.isPlaying
        };
    }
}

// Export for global access
window.CoreAudioEngine = CoreAudioEngine;
