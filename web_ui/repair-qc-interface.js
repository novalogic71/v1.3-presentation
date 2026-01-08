/**
 * Repair QC Interface: interactive offset manipulation and repair tools.
 * Separate from the QC modal, focused on preparing corrected outputs.
 */

class RepairQCInterface {
    constructor(options = {}) {
        this.audioEngine = null;
        this.currentData = null;
        this.isVisible = false;
        this.apiBase = options.apiBase || (window.app ? window.app.FASTAPI_BASE : '/api/v1');

        this.initializeModal();
        this.setupEventListeners();
    }

    initializeModal() {
        const modalHTML = `
            <div id="repair-qc-modal" class="qc-modal" style="display: none;">
                <div class="qc-modal-content">
                    <div class="qc-header">
                        <h3><i class="fas fa-toolbox"></i> Repair QC</h3>
                        <button class="qc-close-btn" id="repair-qc-close-btn"><i class="fas fa-times"></i></button>
                    </div>

                    <div class="qc-file-info">
                        <div class="qc-file-pair">
                            <div class="qc-file-item master-file">
                                <label>Master File:</label>
                                <span id="repair-qc-master-file">No file selected</span>
                            </div>
                            <div class="qc-file-item dub-file">
                                <label>Dub File:</label>
                                <span id="repair-qc-dub-file">No file selected</span>
                            </div>
                        </div>
                    </div>

                    <div class="qc-waveform-container">
                        <div class="qc-waveform-header">
                            <h4><i class="fas fa-chart-area"></i> Waveform (Adjustable)</h4>
                            <div class="qc-view-toggle">
                                <button class="qc-toggle-btn active" data-view="before"><i class="fas fa-exclamation-triangle"></i> Before</button>
                                <button class="qc-toggle-btn" data-view="after"><i class="fas fa-check-circle"></i> After</button>
                            </div>
                        </div>
                        <div class="qc-waveform-display" style="position:relative;">
                            <canvas id="repair-qc-canvas" width="900" height="320"></canvas>
                            <div class="qc-waveform-overlay" style="position:absolute;left:0;top:0;right:0;bottom:0;z-index:5;pointer-events:auto;">
                                <div class="qc-scene-bands" id="repair-qc-scene-bands" style="position:absolute;left:0;top:0;right:0;bottom:0;display:flex;gap:2px;z-index:6;"></div>
                                <div class="qc-drift-markers" id="repair-qc-drift-markers" style="position:absolute;left:0;bottom:0;right:0;height:100%;z-index:6;"></div>
                            </div>
                        </div>

                        <!-- Repair QC Drift Timeline Legend and Guide -->
                        <div class="qc-timeline-info" id="repair-qc-timeline-info" style="display: none;">
                            <div class="qc-drift-legend">
                                <div class="legend-header">
                                    <span><i class="fas fa-timeline"></i> Timeline: <span id="repair-qc-drift-count">0</span> drift points</span>
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
                            <h4><i class="fas fa-sliders-h"></i> Offset Controls</h4>
                            <div class="qc-play-buttons" style="gap: 8px; flex-wrap: wrap;">
                                <button class="qc-play-btn" data-nudge="-0.100">-100ms</button>
                                <button class="qc-play-btn" data-nudge="-0.050">-50ms</button>
                                <button class="qc-play-btn" data-nudge="-0.010">-10ms</button>
                                <button class="qc-play-btn" data-nudge="0.010">+10ms</button>
                                <button class="qc-play-btn" data-nudge="0.050">+50ms</button>
                                <button class="qc-play-btn" data-nudge="0.100">+100ms</button>
                                <label style="display:flex;align-items:center;gap:6px;margin-left:8px;">
                                    Offset (s)
                                    <input type="number" step="0.001" id="repair-qc-offset" style="width:120px" value="0.000" />
                                </label>
                                <label style="display:flex;align-items:center;gap:6px;margin-left:8px;">
                                    <input type="checkbox" id="repair-qc-keepdur" checked /> Keep duration
                                </label>
                            </div>

                            <div class="qc-play-buttons" style="margin-top:10px;">
                                <button class="qc-play-btn primary" id="repair-qc-play-before"><i class="fas fa-exclamation-triangle"></i> Play Problem</button>
                                <button class="qc-play-btn success" id="repair-qc-play-after"><i class="fas fa-check-circle"></i> Play Fixed</button>
                                <button class="qc-play-btn" id="repair-qc-stop"><i class="fas fa-stop"></i> Stop</button>
                            </div>
                        </div>
                    </div>

                    <div class="qc-volume-controls">
                        <div class="qc-volume-section">
                            <h4><i class="fas fa-stream"></i> Per-Channel Offsets</h4>
                            <div id="repair-qc-channels" class="per-channel-table" style="max-height:200px;overflow:auto;"></div>
                        </div>
                    </div>

                    <div class="qc-actions">
                        <button class="qc-action-btn success" id="repair-qc-apply"><i class="fas fa-hammer"></i> Apply Repair</button>
                        <button class="qc-action-btn" id="repair-qc-export"><i class="fas fa-download"></i> Export Config</button>
                    </div>
                </div>
            </div>
        `;
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.initializeAudioEngine();
    }

