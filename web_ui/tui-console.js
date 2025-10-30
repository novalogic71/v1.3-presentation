/**
 * Professional TUI Console Status System
 * Terminal-inspired interface for sync analyzer progress and status
 */

class TUIConsole {
    constructor() {
        this.progressStages = new Map();
        this.systemStats = {
            status: 'ready',
            gpu: { active: 0, total: 0 },
            memory: { used: 0, total: 0 },
            currentOperation: null
        };
        this.logBuffer = [];
        this.maxLogEntries = 50;
        this.animationFrame = null;
        this.lastUpdate = 0;
        
        this.init();
    }
    
    init() {
        this.createTUIElements();
        this.setupEventListeners();
        this.startUpdateLoop();
    }
    
    createTUIElements() {
        // Find the existing console-status quadrant
        const consoleQuadrant = document.querySelector('.console-status .quadrant-content');
        if (!consoleQuadrant) {
            console.error('Console status quadrant not found');
            return;
        }
        
        // Clear existing content
        consoleQuadrant.innerHTML = '';
        
        // Create TUI container
        const tuiContainer = document.createElement('div');
        tuiContainer.className = 'tui-console';
        tuiContainer.innerHTML = `
            <div class="tui-system-status">
                <div class="tui-box">
                    <div class="tui-box-header">SYSTEM STATUS</div>
                    <div class="tui-box-content">
                        <div class="tui-status-line">
                            <span class="status-indicator">🟢</span>
                            <span class="status-text">Ready</span>
                            <span class="status-detail">GPU: 0/0 Active</span>
                            <span class="status-memory">Memory: 0GB/0GB</span>
                        </div>
                        <div class="tui-overall-progress">
                            <span class="progress-label">Analysis Pipeline:</span>
                            <div class="tui-progress-bar">
                                <div class="progress-track"></div>
                                <div class="progress-fill" style="width: 0%"></div>
                                <span class="progress-text">0%</span>
                            </div>
                        </div>
                        <div class="tui-chunk-info">
                            <span class="chunk-counter">Chunks: 0/0</span>
                            <span class="chunk-detail">Ready</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="tui-progress-stages">
                <div class="tui-box">
                    <div class="tui-box-header">ANALYSIS PROGRESS</div>
                    <div class="tui-box-content" id="tui-stages-content">
                        <div class="tui-stage-placeholder">Waiting for analysis to start...</div>
                    </div>
                </div>
            </div>
            
            <div class="tui-activity-log">
                <div class="tui-box">
                    <div class="tui-box-header">
                        RECENT ACTIVITY
                        <div class="tui-log-controls">
                            <button class="tui-btn" id="tui-clear-log">Clear</button>
                            <button class="tui-btn" id="tui-scroll-toggle">Auto</button>
                        </div>
                    </div>
                    <div class="tui-box-content tui-log-container" id="tui-log-content">
                        <div class="tui-log-entry startup">
                            <span class="log-time">${this.getCurrentTime()}</span>
                            <span class="log-icon">🚀</span>
                            <span class="log-message">Professional Audio Sync Analyzer initialized</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="tui-visualization">
                <div class="tui-box">
                    <div class="tui-box-header">CHUNK ANALYSIS MAP</div>
                    <div class="tui-box-content" id="tui-viz-content">
                        <div class="tui-timeline">
                            <div class="timeline-label">Timeline:</div>
                            <div class="timeline-bar" id="tui-timeline-bar">
                                <span class="timeline-placeholder">No analysis in progress</span>
                            </div>
                            <div class="timeline-duration">0s────0s</div>
                        </div>
                        <div class="tui-quality-bar">
                            <div class="quality-label">Quality:</div>
                            <div class="quality-meter">
                                <div class="quality-fill" style="width: 0%"></div>
                                <span class="quality-text">Avg: 0%</span>
                            </div>
                        </div>
                        <div class="tui-status-summary" id="tui-status-summary">
                            Ready for analysis
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        consoleQuadrant.appendChild(tuiContainer);
        
        // Store references to key elements
        this.elements = {
            statusIndicator: tuiContainer.querySelector('.status-indicator'),
            statusText: tuiContainer.querySelector('.status-text'),
            statusDetail: tuiContainer.querySelector('.status-detail'),
            statusMemory: tuiContainer.querySelector('.status-memory'),
            overallProgress: tuiContainer.querySelector('.progress-fill'),
            progressText: tuiContainer.querySelector('.progress-text'),
            chunkCounter: tuiContainer.querySelector('.chunk-counter'),
            chunkDetail: tuiContainer.querySelector('.chunk-detail'),
            stagesContent: tuiContainer.querySelector('#tui-stages-content'),
            logContent: tuiContainer.querySelector('#tui-log-content'),
            timelineBar: tuiContainer.querySelector('#tui-timeline-bar'),
            timelineDuration: tuiContainer.querySelector('.timeline-duration'),
            qualityFill: tuiContainer.querySelector('.quality-fill'),
            qualityText: tuiContainer.querySelector('.quality-text'),
            statusSummary: tuiContainer.querySelector('#tui-status-summary')
        };
    }
    
    setupEventListeners() {
        // Clear log button
        document.getElementById('tui-clear-log')?.addEventListener('click', () => {
            this.clearLog();
        });
        
        // Auto-scroll toggle
        let autoScroll = true;
        document.getElementById('tui-scroll-toggle')?.addEventListener('click', (e) => {
            autoScroll = !autoScroll;
            e.target.textContent = autoScroll ? 'Auto' : 'Manual';
            e.target.classList.toggle('active', autoScroll);
        });
    }
    
    getCurrentTime() {
        return new Date().toLocaleTimeString('en-US', { 
            hour12: false, 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
    }
    
    updateSystemStatus(status, details = {}) {
        this.systemStats = { ...this.systemStats, ...details };
        
        // Update status indicator
        const statusConfig = {
            ready: { icon: '🟢', text: 'Ready', class: 'ready' },
            processing: { icon: '⚡', text: 'Processing', class: 'processing' },
            completed: { icon: '✅', text: 'Completed', class: 'completed' },
            error: { icon: '❌', text: 'Error', class: 'error' },
            warning: { icon: '⚠️', text: 'Warning', class: 'warning' }
        };
        
        const config = statusConfig[status] || statusConfig.ready;
        
        if (this.elements.statusIndicator) {
            this.elements.statusIndicator.textContent = config.icon;
            this.elements.statusText.textContent = config.text;
            this.elements.statusText.className = `status-text ${config.class}`;
        }
        
        // Update GPU info
        if (details.gpu) {
            this.elements.statusDetail.textContent = 
                `GPU: ${details.gpu.active}/${details.gpu.total} Active`;
        }
        
        // Update memory info
        if (details.memory) {
            this.elements.statusMemory.textContent = 
                `Memory: ${details.memory.used.toFixed(1)}GB/${details.memory.total.toFixed(1)}GB`;
        }
    }
    
    updateOverallProgress(percentage, message) {
        if (this.elements.overallProgress) {
            this.elements.overallProgress.style.width = `${Math.max(0, Math.min(100, percentage))}%`;
            this.elements.progressText.textContent = `${Math.round(percentage)}%`;
        }
    }
    
    updateChunkProgress(processed, total, message) {
        if (this.elements.chunkCounter) {
            this.elements.chunkCounter.textContent = `Chunks: ${processed}/${total}`;
            this.elements.chunkDetail.textContent = message || `${total - processed} remaining`;
        }
    }
    
    setProgressStage(stageName, percentage, status = 'pending') {
        this.progressStages.set(stageName, { percentage, status });
        this.renderProgressStages();
    }
    
    renderProgressStages() {
        const stageOrder = [
            { key: 'loading', name: 'Audio Loading', icon: '📁' },
            { key: 'mfcc', name: 'MFCC Extraction', icon: '🔊' },
            { key: 'correlation', name: 'Correlation Analysis', icon: '🔍' },
            { key: 'consensus', name: 'Consensus Analysis', icon: '🧠' },
            { key: 'reporting', name: 'Report Generation', icon: '📊' }
        ];
        
        let stagesHTML = '';
        
        for (const stage of stageOrder) {
            const stageData = this.progressStages.get(stage.key) || { percentage: 0, status: 'pending' };
            const statusIcon = this.getStageStatusIcon(stageData.status);
            const progressBar = this.createProgressBar(stageData.percentage);
            
            stagesHTML += `
                <div class="tui-stage ${stageData.status}">
                    <span class="stage-status">${statusIcon}</span>
                    <span class="stage-name">${stage.name}</span>
                    <div class="stage-progress">${progressBar}</div>
                    <span class="stage-percent">${Math.round(stageData.percentage)}%</span>
                </div>
            `;
        }
        
        this.elements.stagesContent.innerHTML = stagesHTML;
    }
    
    getStageStatusIcon(status) {
        const icons = {
            pending: '⏸️',
            processing: '⚡',
            completed: '✅',
            error: '❌'
        };
        return icons[status] || '⏸️';
    }
    
    createProgressBar(percentage, width = 20) {
        const filled = Math.round((percentage / 100) * width);
        const empty = width - filled;
        return `[${'\u2588'.repeat(filled)}${'\u2591'.repeat(empty)}]`;
    }
    
    addLogEntry(type, message, icon = null) {
        const entry = {
            timestamp: this.getCurrentTime(),
            type,
            message,
            icon: icon || this.getLogIcon(type)
        };
        
        this.logBuffer.push(entry);
        
        // Keep buffer size manageable
        if (this.logBuffer.length > this.maxLogEntries) {
            this.logBuffer.shift();
        }
        
        this.renderLogEntries();
    }
    
    getLogIcon(type) {
        const icons = {
            info: 'ℹ️',
            success: '✅',
            warning: '⚠️',
            error: '❌',
            progress: '⚡',
            chunk: '📊',
            gpu: '🎮'
        };
        return icons[type] || 'ℹ️';
    }
    
    renderLogEntries() {
        const logsHTML = this.logBuffer.map(entry => `
            <div class="tui-log-entry ${entry.type}">
                <span class="log-time">${entry.timestamp}</span>
                <span class="log-icon">${entry.icon}</span>
                <span class="log-message">${entry.message}</span>
            </div>
        `).join('');
        
        this.elements.logContent.innerHTML = logsHTML;
        
        // Auto-scroll to bottom
        if (this.elements.logContent.querySelector('#tui-scroll-toggle')?.classList.contains('active') !== false) {
            this.elements.logContent.scrollTop = this.elements.logContent.scrollHeight;
        }
    }
    
    updateTimeline(chunks, duration) {
        if (!chunks || chunks.length === 0) {
            this.elements.timelineBar.innerHTML = '<span class="timeline-placeholder">No analysis in progress</span>';
            this.elements.timelineDuration.textContent = '0s────0s';
            return;
        }
        
        let timelineHTML = '';
        for (let i = 0; i < chunks.length; i++) {
            const chunk = chunks[i];
            const status = chunk.status || 'pending';
            const statusIcon = this.getChunkStatusIcon(status);
            timelineHTML += `<span class="timeline-chunk ${status}" title="Chunk ${i+1}: ${chunk.start_time}s-${chunk.end_time}s">${statusIcon}</span>`;
        }
        
        this.elements.timelineBar.innerHTML = timelineHTML;
        this.elements.timelineDuration.textContent = `0s────${Math.round(duration)}s`;
        
        // Update quality meter
        const completedChunks = chunks.filter(c => c.status === 'completed');
        if (completedChunks.length > 0) {
            const avgQuality = completedChunks.reduce((sum, c) => sum + (c.quality || 0), 0) / completedChunks.length;
            this.elements.qualityFill.style.width = `${avgQuality}%`;
            this.elements.qualityText.textContent = `Avg: ${Math.round(avgQuality)}%`;
        }
        
        // Update status summary
        const completed = chunks.filter(c => c.status === 'completed').length;
        const processing = chunks.filter(c => c.status === 'processing').length;
        const pending = chunks.filter(c => c.status === 'pending').length;
        
        this.elements.statusSummary.textContent = 
            `${completed} completed, ${processing} processing, ${pending} pending`;
    }
    
    getChunkStatusIcon(status) {
        const icons = {
            pending: '⏳',
            processing: '⚡',
            completed: '✅',
            error: '❌'
        };
        return icons[status] || '⏳';
    }
    
    clearLog() {
        this.logBuffer = [];
        this.elements.logContent.innerHTML = `
            <div class="tui-log-entry startup">
                <span class="log-time">${this.getCurrentTime()}</span>
                <span class="log-icon">🧹</span>
                <span class="log-message">Activity log cleared</span>
            </div>
        `;
    }
    
    startUpdateLoop() {
        const update = (timestamp) => {
            if (timestamp - this.lastUpdate > 100) { // Update every 100ms
                this.updateAnimations();
                this.lastUpdate = timestamp;
            }
            this.animationFrame = requestAnimationFrame(update);
        };
        this.animationFrame = requestAnimationFrame(update);
    }
    
    updateAnimations() {
        // Add subtle animations for processing states
        const processingElements = document.querySelectorAll('.tui-stage.processing .stage-status');
        processingElements.forEach(el => {
            if (!el.classList.contains('animate')) {
                el.classList.add('animate');
                setTimeout(() => el.classList.remove('animate'), 1000);
            }
        });
    }
    
    destroy() {
        if (this.animationFrame) {
            cancelAnimationFrame(this.animationFrame);
        }
    }
    
    // Public API methods for integration
    startAnalysis(config) {
        this.updateSystemStatus('processing');
        this.addLogEntry('info', `Starting analysis: ${config.master} + ${config.dub}`, '🎵');
        this.setProgressStage('loading', 0, 'processing');
    }
    
    updateAnalysisProgress(data) {
        if (data.stage) {
            this.setProgressStage(data.stage, data.percentage, 'processing');
        }
        if (data.overall_progress) {
            this.updateOverallProgress(data.overall_progress, data.message);
        }
        if (data.chunks) {
            this.updateTimeline(data.chunks, data.duration);
        }
        if (data.message) {
            this.addLogEntry(data.type || 'progress', data.message);
        }
    }
    
    completeAnalysis(result) {
        this.updateSystemStatus('completed');
        this.updateOverallProgress(100, 'Analysis Complete');
        this.setProgressStage('reporting', 100, 'completed');
        
        const offsetMs = Math.abs(result.offset_seconds * 1000);
        this.addLogEntry('success', `Analysis complete: ${offsetMs.toFixed(1)}ms offset detected`, '🎯');
        
        if (result.chunks_analyzed) {
            this.addLogEntry('chunk', `Long method used: ${result.chunks_analyzed} chunks analyzed`);
        }
    }
    
    handleError(error) {
        this.updateSystemStatus('error');
        this.addLogEntry('error', `Analysis failed: ${error.message}`, '💥');
        
        // Mark current stages as error
        for (const [key, stage] of this.progressStages) {
            if (stage.status === 'processing') {
                this.setProgressStage(key, stage.percentage, 'error');
            }
        }
    }
}

// Export for use in other modules
window.TUIConsole = TUIConsole;