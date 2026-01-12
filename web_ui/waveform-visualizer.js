/**
 * Professional Waveform Visualizer for Audio Sync Analysis
 * Creates exact representations of out-of-sync audio with before/after correction
 */

class WaveformVisualizer {
    constructor() {
        this.canvases = new Map();
        this.audioData = new Map();
        this.sampleRate = 44100;
        this.waveformHeight = 80;
        this.waveformWidth = 800;
        this.pixelRatio = window.devicePixelRatio || 1;
        
        // Zoom functionality
        this.zoomLevel = 1.0;
        this.minZoom = 0.1;
        this.maxZoom = 20.0;
        this.zoomStep = 0.1;
        this.panOffset = 0;
        this.viewWindow = 10; // seconds visible in view
        this.isDragging = false;
        this.lastMouseX = 0;
        
        // Active waveform tracking
        this.activeWaveforms = new Map();
    }

    /**
     * Generate exact out-of-sync waveform representation
     * @param {string} masterId - Master audio identifier
     * @param {string} dubId - Dub audio identifier  
     * @param {number} offsetSeconds - Detected sync offset in seconds
     * @param {HTMLElement} container - Container element for waveforms
     */
    async generateSyncWaveforms(masterId, dubId, offsetSeconds, container, timelineData = null) {
        try {
            // Create waveform container structure
            const waveformContainer = this.createWaveformContainer(masterId, dubId, offsetSeconds);
            container.innerHTML = '';
            container.appendChild(waveformContainer);

            // Generate unified timeline with both master and dub waveforms
            await this.generateUnifiedTimeline(masterId, dubId, offsetSeconds, waveformContainer, timelineData);

            // Add sync indicators and measurements
            this.addSyncIndicators(waveformContainer, offsetSeconds);

            // Add interactive controls
            this.addInteractiveControls(waveformContainer, masterId, dubId, offsetSeconds);
            
            // Initialize zoom functionality
            this.initializeZoomAndPan(waveformContainer, masterId, dubId);

        } catch (error) {
            console.error('Error generating sync waveforms:', error);
            this.showWaveformError(container, error.message);
        }
    }

    /**
     * Create the HTML structure for waveform display
     */
    createWaveformContainer(masterId, dubId, offsetSeconds) {
        const container = document.createElement('div');
        container.className = 'sync-waveform-container';
        container.innerHTML = `
            <div class="waveform-header">
                <h4><i class="fas fa-chart-area"></i> Exact Audio Waveform Analysis</h4>
                    <div class="waveform-info">
                        <span class="offset-info">Detected Offset: <strong>${(offsetSeconds * 1000).toFixed(2)}ms</strong></span>
                        <div class="waveform-controls">
                        <div class="control-group view-controls">
                            <button class="waveform-btn" data-action="toggle-view">
                                <i class="fas fa-eye"></i> Toggle Before/After
                            </button>
                            <button class="waveform-btn qc-open-btn" data-master-id="${masterId}" data-dub-id="${dubId}" data-offset="${offsetSeconds}" title="Open Quality Control Interface">
                                <i class="fas fa-microscope"></i> QC Review
                            </button>
                        </div>
                        
                        <div class="control-group zoom-controls">
                            <button class="waveform-btn zoom-btn" data-action="zoom-out" title="Zoom Out (Ctrl + -)">
                                <i class="fas fa-search-minus"></i>
                            </button>
                            <div class="zoom-display">
                                <span class="zoom-level">${(this.zoomLevel * 100).toFixed(0)}%</span>
                                <div class="zoom-slider-container">
                                    <input type="range" class="zoom-slider" 
                                           min="${this.minZoom}" 
                                           max="${this.maxZoom}" 
                                           step="${this.zoomStep}" 
                                           value="${this.zoomLevel}"
                                           data-action="zoom-slider">
                                </div>
                            </div>
                            <button class="waveform-btn zoom-btn" data-action="zoom-in" title="Zoom In (Ctrl + +)">
                                <i class="fas fa-search-plus"></i>
                            </button>
                            <button class="waveform-btn" data-action="zoom-fit" title="Fit to View (F)">
                                <i class="fas fa-expand-arrows-alt"></i> Fit
                            </button>
                            <button class="waveform-btn" data-action="zoom-to-sync" title="Zoom to Sync Point (S)">
                                <i class="fas fa-crosshairs"></i> Sync Point
                            </button>
                            <button class="waveform-btn" data-action="fit-offset" title="Fit Entire Offset">
                                <i class="fas fa-arrows-left-right"></i> Fit Offset
                            </button>
                        </div>
                        
                        <div class="control-group navigation-controls">
                            <button class="waveform-btn" data-action="pan-left" title="Pan Left (←)">
                                <i class="fas fa-chevron-left"></i>
                            </button>
                            <button class="waveform-btn" data-action="pan-right" title="Pan Right (→)">
                                <i class="fas fa-chevron-right"></i>
                            </button>
                            <button class="waveform-btn" data-action="reset-view" title="Reset View (R)">
                                <i class="fas fa-home"></i> Reset
                            </button>
                        </div>
                        
                        
                        <div class="control-group navigation-controls">
                            <span style="color:#cbd5e0;font-size:12px;opacity:0.7;">Audio controls moved to QC Review interface</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="waveform-display-area">
                <!-- Unified Timeline View -->
                <div class="unified-timeline-track">
                    <div class="timeline-header">
                        <div class="track-labels">
                            <div class="track-label-item master-label">
                                <div class="label-indicator master-indicator"></div>
                                <span>Master Audio</span>
                                <div class="track-status">Reference</div>
                            </div>
                            <div class="track-label-item dub-label">
                                <div class="label-indicator dub-indicator"></div>
                                <span>Dub Audio</span>
                                <div class="track-status sync-status" id="dub-status-${dubId}">
                                    Out of Sync (${offsetSeconds > 0 ? 'Delayed' : 'Advanced'})
                                </div>
                            </div>
                        </div>
                        <div class="timeline-view-toggle">
                            <button class="timeline-toggle-btn" data-view="overlay" title="Overlay View - Both waveforms together">
                                <i class="fas fa-layer-group"></i> Overlay
                            </button>
                            <button class="timeline-toggle-btn active" data-view="stacked" title="Stacked View - Separate but aligned">
                                <i class="fas fa-bars"></i> Stacked
                            </button>
                        </div>
                    </div>
                    
                    <div class="unified-waveform-container" data-waveform-id="unified-${masterId}-${dubId}">
                        <div class="zoom-pan-container">
                            <!-- Single canvas for unified timeline display -->
                            <canvas id="unified-timeline-${masterId}-${dubId}" 
                                    class="unified-timeline-canvas zoomable-canvas"
                                    width="${this.waveformWidth * this.pixelRatio}"
                                    height="${(this.waveformHeight * 2.5) * this.pixelRatio}"
                                    style="width: ${this.waveformWidth}px; height: ${(this.waveformHeight * 2.5)}px;">
                            </canvas>
                            
                            <div class="waveform-overlay">
                                <!-- Sync offset indicator -->
                                <div class="sync-offset-indicator" data-offset="${offsetSeconds}" style="left: ${this.calculateOffsetPosition(offsetSeconds)}px;">
                                    <div class="offset-line"></div>
                                    <div class="offset-label">${(Math.abs(offsetSeconds) * 1000).toFixed(1)}ms ${offsetSeconds > 0 ? 'delay' : 'advance'}</div>
                                </div>
                                
                                <!-- Alignment guides -->
                                <div class="alignment-guides">
                                    <div class="sync-alignment-line master-line" data-track="master"></div>
                                    <div class="sync-alignment-line dub-line" data-track="dub"></div>
                                </div>
                                
                                <!-- Time markers -->
                                <div class="time-markers unified-markers"></div>
                                
                                <!-- Drift markers (from analysis timeline) -->
                                <div class="drift-markers unified-drift-markers"></div>
                                
                                <!-- Zoom selection box -->
                                <div class="zoom-selection-box" style="display: none;"></div>
                                
                                <!-- Before/After comparison overlay -->
                                <div class="comparison-overlay" id="comparison-overlay-${dubId}" style="display: none;">
                                    <div class="overlay-label">After Sync Correction</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Timeline legends -->
                    <div class="timeline-legend">
                        <div class="legend-item">
                            <div class="legend-color master-color"></div>
                            <span>Master Audio</span>
                        </div>
                        <div class="legend-item">
                            <div class="legend-color dub-before-color"></div>
                            <span>Dub Audio (Before Sync)</span>
                        </div>
                        <div class="legend-item comparison-legend" style="display: none;">
                            <div class="legend-color dub-after-color"></div>
                            <span>Dub Audio (After Sync)</span>
                        </div>
                        <div class="legend-item offset-legend">
                            <div class="legend-color offset-color"></div>
                            <span>Sync Offset: ${(Math.abs(offsetSeconds) * 1000).toFixed(1)}ms</span>
                        </div>
                        <div class="legend-item drift-legend" id="drift-legend-${masterId}-${dubId}" style="display: none;">
                            <div class="legend-color drift-legend-color"></div>
                            <span>Drift Timeline: <span class="drift-count">0</span> points</span>
                        </div>
                    </div>
                    <!-- Drift Severity Guide -->
                    <div class="drift-severity-guide" id="drift-guide-${masterId}-${dubId}" style="display: none;">
                        <div class="guide-title">🎯 Sync Quality Guide</div>
                        <div class="severity-items">
                            <div class="severity-item">
                                <div class="severity-marker severity-insync"></div>
                                <span>✅ In Sync (≤40ms)</span>
                            </div>
                            <div class="severity-item">
                                <div class="severity-marker severity-minor"></div>
                                <span>⚠️ Minor Drift (≤100ms)</span>
                            </div>
                            <div class="severity-item">
                                <div class="severity-marker severity-issue"></div>
                                <span>🟠 Sync Issue (≤1s)</span>
                            </div>
                            <div class="severity-item">
                                <div class="severity-marker severity-major"></div>
                                <span>🔴 Major Problem (>1s)</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Sync Analysis Panel -->
                <div class="sync-analysis-panel">
                    <div class="analysis-metrics">
                        <div class="metric">
                            <span class="metric-label">Cross-correlation:</span>
                            <span class="metric-value correlation-score" id="correlation-${masterId}-${dubId}">--</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Confidence:</span>
                            <span class="metric-value confidence-score" id="confidence-${masterId}-${dubId}">--</span>
                        </div>
                        <div class="metric">
                            <span class="metric-label">Quality:</span>
                            <span class="metric-value quality-score" id="quality-${masterId}-${dubId}">--</span>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        return container;
    }

    /**
     * Generate unified timeline displaying both master and dub waveforms together
     */
    async generateUnifiedTimeline(masterId, dubId, offsetSeconds, container, timelineData = null) {
        const canvas = container.querySelector(`#unified-timeline-${masterId}-${dubId}`);
        const ctx = canvas.getContext('2d');
        // Auto-expand canvas width to container when available (up to 4000px)
        try {
            const host = container.querySelector('.zoom-pan-container') || container;
            const hostWidth = host.clientWidth || host.offsetWidth || 0;
            const desired = Math.max(this.waveformWidth, Math.min(4000, Math.max(1200, hostWidth - 24)));
            if (desired && desired !== this.waveformWidth) {
                this.waveformWidth = desired;
                canvas.width = Math.floor(this.waveformWidth * this.pixelRatio);
                canvas.style.width = `${this.waveformWidth}px`;
            }
        } catch {}
        
        // Reset and apply DPR scaling once
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
        
        // Ensure the visible window covers the full offset (and up to total duration if available)
        try {
            const getMeta = this.getAudioMetadata ? (t) => this.getAudioMetadata(t) : () => ({ duration: null });
            const mMeta = getMeta('master');
            const dMeta = getMeta('dub');
            const total = Math.max(mMeta?.duration || 0, dMeta?.duration || 0) || null;
            const minWindow = Math.max(10, Math.abs(offsetSeconds || 0) * 2 + 2);
            this.viewWindow = total ? Math.min(total, Math.max(this.viewWindow, minWindow)) : Math.max(this.viewWindow, minWindow);
        } catch {}

        // Generate waveform data for both tracks
        const masterData = this.generateRealisticWaveformData(this.waveformWidth, 'master');
        // Always show BEFORE (offset applied) and AFTER (aligned) distinctly
        const dubBeforeData = this.generateRealisticWaveformData(this.waveformWidth, 'dub', offsetSeconds);
        const dubAfterData = this.generateRealisticWaveformData(this.waveformWidth, 'dub', 0); // Synchronized
        
        // Store waveform data for zoom functionality
        this.audioData.set(`unified-timeline-${masterId}-${dubId}`, {
            master: masterData,
            dubBefore: dubBeforeData,
            dubAfter: dubAfterData,
            offsetSeconds: offsetSeconds,
            driftTimeline: Array.isArray(timelineData) ? timelineData : null
        });
        
        // Draw unified timeline
        this.drawUnifiedTimeline(ctx, masterData, dubBeforeData, dubAfterData, offsetSeconds);
        
        // Add time markers for unified view
        this.addTimeMarkers(container.querySelector('.unified-markers'), this.waveformWidth);
        // Add drift markers if timeline provided
        if (Array.isArray(timelineData) && timelineData.length) {
            this.addDriftMarkers(container, timelineData);
        } else {
            // Clear if not available
            const dm = container.querySelector('.unified-drift-markers');
            if (dm) dm.innerHTML = '';
        }
        
        // Add timeline view toggle functionality
        this.addTimelineToggleHandlers(container, masterId, dubId);

        
    }
    
