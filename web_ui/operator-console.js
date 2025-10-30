/**
 * Operator-Friendly Console System
 * Replaces the complex TUI with clear, visual status information for operators
 */

class OperatorConsole {
    constructor() {
        this.currentAnalysisResult = null;
        this.systemStatus = 'ready';
        this.currentOperation = null;
        this.analysisProgress = {
            stage: null,
            percentage: 0,
            message: ''
        };

        this.severityIndicators = {
            'IN_SYNC': { icon: '🟢', label: 'IN SYNC', description: 'Perfect sync' },
            'MINOR_DRIFT': { icon: '🟡', label: 'MINOR DRIFT', description: 'Minor drift detected' },
            'SYNC_ISSUE': { icon: '🟠', label: 'SYNC ISSUE', description: 'Needs correction' },
            'MAJOR_DRIFT': { icon: '🔴', label: 'MAJOR DRIFT', description: 'Critical problem' },
            'NO_DATA': { icon: '❓', label: 'NO DATA', description: 'Unable to analyze' }
        };

        this.contentTypes = {
            'dialogue': { icon: '🎭', label: 'Dialogue Scene' },
            'music': { icon: '🎵', label: 'Music Scene' },
            'mixed': { icon: '🎬', label: 'Mixed Content' },
            'silence': { icon: '🔇', label: 'Silence/Pause' },
            'unknown': { icon: '❓', label: 'Unknown Content' }
        };

        this.init();
    }

    init() {
        this.createOperatorElements();
        this.bindEvents();
    }

    createOperatorElements() {
        // Find the existing console-status quadrant
        const consoleQuadrant = document.querySelector('.console-status .quadrant-content');
        if (!consoleQuadrant) {
            console.error('Console status quadrant not found');
            return;
        }

        // Preserve the existing log-container before clearing
        const existingLogContainer = consoleQuadrant.querySelector('#log-container');

        // Clear existing TUI content (but don't remove the log-container yet)
        consoleQuadrant.innerHTML = '';

        // Create operator-friendly console wrapper that includes status AND logs
        const operatorContainer = document.createElement('div');
        operatorContainer.className = 'operator-console-wrapper';
        operatorContainer.innerHTML = `
            <div class="operator-status-compact">
                <div class="status-indicator-compact">
                    <span class="status-icon" id="operator-status-icon">🟢</span>
                    <span class="status-text" id="operator-status-text">Ready</span>
                </div>
            </div>
        `;

        // Append the operator status
        consoleQuadrant.appendChild(operatorContainer);

        // Restore the log-container after operator status
        if (existingLogContainer) {
            consoleQuadrant.appendChild(existingLogContainer);
        }

        this.bindOperatorEvents();
    }

    bindOperatorEvents() {
        const viewToggle = document.getElementById('timeline-view-toggle');
        if (viewToggle) {
            viewToggle.addEventListener('click', () => this.toggleTimelineView());
        }
    }

    bindEvents() {
        // Listen for analysis events
        document.addEventListener('analysisStarted', (e) => this.handleAnalysisStarted(e.detail));
        document.addEventListener('analysisProgress', (e) => this.handleAnalysisProgress(e.detail));
        document.addEventListener('analysisComplete', (e) => this.handleAnalysisComplete(e.detail));
        document.addEventListener('analysisError', (e) => this.handleAnalysisError(e.detail));
    }

    updateStatus(status, message, icon = null) {
        this.systemStatus = status;

        const statusIcon = document.getElementById('operator-status-icon');
        const statusText = document.getElementById('operator-status-text');

        if (statusIcon && statusText) {
            if (icon) statusIcon.textContent = icon;
            statusText.textContent = message;

            // Update status styling
            const statusIndicator = statusIcon.parentElement;
            statusIndicator.className = `status-indicator status-${status.toLowerCase()}`;
        }
    }

    handleAnalysisStarted(details) {
        this.updateStatus('analyzing', 'Analysis in Progress...', '⚡');
        this.showAnalysisProgress();
        this.hideAnalysisResults();
    }

    handleAnalysisProgress(progress) {
        this.analysisProgress = progress;
        this.updateProgressDisplay();
    }

    handleAnalysisComplete(result) {
        this.currentAnalysisResult = result;
        this.updateStatus('complete', 'Analysis Complete', '✅');
        this.hideAnalysisProgress();
        this.displayAnalysisResults();
    }

