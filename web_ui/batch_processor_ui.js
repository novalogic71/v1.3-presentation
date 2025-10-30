/**
 * Enhanced Batch Processing UI with CSV Upload and Formatted Reports
 */

class BatchProcessorUI {
    constructor(apiBase) {
        this.FASTAPI_BASE = apiBase;
        this.currentBatchId = null;
        this.statusCheckInterval = null;
        this.uploadedCSV = null;
        
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        // Create CSV upload section
        const uploadSection = document.createElement('div');
        uploadSection.className = 'csv-upload-section';
        uploadSection.innerHTML = `
            <div class="card">
                <div class="card-header">
                    <h3>📊 Batch CSV Processing</h3>
                    <p>Upload a CSV file to process multiple video pairs simultaneously</p>
                </div>
                <div class="card-body">
                    <div class="upload-area" id="csvUploadArea">
                        <div class="upload-drop-zone" id="csvDropZone">
                            <i class="upload-icon">📁</i>
                            <p class="upload-text">
                                <strong>Drop CSV file here or click to browse</strong><br>
                                <small>Required columns: master_file, dub_file, episode_name</small>
                            </p>
                            <input type="file" id="csvFileInput" accept=".csv" style="display: none;">
                        </div>
                    </div>
                    
                    <div class="csv-preview" id="csvPreview" style="display: none;">
                        <h4>CSV Preview</h4>
                        <div class="preview-table" id="previewTable"></div>
                        <div class="upload-controls">
                            <input type="text" id="outputDirInput" placeholder="Output directory (optional)" 
                                   value="batch_results" class="form-input">
                            <label class="checkbox-label">
                                <input type="checkbox" id="generatePlotsCheck" checked> Generate visualization plots
                            </label>
                            <div class="worker-controls">
                                <label>Max Workers: 
                                    <input type="number" id="maxWorkersInput" min="1" max="8" value="" 
                                           placeholder="Auto" class="form-input small">
                                </label>
                            </div>
                            <div class="button-group">
                                <button id="startBatchBtn" class="btn btn-primary">
                                    🚀 Start Batch Processing
                                </button>
                                <button id="clearBatchBtn" class="btn btn-secondary">
                                    🗑️ Clear
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Create batch status section
        const statusSection = document.createElement('div');
        statusSection.className = 'batch-status-section';
        statusSection.innerHTML = `
            <div class="card" id="batchStatusCard" style="display: none;">
                <div class="card-header">
                    <h3>📈 Batch Processing Status</h3>
                    <div class="status-badges">
                        <span class="badge" id="batchStatusBadge">Initializing</span>
                        <span class="badge" id="batchProgressBadge">0/0</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="progress-container">
                        <div class="progress-bar">
                            <div class="progress-fill" id="batchProgressFill"></div>
                        </div>
                        <div class="progress-text" id="batchProgressText">Preparing...</div>
                    </div>
                    
                    <div class="batch-details">
                        <div class="detail-row">
                            <span class="label">Batch ID:</span>
                            <span class="value" id="batchIdDisplay">-</span>
                        </div>
                        <div class="detail-row">
                            <span class="label">Episodes:</span>
                            <span class="value" id="episodeCountDisplay">0</span>
                        </div>
                        <div class="detail-row">
                            <span class="label">Output Directory:</span>
                            <span class="value" id="outputDirDisplay">-</span>
                        </div>
                        <div class="detail-row">
                            <span class="label">Elapsed Time:</span>
                            <span class="value" id="elapsedTimeDisplay">00:00</span>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Create results section
        const resultsSection = document.createElement('div');
        resultsSection.className = 'batch-results-section';
        resultsSection.innerHTML = `
            <div class="card" id="batchResultsCard" style="display: none;">
                <div class="card-header">
                    <h3>📋 Batch Results</h3>
                    <div class="results-actions">
                        <button id="downloadResultsBtn" class="btn btn-secondary">
                            💾 Download Summary
                        </button>
                        <button id="showAllReportsBtn" class="btn btn-primary">
                            📊 View All Reports
                        </button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="results-summary" id="resultsSummary"></div>
                    <div class="results-table-container">
                        <table class="results-table" id="resultsTable">
                            <thead>
                                <tr>
                                    <th>Episode</th>
                                    <th>Status</th>
                                    <th>Duration</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody id="resultsTableBody">
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;

        // Create formatted report viewer
        const reportViewerSection = document.createElement('div');
        reportViewerSection.className = 'report-viewer-section';
        reportViewerSection.innerHTML = `
            <div class="modal" id="reportModal" style="display: none;">
                <div class="modal-content large">
                    <div class="modal-header">
                        <h3 id="reportTitle">Formatted Analysis Report</h3>
                        <div class="modal-controls">
                            <button id="reportFormatToggle" class="btn btn-secondary small">
                                📝 Switch to Markdown
                            </button>
                            <button id="downloadReportBtn" class="btn btn-secondary small">
                                💾 Download
                            </button>
                            <button class="modal-close" id="reportModalClose">×</button>
                        </div>
                    </div>
                    <div class="modal-body">
                        <div class="report-content" id="reportContent"></div>
                    </div>
                </div>
            </div>
        `;

        // Insert sections into the page
        const container = document.querySelector('#batch-controls') || document.body;
        container.appendChild(uploadSection);
        container.appendChild(statusSection);
        container.appendChild(resultsSection);
        document.body.appendChild(reportViewerSection);
    }

    bindEvents() {
        // File upload events
        const csvFileInput = document.getElementById('csvFileInput');
        const csvDropZone = document.getElementById('csvDropZone');
        const uploadArea = document.getElementById('csvUploadArea');

        csvDropZone.addEventListener('click', () => csvFileInput.click());
        csvFileInput.addEventListener('change', (e) => this.handleFileSelect(e.target.files[0]));

        // Drag and drop
        csvDropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            csvDropZone.classList.add('drag-over');
        });

        csvDropZone.addEventListener('dragleave', () => {
            csvDropZone.classList.remove('drag-over');
        });

        csvDropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            csvDropZone.classList.remove('drag-over');
            this.handleFileSelect(e.dataTransfer.files[0]);
        });

        // Control buttons
        document.getElementById('startBatchBtn').addEventListener('click', () => this.startBatchProcessing());
        document.getElementById('clearBatchBtn').addEventListener('click', () => this.clearBatch());

        // Results actions
        document.getElementById('downloadResultsBtn')?.addEventListener('click', () => this.downloadResults());
        document.getElementById('showAllReportsBtn')?.addEventListener('click', () => this.showAllReports());

        // Report modal
        document.getElementById('reportModalClose')?.addEventListener('click', () => this.closeReportModal());
        document.getElementById('reportFormatToggle')?.addEventListener('click', () => this.toggleReportFormat());
        document.getElementById('downloadReportBtn')?.addEventListener('click', () => this.downloadCurrentReport());
    }

    async handleFileSelect(file) {
        if (!file) return;

        if (!file.name.toLowerCase().endsWith('.csv')) {
            this.showError('Please select a CSV file');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('output_dir', document.getElementById('outputDirInput').value || 'batch_results');

        try {
            this.showProgress('Uploading CSV...');
            
            const response = await fetch(`${this.FASTAPI_BASE}/reports/batch/csv`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Upload failed');
            }

            const result = await response.json();
            this.uploadedCSV = result;
            this.currentBatchId = result.batch_id;
            
            this.showCSVPreview(result);
            this.hideProgress();

        } catch (error) {
            console.error('CSV upload error:', error);
            this.showError(`Upload failed: ${error.message}`);
            this.hideProgress();
        }
    }

    showCSVPreview(uploadResult) {
        const previewSection = document.getElementById('csvPreview');
        const previewTable = document.getElementById('previewTable');

        // Create table from CSV preview data
        if (uploadResult.csv_preview && uploadResult.csv_preview.length > 0) {
            const headers = Object.keys(uploadResult.csv_preview[0]);
            
            let tableHTML = `
                <table class="preview-table">
                    <thead>
                        <tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>
                    </thead>
                    <tbody>
                        ${uploadResult.csv_preview.map(row => 
                            `<tr>${headers.map(h => `<td>${row[h] || ''}</td>`).join('')}</tr>`
                        ).join('')}
                    </tbody>
                </table>
            `;

            previewTable.innerHTML = tableHTML;
        }

        // Update batch info
        document.getElementById('batchIdDisplay').textContent = uploadResult.batch_id;
        document.getElementById('episodeCountDisplay').textContent = uploadResult.episodes_count;

        previewSection.style.display = 'block';
        this.showSuccess(`CSV uploaded successfully. Found ${uploadResult.episodes_count} episodes to process.`);
    }

    async startBatchProcessing() {
        if (!this.currentBatchId) {
            this.showError('Please upload a CSV file first');
            return;
        }

        const maxWorkers = document.getElementById('maxWorkersInput').value || null;
        const generatePlots = document.getElementById('generatePlotsCheck').checked;

        try {
            const params = new URLSearchParams();
            if (maxWorkers) params.append('max_workers', maxWorkers);
            params.append('generate_plots', generatePlots.toString());

            const response = await fetch(
                `${this.FASTAPI_BASE}/reports/batch/${this.currentBatchId}/process?${params}`,
                { method: 'POST' }
            );

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start batch processing');
            }

            const result = await response.json();
            
            this.showBatchStatus();
            this.startStatusMonitoring();
            this.showSuccess(`Batch processing started with ${result.episodes_count || this.uploadedCSV.episodes_count} episodes`);

            // Update display
            document.getElementById('outputDirDisplay').textContent = result.output_dir;

        } catch (error) {
            console.error('Batch start error:', error);
            this.showError(`Failed to start batch processing: ${error.message}`);
        }
    }

    showBatchStatus() {
        const statusCard = document.getElementById('batchStatusCard');
        statusCard.style.display = 'block';
        
        // Update status
        document.getElementById('batchStatusBadge').textContent = 'Processing';
        document.getElementById('batchStatusBadge').className = 'badge processing';
    }

    startStatusMonitoring() {
        this.statusStartTime = Date.now();
        
        this.statusCheckInterval = setInterval(async () => {
            await this.checkBatchStatus();
        }, 3000); // Check every 3 seconds
    }

    async checkBatchStatus() {
        if (!this.currentBatchId) return;

        try {
            const response = await fetch(`${this.FASTAPI_BASE}/reports/batch/${this.currentBatchId}/status`);
            if (!response.ok) return;

            const result = await response.json();
            const batchInfo = result.batch_info;

            // Update elapsed time
            if (this.statusStartTime) {
                const elapsed = Math.floor((Date.now() - this.statusStartTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                document.getElementById('elapsedTimeDisplay').textContent = 
                    `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            }