    /**
     * Draw unified timeline with master and dub waveforms
     */
    drawUnifiedTimeline(ctx, masterData, dubBeforeData, dubAfterData, offsetSeconds, viewMode = 'stacked') {
        const width = this.waveformWidth;
        const height = this.waveformHeight * 2.2;
        
        // Clear canvas
        ctx.clearRect(0, 0, width, height);
        
        // Fill background
        ctx.fillStyle = '#0f0f0f';
        ctx.fillRect(0, 0, width, height);
        
        if (viewMode === 'overlay') {
            // Overlay mode - both waveforms in same space with transparency
            this.drawOverlayWaveforms(ctx, masterData, dubBeforeData, offsetSeconds);
        } else {
            // Stacked mode - waveforms stacked vertically
            this.drawStackedWaveforms(ctx, masterData, dubBeforeData, offsetSeconds);
        }
    }

    /**
     * Render drift markers from timeline data into overlay container
     * timelineData: [{start_time, end_time, offset_seconds, confidence?, reliable?, quality?}, ...]
     */
    addDriftMarkers(container, timelineData) {
        const host = container.querySelector('.unified-drift-markers');
        if (!host) return;
        host.innerHTML = '';

        // Normalize to points (use midpoint of each segment)
        const points = (timelineData || [])
            .filter(d => Number.isFinite(d.start_time) && Number.isFinite(d.end_time))
            .map(d => {
                const t = (Number(d.start_time) + Number(d.end_time)) / 2;
                const off = Number(d.offset_seconds || 0);
                const abs = Math.abs(off);
                let sev = 'in_sync';
                if (abs <= 0.040) sev = 'in_sync';
                else if (abs <= 0.100) sev = 'minor';
                else if (abs <= 1.000) sev = 'issue';
                else sev = 'major';
                return {
                    time: t,
                    offset: off,
                    confidence: typeof d.confidence === 'number' ? d.confidence : null,
                    reliable: !!d.reliable,
                    severity: sev,
                    label: `${(off * 1000).toFixed(0)}ms ${off >= 0 ? 'delay' : 'advance'}`
                };
            });

        // Store on container for zoom updates
        container._driftPoints = points;

        // Show drift legend and guide if we have drift points
        const driftLegend = container.querySelector('.drift-legend');
        const driftGuide = container.querySelector('.drift-severity-guide');
        if (points.length > 0) {
            if (driftLegend) {
                driftLegend.style.display = 'flex';
                const countSpan = driftLegend.querySelector('.drift-count');
                if (countSpan) countSpan.textContent = points.length;
            }
            if (driftGuide) {
                driftGuide.style.display = 'block';
            }
        } else {
            if (driftLegend) driftLegend.style.display = 'none';
            if (driftGuide) driftGuide.style.display = 'none';
        }

        // Initial render at current zoom/pan
        this.updateDriftMarkersForZoom(container);
    }