    handleAnalysisError(error) {
        this.updateStatus('error', `Error: ${error.message}`, '❌');
        this.hideAnalysisProgress();
        this.hideAnalysisResults();
    }

    showAnalysisProgress() {
        const progressElement = document.getElementById('analysis-progress');
        if (progressElement) {
            progressElement.style.display = 'block';
        }
    }

    hideAnalysisProgress() {
        const progressElement = document.getElementById('analysis-progress');
        if (progressElement) {
            progressElement.style.display = 'none';
        }
    }

    updateProgressDisplay() {
        const stageElement = document.getElementById('progress-stage');
        const fillElement = document.getElementById('progress-fill');
        const detailsElement = document.getElementById('progress-details');

        if (stageElement) {
            stageElement.textContent = this.analysisProgress.stage || 'Processing...';
        }

        if (fillElement) {
            fillElement.style.width = `${this.analysisProgress.percentage || 0}%`;
        }

        if (detailsElement) {
            detailsElement.textContent = this.analysisProgress.message || '';
        }
    }

    displayAnalysisResults() {
        if (!this.currentAnalysisResult) return;

        this.displayOperatorTimeline();
        this.displayProblemSummary();
        this.displayActionRecommendations();
    }

    displayOperatorTimeline() {
        const timelineElement = document.getElementById('operator-timeline');
        const timelineContent = document.getElementById('timeline-content');

        if (!timelineElement || !timelineContent || !this.currentAnalysisResult) return;

        // Extract timeline data - check for operator timeline first, fallback to regular timeline
        const operatorData = this.currentAnalysisResult.operator_timeline;
        const regularTimeline = this.currentAnalysisResult.timeline;
        const combinedChunks = this.currentAnalysisResult.combined_chunks;

        let scenes = [];

        if (operatorData && operatorData.scenes) {
            scenes = operatorData.scenes;
        } else {
            // Convert regular timeline to operator-friendly format
            scenes = this.convertToOperatorFormat(combinedChunks || regularTimeline || []);
        }

        if (scenes.length === 0) {
            timelineContent.innerHTML = '<div class="no-data">No timeline data available</div>';
            return;
        }

        timelineElement.style.display = 'block';

        // Create scene breakdown
        const scenesHtml = scenes.map(scene => {
            const severity = this.severityIndicators[scene.severity] || this.severityIndicators['NO_DATA'];
            const contentInfo = this.contentTypes[scene.scene_type?.toLowerCase()] || this.contentTypes['unknown'];

            return `
                <div class="scene-segment severity-${scene.severity.toLowerCase()}">
                    <div class="scene-time">${scene.time_range}</div>
                    <div class="scene-content">
                        <span class="content-icon">${contentInfo.icon}</span>
                        <span class="content-label">${contentInfo.label}</span>
                    </div>
                    <div class="scene-status">
                        <span class="status-icon">${severity.icon}</span>
                        <span class="status-label">${severity.label}</span>
                    </div>
                    <div class="scene-description">${scene.description || severity.description}</div>
                </div>
            `;
        }).join('');

        timelineContent.innerHTML = `
            <div class="scene-breakdown">
                <h4>🎬 Scene Breakdown</h4>
                <div class="scenes-list">${scenesHtml}</div>
            </div>
        `;
    }

