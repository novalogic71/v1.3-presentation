/**
 * Enhanced Waveform Integration
 * Adds real audio file loading capability to existing waveform system
 */

// Extend the existing WaveformVisualizer with real audio capabilities
if (window.WaveformVisualizer) {
    const originalConstructor = window.WaveformVisualizer;
    
    window.WaveformVisualizer = function() {
        // Call original constructor
        originalConstructor.call(this);
        
        // Add real audio data storage
        this.realAudioData = new Map();
        
        // Initialize audio engine
        this.audioEngine = new CoreAudioEngine();
        this.setupAudioEngineCallbacks();
    };
    
    // Inherit from original prototype
    window.WaveformVisualizer.prototype = Object.create(originalConstructor.prototype);
    window.WaveformVisualizer.prototype.constructor = window.WaveformVisualizer;
    
    // Add new methods
    window.WaveformVisualizer.prototype.setupAudioEngineCallbacks = function() {
        this.audioEngine.onProgress = (message, percentage) => {
            console.log(`Audio processing: ${message} (${percentage}%)`);
        };
        
        this.audioEngine.onAudioLoaded = (type, data) => {
            this.realAudioData.set(type, data.waveformData);
            console.log(`Real ${type} audio loaded:`, data.metadata);
            try { window.showToast?.('success', `${type} audio loaded (${Math.round((data.metadata?.duration||0))}s)`, 'Audio'); } catch {}
        };
        
        this.audioEngine.onError = (error) => {
            console.error('Audio engine error:', error);
            try { window.showToast?.('error', String(error), 'Audio'); } catch {}
        };
    };
    
    // Override generateRealisticWaveformData to use real audio when available
    const originalGenerateWaveformData = window.WaveformVisualizer.prototype.generateRealisticWaveformData;
    window.WaveformVisualizer.prototype.generateRealisticWaveformData = function(width, type = 'master', offset = 0) {
        // Try to use real audio data first
        const realData = this.realAudioData.get(type);
        if (realData && realData.peaks) {
            return this.processRealWaveformData(realData, width, offset);
        }
        
        // Fallback to original simulated data
        return originalGenerateWaveformData.call(this, width, type, offset);
    };
    
    // Add method to process real waveform data
    window.WaveformVisualizer.prototype.processRealWaveformData = function(realData, targetWidth, offset = 0) {
        const peaks = realData.peaks;
        const originalWidth = peaks.length;
        const data = new Float32Array(targetWidth);
        
        // Calculate scaling factor
        const scaleFactor = originalWidth / targetWidth;
        
        for (let i = 0; i < targetWidth; i++) {
            // Map target pixel to source data with offset
            // Revised convention: positive = dub ahead → shift LEFT; negative = behind → shift RIGHT
            const offsetPixels = offset * (targetWidth / this.viewWindow);
            const sourceIndex = Math.floor((i + offsetPixels) * scaleFactor);
            
            if (sourceIndex >= 0 && sourceIndex < originalWidth) {
                data[i] = peaks[sourceIndex];
            } else {
                data[i] = 0; // Silence outside range
            }
        }
        
        return data;
    };
    
    // Add method to load real audio files
    window.WaveformVisualizer.prototype.loadAudioFile = async function(file, type) {
        if (!this.audioEngine.isAudioFile(file)) {
            throw new Error('Unsupported audio file format');
        }
        
        try {
            await this.audioEngine.loadAudioFile(file, type);
            return true;
        } catch (error) {
            console.error(`Failed to load ${type} audio file:`, error);
            throw error;
        }
    };
    
    // Add method to load by URL (served by backend)
    window.WaveformVisualizer.prototype.loadAudioUrl = async function(url, type) {
        try {
            await this.audioEngine.loadAudioUrl(url, type);
            return true;
        } catch (error) {
            console.error(`Failed to load ${type} audio URL:`, error);
            throw error;
        }
    };
    
    // Add method to check for real audio data
    window.WaveformVisualizer.prototype.hasRealAudioData = function(type) {
        return this.realAudioData.has(type) && this.realAudioData.get(type).peaks;
    };
    
    // Add method to get audio metadata
    window.WaveformVisualizer.prototype.getAudioMetadata = function(type) {
        const audioData = this.realAudioData.get(type);
        if (audioData) {
            return {
                duration: audioData.duration,
                sampleRate: audioData.sampleRate,
                width: audioData.width,
                hasRealData: true
            };
        }
        return { hasRealData: false };
    };
    
    // Add method to clear audio data
    window.WaveformVisualizer.prototype.clearAudioData = function() {
        this.realAudioData.clear();
        this.audioData.clear();
        if (this.audioEngine) {
            this.audioEngine.dispose();
            this.audioEngine = new CoreAudioEngine();
            this.setupAudioEngineCallbacks();
        }
    };

    // Add simple volume control wrapper
    window.WaveformVisualizer.prototype.setVolume = function(track, value) {
        if (this.audioEngine && typeof this.audioEngine.setVolume === 'function') {
            this.audioEngine.setVolume(track, value);
        }
    };

    // Master output volume
    window.WaveformVisualizer.prototype.setMasterOutputVolume = function(value) {
        if (this.audioEngine && typeof this.audioEngine.setMasterOutputVolume === 'function') {
            this.audioEngine.setMasterOutputVolume(value);
        }
    };

    // Balance control
    window.WaveformVisualizer.prototype.setBalance = function(value) {
        if (this.audioEngine && typeof this.audioEngine.setBalance === 'function') {
            this.audioEngine.setBalance(value);
        }
    };

    // Per-track pan
    window.WaveformVisualizer.prototype.setPan = function(track, value) {
        if (this.audioEngine && typeof this.audioEngine.setPan === 'function') {
            this.audioEngine.setPan(track, value);
        }
    };

    // Per-track mute
    window.WaveformVisualizer.prototype.setMute = function(track, muted) {
        if (this.audioEngine && typeof this.audioEngine.setMute === 'function') {
            this.audioEngine.setMute(track, muted);
        }
    };

    // Stop playback wrapper
    window.WaveformVisualizer.prototype.stopAudio = function() {
        if (this.audioEngine && typeof this.audioEngine.stopPlayback === 'function') {
            this.audioEngine.stopPlayback();
        }
    };
    
    // Override generateUnifiedTimeline to work with real audio data
    const originalGenerateUnifiedTimeline = window.WaveformVisualizer.prototype.generateUnifiedTimeline;
    window.WaveformVisualizer.prototype.generateUnifiedTimeline = async function(masterId, dubId, offsetSeconds, container, timelineData = null) {
        const canvas = container.querySelector(`#unified-timeline-${masterId}-${dubId}`);
        const ctx = canvas.getContext('2d');
        
        console.log(`Generating unified timeline for ${masterId}-${dubId} with offset ${offsetSeconds}s`);
        console.log(`Canvas found:`, !!canvas, `Context:`, !!ctx);
        console.log(`Canvas actual size:`, canvas.width, 'x', canvas.height);
        console.log(`Canvas style size:`, canvas.style.width, 'x', canvas.style.height);
        console.log(`Pixel ratio:`, this.pixelRatio);
        console.log(`Master real data:`, this.hasRealAudioData('master'));
        console.log(`Dub real data:`, this.hasRealAudioData('dub'));
        
        // Auto-expand to container width when available (max 4000px)
        try {
            const host = container.querySelector('.zoom-pan-container') || container;
            const hostWidth = host.clientWidth || host.offsetWidth || 0;
            const desired = Math.max(this.waveformWidth, Math.min(4000, Math.max(1200, hostWidth - 24)));
            if (desired && desired !== this.waveformWidth) {
                this.waveformWidth = desired;
                canvas.width = Math.floor(this.waveformWidth * this.pixelRatio);
            }
        } catch {}
        // Ensure CSS size is in CSS pixels to match overlay; use DPR for backing store
        canvas.style.width = `${this.waveformWidth}px`;
        canvas.style.height = `${(this.waveformHeight * 2.2)}px`;

        // Clear and apply DPR transform (no compounding)
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
        console.log(`Applied pixel ratio scaling:`, this.pixelRatio);
        
        // If real audio is loaded, set the view window to full duration for fit-to-view
        const masterMeta = this.getAudioMetadata('master');
        const dubMeta = this.getAudioMetadata('dub');
        const totalDuration = Math.max(masterMeta.duration || 0, dubMeta.duration || 0);
        const minWindow = Math.max(10, Math.abs(offsetSeconds || 0) * 2 + 2);
        if (totalDuration && Number.isFinite(totalDuration) && totalDuration > 0) {
            this.viewWindow = Math.min(totalDuration, Math.max(this.viewWindow, minWindow));
        } else {
            this.viewWindow = Math.max(this.viewWindow, minWindow);
        }

        // Generate waveform data - this will use real audio data when available
        const masterData = this.generateRealisticWaveformData(this.waveformWidth, 'master');
        const dubBeforeData = this.generateRealisticWaveformData(this.waveformWidth, 'dub', offsetSeconds);
        const dubAfterData = this.generateRealisticWaveformData(this.waveformWidth, 'dub', 0);
        
        console.log(`Generated data - Master:`, masterData?.length, `Dub Before:`, dubBeforeData?.length, `Dub After:`, dubAfterData?.length);
        
        // Store waveform data for zoom functionality
        this.audioData.set(`unified-timeline-${masterId}-${dubId}`, {
            master: masterData,
            dubBefore: dubBeforeData,
            dubAfter: dubAfterData,
            offsetSeconds: offsetSeconds,
            driftTimeline: Array.isArray(timelineData) ? timelineData : null
        });
        
        // Draw unified timeline with error handling
        try {
            console.log(`Drawing unified timeline - Master data range:`, Math.min(...masterData), Math.max(...masterData));
            console.log(`Drawing unified timeline - Dub data range:`, Math.min(...dubBeforeData), Math.max(...dubBeforeData));
            console.log(`Canvas dimensions:`, canvas.width, 'x', canvas.height);
            console.log(`Canvas context properties:`, {
                fillStyle: ctx.fillStyle,
                strokeStyle: ctx.strokeStyle,
                globalAlpha: ctx.globalAlpha
            });
            
            this.drawUnifiedTimeline(ctx, masterData, dubBeforeData, dubAfterData, offsetSeconds);
            
            
        } catch (error) {
            console.error('❌ Error drawing unified timeline:', error);
            // Draw a fallback indicator
            ctx.fillStyle = '#ff0000';
            ctx.fillRect(0, 0, 100, 20);
            ctx.fillStyle = '#ffffff';
            ctx.font = '12px Arial';
            ctx.fillText('Draw Error', 5, 15);
        }
        
        // Add time markers for unified view
        this.addTimeMarkers(container.querySelector('.unified-markers'), this.waveformWidth);
        // Add drift markers if timeline provided
        if (Array.isArray(timelineData) && timelineData.length) {
            this.addDriftMarkers(container, timelineData);
        } else {
            const dm = container.querySelector('.unified-drift-markers');
            if (dm) dm.innerHTML = '';
        }
        
        // Add timeline view toggle functionality
        this.addTimelineToggleHandlers(container, masterId, dubId);

        


        // Add compact player for direct playback (single stream)
        try {
            this._addCompactPlayer(container, masterId, dubId);
        } catch (e) {
            console.warn('Compact player setup failed:', e);
        }
    };

    // Internal: add a minimal HTML5 audio player to ensure something can play
    window.WaveformVisualizer.prototype._addCompactPlayer = function(container, masterId, dubId) {
        const unified = container.querySelector(`[data-waveform-id="unified-${masterId}-${dubId}"]`);
        if (!unified) return;
        // Avoid duplicates
        if (container.querySelector('.compact-player')) return;

        const playerWrap = document.createElement('div');
        playerWrap.className = 'compact-player';
        playerWrap.style.cssText = 'margin-top:8px; padding:6px 8px; background:#0e0e0e; border:1px solid #222; border-radius:6px; display:flex; align-items:center; gap:8px;';
        playerWrap.innerHTML = `
            <span style="font-size:12px;color:#bbb;">Mini Player</span>
            <button class="cp-btn" data-src="master" style="font-size:12px; padding:4px 8px;">Master</button>
            <button class="cp-btn" data-src="dub" style="font-size:12px; padding:4px 8px;">Dub</button>
            <audio class="cp-audio" controls preload="none" style="height:22px; flex:1;"></audio>
        `;
        const controlsHost = container.querySelector('.waveform-controls') || container;
        try { controlsHost.parentNode.insertBefore(playerWrap, controlsHost.nextSibling); }
        catch { container.appendChild(playerWrap); }
        try { window.showToast?.('info', 'Mini Player added (Master/Dub buttons)', 'Audio'); } catch {}

        const audioEl = playerWrap.querySelector('.cp-audio');
        const buttons = playerWrap.querySelectorAll('.cp-btn');
        audioEl.addEventListener('error', () => {
            try { window.showToast?.('error', `Mini Player media error — ${audioEl.currentSrc || 'no source'}`, 'Audio Load'); } catch {}
        });

        const resolveUrls = async () => {
            let mUrl = unified.dataset.masterUrl || null;
            let dUrl = unified.dataset.dubUrl || null;
            const mPath = unified.dataset.masterPath;
            const dPath = unified.dataset.dubPath;
            const enc = encodeURIComponent;
            if ((!mUrl || !dUrl) && mPath && dPath) {
                try {
                    const prep = await fetch('/api/v1/proxy/prepare', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ master: mPath, dub: dPath })
                    }).then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)));
                    if (prep && prep.success) {
                        mUrl = prep.master_url; dUrl = prep.dub_url;
                        unified.dataset.masterUrl = mUrl; unified.dataset.dubUrl = dUrl;
                    }
                } catch (e) {
                    // Fallback to raw endpoints
                    mUrl = mUrl || (mPath ? `/api/v1/files/raw?path=${enc(mPath)}` : null);
                    dUrl = dUrl || (dPath ? `/api/v1/files/raw?path=${enc(dPath)}` : null);
                }
            }
            // As final fallback, use raw if still missing
            if (!mUrl && mPath) mUrl = `/api/v1/files/raw?path=${enc(mPath)}`;
            if (!dUrl && dPath) dUrl = `/api/v1/files/raw?path=${enc(dPath)}`;
            return { mUrl, dUrl };
        };

        const setSource = async (which) => {
            const { mUrl, dUrl } = await resolveUrls();
            const url = which === 'master' ? mUrl : dUrl;
            if (!url) return;
            audioEl.src = url;
            try { await audioEl.load(); } catch (e) { try { window.showToast?.('error', `Mini Player load failed — ${url}`, 'Audio Load'); } catch {} }
        };

        buttons.forEach(btn => {
            btn.addEventListener('click', async () => {
                await setSource(btn.dataset.src);
                try { await audioEl.play(); } catch (e) { try { window.showToast?.('error', `Mini Player play prevented — user gesture or policy`, 'Audio'); } catch {} }
            });
        });
    };

    // Override playAudioComparison to show real vs simulated data info
    window.WaveformVisualizer.prototype.playAudioComparison = async function(masterId, dubId, offsetSeconds, forceAfter) {
        const masterMeta = this.getAudioMetadata('master');
        const dubMeta = this.getAudioMetadata('dub');

        // Determine if UI is showing After (corrected) or Before
        const unified = document.querySelector(`[data-waveform-id="unified-${masterId}-${dubId}"]`);
        const container = unified?.closest('.sync-waveform-container');
        let isAfter = !!container && container.querySelector('.comparison-overlay')?.style.display === 'block';
        if (typeof forceAfter === 'boolean') isAfter = forceAfter;

        // Try to unlock audio context immediately on user gesture
        try { await this.audioEngine?.audioContext?.resume?.(); } catch {}

        // First, attempt robust direct-media playback using stored URLs (bypasses engine)
        try {
            const mUrl0 = unified?.dataset?.masterUrl || null;
            const dUrl0 = unified?.dataset?.dubUrl || null;
            const rUrl0 = unified?.dataset?.repairedUrl || null;
            const useDub0 = (typeof forceAfter === 'boolean' ? forceAfter : isAfter) && (rUrl0 || unified?.dataset?.repairedPath)
                ? (rUrl0 || `/api/v1/files/raw?path=${encodeURIComponent(unified.dataset.repairedPath)}`)
                : dUrl0;
            if (mUrl0 && useDub0) {
                const played = await this._fallbackPlayElements(unified, mUrl0, useDub0, offsetSeconds || 0, (typeof forceAfter === 'boolean' ? forceAfter : isAfter));
                if (played) return;
            }
        } catch {}

        // If engine has decoded data, use it; otherwise prefer a robust element-based fallback
        if (this.audioEngine && masterMeta.hasRealData && dubMeta.hasRealData && this.audioEngine.masterBuffer && this.audioEngine.dubBuffer) {
            try { window.showToast?.('info', 'Playing comparison…', 'Audio'); } catch {}
            this.audioEngine.playComparison(offsetSeconds || 0, isAfter);
            return;
        }

        // Attempt auto-load from job DOM data if buffers missing
        if (this.audioEngine && unified) {
            const mPath = unified.dataset.masterPath;
            const dPath = unified.dataset.dubPath;
            const enc = encodeURIComponent;
            // Prefer prepared proxy URLs if present
            let mUrl = unified.dataset.masterUrl || null;
            let dUrl = unified.dataset.dubUrl || null;
            const rUrlExisting = unified.dataset.repairedUrl || null;
            try {
                if ((!mUrl || !dUrl) && mPath && dPath) {
                    // Try to create proxies on-demand
                    const prep = await fetch('/api/v1/proxy/prepare', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ master: mPath, dub: dPath })
                    }).then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)));
                    if (prep && prep.success) {
                        mUrl = prep.master_url; dUrl = prep.dub_url;
                        unified.dataset.masterUrl = mUrl; unified.dataset.dubUrl = dUrl;
                    }
                }
                // If an item-level repaired file was provided on the dataset, ensure URL
                if (!rUrlExisting && unified.dataset.repairedPath) {
                    try {
                        const p = await fetch('/api/v1/proxy/prepare', {
                            method: 'POST', headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ master: mPath, dub: unified.dataset.repairedPath })
                        }).then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)));
                        if (p && p.success && p.dub_url) {
                            unified.dataset.repairedUrl = p.dub_url;
                        }
                    } catch {}
                }
            } catch (e) {
                console.warn('Proxy prepare in play failed, falling back to raw:', e);
            }
            // Fall back to raw endpoints
            mUrl = mUrl || (mPath ? `/api/v1/files/raw?path=${enc(mPath)}` : null);
            dUrl = dUrl || (dPath ? `/api/v1/files/raw?path=${enc(dPath)}` : null);
            const useDubUrl = (isAfter && (unified.dataset.repairedUrl || unified.dataset.repairedPath))
                ? (unified.dataset.repairedUrl || `/api/v1/files/raw?path=${enc(unified.dataset.repairedPath)}`)
                : dUrl;
            if (mUrl && useDubUrl) {
                // Robust direct element playback (no pan), independent of WebAudio graphs
                try { await this._fallbackPlayElements(unified, mUrl, useDubUrl, offsetSeconds || 0, isAfter); return; } catch {}
                // If fallback fails, try engine load
                try {
                    await Promise.all([
                        this.loadAudioUrl(mUrl, 'master'),
                        this.loadAudioUrl(useDubUrl, 'dub')
                    ]);
                    try { await this.audioEngine?.audioContext?.resume?.(); } catch {}
                    try { window.showToast?.('info', 'Playing comparison…', 'Audio'); } catch {}
                    this.audioEngine.playComparison(offsetSeconds || 0, isAfter);
                    return;
                } catch (e) {
                    console.warn('Auto-load from URLs failed:', e);
                    try { window.showToast?.('error', `Auto-load failed: ${e.message}`, 'Audio'); } catch {}
                }
            }
        }

        const note = `[Simulated] ${isAfter ? 'Corrected' : 'Original'} comparison: offset=${offsetSeconds || 0}s — load audio files to enable playback`;
        console.log(note);
        try { window.showToast?.('warning', 'Audio not loaded — click Mini Player Master/Dub to test sources', 'Audio'); } catch {}
    };

    // Simple direct playback using HTML media elements (master/dub), with scheduling
    window.WaveformVisualizer.prototype._fallbackPlayElements = async function(unifiedEl, masterUrl, dubUrl, offsetSeconds, corrected) {
        const ensureEl = (key, url) => {
            let el = unifiedEl.querySelector(`audio[data-role="${key}"], video[data-role="${key}"]`);
            if (!el) {
                const isVideo = /\.(mp4|mov|mkv|avi)(\?|$)/i.test(url);
                el = document.createElement(isVideo ? 'video' : 'audio');
                el.setAttribute('data-role', key);
                el.preload = 'auto';
                el.style.display = 'none';
                el.crossOrigin = 'use-credentials';
                unifiedEl.appendChild(el);
            }
            if (el.src !== url) el.src = url;
            return el;
        };
        const m = ensureEl('master-el', masterUrl);
        const d = ensureEl('dub-el', dubUrl);
        // Wait metadata
        const waitMeta = (el) => new Promise((res) => {
            if (el.readyState >= 1) return res();
            el.addEventListener('loadedmetadata', () => res(), { once: true });
        });
        await Promise.all([waitMeta(m), waitMeta(d)]);
        // Set volumes using UI-engine values if available
        try {
            const out = this.audioEngine?.masterOutputValue ?? 1.0;
            const bal = this.audioEngine?.balanceValue ?? 0.0;
            const mBase = this.audioEngine?.masterGainValue ?? 0.8;
            const dBase = this.audioEngine?.dubGainValue ?? 0.8;
            const mScale = (this.audioEngine?.muteMaster ? 0 : 1) * (1 - Math.max(0, bal)) * out * mBase;
            const dScale = (this.audioEngine?.muteDub ? 0 : 1) * (1 - Math.max(0, -bal)) * out * dBase;
            m.volume = Math.max(0, Math.min(1, mScale));
            d.volume = Math.max(0, Math.min(1, dScale));
        } catch {}
        // Position timelines
        const startAt = 0;
        m.currentTime = startAt;
        d.currentTime = startAt;
        if (!corrected) {
            if (offsetSeconds > 0) {
                // dub delayed
                await m.play().catch(() => {});
                setTimeout(() => { d.play().catch(() => {}); }, offsetSeconds * 1000);
            } else if (offsetSeconds < 0) {
                d.currentTime = Math.min(Math.max(0, startAt + (-offsetSeconds)), Math.max(0.01, (d.duration || 1) - 0.01));
                await m.play().catch(() => {});
                await d.play().catch(() => {});
            } else {
                await m.play().catch(() => {});
                await d.play().catch(() => {});
            }
        } else {
            if (offsetSeconds > 0) {
                m.currentTime = Math.min(Math.max(0, startAt + offsetSeconds), Math.max(0.01, (m.duration || 1) - 0.01));
                d.currentTime = startAt;
            } else if (offsetSeconds < 0) {
                d.currentTime = Math.min(Math.max(0, startAt + (-offsetSeconds)), Math.max(0.01, (d.duration || 1) - 0.01));
                m.currentTime = startAt;
            }
            await m.play().catch(() => {});
            await d.play().catch(() => {});
        }
        try { window.showToast?.('success', `Playing via direct ${/\.\w+$/.exec(masterUrl)?.[0] || 'media'}`, 'Audio'); } catch {}
        return true;
    };

    // Override handleWaveformAction to ensure play-comparison triggers real playback
    const originalHandle = window.WaveformVisualizer.prototype.handleWaveformAction;
    window.WaveformVisualizer.prototype.handleWaveformAction = function(action, container, masterId, dubId, offsetSeconds) {
        if (action === 'play-comparison') {
            // Ensure offsetSeconds available
            if (!offsetSeconds) {
                const waveformKey = this.getWaveformKey(container);
                const waveformData = this.audioData.get(waveformKey);
                if (waveformData) offsetSeconds = waveformData.offsetSeconds;
            }
            // Use the overridden playAudioComparison (which drives CoreAudioEngine)
            this.playAudioComparison(masterId, dubId, offsetSeconds || 0);
            return;
        }
        // Delegate other actions to original
        return originalHandle.call(this, action, container, masterId, dubId, offsetSeconds);
    };
}

console.log('Enhanced waveform with real audio support loaded');