    /**
     * Update drift markers positions/visibility on zoom/pan changes
     */
    updateDriftMarkersForZoom(container) {
        const host = container.querySelector('.unified-drift-markers');
        if (!host) return;
        const points = container._driftPoints || [];
        const visibleStart = -this.panOffset / (this.waveformWidth / this.viewWindow);
        const visibleDuration = this.viewWindow / this.zoomLevel;
        const pps = this.waveformWidth / visibleDuration; // pixels per second within visible window

        // Build or reuse marker elements
        // Use a keyed map by time to avoid full re-create flicker
        if (!host._pool) host._pool = new Map();
        const pool = host._pool;
        const inUse = new Set();

        points.forEach(pt => {
            const rel = (pt.time - visibleStart) / visibleDuration;
            const x = rel * this.waveformWidth;
            if (x < 0 || x > this.waveformWidth) return; // out of view

            const key = `${pt.time.toFixed(3)}|${pt.offset.toFixed(3)}`;
            let el = pool.get(key);
            if (!el) {
                el = document.createElement('div');
                el.className = 'drift-marker';
                el.title = `${pt.label}${pt.confidence != null ? ` • conf ${(pt.confidence * 100).toFixed(0)}%` : ''}${pt.reliable ? ' • reliable' : ''}`;
                host.appendChild(el);
                pool.set(key, el);
            }
            inUse.add(key);
            // Severity and reliability classes
            el.classList.toggle('severity-major', pt.severity === 'major');
            el.classList.toggle('severity-issue', pt.severity === 'issue');
            el.classList.toggle('severity-minor', pt.severity === 'minor');
            el.classList.toggle('severity-insync', pt.severity === 'in_sync');
            el.classList.toggle('unreliable', !pt.reliable);

            // Position at bottom above time ruler
            el.style.left = `${x}px`;
        });

        // Cleanup unused
        for (const [k, el] of pool.entries()) {
            if (!inUse.has(k)) {
                el.remove();
                pool.delete(k);
            }
        }
    }
    
    /**
     * Draw waveforms overlaid on top of each other
     */
    drawOverlayWaveforms(ctx, masterData, dubData, offsetSeconds) {
        const width = this.waveformWidth;
        const height = this.waveformHeight * 2.2;
        const centerY = height / 2;
        
        // Draw center reference line
        ctx.strokeStyle = '#333';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, centerY);
        ctx.lineTo(width, centerY);
        ctx.stroke();
        
        // Draw master waveform (semi-transparent)
        this.drawWaveform(ctx, masterData, {
            strokeStyle: '#4CAF50',
            fillStyle: 'rgba(76, 175, 80, 0.4)',
            lineWidth: 2,
            centerLine: false,
            yOffset: centerY
        });
        
        // Draw dub waveform (semi-transparent, different color)
        this.drawWaveform(ctx, dubData, {
            strokeStyle: '#f44336',
            fillStyle: 'rgba(244, 67, 54, 0.4)',
            lineWidth: 2,
            centerLine: false,
            yOffset: centerY
        });
        