            // Check if completed
            if (batchInfo.status === 'completed' && batchInfo.results) {
                this.handleBatchCompletion(batchInfo.results);
                if (this.statusCheckInterval) {
                    clearInterval(this.statusCheckInterval);
                    this.statusCheckInterval = null;
                }
            }

        } catch (error) {
            console.error('Status check error:', error);
        }
    }

    handleBatchCompletion(results) {
        // Update status
        document.getElementById('batchStatusBadge').textContent = 'Completed';
        document.getElementById('batchStatusBadge').className = 'badge completed';

        const summary = results.processing_summary;
        const episodes = results.episode_results;

        // Update progress
        document.getElementById('batchProgressText').textContent = 
            `Completed ${summary.total_episodes} episodes`;
        document.getElementById('batchProgressFill').style.width = '100%';

        // Show results
        this.showBatchResults(results);
    }

    showBatchResults(results) {
        const resultsCard = document.getElementById('batchResultsCard');
        const summaryDiv = document.getElementById('resultsSummary');
        const tableBody = document.getElementById('resultsTableBody');

        const summary = results.processing_summary;

        // Create summary
        summaryDiv.innerHTML = `
            <div class="summary-stats">
                <div class="stat-item">
                    <div class="stat-value">${summary.total_episodes}</div>
                    <div class="stat-label">Total Episodes</div>
                </div>
                <div class="stat-item success">
                    <div class="stat-value">${summary.successful}</div>
                    <div class="stat-label">Successful</div>
                </div>
                <div class="stat-item warning">
                    <div class="stat-value">${summary.drift_detected || 0}</div>
                    <div class="stat-label">Drift Detected</div>
                </div>
                <div class="stat-item error">
                    <div class="stat-value">${summary.failed}</div>
                    <div class="stat-label">Failed</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${(summary.total_time_seconds / 60).toFixed(1)}m</div>
                    <div class="stat-label">Total Time</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${summary.throughput_episodes_per_minute.toFixed(1)}</div>
                    <div class="stat-label">Episodes/Min</div>
                </div>
            </div>
        `;

        // Create results table
        tableBody.innerHTML = results.episode_results.map(result => {
            const statusClass = this.getStatusClass(result.status);
            const statusIcon = this.getStatusIcon(result.status);
            
            return `
                <tr class="result-row ${statusClass}">
                    <td class="episode-name">${result.episode}</td>
                    <td class="status">${statusIcon} ${result.status}</td>
                    <td class="duration">${result.duration.toFixed(1)}s</td>
                    <td class="actions">
                        ${result.json_output ? 
                            `<button onclick="batchUI.viewReport('${result.episode}', '${result.json_output}')" 
                                    class="btn btn-small">📊 Report</button>` : ''
                        }
                        ${result.report_output ? 
                            `<button onclick="batchUI.downloadFile('${result.report_output}')" 
                                    class="btn btn-small">📝 Download</button>` : ''
                        }
                    </td>
                </tr>
            `;
        }).join('');

        resultsCard.style.display = 'block';
        
        // Show success message
        if (summary.failed === 0) {
            this.showSuccess('🎉 All episodes processed successfully!');
        } else {
            this.showWarning(`⚠️ ${summary.failed} episodes failed - check individual results`);
        }
    }

    async viewReport(episodeName, jsonPath) {
        try {
            // For now, download and display the JSON
            // In production, this would call the formatted report API
            const response = await fetch(jsonPath);
            if (!response.ok) throw new Error('Failed to load report');
            
            const reportData = await response.json();
            
            // Show formatted report modal (simplified version)
            this.showFormattedReport(episodeName, reportData);
            
        } catch (error) {
            console.error('Report viewing error:', error);
            this.showError(`Failed to load report: ${error.message}`);
        }
    }

    showFormattedReport(episodeName, reportData) {
        const modal = document.getElementById('reportModal');
        const title = document.getElementById('reportTitle');
        const content = document.getElementById('reportContent');

        title.textContent = `Analysis Report: ${episodeName}`;
        
        // Create a simple formatted view of the JSON data
        content.innerHTML = this.formatReportData(reportData);
        
        modal.style.display = 'block';
        this.currentReportData = { episodeName, data: reportData };
    }

    formatReportData(data) {
        // Simple JSON to HTML formatting
        const timeline = data.timeline || [];
        const drift = data.drift_analysis || {};
        
        let html = `
            <div class="report-section">
                <h3>📊 Analysis Summary</h3>
                <div class="summary-grid">
                    <div class="summary-item">
                        <strong>Duration:</strong> ${(data.master_duration / 60).toFixed(1)} minutes
                    </div>
                    <div class="summary-item">
                        <strong>Chunks Analyzed:</strong> ${timeline.length}
                    </div>
                    <div class="summary-item">
                        <strong>Overall Offset:</strong> ${data.consensus_offset?.offset_seconds?.toFixed(3) || 'N/A'}s
                    </div>
                    <div class="summary-item">
                        <strong>Confidence:</strong> ${data.consensus_offset?.confidence?.toFixed(3) || 'N/A'}
                    </div>
                </div>
            </div>
        `;

        if (drift.has_drift) {
            html += `
                <div class="report-section">
                    <h3>⚠️ Drift Analysis</h3>
                    <div class="drift-info">
                        <p><strong>Significant Drift Detected:</strong> ${drift.drift_magnitude?.toFixed(3)}s</p>
                        <p><strong>Summary:</strong> ${drift.drift_summary || 'No summary available'}</p>
                    </div>
                </div>
            `;
        }

        if (timeline.length > 0) {
            html += `
                <div class="report-section">
                    <h3>📈 Timeline Analysis</h3>
                    <div class="timeline-preview">
                        <p>Showing first 10 chunks of ${timeline.length} total:</p>
                        <table class="timeline-table">
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Offset</th>
                                    <th>Confidence</th>
                                    <th>Reliable</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${timeline.slice(0, 10).map(chunk => `
                                    <tr class="${chunk.reliable ? 'reliable' : 'unreliable'}">
                                        <td>${(chunk.start_time / 60).toFixed(1)}m</td>
                                        <td>${chunk.offset_seconds?.toFixed(3) || 'N/A'}s</td>
                                        <td>${chunk.confidence?.toFixed(3) || 'N/A'}</td>
                                        <td>${chunk.reliable ? '✅' : '❌'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }

        return html;
    }

    getStatusClass(status) {
        switch (status) {
            case 'SUCCESS': return 'success';
            case 'DRIFT_DETECTED': return 'warning';
            case 'ANALYSIS_FAILED':
            case 'ERROR':
            case 'TIMEOUT': return 'error';
            default: return '';
        }
    }

    getStatusIcon(status) {
        switch (status) {
            case 'SUCCESS': return '✅';
            case 'DRIFT_DETECTED': return '⚠️';
            case 'ANALYSIS_FAILED': return '❌';
            case 'TIMEOUT': return '⏰';
            case 'ERROR': return '💥';
            default: return '❓';
        }
    }

    closeReportModal() {
        document.getElementById('reportModal').style.display = 'none';
    }

    clearBatch() {
        this.currentBatchId = null;
        this.uploadedCSV = null;
        
        if (this.statusCheckInterval) {
            clearInterval(this.statusCheckInterval);
            this.statusCheckInterval = null;
        }
        
        document.getElementById('csvPreview').style.display = 'none';
        document.getElementById('batchStatusCard').style.display = 'none';
        document.getElementById('batchResultsCard').style.display = 'none';
        document.getElementById('csvFileInput').value = '';
    }

    // Utility methods
    showSuccess(message) {
        // Integration with existing toast system
        if (window.showToast) {
            window.showToast('success', message, 'Batch Processing');
        } else {
            alert(message);
        }
    }

    showError(message) {
        if (window.showToast) {
            window.showToast('error', message, 'Batch Processing');
        } else {
            alert('Error: ' + message);
        }
    }

    showWarning(message) {
        if (window.showToast) {
            window.showToast('warning', message, 'Batch Processing');
        } else {
            alert('Warning: ' + message);
        }
    }

    showProgress(message) {
        // Could integrate with existing progress indicators
        console.log('Progress:', message);
    }

    hideProgress() {
        // Hide progress indicators
        console.log('Progress complete');
    }
}

// Global instance
let batchUI = null;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Get API base from main UI if available
    const apiBase = window.syncUI?.FASTAPI_BASE || 'http://localhost:8000/api/v1';
    batchUI = new BatchProcessorUI(apiBase);
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BatchProcessorUI;
}