    displayProblemSummary() {
        const summaryElement = document.getElementById('problem-summary');
        const summaryContent = document.getElementById('summary-content');

        if (!summaryElement || !summaryContent || !this.currentAnalysisResult) return;

        const operatorData = this.currentAnalysisResult.operator_timeline;

        if (!operatorData || !operatorData.scenes) {
            summaryElement.style.display = 'none';
            return;
        }

        const scenes = operatorData.scenes;

        // Count issues by severity
        const severityCounts = {
            'MAJOR_DRIFT': scenes.filter(s => s.severity === 'MAJOR_DRIFT').length,
            'SYNC_ISSUE': scenes.filter(s => s.severity === 'SYNC_ISSUE').length,
            'MINOR_DRIFT': scenes.filter(s => s.severity === 'MINOR_DRIFT').length,
            'IN_SYNC': scenes.filter(s => s.severity === 'IN_SYNC').length
        };

        const summaryHtml = `
            <div class="severity-summary">
                ${severityCounts['MAJOR_DRIFT'] > 0 ? `
                    <div class="severity-item critical">
                        <span class="severity-icon">🔴</span>
                        <span class="severity-count">${severityCounts['MAJOR_DRIFT']}</span>
                        <span class="severity-label">Critical Issue${severityCounts['MAJOR_DRIFT'] > 1 ? 's' : ''}</span>
                    </div>
                ` : ''}
                ${severityCounts['SYNC_ISSUE'] > 0 ? `
                    <div class="severity-item moderate">
                        <span class="severity-icon">🟠</span>
                        <span class="severity-count">${severityCounts['SYNC_ISSUE']}</span>
                        <span class="severity-label">Moderate Issue${severityCounts['SYNC_ISSUE'] > 1 ? 's' : ''}</span>
                    </div>
                ` : ''}
                ${severityCounts['MINOR_DRIFT'] > 0 ? `
                    <div class="severity-item minor">
                        <span class="severity-icon">🟡</span>
                        <span class="severity-count">${severityCounts['MINOR_DRIFT']}</span>
                        <span class="severity-label">Minor Issue${severityCounts['MINOR_DRIFT'] > 1 ? 's' : ''}</span>
                    </div>
                ` : ''}
                ${severityCounts['IN_SYNC'] > 0 ? `
                    <div class="severity-item good">
                        <span class="severity-icon">🟢</span>
                        <span class="severity-count">${severityCounts['IN_SYNC']}</span>
                        <span class="severity-label">Good Section${severityCounts['IN_SYNC'] > 1 ? 's' : ''}</span>
                    </div>
                ` : ''}
            </div>
        `;

        summaryContent.innerHTML = summaryHtml;
        summaryElement.style.display = 'block';
    }