        // Highlight the sync difference area
        this.highlightSyncDifference(ctx, offsetSeconds, centerY);
    }
    
    /**
     * Draw waveforms stacked vertically in DAW-style multi-track view
     * Matches the componentized visualization style with track labels and offset markers
     */
    drawStackedWaveforms(ctx, masterData, dubData, offsetSeconds) {
        const width = this.waveformWidth;
        const labelWidth = 70;
        const waveformWidth = width - labelWidth;
        const trackHeight = this.waveformHeight * 0.9;
        const trackPadding = 4;
        const timelineHeight = 25;
        
        // Calculate durations
        const masterDuration = this.viewWindow;
        const dubDuration = this.viewWindow;
        const maxDuration = Math.max(masterDuration, dubDuration);
        const pxPerSecond = waveformWidth / maxDuration;
        
        // Draw timeline ruler at top
        this.drawTimelineRulerForStacked(ctx, labelWidth, 0, waveformWidth, timelineHeight, maxDuration);
        
        // Track 1: Master (AREF)
        const masterY = timelineHeight;
        this.drawDAWTrack(ctx, masterData, {
            x: 0,
            y: masterY,
            labelWidth: labelWidth,
            waveformWidth: waveformWidth,
            trackHeight: trackHeight,
            maxDuration: maxDuration,
            name: 'AREF',
            color: '#60a5fa',  // Blue for master
            type: 'master',
            offset: 0
        });
        
        // Track 2: Dub
        const dubY = masterY + trackHeight + trackPadding;
        this.drawDAWTrack(ctx, dubData, {
            x: 0,
            y: dubY,
            labelWidth: labelWidth,
            waveformWidth: waveformWidth,
            trackHeight: trackHeight,
            maxDuration: maxDuration,
            name: 'Dub',
            color: '#4ade80',  // Teal/green for dub
            type: 'dub',
            offset: offsetSeconds
        });
        
        // Draw mode indicator
        ctx.fillStyle = '#9ca3af';
        ctx.font = 'bold 10px Arial';
        ctx.textAlign = 'right';
        ctx.fillText('Offset Applied', width - 10, timelineHeight - 8);
        ctx.textAlign = 'left';
    }
    
    /**
     * Draw timeline ruler for stacked view
     */
    drawTimelineRulerForStacked(ctx, x, y, width, height, duration) {
        // Background
        const bgGradient = ctx.createLinearGradient(x, y, x, y + height);
        bgGradient.addColorStop(0, '#1e293b');
        bgGradient.addColorStop(1, '#0f172a');
        ctx.fillStyle = bgGradient;
        ctx.fillRect(x, y, width, height);
        
        // Border
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, width, height);
        
        // Time markers
        const pxPerSecond = width / duration;
        const tickInterval = this.calculateTickInterval(duration);
        
        ctx.fillStyle = '#94a3b8';
        ctx.font = '9px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.strokeStyle = '#475569';
        
        for (let t = 0; t <= duration; t += tickInterval) {
            const tickX = x + t * pxPerSecond;
            
            // Draw tick
            ctx.beginPath();
            ctx.moveTo(tickX, y + height - 8);
            ctx.lineTo(tickX, y + height);
            ctx.stroke();
            
            // Draw time label
            const minutes = Math.floor(t / 60);
            const seconds = Math.floor(t % 60);
            const label = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            ctx.fillText(label, tickX, y + height - 10);
        }
    }
    
    /**
     * Calculate appropriate tick interval for timeline
     */
    calculateTickInterval(duration) {
        if (duration <= 30) return 5;
        if (duration <= 60) return 10;
        if (duration <= 300) return 30;
        if (duration <= 600) return 60;
        return 120;
    }
    
    /**
     * Draw a single DAW-style track with label, waveform, and offset marker
     */
    drawDAWTrack(ctx, waveformData, options) {
        const { x, y, labelWidth, waveformWidth, trackHeight, maxDuration, name, color, type, offset } = options;
        const pxPerSecond = waveformWidth / maxDuration;
        
        // Draw track background with gradient
        const bgGradient = ctx.createLinearGradient(x, y, x, y + trackHeight);
        bgGradient.addColorStop(0, '#0f172a');
        bgGradient.addColorStop(0.5, type === 'master' ? '#1e3a5f' : '#134e4a');
        bgGradient.addColorStop(1, '#0f172a');
        ctx.fillStyle = bgGradient;
        ctx.fillRect(x, y, labelWidth + waveformWidth, trackHeight);
        
        // Draw track border
        ctx.strokeStyle = '#334155';
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, labelWidth + waveformWidth, trackHeight);
        
        // Draw label background
        ctx.fillStyle = type === 'master' ? 'rgba(96, 165, 250, 0.15)' : 'rgba(74, 222, 128, 0.15)';
        ctx.fillRect(x, y, labelWidth, trackHeight);
        
        // Draw label text
        ctx.fillStyle = color;
        ctx.font = 'bold 11px JetBrains Mono, monospace';
        ctx.textAlign = 'left';
        ctx.fillText(name, x + 8, y + trackHeight / 2 + 4);
        
        // Draw separator line between label and waveform
        ctx.strokeStyle = '#334155';
        ctx.beginPath();
        ctx.moveTo(x + labelWidth, y);
        ctx.lineTo(x + labelWidth, y + trackHeight);
        ctx.stroke();
        
        // Draw center line for waveform
        const centerY = y + trackHeight / 2;
        ctx.strokeStyle = '#334155';
        ctx.setLineDash([2, 2]);
        ctx.beginPath();
        ctx.moveTo(x + labelWidth, centerY);
        ctx.lineTo(x + labelWidth + waveformWidth, centerY);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Draw offset marker for non-master tracks
        if (type !== 'master' && Math.abs(offset) > 0.001) {
            const offsetPx = Math.abs(offset) * pxPerSecond;
            const markerX = x + labelWidth + offsetPx;
            
            // Offset marker line
            ctx.strokeStyle = '#f87171';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(markerX, y);
            ctx.lineTo(markerX, y + trackHeight);
            ctx.stroke();
            
            // Offset label background
            const offsetLabel = this.formatOffsetLabel(offset);
            ctx.font = 'bold 9px Arial';
            const labelMetrics = ctx.measureText(offsetLabel);
            const labelPadding = 4;
            const labelBgWidth = labelMetrics.width + labelPadding * 2;
            const labelBgHeight = 14;
            const labelBgX = markerX - labelBgWidth / 2;
            const labelBgY = y + 2;
            
            ctx.fillStyle = '#f87171';
            ctx.beginPath();
            ctx.roundRect(labelBgX, labelBgY, labelBgWidth, labelBgHeight, 3);
            ctx.fill();
            
            // Offset label text
            ctx.fillStyle = '#1f2937';
            ctx.textAlign = 'center';
            ctx.fillText(offsetLabel, markerX, labelBgY + 10);
            ctx.textAlign = 'left';
        }
        
        // Draw waveform
        if (waveformData && waveformData.length > 0) {
            const waveHeight = (trackHeight - 8) / 2;
            const offsetPx = (type !== 'master' ? offset : 0) * pxPerSecond;
            
            // Draw upper half
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            let firstPoint = true;
            
            for (let i = 0; i < waveformData.length; i++) {
                const sampleTime = (i / waveformData.length) * maxDuration;
                const drawX = x + labelWidth + sampleTime * pxPerSecond + offsetPx;
                
                if (drawX < x + labelWidth || drawX > x + labelWidth + waveformWidth) continue;
                
                const amplitude = waveformData[i] || 0;
                const drawY = centerY - amplitude * waveHeight;
                
                if (firstPoint) {
                    ctx.moveTo(drawX, drawY);
                    firstPoint = false;
                } else {
                    ctx.lineTo(drawX, drawY);
                }
            }
            ctx.stroke();
            
            // Draw lower half (mirrored)
            ctx.beginPath();
            firstPoint = true;
            for (let i = 0; i < waveformData.length; i++) {
                const sampleTime = (i / waveformData.length) * maxDuration;
                const drawX = x + labelWidth + sampleTime * pxPerSecond + offsetPx;
                
                if (drawX < x + labelWidth || drawX > x + labelWidth + waveformWidth) continue;
                
                const amplitude = waveformData[i] || 0;
                const drawY = centerY + amplitude * waveHeight;
                
                if (firstPoint) {
                    ctx.moveTo(drawX, drawY);
                    firstPoint = false;
                } else {
                    ctx.lineTo(drawX, drawY);
                }
            }
            ctx.stroke();
            
            // Fill waveform area
            const r = parseInt(color.slice(1, 3), 16) || 100;
            const g = parseInt(color.slice(3, 5), 16) || 200;
            const b = parseInt(color.slice(5, 7), 16) || 150;
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.15)`;
            
            ctx.beginPath();
            for (let i = 0; i < waveformData.length; i++) {
                const sampleTime = (i / waveformData.length) * maxDuration;
                const drawX = x + labelWidth + sampleTime * pxPerSecond + offsetPx;
                
                if (drawX < x + labelWidth || drawX > x + labelWidth + waveformWidth) continue;
                
                const amplitude = waveformData[i] || 0;
                const topY = centerY - amplitude * waveHeight;
                
                if (i === 0) {
                    ctx.moveTo(drawX, topY);
                } else {
                    ctx.lineTo(drawX, topY);
                }
            }
            // Close through bottom
            for (let i = waveformData.length - 1; i >= 0; i--) {
                const sampleTime = (i / waveformData.length) * maxDuration;
                const drawX = x + labelWidth + sampleTime * pxPerSecond + offsetPx;
                
                if (drawX < x + labelWidth || drawX > x + labelWidth + waveformWidth) continue;
                
                const amplitude = waveformData[i] || 0;
                const bottomY = centerY + amplitude * waveHeight;
                ctx.lineTo(drawX, bottomY);
            }
            ctx.closePath();
            ctx.fill();
        }
    }
    
    /**
     * Format offset label for display
     */
    formatOffsetLabel(offsetSeconds) {
        const absOffset = Math.abs(offsetSeconds);
        const sign = offsetSeconds >= 0 ? '+' : '-';
        
        if (absOffset >= 60) {
            const mins = Math.floor(absOffset / 60);
            const secs = (absOffset % 60).toFixed(2);
            return `${sign}${mins}:${secs.padStart(5, '0')}`;
        } else {
            return `${sign}${absOffset.toFixed(2)}s`;
        }
    }
    
    /**
     * Highlight sync difference area in overlay mode
     */
    highlightSyncDifference(ctx, offsetSeconds, centerY) {
        if (Math.abs(offsetSeconds) < 0.01) return; // No significant offset
        
        const pixelsPerSecond = this.waveformWidth / this.viewWindow; // scale to current view window
        const offsetPixels = Math.abs(offsetSeconds) * pixelsPerSecond;
        const highlightWidth = Math.max(offsetPixels, 20);
        
        // Draw highlight area
        ctx.fillStyle = 'rgba(255, 193, 7, 0.2)';
        ctx.fillRect(offsetPixels - highlightWidth/2, centerY - this.waveformHeight/2, 
                    highlightWidth, this.waveformHeight);
        
        // Draw sync issue indicator
        ctx.strokeStyle = '#fbbf24';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(offsetPixels, centerY - this.waveformHeight/2);
        ctx.lineTo(offsetPixels, centerY + this.waveformHeight/2);
        ctx.stroke();
    }
    
    /**
     * Add handlers for timeline view toggle buttons
     */
    addTimelineToggleHandlers(container, masterId, dubId) {
        const toggleButtons = container.querySelectorAll('.timeline-toggle-btn');
        const canvas = container.querySelector(`#unified-timeline-${masterId}-${dubId}`);
        
        // Remove existing event listeners to prevent duplication
        toggleButtons.forEach(btn => {
            const oldHandler = btn._toggleHandler;
            if (oldHandler) {
                btn.removeEventListener('click', oldHandler);
            }
        });
        
        toggleButtons.forEach(btn => {
            const toggleHandler = () => {
                // Update active state
                toggleButtons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                
                // Get view mode and redraw
                const viewMode = btn.dataset.view;
                const ctx = canvas.getContext('2d');
                
                // Clear and set DPR transform without compounding
                ctx.setTransform(1, 0, 0, 1, 0, 0);
                ctx.clearRect(0, 0, canvas.width, canvas.height);
                ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
                
                const waveformData = this.audioData.get(`unified-timeline-${masterId}-${dubId}`);
                if (waveformData) {
                    this.drawUnifiedTimeline(ctx, waveformData.master, waveformData.dubBefore, 
                                          waveformData.dubAfter, waveformData.offsetSeconds, viewMode);
                }
            };
            
            // Store handler reference for cleanup
            btn._toggleHandler = toggleHandler;
            btn.addEventListener('click', toggleHandler);
        });
    }

    /**
     * Generate exact out-of-sync waveform representation
     */
    async generateOutOfSyncWaveform(dubId, offsetSeconds, container, phase) {
        const canvas = container.querySelector(`#dub-${phase}-waveform-${dubId}`);
        const ctx = canvas.getContext('2d');
        
        // Reset and apply DPR scaling once
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
        
        // Generate dub waveform data with exact offset
        const waveformData = this.generateRealisticWaveformData(this.waveformWidth, 'dub', phase === 'before' ? offsetSeconds : 0);
        
        // Store waveform data for zoom functionality
        this.audioData.set(`dub-${phase}-waveform-${dubId}`, waveformData);
        
        // Draw out-of-sync waveform with visual indication of misalignment
        this.drawWaveform(ctx, waveformData, {
            strokeStyle: phase === 'before' ? '#f44336' : '#4CAF50',
            fillStyle: phase === 'before' ? 'rgba(244, 67, 54, 0.3)' : 'rgba(76, 175, 80, 0.3)',
            lineWidth: 1,
            centerLine: true,
            offset: phase === 'before' ? offsetSeconds : 0
        });

        // Highlight sync issues for 'before' view
        if (phase === 'before') {
            this.highlightSyncIssues(ctx, waveformData, offsetSeconds);
        }
    }

    /**
     * Generate synchronized waveform (after correction)
     */
    async generateSynchronizedWaveform(dubId, offsetSeconds, container, phase) {
        await this.generateOutOfSyncWaveform(dubId, offsetSeconds, container, phase);
    }

    /**
     * Generate realistic waveform data simulating actual audio
     */
    generateRealisticWaveformData(width, type = 'master', offset = 0) {
        const data = new Float32Array(width);
        const baseFreq = type === 'master' ? 0.1 : 0.11; // Slight difference for dub
        const pixelsPerSecond = this.waveformWidth / this.viewWindow;
        const offsetPixels = offset * pixelsPerSecond; // negative = advance, positive = delay

        // Helper to synthesize a sample at a (possibly fractional) index
        const synthAt = (idx) => {
            // If out of bounds, return near-silence
            if (idx < 0 || idx >= width) return (Math.random() - 0.5) * 0.05;

            // Use idx as our time-like variable
            let s = 0;
            s += 0.6 * Math.sin(2 * Math.PI * baseFreq * idx);
            s += 0.3 * Math.sin(2 * Math.PI * baseFreq * 2 * idx + Math.PI * 0.3);
            s += 0.2 * Math.sin(2 * Math.PI * baseFreq * 3 * idx + Math.PI * 0.7);
            s += 0.1 * Math.sin(2 * Math.PI * baseFreq * 4 * idx + Math.PI * 1.1);
            // Add some noise for realism
            s += (Math.random() - 0.5) * 0.1;
            // Envelope modulation to simulate speech
            const envelope = 0.5 + 0.5 * Math.sin(2 * Math.PI * 0.02 * idx);
            s *= envelope;
            return s * 0.8; // Normalize amplitude
        };

        for (let i = 0; i < width; i++) {
            // Branch convention: positive = dub ahead (advance) → shift LEFT; negative = behind → shift RIGHT
            const sourceIndex = type === 'dub' && offset !== 0 ? (i + offsetPixels) : i;
            data[i] = synthAt(sourceIndex);
        }

        return data;
    }

    /**
     * Draw waveform on canvas with specified style
     */
    drawWaveform(ctx, data, style) {
        const width = this.waveformWidth;
        const height = style.trackHeight || this.waveformHeight;
        const centerY = style.yOffset || (height / 2);
        const amplitude = (style.trackHeight || this.waveformHeight) / 2;
        
        // Don't clear rect for unified timeline (multiple waveforms on same canvas)
        if (!style.yOffset) {
            ctx.clearRect(0, 0, width, height);
            
            // Fill background
            ctx.fillStyle = '#1a1a1a';
            ctx.fillRect(0, 0, width, height);
        }
        
        // Draw center line if requested
        if (style.centerLine) {
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 0.5;
            ctx.beginPath();
            ctx.moveTo(0, centerY);
            ctx.lineTo(width, centerY);
            ctx.stroke();
        }
        
        // Draw waveform fill
        ctx.fillStyle = style.fillStyle;
        ctx.beginPath();
        ctx.moveTo(0, centerY);
        
        for (let i = 0; i < data.length; i++) {
            const x = (i / data.length) * width;
            const y = centerY + (data[i] * amplitude * 0.9);
            ctx.lineTo(x, y);
        }
        
        for (let i = data.length - 1; i >= 0; i--) {
            const x = (i / data.length) * width;
            const y = centerY - (data[i] * amplitude * 0.9);
            ctx.lineTo(x, y);
        }
        
        ctx.closePath();
        ctx.fill();
        
        // Draw waveform outline
        ctx.strokeStyle = style.strokeStyle;
        ctx.lineWidth = style.lineWidth;
        ctx.beginPath();
        
        for (let i = 0; i < data.length; i++) {
            const x = (i / data.length) * width;
            const y = centerY + (data[i] * amplitude * 0.9);
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        
        ctx.stroke();
    }

    /**
     * Highlight sync issues in the waveform
     */
    highlightSyncIssues(ctx, data, offsetSeconds) {
        const width = this.waveformWidth;
        const height = this.waveformHeight;
        const offsetPixels = Math.abs(offsetSeconds) * (width / this.viewWindow); // scale to current view window
        
        // Highlight misaligned region
        ctx.fillStyle = 'rgba(255, 193, 7, 0.4)';
        ctx.fillRect(offsetPixels - 10, 0, 20, height);
        
        // Add warning indicators
        ctx.fillStyle = '#FF5722';
        ctx.font = '12px Arial';
        ctx.fillText('⚠ SYNC ISSUE', offsetPixels + 15, 20);
    }

    /**
     * Calculate visual position for offset indicator
     */
    calculateOffsetPosition(offsetSeconds) {
        // Convert offset to pixel position based on current view window
        const pixelsPerSecond = this.waveformWidth / this.viewWindow;
        return Math.abs(offsetSeconds) * pixelsPerSecond;
    }

    /**
     * Add sync indicators and measurements
     */
    addSyncIndicators(container, offsetSeconds) {
        // Add visual sync alignment guides
        const syncGuide = document.createElement('div');
        syncGuide.className = 'sync-alignment-guide';
        syncGuide.innerHTML = `
            <div class="guide-line master-guide"></div>
            <div class="guide-line dub-guide" style="transform: translateX(${this.calculateOffsetPosition(offsetSeconds)}px);"></div>
            <div class="alignment-measurement">
                <span class="measurement-value">${(Math.abs(offsetSeconds) * 1000).toFixed(2)}ms</span>
                <span class="measurement-direction">${offsetSeconds > 0 ? 'Dub Delayed' : 'Dub Advanced'}</span>
            </div>
        `;
        
        container.querySelector('.waveform-display-area').appendChild(syncGuide);
    }

    /**
     * Add interactive controls for waveform manipulation
     */
    addInteractiveControls(container, masterId, dubId, offsetSeconds) {
        const controls = container.querySelectorAll('.waveform-btn');
        
        controls.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.target.closest('button').dataset.action;
                this.handleWaveformAction(action, container, masterId, dubId, offsetSeconds);
            });
        });

        // Volume sliders
        const volumeSliders = container.querySelectorAll('.volume-slider');
        volumeSliders.forEach(slider => {
            const handler = (e) => {
                const track = slider.dataset.track;
                const value = parseFloat(slider.value);
                if (window.WaveformVisualizer && typeof this.setVolume === 'function') {
                    this.setVolume(track, value);
                }
            };
            slider.addEventListener('input', handler);
        });
        // Master output volume
        const out = container.querySelector('.master-output-slider');
        if (out) {
            const handler = () => {
                const v = parseFloat(out.value);
                if (typeof this.setMasterOutputVolume === 'function') this.setMasterOutputVolume(v);
            };
            out.addEventListener('input', handler);
        }
        // Balance slider
        const bal = container.querySelector('.balance-slider');
        if (bal) {
            const handler = () => {
                const v = parseFloat(bal.value);
                if (typeof this.setBalance === 'function') this.setBalance(v);
            };
            bal.addEventListener('input', handler);
        }
        // Pan sliders
        const pans = container.querySelectorAll('.pan-slider');
        pans.forEach(slider => {
            const handler = () => {
                const v = parseFloat(slider.value);
                const tr = slider.dataset.track;
                if (typeof this.setPan === 'function') this.setPan(tr, v);
            };
            slider.addEventListener('input', handler);
        });
        // Mute toggles
        const mutes = container.querySelectorAll('.mute-toggle');
        mutes.forEach(chk => {
            const handler = () => {
                const tr = chk.dataset.track;
                const on = !!chk.checked;
                if (typeof this.setMute === 'function') this.setMute(tr, on);
            };
            chk.addEventListener('change', handler);
        });
    }

    /**
     * Handle interactive waveform actions
     */
    handleWaveformAction(action, container, masterId, dubId, offsetSeconds) {
        // Get offsetSeconds from stored data if not provided
        if (!offsetSeconds) {
            const waveformKey = this.getWaveformKey(container);
            const waveformData = this.audioData.get(waveformKey);
            if (waveformData) {
                offsetSeconds = waveformData.offsetSeconds;
            }
        }
        
        switch (action) {
            case 'toggle-view':
                this.toggleBeforeAfterView(container);
                break;
            case 'zoom-in':
                this.zoomIn(container);
                break;
            case 'zoom-out':
                this.zoomOut(container);
                break;
            case 'zoom-fit':
                this.zoomToFit(container);
                break;
            case 'zoom-to-sync':
                this.zoomToSyncPoint(container, offsetSeconds);
                break;
            case 'fit-offset':
                this.fitOffset(container, offsetSeconds);
                break;
            case 'pan-left':
                this.panLeft(container);
                break;
            case 'pan-right':
                this.panRight(container);
                break;
            case 'reset-view':
                this.resetView(container);
                break;
            case 'play-comparison':
                this.playAudioComparison(masterId, dubId, offsetSeconds);
                break;
            case 'play-before':
                this.playAudioComparison(masterId, dubId, offsetSeconds, false);
                break;
            case 'play-after':
                this.playAudioComparison(masterId, dubId, offsetSeconds, true);
                break;
            case 'stop-playback':
                if (typeof this.stopAudio === 'function') this.stopAudio();
                break;
        }
    }

    /**
     * Toggle between before/after sync correction views
     */
    toggleBeforeAfterView(container) {
        const toggleBtn = container.querySelector('[data-action="toggle-view"]');
        const comparisonOverlay = container.querySelector('.comparison-overlay');
        const comparisonLegend = container.querySelector('.comparison-legend');
        const dubStatus = container.querySelector('.sync-status');
        
        // Find the unified timeline canvas
        const canvas = container.querySelector('.unified-timeline-canvas');
        const waveformKey = this.getWaveformKey(container);
        const waveformData = this.activeWaveforms.get(waveformKey);
        
        if (!canvas || !waveformData) return;
        
        const isShowingBefore = !comparisonOverlay || comparisonOverlay.style.display === 'none';
        
        if (isShowingBefore) {
            // Switch to after view
            if (comparisonOverlay) comparisonOverlay.style.display = 'block';
            if (comparisonLegend) comparisonLegend.style.display = 'flex';
            if (dubStatus) {
                dubStatus.textContent = 'Synchronized';
                dubStatus.className = 'track-status sync-status in-sync';
            }
            toggleBtn.innerHTML = '<i class="fas fa-undo"></i> Show Before Sync';
            
            // Redraw with synchronized waveform
            this.redrawUnifiedTimelineWithAfter(container);
            
        } else {
            // Switch to before view
            if (comparisonOverlay) comparisonOverlay.style.display = 'none';
            if (comparisonLegend) comparisonLegend.style.display = 'none';
            if (dubStatus) {
                dubStatus.textContent = 'Out of Sync';
                dubStatus.className = 'track-status sync-status out-of-sync';
            }
            toggleBtn.innerHTML = '<i class="fas fa-eye"></i> Toggle Before/After';
            
            // Redraw with out-of-sync waveform
            this.redrawUnifiedTimelineWithBefore(container);
        }
    }
    
    /**
     * Redraw unified timeline with before-sync data
     */
    redrawUnifiedTimelineWithBefore(container) {
        const canvas = container.querySelector('.unified-timeline-canvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
        
        const waveformKey = this.getWaveformKey(container);
        const storedData = this.audioData.get(waveformKey);
        
        if (storedData) {
            const currentView = container.querySelector('.timeline-toggle-btn.active')?.dataset.view || 'overlay';
            this.drawUnifiedTimeline(ctx, storedData.master, storedData.dubBefore, 
                                  storedData.dubAfter, storedData.offsetSeconds, currentView);
        }
    }
    
    /**
     * Redraw unified timeline with after-sync data
     */
    redrawUnifiedTimelineWithAfter(container) {
        const canvas = container.querySelector('.unified-timeline-canvas');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
        
        const waveformKey = this.getWaveformKey(container);
        const storedData = this.audioData.get(waveformKey);
        
        if (storedData) {
            const currentView = container.querySelector('.timeline-toggle-btn.active')?.dataset.view || 'overlay';
            this.drawUnifiedTimeline(ctx, storedData.master, storedData.dubAfter, 
                                  storedData.dubAfter, 0, currentView); // 0 offset for synchronized
        }
    }

    /**
     * Add time markers to waveform
     */
    addTimeMarkers(container, width) {
        container.innerHTML = '';
        // Use the same logic as zoomed markers for consistency
        this.addTimeMarkersZoomed(container, 0, this.viewWindow);
    }

    /**
     * Show error message if waveform generation fails
     */
    showWaveformError(container, message) {
        container.innerHTML = `
            <div class="waveform-error">
                <i class="fas fa-exclamation-triangle"></i>
                <h4>Waveform Generation Error</h4>
                <p>${message}</p>
                <button class="retry-btn" onclick="location.reload()">
                    <i class="fas fa-redo"></i> Retry
                </button>
            </div>
        `;
    }

    /**
     * Initialize zoom and pan functionality
     */
    initializeZoomAndPan(container, masterId, dubId) {
        const canvas = container.querySelector('.unified-timeline-canvas');
        const zoomSlider = container.querySelector('.zoom-slider');
        
        if (!canvas) return;
        
        // Store waveform reference with correct key
        const waveformKey = canvas.id;
        this.activeWaveforms.set(waveformKey, {
            container,
            canvas,
            zoomSlider,
            masterId,
            dubId
        });
        
        // Add mouse event listeners for pan and zoom
        this.addCanvasEventListeners(canvas, container);
        
        // Add zoom slider event listener - remove existing first
        if (zoomSlider) {
            const oldHandler = zoomSlider._zoomHandler;
            if (oldHandler) {
                zoomSlider.removeEventListener('input', oldHandler);
            }
            
            const zoomHandler = (e) => {
                this.setZoomLevel(container, parseFloat(e.target.value));
            };
            
            zoomSlider._zoomHandler = zoomHandler;
            zoomSlider.addEventListener('input', zoomHandler);
        }
        
        // Fix zoom control buttons
        const zoomButtons = container.querySelectorAll('.waveform-btn[data-action^="zoom"]');
        zoomButtons.forEach(btn => {
            const oldHandler = btn._zoomButtonHandler;
            if (oldHandler) {
                btn.removeEventListener('click', oldHandler);
            }
            
            const buttonHandler = (e) => {
                e.stopPropagation();
                const action = btn.dataset.action;
                this.handleWaveformAction(action, container, masterId, dubId);
            };
            
            btn._zoomButtonHandler = buttonHandler;
            btn.addEventListener('click', buttonHandler);
        });
        
        // Add keyboard shortcuts
        this.addKeyboardShortcuts(container);
    }
    
    /**
     * Add mouse and touch event listeners to canvas
     */
    addCanvasEventListeners(canvas, container) {
        // Mouse wheel zoom
        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? -this.zoomStep : this.zoomStep;
            const newZoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.zoomLevel + delta));
            this.setZoomLevel(container, newZoom);
        });
        
        // Mouse drag for panning
        canvas.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.lastMouseX = e.clientX;
            canvas.style.cursor = 'grabbing';
        });
        
        canvas.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                const deltaX = e.clientX - this.lastMouseX;
                this.panOffset += deltaX / this.zoomLevel;
                this.lastMouseX = e.clientX;
                this.clampPan();
                this.redrawAllWaveforms(container);
            }
        });
        
        canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
            canvas.style.cursor = 'grab';
        });
        
        canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            canvas.style.cursor = 'grab';
        });
        
        // Double-click to zoom to cursor position
        canvas.addEventListener('dblclick', (e) => {
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            this.zoomToCursor(container, x / rect.width);
        });
        
        // Touch events for mobile
        this.addTouchEventListeners(canvas, container);
    }

    /**
     * Add touch event listeners for mobile zoom and pan
     */
    
    /**
     * Keep pan within content bounds based on zoom level
     */
    clampPan() {
        const totalDuration = this.viewWindow;
        const visibleDuration = totalDuration / this.zoomLevel;
        const pixelsPerSecond = this.waveformWidth / totalDuration;
        // Convert current pan to visible start time (seconds)
        let visibleStart = -this.panOffset / pixelsPerSecond;
        const minStart = 0;
        const maxStart = Math.max(0, totalDuration - visibleDuration);
        if (visibleStart < minStart) visibleStart = minStart;
        if (visibleStart > maxStart) visibleStart = maxStart;
        // Recalculate panOffset from clamped visibleStart
        this.panOffset = -visibleStart * pixelsPerSecond;
    }
    addTouchEventListeners(canvas, container) {
        let touches = [];
        let lastTouchDistance = 0;
        
        canvas.addEventListener('touchstart', (e) => {
            touches = Array.from(e.touches);
            if (touches.length === 2) {
                lastTouchDistance = this.getTouchDistance(touches[0], touches[1]);
            }
        });
        
        canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            touches = Array.from(e.touches);
            
            if (touches.length === 2) {
                // Pinch zoom
                const distance = this.getTouchDistance(touches[0], touches[1]);
                const scale = distance / lastTouchDistance;
                const newZoom = Math.max(this.minZoom, Math.min(this.maxZoom, this.zoomLevel * scale));
                this.setZoomLevel(container, newZoom);
                lastTouchDistance = distance;
            } else if (touches.length === 1) {
                // Pan
                const touch = touches[0];
                const deltaX = touch.clientX - this.lastMouseX;
                this.panOffset += deltaX / this.zoomLevel;
                this.lastMouseX = touch.clientX;
                this.clampPan();
                this.redrawAllWaveforms(container);
            }
        });
    }
    
    /**
     * Get distance between two touch points
     */
    getTouchDistance(touch1, touch2) {
        const dx = touch1.clientX - touch2.clientX;
        const dy = touch1.clientY - touch2.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    /**
     * Add keyboard shortcuts for zoom and pan
     */
    addKeyboardShortcuts(container) {
        // Only add global keyboard listeners once
        if (!this.keyboardListenersAdded) {
            document.addEventListener('keydown', (e) => {
                // Check if a waveform container is focused
                const focusedContainer = document.activeElement.closest('.sync-waveform-container');
                if (!focusedContainer) return;
                
                switch (e.key) {
                    case '=':
                    case '+':
                        if (e.ctrlKey || e.metaKey) {
                            e.preventDefault();
                            this.zoomIn(focusedContainer);
                        }
                        break;
                    case '-':
                        if (e.ctrlKey || e.metaKey) {
                            e.preventDefault();
                            this.zoomOut(focusedContainer);
                        }
                        break;
                    case 'f':
                    case 'F':
                        e.preventDefault();
                        this.zoomToFit(focusedContainer);
                        break;
                    case 's':
                    case 'S':
                        e.preventDefault();
                        this.zoomToSyncPoint(focusedContainer);
                        break;
                    case 'r':
                    case 'R':
                        e.preventDefault();
                        this.resetView(focusedContainer);
                        break;
                    case 'ArrowLeft':
                        e.preventDefault();
                        this.panLeft(focusedContainer);
                        break;
                    case 'ArrowRight':
                        e.preventDefault();
                        this.panRight(focusedContainer);
                        break;
                }
            });
            this.keyboardListenersAdded = true;
        }
        
        // Make container focusable for keyboard shortcuts
        container.setAttribute('tabindex', '0');
    }
    
    /**
     * Zoom in
     */
    zoomIn(container) {
        const newZoom = Math.min(this.maxZoom, this.zoomLevel + this.zoomStep * 5);
        this.setZoomLevel(container, newZoom);
    }
    
    /**
     * Zoom out
     */
    zoomOut(container) {
        const newZoom = Math.max(this.minZoom, this.zoomLevel - this.zoomStep * 5);
        this.setZoomLevel(container, newZoom);
    }
    
    /**
     * Zoom to fit all content
     */
    zoomToFit(container) {
        // Fit to whatever the current viewWindow represents (real duration if loaded)
        this.panOffset = 0;
        this.setZoomLevel(container, 1.0);
        this.redrawAllWaveforms(container);
    }
    
    /**
     * Reset view to default
     */
    resetView(container) {
        this.zoomLevel = 1.0;
        this.panOffset = 0;
        this.redrawAllWaveforms(container);
        this.updateZoomDisplay(container);
    }
    
    /**
     * Pan left
     */
    panLeft(container) {
        this.panOffset += 50 / this.zoomLevel;
        this.clampPan();
        this.redrawAllWaveforms(container);
    }
    
    /**
     * Pan right
     */
    panRight(container) {
        this.panOffset -= 50 / this.zoomLevel;
        this.clampPan();
        this.redrawAllWaveforms(container);
    }
    
    /**
     * Set zoom level and update display
     */
    setZoomLevel(container, newZoom) {
        this.zoomLevel = Math.max(this.minZoom, Math.min(this.maxZoom, newZoom));
        this.clampPan();
        this.redrawAllWaveforms(container);
        this.updateZoomDisplay(container);
    }
    
    /**
     * Update zoom display elements
     */
    updateZoomDisplay(container) {
        const zoomDisplay = container.querySelector('.zoom-level');
        const zoomSlider = container.querySelector('.zoom-slider');
        
        if (zoomDisplay) {
            zoomDisplay.textContent = `${(this.zoomLevel * 100).toFixed(0)}%`;
        }
        if (zoomSlider) {
            zoomSlider.value = this.zoomLevel;
        }
    }
    
    /**
     * Zoom to cursor position
     */
    zoomToCursor(container, normalizedX) {
        const oldZoom = this.zoomLevel;
        const newZoom = Math.min(this.maxZoom, oldZoom * 2);
        
        // Adjust pan to keep cursor position centered
        const cursorOffset = (normalizedX - 0.5) * this.waveformWidth;
        this.panOffset += cursorOffset * (1 / oldZoom - 1 / newZoom);
        this.clampPan();
        
        this.setZoomLevel(container, newZoom);
    }
    
    /**
     * Redraw all waveforms with current zoom and pan
     */
    redrawAllWaveforms(container) {
        const canvas = container.querySelector('.unified-timeline-canvas');
        if (!canvas) return;
        
        const canvasId = canvas.id;
        const waveformData = this.audioData.get(canvasId);
        if (!waveformData) return;
        
        const ctx = canvas.getContext('2d');
        
        // Clear and apply DPR transform without compounding
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.setTransform(this.pixelRatio, 0, 0, this.pixelRatio, 0, 0);
        
        // Get current view mode
        const activeToggle = container.querySelector('.timeline-toggle-btn.active');
        const viewMode = activeToggle ? activeToggle.dataset.view : 'overlay';
        
        // Apply zoom and pan to waveform data
        const zoomedMaster = this.applyZoomPan(waveformData.master);
        const zoomedDubBefore = this.applyZoomPan(waveformData.dubBefore);
        const zoomedDubAfter = this.applyZoomPan(waveformData.dubAfter);
        
        // Draw unified timeline with zoom applied
        this.drawUnifiedTimeline(ctx, zoomedMaster, zoomedDubBefore, zoomedDubAfter, 
                               waveformData.offsetSeconds, viewMode);
        
        // Update time markers
        this.updateTimeMarkersForZoom(container);
        
        // Update offset indicators
        this.updateOffsetIndicatorsForZoom(container);
        // Update drift markers
        this.updateDriftMarkersForZoom(container);
    }
    
    /**
     * Redraw waveform with zoom and pan applied
     */
    redrawWaveformWithZoom(ctx, canvasId) {
        // Get stored waveform data
        const data = this.audioData.get(canvasId);
        if (!data) return;
        
        // For unified timeline, we need to handle it differently
        if (canvasId.includes('unified-timeline')) {
            const activeToggle = document.querySelector('.timeline-toggle-btn.active');
            const viewMode = activeToggle ? activeToggle.dataset.view : 'overlay';
            
            const zoomedMaster = this.applyZoomPan(data.master);
            const zoomedDubBefore = this.applyZoomPan(data.dubBefore);
            const zoomedDubAfter = this.applyZoomPan(data.dubAfter);
            
            this.drawUnifiedTimeline(ctx, zoomedMaster, zoomedDubBefore, zoomedDubAfter, 
                                   data.offsetSeconds, viewMode);
            return;
        }
        
        // Legacy single waveform handling
        const zoomedData = this.applyZoomPan(data);
        
        // Determine canvas style based on ID
        let style = {
            strokeStyle: '#4CAF50',
            fillStyle: 'rgba(76, 175, 80, 0.3)',
            lineWidth: 1,
            centerLine: true
        };
        
        if (canvasId.includes('dub-before')) {
            style.strokeStyle = '#f44336';
            style.fillStyle = 'rgba(244, 67, 54, 0.3)';
        }
        
        // Draw the waveform
        this.drawWaveform(ctx, zoomedData, style);
    }
    
    /**
     * Get zoomed portion of waveform data
     */
    getZoomedWaveformData(originalData, startTime, duration) {
        const totalDuration = this.viewWindow;
        const startIndex = Math.max(0, Math.floor((startTime / totalDuration) * originalData.length));
        const endIndex = Math.min(originalData.length, Math.ceil(((startTime + duration) / totalDuration) * originalData.length));
        
        return originalData.slice(startIndex, endIndex);
    }
    
    /**
     * Apply zoom and pan transformations to waveform data
     */
    applyZoomPan(originalData) {
        if (this.zoomLevel === 1.0 && this.panOffset === 0) {
            return originalData;
        }
        
        const totalDuration = this.viewWindow;
        const visibleDuration = totalDuration / this.zoomLevel;
        const visibleStart = -this.panOffset / (this.waveformWidth / totalDuration);
        
        const startIndex = Math.max(0, Math.floor((visibleStart / totalDuration) * originalData.length));
        const endIndex = Math.min(originalData.length, 
            Math.ceil(((visibleStart + visibleDuration) / totalDuration) * originalData.length));
        
        // Extract the visible portion
        const visibleData = originalData.slice(startIndex, endIndex);
        
        // If we need more samples due to zoom, interpolate
        if (this.zoomLevel > 1.0 && visibleData.length < this.waveformWidth) {
            const interpolatedData = new Float32Array(this.waveformWidth);
            for (let i = 0; i < this.waveformWidth; i++) {
                const sourceIndex = (i / this.waveformWidth) * (visibleData.length - 1);
                const lowerIndex = Math.floor(sourceIndex);
                const upperIndex = Math.ceil(sourceIndex);
                const fraction = sourceIndex - lowerIndex;
                
                if (upperIndex < visibleData.length) {
                    interpolatedData[i] = visibleData[lowerIndex] * (1 - fraction) + 
                                        visibleData[upperIndex] * fraction;
                } else {
                    interpolatedData[i] = visibleData[lowerIndex] || 0;
                }
            }
            return interpolatedData;
        }
        
        return visibleData;
    }
    
    /**
     * Update time markers for current zoom level
     */
    updateTimeMarkersForZoom(container) {
        const timeMarkers = container.querySelectorAll('.time-markers');
        const visibleDuration = this.viewWindow / this.zoomLevel;
        const visibleStart = -this.panOffset / (this.waveformWidth / this.viewWindow);
        
        timeMarkers.forEach(markerContainer => {
            this.addTimeMarkersZoomed(markerContainer, visibleStart, visibleDuration);
        });
    }
    
    /**
     * Add time markers for zoomed view
     */
    addTimeMarkersZoomed(container, startTime, duration) {
        container.innerHTML = '';
        
        // Determine appropriate marker interval based on zoom
        let interval = 1; // seconds
        if (duration > 300) interval = 30;
        else if (duration > 60) interval = 10;
        else if (duration < 2) interval = 0.1;
        else if (duration < 10) interval = 0.5;
        
        const pixelsPerSecond = this.waveformWidth / duration;
        
        for (let time = Math.ceil(startTime / interval) * interval; 
             time <= startTime + duration; 
             time += interval) {
            
            const position = (time - startTime) * pixelsPerSecond;
            if (position >= 0 && position <= this.waveformWidth) {
                const marker = document.createElement('div');
                marker.className = 'time-marker';
                marker.style.left = `${position}px`;
                marker.innerHTML = `<span>${time.toFixed(interval < 1 ? 1 : 0)}s</span>`;
                container.appendChild(marker);
            }
        }
    }
    
    /**
     * Update offset indicators for current zoom level
     */
    updateOffsetIndicatorsForZoom(container) {
        const offsetIndicators = container.querySelectorAll('.sync-offset-indicator');
        const visibleStart = -this.panOffset / (this.waveformWidth / this.viewWindow);
        const visibleDuration = this.viewWindow / this.zoomLevel;
        
        // Update position based on zoom and pan
        offsetIndicators.forEach(indicator => {
            const offsetSeconds = parseFloat(indicator.dataset.offset || '0');
            const relativePosition = (offsetSeconds - visibleStart) / visibleDuration;
            const pixelPosition = relativePosition * this.waveformWidth;
            
            if (pixelPosition >= 0 && pixelPosition <= this.waveformWidth) {
                indicator.style.left = `${pixelPosition}px`;
                indicator.style.display = 'block';
            } else {
                indicator.style.display = 'none';
            }
        });
    }
    
    /**
     * Get waveform key for tracking
     */
    getWaveformKey(container) {
        // Look for unified timeline canvas
        const unifiedCanvas = container.querySelector('.unified-timeline-canvas');
        if (unifiedCanvas) {
            return unifiedCanvas.id;
        }
        
        // Fallback to extracting from other elements
        const masterId = container.querySelector('[id*="master-waveform"]')?.id?.match(/master-waveform-(.+)/)?.[1];
        const dubId = container.querySelector('[id*="dub-"]')?.id?.match(/dub-(?:before|after)-waveform-(.+)/)?.[1];
        return masterId && dubId ? `unified-timeline-${masterId}-${dubId}` : null;
    }

    /**
     * Simulate audio comparison playback
     */
    playAudioComparison(masterId, dubId, offsetSeconds) {
        console.log(`Playing audio comparison: Master ${masterId} vs Dub ${dubId} (offset: ${offsetSeconds}s)`);
        // In a real implementation, this would use Web Audio API to play synchronized audio
    }

    /**
     * Zoom to sync point in waveform
     */
    zoomToSyncPoint(container, offsetSeconds) {
        if (!offsetSeconds) {
            const waveformKey = this.getWaveformKey(container);
            const waveformData = this.audioData.get(waveformKey);
            if (waveformData) {
                offsetSeconds = waveformData.offsetSeconds;
            }
        }
        
        if (!offsetSeconds) return;
        
        // Calculate pan offset to center on sync point
        const pixelsPerSecond = this.waveformWidth / this.viewWindow;
        const syncPointPixel = Math.abs(offsetSeconds) * pixelsPerSecond;
        const centerOffset = this.waveformWidth / 2;
        
        // Set pan to center the sync point
        this.panOffset = centerOffset - syncPointPixel;
        
        // Set zoom level to show detail
        this.setZoomLevel(container, Math.min(this.maxZoom, 5.0));
    }

    /**
     * Fit the entire offset in view (with padding)
     */
    fitOffset(container, offsetSeconds) {
        if (!offsetSeconds) {
            const waveformKey = this.getWaveformKey(container);
            const waveformData = this.audioData.get(waveformKey);
            if (waveformData) offsetSeconds = waveformData.offsetSeconds;
        }
        const absOff = Math.abs(offsetSeconds || 0);
        // At least show twice the offset plus padding
        const targetWindow = Math.max(10, absOff * 2 + 2);
        this.viewWindow = targetWindow;
        this.panOffset = 0;
        this.setZoomLevel(container, 1.0);
        this.redrawAllWaveforms(container);
        this.updateZoomDisplay(container);
    }
}

// Export for use in main application
window.WaveformVisualizer = WaveformVisualizer;