    initializeAudioEngine() {
        try {
            this.audioEngine = new CoreAudioEngine();
            this.audioEngine.onAudioLoaded = () => this.updateWaveform();
        } catch (e) {
            console.warn('RepairQC: audio init failed', e);
        }
    }

    setupEventListeners() {
        document.addEventListener('click', (e) => {
            if (e.target.closest('#repair-qc-close-btn')) this.close();
            if (e.target.closest('#repair-qc-play-before')) this.play(false);
            if (e.target.closest('#repair-qc-play-after')) this.play(true);
            if (e.target.closest('#repair-qc-stop')) this.stop();
            const n = e.target.closest('[data-nudge]');
            if (n) {
                const v = parseFloat(n.getAttribute('data-nudge') || '0');
                const input = document.getElementById('repair-qc-offset');
                if (input) {
                    input.value = (parseFloat(input.value || '0') + v).toFixed(3);
                    this.updateWaveform();
                }
            }
            if (e.target.classList && e.target.classList.contains('repair-qc-open')) {
                // external trigger — not used here
            }
            if (e.target.closest('.qc-toggle-btn')) {
                const btn = e.target.closest('.qc-toggle-btn');
                document.querySelectorAll('#repair-qc-modal .qc-toggle-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.updateWaveform();
            }
            if (e.target.closest('#repair-qc-apply')) this.applyRepair();
            if (e.target.closest('#repair-qc-export')) this.exportConfig();
        });

        document.addEventListener('input', (e) => {
            if (e.target && e.target.id === 'repair-qc-offset') this.updateWaveform();
            if (e.target && e.target.classList && e.target.classList.contains('repair-qc-chan-input')) this.updateWaveform();
        });
    }

    async open(syncData, opts = {}) {
        this.apiBase = opts.apiBase || this.apiBase;
        this.currentData = syncData || {};
        this.isVisible = true;
        document.getElementById('repair-qc-modal').style.display = 'flex';
        document.getElementById('repair-qc-master-file').textContent = syncData.masterFile || 'Unknown';
        document.getElementById('repair-qc-dub-file').textContent = syncData.dubFile || 'Unknown';
        const off = typeof syncData.detectedOffset === 'number' ? syncData.detectedOffset : 0;
        const offInput = document.getElementById('repair-qc-offset');
        if (offInput) offInput.value = off.toFixed(3);
        this.renderChannelTable(syncData.perChannel || syncData.per_channel_results, off);

        // Load audio
        try {
            if (syncData.masterUrl) await this.audioEngine.loadAudioUrl(syncData.masterUrl, 'master');
            if (syncData.dubUrl) await this.audioEngine.loadAudioUrl(syncData.dubUrl, 'dub');
        } catch (e) {
            console.warn('RepairQC audio load failed', e);
        }
        this.updateWaveform();
        this.renderDriftMarkers();
        this.renderSceneBands();
    }

    close() {
        this.isVisible = false;
        const modal = document.getElementById('repair-qc-modal');
        if (modal) modal.style.display = 'none';
        try { this.audioEngine?.stopPlayback(); } catch {}
    }

    getEditedOffsets() {
        const table = document.getElementById('repair-qc-channels');
        const inputs = table ? table.querySelectorAll('input.repair-qc-chan-input') : [];
        const m = {};
        inputs.forEach(inp => {
            const role = inp.getAttribute('data-role');
            const v = parseFloat(inp.value || '0') || 0;
            m[role] = { offset_seconds: v };
        });
        // Ensure we have at least a uniform map using overall offset
        if (Object.keys(m).length === 0) {
            const o = parseFloat((document.getElementById('repair-qc-offset')?.value) || '0') || 0;
            ['FL','FR','FC','LFE','SL','SR','S0','S1','S2','S3','S4','S5'].forEach(r => m[r] = { offset_seconds: o });
        }
        return m;
    }

    renderChannelTable(per, fallbackOffset = 0) {
        const host = document.getElementById('repair-qc-channels');
        if (!host) return;
        const entries = per && typeof per === 'object' ? Object.entries(per) : [];
        if (!entries.length) {
            host.innerHTML = `<div class="hint">No per-channel results reported. Editing will apply a uniform offset.</div>`;
            return;
        }
        const rows = entries.map(([role, v]) => {
            const off = (v && typeof v === 'object' && typeof v.offset_seconds === 'number') ? v.offset_seconds : fallbackOffset;
            return `<div style="display:flex;align-items:center;gap:8px;margin:4px 0;">
                <code style="width:48px;display:inline-block;">${role}</code>
                <input class="repair-qc-chan-input" data-role="${role}" type="number" step="0.001" value="${off.toFixed(3)}" style="width:120px;" />
                <span>sec</span>
            </div>`;
        }).join('');
        host.innerHTML = rows;
    }

    updateWaveform() {
        const canvas = document.getElementById('repair-qc-canvas');
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = '#111';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        const isAfter = document.querySelector('#repair-qc-modal .qc-toggle-btn[data-view="after"]').classList.contains('active');
        const off = parseFloat(document.getElementById('repair-qc-offset')?.value || '0') || 0;

        const m = this.audioEngine?.masterWaveformData;
        const d = this.audioEngine?.dubWaveformData;
        if (!m || !d) {
            ctx.fillStyle = '#666';
            ctx.font = '14px Arial';
            ctx.fillText('Load audio to view waveform', 20, 24);
            return;
        }
        const width = canvas.width;
        const height = canvas.height;
        const centerY = height / 2;
        const waveH = height / 4;
        const maxDur = Math.max(m.duration || 1, d.duration || 1);
        const pixelsPerSec = width / maxDur;
        // Before uses natural audio; After applies the entered offset to simulate correction
        const px = (isAfter ? off : 0) * pixelsPerSec;

        // Master
        ctx.strokeStyle = '#4ade80';
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < m.peaks.length; i++) {
            const x = (i / m.peaks.length) * (m.duration / maxDur) * width;
            const y = centerY - (m.peaks[i] * waveH);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
        // Dub
        ctx.strokeStyle = '#f87171';
        ctx.beginPath();
        for (let i = 0; i < d.peaks.length; i++) {
            const baseX = (i / d.peaks.length) * (d.duration / maxDur) * width;
            const x = baseX + px;
            const y = centerY + (d.peaks[i] * waveH);
            if (x >= 0 && x <= width) {
                if (i === 0 || (i > 0 && baseX + px < 0)) ctx.moveTo(x, y); else ctx.lineTo(x, y);
            }
        }
        ctx.stroke();

        // Labels
        ctx.fillStyle = '#9ca3af';
        ctx.font = '12px Arial';
        ctx.fillText(isAfter ? 'After (aligned)' : 'Before (problem)', width - 140, 18);
        this.renderDriftMarkers();
        this.renderSceneBands();
    }

    play(corrected) {
        const off = parseFloat(document.getElementById('repair-qc-offset')?.value || '0') || 0;
        try { this.audioEngine?.playComparison(off, !!corrected); } catch {}
    }

    stop() {
        try { this.audioEngine?.stopPlayback(); } catch {}
    }

    async applyRepair() {
        const keep = !!document.getElementById('repair-qc-keepdur')?.checked;
        const per = this.getEditedOffsets();
        const filePath = this.currentData?.dubPath || this.currentData?.dub_file || this.currentData?.dubPathname || this.currentData?.dubUrl;
        if (!filePath || typeof filePath !== 'string') {
            alert('No dub file path available for repair');
            return;
        }
        try {
            const resp = await fetch(`${this.apiBase}/repair/repair/per-channel`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: filePath, per_channel_results: per, keep_duration: keep })
            });
            const j = await resp.json().catch(() => ({}));
            if (resp.ok && j.success) {
                alert(`Repair complete: ${j.output_file}`);
            } else {
                alert(`Repair failed: ${j.error || resp.status}`);
            }
        } catch (e) {
            alert(`Repair error: ${e.message}`);
        }
    }

    exportConfig() {
        const per = this.getEditedOffsets();
        const cfg = {
            file_path: this.currentData?.dubPath || this.currentData?.dub_file,
            keep_duration: !!document.getElementById('repair-qc-keepdur')?.checked,
            per_channel_results: per,
            detectedOffset: this.currentData?.detectedOffset || 0,
            generated_at: new Date().toISOString()
        };
        const blob = new Blob([JSON.stringify(cfg, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `repair-qc-config-${Date.now()}.json`;
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    renderDriftMarkers() {
        const container = document.getElementById('repair-qc-drift-markers');
        const canvas = document.getElementById('repair-qc-canvas');
        const timelineInfo = document.getElementById('repair-qc-timeline-info');
        const driftCount = document.getElementById('repair-qc-drift-count');

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

        const m = this.audioEngine?.masterWaveformData;
        const d = this.audioEngine?.dubWaveformData;
        const maxDur = Math.max(m?.duration || 0, d?.duration || 0) || 0;
        if (!maxDur) return;

        const pxPerSec = canvas.width / maxDur;

        timeline.forEach(seg => {
            const start = typeof seg.start_time === 'number' ? seg.start_time : 0;
            const end = typeof seg.end_time === 'number' ? seg.end_time : start;
            const off = typeof seg.offset_seconds === 'number' ? seg.offset_seconds : 0;
            const mag = Math.abs(off);
            const x = start * pxPerSec;
            const w = Math.max(2, (end - start) * pxPerSec);

            let cls = 'minor';
            if (mag >= 0.25) cls = 'major';
            else if (mag >= 0.10) cls = 'issue';
            else if (mag < 0.03) cls = 'insync';

            const el = document.createElement('div');
            el.className = `qc-drift-marker severity-${cls}`;
            el.style.position = 'absolute';
            el.style.left = `${x}px`;
            el.style.bottom = '0';
            el.style.top = '0';
            el.style.width = `${w}px`;
            el.style.pointerEvents = 'auto';
            el.title = `${start.toFixed(2)}s → ${end.toFixed(2)}s • ${(off*1000).toFixed(0)}ms` + (seg.reliable ? ' • reliable' : '');

            const line = document.createElement('div');
            line.style.position = 'absolute';
            line.style.left = '0';
            line.style.top = '0';
            line.style.bottom = '0';
            line.style.width = '2px';
            line.style.background = cls === 'major' ? '#ef4444' : cls === 'issue' ? '#f59e0b' : cls === 'insync' ? '#10b981' : '#fbbf24';
            line.style.opacity = '0.9';
            el.appendChild(line);

            el.addEventListener('click', (e) => {
                e.stopPropagation();
                try { this.audioEngine?.seekTo(start); } catch {}
            });

            container.appendChild(el);
        });
    }

    renderSceneBands() {
        const container = document.getElementById('repair-qc-scene-bands');
        const canvas = document.getElementById('repair-qc-canvas');
        if (!container || !canvas) return;
        container.innerHTML = '';

        const op = this.currentData?.operatorTimeline || this.currentData?.operator_timeline;
        const scenes = Array.isArray(op?.scenes) ? op.scenes : [];
        const timeline = Array.isArray(this.currentData?.timeline) ? this.currentData.timeline : [];

        const m = this.audioEngine?.masterWaveformData;
        const d = this.audioEngine?.dubWaveformData;
        const maxDur = Math.max(m?.duration || 0, d?.duration || 0) || 0;
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
                try { this.audioEngine?.seekTo(b.start); } catch {}
            });

            container.appendChild(el);
        });
    }
}

window.RepairQCInterface = RepairQCInterface;