    displayActionRecommendations() {
        const actionPanel = document.getElementById('action-panel');
        const actionsContent = document.getElementById('actions-content');

        if (!actionPanel || !actionsContent || !this.currentAnalysisResult) return;

        const operatorData = this.currentAnalysisResult.operator_timeline;

        if (!operatorData || !operatorData.scenes) {
            actionPanel.style.display = 'none';
            return;
        }

        const scenes = operatorData.scenes;

        // Group scenes by action priority
        const immediateActions = scenes.filter(s =>
            s.repair_recommendation && ['HIGH', 'MEDIUM-HIGH'].includes(s.repair_recommendation.priority)
        );

        const reviewRecommended = scenes.filter(s =>
            s.repair_recommendation && ['MEDIUM', 'LOW-MEDIUM'].includes(s.repair_recommendation.priority)
        );

        const monitorOnly = scenes.filter(s =>
            s.repair_recommendation && s.repair_recommendation.priority === 'LOW'
        );

        let actionsHtml = '';

        if (immediateActions.length > 0) {
            actionsHtml += `
                <div class="action-group immediate">
                    <h4>🚨 IMMEDIATE ACTION REQUIRED</h4>
                    ${immediateActions.map(scene => `
                        <div class="action-item">
                            <div class="action-scene">→ Scene ${scene.time_range}: ${scene.description}</div>
                            <div class="action-details">
                                <span class="action-type">Action: ${scene.repair_recommendation.action}</span>
                                <span class="action-priority">Priority: ${scene.repair_recommendation.priority}</span>
                            </div>
                            <div class="action-description">${scene.repair_recommendation.description}</div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        if (reviewRecommended.length > 0) {
            actionsHtml += `
                <div class="action-group review">
                    <h4>⚠️ REVIEW RECOMMENDED</h4>
                    ${reviewRecommended.map(scene => `
                        <div class="action-item">
                            <div class="action-scene">→ Scene ${scene.time_range}: ${scene.repair_recommendation.description}</div>
                            <div class="action-details">
                                <span class="action-type">Action: ${scene.repair_recommendation.action}</span>
                                <span class="action-priority">Priority: ${scene.repair_recommendation.priority}</span>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        if (monitorOnly.length > 0) {
            actionsHtml += `
                <div class="action-group monitor">
                    <h4>📝 MONITOR ONLY</h4>
                    ${monitorOnly.slice(0, 3).map(scene => `
                        <div class="action-item">
                            <div class="action-scene">→ Scene ${scene.time_range}: ${scene.repair_recommendation.description}</div>
                        </div>
                    `).join('')}
                    ${monitorOnly.length > 3 ? `<div class="more-items">... and ${monitorOnly.length - 3} more sections</div>` : ''}
                </div>
            `;
        }

        actionsContent.innerHTML = actionsHtml;
        actionPanel.style.display = 'block';
    }

    convertToOperatorFormat(timelineData) {
        // Convert regular timeline data to operator-friendly format
        if (!timelineData || !Array.isArray(timelineData)) return [];

        return timelineData.map((chunk, index) => {
            const offsetSeconds = chunk.offset_seconds || 0;
            const absOffset = Math.abs(offsetSeconds);
            const offsetMs = absOffset * 1000;

            // Classify severity
            let severity, description;
            if (absOffset <= 0.040) {
                severity = 'IN_SYNC';
                description = 'Perfect sync';
            } else if (absOffset <= 0.100) {
                severity = 'MINOR_DRIFT';
                description = `+${Math.round(offsetMs)}ms drift`;
            } else if (absOffset <= 1.000) {
                severity = 'SYNC_ISSUE';
                description = `+${Math.round(offsetMs)}ms drift`;
            } else {
                severity = 'MAJOR_DRIFT';
                description = `+${absOffset.toFixed(1)}s offset`;
            }

            // Determine scene type
            const contentType = chunk.master_content?.content_type || 'unknown';

            // Generate time range
            const startTime = chunk.start_time || (index * 30);
            const endTime = chunk.end_time || (startTime + 30);
            const timeRange = this.formatTimeRange(startTime, endTime);

            // Generate repair recommendation
            const repairRecommendation = this.generateRepairRecommendation(severity, contentType, offsetSeconds);

            return {
                time_range: timeRange,
                scene_type: contentType,
                severity: severity,
                description: description,
                repair_recommendation: repairRecommendation
            };
        });
    }

    formatTimeRange(startSeconds, endSeconds) {
        const formatTime = (seconds) => {
            const minutes = Math.floor(seconds / 60);
            const secs = Math.floor(seconds % 60);
            return `${minutes}:${secs.toString().padStart(2, '0')}`;
        };

        return `${formatTime(startSeconds)}-${formatTime(endSeconds)}`;
    }

    generateRepairRecommendation(severity, contentType, offsetSeconds) {
        let action, priority, description;

        if (severity === 'MAJOR_DRIFT') {
            if (Math.abs(offsetSeconds) > 2.0) {
                action = 'MANUAL REVIEW';
                priority = 'HIGH';
                description = 'Large drift requires manual adjustment';
            } else {
                action = 'AUTO-REPAIR';
                priority = 'HIGH';
                description = 'Simple offset correction available';
            }
        } else if (severity === 'SYNC_ISSUE') {
            if (contentType === 'dialogue') {
                action = 'AUTO-REPAIR';
                priority = 'MEDIUM-HIGH';
                description = 'Critical for lip sync accuracy';
            } else {
                action = 'MANUAL REVIEW';
                priority = 'MEDIUM';
                description = 'Correction recommended';
            }
        } else if (severity === 'MINOR_DRIFT') {
            action = 'MONITOR ONLY';
            priority = 'LOW';
            description = 'Within acceptable limits';
        } else {
            action = 'NO ACTION';
            priority = 'NONE';
            description = 'Good sync quality';
        }

        return { action, priority, description };
    }

    toggleTimelineView() {
        // This will be implemented to switch between operator and technical views
        const toggleButton = document.getElementById('timeline-view-toggle');
        if (toggleButton) {
            const isTechnical = toggleButton.textContent === 'Technical View';
            toggleButton.textContent = isTechnical ? 'Operator View' : 'Technical View';

            // Dispatch event to update the display
            document.dispatchEvent(new CustomEvent('timelineViewChanged', {
                detail: { viewMode: isTechnical ? 'technical' : 'operator' }
            }));
        }
    }

    hideAnalysisResults() {
        const elements = ['operator-timeline', 'problem-summary', 'action-panel'];
        elements.forEach(id => {
            const element = document.getElementById(id);
            if (element) {
                element.style.display = 'none';
            }
        });
    }
}

// Initialize the operator console when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.operatorConsole = new OperatorConsole();
});