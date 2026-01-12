class SyncAnalyzerUI {
    constructor() {
        // Use relative URL since UI is served from the same FastAPI server
        // This avoids CORS issues and protocol/port mismatches
        this.FASTAPI_BASE = '/api/v1';
        this.currentPath = '/mnt/data';
        this.selectedMaster = null;
        this.selectedDub = null;
        this.autoScroll = true;
        this.analysisInProgress = false;
        this.batchQueue = [];
        this.batchProcessing = false;
        this.currentBatchIndex = -1;
        this.detectedFrameRate = 23.976; // Default frame rate (industry standard)
        
        // Unique client ID for tracking which browser made updates
        this.clientId = localStorage.getItem('sync-analyzer-client-id') || this.generateClientId();
        localStorage.setItem('sync-analyzer-client-id', this.clientId);
        
        // Start periodic sync for cross-browser updates (every 10 seconds)
        this.startPeriodicSync();
        
        // Track last seen job timestamp for polling new API jobs
        this.lastJobPollTime = new Date().toISOString();
        
        // Parallel processing configuration
        this.maxConcurrentJobs = 1; // Number of jobs to process in parallel (start with 1 to avoid memory issues)
        this.activeJobs = new Map(); // Track currently running jobs by item ID

        // Componentized analysis mode state
        this.analysisMode = 'standard';  // 'standard' | 'componentized'
        this.selectedComponents = [];     // Array of {name, path, type, label}
        this.componentizedMaster = null;  // Master file for componentized mode
        this.componentSelectionMode = false; // Whether file browser is in multi-select mode
        this.componentizedOffsetMode = 'channel_aware';

        // Initialize Operator Console
        this.operatorConsole = null;

        this.initializeElements();
        this.initComponentizedOffsetMode();
        this.initBrowserTabs();
        this.initDefaultMethods();
        this.bindEvents();
        this.loadFileTree();

        // Load saved batch queue from localStorage
        this.loadBatchQueue();
        this.updateBatchSummary();

        // Initialize Operator Console after elements are set up
        this.initOperatorConsole();
        
        // Initialize the enhanced waveform visualizer
        this.waveformVisualizer = new WaveformVisualizer();
        // Instance-level override to guarantee play uses CoreAudioEngine even if prototype override is bypassed
        try {
            const viz = this.waveformVisualizer;
            if (!viz.audioEngine) {
                viz.audioEngine = new CoreAudioEngine();
                console.log('CoreAudioEngine initialized for WaveformVisualizer');
                if (typeof viz.setupAudioEngineCallbacks === 'function') viz.setupAudioEngineCallbacks();
            }
            // Respect enhanced implementation if present; otherwise fall back to direct engine call
            viz.playAudioComparison = async (masterId, dubId, offsetSeconds, forceAfter) => {
                const proto = Object.getPrototypeOf(viz);
                const protoPlay = proto && typeof proto.playAudioComparison === 'function' ? proto.playAudioComparison : null;
                if (protoPlay && protoPlay !== viz.playAudioComparison) {
                    return protoPlay.call(viz, masterId, dubId, offsetSeconds, forceAfter);
                }
                try { await viz.audioEngine?.audioContext?.resume?.(); } catch {}
                window.showToast?.('info', 'Playing comparison…', 'Audio');
                viz.audioEngine.playComparison(offsetSeconds || 0, !!forceAfter);
            };
            // Ensure the action handler on this instance routes play to the override
            const origHandle = viz.handleWaveformAction?.bind(viz);
            viz.handleWaveformAction = function(action, container, masterId, dubId, offsetSeconds) {
                if (action === 'play-comparison') return viz.playAudioComparison(masterId, dubId, offsetSeconds || 0);
                if (action === 'play-before') return viz.playAudioComparison(masterId, dubId, offsetSeconds || 0, false);
                if (action === 'play-after') return viz.playAudioComparison(masterId, dubId, offsetSeconds || 0, true);
                return origHandle ? origHandle(action, container, masterId, dubId, offsetSeconds) : undefined;
            };
        } catch (e) {
            console.warn('WaveformVisualizer instance patch failed:', e);
        }

        // Add audio file loading capability
        this.setupAudioFileLoading();

        // Ensure global slider listeners affect current engine even if per-instance handlers miss
        this.setupGlobalAudioControls();

        // Aggressively unlock AudioContext on first user gesture in Chrome
        this.setupAudioUnlockers();

        // Intercept waveform play buttons globally to ensure reliable playback
        this.setupGlobalPlayHandlers();
        
        // Initialize batch queue from server persistence
        this.initBatchQueue();
        
        // Add global audio debug helper
        window.debugAudio = () => {
            const engine = this.waveformVisualizer?.audioEngine;
            if (engine && typeof engine.getStatus === 'function') {
                console.log('Audio Engine Status:', engine.getStatus());
            } else {
                console.log('Audio Engine not available');
            }
        };
        
        // Helper to adjust dub volume (0-2, where 1.2 is default, 2 is max boost)
        window.setDubVolume = (vol) => {
            const engine = this.waveformVisualizer?.audioEngine;
            if (engine) {
                engine.setVolume('dub', vol);
                console.log(`Dub volume set to ${vol} (0-2 range, 1.2 is default)`);
            } else {
                console.log('Audio Engine not available');
            }
        };
        
        // Helper to adjust master volume (0-1)
        window.setMasterVolume = (vol) => {
            const engine = this.waveformVisualizer?.audioEngine;
            if (engine) {
                engine.setVolume('master', vol);
                console.log(`Master volume set to ${vol} (0-1 range, 0.8 is default)`);
            } else {
                console.log('Audio Engine not available');
            }
        };

        // Add QC debug helper
        window.debugQC = () => {
            if (this.qcInterface && typeof this.qcInterface.getDebugInfo === 'function') {
                console.log('QC Interface Debug Info:', this.qcInterface.getDebugInfo());
            } else {
                console.log('QC Interface not available');
            }
        };

        // Initialize QC Interface
        this.initializeQCInterface();
        // Initialize Repair QC Interface
        this.initializeRepairQCInterface();

        // Test log to verify console is working
        setTimeout(() => {
            this.addLog('info', 'Sync Analyzer UI ready');
        }, 500);
    }

    setupGlobalAudioControls() {
        const engine = () => this.waveformVisualizer && this.waveformVisualizer.audioEngine;
        // Delegate for volume sliders
        document.addEventListener('input', (e) => {
            const t = e.target;
            if (!(t instanceof HTMLElement)) return;
            if (t.classList.contains('volume-slider')) {
                const track = t.dataset.track;
                const val = parseFloat(t.value);
                console.log(`Setting ${track} volume to ${val}`);
                try { 
                    const audioEngine = engine();
                    if (audioEngine && typeof audioEngine.setVolume === 'function') {
                        audioEngine.setVolume(track, val);
                    } else {
                        console.warn('AudioEngine or setVolume method not available');
                    }
                } catch (err) {
                    console.error('Error setting volume:', err);
                }
            } else if (t.classList.contains('master-output-slider')) {
                const val = parseFloat(t.value);
                console.log(`Setting master output volume to ${val}`);
                try { engine()?.setMasterOutputVolume?.(val); } catch {}
            } else if (t.classList.contains('balance-slider')) {
                const val = parseFloat(t.value);
                console.log(`Setting balance to ${val}`);
                try { engine()?.setBalance?.(val); } catch {}
            } else if (t.classList.contains('pan-slider')) {
                const track = t.dataset.track;
                const val = parseFloat(t.value);
                console.log(`Setting ${track} pan to ${val}`);
                try { engine()?.setPan?.(track, val); } catch {}
            }
        });
        document.addEventListener('change', (e) => {
            const t = e.target;
            if (!(t instanceof HTMLElement)) return;
            if (t.classList.contains('mute-toggle')) {
                const track = t.dataset.track;
                const on = !!t.checked;
                try { engine()?.setMute?.(track, on); } catch {}
            }
        });
    }

    setupAudioUnlockers() {
        const tryResume = async () => {
            try {
                const eng = this.waveformVisualizer?.audioEngine;
                if (eng?.audioContext && eng.audioContext.state === 'suspended') {
                    await eng.audioContext.resume();
                    console.log('🔊 AudioContext resumed via user gesture');
                }
            } catch {}
        };
        const once = (ev) => {
            window.removeEventListener('pointerdown', once, true);
            window.removeEventListener('keydown', once, true);
            window.removeEventListener('touchstart', once, true);
            tryResume();
        };
        window.addEventListener('pointerdown', once, true);
        window.addEventListener('keydown', once, true);
        window.addEventListener('touchstart', once, true);
    }

    setupGlobalPlayHandlers() {
        document.addEventListener('click', async (e) => {
            const btn = e.target.closest && e.target.closest('.waveform-btn');
            if (!btn) return;
            const action = btn.dataset.action;
            if (!action || !/^play-(before|after|comparison)$/.test(action)) return;
            e.preventDefault();
            e.stopPropagation();
            const container = btn.closest('.sync-waveform-container');
            if (!container) return;
            // Derive masterId/dubId from data-waveform-id
            const uni = container.querySelector('[data-waveform-id]');
            if (!uni) return;
            const id = uni.getAttribute('data-waveform-id');
            // format unified-master-<id>-dub-<id> or unified-<masterId>-<dubId>
            const m = id.match(/^unified-(.+)-(.+)$/);
            if (!m) return;
            const masterId = m[1];
            const dubId = m[2];
            // Get offsetSeconds from stored data if possible
            let offsetSeconds = 0;
            try {
                const key = `unified-timeline-${masterId}-${dubId}`;
                const wf = this.waveformVisualizer?.audioData?.get(key);
                if (wf && typeof wf.offsetSeconds === 'number') offsetSeconds = wf.offsetSeconds;
            } catch {}
            const isAfter = action === 'play-after' ? true : (action === 'play-before' ? false : undefined);
            try {
                await this.waveformVisualizer?.playAudioComparison?.(masterId, dubId, offsetSeconds, isAfter);
            } catch (err) {
                console.warn('Global play handler failed:', err);
            }
        }, true); // capture to preempt default handlers
    }
    
    initializeElements() {
        this.elements = {
            fileTree: document.getElementById('file-tree'),
            currentPath: document.getElementById('current-path'),
            masterSlot: document.getElementById('master-slot'),
            dubSlot: document.getElementById('dub-slot'),
            analyzeBtn: document.getElementById('analyze-btn'),
            statusDot: document.getElementById('status-dot'),
            statusText: document.getElementById('status-text'),
            // File search elements
            fileSearchInput: document.getElementById('file-search-input'),
            searchClearBtn: document.getElementById('search-clear-btn'),
            searchResultsCount: document.getElementById('search-results-count'),
            searchCountText: document.getElementById('search-count-text'),
            // Configuration elements
            resetConfigBtn: document.getElementById('reset-config-btn'),
            methodMfcc: document.getElementById('method-mfcc'),
            methodOnset: document.getElementById('method-onset'),
            methodSpectral: document.getElementById('method-spectral'),
            methodAi: document.getElementById('method-ai'),
            methodGpu: document.getElementById('method-gpu'),
            methodFingerprint: document.getElementById('method-fingerprint'),
            sampleRate: document.getElementById('sample-rate'),
            windowSize: document.getElementById('window-size'),
            confidenceThreshold: document.getElementById('confidence-threshold'),
            confidenceValue: document.getElementById('confidence-value'),
            nMfcc: document.getElementById('n-mfcc'),
            generateJson: document.getElementById('generate-json'),
            generateVisualizations: document.getElementById('generate-visualizations'),
            enableGpu: document.getElementById('enable-gpu'),
            verboseLogging: document.getElementById('verbose-logging'),
            enableDriftDetection: document.getElementById('enable-drift-detection'),
            outputDirectory: document.getElementById('output-directory'),
            channelStrategy: document.getElementById('channel-strategy'),
            targetChannels: document.getElementById('target-channels'),
            aiConfig: document.getElementById('ai-config'),
            // Batch processing elements
            addToBatch: document.getElementById('add-to-batch'),
            uploadCsvBatch: document.getElementById('upload-csv-batch'),
            csvFileInput: document.getElementById('csv-file-input'),
            importCsvBtn: document.getElementById('import-csv-btn'),
            concurrentJobs: document.getElementById('concurrent-jobs'),
            jobsDropdownBtn: document.getElementById('jobs-dropdown-btn'),
            jobsDropdownMenu: document.getElementById('jobs-dropdown-menu'),
            jobsLabel: document.getElementById('jobs-label'),
            processBatch: document.getElementById('process-batch'),
            refreshBatchStatus: document.getElementById('refresh-batch-status'),
            repairAllBatch: document.getElementById('repair-all-batch'),
            exportDropdownBtn: document.getElementById('export-dropdown-btn'),
            exportDropdownMenu: document.getElementById('export-dropdown-menu'),
            exportBatch: document.getElementById('export-batch'),
            exportHtmlReport: document.getElementById('export-html-report'),
            exportJson: document.getElementById('export-json'),
            exportTableView: document.getElementById('export-table-view'),
            exportWaveformView: document.getElementById('export-waveform-view'),
            clearBatch: document.getElementById('clear-batch'),
            toggleBatchFullscreen: document.getElementById('toggle-batch-fullscreen'),
            queueCount: document.getElementById('queue-count'),
            completedCount: document.getElementById('completed-count'),
            processingStatus: document.getElementById('processing-status'),
            batchTableBody: document.getElementById('batch-table-body'),
            batchDetails: document.getElementById('batch-details'),
            closeDetails: document.getElementById('close-details'),
            detailsContent: document.getElementById('details-content'),
            detailsSubtitle: document.getElementById('details-subtitle'),
            // Active jobs display elements
            activeJobsContainer: document.getElementById('active-jobs-container'),
            activeJobsList: document.getElementById('active-jobs-list'),
            activeJobsCount: document.getElementById('active-jobs-count'),
            detailsLoading: document.getElementById('details-loading'),
            exportResultsBtn: document.getElementById('export-results-btn'),
            compareResultsBtn: document.getElementById('compare-results-btn'),
            batchSplitter: document.getElementById('batch-splitter'),
            // Componentized mode elements
            modeTabs: document.querySelectorAll('.mode-tab'),
            standardModeUi: document.getElementById('standard-mode-ui'),
            componentizedModeUi: document.getElementById('componentized-mode-ui'),
            compMasterSlot: document.getElementById('comp-master-slot'),
            componentFilesList: document.getElementById('component-files-list'),
            componentCount: document.getElementById('component-count'),
            selectComponentsBtn: document.getElementById('select-components-btn'),
            analyzeComponentizedBtn: document.getElementById('analyze-componentized-btn'),
            componentizedOffsetRadios: document.querySelectorAll('input[name="componentized-offset-mode"]'),
            // Maintenance elements
            maintClearJobs: document.getElementById('maint-clear-jobs'),
            maintClearWaveforms: document.getElementById('maint-clear-waveforms'),
            maintRestartCelery: document.getElementById('maint-restart-celery'),
            maintFlushRedis: document.getElementById('maint-flush-redis'),
            maintHealthCheck: document.getElementById('maint-health-check'),
            maintFactoryReset: document.getElementById('maint-factory-reset'),
            maintenanceStatus: document.getElementById('maintenance-status'),
            // Verbose logging toggle
            verboseLogging: document.getElementById('verbose-logging'),
            // Log viewer elements
            logLevelFilter: document.getElementById('log-level-filter'),
            toggleLogViewer: document.getElementById('toggle-log-viewer'),
            refreshLogs: document.getElementById('refresh-logs'),
            clearLogViewer: document.getElementById('clear-log-viewer'),
            celeryLogViewer: document.getElementById('celery-log-viewer'),
            logViewerStatus: document.getElementById('log-viewer-status'),
            logAutoScroll: document.getElementById('log-auto-scroll'),
            logLineCount: document.getElementById('log-line-count'),
            logViewerContent: document.getElementById('log-viewer-content')
        };
        // Console status UI (optional)
        this.elements.logContainer = document.getElementById('log-container');
        this.elements.clearLogsBtn = document.getElementById('clear-logs-btn');
        this.elements.autoScrollBtn = document.getElementById('auto-scroll-btn');

        // Debug: Verify log container exists
        if (!this.elements.logContainer) {
            console.error('CRITICAL: #log-container element not found in DOM!');
            console.error('Available elements in body:', document.body.innerHTML.substring(0, 500));
            console.error('All elements with class log-container:', document.querySelectorAll('.log-container'));
            console.error('All elements with id containing log:', Array.from(document.querySelectorAll('[id*="log"]')).map(el => el.id));
        } else {
            console.log('✓ Log container initialized successfully');
        }

            // Toast container
            this.toastContainer = document.getElementById('toast-container');
            // Operator mode toggle (optional)
            this.elements.operatorMode = document.getElementById('operator-mode');
            // Browser tabs (Files/Config)
            this.elements.browserTabs = document.querySelectorAll('.browser-tab');
            this.elements.browserPanels = document.querySelectorAll('.browser-panel');
            this.elements.pathBreadcrumb = document.getElementById('path-breadcrumb-container');
    }
    
    /**
     * Initialize browser tabs (Files/Config toggle in left panel)
     */
    initBrowserTabs() {
        if (!this.elements.browserTabs) return;
        
        this.elements.browserTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetPanel = tab.dataset.panel;
                
                // Update tab states
                this.elements.browserTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                
                // Update panel visibility
                this.elements.browserPanels.forEach(panel => {
                    if (panel.id === targetPanel) {
                        panel.classList.add('active');
                        panel.style.display = 'flex';
                    } else {
                        panel.classList.remove('active');
                        panel.style.display = 'none';
                    }
                });
                
                // Show/hide path breadcrumb based on active panel
                if (this.elements.pathBreadcrumb) {
                    this.elements.pathBreadcrumb.style.display = targetPanel === 'files-panel' ? 'block' : 'none';
                }
            });
        });
    }
    
    /**
     * Initialize default detection methods (GPU by default)
     */
    initDefaultMethods() {
        // Ensure GPU is selected by default
        if (this.elements.methodGpu) {
            this.elements.methodGpu.checked = true;
            // Uncheck other methods since GPU is exclusive
            if (this.elements.methodMfcc) this.elements.methodMfcc.checked = false;
            if (this.elements.methodOnset) this.elements.methodOnset.checked = false;
            if (this.elements.methodSpectral) this.elements.methodSpectral.checked = false;
            if (this.elements.methodAi) this.elements.methodAi.checked = false;
            if (this.elements.methodFingerprint) this.elements.methodFingerprint.checked = false;
        }
        
        // Initialize the currentMethods array
        this.currentMethods = ['gpu'];
        this.addLog('info', '🚀 GPU Fast mode enabled by default');
    }

    initComponentizedOffsetMode() {
        let stored = null;
        try {
            stored = localStorage.getItem('componentized-offset-mode');
        } catch (e) {
            stored = null;
        }
        this.componentizedOffsetMode = stored || this.componentizedOffsetMode || 'channel_aware';
        if (this.elements && this.elements.componentizedOffsetRadios) {
            this.elements.componentizedOffsetRadios.forEach(radio => {
                radio.checked = radio.value === this.componentizedOffsetMode;
            });
        }
    }
    
    bindEvents() {
        this.elements.analyzeBtn.addEventListener('click', () => this.startAnalysis());
        // Logs UI controls if present
        if (this.elements.clearLogsBtn) this.elements.clearLogsBtn.addEventListener('click', () => this.clearLogs());
        if (this.elements.autoScrollBtn) this.elements.autoScrollBtn.addEventListener('click', () => this.toggleAutoScroll());

        // File search events
        if (this.elements.fileSearchInput) {
            this.elements.fileSearchInput.addEventListener('input', (e) => this.handleFileSearch(e.target.value));
            this.elements.fileSearchInput.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    this.clearFileSearch();
                }
            });
        }
        if (this.elements.searchClearBtn) {
            this.elements.searchClearBtn.addEventListener('click', () => this.clearFileSearch());
        }

        // File slot click events
        this.elements.masterSlot.addEventListener('click', () => this.openFileSelector('master'));
        this.elements.dubSlot.addEventListener('click', () => this.openFileSelector('dub'));

        // Mode switching events
        this.elements.modeTabs.forEach(tab => {
            tab.addEventListener('click', () => this.switchAnalysisMode(tab.dataset.mode));
        });

        // Componentized mode events
        if (this.elements.compMasterSlot) {
            this.elements.compMasterSlot.addEventListener('click', () => this.openFileSelector('comp-master'));
        }
        if (this.elements.selectComponentsBtn) {
            this.elements.selectComponentsBtn.addEventListener('click', () => this.enableComponentSelection());
        }
        if (this.elements.analyzeComponentizedBtn) {
            this.elements.analyzeComponentizedBtn.addEventListener('click', () => this.startComponentizedAnalysis());
        }
        if (this.elements.componentizedOffsetRadios) {
            console.log('[bindEvents] Found', this.elements.componentizedOffsetRadios.length, 'componentized offset radios');
            this.elements.componentizedOffsetRadios.forEach(radio => {
                radio.addEventListener('change', () => {
                    console.log('[Radio Change] radio.value:', radio.value, 'radio.checked:', radio.checked);
                    if (!radio.checked) return;
                    this.componentizedOffsetMode = radio.value || 'channel_aware';
                    console.log('[Radio Change] Set componentizedOffsetMode to:', this.componentizedOffsetMode);
                    try {
                        localStorage.setItem('componentized-offset-mode', this.componentizedOffsetMode);
                    } catch (e) {
                        console.warn('Failed to persist componentized offset mode:', e);
                    }
                    this.addLog('info', `Componentized offset mode: ${this.componentizedOffsetMode.toUpperCase()}`);
                    // Update detection methods section based on mode
                    this.updateDetectionMethodsState();
                });
            });
            // Set initial state on load
            console.log('[bindEvents] Initial componentizedOffsetMode:', this.componentizedOffsetMode);
            this.updateDetectionMethodsState();
        }

        // Configuration events
        this.elements.resetConfigBtn.addEventListener('click', () => this.resetConfiguration());
        if (this.elements.methodAi) {
            this.elements.methodAi.addEventListener('change', () => this.toggleAiConfig());
        }
        this.elements.confidenceThreshold.addEventListener('input', () => this.updateConfidenceValue());
        
        // View selector tabs for Quadrant 2
        this.setupViewSelector();
        this.setupBatchSplitter();
        
        // Configuration method selection events
        [this.elements.methodMfcc, this.elements.methodOnset, this.elements.methodSpectral, this.elements.methodAi, this.elements.methodGpu, this.elements.methodFingerprint].filter(cb => cb).forEach(checkbox => {
            checkbox.addEventListener('change', () => {
                this.updateMethodSelection();
                // Add visual feedback for toggle switches
                this.updateToggleVisualFeedback(checkbox);
            });
        });
        
        // Batch processing events
        this.elements.addToBatch.addEventListener('click', () => this.addToBatchQueue());
        this.elements.uploadCsvBatch.addEventListener('click', () => this.elements.csvFileInput.click());
        this.elements.csvFileInput.addEventListener('change', (e) => this.handleCsvUpload(e));
        
        // New Import CSV button (server-side validation)
        if (this.elements.importCsvBtn) {
            this.elements.importCsvBtn.addEventListener('click', () => this.elements.csvFileInput.click());
        }
        
        // Jobs dropdown (custom dropdown style)
        if (this.elements.jobsDropdownBtn) {
            this.elements.jobsDropdownBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleJobsDropdown();
            });
        }
        if (this.elements.jobsDropdownMenu) {
            this.elements.jobsDropdownMenu.querySelectorAll('.dropdown-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    const value = parseInt(item.dataset.value, 10);
                    this.setJobsLimit(value);
                    this.closeJobsDropdown();
                });
            });
        }
        
        this.elements.processBatch.addEventListener('click', () => this.processBatchQueue());
        if (this.elements.refreshBatchStatus) {
            this.elements.refreshBatchStatus.addEventListener('click', () => this.refreshStaleJobs());
        }
        this.elements.repairAllBatch.addEventListener('click', () => this.repairAllCompleted());
        // Export dropdown
        if (this.elements.exportDropdownBtn) {
            this.elements.exportDropdownBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleExportDropdown();
            });
        }
        if (this.elements.exportBatch) {
            this.elements.exportBatch.addEventListener('click', () => {
                this.closeExportDropdown();
                this.exportBatchReport();
            });
        }
        if (this.elements.exportHtmlReport) {
            this.elements.exportHtmlReport.addEventListener('click', () => {
                this.closeExportDropdown();
                this.exportHtmlReport();
            });
        }
        if (this.elements.exportJson) {
            this.elements.exportJson.addEventListener('click', () => {
                this.closeExportDropdown();
                this.exportJsonReport();
            });
        }
        if (this.elements.exportTableView) {
            this.elements.exportTableView.addEventListener('click', () => {
                this.closeExportDropdown();
                this.exportTableViewReport();
            });
        }
        if (this.elements.exportWaveformView) {
            this.elements.exportWaveformView.addEventListener('click', () => {
                this.closeExportDropdown();
                this.exportWaveformViewReport();
            });
        }
        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.export-dropdown')) {
                this.closeExportDropdown();
            }
            if (!e.target.closest('.jobs-dropdown')) {
                this.closeJobsDropdown();
            }
        });
        this.elements.clearBatch.addEventListener('click', () => this.clearBatchQueue());
        this.elements.closeDetails.addEventListener('click', () => this.closeBatchDetails());
        if (this.elements.toggleBatchFullscreen) {
            this.elements.toggleBatchFullscreen.addEventListener('click', () => this.toggleBatchFullscreen());
        }
        
        // Enhanced details events
        this.elements.exportResultsBtn.addEventListener('click', () => this.exportResults());
        this.elements.compareResultsBtn.addEventListener('click', () => this.compareResults());
        // Operator mode toggle
        if (this.elements.operatorMode) {
            this.elements.operatorMode.addEventListener('change', () => this.setOperatorMode());
        }

        // New redesigned action button handlers (event delegation)
        this.setupActionButtonHandlers();

        // Maintenance button handlers
        this.setupMaintenanceHandlers();

        // Log viewer handlers
        this.setupLogViewerHandlers();

        // Initialize configuration
        this.initializeConfiguration();
    }

    /**
     * Setup maintenance button handlers
     */
    setupMaintenanceHandlers() {
        if (this.elements.maintClearJobs) {
            this.elements.maintClearJobs.addEventListener('click', () => this.runMaintenance('clear-jobs', 'Clearing all jobs...'));
        }
        if (this.elements.maintClearWaveforms) {
            this.elements.maintClearWaveforms.addEventListener('click', () => this.runMaintenance('clear-waveforms', 'Clearing waveform cache...'));
        }
        if (this.elements.maintRestartCelery) {
            this.elements.maintRestartCelery.addEventListener('click', () => this.runMaintenance('restart-celery', 'Restarting Celery worker...'));
        }
        if (this.elements.maintFlushRedis) {
            this.elements.maintFlushRedis.addEventListener('click', () => this.runMaintenance('flush-redis', 'Flushing Redis cache...'));
        }
        if (this.elements.maintHealthCheck) {
            this.elements.maintHealthCheck.addEventListener('click', () => this.runHealthCheck());
        }
        if (this.elements.maintFactoryReset) {
            this.elements.maintFactoryReset.addEventListener('click', () => this.runFactoryReset());
        }
    }

    /**
     * Setup log viewer handlers
     */
    setupLogViewerHandlers() {
        // Toggle log viewer visibility
        if (this.elements.toggleLogViewer) {
            this.elements.toggleLogViewer.addEventListener('click', () => this.toggleLogViewer());
        }
        
        // Refresh logs
        if (this.elements.refreshLogs) {
            this.elements.refreshLogs.addEventListener('click', () => this.fetchCeleryLogs());
        }
        
        // Clear log viewer
        if (this.elements.clearLogViewer) {
            this.elements.clearLogViewer.addEventListener('click', () => this.clearLogViewer());
        }
        
        // Log level filter change
        if (this.elements.logLevelFilter) {
            this.elements.logLevelFilter.addEventListener('change', () => this.fetchCeleryLogs());
        }
        
        // Log viewer state
        this.logViewerVisible = false;
        this.logPollingInterval = null;
        this.logAutoScrollEnabled = true;
        
        // Auto-scroll checkbox
        if (this.elements.logAutoScroll) {
            this.elements.logAutoScroll.addEventListener('change', (e) => {
                this.logAutoScrollEnabled = e.target.checked;
            });
        }
    }

    /**
     * Toggle log viewer visibility
     */
    toggleLogViewer() {
        this.logViewerVisible = !this.logViewerVisible;
        
        if (this.elements.celeryLogViewer) {
            this.elements.celeryLogViewer.style.display = this.logViewerVisible ? 'block' : 'none';
        }
        
        if (this.elements.toggleLogViewer) {
            this.elements.toggleLogViewer.classList.toggle('active', this.logViewerVisible);
        }
        
        if (this.logViewerVisible) {
            // Fetch initial logs
            this.fetchCeleryLogs();
            // Start polling for new logs
            this.startLogPolling();
        } else {
            // Stop polling
            this.stopLogPolling();
        }
    }

    /**
     * Fetch Celery logs from API
     */
    async fetchCeleryLogs() {
        try {
            const level = this.elements.logLevelFilter?.value || '';
            const response = await fetch(`${this.FASTAPI_BASE}/logs/tail?lines=100&level=${level}`);
            const data = await response.json();
            
            if (data.entries) {
                this.renderLogEntries(data.entries);
                this.updateLogStatus('live', `${data.entries.length} lines`);
            }
        } catch (error) {
            console.error('Failed to fetch logs:', error);
            this.updateLogStatus('error', 'Failed to fetch logs');
        }
    }

    /**
     * Start polling for new logs
     */
    startLogPolling() {
        if (this.logPollingInterval) {
            clearInterval(this.logPollingInterval);
        }
        
        this.logPollingInterval = setInterval(async () => {
            try {
                const level = this.elements.logLevelFilter?.value || '';
                const response = await fetch(`${this.FASTAPI_BASE}/logs/poll?level=${level}`);
                const data = await response.json();
                
                if (data.entries && data.entries.length > 0) {
                    this.appendLogEntries(data.entries);
                }
            } catch (error) {
                // Silent fail for polling
            }
        }, 2000); // Poll every 2 seconds
        
        this.updateLogStatus('live', 'Polling...');
    }

    /**
     * Stop polling for logs
     */
    stopLogPolling() {
        if (this.logPollingInterval) {
            clearInterval(this.logPollingInterval);
            this.logPollingInterval = null;
        }
        this.updateLogStatus('paused', 'Paused');
    }

    /**
     * Render log entries in the viewer
     */
    renderLogEntries(entries) {
        if (!this.elements.logViewerContent) return;
        
        if (entries.length === 0) {
            this.elements.logViewerContent.innerHTML = '<div class="log-empty-state">No log entries found</div>';
            return;
        }
        
        const html = entries.map(entry => this.formatLogEntry(entry)).join('');
        this.elements.logViewerContent.innerHTML = html;
        
        if (this.logAutoScrollEnabled) {
            this.elements.logViewerContent.scrollTop = this.elements.logViewerContent.scrollHeight;
        }
        
        this.updateLineCount(entries.length);
    }

    /**
     * Append new log entries
     */
    appendLogEntries(entries) {
        if (!this.elements.logViewerContent || entries.length === 0) return;
        
        // Remove empty state if present
        const emptyState = this.elements.logViewerContent.querySelector('.log-empty-state');
        if (emptyState) {
            emptyState.remove();
        }
        
        const html = entries.map(entry => this.formatLogEntry(entry)).join('');
        this.elements.logViewerContent.insertAdjacentHTML('beforeend', html);
        
        if (this.logAutoScrollEnabled) {
            this.elements.logViewerContent.scrollTop = this.elements.logViewerContent.scrollHeight;
        }
        
        // Update line count
        const currentCount = this.elements.logViewerContent.querySelectorAll('.log-entry').length;
        this.updateLineCount(currentCount);
    }

    /**
     * Format a single log entry
     */
    formatLogEntry(entry) {
        const time = entry.timestamp ? entry.timestamp.split(',')[0].split(' ')[1] || '' : '';
        const level = entry.level || 'INFO';
        const process = entry.process || '';
        let message = entry.message || entry.raw || '';
        
        // Highlight certain patterns in the message
        message = message
            .replace(/offset[=:]\s*([\d.+-]+s?)/gi, '<span class="highlight-offset">$&</span>')
            .replace(/(error|failed|exception)/gi, '<span class="highlight-error">$&</span>')
            .replace(/(task\s+[\w-]+)/gi, '<span class="highlight-task">$&</span>');
        
        return `
            <div class="log-entry">
                <span class="log-time">${time}</span>
                <span class="log-level ${level}">${level}</span>
                ${process ? `<span class="log-process">[${process}]</span>` : ''}
                <span class="log-message">${message}</span>
            </div>
        `;
    }

    /**
     * Update log status indicator
     */
    updateLogStatus(status, text) {
        if (this.elements.logViewerStatus) {
            this.elements.logViewerStatus.textContent = text;
            this.elements.logViewerStatus.className = 'log-status ' + (status === 'live' ? 'live' : '');
        }
    }

    /**
     * Update line count display
     */
    updateLineCount(count) {
        if (this.elements.logLineCount) {
            this.elements.logLineCount.textContent = `${count} lines`;
        }
    }

    /**
     * Clear log viewer
     */
    clearLogViewer() {
        if (this.elements.logViewerContent) {
            this.elements.logViewerContent.innerHTML = '<div class="log-empty-state">Logs cleared. Click refresh to reload.</div>';
        }
        this.updateLineCount(0);
        
        // Also clear the server-side buffer
        fetch(`${this.FASTAPI_BASE}/logs/clear-buffer`, { method: 'POST' }).catch(() => {});
    }

    /**
     * Run a maintenance command
     */
    async runMaintenance(action, statusMessage) {
        const btn = document.getElementById(`maint-${action.replace('/', '-')}`);
        const statusEl = this.elements.maintenanceStatus;
        
        if (btn) {
            btn.disabled = true;
            btn.classList.add('loading');
            const icon = btn.querySelector('i');
            const origClass = icon?.className;
            if (icon) icon.className = 'fas fa-spinner';
        }
        
        this.showMaintenanceStatus('info', statusMessage);
        
        try {
            const response = await fetch(`${this.FASTAPI_BASE}/maintenance/${action}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showMaintenanceStatus('success', `✓ ${result.message}`);
                this.addLog('success', `Maintenance: ${result.message}`);
                
                // If jobs were cleared, also clear local state
                if (action === 'clear-jobs' || action === 'flush-redis' || action === 'factory-reset') {
                    this.batchQueue = [];
                    this.renderBatchTable();
                    this.updateBatchSummary();
                    localStorage.removeItem('batchQueue');
                }
            } else {
                this.showMaintenanceStatus('error', `✗ ${result.message || 'Operation failed'}`);
                this.addLog('error', `Maintenance failed: ${result.message}`);
            }
        } catch (error) {
            this.showMaintenanceStatus('error', `✗ Error: ${error.message}`);
            this.addLog('error', `Maintenance error: ${error.message}`);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.classList.remove('loading');
                const icon = btn.querySelector('i');
                // Restore original icon based on action
                const iconMap = {
                    'clear-jobs': 'fa-trash-alt',
                    'clear-waveforms': 'fa-wave-square',
                    'restart-celery': 'fa-sync',
                    'flush-redis': 'fa-database',
                    'health': 'fa-heartbeat',
                    'factory-reset': 'fa-exclamation-triangle'
                };
                if (icon) icon.className = `fas ${iconMap[action] || 'fa-cog'}`;
            }
        }
    }

    /**
     * Run health check
     */
    async runHealthCheck() {
        const btn = this.elements.maintHealthCheck;
        const statusEl = this.elements.maintenanceStatus;
        
        if (btn) {
            btn.disabled = true;
            btn.classList.add('loading');
            const icon = btn.querySelector('i');
            if (icon) icon.className = 'fas fa-spinner';
        }
        
        this.showMaintenanceStatus('info', 'Running health check...');
        
        try {
            const response = await fetch(`${this.FASTAPI_BASE}/maintenance/health`);
            const result = await response.json();
            
            if (result.success) {
                const details = result.details || {};
                let healthReport = '✓ System Healthy\n';
                healthReport += `• Redis: ${details.redis ? '✓' : '✗'}\n`;
                healthReport += `• Celery: ${details.celery ? '✓' : '✗'}\n`;
                healthReport += `• AI Model: ${details.ai_model ? '✓' : '✗'}\n`;
                healthReport += `• Disk: ${details.disk_space || 'Unknown'}\n`;
                healthReport += `• Cached Waveforms: ${details.waveform_cache || 0}`;
                
                this.showMaintenanceStatus('success', healthReport);
                this.addLog('success', 'Health check passed');
            } else {
                this.showMaintenanceStatus('error', `⚠ Issues Found:\n${result.message}`);
                this.addLog('warning', `Health check: ${result.message}`);
            }
        } catch (error) {
            this.showMaintenanceStatus('error', `✗ Health check failed: ${error.message}`);
            this.addLog('error', `Health check error: ${error.message}`);
        } finally {
            if (btn) {
                btn.disabled = false;
                btn.classList.remove('loading');
                const icon = btn.querySelector('i');
                if (icon) icon.className = 'fas fa-heartbeat';
            }
        }
    }

    /**
     * Run factory reset with confirmation
     */
    async runFactoryReset() {
        const confirmed = await this.showConfirmDialog(
            'Factory Reset',
            'This will clear ALL data including:\n• All jobs and queues\n• Waveform cache\n• Analysis reports\n• Log files\n\nThis action cannot be undone. Continue?',
            'Reset Everything',
            'Cancel'
        );
        
        if (!confirmed) return;
        
        await this.runMaintenance('factory-reset', 'Performing factory reset...');
    }

    /**
     * Show maintenance status message
     */
    showMaintenanceStatus(type, message) {
        const statusEl = this.elements.maintenanceStatus;
        if (!statusEl) return;
        
        statusEl.className = `maintenance-status ${type}`;
        statusEl.textContent = message;
        statusEl.style.display = 'block';
        statusEl.style.whiteSpace = 'pre-line';
        
        // Auto-hide after 10 seconds for success/error
        if (type !== 'info') {
            setTimeout(() => {
                statusEl.style.display = 'none';
            }, 10000);
        }
    }

    /**
     * Setup view selector tabs (legacy - now handled by browser tabs)
     */
    setupViewSelector() {
        // View selector is now integrated into browser tabs (Files/Config)
        // This function is kept for backwards compatibility
    }

    setupBatchSplitter() {
        const splitter = this.elements.batchSplitter;
        const details = this.elements.batchDetails;
        if (!splitter || !details) return;

        const container = splitter.closest('.quadrant-content');
        if (!container) return;

        const minTableHeight = 160;
        const minDetailsHeight = 200;
        let dragging = false;
        let startY = 0;
        let startHeight = 0;
        let maxDetailsHeight = 0;

        const onPointerMove = (e) => {
            if (!dragging) return;
            const delta = startY - e.clientY;
            let nextHeight = startHeight + delta;
            nextHeight = Math.max(minDetailsHeight, Math.min(maxDetailsHeight, nextHeight));
            details.style.height = `${Math.round(nextHeight)}px`;
            details.style.maxHeight = 'none';
        };

        const onPointerUp = () => {
            if (!dragging) return;
            dragging = false;
            splitter.classList.remove('active');
            document.body.classList.remove('batch-details-resizing');
            try {
                const currentHeight = Math.round(details.getBoundingClientRect().height);
                if (currentHeight > 0) {
                    localStorage.setItem('batch-details-height', String(currentHeight));
                }
            } catch {}
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('pointerup', onPointerUp);
        };

        splitter.addEventListener('pointerdown', (e) => {
            if (details.style.display === 'none') return;
            dragging = true;
            startY = e.clientY;
            startHeight = details.getBoundingClientRect().height;
            const containerRect = container.getBoundingClientRect();
            const summaryHeight = container.querySelector('.batch-summary')?.getBoundingClientRect().height || 0;
            const splitterHeight = splitter.getBoundingClientRect().height || 0;
            const available = containerRect.height - summaryHeight - splitterHeight - minTableHeight;
            maxDetailsHeight = Math.max(minDetailsHeight, Math.floor(available));

            splitter.classList.add('active');
            document.body.classList.add('batch-details-resizing');
            splitter.setPointerCapture(e.pointerId);
            e.preventDefault();

            window.addEventListener('pointermove', onPointerMove);
            window.addEventListener('pointerup', onPointerUp);
        });

        splitter.addEventListener('dblclick', () => {
            details.style.height = '';
            details.style.maxHeight = '';
            try { localStorage.removeItem('batch-details-height'); } catch {}
        });
    }

    /**
     * Switch analysis mode between standard and componentized
     */
    switchAnalysisMode(mode) {
        this.analysisMode = mode;

        // Update tab active states
        this.elements.modeTabs.forEach(tab => {
            if (tab.dataset.mode === mode) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Toggle UI visibility
        if (mode === 'standard') {
            this.elements.standardModeUi.style.display = 'block';
            this.elements.componentizedModeUi.style.display = 'none';
            this.componentSelectionMode = false;
        } else if (mode === 'componentized') {
            this.elements.standardModeUi.style.display = 'none';
            this.elements.componentizedModeUi.style.display = 'block';
        }

        // Update detection methods state based on analysis mode
        this.updateDetectionMethodsState();

        console.log(`Switched to ${mode} mode`);
    }

    /**
     * Start componentized analysis - add to batch queue
     */
    startComponentizedAnalysis() {
        if (!this.componentizedMaster || this.selectedComponents.length === 0) {
            this.addLog('warning', 'Please select a master file and at least one component file');
            return;
        }

        const batchItem = this.createComponentizedBatchItem();
        if (batchItem) {
            this.batchQueue.push(batchItem);
            this.updateBatchTable();
            this.updateBatchSummary();
            this.persistBatchQueue().catch(err => console.warn('Persist batch queue failed:', err));

            this.addLog('success', `Added componentized item to batch: ${this.componentizedMaster.name} with ${this.selectedComponents.length} components`);

            // Clear selections
            this.componentizedMaster = null;
            this.selectedComponents = [];
            this.updateComponentsList();
            this.validateComponentizedSelection();

            // Clear master slot
            const placeholder = this.elements.compMasterSlot.querySelector('.file-placeholder');
            placeholder.classList.remove('filled');
            placeholder.innerHTML = `
                <i class="fas fa-file-audio"></i>
                <span>Click to select master file</span>
            `;
        }
    }

    /**
     * Create a componentized batch item
     */
    createComponentizedBatchItem() {
        // Check for duplicates
        const duplicate = this.batchQueue.find(item =>
            item.type === 'componentized' &&
            item.master.path === this.componentizedMaster.path &&
            JSON.stringify(item.components.map(c => c.path).sort()) ===
            JSON.stringify(this.selectedComponents.map(c => c.path).sort())
        );

        if (duplicate) {
            this.addLog('warning', 'This componentized item already exists in batch queue');
            return null;
        }

        const batchItem = {
            id: Date.now(),
            type: 'componentized',
            master: {...this.componentizedMaster},
            components: this.selectedComponents.map((comp, index) => ({
                ...comp,
                index: index
            })),
            status: 'queued',
            progress: 0,
            componentResults: [],
            offsetMode: this.componentizedOffsetMode,
            error: null,
            timestamp: new Date().toISOString(),
            frameRate: this.detectedFrameRate
        };

        return batchItem;
    }

    /**
     * Switch to Batch Details view and show item details in the dedicated quadrant
     */
    showBatchDetailsInQuadrant(itemId) {
        // Hide placeholder, show content
        const placeholder = document.getElementById('batch-details-placeholder');
        const content = document.getElementById('batch-details-content');
        if (placeholder) placeholder.style.display = 'none';
        if (content) content.style.display = 'block';
    }
    
    /**
     * Hide batch details and show placeholder
     */
    hideBatchDetailsInQuadrant() {
        const placeholder = document.getElementById('batch-details-placeholder');
        const content = document.getElementById('batch-details-content');
        if (placeholder) placeholder.style.display = 'flex';
        if (content) {
            content.style.display = 'none';
            content.innerHTML = '';
        }
    }
    
    /**
     * Show item details in the Batch Details quadrant (not dropdown)
     */
    showItemDetailsInQuadrant(item) {
        const content = document.getElementById('batch-details-content');
        const placeholder = document.getElementById('batch-details-placeholder');
        
        if (!content) return;
        
        // Hide placeholder, show content
        if (placeholder) placeholder.style.display = 'none';
        content.style.display = 'block';
        
        const isComponentized = item.type === 'componentized';
        const hasResults = isComponentized 
            ? (item.componentResults && item.componentResults.length > 0)
            : !!item.result;
        
        // Build the details HTML
        let detailsHtml = '';
        
        // Header with item info
        detailsHtml += `
            <div class="quadrant-details-header">
                <h3><i class="fas ${isComponentized ? 'fa-layer-group' : 'fa-file-audio'}"></i> 
                    ${item.master.name}
                </h3>
                <span class="status-badge ${item.status}">${item.status}</span>
            </div>
        `;
        
        if (!hasResults) {
            // Show pending/processing state
            detailsHtml += `
                <div class="details-pending">
                    <i class="fas ${item.status === 'processing' ? 'fa-spinner fa-spin' : 'fa-clock'}"></i>
                    <p>${item.status === 'processing' ? 'Analysis in progress...' : 'Analysis pending'}</p>
                    ${item.progress > 0 ? `<p class="progress-info">Progress: ${item.progress}%</p>` : ''}
                    ${item.progressMessage ? `<p class="progress-message">${item.progressMessage}</p>` : ''}
                </div>
            `;
        } else if (isComponentized) {
            // Show componentized results
            detailsHtml += this.generateComponentizedQuadrantDetails(item);
        } else {
            // Show standard results
            detailsHtml += this.generateStandardQuadrantDetails(item);
        }
        
        content.innerHTML = detailsHtml;
    }
    
    /**
     * Generate componentized item details for quadrant display
     */
    generateComponentizedQuadrantDetails(item) {
        const fps = item.frameRate || this.detectedFrameRate;
        const masterDuration = item.masterDuration || 0;
        
        let html = `<div class="quadrant-component-results">`;
        
        // Master findings if any
        if (item.masterFindings && item.masterFindings.length > 0) {
            html += `
                <div class="master-findings-section">
                    <h4><i class="fas fa-info-circle"></i> Master Findings</h4>
                    <div class="findings-tags">
                        ${item.masterFindings.map(f => `<span class="finding-tag info">${f}</span>`).join('')}
                    </div>
                </div>
            `;
        }
        
        // Offset visualization section
        html += `
            <div class="offset-visualization-section">
                <h4><i class="fas fa-align-left"></i> Offset Visualization</h4>
                <div class="offset-timeline-container">
                    ${this.generateOffsetVisualization(item, fps, masterDuration)}
                </div>
            </div>
        `;
        
        // Component results table
        html += `
            <div class="component-results-section">
                <h4><i class="fas fa-list"></i> Component Results</h4>
                <table class="component-results-table">
                    <thead>
                        <tr>
                            <th>Component</th>
                            <th>Offset</th>
                            <th>Confidence</th>
                            <th>Visual</th>
                            <th>Findings</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        item.componentResults.forEach(result => {
            if (!result) return; // Skip null/undefined results
            const timecode = this.formatTimecode(result.offset_seconds ?? 0, fps);
            const confidence = ((result.confidence ?? 0) * 100).toFixed(0);
            const confClass = (result.confidence ?? 0) >= 0.8 ? 'high' : (result.confidence ?? 0) >= 0.5 ? 'medium' : 'low';
            
            html += `
                <tr>
                    <td><span class="comp-label">${result.component || 'Unknown'}</span></td>
                    <td class="offset-cell">${timecode}</td>
                    <td><span class="confidence-badge ${confClass}">${confidence}%</span></td>
                    <td class="visual-cell">${this.generateMiniOffsetBar(result.offset_seconds ?? 0, fps)}</td>
                    <td class="findings-cell">
                        ${result.findings && result.findings.length > 0 
                            ? result.findings.map(f => `<span class="finding-tag ${this.getFindingTagClass(f)}">${f}</span>`).join('')
                            : '<span class="finding-tag neutral">-</span>'
                        }
                    </td>
                </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        </div>`;
        
        return html;
    }
    
    /**
     * Generate compact offset visualization showing all components relative to master
     */
    generateOffsetVisualization(item, fps, masterDuration) {
        if (!item.componentResults || item.componentResults.length === 0) {
            return '<div class="no-visualization">No results to visualize</div>';
        }
        
        // Calculate the range of offsets (filter out null results)
        const offsets = item.componentResults.filter(r => r != null).map(r => r.offset_seconds ?? 0);
        const minOffset = Math.min(...offsets, 0);
        const maxOffset = Math.max(...offsets, 0);
        const range = Math.max(Math.abs(minOffset), Math.abs(maxOffset), 1);
        
        // Compact SVG visualization
        const rowHeight = 16;
        const height = 16 + (item.componentResults.length * rowHeight);
        const centerX = 50;
        const scale = 35 / range;
        
        let svg = `
            <svg class="offset-viz-svg compact" viewBox="0 0 100 ${height}" preserveAspectRatio="xMidYMid meet">
                <!-- Center line -->
                <line x1="${centerX}" y1="0" x2="${centerX}" y2="${height}" stroke="#3b82f6" stroke-width="1.5" stroke-dasharray="2,2"/>
                <!-- Scale labels -->
                <text x="12" y="8" fill="#64748b" font-size="5">-${range.toFixed(1)}s</text>
                <text x="${centerX}" y="8" text-anchor="middle" fill="#3b82f6" font-size="5" font-weight="600">0</text>
                <text x="88" y="8" text-anchor="end" fill="#64748b" font-size="5">+${range.toFixed(1)}s</text>
        `;
        
        item.componentResults.forEach((result, index) => {
            if (!result) return; // Skip null/undefined results
            const y = 14 + (index * rowHeight);
            const offset = result.offset_seconds ?? 0;
            const offsetX = centerX + (offset * scale);
            const barStart = Math.min(centerX, offsetX);
            const barEnd = Math.max(centerX, offsetX);
            
            const colors = { 'a0': '#22c55e', 'a1': '#3b82f6', 'a2': '#f59e0b', 'a3': '#8b5cf6' };
            const color = colors[result.component?.toLowerCase()] || '#94a3b8';
            const direction = offset < 0 ? 'delayed' : offset > 0 ? 'advanced' : 'sync';
            const dirColor = direction === 'delayed' ? '#ef4444' : direction === 'advanced' ? '#3b82f6' : '#22c55e';
            const shortLabel = result.component?.toUpperCase().replace('COMPONENT', 'C').replace(' ', '') || `C${index}`;
            
            svg += `
                <g class="comp-row">
                    <text x="2" y="${y + 3}" fill="${color}" font-size="6" font-weight="600">${shortLabel}</text>
                    <rect x="12" y="${y - 3}" width="76" height="8" rx="2" fill="#1e293b"/>
                    <line x1="${barStart}" y1="${y}" x2="${barEnd}" y2="${y}" stroke="${dirColor}" stroke-width="2" stroke-linecap="round"/>
                    <circle cx="${offsetX}" cy="${y}" r="3" fill="${dirColor}" stroke="#fff" stroke-width="0.5"/>
                    <text x="90" y="${y + 2}" fill="#94a3b8" font-size="5">${offset >= 0 ? '+' : ''}${offset.toFixed(1)}s</text>
                </g>
            `;
        });
        
        svg += '</svg>';
        return svg;
    }
    
    /**
     * Generate mini offset bar for table cell
     */
    generateMiniOffsetBar(offsetSeconds, fps) {
        const maxRange = 2; // +/- 2 seconds for mini display
        const clampedOffset = Math.max(-maxRange, Math.min(maxRange, offsetSeconds));
        const percentage = ((clampedOffset / maxRange) * 50) + 50; // 0-100, 50 is center
        
        const direction = offsetSeconds < 0 ? 'delayed' : offsetSeconds > 0 ? 'advanced' : 'sync';
        const barColor = direction === 'delayed' ? '#ef4444' : direction === 'advanced' ? '#3b82f6' : '#22c55e';
        
        return `
            <div class="mini-offset-bar">
                <div class="mini-offset-track">
                    <div class="mini-offset-center"></div>
                    <div class="mini-offset-marker" style="left: ${percentage}%; background: ${barColor};"></div>
                </div>
            </div>
        `;
    }
    
    /**
     * Generate standard item details for quadrant display
     */
    generateStandardQuadrantDetails(item) {
        const result = item.result;
        const fps = item.frameRate || this.detectedFrameRate;
        const offsetSeconds = result.offset_seconds || 0;
        const confidence = result.confidence || 0;
        const confClass = confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low';
        
        const offsetMs = (offsetSeconds * 1000).toFixed(2);
        const offsetFrames = Math.round(offsetSeconds * fps);
        const offsetDirection = offsetSeconds < 0 ? 'delayed' : offsetSeconds > 0 ? 'advanced' : 'sync';
        
        // Determine severity
        const absOffset = Math.abs(offsetSeconds);
        let severityClass = 'good';
        let severityText = 'In Sync';
        let severityIcon = 'fa-check-circle';
        if (absOffset > 0.5) {
            severityClass = 'critical';
            severityText = 'Critical Offset';
            severityIcon = 'fa-exclamation-triangle';
        } else if (absOffset > 0.1) {
            severityClass = 'warning';
            severityText = 'Minor Offset';
            severityIcon = 'fa-exclamation-circle';
        } else if (absOffset > 0.04) {
            severityClass = 'minor';
            severityText = 'Slight Offset';
            severityIcon = 'fa-info-circle';
        }
        
        return `
            <div class="quadrant-standard-results">
                <!-- Severity Banner -->
                <div class="severity-banner ${severityClass}">
                    <i class="fas ${severityIcon}"></i>
                    <span>${severityText}</span>
                </div>
                
                <!-- Offset Visualization -->
                <div class="standard-offset-viz">
                    ${this.generateStandardOffsetVisualization(offsetSeconds, fps, item)}
                </div>
                
                <!-- Metrics Grid -->
                <div class="result-metrics">
                    <div class="metric-card">
                        <div class="metric-label"><i class="fas fa-clock"></i> Offset</div>
                        <div class="metric-value ${offsetDirection}">${this.formatTimecode(offsetSeconds, fps)}</div>
                        <div class="metric-sub">${offsetMs}ms | ${offsetFrames} frames</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label"><i class="fas fa-check-circle"></i> Confidence</div>
                        <div class="metric-value confidence-${confClass}">${(confidence * 100).toFixed(0)}%</div>
                        <div class="confidence-bar">
                            <div class="confidence-fill ${confClass}" style="width: ${confidence * 100}%"></div>
                        </div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label"><i class="fas fa-film"></i> Frame Rate</div>
                        <div class="metric-value">${fps} fps</div>
                        <div class="metric-sub">Detected</div>
                    </div>
                </div>
                
                <!-- Method info if available -->
                ${result.method ? `
                    <div class="method-info">
                        <span class="method-badge"><i class="fas fa-microscope"></i> ${result.method.toUpperCase()}</span>
                    </div>
                ` : ''}
                
                <!-- File Info -->
                <div class="result-files">
                    <div class="file-row">
                        <span class="file-label"><i class="fas fa-file-video"></i> Master:</span>
                        <span class="file-name" title="${item.master.path}">${item.master.name}</span>
                    </div>
                    <div class="file-row">
                        <span class="file-label"><i class="fas fa-file-audio"></i> Dub:</span>
                        <span class="file-name" title="${item.dub.path}">${item.dub.name}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    /**
     * Generate compact offset visualization for standard (non-componentized) items
     */
    generateStandardOffsetVisualization(offsetSeconds, fps, item) {
        const maxRange = Math.max(Math.abs(offsetSeconds) * 1.5, 1);
        const centerX = 50;
        const scale = 35 / maxRange;
        const offsetX = centerX + (offsetSeconds * scale);
        
        const direction = offsetSeconds < 0 ? 'delayed' : offsetSeconds > 0 ? 'advanced' : 'sync';
        const dirColor = direction === 'delayed' ? '#ef4444' : direction === 'advanced' ? '#3b82f6' : '#22c55e';
        const barStart = Math.min(centerX, offsetX);
        const barWidth = Math.abs(offsetX - centerX);
        
        return `
            <svg class="standard-offset-svg compact" viewBox="0 0 100 35" preserveAspectRatio="xMidYMid meet">
                <rect x="10" y="14" width="80" height="8" rx="4" fill="#1e293b"/>
                <line x1="${centerX}" y1="10" x2="${centerX}" y2="26" stroke="#3b82f6" stroke-width="1.5"/>
                <rect x="${barStart}" y="15" width="${barWidth}" height="6" rx="3" fill="${dirColor}" opacity="0.6"/>
                <circle cx="${offsetX}" cy="18" r="5" fill="${dirColor}" stroke="#fff" stroke-width="1.5"/>
                <text x="${centerX}" y="8" text-anchor="middle" fill="#3b82f6" font-size="6" font-weight="600">MASTER</text>
                <text x="${offsetX}" y="32" text-anchor="middle" fill="${dirColor}" font-size="6" font-weight="600">
                    DUB ${offsetSeconds >= 0 ? '+' : ''}${offsetSeconds.toFixed(2)}s
                </text>
            </svg>
            <div class="offset-direction-label compact ${direction}">
                <i class="fas ${direction === 'delayed' ? 'fa-arrow-left' : direction === 'advanced' ? 'fa-arrow-right' : 'fa-check'}"></i>
                <span>${direction === 'delayed' ? 'Dub BEHIND' : direction === 'advanced' ? 'Dub AHEAD' : 'Aligned'}</span>
            </div>
        `;
    }

    /**
     * Generate a simplified summary for Quadrant 2 (without waveform to avoid duplicate IDs)
     */
    generateQuadrantSummary(item, result, offsetSeconds, confidence, methodDisplayName, offsetFrames, itemFps) {
        const offsetMs = (offsetSeconds * 1000).toFixed(2);
        const confidenceClass = confidence >= 0.8 ? 'high' : confidence >= 0.5 ? 'medium' : 'low';
        const offsetDirection = offsetSeconds < 0 ? 'delayed' : offsetSeconds > 0 ? 'advanced' : 'sync';
        
        // Determine severity
        const absOffset = Math.abs(offsetSeconds);
        let severityClass = 'good';
        let severityText = 'In Sync';
        if (absOffset > 0.5) {
            severityClass = 'critical';
            severityText = 'Critical';
        } else if (absOffset > 0.1) {
            severityClass = 'warning';
            severityText = 'Warning';
        } else if (absOffset > 0.04) {
            severityClass = 'minor';
            severityText = 'Minor';
        }

        return `
            <div class="quadrant-summary">
                <div class="summary-header">
                    <h3><i class="fas fa-file-audio"></i> ${item.master?.name || 'Unknown'}</h3>
                    <span class="severity-badge ${severityClass}">${severityText}</span>
                </div>
                
                <div class="summary-metrics">
                    <div class="metric-card">
                        <div class="metric-label"><i class="fas fa-clock"></i> Sync Offset</div>
                        <div class="metric-value ${offsetDirection}">${this.formatTimecode(offsetSeconds, itemFps)}</div>
                        <div class="metric-sub">${offsetMs}ms | ${offsetFrames}</div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-label"><i class="fas fa-check-circle"></i> Confidence</div>
                        <div class="metric-value confidence-${confidenceClass}">${(confidence * 100).toFixed(0)}%</div>
                        <div class="metric-sub">${confidenceClass.toUpperCase()}</div>
                    </div>
                    
                    <div class="metric-card">
                        <div class="metric-label"><i class="fas fa-film"></i> Frame Rate</div>
                        <div class="metric-value">${itemFps}</div>
                        <div class="metric-sub">fps (detected)</div>
                    </div>
                </div>
                
                <div class="summary-actions">
                    <p class="action-hint"><i class="fas fa-info-circle"></i> Click the row again to view full waveform analysis</p>
                </div>
            </div>
        `;
    }

    /**
     * Setup event handlers for redesigned action buttons with keyboard shortcuts
     */
    setupActionButtonHandlers() {
        // Event delegation for all action buttons
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.action-btn-v2');
            if (!btn) return;

            if (btn.disabled) {
                console.log('Button is disabled, ignoring click');
                return;
            }

            const action = btn.dataset.action;
            const itemId = btn.dataset.itemId;

            console.log('Button click detected:', { action, itemId, btn });

            if (!action || !itemId) {
                console.warn('Missing action or itemId:', { action, itemId });
                return;
            }

            e.stopPropagation(); // Prevent row click handler from interfering
            this.handleActionButton(action, itemId, btn);
        });

        // Keyboard shortcuts (when a table row is focused)
        document.addEventListener('keydown', (e) => {
            // Only handle if a batch table row is focused
            const focusedRow = document.activeElement.closest('tr[data-item-id]');
            if (!focusedRow) return;

            const itemId = focusedRow.dataset.itemId;
            const item = this.batchQueue.find(i => String(i.id) === String(itemId));
            if (!item || item.status !== 'completed') return;

            // Keyboard shortcuts
            if (e.key === 'q' || e.key === 'Q') {
                e.preventDefault();
                const qcBtn = focusedRow.querySelector('.action-btn-v2.qc');
                if (qcBtn && !qcBtn.disabled) {
                    this.handleActionButton('qc', itemId, qcBtn);
                }
            } else if (e.key === 'r' || e.key === 'R') {
                e.preventDefault();
                const repairBtn = focusedRow.querySelector('.action-btn-v2.repair');
                if (repairBtn && !repairBtn.disabled) {
                    this.handleActionButton('repair', itemId, repairBtn);
                }
            } else if (e.key === 'd' || e.key === 'D') {
                e.preventDefault();
                const detailsBtn = focusedRow.querySelector('.action-btn-v2.details');
                if (detailsBtn && !detailsBtn.disabled) {
                    this.handleActionButton('details', itemId, detailsBtn);
                }
            } else if (e.key === 't' || e.key === 'T') {
                e.preventDefault();
                const restartBtn = focusedRow.querySelector('.action-btn-v2.restart');
                if (restartBtn && !restartBtn.disabled) {
                    this.handleActionButton('restart', itemId, restartBtn);
                }
            } else if (e.key === 'Delete') {
                e.preventDefault();
                this.handleActionButton('remove', itemId, null);
            }
        });

        // Global keyboard shortcuts for mode switching
        document.addEventListener('keydown', (e) => {
            // Alt+C for Componentized mode
            if (e.altKey && (e.key === 'c' || e.key === 'C')) {
                e.preventDefault();
                this.switchAnalysisMode('componentized');
                this.showToast('info', 'Switched to Componentized Analysis mode', 'Mode Changed');
            }
            // Alt+S for Standard mode
            else if (e.altKey && (e.key === 's' || e.key === 'S')) {
                e.preventDefault();
                this.switchAnalysisMode('standard');
                this.showToast('info', 'Switched to Standard Analysis mode', 'Mode Changed');
            }
        });
    }

    /**
     * Handle action button clicks with unified logic
     */
    handleActionButton(action, itemId, btn) {
        // Convert itemId to string for comparison since dataset values are always strings
        const item = this.batchQueue.find(i => String(i.id) === String(itemId));
        if (!item) {
            console.warn('Item not found for action:', action, 'itemId:', itemId);
            return;
        }

        console.log('Action button clicked:', action, 'for item:', item.master.name);

        switch (action) {
            case 'qc':
                this.openQCInterface(btn);
                break;
            case 'qc-componentized':
                this.openComponentizedQCInterface(item);
                break;
            case 'repair':
                this.openRepairQCInterface(btn);
                break;
            case 'repair-componentized':
                this.openComponentizedRepairInterface(item);
                break;
            case 'details':
                this.toggleBatchDetails(item);
                break;
            case 'retry':
                this.retryJob(itemId);
                break;
            case 'restart':
                this.restartJob(itemId);
                break;
            case 'remove':
                this.confirmRemoveBatchItem(itemId);
                break;
        }
    }

    /**
     * Show confirmation dialog before removing batch item
     */
    confirmRemoveBatchItem(itemId) {
        const item = this.batchQueue.find(i => String(i.id) === String(itemId));
        if (!item) return;

        // Create confirmation dialog
        const overlay = document.createElement('div');
        overlay.className = 'confirm-dialog-overlay';

        const dialog = document.createElement('div');
        dialog.className = 'confirm-dialog';
        dialog.setAttribute('role', 'dialog');
        dialog.setAttribute('aria-labelledby', 'confirm-dialog-title');
        dialog.setAttribute('aria-describedby', 'confirm-dialog-desc');

        // Handle display text for standard vs componentized items
        const isComponentized = item.type === 'componentized';
        const itemDescription = isComponentized
            ? `<p><strong>${item.master.name}</strong> with <strong>${item.components.length} components</strong></p>`
            : `<p><strong>${item.master.name}</strong> vs <strong>${item.dub.name}</strong></p>`;

        dialog.innerHTML = `
            <div class="confirm-dialog-header">
                <i class="fas fa-exclamation-triangle" aria-hidden="true"></i>
                <h3 id="confirm-dialog-title">Remove from Batch?</h3>
            </div>
            <div class="confirm-dialog-body" id="confirm-dialog-desc">
                ${itemDescription}
                <p>This will remove the analysis from the batch queue. This action cannot be undone.</p>
            </div>
            <div class="confirm-dialog-actions">
                <button class="confirm-dialog-btn" data-action="cancel">Cancel</button>
                <button class="confirm-dialog-btn danger" data-action="confirm">Remove</button>
            </div>
        `;

        document.body.appendChild(overlay);
        document.body.appendChild(dialog);

        // Focus the confirm button
        const confirmBtn = dialog.querySelector('[data-action="confirm"]');
        confirmBtn.focus();

        // Handle button clicks
        dialog.addEventListener('click', (e) => {
            const btn = e.target.closest('[data-action]');
            if (!btn) return;

            if (btn.dataset.action === 'confirm') {
                this.removeBatchItem(itemId);
            }

            // Close dialog
            overlay.remove();
            dialog.remove();
        });

        // Close on overlay click
        overlay.addEventListener('click', () => {
            overlay.remove();
            dialog.remove();
        });

        // Close on Escape key
        const escapeHandler = (e) => {
            if (e.key === 'Escape') {
                overlay.remove();
                dialog.remove();
                document.removeEventListener('keydown', escapeHandler);
            }
        };
        document.addEventListener('keydown', escapeHandler);
    }

    showToast(level, message, title = null, timeoutMs = 6000) {
        try {
            const container = this.toastContainer || document.getElementById('toast-container');
            if (!container) return;
            const el = document.createElement('div');
            el.className = `toast ${level}`;
            const iconMap = { info: 'ℹ️', success: '✅', warning: '⚠️', error: '❌' };
            const icon = iconMap[level] || 'ℹ️';
            el.innerHTML = `
                <span class="toast-title">${icon} ${title ? title : level.toUpperCase()}</span>
                <span class="toast-msg">${message}</span>
                <button class="toast-close" aria-label="Close">×</button>
            `;
            container.appendChild(el);
            const close = () => { try { el.remove(); } catch {} };
            el.querySelector('.toast-close').addEventListener('click', close);
            setTimeout(close, timeoutMs);
        } catch {}
    }
    
    async loadFileTree(path = this.currentPath) {
        this.elements.fileTree.innerHTML = '<div class="loading"><i class="fas fa-spinner fa-spin"></i> Loading files...</div>';

        try {
            console.log('Loading file tree for path:', path);
            // Add cache-busting to force fresh data
            const cacheBuster = `_=${Date.now()}`;
            const response = await fetch(`/api/v1/files?path=${encodeURIComponent(path)}&${cacheBuster}`, {
                cache: 'no-cache',
                headers: {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache'
                }
            });
            console.log('Response status:', response.status);
            const data = await response.json();
            console.log('Response data:', data);
            
            if (data.success) {
                // Combine directories and files into a single list
                const allItems = [];
                
                // Add directories (mark them with type 'directory')
                if (data.directories && Array.isArray(data.directories)) {
                    data.directories.forEach(dir => {
                        allItems.push({
                            name: dir.name,
                            type: 'directory',
                            path: dir.path
                        });
                    });
                }
                
                // Add files with their detected types
                if (data.files && Array.isArray(data.files)) {
                    data.files.forEach(file => {
                        allItems.push({
                            name: file.name,
                            type: file.type || this.detectFileType(file.name),
                            path: file.path
                        });
                    });
                }
                
                this.renderFileTree(allItems, path);
                this.currentPath = path;
                this.elements.currentPath.textContent = path;
                console.log('Successfully loaded file tree:', allItems.length, 'items');
            } else {
                console.error('API returned error:', data.error);
                this.addLog('error', `Failed to load directory: ${data.error}`);
                this.renderMockFileTree();
            }
        } catch (error) {
            console.error('Network error:', error);
            this.addLog('error', `Network error: ${error.message}`);
            // Fallback: render mock file tree for demonstration
            this.renderMockFileTree();
        }
    }
    
    renderFileTree(files, currentPath) {
        const container = this.elements.fileTree;
        container.innerHTML = '';
        
        // Add parent directory link if not at root
        if (currentPath !== '/mnt/data') {
            const parentPath = currentPath.split('/').slice(0, -1).join('/') || '/mnt/data';
            const parentItem = this.createFileItem({
                name: '..',
                type: 'directory',
                path: parentPath
            }, true);
            container.appendChild(parentItem);
        }
        
        // Sort files: directories first, then files
        files.sort((a, b) => {
            if (a.type !== b.type) {
                return a.type === 'directory' ? -1 : 1;
            }
            return a.name.localeCompare(b.name);
        });
        
        files.forEach(file => {
            const item = this.createFileItem(file);
            container.appendChild(item);
        });
    }
    
    renderMockFileTree() {
        const mockFiles = [
            { name: 'amcmurray', type: 'directory', path: '/mnt/data/amcmurray' },
            { name: '_insync_master_files', type: 'directory', path: '/mnt/data/amcmurray/_insync_master_files' },
            { name: '_outofsync_master_files', type: 'directory', path: '/mnt/data/amcmurray/_outofsync_master_files' },
            // Original test files
            { name: 'DunkirkEC_InsideTheCockpit_ProRes.mov', type: 'video', path: '/mnt/data/amcmurray/_insync_master_files/DunkirkEC_InsideTheCockpit_ProRes.mov' },
            { name: 'DunkirkEC_InsideTheCockpit_ProRes_15sec.mov', type: 'video', path: '/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_InsideTheCockpit_ProRes_15sec.mov' },
            // New test files
            { name: 'DunkirkEC_TheInCameraApproach1_ProRes.mov', type: 'video', path: '/mnt/data/amcmurray/_insync_master_files/DunkirkEC_TheInCameraApproach1_ProRes.mov' },
            { name: 'DunkirkEC_TheInCameraApproach1_ProRes_5sec23f.mov', type: 'video', path: '/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_TheInCameraApproach1_ProRes_5sec23f.mov' },
            // MXF files
            { name: 'E4284683_SINNERS_OV_HDR_JG_01_EN_20_B.mxf', type: 'atmos', path: '/mnt/data/amcmurray/_insync_master_files/E4284683_SINNERS_OV_HDR_JG_01_EN_20_B.mxf' },
            { name: 'E5168533_GRCH_LP_NEARFIELD_DOM_ATMOS_2398fps_.atmos.mxf', type: 'atmos', path: '/mnt/data/amcmurray/_outofsync_master_files/E5168533_GRCH_LP_NEARFIELD_DOM_ATMOS_2398fps_.atmos.mxf' }
        ];
        
        this.renderFileTree(mockFiles, '/mnt/data');
        this.addLog('warning', 'Using mock file tree - backend not available');
    }
    
    // Utility method to navigate directly to test files
    async navigateToTestFiles() {
        try {
            await this.loadFileTree('/mnt/data/amcmurray');
        } catch (error) {
            this.addLog('error', `Could not navigate to test files: ${error.message}`);
        }
    }
    
    createFileItem(file, isParent = false) {
        const item = document.createElement('div');
        item.className = `file-item ${file.type}`;
        
        let icon = 'fas fa-file';
        let actualFileType = file.type;
        
        // Override file type based on actual file extension if needed
        if (file.type !== 'directory') {
            if (this.isAudioFile(file.name)) {
                actualFileType = 'audio';
                icon = 'fas fa-file-audio';
                item.classList.add('audio');
            } else if (this.isVideoFile(file.name)) {
                actualFileType = 'video';
                icon = 'fas fa-file-video';
                item.classList.add('video');
            } else {
                actualFileType = 'file';
                icon = 'fas fa-file';
            }
        } else {
            icon = 'fas fa-folder';
            item.classList.add('folder');
        }
        
        // Store the corrected file type
        file.actualType = actualFileType;

        // Add checkbox for component selection mode
        const checkboxHtml = (this.componentSelectionMode && this.isMediaFile(file.name) && file.type !== 'directory')
            ? `<input type="checkbox" class="file-checkbox" data-file-path="${file.path}">`
            : '';

        item.innerHTML = `
            ${checkboxHtml}
            <i class="${icon}"></i>
            <span>${file.name}</span>
        `;
        
        // Add file type indicator for debugging
        if (file.name.includes('Dunkirk')) {
            this.addLog('info', `File: ${file.name} | Detected: ${actualFileType} | Original: ${file.type}`);
        }
        
        if (file.type === 'directory' || isParent) {
            item.addEventListener('click', () => {
                this.loadFileTree(file.path);
                this.addLog('info', `Navigated to: ${file.path}`);
            });
        } else if (this.isMediaFile(file.name)) {
            item.addEventListener('click', (e) => {
                // Handle component selection mode differently
                if (this.componentSelectionMode) {
                    this.handleComponentFileClick(file, item, e);
                } else {
                    this.selectFile(file, item);
                }
            });
            item.addEventListener('dblclick', () => {
                if (!this.componentSelectionMode) {
                    this.assignToSlot(file);
                }
            });

            // Handle checkbox changes in component selection mode
            const checkbox = item.querySelector('.file-checkbox');
            if (checkbox) {
                checkbox.addEventListener('change', (e) => {
                    e.stopPropagation();
                    this.handleComponentFileClick(file, item, e);
                });
            }
        }
        
        return item;
    }
    
    selectFile(file, element) {
        // Remove previous selections
        document.querySelectorAll('.file-item.selected').forEach(el => {
            el.classList.remove('selected');
        });
        
        element.classList.add('selected');
        this.selectedFile = file;
        this.addLog('info', `Selected: ${file.name}`);
    }
    
    assignToSlot(file) {
        if (!this.selectedMaster) {
            this.setMasterFile(file);
        } else if (!this.selectedDub) {
            this.setDubFile(file);
        } else {
            // Both slots filled, ask which to replace
            this.addLog('info', `Both slots filled. Click a slot to replace it.`);
        }
    }
    
    openFileSelector(type) {
        if (this.selectedFile && this.isMediaFile(this.selectedFile.name)) {
            if (type === 'master') {
                this.setMasterFile(this.selectedFile);
            } else if (type === 'dub') {
                this.setDubFile(this.selectedFile);
            } else if (type === 'comp-master') {
                this.setComponentizedMaster(this.selectedFile);
            }
        } else {
            this.addLog('warning', `Please select a media file first`);
        }
    }

    /**
     * Enable component selection mode for file browser
     */
    enableComponentSelection() {
        this.componentSelectionMode = true;
        this.addLog('info', 'Component selection mode enabled - select multiple files');

        // Reload the file tree to add checkboxes
        this.renderFileTree(
            Array.from(this.elements.fileTree.querySelectorAll('.file-item'))
                .map(item => ({
                    name: item.querySelector('span').textContent,
                    type: item.classList.contains('folder') ? 'directory' : 'file',
                    path: item.dataset.path || this.currentPath + '/' + item.querySelector('span').textContent
                })),
            this.currentPath
        );

        // Re-load from server to get fresh data with checkboxes
        this.loadFileTree(this.currentPath);
    }

    /**
     * Handle file search input
     */
    handleFileSearch(searchTerm) {
        const trimmedSearch = searchTerm.trim().toLowerCase();
        const fileItems = this.elements.fileTree.querySelectorAll('.file-item');

        // Show/hide clear button
        if (this.elements.searchClearBtn) {
            this.elements.searchClearBtn.style.display = searchTerm ? 'block' : 'none';
        }

        // If search is empty, show all files
        if (!trimmedSearch) {
            fileItems.forEach(item => {
                item.classList.remove('search-match', 'search-hidden');
                // Remove any search highlights
                const textSpan = item.querySelector('span');
                if (textSpan && textSpan.dataset.originalText) {
                    textSpan.innerHTML = textSpan.dataset.originalText;
                    delete textSpan.dataset.originalText;
                }
            });
            if (this.elements.searchResultsCount) {
                this.elements.searchResultsCount.style.display = 'none';
            }
            return;
        }

        let matchCount = 0;

        fileItems.forEach(item => {
            const textSpan = item.querySelector('span');
            if (!textSpan) return;

            // Store original text if not already stored
            if (!textSpan.dataset.originalText) {
                textSpan.dataset.originalText = textSpan.textContent;
            }

            const fileName = textSpan.dataset.originalText.toLowerCase();
            const isMatch = fileName.includes(trimmedSearch);

            if (isMatch) {
                matchCount++;
                item.classList.add('search-match');
                item.classList.remove('search-hidden');

                // Highlight matching text
                const regex = new RegExp(`(${this.escapeRegex(trimmedSearch)})`, 'gi');
                const highlightedText = textSpan.dataset.originalText.replace(
                    regex,
                    '<span class="search-highlight">$1</span>'
                );
                textSpan.innerHTML = highlightedText;
            } else {
                item.classList.remove('search-match');
                item.classList.add('search-hidden');
                textSpan.innerHTML = textSpan.dataset.originalText;
            }
        });

        // Update results count
        if (this.elements.searchResultsCount && this.elements.searchCountText) {
            this.elements.searchCountText.textContent = `${matchCount} result${matchCount !== 1 ? 's' : ''}`;
            this.elements.searchResultsCount.style.display = 'block';
        }
    }

    /**
     * Clear file search
     */
    clearFileSearch() {
        if (this.elements.fileSearchInput) {
            this.elements.fileSearchInput.value = '';
            this.handleFileSearch('');
            this.elements.fileSearchInput.focus();
        }
    }

    /**
     * Escape special regex characters
     */
    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    /**
     * Handle component file click in multi-select mode
     */
    handleComponentFileClick(file, element, event) {
        const checkbox = element.querySelector('.file-checkbox');

        // Toggle checkbox if clicking on the item (not just the checkbox itself)
        if (!event.target.classList.contains('file-checkbox')) {
            if (checkbox) {
                checkbox.checked = !checkbox.checked;
            }
        }

        const isSelected = checkbox ? checkbox.checked : false;
        const index = this.selectedComponents.findIndex(c => c.path === file.path);

        if (isSelected && index === -1) {
            // Add to selection
            const component = {
                name: file.name,
                path: file.path,
                type: file.actualType || file.type,
                label: this.extractComponentLabel(file.name)
            };
            this.selectedComponents.push(component);
            element.classList.add('selected');
            this.addLog('info', `Added: ${file.name} (${component.label})`);
        } else if (!isSelected && index >= 0) {
            // Remove from selection
            this.selectedComponents.splice(index, 1);
            element.classList.remove('selected');
            this.addLog('info', `Removed: ${file.name}`);
        }

        this.updateComponentsList();
        this.validateComponentizedSelection();
    }

    /**
     * Extract component label from filename (e.g., "a0" from "file_a0.mxf")
     */
    extractComponentLabel(filename) {
        // Try to match pattern like _a0, _a1, etc.
        const match = filename.match(/_a(\d+)\./i);
        if (match) {
            return `a${match[1]}`;
        }

        // Try to match pattern like .a0, .a1, etc.
        const match2 = filename.match(/\.a(\d+)\./i);
        if (match2) {
            return `a${match2[1]}`;
        }

        // Fallback to Component N
        return `Component ${this.selectedComponents.length + 1}`;
    }

    /**
     * Update the visual display of selected components
     */
    updateComponentsList() {
        const container = this.elements.componentFilesList;

        if (this.selectedComponents.length === 0) {
            container.innerHTML = '';
        } else {
            container.innerHTML = this.selectedComponents.map((comp, idx) => `
                <div class="component-chip" data-index="${idx}">
                    <i class="fas fa-file-audio"></i>
                    <span class="chip-name" title="${comp.name}">${comp.name}</span>
                    <button class="chip-remove" onclick="app.removeComponent(${idx}); return false;">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `).join('');
        }

        // Update count
        this.elements.componentCount.textContent = `(${this.selectedComponents.length} selected)`;
    }

    /**
     * Remove a component from selection
     */
    removeComponent(index) {
        const removed = this.selectedComponents.splice(index, 1)[0];
        if (removed) {
            this.addLog('info', `Removed: ${removed.name}`);

            // Uncheck the checkbox if visible
            const fileItems = this.elements.fileTree.querySelectorAll('.file-item');
            fileItems.forEach(item => {
                const checkbox = item.querySelector('.file-checkbox');
                if (checkbox && checkbox.dataset.filePath === removed.path) {
                    checkbox.checked = false;
                    item.classList.remove('selected');
                }
            });

            this.updateComponentsList();
            this.validateComponentizedSelection();
        }
    }

    /**
     * Validate componentized selection and enable/disable analyze button
     */
    validateComponentizedSelection() {
        const hasComponents = this.selectedComponents.length > 0;
        const hasMaster = this.componentizedMaster !== null;
        const componentCount = this.selectedComponents.length;

        if (this.elements.analyzeComponentizedBtn) {
            const isValid = hasComponents && hasMaster;
            this.elements.analyzeComponentizedBtn.disabled = !isValid;

            // Update button tooltip with helpful feedback
            if (!hasMaster && !hasComponents) {
                this.elements.analyzeComponentizedBtn.title = 'Please select a master file and at least one component file';
            } else if (!hasMaster) {
                this.elements.analyzeComponentizedBtn.title = 'Please select a master file';
            } else if (!hasComponents) {
                this.elements.analyzeComponentizedBtn.title = 'Please select at least one component file';
            } else {
                this.elements.analyzeComponentizedBtn.title = `Analyze ${componentCount} component${componentCount === 1 ? '' : 's'} against master`;
            }

            // Add visual feedback to the button text
            if (isValid) {
                const btnIcon = this.elements.analyzeComponentizedBtn.querySelector('i');
                const btnText = this.elements.analyzeComponentizedBtn.querySelector('span') ||
                               this.elements.analyzeComponentizedBtn.childNodes[1];
                if (btnText && btnText.nodeType === Node.TEXT_NODE) {
                    this.elements.analyzeComponentizedBtn.innerHTML = `<i class="fas fa-play"></i> Analyze ${componentCount} Component${componentCount === 1 ? '' : 's'}`;
                }
            }
        }
    }

    /**
     * Set master file for componentized analysis
     */
    setComponentizedMaster(file) {
        this.componentizedMaster = file;
        const placeholder = this.elements.compMasterSlot.querySelector('.file-placeholder');
        placeholder.classList.add('filled');
        placeholder.innerHTML = `
            <i class="fas fa-file-audio"></i>
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-path">${file.path}</div>
            </div>
        `;
        this.validateComponentizedSelection();
        this.addLog('success', `Componentized master set: ${file.name}`);
    }

    setMasterFile(file) {
        this.selectedMaster = file;
        const placeholder = this.elements.masterSlot.querySelector('.file-placeholder');
        placeholder.classList.add('filled');
        placeholder.innerHTML = `
            <i class="fas fa-file-audio"></i>
            <span>${file.name}</span>
        `;
        this.addLog('success', `Master file set: ${file.name}`);
        this.updateAnalyzeButton();
    }
    
    setDubFile(file) {
        this.selectedDub = file;
        const placeholder = this.elements.dubSlot.querySelector('.file-placeholder');
        placeholder.classList.add('filled');
        placeholder.innerHTML = `
            <i class="fas fa-file-audio"></i>
            <span>${file.name}</span>
        `;
        this.addLog('success', `Dub file set: ${file.name}`);
        this.updateAnalyzeButton();
    }
    
    updateAnalyzeButton() {
        const canAnalyze = this.selectedMaster && this.selectedDub && !this.analysisInProgress;
        this.elements.analyzeBtn.disabled = !canAnalyze;
        
        if (canAnalyze) {
            this.elements.analyzeBtn.innerHTML = '<i class="fas fa-play"></i> Start Analysis';
        } else if (this.analysisInProgress) {
            this.elements.analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
        }
    }
    
    updateFileSlots() {
        // Update master slot
        const masterPlaceholder = this.elements.masterSlot.querySelector('.file-placeholder');
        if (this.selectedMaster) {
            masterPlaceholder.classList.add('filled');
            masterPlaceholder.querySelector('.placeholder-text').textContent = this.selectedMaster.name;
        } else {
            masterPlaceholder.classList.remove('filled');
            masterPlaceholder.querySelector('.placeholder-text').textContent = 'Select Master File';
        }
        
        // Update dub slot
        const dubPlaceholder = this.elements.dubSlot.querySelector('.file-placeholder');
        if (this.selectedDub) {
            dubPlaceholder.classList.add('filled');
            dubPlaceholder.querySelector('.placeholder-text').textContent = this.selectedDub.name;
        } else {
            dubPlaceholder.classList.remove('filled');
            dubPlaceholder.querySelector('.placeholder-text').textContent = 'Select Dub File';
        }
    }
    
    async startAnalysis() {
        if (!this.selectedMaster || !this.selectedDub) {
            this.addLog('error', 'Please select both master and dub files');
            return;
        }

        // Detect frame rate from master file
        this.addLog('info', 'Detecting video frame rate...');
        this.detectedFrameRate = await this.detectFrameRate(this.selectedMaster.path);
        this.addLog('info', `Using frame rate: ${this.detectedFrameRate} fps`);

        // Automatically add to batch and process (don't clear selections)
        const newItem = this.addToBatchQueue(false);
        if (!newItem) return;

        this.analysisInProgress = true;
        this.updateAnalyzeButton();
        this.updateStatus('analyzing', 'Analyzing...');

        this.addLog('info', '='.repeat(50));
        this.addLog('info', 'Starting sync analysis...');
        this.addLog('info', `Master: ${newItem.master.name}`);
        this.addLog('info', `Dub: ${newItem.dub.name}`);
        
        // Dispatch analysis started event for operator console
        document.dispatchEvent(new CustomEvent('analysisStarted', {
            detail: {
                master: newItem.master.name,
                dub: newItem.dub.name,
                timestamp: new Date().toISOString()
            }
        }));
        
        let progressInterval = null;
        let es = null; // EventSource for SSE progress
        
        try {
            // Update item status
            newItem.status = 'processing';
            newItem.progress = 0;
            this.updateBatchTableRow(newItem);
            this.updateBatchSummary();
            
            // Progress now updated from FastAPI polling
            
            this.addLog('info', `Starting server-side analysis via FastAPI...`);
            this.addLog('info', `Master path: ${newItem.master.path}`);
            this.addLog('info', `Dub path: ${newItem.dub.path}`);

            // Get current configuration
            const config = this.getAnalysisConfig();

            // Start job
            const startResp = await fetch(`${this.FASTAPI_BASE}/analysis/sync`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    master_file: newItem.master.path,
                    dub_file: newItem.dub.path,
                    methods: (config.methods || []).filter(m => m !== 'ai'),
                    enable_ai: !!config.aiModel,
                    ai_model: config.aiModel || 'wav2vec2',
                    sample_rate: config.sampleRate,
                    window_size: config.windowSize,
                    confidence_threshold: config.confidenceThreshold,
                    frame_rate: this.detectedFrameRate,
                    // Request-level preferences to align UI with API behavior
                    prefer_gpu: !!config.enableGpu,
                    prefer_gpu_bypass_chunked: !!config.enableGpu,
                    enable_drift_detection: !!config.enableDriftDetection,
                    channel_strategy: config.channelStrategy,
                    target_channels: config.targetChannels
                })
            });
            if (!startResp.ok) {
                const t = await startResp.text().catch(() => '');
                throw new Error(`FastAPI start failed: ${startResp.status} ${t}`);
            }
            const startJson = await startResp.json();
            const analysisId = startJson.analysis_id;
            newItem.analysisId = analysisId;
            this.addLog('info', `Analysis started: ${analysisId}`);

            // Live progress via SSE (fallback to polling on error)
            const awaitCompletion = () => new Promise((resolve, reject) => {
                const streamUrl = `${this.FASTAPI_BASE}/analysis/${analysisId}/progress/stream`;
                try {
                    es = new EventSource(streamUrl);
                } catch (e) {
                    es = null;
                }
                let closed = false;
                const closeES = () => { try { es && es.close(); } catch {} es = null; closed = true; };
                const onMessage = (evt) => {
                    try {
                        const s = JSON.parse(evt.data || '{}');
                        if (typeof s.progress === 'number') {
                            newItem.progress = Math.max(newItem.progress, Math.floor(s.progress));
                            this.updateBatchTableRow(newItem);
                            // removed top progress bar; row-level progress only
                        }
                        // Surface server status messages in the UI log with progress (de-dup consecutive)
                        if (s.status_message && s.status_message !== newItem._lastStatusMessage) {
                            const progressPercent = typeof s.progress === 'number' ? Math.floor(s.progress) : 0;
                            this.addProgressLog(s.status_message, progressPercent);
                            newItem._lastStatusMessage = s.status_message;
                        }
                        if (s.status === 'completed') {
                            // Immediately reflect completion in UI, even if we still fetch final payload
                            newItem.progress = 100;
                            newItem.status = 'completed';
                            this.updateBatchTableRow(newItem);
                            // Add final progress update to complete any open progress bars
                            if (s.status_message || newItem._lastStatusMessage) {
                                const finalMessage = s.status_message || newItem._lastStatusMessage || 'Analysis complete';
                                this.addProgressLog(finalMessage, 100);
                            }
                            // Prefer full result payload; fetch if missing
                            const finish = async () => {
                                if (s && s.result) return s;
                                const r = await fetch(`${this.FASTAPI_BASE}/analysis/${analysisId}`);
                                if (!r.ok) throw new Error(`Final fetch failed: HTTP ${r.status}`);
                                return await r.json();
                            };
                            closeES();
                            finish().then(resolve).catch(reject);
                            return;
                        }
                        if (s.status === 'failed' || s.status === 'cancelled') { closeES(); reject(new Error(`Job ${s.status}`)); }
                    } catch {}
                };
                const onError = async () => {
                    // SSE not available or dropped — fall back to polling once
                    closeES();
                    try {
                        const final = await (async () => {
                            let retryDelay = 1000; const maxDelay = 10000;
                            while (true) {
                                const r = await fetch(`${this.FASTAPI_BASE}/analysis/${analysisId}`);
                                if (!r.ok) throw new Error(`Poll failed: HTTP ${r.status}`);
                                const s = await r.json();
                                if (typeof s.progress === 'number') {
                                    newItem.progress = Math.max(newItem.progress, Math.floor(s.progress));
                                    this.updateBatchTableRow(newItem);
                                    // removed top progress bar; row-level progress only
                                }
                                if (s.status === 'completed') {
                                    // Complete any open progress bars
                                    if (newItem._lastStatusMessage) {
                                        this.addProgressLog(newItem._lastStatusMessage, 100);
                                    }
                                    return s;
                                }
                                if (s.status === 'failed' || s.status === 'cancelled') throw new Error(s.message || `Job ${s.status}`);
                                await new Promise(res => setTimeout(res, retryDelay));
                                retryDelay = Math.min(maxDelay, Math.floor(retryDelay * 1.6));
                            }
                        })();
                        resolve(final);
                    } catch (err) {
                        reject(err);
                    }
                };
                if (es) {
                    es.onmessage = onMessage;
                    es.addEventListener('end', () => {
                        if (!closed) {
                            // If the stream ends without an explicit completed event, force-complete the UI row
                            if (newItem.progress < 100) {
                                newItem.progress = 100;
                                newItem.status = 'completed';
                                this.updateBatchTableRow(newItem);
                                // Complete any open progress bars
                                if (newItem._lastStatusMessage) {
                                    this.addProgressLog(newItem._lastStatusMessage, 100);
                                }
                            }
                            closeES();
                        }
                    });
                    es.onerror = onError;
                } else {
                    onError();
                }
            });
            // Top progress bar removed
            const final = await awaitCompletion();

            // Adapt result for UI
            const res = final.result || {};
            const co = res.consensus_offset || {};
            let adapted = {
                offset_seconds: co.offset_seconds ?? 0,
                confidence: co.confidence ?? 0,
                quality_score: res.overall_confidence ?? 0,
                method_used: 'Consensus',
                analysis_id: res.analysis_id || analysisId,
                created_at: res.completed_at || res.created_at || null,
                analysis_methods: Array.isArray(res.method_results) ? res.method_results.map(m => m.method) : []
            };

            // Use the live API result (avoid stale DB overrides)
            this.addLog('success', `Analysis completed: ${this.formatOffsetDisplay(adapted.offset_seconds, true, this.detectedFrameRate)}`);

            // Update batch item
            newItem.status = 'completed';
            newItem.progress = 100;
            newItem.result = adapted;
            newItem.frameRate = this.detectedFrameRate; // Store detected frame rate with the item
            this.updateBatchTableRow(newItem);
            await this.persistBatchQueue().catch(() => {});

            // Auto-repair if enabled from CSV upload
            if (newItem.autoRepair) {
                this.addLog('info', `Auto-repair enabled for: ${newItem.dub.name}`);
                // Delay slightly to ensure UI updates are visible
                setTimeout(() => {
                    this.repairBatchItem(newItem.id.toString(), 'auto');
                }, 500);
            }

            // Prepare browser-compatible audio proxies for playback (with timeout + fallback)
            try {
                this.addLog('info', 'Preparing browser-compatible audio proxies...');
                const ctrl = new AbortController();
                const tId = setTimeout(() => ctrl.abort(), 20000); // 20s timeout
                let usedFallback = false;
                try {
                    const prepResp = await fetch('/api/v1/proxy/prepare', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ master: newItem.master.path, dub: newItem.dub.path }),
                        signal: ctrl.signal
                    });
                    clearTimeout(tId);
                    if (prepResp.ok) {
                        const prep = await prepResp.json();
                        if (prep.success) {
                            newItem.masterProxyUrl = prep.master_url;
                            newItem.dubProxyUrl = prep.dub_url;
                            this.addLog('success', 'Audio proxies ready for playback');
                            if (this.waveformVisualizer && this.waveformVisualizer.loadAudioUrl) {
                                await Promise.all([
                                    this.waveformVisualizer.loadAudioUrl(prep.master_url, 'master'),
                                    this.waveformVisualizer.loadAudioUrl(prep.dub_url, 'dub')
                                ]);
                                this.addLog('info', 'Proxies loaded into waveform engine');
                            }
                        } else {
                            this.addLog('warning', `Proxy prepare failed: ${prep.error || 'unknown error'}`);
                            usedFallback = true;
                        }
                    } else {
                        const t = await prepResp.text().catch(() => '');
                        this.addLog('warning', `Proxy prepare HTTP ${prepResp.status}: ${t}`);
                        usedFallback = true;
                    }
                } catch (e) {
                    clearTimeout(tId);
                    this.addLog('warning', `Proxy prepare timed out or failed: ${e.message}`);
                    usedFallback = true;
                }

                if (usedFallback) {
                    // Fallback to FastAPI streaming proxy (no pre-create step)
                    const masterUrl = `${this.FASTAPI_BASE}/files/proxy-audio?path=${encodeURIComponent(newItem.master.path)}&format=wav&role=master`;
                    const dubUrl = `${this.FASTAPI_BASE}/files/proxy-audio?path=${encodeURIComponent(newItem.dub.path)}&format=wav&role=dub`;
                    newItem.masterProxyUrl = masterUrl;
                    newItem.dubProxyUrl = dubUrl;
                    this.addLog('info', 'Using streaming proxy fallback from API');
                    try {
                        if (this.waveformVisualizer && this.waveformVisualizer.loadAudioUrl) {
                            await Promise.all([
                                this.waveformVisualizer.loadAudioUrl(masterUrl, 'master'),
                                this.waveformVisualizer.loadAudioUrl(dubUrl, 'dub')
                            ]);
                            this.addLog('info', 'Streaming proxies loaded into waveform engine');
                        }
                    } catch (loadErr) {
                        this.addLog('warning', `Streaming proxy load error: ${loadErr.message}`);
                    }
                }
            } catch (e) {
                this.addLog('warning', `Proxy prepare unexpected error: ${e.message}`);
            }
            
        } catch (error) {
            if (progressInterval) clearInterval(progressInterval);
            try { if (es) es.close(); } catch {}
            this.addLog('error', `Analysis failed: ${error.message}`);

            // Dispatch analysis error event for operator console
            document.dispatchEvent(new CustomEvent('analysisError', {
                detail: {
                    message: error.message,
                    timestamp: new Date().toISOString(),
                    master: newItem.master.name,
                    dub: newItem.dub.name
                }
            }));

            // Update batch item with error
            newItem.status = 'failed';
            newItem.error = error.message;
            newItem.progress = 0;
            this.updateBatchTableRow(newItem);
        }
        
        this.analysisInProgress = false;
        this.updateAnalyzeButton();
        this.updateBatchSummary();
        this.updateStatus('ready', 'Ready');
    }

    
    async simulateAnalysis() {
        const steps = [
            { progress: 10, message: 'Loading audio files...' },
            { progress: 25, message: 'Extracting MFCC features...' },
            { progress: 40, message: 'Performing onset detection...' },
            { progress: 60, message: 'Computing spectral correlation...' },
            { progress: 80, message: 'Generating consensus result...' },
            { progress: 95, message: 'Creating visualizations...' },
            { progress: 100, message: 'Analysis complete!' }
        ];
        
        for (const step of steps) {
            this.updateProgress(step.progress, step.message);
            this.addLog('info', step.message);
            await new Promise(resolve => setTimeout(resolve, 800));
        }
    }
    
    displayMockResults() {
        // Use different mock results based on selected files
        let mockResult;
        
        if (this.selectedDub && this.selectedDub.name.includes('TheInCameraApproach1_ProRes_5sec23f')) {
            // New Dunkirk files test case
            mockResult = {
                offset_seconds: -5.990748299319728,
                confidence: 1.0,
                quality_score: 0.47746863066345163,
                method_used: 'Consensus (mfcc primary)',
                analysis_methods: ['mfcc'],
                recommendations: [
                    '❌ CRITICAL: Sync offset exceeds acceptable limits (>100ms) - Correction required',
                    '🔬 HIGH CONFIDENCE: Analysis results are highly reliable',
                    '🔧 CORRECTION: Delay dub audio by 5990.7ms'
                ],
                technical_details: {
                    all_methods: ['mfcc'],
                    primary_method: 'mfcc',
                    method_agreement: 1.0
                }
            };
            this.addLog('info', 'Using mock results for TheInCameraApproach1 files - 5.991s offset');
        } else {
            // Original Dunkirk files test case
            mockResult = {
                offset_seconds: -15.023310657596372,
                confidence: 1.0,
                quality_score: 0.5986970580221493,
                method_used: 'Consensus (mfcc primary)',
                analysis_methods: ['mfcc'],
                recommendations: [
                    '❌ CRITICAL: Sync offset exceeds acceptable limits (>100ms) - Correction required',
                    '🔬 HIGH CONFIDENCE: Analysis results are highly reliable',
                    '🔧 CORRECTION: Delay dub audio by 15023.3ms'
                ],
                technical_details: {
                    all_methods: ['mfcc'],
                    primary_method: 'mfcc',
                    method_agreement: 1.0
                }
            };
            this.addLog('info', 'Using mock results for InsideTheCockpit files - 15.023s offset');
        }
        
        this.addLog('info', 'Using mock results (API failed) - but with correct known offset values');
        this.displayResults({ success: true, result: mockResult });
    }
    
    displayResults(data) {
        if (!data.success) {
            this.addLog('error', 'Analysis failed');
            return;
        }
        
        const result = data.result;
        this.currentAnalysis = result; // Store for repair functionality
        
        // Hide placeholder and show results
        this.elements.resultsPlaceholder.style.display = 'none';

        // Use backend's pre-calculated milliseconds to avoid precision loss
        const offsetMs = result.offset_milliseconds !== undefined
            ? Math.abs(result.offset_milliseconds)
            : Math.abs(result.offset_seconds * 1000);
        const absOffset = Math.abs(result.offset_seconds);
        // Branch convention: positive => dub advanced, negative => dub delayed
        const direction = result.offset_seconds > 0 ? 'advanced' : 'delayed';

        // Calculate frame offset (using common frame rates)
        const frameRates = [23.976, 24, 25, 29.97, 30, 50, 59.94, 60];
        const frameOffsets = this.calculateFrameOffsets(result.offset_seconds, frameRates);

        // Create results summary
        const resultsHTML = `
            <div class="results-summary">
                <div class="result-card sync-offset">
                    <h3>Sync Offset</h3>
                    <div class="result-value ${absOffset > 0.1 ? 'critical' : absOffset > 0.04 ? 'warning' : 'good'}">
                        ${result.offset_seconds > 0 ? '+' : ''}${result.offset_seconds.toFixed(3)}s
                    </div>
                    <div class="result-detail">
                        <div class="offset-frames">
                            ${this.getFrameDisplayString(frameOffsets)}
                        </div>
                        <div class="offset-ms">(${offsetMs.toFixed(1)}ms ${direction})</div>
                    </div>
                </div>
                
                <div class="result-card">
                    <h3>Sync Reliability</h3>
                    <div class="result-value">
                        ${result.confidence > 0.8 ? '✅ RELIABLE' : result.confidence > 0.5 ? '⚠️ UNCERTAIN' : '🔴 PROBLEM'}
                    </div>
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${result.confidence * 100}%"></div>
                    </div>
                </div>
                
                <div class="result-card">
                    <h3>Detection Method</h3>
                    <div class="result-value" style="font-size: 1.2rem;">${this.getMethodDisplayName(result.method_used)}</div>
                    <div class="result-detail">Audio clarity: ${result.quality_score > 0.7 ? '🔵 CLEAR' : result.quality_score > 0.4 ? '🟡 MIXED' : '🟠 POOR'}</div>
                    ${result.chunks_analyzed ? `<div class="result-detail chunks-info">📊 Extended Analysis: ${result.chunks_analyzed} segments checked (${result.chunks_reliable || 0} reliable)</div>` : ''}
                </div>
            </div>
            
            <div class="recommendations">
                <h3>Recommendations</h3>
                ${result.recommendations.map(rec => `<div class="recommendation">${rec}</div>`).join('')}
            </div>
        `;
        
        // Insert results before repair section
        this.elements.repairSection.insertAdjacentHTML('beforebegin', resultsHTML);
        
        // Show repair section and initialize manual offset
        this.elements.repairSection.style.display = 'block';
        this.elements.manualOffset.value = result.offset_seconds.toFixed(6); // Use higher precision
        this.updatePresetButtons(result.offset_seconds);
        
        this.addLog('success', `Analysis complete! Offset: ${this.formatOffsetDisplay(result.offset_seconds, true, this.detectedFrameRate)}`);
        this.addLog('info', `Detection method: ${this.getMethodDisplayName(result.method_used)}`);
        this.addLog('info', `Sync reliability: ${result.confidence > 0.8 ? '✅ RELIABLE' : result.confidence > 0.5 ? '⚠️ UNCERTAIN' : '🔴 PROBLEM'} | Audio clarity: ${result.quality_score > 0.7 ? '🔵 CLEAR' : result.quality_score > 0.4 ? '🟡 MIXED' : '🟠 POOR'}`);

        // Log frame information for common rates
        const framesDetected = Math.round(Math.abs(result.offset_seconds) * this.detectedFrameRate);
        const frames30 = Math.round(Math.abs(result.offset_seconds) * 29.97);
        const frameSign = result.offset_seconds < 0 ? '-' : '+';
        this.addLog('info', `Additional frame rates: ${frameSign}${frames30}f @ 29.97fps`);
        
        // Log additional detection method details if available
        if (result.analysis_methods && result.analysis_methods.length > 0) {
            this.addLog('info', `Detection methods used: ${result.analysis_methods.join(', ').toUpperCase()}`);
        }
        
        // Log segment information to show extended analysis usage
        if (result.chunks_analyzed) {
            this.addLog('info', `📊 Extended Analysis: Analyzed ${result.chunks_analyzed} segments (${result.chunks_reliable || 0} reliable segments)`);
            if (result.chunks_analyzed > 10) {
                this.addLog('success', '✅ Comprehensive segment analysis completed - Extended analysis used successfully');
            }
        }
        
        // Dispatch analysis complete event for operator console
        document.dispatchEvent(new CustomEvent('analysisComplete', {
            detail: {
                ...result,
                timestamp: new Date().toISOString(),
                timeline: result.chunk_details || result.timeline || [],
                combined_chunks: result.chunk_details || []
            }
        }));
        
        // Enable repair buttons if we have a significant offset
        const shouldRepair = Math.abs(result.offset_seconds) > 0.01; // > 10ms
        this.elements.autoRepairBtn.disabled = !shouldRepair;
        this.elements.manualRepairBtn.disabled = false;
        
        if (shouldRepair) {
            this.addLog('info', 'Sync correction recommended - repair options now available');
        } else {
            this.addLog('info', 'Sync is within acceptable limits');
        }
    }
    
    updatePresetButtons(currentOffset) {
        document.querySelectorAll('.preset-btn').forEach(btn => {
            const btnOffset = parseFloat(btn.dataset.offset);
            if (Math.abs(btnOffset - currentOffset) < 0.001) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });
    }
    
    async startAutoRepair() {
        if (!this.currentAnalysis) {
            this.addLog('error', 'No analysis results available for repair');
            return;
        }
        
        const offset = this.currentAnalysis.offset_seconds;
        await this.performRepair(offset, 'auto');
    }
    
    async startManualRepair() {
        const offset = parseFloat(this.elements.manualOffset.value);
        if (isNaN(offset)) {
            this.addLog('error', 'Invalid offset value');
            return;
        }
        
        await this.performRepair(offset, 'manual');
    }
    
    async performRepair(offset, mode) {
        if (!this.selectedDub) {
            this.addLog('error', 'No dub file selected for repair');
            return;
        }
        
        this.addLog('info', '='.repeat(50));
        this.addLog('info', `Starting ${mode} repair...`);
        this.addLog('info', `Target offset: ${offset.toFixed(3)}s`);
        this.addLog('info', `File: ${this.selectedDub.name}`);
        
        // Disable repair buttons during operation
        this.elements.autoRepairBtn.disabled = true;
        this.elements.manualRepairBtn.disabled = true;
        
        try {
            // Show repair progress
            this.showRepairProgress();
            
            const response = await fetch('/api/v1/repair', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: this.selectedDub.path,
                    offset_seconds: offset,
                    preserve_quality: this.elements.preserveQuality.checked,
                    create_backup: this.elements.createBackup.checked,
                    output_dir: this.elements.outputDir.value,
                    repair_mode: mode
                })
            });
            
            if (response.ok) {
                const result = await response.json();
                this.displayRepairResults(result);
            } else {
                const error = await response.json();
                throw new Error(error.error || 'Repair failed');
            }
            
        } catch (error) {
            this.addLog('error', `Repair failed: ${error.message}`);
            this.hideRepairProgress();
        }
        
        // Re-enable repair buttons
        this.elements.autoRepairBtn.disabled = false;
        this.elements.manualRepairBtn.disabled = false;
    }
    
    showRepairProgress() {
        const progressHTML = `
            <div class="repair-progress" id="repair-progress">
                <h4><i class="fas fa-cog fa-spin"></i> Repairing Audio Sync...</h4>
                <div class="repair-progress-bar">
                    <div class="repair-progress-fill" id="repair-progress-fill"></div>
                </div>
                <div class="repair-status" id="repair-status">Initializing repair process...</div>
            </div>
        `;
        
        this.elements.repairSection.insertAdjacentHTML('beforeend', progressHTML);
        this.simulateRepairProgress();
    }
    
    hideRepairProgress() {
        const progressElement = document.getElementById('repair-progress');
        if (progressElement) {
            progressElement.remove();
        }
    }
    
    async simulateRepairProgress() {
        const steps = [
            { progress: 10, message: 'Creating backup...' },
            { progress: 25, message: 'Analyzing audio stream...' },
            { progress: 50, message: 'Applying timing correction...' },
            { progress: 75, message: 'Re-encoding with preserved quality...' },
            { progress: 90, message: 'Verifying repair integrity...' },
            { progress: 100, message: 'Repair complete!' }
        ];
        
        for (const step of steps) {
            const fillElement = document.getElementById('repair-progress-fill');
            const statusElement = document.getElementById('repair-status');
            
            if (fillElement && statusElement) {
                fillElement.style.width = `${step.progress}%`;
                statusElement.textContent = step.message;
                this.addLog('info', step.message);
            }
            
            await new Promise(resolve => setTimeout(resolve, 1000));
        }
    }
    
    displayRepairResults(data) {
        this.hideRepairProgress();
        
        if (data.success) {
            this.addLog('success', 'Repair completed successfully!');
            this.addLog('info', `Repaired file: ${data.output_file}`);
            this.addLog('info', `Applied offset: ${data.applied_offset}s`);
            
            if (data.backup_created) {
                this.addLog('info', `Backup saved: ${data.backup_file}`);
            }
            
            // Show success message in repair section
            const successHTML = `
                <div class="repair-success">
                    <h4><i class="fas fa-check-circle"></i> Repair Successful!</h4>
                    <p><strong>Output:</strong> ${data.output_file}</p>
                    <p><strong>Offset Applied:</strong> ${data.applied_offset}s</p>
                    ${data.backup_created ? `<p><strong>Backup:</strong> ${data.backup_file}</p>` : ''}
                </div>
            `;
            
            this.elements.repairSection.insertAdjacentHTML('beforeend', successHTML);
        } else {
            this.addLog('error', `Repair failed: ${data.error}`);
        }
    }
    
    updateProgress(percentage, message) {
        // Dispatch progress event for operator console
        document.dispatchEvent(new CustomEvent('analysisProgress', {
            detail: {
                percentage: percentage,
                message: message,
                stage: this.getCurrentAnalysisStage(percentage),
                timestamp: new Date().toISOString()
            }
        }));

        // Update status indicator to show progress
        if (this.elements?.statusText) {
            this.elements.statusText.textContent = `${message} (${percentage}%)`;
        }
    }

    getCurrentAnalysisStage(percentage) {
        if (percentage < 15) return "Loading audio files";
        if (percentage < 30) return "Extracting features";
        if (percentage < 50) return "Analyzing sync";
        if (percentage < 75) return "Processing results";
        if (percentage < 95) return "Finalizing analysis";
        return "Complete";
    }
    
    updateStatus(status, text) {
        this.elements.statusText.textContent = text;
        this.elements.statusDot.className = `status-dot ${status}`;
    }
    
    /**
     * Setup audio file loading capabilities
     */
    setupAudioFileLoading() {
        // Create hidden file inputs for audio loading
        this.createAudioFileInputs();
        
        // Add drag and drop to file slots
        this.setupDragAndDrop();
        
        // Add click handlers to file slots
        this.setupFileSlotClicks();
    }
    
    /**
     * Create hidden file inputs for audio files
     */
    createAudioFileInputs() {
        // Master file input
        this.masterFileInput = document.createElement('input');
        this.masterFileInput.type = 'file';
        this.masterFileInput.accept = '.wav,.mp3,.flac,.m4a,.aiff,.aac,.ogg,.mov,.mp4,.avi,.mkv,.wmv,.ec3,.eac3,.adm,.iab,.mxf';
        this.masterFileInput.style.display = 'none';
        this.masterFileInput.addEventListener('change', (e) => {
            if (e.target.files[0]) {
                this.loadAudioFile(e.target.files[0], 'master');
            }
        });
        document.body.appendChild(this.masterFileInput);

        // Dub file input
        this.dubFileInput = document.createElement('input');
        this.dubFileInput.type = 'file';
        this.dubFileInput.accept = '.wav,.mp3,.flac,.m4a,.aiff,.aac,.ogg,.mov,.mp4,.avi,.mkv,.wmv,.ec3,.eac3,.adm,.iab,.mxf';
        this.dubFileInput.style.display = 'none';
        this.dubFileInput.addEventListener('change', (e) => {
            if (e.target.files[0]) {
                this.loadAudioFile(e.target.files[0], 'dub');
            }
        });
        document.body.appendChild(this.dubFileInput);
    }
    
    /**
     * Setup drag and drop functionality
     */
    setupDragAndDrop() {
        // Standard mode drag and drop
        [this.elements.masterSlot, this.elements.dubSlot].forEach((slot, index) => {
            const type = index === 0 ? 'master' : 'dub';

            slot.addEventListener('dragover', (e) => {
                e.preventDefault();
                slot.classList.add('drag-over');
            });

            slot.addEventListener('dragleave', (e) => {
                e.preventDefault();
                slot.classList.remove('drag-over');
            });

            slot.addEventListener('drop', (e) => {
                e.preventDefault();
                slot.classList.remove('drag-over');

                const files = Array.from(e.dataTransfer.files);
                const audioFile = files.find(file => this.isAudioFile(file));

                if (audioFile) {
                    this.loadAudioFile(audioFile, type);
                } else {
                    console.error('Please drop a valid media file (WAV, MP3, FLAC, M4A, AIFF, MOV, MP4, MXF, etc.)');
                }
            });
        });

        // Componentized mode drag and drop
        if (this.elements.compMasterSlot) {
            this.elements.compMasterSlot.addEventListener('dragover', (e) => {
                e.preventDefault();
                this.elements.compMasterSlot.classList.add('drag-over');
            });

            this.elements.compMasterSlot.addEventListener('dragleave', (e) => {
                e.preventDefault();
                this.elements.compMasterSlot.classList.remove('drag-over');
            });

            this.elements.compMasterSlot.addEventListener('drop', (e) => {
                e.preventDefault();
                this.elements.compMasterSlot.classList.remove('drag-over');

                const files = Array.from(e.dataTransfer.files);
                const audioFile = files.find(file => this.isMediaFile(file.name));

                if (audioFile) {
                    this.setComponentizedMaster({
                        name: audioFile.name,
                        path: audioFile.path || audioFile.webkitRelativePath || `/mnt/data/${audioFile.name}`,
                        type: 'file'
                    });
                } else {
                    this.addLog('error', 'Please drop a valid media file');
                }
            });
        }

        // Component files list drag and drop (multi-file)
        if (this.elements.componentFilesList) {
            const dropZone = this.elements.componentFilesList.parentElement;

            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('drag-over');
            });

            dropZone.addEventListener('dragleave', (e) => {
                e.preventDefault();
                dropZone.classList.remove('drag-over');
            });

            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('drag-over');

                const files = Array.from(e.dataTransfer.files);
                const mediaFiles = files.filter(file => this.isMediaFile(file.name));

                if (mediaFiles.length > 0) {
                    mediaFiles.forEach(file => {
                        const component = {
                            name: file.name,
                            path: file.path || file.webkitRelativePath || `/mnt/data/${file.name}`,
                            type: 'file',
                            label: this.extractComponentLabel(file.name)
                        };

                        // Avoid duplicates
                        const exists = this.selectedComponents.some(c => c.path === component.path);
                        if (!exists) {
                            this.selectedComponents.push(component);
                        }
                    });

                    this.updateComponentsList();
                    this.validateComponentizedSelection();
                    this.addLog('success', `Added ${mediaFiles.length} component(s)`);
                } else {
                    this.addLog('error', 'Please drop valid media files');
                }
            });
        }
    }
    
    /**
     * Setup click handlers for file slots
     */
    setupFileSlotClicks() {
        this.elements.masterSlot.addEventListener('click', () => {
            this.masterFileInput.click();
        });
        
        this.elements.dubSlot.addEventListener('click', () => {
            this.dubFileInput.click();
        });
    }
    
    /**
     * Load audio file and update visualization
     */
    async loadAudioFile(file, type) {
        if (!this.isAudioFile(file)) {
            console.error('Unsupported file format. Please select a valid audio file.');
            return;
        }
        
        try {
            console.log(`Loading ${type} file: ${file.name}`);
            
            // Load into waveform visualizer
            await this.waveformVisualizer.loadAudioFile(file, type);
            
            // Update UI
            this.updateFileSlot(file, type);
            
            // Update file selection state
            if (type === 'master') {
                this.selectedMaster = {
                    type: 'file',
                    path: file.name,
                    file: file
                };
            } else {
                this.selectedDub = {
                    type: 'file', 
                    path: file.name,
                    file: file
                };
            }
            
            this.updateAnalyzeButton();
            
            // Get and display metadata
            const metadata = this.waveformVisualizer.getAudioMetadata(type);
            if (metadata.hasRealData) {
                console.log(`📊 Duration: ${metadata.duration?.toFixed(2)}s, Sample Rate: ${metadata.sampleRate}Hz`);
            }
            
        } catch (error) {
            console.error(`Failed to load ${type} file:`, error);
        }
    }
    
    /**
     * Update file slot display with loaded file info
     */
    updateFileSlot(file, type) {
        const slot = type === 'master' ? this.elements.masterSlot : this.elements.dubSlot;
        const placeholder = slot.querySelector('.file-placeholder');
        
        if (placeholder) {
            placeholder.innerHTML = `
                <div class="file-loaded">
                    <i class="fas fa-file-audio" style="color: #4CAF50;"></i>
                    <div class="file-info">
                        <div class="file-name">${file.name}</div>
                        <div class="file-details">
                            <span>📊 Real Audio</span>
                            <span>📁 ${this.formatFileSize(file.size)}</span>
                        </div>
                    </div>
                    <button class="remove-file-btn" onclick="app.removeAudioFile('${type}')" title="Remove file">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;
            
            slot.classList.add('has-file');
        }
    }
    
    /**
     * Remove loaded audio file
     */
    removeAudioFile(type) {
        const slot = type === 'master' ? this.elements.masterSlot : this.elements.dubSlot;
        const placeholder = slot.querySelector('.file-placeholder');
        
        if (placeholder) {
            placeholder.innerHTML = `
                <i class="fas fa-file-audio"></i>
                <span>Click to select ${type} file</span>
            `;
            
            slot.classList.remove('has-file');
        }
        
        // Clear from waveform visualizer
        if (this.waveformVisualizer && this.waveformVisualizer.realAudioData) {
            this.waveformVisualizer.realAudioData.delete(type);
        }
        
        // Clear selection state
        if (type === 'master') {
            this.selectedMaster = null;
        } else {
            this.selectedDub = null;
        }
        
        this.updateAnalyzeButton();
        console.log(`${type} file removed`);
    }
    
    /**
     * Check if file is a supported audio format
     */
    isAudioFile(file) {
        const supportedTypes = [
            'audio/wav', 'audio/wave', 'audio/x-wav',
            'audio/mp3', 'audio/mpeg',
            'audio/flac',
            'audio/m4a', 'audio/mp4',
            'audio/aiff', 'audio/x-aiff',
            'audio/aac',
            'audio/ogg',
            'video/quicktime',  // MOV files
            'video/mp4',
            'video/x-msvideo',  // AVI
            'video/x-matroska'  // MKV
        ];

        const supportedExtensions = [
            '.wav', '.mp3', '.flac', '.m4a', '.aiff', '.aac', '.ogg',
            '.mov', '.mp4', '.avi', '.mkv', '.wmv',  // Video containers
            '.ec3', '.eac3', '.adm', '.iab', '.mxf'  // Atmos and professional formats
        ];

        return supportedTypes.includes(file.type) ||
               supportedExtensions.some(ext => file.name.toLowerCase().endsWith(ext));
    }
    
    /**
     * Format file size for display
     */
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
    }
    
    initOperatorConsole() {
        // Initialize Operator Console if available
        if (typeof OperatorConsole !== 'undefined') {
            this.operatorConsole = new OperatorConsole();

            // Re-initialize log container reference after Operator Console creates it
            setTimeout(() => {
                this.elements.logContainer = document.getElementById('log-container');
                if (this.elements.logContainer) {
                } else {
                    console.error('❌ Log container still not found after Operator Console setup');
                }
            }, 100);
        } else {
            // OperatorConsole should be available - it will initialize itself
            console.log('🎯 Operator Console will initialize from global instance');
            // Set a timeout to grab the global instance
            setTimeout(() => {
                if (window.operatorConsole) {
                    this.operatorConsole = window.operatorConsole;
                }
            }, 100);
        }
    }

    clearLogs() {
        this.elements.logContainer.innerHTML = '';
        this.addLog('info', 'Logs cleared');
    }
    
    toggleAutoScroll() {
        this.autoScroll = !this.autoScroll;
        this.elements.autoScrollBtn.classList.toggle('active', this.autoScroll);
        this.addLog('info', `Auto-scroll ${this.autoScroll ? 'enabled' : 'disabled'}`);
    }
    
    startLogUpdates() {
        // Simulate periodic system updates
        setInterval(() => {
            if (!this.analysisInProgress) {
                const messages = [
                    'System monitoring active',
                    'File system ready',
                    'Sync analyzer standing by'
                ];
                
                if (Math.random() < 0.1) { // 10% chance every 5 seconds
                    const message = messages[Math.floor(Math.random() * messages.length)];
                    this.addLog('info', message);
                }
            }
        }, 5000);
    }
    
    /**
     * Convert seconds to SMPTE timecode format HH:MM:SS:FF
     * @param {number} seconds - Time in seconds
     * @param {number} fps - Frame rate (default: 23.976)
     * @returns {string} Timecode string
     */
    formatTimecode(seconds, fps = 23.976) {
        const sign = seconds < 0 ? '-' : '';
        const absSeconds = Math.abs(seconds);

        const hours = Math.floor(absSeconds / 3600);
        const minutes = Math.floor((absSeconds % 3600) / 60);
        const secs = Math.floor(absSeconds % 60);
        const frames = Math.floor((absSeconds % 1) * fps);

        return `${sign}${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}:${frames.toString().padStart(2, '0')}`;
    }

    /**
     * Format timecode with seconds display for clarity
     */
    formatTimecodeWithSeconds(offsetSeconds, fps = 23.976, precision = 3) {
        if (!Number.isFinite(offsetSeconds)) {
            return 'N/A';
        }

        const timecode = this.formatTimecode(offsetSeconds, fps);
        const sign = offsetSeconds < 0 ? '-' : '+';
        const secondsAbs = Math.abs(offsetSeconds).toFixed(precision);
        return `${timecode} (${sign}${secondsAbs}s)`;
    }

    isAudioFile(filename) {
        const audioExtensions = ['.wav', '.mp3', '.flac', '.m4a', '.aiff', '.ogg', '.ec3', '.eac3', '.adm', '.iab'];
        return audioExtensions.some(ext => filename.toLowerCase().endsWith(ext));
    }

    isVideoFile(filename) {
        const videoExtensions = ['.mov', '.mp4', '.avi', '.mkv', '.wmv', '.mxf'];
        return videoExtensions.some(ext => filename.toLowerCase().endsWith(ext));
    }
    
    isMediaFile(filename) {
        return this.isAudioFile(filename) || this.isVideoFile(filename);
    }
    
    getMethodDisplayName(methodUsed) {
        if (!methodUsed) return 'Unknown';
        
        // Clean up method names for display
        if (methodUsed.includes('MFCC')) {
            return 'MFCC Analysis';
        } else if (methodUsed.includes('Onset')) {
            return 'Onset Detection';
        } else if (methodUsed.includes('Spectral')) {
            return 'Spectral Analysis';
        } else if (methodUsed.includes('Consensus')) {
            if (methodUsed.includes('mfcc')) return 'Consensus (MFCC)';
            if (methodUsed.includes('onset')) return 'Consensus (Onset)';
            if (methodUsed.includes('spectral')) return 'Consensus (Spectral)';
            return 'Multi-Method Consensus';
        } else if (methodUsed.includes('AI') || methodUsed.includes('Embedding')) {
            return 'AI Embeddings';
        }
        
        return methodUsed;
    }
    
    calculateFrameOffsets(offsetSeconds, frameRates) {
        return frameRates.map(fps => {
            const frames = Math.round(Math.abs(offsetSeconds) * fps);
            const sign = offsetSeconds < 0 ? '-' : '+';
            return {
                fps: fps,
                frames: frames,
                display: `${sign}${frames}f @ ${fps}fps`
            };
        });
    }
    
    getFrameDisplayString(frameOffsets) {
        // Ensure frameOffsets is an array
        if (!Array.isArray(frameOffsets)) {
            return 'N/A';
        }

        // Show the most common frame rates
        const commonRates = [23.976, 24, 25, 29.97];
        const displays = frameOffsets
            .filter(fo => commonRates.includes(fo.fps))
            .map(fo => fo.display);

        return displays.length > 0 ? displays.join(' | ') : 'N/A';
    }

    /**
     * Format offset for display with timecode and frames
     * @param {number} offsetSeconds - Offset in seconds
     * @param {boolean} includeFrames - Whether to include frame count (default: true)
     * @param {number} defaultFps - Default frame rate to use (default: 23.976)
     * @returns {string} Formatted offset string with timecode
     */
    formatOffsetDisplay(offsetSeconds, includeFrames = true, defaultFps = 23.976) {
        if (typeof offsetSeconds !== 'number' || isNaN(offsetSeconds)) {
            return 'N/A';
        }

        const timecode = this.formatTimecode(offsetSeconds, defaultFps);

        if (!includeFrames) {
            return timecode;
        }

        const frames = Math.round(Math.abs(offsetSeconds) * defaultFps);
        const frameSign = offsetSeconds < 0 ? '-' : '+';
        const framesStr = `${frameSign}${frames}f @ ${defaultFps}fps`;

        return `${timecode} (${framesStr})`;
    }

    normalizeAnalysisResult(result, analysisId = null) {
        if (!result || typeof result !== 'object') return null;

        const normalized = { ...result };
        const consensus = normalized.consensus_offset || {};

        const offsetCandidate = normalized.offset_seconds ?? normalized.consensus_offset_seconds ?? consensus.offset_seconds;
        const confidenceCandidate = normalized.confidence ?? consensus.confidence;
        const qualityCandidate = normalized.quality_score ?? normalized.overall_confidence;

        if (offsetCandidate !== undefined) {
            const parsedOffset = Number(offsetCandidate);
            normalized.offset_seconds = Number.isFinite(parsedOffset) ? parsedOffset : 0;
        }

        if (confidenceCandidate !== undefined) {
            const parsedConfidence = Number(confidenceCandidate);
            normalized.confidence = Number.isFinite(parsedConfidence) ? parsedConfidence : 0;
        }

        if (qualityCandidate !== undefined) {
            const parsedQuality = Number(qualityCandidate);
            normalized.quality_score = Number.isFinite(parsedQuality) ? parsedQuality : 0;
        }

        if (!normalized.method_used && normalized.consensus_offset) {
            normalized.method_used = 'Consensus';
        }

        if (analysisId && !normalized.analysis_id) {
            normalized.analysis_id = analysisId;
        }

        return normalized;
    }

    /**
     * Detect frame rate from video file using ffprobe
     * @param {string} filePath - Path to the video file
     * @returns {Promise<number>} Detected frame rate or default (23.976)
     */
    async detectFrameRate(filePath) {
        try {
            const response = await fetch(`${this.FASTAPI_BASE}/files/probe?path=${encodeURIComponent(filePath)}`);
            if (!response.ok) {
                console.warn('Failed to probe file for frame rate');
                return 23.976;
            }
            const data = await response.json();
            if (data.video_summary && data.video_summary.frame_rate && data.video_summary.frame_rate > 0) {
                const fps = data.video_summary.frame_rate;
                console.log(`Detected frame rate: ${fps} fps`);
                return fps;
            }
        } catch (error) {
            console.warn('Error detecting frame rate:', error);
        }
        return 23.976; // Default fallback (industry standard)
    }

    // Simple logging replacement (since we removed the log UI)
    addLog(level, message) {
        const timestamp = new Date().toLocaleTimeString();
        // Console output
        console.log(`[${timestamp}] ${level.toUpperCase()}: ${message}`);
        // UI log entry
        const host = this.elements.logContainer;
        if (!host) {
            console.warn('Log container not found! Make sure #log-container exists in DOM');
            return;
        }
        if (host) {
            // Make log container visible
            host.style.display = 'block';

            // Remove empty state once
            const empty = host.querySelector('.log-empty');
            if (empty) empty.remove();
            const row = document.createElement('div');
            row.className = `log-entry ${level}`;
            row.innerHTML = `
                <span class=\"timestamp\">[${timestamp}]</span>
                <span class=\"level\">${level}</span>
                <span class=\"message\"></span>
            `;
            row.querySelector('.message').textContent = message;
            host.appendChild(row);
            if (this.autoScroll && typeof row.scrollIntoView === 'function') row.scrollIntoView({ behavior: 'smooth', block: 'end' });
        }
        // Header status indicator
        if (level === 'error') {
            this.elements.statusDot.className = 'status-dot error';
            this.elements.statusText.textContent = 'Error';
        } else if (level === 'warning') {
            this.elements.statusDot.className = 'status-dot warning';
            this.elements.statusText.textContent = 'Warning';
        } else if (level === 'success') {
            this.elements.statusDot.className = 'status-dot ready';
            this.elements.statusText.textContent = 'Ready';
        }
    }

    /**
     * Add a progress log entry with visual progress indicator
     * Updates existing progress entry for the same process, creates new one for different process
     * @param {string} message - Progress message
     * @param {number} percent - Progress percentage (0-100)
     */
    addProgressLog(message, percent = 0) {
        const timestamp = new Date().toLocaleTimeString();
        console.log(`[${timestamp}] PROGRESS (${percent}%): ${message}`);

        const host = this.elements.logContainer;
        if (!host) {
            console.warn('Log container not found!');
            return;
        }

        // Make log container visible
        host.style.display = 'block';

        // Remove empty state once
        const empty = host.querySelector('.log-empty');
        if (empty) empty.remove();

        // Extract process name from message (text before any colon, dash, or parenthesis)
        const processName = message.split(/[:(\-]/)[0].trim();

        // Find existing progress entry for the same process
        let existingProgress = null;
        const allProgress = host.querySelectorAll('.log-entry.progress');
        for (let i = allProgress.length - 1; i >= 0; i--) {
            const msgSpan = allProgress[i].querySelector('.message');
            if (msgSpan) {
                const existingProcessName = msgSpan.textContent.split(/[:(\-]/)[0].trim();
                if (existingProcessName === processName) {
                    existingProgress = allProgress[i];
                    break;
                }
            }
        }

        if (existingProgress) {
            // Update existing progress entry for this process
            const fillBar = existingProgress.querySelector('.progress-fill-mini');
            const percentSpan = existingProgress.querySelector('.progress-percent');
            const messageSpan = existingProgress.querySelector('.message');
            const timestampSpan = existingProgress.querySelector('.timestamp');

            if (fillBar) fillBar.style.width = `${percent}%`;
            if (percentSpan) percentSpan.textContent = `${percent}%`;
            if (messageSpan) messageSpan.textContent = message;
            if (timestampSpan) timestampSpan.textContent = `[${timestamp}]`;

            // If progress is complete, convert to success log
            if (percent >= 100) {
                existingProgress.classList.remove('progress');
                existingProgress.classList.add('success');
                existingProgress.querySelector('.level').textContent = 'SUCCESS';
                // Remove progress bar elements
                if (fillBar && fillBar.parentElement) fillBar.parentElement.remove();
                if (percentSpan) percentSpan.remove();
            }
        } else {
            // Create new progress entry for new process
            const row = document.createElement('div');
            row.className = 'log-entry progress';
            row.innerHTML = `
                <span class="timestamp">[${timestamp}]</span>
                <span class="level">PROGRESS</span>
                <span class="progress-bar-mini">
                    <span class="progress-fill-mini" style="width: ${percent}%"></span>
                </span>
                <span class="progress-percent">${percent}%</span>
                <span class="message"></span>
            `;
            row.querySelector('.message').textContent = message;
            host.appendChild(row);

            // Auto-scroll to new entry
            if (this.autoScroll && typeof row.scrollIntoView === 'function') {
                row.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }
        }
    }

    // Batch Processing Methods
    addToBatchQueue(clearSelections = true) {
        if (!this.selectedMaster || !this.selectedDub) {
            this.addLog('warning', 'Please select both master and dub files before adding to batch');
            return null;
        }
        
        // Check for duplicates
        const duplicate = this.batchQueue.find(item => 
            item.master.path === this.selectedMaster.path && 
            item.dub.path === this.selectedDub.path
        );
        
        if (duplicate) {
            this.addLog('warning', 'File pair already exists in batch queue');
            return duplicate;
        }
        
        const batchItem = {
            id: Date.now(),
            master: {...this.selectedMaster},
            dub: {...this.selectedDub},
            status: 'queued',
            progress: 0,
            result: null,
            error: null,
            timestamp: new Date().toISOString()
        };
        
        this.batchQueue.push(batchItem);
        this.updateBatchTable();
        this.updateBatchSummary();
        // Persist queue state
        this.persistBatchQueue().catch(err => console.warn('Persist batch queue failed:', err));
        this.addLog('success', `Added to batch: ${this.selectedMaster.name} + ${this.selectedDub.name}`);
        
        // Clear selections only if requested (not when called from startAnalysis)
        if (clearSelections) {
            this.selectedMaster = null;
            this.selectedDub = null;
            this.updateFileSlots();
            this.elements.analyzeBtn.disabled = true;
        }
        
        return batchItem;
    }

    // Handle CSV file upload for batch processing
    async handleCsvUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Reset the file input so the same file can be selected again
        event.target.value = '';

        this.addLog('info', `Reading CSV file: ${file.name}`);

        try {
            const text = await file.text();
            const lines = text.split('\n').map(line => line.trim()).filter(line => line);

            if (lines.length === 0) {
                this.addLog('error', 'CSV file is empty');
                return;
            }

            // Parse header
            const header = lines[0].toLowerCase().split(',').map(h => h.trim());
            const masterIdx = header.indexOf('master_file');
            const dubIdx = header.indexOf('dub_file');

            // Detect componentized CSV format
            const hasComponentFiles = header.includes('component_files');
            const componentColumns = header.filter(h => h.startsWith('component_')).filter(h => h !== 'component_files');
            const hasArefWildFormat = header.includes('aref') && header.includes('wild');
            const isComponentized = hasComponentFiles || componentColumns.length > 0 || hasArefWildFormat;

            if (isComponentized) {
                // Handle componentized CSV format
                this.addLog('info', 'Detected componentized CSV format');
                
                // For AREF/Wild format, try API-based import first for better validation
                if (hasArefWildFormat) {
                    try {
                        await this.importCsvViaApi(file);
                        return;
                    } catch (apiError) {
                        this.addLog('warning', 'API import unavailable, using client-side parsing');
                    }
                }
                
                await this.handleComponentizedCsvUpload(text, lines, header);
                return;
            }

            // Standard CSV format validation
            const episodeIdx = header.indexOf('episode_name');
            const autoRepairIdx = header.indexOf('auto_repair');
            const keepDurationIdx = header.indexOf('keep_duration');

            if (masterIdx === -1 || dubIdx === -1) {
                this.addLog('error', 'CSV must contain "master_file" and "dub_file" columns');
                this.addLog('info', 'Expected format: master_file,dub_file,episode_name,auto_repair,keep_duration,notes');
                this.addLog('info', 'Or componentized format: master_file,component_0,component_1,component_2,...');
                return;
            }

            // Parse data rows
            const items = [];
            const errors = [];

            for (let i = 1; i < lines.length; i++) {
                const line = lines[i];
                if (!line) continue;

                const values = this.parseCsvLine(line);
                const masterPath = values[masterIdx]?.trim();
                const dubPath = values[dubIdx]?.trim();
                const episodeName = episodeIdx >= 0 ? values[episodeIdx]?.trim() : '';

                // Parse repair settings (default to false for auto_repair, true for keep_duration)
                const autoRepairStr = autoRepairIdx >= 0 ? values[autoRepairIdx]?.trim().toLowerCase() : '';
                const keepDurationStr = keepDurationIdx >= 0 ? values[keepDurationIdx]?.trim().toLowerCase() : '';

                const autoRepair = autoRepairStr === 'true' || autoRepairStr === '1' || autoRepairStr === 'yes';
                const keepDuration = keepDurationStr === 'false' || keepDurationStr === '0' || keepDurationStr === 'no' ? false : true;

                if (!masterPath || !dubPath) {
                    errors.push(`Line ${i + 1}: Missing master or dub file path`);
                    continue;
                }

                // Extract file names from paths
                const masterName = masterPath.split('/').pop();
                const dubName = dubPath.split('/').pop();

                items.push({
                    master: { name: masterName, path: masterPath },
                    dub: { name: dubName, path: dubPath },
                    episodeName: episodeName || `${masterName} + ${dubName}`,
                    autoRepair: autoRepair,
                    keepDuration: keepDuration
                });
            }

            if (errors.length > 0) {
                this.addLog('warning', `CSV parsing errors (${errors.length}):`);
                errors.slice(0, 5).forEach(err => this.addLog('warning', err));
                if (errors.length > 5) {
                    this.addLog('warning', `... and ${errors.length - 5} more errors`);
                }
            }

            if (items.length === 0) {
                this.addLog('error', 'No valid items found in CSV');
                return;
            }

            // Add items to batch queue
            let addedCount = 0;
            let skippedCount = 0;

            for (const item of items) {
                // Check for duplicates
                const duplicate = this.batchQueue.find(qi =>
                    qi.master.path === item.master.path &&
                    qi.dub.path === item.dub.path
                );

                if (duplicate) {
                    skippedCount++;
                    continue;
                }

                const batchItem = {
                    id: Date.now() + addedCount, // Ensure unique IDs
                    master: item.master,
                    dub: item.dub,
                    status: 'queued',
                    progress: 0,
                    result: null,
                    error: null,
                    timestamp: new Date().toISOString(),
                    autoRepair: item.autoRepair || false,
                    keepDuration: item.keepDuration !== undefined ? item.keepDuration : true
                };

                this.batchQueue.push(batchItem);
                addedCount++;

                // Small delay to ensure unique timestamps
                await new Promise(resolve => setTimeout(resolve, 1));
            }

            this.updateBatchTable();
            this.updateBatchSummary();
            await this.persistBatchQueue();

            this.addLog('success', `CSV loaded: ${addedCount} items added to batch queue`);
            if (skippedCount > 0) {
                this.addLog('info', `Skipped ${skippedCount} duplicate items`);
            }

        } catch (error) {
            this.addLog('error', `Failed to parse CSV: ${error.message}`);
            console.error('CSV upload error:', error);
        }
    }

    /**
     * Handle componentized CSV upload
     * Supports three formats:
     * 1. Grouped format: AREF,Wild (rows with same AREF are grouped)
     * 2. Multi-column: master_file,component_0,component_1,component_2,...
     * 3. Array-style: master_file,component_files (semicolon-separated)
     */
    async handleComponentizedCsvUpload(text, lines, header) {
        try {
            // Check for grouped format (AREF/Wild columns)
            const arefIdx = header.findIndex(h => h.toLowerCase() === 'aref');
            const wildIdx = header.findIndex(h => h.toLowerCase() === 'wild');

            if (arefIdx >= 0 && wildIdx >= 0) {
                // Use grouped format parsing
                return await this.handleGroupedComponentizedCsv(lines, arefIdx, wildIdx);
            }

            // Fall back to existing formats
            const masterIdx = header.indexOf('master_file');
            const componentFilesIdx = header.indexOf('component_files');

            // Find all component columns (component_0, component_1, etc.)
            const componentIndices = [];
            header.forEach((col, idx) => {
                if (col.startsWith('component_') && col !== 'component_files') {
                    componentIndices.push(idx);
                }
            });

            if (masterIdx === -1) {
                this.addLog('error', 'Componentized CSV must contain "master_file" column (or use AREF/Wild format)');
                return;
            }

            if (componentFilesIdx === -1 && componentIndices.length === 0) {
                this.addLog('error', 'Componentized CSV must contain either "component_files" or "component_0, component_1,..." columns');
                return;
            }

            const items = [];
            const errors = [];

            // Parse data rows
            for (let i = 1; i < lines.length; i++) {
                const line = lines[i];
                if (!line) continue;

                const values = this.parseCsvLine(line);
                const masterPath = values[masterIdx]?.trim();

                if (!masterPath) {
                    errors.push(`Line ${i + 1}: Missing master file path`);
                    continue;
                }

                // Extract component file paths
                let componentPaths = [];

                if (componentFilesIdx >= 0) {
                    // Array-style format: semicolon-separated list
                    const componentFilesStr = values[componentFilesIdx]?.trim();
                    if (componentFilesStr) {
                        componentPaths = componentFilesStr
                            .split(';')
                            .map(p => p.trim())
                            .filter(p => p);
                    }
                } else {
                    // Multi-column format: component_0, component_1, etc.
                    componentIndices.forEach(idx => {
                        const path = values[idx]?.trim();
                        if (path) {
                            componentPaths.push(path);
                        }
                    });
                }

                if (componentPaths.length === 0) {
                    errors.push(`Line ${i + 1}: No component files found`);
                    continue;
                }

                // Extract file names and create component objects
                const masterName = masterPath.split('/').pop();
                const components = componentPaths.map((path, index) => {
                    const name = path.split('/').pop();
                    return {
                        name: name,
                        path: path,
                        type: 'file',
                        label: this.extractComponentLabel(name) || `Component ${index + 1}`,
                        index: index
                    };
                });

                items.push({
                    master: { name: masterName, path: masterPath },
                    components: components
                });
            }

            if (errors.length > 0) {
                this.addLog('warning', `CSV parsing errors (${errors.length}):`);
                errors.slice(0, 5).forEach(err => this.addLog('warning', err));
                if (errors.length > 5) {
                    this.addLog('warning', `... and ${errors.length - 5} more errors`);
                }
            }

            if (items.length === 0) {
                this.addLog('error', 'No valid componentized items found in CSV');
                return;
            }

            // Add items to batch queue
            let addedCount = 0;
            let skippedCount = 0;

            for (const item of items) {
                // Check for duplicates
                const duplicate = this.batchQueue.find(qi =>
                    qi.type === 'componentized' &&
                    qi.master.path === item.master.path &&
                    JSON.stringify(qi.components.map(c => c.path).sort()) ===
                    JSON.stringify(item.components.map(c => c.path).sort())
                );

                if (duplicate) {
                    skippedCount++;
                    continue;
                }

                const batchItem = {
                    id: Date.now() + addedCount,
                    type: 'componentized',
                    master: item.master,
                    components: item.components,
                    status: 'queued',
                    progress: 0,
                    componentResults: [],
                    offsetMode: this.componentizedOffsetMode,
                    error: null,
                    timestamp: new Date().toISOString(),
                    frameRate: this.detectedFrameRate
                };

                this.batchQueue.push(batchItem);
                addedCount++;

                // Small delay to ensure unique timestamps
                await new Promise(resolve => setTimeout(resolve, 1));
            }

            this.updateBatchTable();
            this.updateBatchSummary();
            await this.persistBatchQueue();

            this.addLog('success', `Componentized CSV loaded: ${addedCount} items added to batch queue`);
            if (skippedCount > 0) {
                this.addLog('info', `Skipped ${skippedCount} duplicate items`);
            }

            // Log summary
            const totalComponents = items.reduce((sum, item) => sum + item.components.length, 0);
            this.addLog('info', `Total components to analyze: ${totalComponents}`);

        } catch (error) {
            this.addLog('error', `Failed to parse componentized CSV: ${error.message}`);
            console.error('Componentized CSV upload error:', error);
        }
    }

    /**
     * Handle grouped componentized CSV format (AREF/Wild columns)
     * Rows with the same AREF are automatically grouped into one componentized item
     * 
     * Example CSV:
     * AREF,Wild
     * /path/master.mov,/path/wild_Lt.wav
     * /path/master.mov,/path/wild_Rt.wav
     * /path/master.mov,/path/wild_C.wav
     * 
     * Results in one componentized item with 3 components
     */
    async handleGroupedComponentizedCsv(lines, arefIdx, wildIdx) {
        try {
            const groupedItems = new Map();
            const errors = [];

            // Parse data rows and group by AREF (master)
            for (let i = 1; i < lines.length; i++) {
                const line = lines[i];
                if (!line || !line.trim()) continue;

                const values = this.parseCsvLine(line);
                const masterPath = values[arefIdx]?.trim();
                const wildPath = values[wildIdx]?.trim();

                if (!masterPath) {
                    errors.push(`Line ${i + 1}: Missing AREF (master) path`);
                    continue;
                }

                if (!wildPath) {
                    errors.push(`Line ${i + 1}: Missing Wild (component) path`);
                    continue;
                }

                // Group by master path
                if (!groupedItems.has(masterPath)) {
                    groupedItems.set(masterPath, []);
                }
                groupedItems.get(masterPath).push(wildPath);
            }

            // Show parsing errors
            if (errors.length > 0) {
                this.addLog('warning', `CSV parsing warnings (${errors.length}):`);
                errors.slice(0, 5).forEach(err => this.addLog('warning', err));
                if (errors.length > 5) {
                    this.addLog('warning', `... and ${errors.length - 5} more`);
                }
            }

            if (groupedItems.size === 0) {
                this.addLog('error', 'No valid items found in grouped CSV');
                return;
            }

            // Convert grouped items to batch items
            const items = [];
            for (const [masterPath, componentPaths] of groupedItems) {
                const masterName = masterPath.split('/').pop();
                const components = componentPaths.map((path, index) => {
                    const name = path.split('/').pop();
                    return {
                        name: name,
                        path: path,
                        type: 'file',
                        label: this.extractComponentLabel(name) || `Component ${index + 1}`,
                        index: index
                    };
                });

                items.push({
                    master: { name: masterName, path: masterPath },
                    components: components
                });
            }

            // Add items to batch queue
            let addedCount = 0;
            let skippedCount = 0;

            for (const item of items) {
                // Check for duplicates
                const duplicate = this.batchQueue.find(qi =>
                    qi.type === 'componentized' &&
                    qi.master.path === item.master.path &&
                    JSON.stringify(qi.components.map(c => c.path).sort()) ===
                    JSON.stringify(item.components.map(c => c.path).sort())
                );

                if (duplicate) {
                    skippedCount++;
                    continue;
                }

                const batchItem = {
                    id: Date.now() + addedCount,
                    type: 'componentized',
                    master: item.master,
                    components: item.components,
                    status: 'queued',
                    progress: 0,
                    componentResults: [],
                    offsetMode: this.componentizedOffsetMode,
                    error: null,
                    timestamp: new Date().toISOString(),
                    frameRate: this.detectedFrameRate
                };

                this.batchQueue.push(batchItem);
                addedCount++;

                // Small delay to ensure unique timestamps
                await new Promise(resolve => setTimeout(resolve, 1));
            }

            this.updateBatchTable();
            this.updateBatchSummary();
            await this.persistBatchQueue();

            this.addLog('success', `Grouped CSV loaded: ${addedCount} items added (${groupedItems.size} masters with components grouped)`);
            if (skippedCount > 0) {
                this.addLog('info', `Skipped ${skippedCount} duplicate items`);
            }

            // Log summary
            const totalComponents = items.reduce((sum, item) => sum + item.components.length, 0);
            this.addLog('info', `Total: ${items.length} masters, ${totalComponents} components`);

        } catch (error) {
            this.addLog('error', `Failed to parse grouped CSV: ${error.message}`);
            console.error('Grouped CSV upload error:', error);
        }
    }

    /**
     * Import CSV via server-side API for validation
     * This provides file existence checks and better error handling
     */
    async importCsvViaApi(file) {
        try {
            this.addLog('info', `Importing CSV via API: ${file.name}`);
            
            const formData = new FormData();
            formData.append('file', file);
            formData.append('auto_queue', 'true');
            
            const response = await fetch(`${this.FASTAPI_BASE}/csv/import`, {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }
            
            const result = await response.json();
            
            if (!result.success) {
                this.addLog('error', `CSV import failed: ${result.errors?.join(', ') || 'Unknown error'}`);
                return;
            }
            
            // Log any validation errors
            if (result.errors && result.errors.length > 0) {
                this.addLog('warning', `CSV import warnings (${result.errors.length}):`);
                result.errors.slice(0, 5).forEach(err => this.addLog('warning', err));
                if (result.errors.length > 5) {
                    this.addLog('warning', `... and ${result.errors.length - 5} more`);
                }
            }
            
            // Add jobs from the API response to the batch queue
            let addedCount = 0;
            let skippedCount = 0;
            
            for (const job of result.jobs) {
                // Check for duplicates
                const isDuplicate = this.batchQueue.some(qi => {
                    if (job.type === 'componentized') {
                        return qi.type === 'componentized' && 
                               qi.master.path === job.master.path &&
                               JSON.stringify(qi.components?.map(c => c.path).sort()) ===
                               JSON.stringify(job.components?.map(c => c.path).sort());
                    } else {
                        return qi.master.path === job.master.path &&
                               qi.dub?.path === job.components[0]?.path;
                    }
                });
                
                if (isDuplicate) {
                    skippedCount++;
                    continue;
                }
                
                // Create batch item from API job
                const batchItem = {
                    id: Date.now() + addedCount,
                    type: job.type,
                    master: job.master,
                    status: 'queued',
                    progress: 0,
                    error: null,
                    timestamp: new Date().toISOString(),
                    frameRate: this.detectedFrameRate,
                    offsetMode: this.componentizedOffsetMode
                };
                
                if (job.type === 'componentized') {
                    batchItem.components = job.components;
                    batchItem.componentResults = [];
                } else {
                    batchItem.dub = job.components[0];
                }
                
                this.batchQueue.push(batchItem);
                addedCount++;
                
                await new Promise(resolve => setTimeout(resolve, 1));
            }
            
            this.updateBatchTable();
            this.updateBatchSummary();
            await this.persistBatchQueue();
            
            this.addLog('success', `CSV imported: ${addedCount} jobs added (${result.standard_jobs} standard, ${result.componentized_jobs} componentized)`);
            if (skippedCount > 0) {
                this.addLog('info', `Skipped ${skippedCount} duplicate items`);
            }
            
        } catch (error) {
            this.addLog('error', `CSV API import failed: ${error.message}`);
            console.error('CSV API import error:', error);
            // Fall back to client-side parsing
            this.addLog('info', 'Falling back to client-side parsing...');
        }
    }

    // Parse a CSV line handling quoted values
    parseCsvLine(line) {
        const values = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const char = line[i];

            if (char === '"') {
                inQuotes = !inQuotes;
            } else if (char === ',' && !inQuotes) {
                values.push(current);
                current = '';
            } else {
                current += char;
            }
        }

        values.push(current); // Push the last value
        return values;
    }

    // Debug method to add a test entry with results
    addTestBatchEntry() {
        const testItem = {
            id: Date.now(),
            master: {
                name: 'DunkirkEC_TheInCameraApproach1_ProRes.mov',
                path: '/mnt/data/amcmurray/_insync_master_files/DunkirkEC_TheInCameraApproach1_ProRes.mov'
            },
            dub: {
                name: 'DunkirkEC_TheInCameraApproach1_ProRes_5sec23f.mov', 
                path: '/mnt/data/amcmurray/_outofsync_master_files/DunkirkEC_TheInCameraApproach1_ProRes_5sec23f.mov'
            },
            status: 'completed',
            progress: 100,
            result: {
                offset_seconds: -5.990748299319728,
                confidence: 1.0,
                method_used: 'Consensus (mfcc primary)',
                quality_score: 0.47746863066345163,
                correlation_peak: 4683.976433616792,
                analysis_methods: ['mfcc'],
                recommendations: [
                    '❌ CRITICAL: Sync offset exceeds acceptable limits (>100ms) - Correction required',
                    '🔬 HIGH CONFIDENCE: Analysis results are highly reliable',
                    '🔧 CORRECTION: Delay dub audio by 5990.7ms'
                ],
                technical_details: {
                    analysis_methods_used: ['mfcc'],
                    frame_rates: [43.06640625],
                    correlation_peaks: { mfcc: 4683.976433616792 },
                    quality_scores: { mfcc: 0.47746863066345163 },
                    confidence_scores: { mfcc: 1.0 },
                    method_agreement_rate: 1.0
                }
            },
            error: null,
            timestamp: new Date().toISOString()
        };
        
        this.batchQueue.push(testItem);
        this.updateBatchTable();
        this.updateBatchSummary();
        this.addLog('info', 'Added test batch entry with real analysis results - click expand arrow to see new features');
    }
    
    async processBatchQueue() {
        console.log('[processBatchQueue] Called');
        console.log('[processBatchQueue] batchQueue length:', this.batchQueue.length);
        console.log('[processBatchQueue] batchQueue items:', this.batchQueue.map(item => ({
            id: item.id,
            master: item.master?.name,
            status: item.status,
            type: item.type
        })));

        if (this.batchQueue.length === 0) {
            this.addLog('warning', 'Batch queue is empty');
            return;
        }

        if (this.batchProcessing) {
            this.addLog('warning', 'Batch processing already in progress');
            return;
        }

        this.batchProcessing = true;
        this.elements.processBatch.disabled = true;

        const queuedItems = this.batchQueue.filter(item => item.status === 'queued');
        const totalItems = queuedItems.length;
        let completedCount = 0;

        console.log('[processBatchQueue] Queued items:', queuedItems.length);
        console.log('[processBatchQueue] All statuses:', this.batchQueue.map(item => item.status));

        if (totalItems === 0) {
            this.addLog('warning', `No items with 'queued' status found. Current statuses: ${this.batchQueue.map(item => item.status).join(', ')}`);
            this.batchProcessing = false;
            this.elements.processBatch.disabled = false;
            return;
        }

        this.addLog('info', `Starting parallel batch processing: ${totalItems} items with ${this.maxConcurrentJobs} concurrent jobs`);
        this.elements.processingStatus.textContent = `Processing 0/${totalItems} (${this.maxConcurrentJobs} parallel)...`;
        
        // Process items in parallel with controlled concurrency
        const processItem = async (item, itemIndex) => {
            const itemId = item.id;
            this.activeJobs.set(itemId, item);
            this.updateActiveJobsDisplay(); // Show in Console Status quadrant

            try {
                // Update status
                item.status = 'processing';
                item.progress = 0;
                this.updateBatchTableRow(item);
                this.updateBatchSummary();

                this.addLog('info', `[Job ${this.activeJobs.size}/${this.maxConcurrentJobs}] Processing: ${item.master.name}`);

                // Check if this is a componentized item
                if (item.type === 'componentized') {
                    // Use componentized analysis method
                    await this.analyzeComponentizedItem(item);
                } else {
                    // Standard single dub analysis
                    const itemFrameRate = await this.detectFrameRate(item.master.path);

                    // Build current configuration
                    const cfg = this.getAnalysisConfig();

                    // Map UI method names to API method names
                    // UI uses 'gpu' for GPU-accelerated AI, API uses 'ai'
                    let methods = Array.isArray(cfg.methods) && cfg.methods.length ? cfg.methods : ['mfcc'];
                    methods = methods.map(m => m === 'gpu' ? 'ai' : m);
                    // Filter out invalid methods (fingerprint is handled separately)
                    const validMethods = ['mfcc', 'onset', 'spectral', 'correlation', 'ai'];
                    methods = methods.filter(m => validMethods.includes(m));
                    if (methods.length === 0) methods = ['mfcc']; // fallback

                    // Start analysis (async - returns immediately with analysis_id)
                    const startResponse = await fetch('/api/v1/analysis/sync', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            master_file: item.master.path,
                            dub_file: item.dub.path,
                            methods: methods,
                            ai_model: cfg.aiModel || 'wav2vec2',
                            enable_ai: methods.includes('ai') || !!cfg.enableGpu,
                            channel_strategy: cfg.channelStrategy || 'mono_downmix',
                            frame_rate: itemFrameRate
                        })
                    });

                    const startResult = await startResponse.json();
                    if (!startResponse.ok || !startResult.analysis_id) {
                        throw new Error(startResult.detail || startResult.error || 'Failed to start analysis');
                    }

                    const analysisId = startResult.analysis_id;
                    this.addLog('info', `🚀 Analysis started: ${analysisId}`);

                    // Poll for progress until complete
                    let result = null;
                    let lastProgressMsg = '';
                    const maxWaitMs = 600000; // 10 minute timeout
                    const pollIntervalMs = 1000; // Poll every second
                    const startTime = Date.now();

                    while (Date.now() - startTime < maxWaitMs) {
                        const statusResponse = await fetch(`/api/v1/analysis/${analysisId}`);
                        const statusData = await statusResponse.json();

                        if (statusData.progress !== undefined) {
                            item.progress = Math.floor(statusData.progress);
                            this.updateBatchTableRow(item);
                        }

                        // Log progress messages (de-dup)
                        if (statusData.status_message && statusData.status_message !== lastProgressMsg) {
                            lastProgressMsg = statusData.status_message;
                            this.addLog('info', `📊 ${item.master.name.substring(0, 30)}... ${item.progress}% - ${lastProgressMsg}`);
                        }

                        const status = statusData.status?.value || statusData.status;
                        if (status === 'completed') {
                            result = { success: true, result: statusData.result, analysis_id: analysisId };
                            break;
                        } else if (status === 'failed') {
                            throw new Error(statusData.error || 'Analysis failed');
                        }

                        await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
                    }

                    if (!result) {
                        throw new Error('Analysis timed out');
                    }

                    item.progress = 100;

                    if (result.success) {
                        item.status = 'completed';
                        // Normalize the result to ensure offset_seconds is at top level
                        item.result = this.normalizeAnalysisResult(result.result, result.analysis_id);
                        item.frameRate = itemFrameRate;
                        const offsetSeconds = item.result?.offset_seconds ?? item.result?.consensus_offset?.offset_seconds ?? 0;
                        this.addLog('success', `✓ Completed: ${item.master.name} → ${this.formatOffsetDisplay(offsetSeconds, true, itemFrameRate)}`);
                    } else {
                        item.status = 'failed';
                        // Handle error being an object or string
                        let errorMsg = result.error || result.detail || 'Unknown error';
                        if (typeof errorMsg === 'object') {
                            errorMsg = errorMsg.message || errorMsg.detail || JSON.stringify(errorMsg);
                        }
                        item.error = errorMsg;
                        this.addLog('error', `✗ Failed: ${item.master.name} - ${item.error}`);
                    }
                }

            } catch (error) {
                item.status = 'failed';
                item.error = error.message;
                item.progress = 0;
                this.addLog('error', `✗ Error: ${item.master.name} - ${error.message}`);
            } finally {
                this.activeJobs.delete(itemId);
                completedCount++;
                this.elements.processingStatus.textContent = `Processing ${completedCount}/${totalItems} (${this.activeJobs.size} active)...`;
                this.updateBatchTableRow(item);
                this.updateBatchSummary();
                this.updateActiveJobsDisplay(); // Update Console Status quadrant
                // Persist after each completion
                this.persistBatchQueue().catch(() => {});
            }
        };

        // Parallel execution with controlled concurrency
        const runWithConcurrency = async (items, limit) => {
            const executing = new Set();
            
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                
                // Create promise for this item
                const promise = processItem(item, i).then(() => {
                    executing.delete(promise);
                });
                
                executing.add(promise);
                
                // If we've reached the concurrency limit, wait for one to complete
                if (executing.size >= limit) {
                    await Promise.race(executing);
                }
            }
            
            // Wait for all remaining jobs to complete
            await Promise.all(executing);
        };

        await runWithConcurrency(queuedItems, this.maxConcurrentJobs);
        
        this.batchProcessing = false;
        this.currentBatchIndex = -1;
        this.elements.processBatch.disabled = false;
        this.elements.processingStatus.textContent = `Complete (${totalItems} items)`;
        this.addLog('success', `🎉 Batch processing completed: ${totalItems} items processed`);
        await this.persistBatchQueue().catch(() => {});
    }

    async analyzeComponentizedItem(item) {
        try {
            this.addLog('info', `Processing componentized item: ${item.master.name} with ${item.components.length} components`);

            // Detect frame rate for the master file
            const itemFrameRate = await this.detectFrameRate(item.master.path);
            item.frameRate = itemFrameRate;
            this.addLog('info', `Using frame rate: ${itemFrameRate} fps`);

            // Initialize component results array
            item.componentResults = [];
            item.status = 'processing';
            item.progress = 0;
            this.updateBatchTableRow(item);
            let offsetMode = (item.offsetMode || this.componentizedOffsetMode || 'channel_aware').toLowerCase();
            
            // Force valid mode - use channel_aware for any unrecognized mode
            if (!['mixdown', 'anchor', 'channel_aware'].includes(offsetMode)) {
                console.warn(`Unknown offset mode "${offsetMode}", defaulting to channel_aware`);
                offsetMode = 'channel_aware';
            }
            item.offsetMode = offsetMode;

            // All componentized items use background processing
            if (true) { // Always use background job path for componentized
                this.addLog('info', `Running ${offsetMode} alignment for componentized item (background processing)...`);
                item.progress = 5;
                this.updateBatchTableRow(item);

                try {
                    // Start the background job using async endpoint
                    // Determine methods - exclusive modes (GPU, Fingerprint) take priority
                    const gpuEnabled = this.elements.methodGpu && this.elements.methodGpu.checked;
                    const fingerprintEnabled = this.elements.methodFingerprint && this.elements.methodFingerprint.checked;
                    let methodsToUse;
                    if (gpuEnabled) {
                        methodsToUse = ['gpu'];
                    } else if (fingerprintEnabled) {
                        methodsToUse = ['fingerprint'];
                    } else {
                        methodsToUse = this.currentMethods || ['mfcc', 'onset', 'spectral'];
                    }
                    
                    console.log(`[processBatchQueue] GPU: ${gpuEnabled}, Fingerprint: ${fingerprintEnabled}, methods: ${methodsToUse}`);
                    
                    // Check if verbose logging is enabled
                    const verboseLogging = this.elements.verboseLogging?.checked || false;
                    
                    const startResponse = await fetch('/api/v1/analysis/componentized/async', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            master: item.master.path,
                            components: item.components,
                            offset_mode: offsetMode,
                            methods: methodsToUse,
                            frame_rate: itemFrameRate,
                            verbose: verboseLogging
                        })
                    });

                    const startResult = await startResponse.json();
                    
                    if (!startResult.success) {
                        throw new Error(startResult.error || 'Failed to start analysis');
                    }

                    // Use the Celery task_id returned from server (NOT a local ID)
                    const jobId = startResult.job_id;
                    
                    // Store the job ID in the batch item for reconnection after refresh
                    item.analysisId = jobId;
                    item.jobId = jobId;
                    this.persistBatchQueue().catch(() => {}); // Save immediately
                    
                    this.addLog('info', `🚀 Background job started: ${jobId.substring(0, 8)}...`);
                    this.addLog('info', `⏳ Waiting for analysis to complete (polling every 1s)...`);

                    // Poll for job completion with timeout (30 min for long files)
                    const maxPollTime = 30 * 60 * 1000; // 30 minutes max
                    const pollInterval = 1000; // Poll every 1 second
                    const startTime = Date.now();
                    
                    const pollForResult = () => {
                        return new Promise((resolve, reject) => {
                            const poll = async () => {
                                try {
                                    // Check if timed out
                                    if (Date.now() - startTime > maxPollTime) {
                                        reject(new Error('Analysis timed out after 10 minutes'));
                                        return;
                                    }

                                    // Poll job status
                                    const jobResponse = await fetch(`/api/v1/jobs/${jobId}`);
                                    const jobData = await jobResponse.json();

                                    if (!jobData.success && jobData.error === 'Job not found') {
                                        // Job may not be registered yet, keep polling
                                        setTimeout(poll, pollInterval);
                                        return;
                                    }

                                    // Update progress and show in console
                                    if (jobData.progress > 0 || jobData.status_message) {
                                        const oldProgress = item.progress || 0;
                                        item.progress = jobData.progress || oldProgress;
                                        item.progressMessage = jobData.status_message;
                                        this.updateBatchTableRow(item);
                                        this.updateActiveJobsDisplay();
                                        
                                        // Log progress updates to console (throttled)
                                        const progressDiff = item.progress - oldProgress;
                                        if (progressDiff >= 5 || jobData.status_message !== item.lastStatusMessage) {
                                            this.addLog('info', `⏳ ${item.master.name.substring(0, 30)}... ${item.progress}% - ${jobData.status_message || 'Processing...'}`);
                                            item.lastStatusMessage = jobData.status_message;
                                        }
                                    }

                                    // Check job status
                                    if (jobData.status === 'completed') {
                                        resolve(jobData);
                                    } else if (jobData.status === 'failed') {
                                        reject(new Error(jobData.error || 'Analysis failed'));
                                    } else {
                                        // Still processing, poll again
                                        setTimeout(poll, pollInterval);
                                    }
                                } catch (error) {
                                    // Network error, retry
                                    console.error('Poll error:', error);
                                    setTimeout(poll, pollInterval * 2); // Back off slightly
                                }
                            };
                            poll();
                        });
                    };

                    // Wait for job to complete
                    const jobResult = await pollForResult();
                    
                    item.progress = 100;
                    this.updateBatchTableRow(item);

                    // Process results
                    const result = jobResult.result;
                    if (result) {
                        const componentResults = Array.isArray(result.component_results)
                            ? result.component_results.filter(r => r !== null && r !== undefined)
                            : [];
                        item.componentResults = componentResults.map((res, idx) => ({
                            component: res?.component || item.components[idx]?.label || `C${idx + 1}`,
                            componentName: res?.componentName || item.components[idx]?.name || `component_${idx + 1}`,
                            channel_type: res?.channel_type || null,
                            optimal_methods: res?.optimal_methods || null,
                            offset_seconds: res?.offset_seconds ?? 0,
                            confidence: res?.confidence ?? 0,
                            frameRate: itemFrameRate,
                            quality_score: res?.quality_score ?? 0,
                            method_used: res?.method_used || null,
                            method_results: res?.method_results || [],
                            analysis_id: res?.analysis_id,
                            status: res?.status || 'completed',
                            findings: res?.findings || [],
                            bars_tone_detected: res?.bars_tone_detected || false,
                            bars_tone_duration: res?.bars_tone_duration || 0,
                            component_duration: res?.component_duration || null,
                        }));
                        item.mixdownOffsetSeconds = result.mixdown_offset_seconds ?? null;
                        item.mixdownConfidence = result.mixdown_confidence ?? null;
                        item.votedOffsetSeconds = result.voted_offset_seconds ?? null;
                        item.voteAgreement = result.vote_agreement ?? null;
                        item.offsetMode = result.offset_mode || offsetMode;
                        item.masterFindings = result.master_findings || [];
                        item.masterDuration = result.master_duration || null;

                        // For channel_aware mode, use voted offset as summary
                        const summaryOffset = item.votedOffsetSeconds ?? item.mixdownOffsetSeconds ?? item.componentResults[0]?.offset_seconds ?? 0;

                        // Log additional info for channel_aware mode
                        if (offsetMode === 'channel_aware' && result.vote_agreement !== undefined) {
                            this.addLog(
                                'success',
                                `Channel-aware completed: ${this.formatOffsetDisplay(summaryOffset, true, itemFrameRate)} (${Math.round(result.vote_agreement * 100)}% agreement)`
                            );
                        } else {
                            this.addLog(
                                'success',
                                `Componentized ${item.offsetMode} completed: ${this.formatOffsetDisplay(summaryOffset, true, itemFrameRate)}`
                            );
                        }
                    } else {
                        throw new Error('No result data from completed job');
                    }
                } catch (error) {
                    item.status = 'failed';
                    item.error = error.message;
                    this.addLog('error', `Componentized ${offsetMode} failed: ${error.message}`);
                }
            } else {
                // Standard per-component analysis with progress tracking
                const cfg = this.getAnalysisConfig();
                const totalComponents = item.components.length;
                let completedComponents = 0;

                const analysisPromises = item.components.map(async (component, index) => {
                    try {
                        this.addLog('info', `Analyzing component ${component.label} (${index + 1}/${totalComponents})`);

                        // Update progress: each component is a portion of the total
                        const startProgress = (index / totalComponents) * 100;
                        item.progress = startProgress;
                        item.currentComponent = `${component.label} (${index + 1}/${totalComponents})`;
                        this.updateBatchTableRow(item);

                        const response = await fetch('/api/v1/analysis/sync', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                master_file: item.master.path,
                                dub_file: component.path,
                                methods: Array.isArray(cfg.methods) && cfg.methods.length ? cfg.methods : ['mfcc'],
                                ai_model: cfg.aiModel || 'wav2vec2',
                                enable_ai: !!cfg.enableGpu,
                                sample_rate: 22050,
                                frame_rate: itemFrameRate
                            })
                        });

                        const result = await response.json();
                        
                        // Check for HTTP errors
                        if (!response.ok) {
                            const errorMsg = result.detail || result.error || result.message || `HTTP ${response.status}`;
                            throw new Error(errorMsg);
                        }

                        // Update completion progress
                        completedComponents++;
                        item.progress = Math.round((completedComponents / totalComponents) * 100);
                        item.currentComponent = `${component.label} complete (${completedComponents}/${totalComponents})`;
                        this.updateBatchTableRow(item);

                        if (result.success && result.result) {
                            this.addLog('success', `✓ Component ${component.label} (${completedComponents}/${totalComponents}): ${this.formatOffsetDisplay(result.result?.offset_seconds ?? 0, true, itemFrameRate)}`);

                            return {
                                component: component.label,
                                componentName: component.name,
                                offset_seconds: result.result?.offset_seconds ?? 0,
                                confidence: result.result?.confidence ?? 0,
                                frameRate: itemFrameRate,
                                quality_score: result.result?.quality_score || 0,
                                method_results: result.result?.method_results || [],
                                analysis_id: result.result?.analysis_id,
                                status: 'completed'
                            };
                        }

                        const errorMsg = result.error || result.detail || result.message || 'Unknown error';
                        this.addLog('error', `Component ${component.label} failed: ${errorMsg}`);
                        return {
                            component: component.label,
                            componentName: component.name,
                            offset_seconds: 0,
                            confidence: 0,
                            frameRate: itemFrameRate,
                            error: errorMsg,
                            status: 'failed'
                        };
                    } catch (error) {
                        this.addLog('error', `Component ${component.label} error: ${error.message}`);
                        return {
                            component: component.label,
                            componentName: component.name,
                            offset_seconds: 0,
                            confidence: 0,
                            frameRate: itemFrameRate,
                            error: error.message,
                            status: 'failed'
                        };
                    }
                });

                this.addLog('info', 'Running parallel component analysis...');
                item.componentResults = await Promise.all(analysisPromises);
            }

            if (item.status === 'failed') {
                item.progress = 0;
                this.updateBatchTableRow(item);
                return;
            }

            // Determine overall status based on component results
            const allCompleted = item.componentResults.every(r => r.status === 'completed');
            const anyFailed = item.componentResults.some(r => r.status === 'failed');

            if (allCompleted) {
                item.status = 'completed';
                this.addLog('success', `All ${item.components.length} components analyzed successfully`);
            } else if (anyFailed) {
                const failedCount = item.componentResults.filter(r => r.status === 'failed').length;
                item.status = 'completed'; // Mark as completed even with some failures
                this.addLog('warning', `Componentized analysis completed with ${failedCount} failed component(s)`);
            }

            item.progress = 100;
            this.updateBatchTableRow(item);

        } catch (error) {
            item.status = 'failed';
            item.error = error.message;
            item.progress = 0;
            this.addLog('error', `Componentized analysis error: ${error.message}`);
        }
    }

    async clearBatchQueue() {
        if (this.batchProcessing) {
            this.addLog('warning', 'Cannot clear queue while processing');
            return;
        }

        // Confirm before clearing
        if (!confirm('Are you sure you want to clear the entire batch queue? This will remove all items.')) {
            return;
        }

        // Clear local queue
        this.batchQueue = [];
        this.updateBatchTable();
        this.updateBatchSummary();
        this.closeBatchDetails();

        // Clear localStorage
        localStorage.removeItem('sync-analyzer-batch-queue');

        // Clear ALL server-side storage to prevent re-sync
        const clearPromises = [];

        // 1. Clear batch-queue (Redis)
        clearPromises.push(
            fetch(`${this.FASTAPI_BASE}/batch-queue`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            }).catch(e => console.warn('Failed to clear batch-queue:', e))
        );

        // 2. Clear job-registry (Redis) - this is what brings jobs back!
        clearPromises.push(
            fetch(`${this.FASTAPI_BASE}/job-registry`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' }
            }).catch(e => console.warn('Failed to clear job-registry:', e))
        );

        try {
            await Promise.all(clearPromises);
            this.addLog('info', 'Batch queue cleared (local, server, and job registry)');
        } catch (error) {
            console.error('Failed to clear server storage:', error);
            this.addLog('warning', 'Cleared locally, but some server data may persist');
        }
    }
    
    /**
     * Toggle export dropdown visibility
     */
    toggleExportDropdown() {
        const dropdown = this.elements.exportDropdownBtn?.closest('.export-dropdown');
        if (dropdown) {
            dropdown.classList.toggle('open');
        }
    }
    
    /**
     * Close export dropdown
     */
    closeExportDropdown() {
        const dropdown = this.elements.exportDropdownBtn?.closest('.export-dropdown');
        if (dropdown) {
            dropdown.classList.remove('open');
        }
    }
    
    /**
     * Toggle jobs dropdown
     */
    toggleJobsDropdown() {
        const dropdown = this.elements.jobsDropdownBtn?.closest('.jobs-dropdown');
        if (dropdown) {
            dropdown.classList.toggle('open');
        }
    }
    
    /**
     * Close jobs dropdown
     */
    closeJobsDropdown() {
        const dropdown = this.elements.jobsDropdownBtn?.closest('.jobs-dropdown');
        if (dropdown) {
            dropdown.classList.remove('open');
        }
    }
    
    /**
     * Set jobs limit and update UI
     */
    setJobsLimit(value) {
        this.maxConcurrentJobs = value;
        // Update hidden input
        if (this.elements.concurrentJobs) {
            this.elements.concurrentJobs.value = value;
        }
        // Update label
        if (this.elements.jobsLabel) {
            this.elements.jobsLabel.textContent = value === 1 ? '1 Job' : `${value} Jobs`;
        }
        // Update selected state
        if (this.elements.jobsDropdownMenu) {
            this.elements.jobsDropdownMenu.querySelectorAll('.dropdown-item').forEach(item => {
                if (parseInt(item.dataset.value, 10) === value) {
                    item.classList.add('selected');
                } else {
                    item.classList.remove('selected');
                }
            });
        }
        this.addLog('info', `Concurrent jobs set to ${value}`);
    }
    
    /**
     * Export batch queue results as CSV report
     */
    exportBatchReport() {
        if (this.batchQueue.length === 0) {
            this.addLog('warning', 'No items in batch queue to export');
            return;
        }
        
        // Build CSV header
        const headers = [
            'Master File',
            'Master Path',
            'Component',
            'Component Path',
            'Status',
            'Offset (seconds)',
            'Offset (timecode)',
            'Confidence',
            'Method Used',
            'Repair Status',
            'Error'
        ];
        
        const rows = [headers.join(',')];
        
        // Build data rows
        for (const item of this.batchQueue) {
            const masterName = item.master?.name || 'N/A';
            const masterPath = item.master?.path || 'N/A';
            
            if (item.components && item.components.length > 0) {
                // Componentized mode - one row per component
                for (let i = 0; i < item.components.length; i++) {
                    const comp = item.components[i];
                    const compResult = item.componentResults?.[i] || item.result?.component_results?.[i] || {};
                    
                    const offsetSec = compResult.offset_seconds ?? item.result?.voted_offset_seconds ?? '';
                    const offsetTC = offsetSec !== '' ? this.formatTimecode(offsetSec, item.frameRate || 23.976) : '';
                    const confidence = compResult.confidence ?? compResult.quality_score ?? '';
                    const method = compResult.method_used || item.result?.method_used || '';
                    const repairStatus = compResult.repairStatus || item.repairStatus || '';
                    
                    rows.push([
                        this.escapeCSV(masterName),
                        this.escapeCSV(masterPath),
                        this.escapeCSV(comp.label || comp.name || `Component ${i + 1}`),
                        this.escapeCSV(comp.path || ''),
                        item.status || '',
                        offsetSec !== '' ? offsetSec.toFixed(6) : '',
                        offsetTC,
                        confidence !== '' ? (confidence * 100).toFixed(1) + '%' : '',
                        this.escapeCSV(method),
                        repairStatus,
                        this.escapeCSV(item.error || compResult.error || '')
                    ].join(','));
                }
            } else {
                // Standard mode - single row
                const dubName = item.dub?.name || 'N/A';
                const dubPath = item.dub?.path || 'N/A';
                const offsetSec = item.result?.offset_seconds ?? '';
                const offsetTC = offsetSec !== '' ? this.formatTimecode(offsetSec, item.frameRate || 23.976) : '';
                const confidence = item.result?.confidence ?? '';
                const method = item.result?.method_used || '';
                
                rows.push([
                    this.escapeCSV(masterName),
                    this.escapeCSV(masterPath),
                    this.escapeCSV(dubName),
                    this.escapeCSV(dubPath),
                    item.status || '',
                    offsetSec !== '' ? offsetSec.toFixed(6) : '',
                    offsetTC,
                    confidence !== '' ? (confidence * 100).toFixed(1) + '%' : '',
                    this.escapeCSV(method),
                    item.repairStatus || '',
                    this.escapeCSV(item.error || '')
                ].join(','));
            }
        }
        
        // Create and download CSV
        const csvContent = rows.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        
        const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
        const filename = `sync_analysis_report_${timestamp}.csv`;
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.addLog('info', `Exported ${this.batchQueue.length} items to ${filename}`);
    }
    
    /**
     * Escape a value for CSV (handle commas, quotes, newlines)
     */
    escapeCSV(value) {
        if (value === null || value === undefined) return '';
        const str = String(value);
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
            return '"' + str.replace(/"/g, '""') + '"';
        }
        return str;
    }
    
    /**
     * Export batch queue as clean HTML report with component cards
     */
    async exportHtmlReport() {
        if (this.batchQueue.length === 0) {
            this.addLog('warning', 'No items in batch queue to export');
            return;
        }
        
        this.addLog('info', 'Generating HTML report...');
        
        // Calculate summary stats
        const total = this.batchQueue.length;
        const completed = this.batchQueue.filter(i => i.status === 'completed').length;
        const failed = this.batchQueue.filter(i => i.status === 'failed').length;
        const queued = this.batchQueue.filter(i => i.status === 'queued').length;
        const totalComponents = this.batchQueue.reduce((sum, item) => sum + (item.components?.length || 1), 0);
        
        const timestamp = new Date().toLocaleString();
        const fileTimestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
        
        // Build clean HTML report
        const htmlContent = this.generateCleanHtmlReport(timestamp, fileTimestamp, { total, completed, failed, queued, totalComponents });
        
        // Download
        const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const filename = `sync_report_${fileTimestamp}.html`;
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.addLog('info', `Exported HTML report with ${totalComponents} components to ${filename}`);
    }
    
    /**
     * Export batch queue as Waveform View (timeline style like Offset Visualization)
     */
    async exportWaveformViewReport() {
        if (this.batchQueue.length === 0) {
            this.addLog('warning', 'No items in batch queue to export');
            return;
        }
        
        this.addLog('info', 'Generating Waveform View report...');
        
        // Calculate summary stats
        const total = this.batchQueue.length;
        const completed = this.batchQueue.filter(i => i.status === 'completed').length;
        const failed = this.batchQueue.filter(i => i.status === 'failed').length;
        const queued = this.batchQueue.filter(i => i.status === 'queued').length;
        const totalComponents = this.batchQueue.reduce((sum, item) => sum + (item.components?.length || 1), 0);
        
        const timestamp = new Date().toLocaleString();
        const fileTimestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
        
        // Build timeline waveform HTML content
        const htmlContent = this.generateTimelineWaveformReport(timestamp, fileTimestamp, { total, completed, failed, queued, totalComponents });
        
        // Download
        const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const filename = `sync_waveform_view_${fileTimestamp}.html`;
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.addLog('info', `Exported Waveform View with ${totalComponents} components to ${filename}`);
    }
    
    /**
     * Generate clean HTML report content with component cards
     */
    generateCleanHtmlReport(timestamp, fileTimestamp, stats) {
        const itemCards = this.batchQueue.map((item, index) => this.generateCleanItemCard(item, index)).join('');
        
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sync Analysis Report - ${fileTimestamp}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-page: #f8fafc;
            --bg-card: #ffffff;
            --bg-surface: #f1f5f9;
            --border: #e2e8f0;
            --text-primary: #0f172a;
            --text-secondary: #475569;
            --text-muted: #94a3b8;
            --accent-blue: #3b82f6;
            --accent-green: #22c55e;
            --accent-red: #ef4444;
            --accent-orange: #f97316;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-page);
            color: var(--text-primary);
            line-height: 1.6;
        }
        
        .container { max-width: 1400px; margin: 0 auto; padding: 30px; }
        
        .header {
            background: var(--bg-card);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
            border: 1px solid var(--border);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        .header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }
        
        .header h1 {
            font-size: 24px;
            font-weight: 700;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .header h1::before { content: '🎬'; }
        
        .header-date { font-size: 13px; color: var(--text-muted); }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 16px;
        }
        
        .stat-box {
            background: var(--bg-surface);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }
        
        .stat-box .value {
            font-size: 32px;
            font-weight: 800;
            line-height: 1;
            margin-bottom: 4px;
        }
        
        .stat-box .label {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            font-weight: 600;
        }
        
        .stat-box.masters .value { color: var(--text-primary); }
        .stat-box.components .value { color: var(--accent-blue); }
        .stat-box.completed .value { color: var(--accent-green); }
        .stat-box.failed .value { color: var(--accent-red); }
        .stat-box.queued .value { color: var(--accent-orange); }
        
        .items-grid { display: flex; flex-direction: column; gap: 20px; }
        
        .item-card {
            background: var(--bg-card);
            border-radius: 16px;
            border: 1px solid var(--border);
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        
        .item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            background: var(--bg-surface);
            border-bottom: 1px solid var(--border);
        }
        
        .item-header .title {
            display: flex;
            align-items: center;
            gap: 12px;
            font-weight: 600;
            font-size: 14px;
        }
        
        .item-header .num {
            background: var(--accent-blue);
            color: white;
            width: 28px;
            height: 28px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 12px;
            font-weight: 700;
        }
        
        .status-pill {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .status-pill.completed { background: #dcfce7; color: #166534; }
        .status-pill.failed { background: #fee2e2; color: #991b1b; }
        .status-pill.queued { background: #fef3c7; color: #92400e; }
        
        .item-body { padding: 20px; }
        
        .quick-info {
            display: flex;
            gap: 24px;
            margin-bottom: 20px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }
        
        .info-block { flex: 1; }
        
        .info-block .label {
            font-size: 10px;
            text-transform: uppercase;
            color: var(--text-muted);
            letter-spacing: 0.5px;
            margin-bottom: 4px;
        }
        
        .info-block .value {
            font-size: 16px;
            font-weight: 700;
            font-family: 'JetBrains Mono', monospace;
        }
        
        .info-block .value.in-sync { color: var(--accent-green); }
        .info-block .value.offset { color: var(--accent-blue); }
        
        .components-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }
        
        .component-card {
            background: var(--bg-surface);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid var(--border);
        }
        
        .component-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .comp-badge {
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
        }
        
        .comp-badge.a0 { background: #fef2f2; color: #dc2626; }
        .comp-badge.a1 { background: #f0fdf4; color: #16a34a; }
        .comp-badge.a2 { background: #eff6ff; color: #2563eb; }
        .comp-badge.a3 { background: #fefce8; color: #ca8a04; }
        
        .comp-name {
            font-size: 12px;
            color: var(--text-secondary);
            max-width: 150px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .comp-offset {
            font-family: 'JetBrains Mono', monospace;
            font-size: 14px;
            font-weight: 600;
            color: var(--accent-blue);
        }
        
        .waveform-container {
            height: 50px;
            background: linear-gradient(180deg, #fff 0%, var(--bg-surface) 100%);
            border-radius: 8px;
            position: relative;
            overflow: hidden;
            border: 1px solid var(--border);
        }
        
        .waveform-svg { width: 100%; height: 100%; }
        
        .sync-tag {
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
        }
        
        .sync-tag.in-sync { background: #dcfce7; color: #166534; }
        .sync-tag.near { background: #d1fae5; color: #047857; }
        .sync-tag.close { background: #fef9c3; color: #a16207; }
        .sync-tag.moderate { background: #fed7aa; color: #c2410c; }
        .sync-tag.far { background: #fee2e2; color: #dc2626; }
        
        .footer {
            text-align: center;
            padding: 30px;
            color: var(--text-muted);
            font-size: 12px;
        }
        
        @media print {
            body { background: white; }
            .item-card, .header { box-shadow: none; border: 1px solid #ddd; }
        }
        
        @media (max-width: 768px) {
            .stats-grid { grid-template-columns: repeat(2, 1fr); }
            .quick-info { flex-wrap: wrap; }
            .components-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="header-top">
                <h1>Sync Analysis Report</h1>
                <span class="header-date">${timestamp}</span>
            </div>
            <div class="stats-grid">
                <div class="stat-box masters">
                    <div class="value">${stats.total}</div>
                    <div class="label">Masters</div>
                </div>
                <div class="stat-box components">
                    <div class="value">${stats.totalComponents}</div>
                    <div class="label">Components</div>
                </div>
                <div class="stat-box completed">
                    <div class="value">${stats.completed}</div>
                    <div class="label">Completed</div>
                </div>
                <div class="stat-box failed">
                    <div class="value">${stats.failed}</div>
                    <div class="label">Failed</div>
                </div>
                <div class="stat-box queued">
                    <div class="value">${stats.queued}</div>
                    <div class="label">Queued</div>
                </div>
            </div>
        </header>
        
        <div class="items-grid">
            ${itemCards}
        </div>
        
        <footer class="footer">
            Professional Audio Sync Analyzer • ${stats.total} masters • ${stats.totalComponents} components
        </footer>
    </div>
</body>
</html>`;
    }
    
    /**
     * Generate a clean item card for the HTML report
     */
    generateCleanItemCard(item, index) {
        const masterName = item.master?.name || 'Unknown';
        const status = item.status || 'queued';
        const fps = item.frameRate || 23.976;
        
        let votedOffset = 0;
        let votedTC = 'N/A';
        let confidence = 0;
        let method = 'N/A';
        
        if (item.result) {
            votedOffset = item.result.voted_offset_seconds ?? item.result.offset_seconds ?? 0;
            votedTC = this.formatTimecode(votedOffset, fps);
            confidence = item.result.overall_offset?.confidence ?? item.result.confidence ?? 0;
            method = item.result.method_used || 'N/A';
        }
        
        const isInSync = Math.abs(votedOffset) < 0.02;
        
        // Generate component cards
        let componentsHtml = '';
        if (item.components && item.components.length > 0) {
            componentsHtml = item.components.map((comp, i) => {
                const compResult = item.componentResults?.[i] || item.result?.component_results?.[i] || {};
                const compOffset = compResult.offset_seconds ?? votedOffset;
                const compTC = this.formatTimecode(compOffset, fps);
                const compConf = compResult.confidence ?? confidence;
                const compLabel = comp.label || `A${i}`;
                const labelClass = compLabel.toLowerCase().replace(/[^a-z0-9]/g, '');
                const syncStatus = this.getSyncStatusLabel(compOffset);
                
                const waveformSvg = this.generateCompactWaveformSvg(comp.name || '', compOffset, labelClass);
                
                return `
                    <div class="component-card">
                        <div class="component-header">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span class="comp-badge ${labelClass}">${this.escapeHtml(compLabel)}</span>
                                <span class="comp-name" title="${this.escapeHtml(comp.name || '')}">${this.escapeHtml(comp.name || 'Unknown')}</span>
                            </div>
                            <span class="comp-offset">${compTC}</span>
                        </div>
                        ${waveformSvg}
                        <div style="display: flex; justify-content: space-between; margin-top: 10px; font-size: 11px;">
                            <span class="sync-tag ${syncStatus.type}">${syncStatus.label}</span>
                            <span style="color: var(--text-muted);">${(compConf * 100).toFixed(0)}% confidence</span>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        return `
            <article class="item-card">
                <div class="item-header">
                    <div class="title">
                        <span class="num">${index + 1}</span>
                        <span>${this.escapeHtml(masterName)}</span>
                    </div>
                    <span class="status-pill ${status}">${status}</span>
                </div>
                <div class="item-body">
                    <div class="quick-info">
                        <div class="info-block">
                            <div class="label">Voted Offset</div>
                            <div class="value ${isInSync ? 'in-sync' : 'offset'}">${votedTC}</div>
                        </div>
                        <div class="info-block">
                            <div class="label">Seconds</div>
                            <div class="value">${votedOffset.toFixed(4)}s</div>
                        </div>
                        <div class="info-block">
                            <div class="label">Confidence</div>
                            <div class="value">${(confidence * 100).toFixed(0)}%</div>
                        </div>
                        <div class="info-block">
                            <div class="label">Method</div>
                            <div class="value" style="font-family: Inter, sans-serif; font-size: 13px;">${this.escapeHtml(method)}</div>
                        </div>
                        <div class="info-block">
                            <div class="label">Components</div>
                            <div class="value">${item.components?.length || 1}</div>
                        </div>
                    </div>
                    <div class="components-grid">
                        ${componentsHtml || '<p style="color: var(--text-muted); font-size: 13px;">No component data</p>'}
                    </div>
                </div>
            </article>
        `;
    }
    
    /**
     * Generate compact waveform SVG for component cards
     */
    generateCompactWaveformSvg(filename, offset, labelClass) {
        const seed = this.hashString(filename || 'default');
        const width = 260;
        const height = 40;
        const barCount = 50;
        
        const colors = {
            'a0': { fill: '#fecaca', stroke: '#ef4444' },
            'a1': { fill: '#bbf7d0', stroke: '#22c55e' },
            'a2': { fill: '#bfdbfe', stroke: '#3b82f6' },
            'a3': { fill: '#fef08a', stroke: '#eab308' },
        };
        const color = colors[labelClass] || { fill: '#e9d5ff', stroke: '#a855f7' };
        
        let bars = '';
        const centerY = height / 2;
        
        for (let i = 0; i < barCount; i++) {
            const x = (i / barCount) * width + 4;
            const t = i / barCount;
            const noise1 = Math.sin(seed + i * 0.4) * 0.3;
            const noise2 = Math.sin(seed * 1.7 + i * 0.8) * 0.2;
            const envelope = Math.sin(t * Math.PI) * 0.6 + 0.4;
            const amplitude = (0.3 + envelope * 0.7 + noise1 + noise2) * (height / 2 - 4);
            const barHeight = Math.max(2, amplitude);
            const y = centerY - barHeight / 2;
            bars += `<rect x="${x}" y="${y}" width="3" height="${barHeight}" rx="1" fill="${color.fill}" stroke="${color.stroke}" stroke-width="0.5"/>`;
        }
        
        const offsetPercent = 50 + (offset / 2) * 25;
        const clampedOffset = Math.max(5, Math.min(95, offsetPercent));
        const showMarker = Math.abs(offset) > 0.01;
        
        const offsetMarker = showMarker ? `
            <line x1="${clampedOffset}%" y1="0" x2="${clampedOffset}%" y2="${height}" stroke="#ef4444" stroke-width="2"/>
            <circle cx="${clampedOffset}%" cy="5" r="3" fill="#ef4444"/>
        ` : '';
        
        const centerLine = `<line x1="50%" y1="0" x2="50%" y2="${height}" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="2,2"/>`;
        
        return `
            <div class="waveform-container">
                <svg class="waveform-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
                    ${centerLine}
                    ${bars}
                    ${offsetMarker}
                </svg>
            </div>
        `;
    }
    
    /**
     * Generate timeline waveform report (like Offset Visualization panel)
     */
    generateTimelineWaveformReport(timestamp, fileTimestamp, stats) {
        // Generate item sections with timeline waveforms
        const itemSections = this.batchQueue.map((item, index) => this.generateTimelineWaveformSection(item, index)).join('');
        
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sync Waveform Report - ${fileTimestamp}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-page: #0d1117;
            --bg-card: #161b22;
            --bg-surface: #21262d;
            --border: #30363d;
            --text-primary: #e6edf3;
            --text-secondary: #8b949e;
            --text-muted: #6e7681;
            --waveform-blue: #2563eb;
            --waveform-green: #22c55e;
            --accent-red: #ef4444;
            --accent-orange: #f97316;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-page);
            color: var(--text-primary);
            line-height: 1.5;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 24px;
        }
        
        /* Header */
        .header {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
        }
        
        .header-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .header h1 {
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
        }
        
        .header-date {
            font-size: 12px;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .stats-row {
            display: flex;
            gap: 24px;
        }
        
        .stat-item {
            display: flex;
            align-items: baseline;
            gap: 8px;
        }
        
        .stat-item .value {
            font-size: 24px;
            font-weight: 700;
        }
        
        .stat-item .label {
            font-size: 12px;
            color: var(--text-muted);
        }
        
        .stat-item.masters .value { color: var(--text-primary); }
        .stat-item.components .value { color: var(--waveform-blue); }
        .stat-item.completed .value { color: var(--waveform-green); }
        .stat-item.failed .value { color: var(--accent-red); }
        
        /* Item Sections */
        .item-section {
            background: var(--bg-card);
            border-radius: 12px;
            margin-bottom: 24px;
            border: 1px solid var(--border);
            overflow: hidden;
        }
        
        .item-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            background: var(--bg-surface);
            border-bottom: 1px solid var(--border);
        }
        
        .item-title {
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .item-num {
            background: var(--waveform-blue);
            color: white;
            width: 24px;
            height: 24px;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 700;
        }
        
        .item-name {
            font-weight: 600;
            font-size: 13px;
        }
        
        .item-meta {
            display: flex;
            gap: 16px;
            align-items: center;
        }
        
        .meta-item {
            font-size: 11px;
            color: var(--text-secondary);
            font-family: 'JetBrains Mono', monospace;
        }
        
        .status-badge {
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .status-badge.completed { background: rgba(34, 197, 94, 0.15); color: #4ade80; }
        .status-badge.failed { background: rgba(239, 68, 68, 0.15); color: #f87171; }
        .status-badge.queued { background: rgba(249, 115, 22, 0.15); color: #fb923c; }
        
        /* Waveform Visualization Container */
        .waveform-viz {
            padding: 16px 20px;
        }
        
        .viz-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .zero-marker {
            background: var(--accent-orange);
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
        }
        
        /* Timeline Track */
        .track {
            position: relative;
            margin-bottom: 8px;
        }
        
        .track-label {
            position: absolute;
            left: 0;
            top: 50%;
            transform: translateY(-50%);
            width: 50px;
            z-index: 10;
        }
        
        .track-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }
        
        .track-badge.aref { background: var(--waveform-blue); color: white; }
        .track-badge.a0 { background: #16a34a; color: white; }
        .track-badge.a1 { background: #16a34a; color: white; }
        .track-badge.a2 { background: #16a34a; color: white; }
        .track-badge.a3 { background: #16a34a; color: white; }
        
        .track-waveform {
            margin-left: 60px;
            height: 60px;
            border-radius: 4px;
            position: relative;
            overflow: hidden;
        }
        
        .track-waveform.master {
            background: var(--waveform-blue);
        }
        
        .track-waveform.component {
            background: var(--waveform-green);
        }
        
        /* Waveform SVG */
        .waveform-svg {
            width: 100%;
            height: 100%;
            display: block;
        }
        
        /* Offset Marker */
        .offset-marker {
            position: absolute;
            top: 4px;
            background: var(--accent-red);
            color: white;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 10px;
            font-weight: 600;
            font-family: 'JetBrains Mono', monospace;
            white-space: nowrap;
            z-index: 5;
        }
        
        /* Timeline */
        .timeline {
            margin-left: 60px;
            height: 20px;
            position: relative;
            border-top: 1px solid var(--border);
            margin-top: 8px;
        }
        
        .timeline-marker {
            position: absolute;
            top: 4px;
            font-size: 9px;
            color: var(--text-muted);
            font-family: 'JetBrains Mono', monospace;
            transform: translateX(-50%);
        }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 20px;
            color: var(--text-muted);
            font-size: 11px;
        }
        
        /* Print */
        @media print {
            body { background: white; color: black; }
            .item-section { border: 1px solid #ccc; }
            .track-waveform.master { background: #3b82f6; }
            .track-waveform.component { background: #22c55e; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="header-row">
                <h1>🎬 Offset Visualization Report</h1>
                <span class="header-date">${timestamp}</span>
            </div>
            <div class="stats-row">
                <div class="stat-item masters">
                    <span class="value">${stats.total}</span>
                    <span class="label">Masters</span>
                </div>
                <div class="stat-item components">
                    <span class="value">${stats.totalComponents}</span>
                    <span class="label">Components</span>
                </div>
                <div class="stat-item completed">
                    <span class="value">${stats.completed}</span>
                    <span class="label">Completed</span>
                </div>
                <div class="stat-item failed">
                    <span class="value">${stats.failed}</span>
                    <span class="label">Failed</span>
                </div>
            </div>
        </header>
        
        ${itemSections}
        
        <footer class="footer">
            Professional Audio Sync Analyzer • Offset Visualization Report
        </footer>
    </div>
</body>
</html>`;
    }
    
    /**
     * Generate timeline waveform section for an item (like Offset Visualization panel)
     */
    generateTimelineWaveformSection(item, index) {
        const masterName = item.master?.name || 'Unknown';
        const status = item.status || 'queued';
        const fps = item.frameRate || 23.976;
        
        // Get overall offset info
        let votedOffset = 0;
        let votedTC = '00:00:00:00';
        let confidence = 0;
        let method = 'N/A';
        
        if (item.result) {
            votedOffset = item.result.voted_offset_seconds ?? item.result.offset_seconds ?? 0;
            votedTC = this.formatTimecode(votedOffset, fps);
            confidence = item.result.overall_offset?.confidence ?? item.result.confidence ?? 0;
            method = item.result.method_used || 'N/A';
        }
        
        // Generate master waveform track (AREF - blue)
        const masterWaveformSvg = this.generateTimelineWaveformSvg(masterName, 'master');
        
        // Generate component tracks (green)
        let componentTracks = '';
        if (item.components && item.components.length > 0) {
            componentTracks = item.components.map((comp, i) => {
                const compResult = item.componentResults?.[i] || item.result?.component_results?.[i] || {};
                const compOffset = compResult.offset_seconds ?? votedOffset;
                const compTC = this.formatTimecode(compOffset, fps);
                const compLabel = comp.label || `A${i}`;
                const labelClass = compLabel.toLowerCase().replace(/[^a-z0-9]/g, '');
                
                const compWaveformSvg = this.generateTimelineWaveformSvg(comp.name || '', 'component');
                
                return `
                    <div class="track">
                        <div class="track-label">
                            <span class="track-badge ${labelClass}">${this.escapeHtml(compLabel)}</span>
                        </div>
                        <div class="track-waveform component">
                            ${compWaveformSvg}
                            <div class="offset-marker" style="left: 180px;">Offset: ${compTC}</div>
                        </div>
                    </div>
                `;
            }).join('');
        }
        
        // Generate timeline markers
        const timelineMarkers = this.generateTimelineMarkers();
        
        return `
            <section class="item-section">
                <div class="item-header">
                    <div class="item-title">
                        <span class="item-num">${index + 1}</span>
                        <span class="item-name">${this.escapeHtml(masterName)}</span>
                    </div>
                    <div class="item-meta">
                        <span class="meta-item">Offset: ${votedTC}</span>
                        <span class="meta-item">${(confidence * 100).toFixed(0)}%</span>
                        <span class="meta-item">${this.escapeHtml(method)}</span>
                        <span class="status-badge ${status}">${status}</span>
                    </div>
                </div>
                <div class="waveform-viz">
                    <div class="viz-header">
                        <span class="zero-marker">Zero: 00:00:00:00</span>
                    </div>
                    
                    <!-- Master Track (AREF) -->
                    <div class="track">
                        <div class="track-label">
                            <span class="track-badge aref">AREF</span>
                        </div>
                        <div class="track-waveform master">
                            ${masterWaveformSvg}
                        </div>
                    </div>
                    
                    <!-- Component Tracks -->
                    ${componentTracks}
                    
                    <!-- Timeline -->
                    <div class="timeline">
                        ${timelineMarkers}
                    </div>
                </div>
            </section>
        `;
    }
    
    /**
     * Generate SVG waveform for timeline visualization
     */
    generateTimelineWaveformSvg(filename, type) {
        const seed = this.hashString(filename || 'default');
        const width = 1400;
        const height = 60;
        const barCount = 300;
        
        const color = type === 'master' ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.6)';
        
        let bars = '';
        const centerY = height / 2;
        
        for (let i = 0; i < barCount; i++) {
            const x = (i / barCount) * width;
            const t = i / barCount;
            
            // Create varied waveform pattern - simulate audio
            const noise1 = Math.sin(seed + i * 0.15) * 0.4;
            const noise2 = Math.sin(seed * 2.3 + i * 0.4) * 0.3;
            const noise3 = Math.sin(seed * 0.7 + i * 0.08) * 0.2;
            
            // Add some "quiet" and "loud" sections
            const section = Math.floor(t * 10);
            const sectionNoise = Math.sin(seed + section * 1.5) * 0.3;
            
            const amplitude = Math.max(0.05, Math.min(1, 0.3 + noise1 + noise2 + noise3 + sectionNoise));
            const barHeight = amplitude * (height - 8);
            const y = centerY - barHeight / 2;
            
            bars += `<rect x="${x}" y="${y}" width="3" height="${barHeight}" fill="${color}" rx="1"/>`;
        }
        
        return `<svg class="waveform-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">${bars}</svg>`;
    }
    
    /**
     * Generate timeline markers (00:00, 01:00, 02:00, etc.)
     */
    generateTimelineMarkers() {
        const markers = [];
        const totalMinutes = 10;
        
        for (let i = 0; i <= totalMinutes; i++) {
            const percent = (i / totalMinutes) * 100;
            const time = i === 0 ? '00' : `0${i}:00`.slice(-5);
            markers.push(`<span class="timeline-marker" style="left: ${percent}%;">${time}</span>`);
        }
        
        return markers.join('');
    }
    
    
    /**
     * Simple string hash for consistent pseudo-random generation
     */
    hashString(str) {
        let hash = 0;
        for (let i = 0; i < str.length; i++) {
            const char = str.charCodeAt(i);
            hash = ((hash << 5) - hash) + char;
            hash = hash & hash;
        }
        return Math.abs(hash);
    }
    
    /**
     * Escape HTML special characters
     */
    escapeHtml(str) {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
    
    /**
     * Export batch queue as JSON
     */
    exportJsonReport() {
        if (this.batchQueue.length === 0) {
            this.addLog('warning', 'No items in batch queue to export');
            return;
        }
        
        // Build export data structure
        const exportData = {
            exportDate: new Date().toISOString(),
            summary: {
                total: this.batchQueue.length,
                completed: this.batchQueue.filter(i => i.status === 'completed').length,
                failed: this.batchQueue.filter(i => i.status === 'failed').length,
                queued: this.batchQueue.filter(i => i.status === 'queued').length,
            },
            items: this.batchQueue.map(item => ({
                id: item.id,
                master: {
                    name: item.master?.name,
                    path: item.master?.path,
                },
                components: item.components?.map(c => ({
                    label: c.label,
                    name: c.name,
                    path: c.path,
                })),
                dub: item.dub ? {
                    name: item.dub?.name,
                    path: item.dub?.path,
                } : null,
                status: item.status,
                frameRate: item.frameRate,
                result: item.result,
                componentResults: item.componentResults,
                error: item.error,
            })),
        };
        
        const jsonContent = JSON.stringify(exportData, null, 2);
        const blob = new Blob([jsonContent], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
        const filename = `sync_analysis_report_${timestamp}.json`;
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.addLog('info', `Exported ${this.batchQueue.length} items to ${filename}`);
    }
    
    /**
     * Export batch queue as Table View HTML (Frame Management style)
     */
    exportTableViewReport() {
        if (this.batchQueue.length === 0) {
            this.addLog('warning', 'No items in batch queue to export');
            return;
        }
        
        this.addLog('info', 'Generating Table View report...');
        
        const timestamp = new Date().toLocaleString();
        const fileTimestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
        
        // Flatten all components into rows
        const rows = [];
        let rowNum = 1;
        
        this.batchQueue.forEach((item, itemIndex) => {
            const masterName = item.master?.name || 'Unknown';
            const fps = item.frameRate || 23.976;
            const status = item.status || 'queued';
            
            if (item.components && item.components.length > 0) {
                item.components.forEach((comp, compIndex) => {
                    const compResult = item.componentResults?.[compIndex] || item.result?.component_results?.[compIndex] || {};
                    const offset = compResult.offset_seconds ?? item.result?.voted_offset_seconds ?? 0;
                    const confidence = compResult.confidence ?? item.result?.overall_offset?.confidence ?? 0;
                    const method = compResult.method_used || item.result?.method_used || 'N/A';
                    const compLabel = comp.label || `A${compIndex}`;
                    
                    rows.push({
                        rowNum: rowNum++,
                        masterName,
                        componentLabel: compLabel,
                        componentName: comp.name || 'Unknown',
                        offset,
                        offsetTC: this.formatTimecode(offset, fps),
                        confidence,
                        method,
                        status,
                        syncStatus: this.getSyncStatusLabel(offset),
                    });
                });
            } else {
                const offset = item.result?.offset_seconds ?? 0;
                const confidence = item.result?.confidence ?? 0;
                const method = item.result?.method_used || 'N/A';
                
                rows.push({
                    rowNum: rowNum++,
                    masterName,
                    componentLabel: 'Main',
                    componentName: item.dub?.name || 'N/A',
                    offset,
                    offsetTC: this.formatTimecode(offset, fps),
                    confidence,
                    method,
                    status,
                    syncStatus: this.getSyncStatusLabel(offset),
                });
            }
        });
        
        const htmlContent = this.generateTableViewHtml(rows, timestamp);
        
        // Download
        const blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const filename = `sync_table_view_${fileTimestamp}.html`;
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.addLog('info', `Exported Table View with ${rows.length} rows to ${filename}`);
    }
    
    /**
     * Get sync status label based on offset
     */
    getSyncStatusLabel(offset) {
        const absOffset = Math.abs(offset);
        if (absOffset < 0.02) return { label: 'In Sync', type: 'success' };
        if (absOffset < 0.1) return { label: 'Near', type: 'near' };
        if (absOffset < 0.5) return { label: 'Close', type: 'close' };
        if (absOffset < 1.0) return { label: 'Moderate', type: 'moderate' };
        return { label: 'Far', type: 'far' };
    }
    
    /**
     * Generate Table View HTML in Frame Management style
     */
    generateTableViewHtml(rows, timestamp) {
        const tableRows = rows.map(row => {
            const waveformSvg = this.generateMiniWaveformSvg(row.componentName, row.offset, row.componentLabel);
            return `
            <tr>
                <td class="row-num">${row.rowNum}</td>
                <td class="cell-text">${this.escapeHtml(row.masterName)}</td>
                <td class="cell-component">
                    <span class="comp-tag ${row.componentLabel.toLowerCase()}">${this.escapeHtml(row.componentLabel)}</span>
                </td>
                <td class="cell-text" title="${this.escapeHtml(row.componentName)}">${this.escapeHtml(row.componentName)}</td>
                <td class="cell-waveform">${waveformSvg}</td>
                <td class="cell-status">
                    <span class="status-tag ${row.syncStatus.type}">${row.syncStatus.label}</span>
                </td>
                <td class="cell-mono">${row.offsetTC}</td>
                <td class="cell-mono">${row.offset.toFixed(4)}s</td>
                <td class="cell-confidence">
                    <div class="confidence-bar">
                        <div class="confidence-fill" style="width: ${(row.confidence * 100).toFixed(0)}%"></div>
                        <span class="confidence-text">${(row.confidence * 100).toFixed(0)}%</span>
                    </div>
                </td>
                <td class="cell-text">${this.escapeHtml(row.method)}</td>
                <td class="cell-status">
                    <span class="status-tag ${row.status}">${row.status}</span>
                </td>
            </tr>
        `}).join('');
        
        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Sync Analysis - Table View</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #f8fafc;
            --bg-secondary: #ffffff;
            --bg-hover: #f1f5f9;
            --border-color: #e2e8f0;
            --text-primary: #1e293b;
            --text-secondary: #64748b;
            --text-muted: #94a3b8;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            line-height: 1.5;
        }
        
        .container {
            max-width: 100%;
            padding: 20px;
        }
        
        /* Header */
        .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 16px 20px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 0;
        }
        
        .header h1 {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .header h1::before {
            content: '📊';
        }
        
        .header-meta {
            font-size: 13px;
            color: var(--text-secondary);
        }
        
        /* Toolbar */
        .toolbar {
            display: flex;
            gap: 8px;
            padding: 12px 20px;
            background: var(--bg-secondary);
            border-bottom: 1px solid var(--border-color);
            flex-wrap: wrap;
        }
        
        .toolbar-btn {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: transparent;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            font-size: 13px;
            color: var(--text-secondary);
            cursor: pointer;
            transition: all 0.15s;
        }
        
        .toolbar-btn:hover {
            background: var(--bg-hover);
            color: var(--text-primary);
        }
        
        .toolbar-btn.active {
            background: #3b82f6;
            color: white;
            border-color: #3b82f6;
        }
        
        /* Table */
        .table-container {
            background: var(--bg-secondary);
            overflow-x: auto;
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        
        thead {
            position: sticky;
            top: 0;
            z-index: 10;
        }
        
        th {
            background: var(--bg-primary);
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border-color);
            white-space: nowrap;
        }
        
        th .col-icon {
            margin-right: 6px;
            opacity: 0.7;
        }
        
        td {
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            vertical-align: middle;
        }
        
        tr:hover td {
            background: var(--bg-hover);
        }
        
        .row-num {
            width: 40px;
            text-align: center;
            color: var(--text-muted);
            font-weight: 500;
        }
        
        .cell-text {
            max-width: 250px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .cell-mono {
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            color: var(--text-primary);
        }
        
        .cell-component {
            width: 60px;
        }
        
        .cell-status {
            width: 100px;
        }
        
        .cell-confidence {
            width: 120px;
        }
        
        .cell-waveform {
            width: 180px;
            padding: 6px 8px;
        }
        
        .waveform-container {
            position: relative;
            height: 36px;
            background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
            border-radius: 6px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }
        
        .waveform-svg {
            width: 100%;
            height: 100%;
        }
        
        .waveform-center-line {
            position: absolute;
            left: 50%;
            top: 0;
            bottom: 0;
            width: 1px;
            background: #e2e8f0;
        }
        
        .waveform-offset-marker {
            position: absolute;
            top: 0;
            bottom: 0;
            width: 2px;
            background: #ef4444;
        }
        
        .waveform-offset-marker::after {
            content: attr(data-offset);
            position: absolute;
            bottom: -14px;
            left: 50%;
            transform: translateX(-50%);
            font-size: 8px;
            color: #ef4444;
            white-space: nowrap;
            font-weight: 600;
        }
        
        /* Component Tags */
        .comp-tag {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        
        .comp-tag.a0 { background: #fef2f2; color: #dc2626; }
        .comp-tag.a1 { background: #f0fdf4; color: #16a34a; }
        .comp-tag.a2 { background: #eff6ff; color: #2563eb; }
        .comp-tag.a3 { background: #fefce8; color: #ca8a04; }
        .comp-tag.main { background: #f3e8ff; color: #9333ea; }
        
        /* Status Tags */
        .status-tag {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
        }
        
        .status-tag.success { background: #dcfce7; color: #166534; }
        .status-tag.near { background: #d1fae5; color: #047857; }
        .status-tag.close { background: #fef9c3; color: #a16207; }
        .status-tag.moderate { background: #fed7aa; color: #c2410c; }
        .status-tag.far { background: #fee2e2; color: #dc2626; }
        .status-tag.completed { background: #dcfce7; color: #166534; }
        .status-tag.failed { background: #fee2e2; color: #dc2626; }
        .status-tag.queued { background: #fef3c7; color: #b45309; }
        .status-tag.processing { background: #dbeafe; color: #1d4ed8; }
        
        /* Confidence Bar */
        .confidence-bar {
            position: relative;
            height: 20px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
        }
        
        .confidence-fill {
            height: 100%;
            background: linear-gradient(90deg, #22c55e, #16a34a);
            border-radius: 4px;
            transition: width 0.3s;
        }
        
        .confidence-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 10px;
            font-weight: 600;
            color: var(--text-primary);
        }
        
        /* Summary Bar */
        .summary-bar {
            display: flex;
            gap: 20px;
            padding: 12px 20px;
            background: var(--bg-secondary);
            border-top: 1px solid var(--border-color);
            font-size: 12px;
            color: var(--text-secondary);
        }
        
        .summary-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .summary-item strong {
            color: var(--text-primary);
        }
        
        /* Print styles */
        @media print {
            .toolbar { display: none; }
            .header { position: static; }
            th { background: #f5f5f5 !important; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header class="header">
            <h1>Sync Analysis Management</h1>
            <span class="header-meta">Generated: ${timestamp} • ${rows.length} components</span>
        </header>
        
        <div class="toolbar">
            <button class="toolbar-btn">🔍 Filter</button>
            <button class="toolbar-btn">📊 Sort</button>
            <button class="toolbar-btn">👁️ View Settings</button>
            <button class="toolbar-btn">🎨 Conditional Coloring</button>
        </div>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th><span class="col-icon">🔢</span>#</th>
                        <th><span class="col-icon">🎬</span>Master File</th>
                        <th><span class="col-icon">🔊</span>Track</th>
                        <th><span class="col-icon">📁</span>Component</th>
                        <th><span class="col-icon">🎵</span>Waveform</th>
                        <th><span class="col-icon">📍</span>Sync Status</th>
                        <th><span class="col-icon">⏱️</span>Offset TC</th>
                        <th><span class="col-icon">⏱️</span>Seconds</th>
                        <th><span class="col-icon">📊</span>Confidence</th>
                        <th><span class="col-icon">🔬</span>Method</th>
                        <th><span class="col-icon">✅</span>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${tableRows}
                </tbody>
            </table>
        </div>
        
        <div class="summary-bar">
            <div class="summary-item">
                <span>Total:</span>
                <strong>${rows.length} components</strong>
            </div>
            <div class="summary-item">
                <span>In Sync:</span>
                <strong>${rows.filter(r => r.syncStatus.type === 'success').length}</strong>
            </div>
            <div class="summary-item">
                <span>Near:</span>
                <strong>${rows.filter(r => r.syncStatus.type === 'near' || r.syncStatus.type === 'close').length}</strong>
            </div>
            <div class="summary-item">
                <span>Far:</span>
                <strong>${rows.filter(r => r.syncStatus.type === 'far' || r.syncStatus.type === 'moderate').length}</strong>
            </div>
        </div>
    </div>
</body>
</html>`;
    }
    
    /**
     * Generate mini waveform SVG for table view
     */
    generateMiniWaveformSvg(filename, offset, componentLabel) {
        const seed = this.hashString(filename || 'default');
        const width = 160;
        const height = 32;
        const barCount = 40;
        const barWidth = 3;
        const gap = 1;
        
        // Get color based on component label
        const colors = {
            'a0': { fill: '#fecaca', stroke: '#ef4444' },
            'a1': { fill: '#bbf7d0', stroke: '#22c55e' },
            'a2': { fill: '#bfdbfe', stroke: '#3b82f6' },
            'a3': { fill: '#fef08a', stroke: '#eab308' },
            'main': { fill: '#e9d5ff', stroke: '#a855f7' },
        };
        const labelKey = componentLabel.toLowerCase().replace(/[^a-z0-9]/g, '');
        const color = colors[labelKey] || colors['main'];
        
        // Generate waveform bars
        let bars = '';
        const centerY = height / 2;
        
        for (let i = 0; i < barCount; i++) {
            const x = i * (barWidth + gap) + 2;
            const t = i / barCount;
            
            // Create varied waveform pattern
            const noise1 = Math.sin(seed + i * 0.4) * 0.3;
            const noise2 = Math.sin(seed * 1.7 + i * 0.8) * 0.2;
            const envelope = Math.sin(t * Math.PI) * 0.6 + 0.4;
            const amplitude = (0.3 + envelope * 0.7 + noise1 + noise2) * (height / 2 - 4);
            
            const barHeight = Math.max(2, amplitude);
            const y = centerY - barHeight / 2;
            
            bars += `<rect x="${x}" y="${y}" width="${barWidth}" height="${barHeight}" rx="1" fill="${color.fill}" stroke="${color.stroke}" stroke-width="0.5"/>`;
        }
        
        // Calculate offset marker position (center = 50%, scale by 10 seconds = full width)
        const offsetPercent = 50 + (offset / 2) * 25;
        const clampedOffset = Math.max(5, Math.min(95, offsetPercent));
        const showMarker = Math.abs(offset) > 0.01;
        
        const offsetMarker = showMarker ? `
            <line x1="${clampedOffset}%" y1="0" x2="${clampedOffset}%" y2="${height}" stroke="#ef4444" stroke-width="2"/>
            <circle cx="${clampedOffset}%" cy="4" r="3" fill="#ef4444"/>
        ` : '';
        
        // Center reference line
        const centerLine = `<line x1="50%" y1="0" x2="50%" y2="${height}" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="2,2"/>`;
        
        return `
            <div class="waveform-container">
                <svg class="waveform-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
                    ${centerLine}
                    ${bars}
                    ${offsetMarker}
                </svg>
            </div>
        `;
    }
    
    /**
     * Export single item results (for details panel)
     */
    exportResults() {
        if (!this.selectedBatchItem) {
            this.addLog('warning', 'No item selected to export');
            return;
        }
        
        // Export just the selected item as JSON
        const item = this.selectedBatchItem;
        const exportData = {
            master: item.master,
            components: item.components,
            dub: item.dub,
            status: item.status,
            result: item.result,
            componentResults: item.componentResults,
            frameRate: item.frameRate,
            timestamp: new Date().toISOString()
        };
        
        const jsonContent = JSON.stringify(exportData, null, 2);
        const blob = new Blob([jsonContent], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const masterName = item.master?.name?.replace(/\.[^.]+$/, '') || 'analysis';
        const filename = `${masterName}_sync_result.json`;
        
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
        
        this.addLog('info', `Exported results to ${filename}`);
    }
    
    /**
     * Compare results placeholder
     */
    compareResults() {
        this.addLog('info', 'Compare feature coming soon');
    }
    
    updateBatchSummary() {
        const total = this.batchQueue.length;
        const completed = this.batchQueue.filter(item => item.status === 'completed').length;
        const processing = this.batchQueue.filter(item => item.status === 'processing').length;
        
        this.elements.queueCount.textContent = `${total} pairs`;
        this.elements.completedCount.textContent = completed.toString();
        
        if (processing > 0) {
            this.elements.processingStatus.textContent = `Processing (${processing})`;
        } else if (this.batchProcessing) {
            this.elements.processingStatus.textContent = 'Starting...';
        } else {
            this.elements.processingStatus.textContent = 'Ready';
        }
    }
    
    updateBatchTable() {
        const tbody = this.elements.batchTableBody;
        
        if (this.batchQueue.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-state">
                    <td colspan="7">
                        <div class="empty-message">
                            <i class="fas fa-inbox"></i>
                            <p>No files in batch queue</p>
                            <p>Select master and dub files, then click "Add to Batch"</p>
                        </div>
                    </td>
                </tr>
            `;
            return;
        }
        
        tbody.innerHTML = '';
        this.batchQueue.forEach(item => {
            const row = this.createBatchTableRow(item);
            tbody.appendChild(row);
        });
    }
    
    createBatchTableRow(item) {
        const row = document.createElement('tr');
        row.className = `batch-row ${item.status}`;
        row.setAttribute('tabindex', '0');
        row.setAttribute('role', 'button');
        row.setAttribute('aria-expanded', 'false');
        row.dataset.itemId = item.id;
        
        // Status badges
        const statusBadges = {
            'queued': '<span class="status-badge queued"><i class="fas fa-clock"></i> Queued</span>',
            'processing': '<span class="status-badge processing"><i class="fas fa-cog fa-spin"></i> Processing</span>',
            'completed': '<span class="status-badge completed"><i class="fas fa-check"></i> Completed</span>',
            'failed': '<span class="status-badge failed"><i class="fas fa-times"></i> Failed</span>',
            'orphaned': '<span class="status-badge orphaned"><i class="fas fa-exclamation-triangle"></i> Orphaned</span>'
        };

        // Handle componentized vs standard items
        const isComponentized = item.type === 'componentized';

        // Progress bar - enhanced for componentized items
        const progressText = item.status === 'processing' && isComponentized && item.currentComponent
            ? `<span class="progress-text">${item.progress}%</span><span class="component-progress">${item.currentComponent}</span>`
            : `<span class="progress-text">${item.progress}%</span>`;

        const progressBar = `
            <div class="progress-container">
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${item.progress}%"></div>
                </div>
                ${progressText}
            </div>
        `;

        // Offset display - different for componentized items
        let offsetDisplay = '-';
        if (isComponentized) {
            // Show mini table for componentized items
            offsetDisplay = this.renderComponentizedResultCell(item);
        } else {
            // Standard single offset display
            const offsetSeconds = item.result?.offset_seconds ?? item.result?.consensus_offset?.offset_seconds;
            if (offsetSeconds !== undefined) {
                const fps = item.frameRate || this.detectedFrameRate;
                offsetDisplay = this.formatOffsetDisplay(offsetSeconds, true, fps);
            }
        }

        // File cell - show components count for componentized items
        const dubFileCell = isComponentized
            ? `<span class="component-badge">${item.components.length} components</span>`
            : `<i class="fas fa-file-video"></i>
               <span class="file-name" title="${item.dub.path}">${item.dub.name}</span>`;

        row.innerHTML = `
            <td class="expand-cell">
                <button class="expand-btn" ${item.result || item.componentResults?.length > 0 ? '' : 'disabled'}
                        title="${item.result || item.componentResults?.length > 0 ? 'View analysis details' : 'Analysis not complete'}">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
            <td class="file-cell">
                <i class="fas ${isComponentized ? 'fa-layer-group' : 'fa-file-video'}"></i>
                <span class="file-name" title="${item.master.path}">${item.master.name}</span>
            </td>
            <td class="file-cell">
                ${dubFileCell}
            </td>
            <td class="status-cell">${statusBadges[item.status]}</td>
            <td class="progress-cell">${progressBar}</td>
            <td class="result-cell">${offsetDisplay}</td>
            <td class="actions-cell">
                <div class="action-buttons">
                    ${item.status === 'completed' && !isComponentized ? `
                        <button class="action-btn-v2 qc"
                                data-item-id="${item.id}"
                                data-action="qc"
                                data-master-id="${item.master.id || item.id + '_master'}"
                                data-dub-id="${item.dub.id || item.id + '_dub'}"
                                data-offset="${item.result?.offset_seconds || 0}"
                                data-master-path="${item.master.path}"
                                data-dub-path="${item.dub.path}"
                                title="Open Quality Control Interface (Keyboard: Q)"
                                aria-label="Open Quality Control Interface for ${item.master.name}">
                            <i class="fas fa-microscope" aria-hidden="true"></i>
                            <span class="btn-label-full">QC</span>
                            <span class="btn-label-short">QC</span>
                            <span class="shortcut-hint">Q</span>
                        </button>
                        <button class="action-btn-v2 repair"
                                data-item-id="${item.id}"
                                data-action="repair"
                                data-master-path="${item.master.path}"
                                data-dub-path="${item.dub.path}"
                                data-offset="${item.result?.offset_seconds || 0}"
                                title="Open Repair Interface (Keyboard: R)"
                                aria-label="Open Repair Interface for ${item.master.name}">
                            <i class="fas fa-wrench" aria-hidden="true"></i>
                            <span class="btn-label-full">Repair</span>
                            <span class="btn-label-short">Rep</span>
                            <span class="shortcut-hint">R</span>
                        </button>
                    ` : ''}
                    ${item.status === 'completed' && isComponentized ? `
                        <button class="action-btn-v2 qc componentized"
                                data-item-id="${item.id}"
                                data-action="qc-componentized"
                                data-master-path="${item.master.path}"
                                title="Open Componentized QC Interface (Keyboard: Q)"
                                aria-label="Open Componentized Quality Control Interface for ${item.master.name}">
                            <i class="fas fa-microscope" aria-hidden="true"></i>
                            <span class="btn-label-full">QC</span>
                            <span class="btn-label-short">QC</span>
                            <span class="shortcut-hint">Q</span>
                        </button>
                        <button class="action-btn-v2 repair componentized"
                                data-item-id="${item.id}"
                                data-action="repair-componentized"
                                data-master-path="${item.master.path}"
                                title="Open Componentized Repair Interface (Keyboard: R)"
                                aria-label="Open Componentized Repair Interface for ${item.master.name}">
                            <i class="fas fa-wrench" aria-hidden="true"></i>
                            <span class="btn-label-full">Repair</span>
                            <span class="btn-label-short">Rep</span>
                            <span class="shortcut-hint">R</span>
                        </button>
                    ` : ''}
                    ${item.status === 'completed' ? `
                        <button class="action-btn-v2 details"
                                data-item-id="${item.id}"
                                data-action="details"
                                title="View Analysis Details (Keyboard: D)"
                                aria-label="View detailed analysis for ${item.master.name}">
                            <i class="fas fa-chart-line" aria-hidden="true"></i>
                            <span class="btn-label-full">Details</span>
                            <span class="btn-label-short">Det</span>
                            <span class="shortcut-hint">D</span>
                        </button>
                        <button class="action-btn-v2 restart"
                                data-item-id="${item.id}"
                                data-action="restart"
                                title="Re-run Analysis (Keyboard: T)"
                                aria-label="Re-run analysis for ${item.master.name}">
                            <i class="fas fa-sync-alt" aria-hidden="true"></i>
                            <span class="btn-label-full">Restart</span>
                            <span class="btn-label-short">Re</span>
                            <span class="shortcut-hint">T</span>
                        </button>
                    ` : ''}
                    ${(item.status === 'failed' || item.status === 'orphaned') ? `
                        <button class="action-btn-v2 retry"
                                data-item-id="${item.id}"
                                data-action="retry"
                                title="Retry Failed Analysis"
                                aria-label="Retry analysis for ${item.master.name}">
                            <i class="fas fa-redo" aria-hidden="true"></i>
                            <span class="btn-label-full">Retry</span>
                            <span class="btn-label-short">Ret</span>
                        </button>
                    ` : ''}
                    <button class="action-btn-v2 remove"
                            data-item-id="${item.id}"
                            data-action="remove"
                            ${this.batchProcessing ? 'disabled' : ''}
                            title="Remove from batch (Keyboard: Delete)"
                            aria-label="Remove ${item.master.name} from batch">
                        <i class="fas fa-trash" aria-hidden="true"></i>
                        <span class="btn-label-full">Remove</span>
                        <span class="btn-label-short">Rem</span>
                        <span class="shortcut-hint">Del</span>
                    </button>
                </div>
            </td>
        `;
        
        const hasResults = isComponentized
            ? (item.componentResults && item.componentResults.length > 0)
            : !!item.result;

        // Add expand functionality
        const expandBtn = row.querySelector('.expand-btn');
        if (expandBtn) {
            expandBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                console.log('Expand button clicked:', {
                    itemId: item.id,
                    disabled: expandBtn.disabled,
                    hasResult: hasResults,
                    status: item.status
                });
                
                if (!expandBtn.disabled && hasResults) {
                    this.toggleBatchDetails(item);
                    try { row.setAttribute('aria-expanded', String(!(row.getAttribute('aria-expanded') === 'true'))); } catch {}
                } else if (!hasResults) {
                    this.addLog('info', 'No results available yet - analysis must complete first');
                } else if (expandBtn.disabled) {
                    this.addLog('info', 'Expand button is disabled - analysis may be in progress');
                }
            });
        }

        // Row click shows details in the Batch Details quadrant (not dropdown)
        const showInQuadrant = (e) => {
            // Skip if clicking action buttons or expand button
            if (e && e.target && e.target.closest && (e.target.closest('.action-buttons') || e.target.closest('.expand-btn'))) return;
            
            // Show details in the dedicated quadrant (regardless of results status)
            this.showItemDetailsInQuadrant(item);
            
            // Highlight the selected row
            document.querySelectorAll('.batch-row.selected').forEach(r => r.classList.remove('selected'));
            row.classList.add('selected');
        };
        row.addEventListener('click', showInQuadrant);
        row.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); showInQuadrant(e); }
        });
        
        return row;
    }

    /**
     * Render componentized result cell with mini table of all component offsets
     */
    renderComponentizedResultCell(item) {
        if (!item.componentResults || item.componentResults.length === 0) {
            return '<div class="component-results-pending">Pending...</div>';
        }

        const resultsHtml = item.componentResults.map(result => {
            const fps = result.frameRate || item.frameRate || this.detectedFrameRate;
            const timecode = this.formatTimecode(result.offset_seconds, fps);
            const timecodeWithSeconds = this.formatTimecodeWithSeconds(result.offset_seconds, fps);
            const confidence = (result.confidence * 100).toFixed(0);

            return `
                <div class="comp-result-row">
                    <span class="comp-label" title="Component ${result.component}">${result.component}</span>
                    <span class="comp-offset" title="Offset: ${timecodeWithSeconds}">${timecode}</span>
                    <span class="comp-conf" title="Confidence">${confidence}%</span>
                </div>
            `;
        }).join('');

        return `<div class="component-results-mini-table">${resultsHtml}</div>`;
    }

    updateBatchTableRow(item) {
        const row = document.querySelector(`tr[data-item-id="${item.id}"]`);
        if (row) {
            const newRow = this.createBatchTableRow(item);
            row.parentNode.replaceChild(newRow, row);
        }
    }
    
    async toggleBatchDetails(item) {
        const isComponentized = item.type === 'componentized';
        const hasComponentResults = Array.isArray(item.componentResults) && item.componentResults.length > 0;
        const hasResults = isComponentized ? hasComponentResults : !!item.result;

        if (!hasResults && !isComponentized) {
            this.addLog('warning', 'No analysis results available to display');
            return;
        }

        const detailsDiv = this.elements.batchDetails;
        const contentDiv = this.elements.detailsContent;
        const loadingDiv = this.elements.detailsLoading;

        // Toggle button visual state
        const expandBtn = document.querySelector(`tr[data-item-id="${item.id}"] .expand-btn`);
        if (expandBtn) {
            expandBtn.classList.toggle('expanded');
        }

        // If details are already shown for this item, close them
        if (detailsDiv.style.display === 'block' && detailsDiv.dataset.currentItem === item.id.toString()) {
            this.closeBatchDetails();
            return;
        }

        // Switch to Batch Details view in Quadrant 2
        this.showBatchDetailsInQuadrant(item.id);

        // Show loading state first
        contentDiv.innerHTML = '';
        contentDiv.appendChild(loadingDiv);
        loadingDiv.style.display = 'flex';

        // Update subtitle (different for componentized items)
        if (isComponentized) {
            this.elements.detailsSubtitle.textContent = `${item.master.name} with ${item.components.length} components`;
        } else {
            this.elements.detailsSubtitle.textContent = `${item.master.name} vs ${item.dub.name}`;
        }

        // Handle componentized items differently
        if (isComponentized) {
            if (!hasComponentResults) {
                this.addLog('warning', 'Component results not available yet - showing placeholder details');
            }
            this.renderComponentizedDetails(item, contentDiv);
            detailsDiv.dataset.currentItem = item.id.toString();
            detailsDiv.style.display = 'block';
            this.updateBatchDetailsSplit(true);
            detailsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            return;
        }

        // Fetch full analysis data to ensure we have complete raw data
        let result = item.result;
        if (item.analysisId && (!result.method_results || !result.consensus_offset)) {
            try {
                this.addLog('info', 'Fetching complete analysis data...');
                const response = await fetch(`${this.FASTAPI_BASE}/analysis/${item.analysisId}`);
                if (response.ok) {
                    const fullData = await response.json();
                    if (fullData.success && fullData.result) {
                        const normalized = this.normalizeAnalysisResult(fullData.result, item.analysisId);
                        result = normalized || fullData.result;
                        item.result = result; // Cache the normalized result
                        console.log('Fetched complete analysis data with method_results:', result);
                    }
                }
            } catch (error) {
                console.warn('Failed to fetch complete analysis data:', error);
                this.addLog('warning', 'Could not load complete analysis data, showing cached results');
            }
        }

        console.log('Expanding item result:', result);
        console.log('Full item:', item);

        // Use item's detected frame rate if available, otherwise fall back to global
        const itemFps = item.frameRate || this.detectedFrameRate;

        const normalizedResult = this.normalizeAnalysisResult(result, item.analysisId) || result;
        if (normalizedResult && normalizedResult !== result) {
            result = normalizedResult;
            item.result = normalizedResult;
        }

        // Handle missing result properties gracefully
        const offsetSeconds = result?.offset_seconds ?? 0;
        const confidence = result?.confidence ?? 0;
        const methodUsed = result?.method_used ?? 'Unknown';
        const qualityScore = result?.quality_score ?? 0;

        // Get frame display with fallback
        let offsetFrames = 'N/A';
        try {
            if (typeof offsetSeconds === 'number' && !Number.isNaN(offsetSeconds) &&
                typeof itemFps === 'number' && !Number.isNaN(itemFps)) {
                const frames = Math.round(Math.abs(offsetSeconds) * itemFps);
                const frameSign = offsetSeconds < 0 ? '-' : '+';
                offsetFrames = `${frameSign}${frames}f @ ${itemFps}fps`;
            }
        } catch (error) {
            console.warn('Frame display calculation failed:', error);
            offsetFrames = `${(offsetSeconds * itemFps).toFixed(0)} frames @ ${itemFps}fps`;
        }
        
        // Get method display name with fallback
        let methodDisplayName = methodUsed;
        try {
            methodDisplayName = this.getMethodDisplayName(methodUsed);
        } catch (error) {
            console.warn('Method display name failed:', error);
        }
        
        this.addLog('info', `Showing detailed results for: ${item.master.name}`);

        // Generate enhanced details view for the slide-over panel
        const enhancedDetailsHtml = this.generateEnhancedDetailsView(item, result, offsetSeconds, confidence, methodDisplayName, qualityScore, offsetFrames, itemFps);
        contentDiv.innerHTML = enhancedDetailsHtml;

        // Update Quadrant 2 with a simplified summary (not full waveform to avoid duplicate IDs)
        const q2Placeholder = document.getElementById('batch-details-placeholder');
        const q2Content = document.getElementById('batch-details-content');
        if (q2Placeholder && q2Content) {
            q2Placeholder.style.display = 'none';
            q2Content.style.display = 'block';
            q2Content.innerHTML = this.generateQuadrantSummary(item, result, offsetSeconds, confidence, methodDisplayName, offsetFrames, itemFps);
        }

        // Store current item ID and show details
        detailsDiv.dataset.currentItem = item.id.toString();
        detailsDiv.style.display = 'block';
        this.updateBatchDetailsSplit(true);

        // Lazy-load waveform: only initialize when section is expanded
        const waveformSection = document.getElementById(`section-waveform-${item.id}`);
        if (waveformSection) {
            const sectionHeader = waveformSection.querySelector('.section-header');
            const initWaveformOnce = () => {
                if (!waveformSection.dataset.waveformInitialized) {
                    waveformSection.dataset.waveformInitialized = 'true';
                    this.initializeEnhancedWaveform(item, offsetSeconds);
                }
            };
            // Initialize on first expand click
            sectionHeader?.addEventListener('click', initWaveformOnce, { once: true });
        }

        // Bind per-channel repair button if per-channel results exist
        try {
            const btn = document.getElementById(`perch-btn-${item.id}`);
            if (btn) {
                btn.addEventListener('click', async () => {
                    const out = document.getElementById(`perch-out-${item.id}`)?.value || '';
                    const keep = !!document.getElementById(`perch-keep-${item.id}`)?.checked;
                    const per = result.per_channel_results || {};
                    if (!Object.keys(per).length) {
                        this.addLog('warning', 'No per-channel results available for repair');
                        return;
                    }
                    this.addLog('info', 'Starting per-channel repair...');
                    try {
                        const resp = await fetch(`${this.FASTAPI_BASE}/repair/repair/per-channel`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                file_path: item.dub.path,
                                per_channel_results: per,
                                output_path: out,
                                keep_duration: keep
                            })
                        });
                        const j = await resp.json();
                        if (resp.ok && j.success) {
                            this.addLog('success', `Per-channel repair complete: ${j.output_file}`);
                        } else {
                            this.addLog('error', `Per-channel repair failed: ${j.error || resp.status}`);
                        }
                    } catch (e) {
                        this.addLog('error', `Per-channel repair error: ${e.message}`);
                    }
                });
            }
        } catch (e) {
            console.warn('Per-channel repair bind failed:', e);
        }

        // Scroll details into view
        detailsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    /**
     * Update active jobs display in Console Status quadrant
     */
    updateActiveJobsDisplay() {
        // Add null checks to prevent crashes if elements don't exist
        if (!this.elements.activeJobsContainer || !this.elements.activeJobsList || !this.elements.activeJobsCount) {
            console.warn('[updateActiveJobsDisplay] Active jobs elements not found in DOM, skipping update');
            return;
        }

        const activeJobsArray = Array.from(this.activeJobs.values());

        // Show/hide container based on active jobs
        if (activeJobsArray.length === 0) {
            this.elements.activeJobsContainer.style.display = 'none';
            return;
        }

        this.elements.activeJobsContainer.style.display = 'block';
        this.elements.activeJobsCount.textContent = `${activeJobsArray.length} running`;

        // Build HTML for all active jobs
        const jobsHtml = activeJobsArray.map(item => {
            const percentage = item.progress || 0;
            const jobName = item.master?.name || 'Unknown';
            const message = item.progressMessage || (item.status === 'processing' ? 'Processing...' : '');

            return `
                <div class="active-job-item" data-item-id="${item.id}">
                    <div class="active-job-header">
                        <span class="active-job-name" title="${jobName}">${jobName}</span>
                        <span class="active-job-percentage">${percentage}%</span>
                    </div>
                    <div class="active-job-progress-bar">
                        <div class="active-job-progress-fill" style="width: ${percentage}%"></div>
                    </div>
                    ${message ? `<div class="active-job-message">${message}</div>` : ''}
                </div>
            `;
        }).join('');

        this.elements.activeJobsList.innerHTML = jobsHtml;
    }

    /**
     * Render componentized item details panel
     */
    renderComponentizedDetails(item, contentDiv) {
        const fps = item.frameRate || this.detectedFrameRate;
        const componentResults = Array.isArray(item.componentResults) ? item.componentResults : [];
        const hasResults = componentResults.length > 0;
        const offsetMode = (item.offsetMode || 'mixdown').toUpperCase();
        const mixdownOffset = typeof item.mixdownOffsetSeconds === 'number' ? item.mixdownOffsetSeconds : null;
        const mixdownDisplay = mixdownOffset !== null ? this.formatTimecodeWithSeconds(mixdownOffset, fps) : 'N/A';

        const detailsHtml = `
            <div class="details-content-v2">
                <!-- Master File Info -->
                <div class="details-section expanded">
                    <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <div class="section-title">
                            <i class="fas fa-file-video"></i>
                            <span>Master File</span>
                        </div>
                        <i class="fas fa-chevron-down section-toggle"></i>
                    </div>
                    <div class="section-content">
                        <div class="master-info-card">
                            <div class="info-row">
                                <span class="label">File Name:</span>
                                <span class="value">${item.master.name}</span>
                            </div>
                            <div class="info-row">
                                <span class="label">File Path:</span>
                                <span class="value file-path">${item.master.path}</span>
                            </div>
                            <div class="info-row">
                                <span class="label">Frame Rate:</span>
                                <span class="value">${fps} fps</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Master Findings Banner -->
                ${item.masterFindings && item.masterFindings.length > 0 ? `
                <div class="master-findings-banner">
                    <i class="fas fa-info-circle"></i>
                    <div class="findings-list">
                        ${item.masterFindings.map(f => `<span class="finding-item">${f}</span>`).join('')}
                    </div>
                </div>
                ` : ''}

                <!-- Component Results Table -->
                <div class="details-section expanded">
                    <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <div class="section-title">
                            <i class="fas fa-layer-group"></i>
                            <span>All Components (${item.components.length})</span>
                        </div>
                        <i class="fas fa-chevron-down section-toggle"></i>
                    </div>
                    <div class="section-content">
                        <table class="component-summary-table">
                            <thead>
                                <tr>
                                    <th>Component</th>
                                    <th>File Name</th>
                                    <th>Offset</th>
                                    <th>Confidence</th>
                                    <th>Findings</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${hasResults ? componentResults.map((result, index) => {
                                    const component = item.components[index];
                                    const timecode = this.formatTimecodeWithSeconds(result.offset_seconds, result.frameRate || fps);
                                    const confidence = (result.confidence * 100).toFixed(1);
                                    const findings = result.findings || [];
                                    const findingsHtml = findings.length > 0 
                                        ? findings.map(f => `<span class="finding-tag">${f}</span>`).join('')
                                        : '<span class="no-findings">—</span>';
                                    return `
                                        <tr>
                                            <td><span class="comp-label">${result.component}</span></td>
                                            <td class="file-name-cell" title="${component.path}">${component.name}</td>
                                            <td class="offset-cell">${timecode}</td>
                                            <td class="confidence-cell">${confidence}%</td>
                                            <td class="findings-cell">${findingsHtml}</td>
                                            <td class="actions-cell">
                                                <button class="action-btn-mini" onclick="app.viewComponentDetails(${item.id}, ${index})" title="View details">
                                                    <i class="fas fa-eye"></i>
                                                </button>
                                            </td>
                                        </tr>
                                    `;
                                }).join('') : `
                                    <tr>
                                        <td colspan="6" style="text-align:center; color:#94a3b8; padding: 18px;">
                                            Results pending or unavailable for this componentized item.
                                        </td>
                                    </tr>
                                `}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Stacked Waveforms Visualization -->
                <div class="details-section expanded" id="waveform-section-${item.id}">
                    <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <div class="section-title">
                            <i class="fas fa-waveform-lines"></i>
                            <span>Offset Visualization</span>
                        </div>
                        <i class="fas fa-chevron-down section-toggle"></i>
                    </div>
                    <div class="section-content">
                        <div class="stacked-waveforms-container" id="stacked-waveforms-${item.id}">
                            <div class="waveform-loading">
                                <i class="fas fa-spinner fa-spin"></i>
                                <span>Loading waveforms...</span>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Analysis Summary -->
                <div class="details-section">
                    <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <div class="section-title">
                            <i class="fas fa-chart-bar"></i>
                            <span>Analysis Summary</span>
                        </div>
                        <i class="fas fa-chevron-down section-toggle"></i>
                    </div>
                    <div class="section-content">
                        <div class="summary-stats">
                            <div class="stat-card">
                                <div class="stat-label">Total Components</div>
                                <div class="stat-value">${item.components.length}</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Offset Mode</div>
                                <div class="stat-value">${offsetMode}</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Mixdown Offset</div>
                                <div class="stat-value">${mixdownDisplay}</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Completed</div>
                                <div class="stat-value">${componentResults.length}</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-label">Average Offset</div>
                                <div class="stat-value">${this.calculateAverageOffset(componentResults, fps)}</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Raw Component Data -->
                <div class="details-section">
                    <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <div class="section-title">
                            <i class="fas fa-code"></i>
                            <span>Raw Component Data</span>
                        </div>
                        <i class="fas fa-chevron-down section-toggle"></i>
                    </div>
                    <div class="section-content">
                        <pre class="json-display">${JSON.stringify(componentResults, null, 2)}</pre>
                    </div>
                </div>
            </div>
        `;

        contentDiv.innerHTML = detailsHtml;
        this.elements.detailsLoading.style.display = 'none';

        // Render stacked waveforms after DOM is updated
        if (hasResults) {
            setTimeout(() => {
                this.renderStackedWaveforms(item);
            }, 100);
        } else {
            const container = document.getElementById(`stacked-waveforms-${item.id}`);
            if (container) {
                container.innerHTML = `
                    <div style="padding: 20px; text-align: center; color: #94a3b8;">
                        <i class="fas fa-info-circle" style="margin-right: 6px;"></i>
                        <span>No waveform data available yet for this item.</span>
                    </div>
                `;
            }
        }
    }

    /**
     * Calculate average offset for componentized results
     */
    calculateAverageOffset(componentResults, fps) {
        if (!componentResults || componentResults.length === 0) return 'N/A';

        const avgSeconds = componentResults.reduce((sum, r) => sum + r.offset_seconds, 0) / componentResults.length;
        return this.formatTimecodeWithSeconds(avgSeconds, fps);
    }

    /**
     * View individual component details (placeholder for future enhancement)
     */
    viewComponentDetails(itemId, componentIndex) {
        const item = this.batchQueue.find(i => i.id === itemId);
        if (!item || !item.componentResults[componentIndex]) {
            this.addLog('warning', 'Component details not available');
            return;
        }

        const component = item.components[componentIndex];
        const result = item.componentResults[componentIndex];

        this.addLog('info', `Viewing details for component: ${component.label}`);
        // Future enhancement: Could show detailed method results, waveform, etc. for this specific component
    }

    /**
     * Render stacked waveforms showing offset visualization with real audio waveforms
     */
    async renderStackedWaveforms(item) {
        const container = document.getElementById(`stacked-waveforms-${item.id}`);
        if (!container) {
            console.warn('Waveforms container not found');
            return;
        }

        if (!Array.isArray(item.componentResults) || item.componentResults.length === 0) {
            container.innerHTML = `
                <div style="padding: 20px; text-align: center; color: #94a3b8;">
                    <i class="fas fa-info-circle" style="margin-right: 6px;"></i>
                    <span>No component results available to render waveforms.</span>
                </div>
            `;
            return;
        }

        try {
            // Show loading state
            container.innerHTML = `
                <div style="padding: 40px; text-align: center; color: #64748b;">
                    <i class="fas fa-spinner fa-spin" style="font-size: 32px; margin-bottom: 12px;"></i>
                    <p>Loading audio waveforms...</p>
                </div>
            `;

            const offsets = item.componentResults.map(r => Number(r.offset_seconds) || 0);
            const minOffset = offsets.length ? Math.min(...offsets, 0) : 0;
            const maxOffset = offsets.length ? Math.max(...offsets, 0) : 0;

            // Get audio URLs
            const masterUrl = this.getAudioUrlForFile(item.master.path, 'master');
            const componentUrls = item.components.map(comp => ({
                url: this.getAudioUrlForFile(comp.path, 'dub'),
                component: comp
            }));

            // Initialize audio engine if needed
            if (!this.waveformVisualizer || !this.waveformVisualizer.audioEngine) {
                if (!this.waveformVisualizer) {
                    this.waveformVisualizer = new WaveformVisualizer();
                }
                if (!this.waveformVisualizer.audioEngine) {
                    this.waveformVisualizer.audioEngine = new CoreAudioEngine();
                }
            }
            const audioEngine = this.waveformVisualizer.audioEngine;

            // Load master audio
            let masterWaveformData = null;
            try {
                masterWaveformData = await audioEngine.loadAudioUrl(masterUrl, 'master');
            } catch (err) {
                console.error('Failed to load master audio:', err);
                throw new Error(`Failed to load master audio: ${err.message}`);
            }

            // Load all component audio files
            const componentWaveformData = [];
            for (let i = 0; i < componentUrls.length; i++) {
                try {
                    const waveformData = await audioEngine.loadAudioUrl(componentUrls[i].url, `component-${i}`);
                    componentWaveformData.push({
                        waveformData,
                        component: componentUrls[i].component,
                        result: item.componentResults[i]
                    });
                } catch (err) {
                    console.error(`Failed to load component ${i} audio:`, err);
                    // Continue with other components even if one fails
                    componentWaveformData.push({
                        waveformData: null,
                        component: componentUrls[i].component,
                        result: item.componentResults[i]
                    });
                }
            }

            // Calculate canvas dimensions based on actual durations
            const durations = [
                masterWaveformData?.duration || 0,
                ...componentWaveformData.map(entry => entry.waveformData?.duration || 0)
            ];
            const maxDuration = Math.max(...durations, 0);
            const startTime = Math.min(0, minOffset);
            const endTime = Math.max(maxDuration + Math.max(0, maxOffset), maxDuration);
            const timeRange = Math.max(endTime - startTime, 30);
            const gridIntervalSeconds = this.getWaveformGridInterval(timeRange);

            const waveformHeight = 70;
            const labelHeight = 14;
            const trackSpacing = 16;
            const labelWidth = 76;
            const labelGap = 10;
            const labelArea = labelWidth + labelGap;
            const pixelsPerSecond = this.getWaveformPixelsPerSecond(timeRange);
            const waveformPixelWidth = Math.min(4000, Math.max(1200, Math.round(timeRange * pixelsPerSecond)));
            const canvasWidth = waveformPixelWidth + labelArea;

            // Create container structure
            container.innerHTML = `
                <div class="waveform-timeline-container" style="position: relative; width: 100%; background: rgba(8, 15, 32, 0.65); border: 1px solid rgba(148, 163, 184, 0.25); border-radius: 8px; padding: 38px 20px 22px; overflow-x: auto;">
                    <!-- Master waveform track -->
                    <div class="waveform-track" style="position: relative; width: ${canvasWidth}px; height: ${waveformHeight}px; margin-bottom: ${trackSpacing}px;">
                        <div class="track-label" style="position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: ${labelWidth}px; text-align: center; font-size: 11px; font-weight: 700; letter-spacing: 0.04em; color: #f8fafc; background: rgba(37, 99, 235, 0.92); border: 1px solid rgba(255, 255, 255, 0.2); padding: 4px 6px; border-radius: 4px; z-index: 10;">
                            AREF
                        </div>
                        <canvas id="master-waveform-${item.id}" 
                                style="position: absolute; left: ${labelArea}px; top: 0; width: ${waveformPixelWidth}px; height: ${waveformHeight}px;"
                                width="${Math.floor(waveformPixelWidth * (window.devicePixelRatio || 1))}"
                                height="${Math.floor(waveformHeight * (window.devicePixelRatio || 1))}">
                        </canvas>
                    </div>

                    <!-- Component waveform tracks -->
                    ${item.componentResults.map((result, index) => {
                        const fps = result.frameRate || item.frameRate || this.detectedFrameRate;
                        const timecode = this.formatTimecode(result.offset_seconds, fps);
                        const timecodeWithSeconds = this.formatTimecodeWithSeconds(result.offset_seconds, fps);
                        const offsetLeft = labelArea + ((result.offset_seconds - startTime) / timeRange) * waveformPixelWidth;
                        const clampedOffsetLeft = Math.max(labelArea, Math.min(labelArea + waveformPixelWidth, offsetLeft));
                        return `
                            <div class="waveform-track" style="position: relative; width: ${canvasWidth}px; height: ${waveformHeight}px; margin-bottom: ${trackSpacing}px;">
                                <div class="track-label" style="position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: ${labelWidth}px; text-align: center; font-size: 11px; font-weight: 700; letter-spacing: 0.04em; color: #f8fafc; background: rgba(21, 128, 61, 0.92); border: 1px solid rgba(255, 255, 255, 0.18); padding: 4px 6px; border-radius: 4px; z-index: 10;">
                                    ${result.component}
                                </div>
                                <canvas id="component-waveform-${item.id}-${index}" 
                                        style="position: absolute; left: ${labelArea}px; top: 0; width: ${waveformPixelWidth}px; height: ${waveformHeight}px;"
                                        width="${Math.floor(waveformPixelWidth * (window.devicePixelRatio || 1))}"
                                        height="${Math.floor(waveformHeight * (window.devicePixelRatio || 1))}">
                                </canvas>
                                <div class="offset-indicator" title="Offset: ${timecodeWithSeconds}" style="position: absolute; left: ${clampedOffsetLeft}px; top: 2px; background: rgba(248, 113, 113, 0.95); color: #0f172a; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.35); z-index: 20;">
                                    Offset: ${timecode}
                                </div>
                            </div>
                        `;
                    }).join('')}

                    <!-- Zero reference line -->
                    <div class="zero-line" style="position: absolute; left: ${labelArea + ((0 - startTime) / timeRange) * waveformPixelWidth}px; top: 0; bottom: 0; width: 2px; background: rgba(248, 113, 113, 0.9); box-shadow: 0 0 8px rgba(248, 113, 113, 0.35); z-index: 5;">
                        <div style="position: absolute; top: 2px; left: 50%; transform: translateX(-50%); background: rgba(34, 197, 94, 0.95); color: #0f172a; padding: 3px 8px; border-radius: 3px; font-size: 10px; font-weight: 700; white-space: nowrap; box-shadow: 0 2px 4px rgba(0,0,0,0.35);">
                            Zero: 00:00:00:00
                        </div>
                    </div>
                </div>

                <div class="waveform-legend" style="margin-top: 14px; display: flex; gap: 24px; font-size: 12px; color: #cbd5f5;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="width: 30px; height: 16px; background: rgba(37, 99, 235, 0.92); border: 1px solid rgba(255, 255, 255, 0.2); border-radius: 2px;"></div>
                        <span>AREF (Reference)</span>
                    </div>
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div style="width: 30px; height: 16px; background: rgba(21, 128, 61, 0.92); border: 1px solid rgba(255, 255, 255, 0.18); border-radius: 2px;"></div>
                        <span>OUTPUT (Components)</span>
                    </div>
                </div>
            `;

            // Render master waveform (blue - AREF)
            const masterCanvas = container.querySelector(`#master-waveform-${item.id}`);
            if (masterCanvas && masterWaveformData) {
                this.drawRealWaveform(masterCanvas, masterWaveformData, {
                    color: 'rgba(248, 250, 252, 0.98)',
                    fillColor: 'rgba(248, 250, 252, 0.85)',
                    backgroundColor: 'rgba(30, 64, 175, 0.95)',
                    startTime,
                    timeRange,
                    gridIntervalSeconds,
                    labelHeight,
                    showTimeLabels: true,
                    gridColor: 'rgba(248, 250, 252, 0.18)',
                    labelColor: 'rgba(248, 250, 252, 0.8)',
                    centerLineColor: 'rgba(248, 250, 252, 0.12)'
                });
            }

            // Render component waveforms (green - OUTPUT)
            componentWaveformData.forEach((compData, index) => {
                const compCanvas = container.querySelector(`#component-waveform-${item.id}-${index}`);
                if (compCanvas && compData.waveformData) {
                    this.drawRealWaveform(compCanvas, compData.waveformData, {
                        color: 'rgba(248, 250, 252, 0.96)',
                        fillColor: 'rgba(248, 250, 252, 0.8)',
                        backgroundColor: 'rgba(21, 128, 61, 0.95)',
                        startTime,
                        timeRange,
                        gridIntervalSeconds,
                        labelHeight,
                        showTimeLabels: true,
                        gridColor: 'rgba(248, 250, 252, 0.18)',
                        labelColor: 'rgba(248, 250, 252, 0.8)',
                        centerLineColor: 'rgba(248, 250, 252, 0.12)',
                        offsetSeconds: compData.result.offset_seconds
                    });
                }
            });

        } catch (error) {
            console.error('Failed to render stacked waveforms:', error);
            container.innerHTML = `
                <div style="padding: 40px; text-align: center; color: #64748b;">
                    <i class="fas fa-exclamation-triangle" style="font-size: 32px; margin-bottom: 12px; opacity: 0.5;"></i>
                    <p>Failed to render waveform visualization</p>
                    <p style="font-size: 11px; margin-top: 8px; opacity: 0.7;">${error.message}</p>
                </div>
            `;
        }
    }

    /**
     * Draw real waveform on canvas from waveform data
     */
    drawRealWaveform(canvas, waveformData, options = {}) {
        const ctx = canvas.getContext('2d');
        const dpr = window.devicePixelRatio || 1;
        const width = canvas.width / dpr;
        const height = canvas.height / dpr;

        // Set up canvas for high DPI
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.scale(dpr, dpr);

        // Clear and fill background
        ctx.fillStyle = options.backgroundColor || 'rgba(15, 23, 42, 0.5)';
        ctx.fillRect(0, 0, width, height);

        if (!waveformData || !waveformData.peaks) {
            return;
        }

        const peaks = waveformData.peaks;
        const duration = waveformData.duration || (waveformData.width / 100); // Estimate if missing
        const timeRange = options.timeRange || duration;
        const startTime = options.startTime || 0;
        const offsetSeconds = options.offsetSeconds || 0;
        const labelHeight = options.labelHeight || 0;
        const labelIntervalSeconds = options.labelIntervalSeconds || options.gridIntervalSeconds || 0;

        // Calculate pixels per second
        const pixelsPerSecond = width / timeRange;

        const waveformHeight = Math.max(0, height - labelHeight);
        const centerY = waveformHeight / 2;
        const amplitude = waveformHeight * 0.45; // Use 90% of waveform area for waveform (45% up, 45% down)

        ctx.fillStyle = options.fillColor || 'rgba(148, 163, 184, 0.3)';
        ctx.strokeStyle = options.color || '#94a3b8';
        ctx.lineWidth = 1.5;

        // Draw filled waveform
        ctx.beginPath();
        ctx.moveTo(0, centerY);

        // Draw top half of waveform
        for (let i = 0; i < width; i++) {
            const timeAtPixel = startTime + (i / pixelsPerSecond);
            // Apply correction offset so positive values delay the component to align with master
            const adjustedTime = timeAtPixel - offsetSeconds;
            const sampleIndex = Math.floor((adjustedTime / duration) * peaks.length);
            
            if (sampleIndex >= 0 && sampleIndex < peaks.length) {
                const peak = Math.max(0, Math.min(1, peaks[sampleIndex])); // Clamp to 0-1
                const y = centerY - (peak * amplitude);
                ctx.lineTo(i, y);
            } else {
                ctx.lineTo(i, centerY);
            }
        }

        // Draw bottom half of waveform
        for (let i = width - 1; i >= 0; i--) {
            const timeAtPixel = startTime + (i / pixelsPerSecond);
            const adjustedTime = timeAtPixel - offsetSeconds;
            const sampleIndex = Math.floor((adjustedTime / duration) * peaks.length);
            
            if (sampleIndex >= 0 && sampleIndex < peaks.length) {
                const peak = Math.max(0, Math.min(1, peaks[sampleIndex]));
                const y = centerY + (peak * amplitude);
                ctx.lineTo(i, y);
            } else {
                ctx.lineTo(i, centerY);
            }
        }

        ctx.closePath();
        ctx.fill();

        // Draw waveform outline (top)
        ctx.beginPath();
        let firstPoint = true;
        for (let i = 0; i < width; i++) {
            const timeAtPixel = startTime + (i / pixelsPerSecond);
            const adjustedTime = timeAtPixel - offsetSeconds;
            const sampleIndex = Math.floor((adjustedTime / duration) * peaks.length);
            
            if (sampleIndex >= 0 && sampleIndex < peaks.length) {
                const peak = Math.max(0, Math.min(1, peaks[sampleIndex]));
                const y = centerY - (peak * amplitude);
                if (firstPoint) {
                    ctx.moveTo(i, y);
                    firstPoint = false;
                } else {
                    ctx.lineTo(i, y);
                }
            }
        }
        ctx.stroke();

        const gridIntervalSeconds = options.gridIntervalSeconds || 0;
        if (gridIntervalSeconds > 0) {
            ctx.strokeStyle = options.gridColor || 'rgba(148, 163, 184, 0.2)';
            ctx.lineWidth = 1;
            const firstTick = Math.ceil(startTime / gridIntervalSeconds) * gridIntervalSeconds;
            for (let t = firstTick; t <= startTime + timeRange; t += gridIntervalSeconds) {
                const x = Math.round((t - startTime) * pixelsPerSecond) + 0.5;
                ctx.beginPath();
                ctx.moveTo(x, 0);
                ctx.lineTo(x, height);
                ctx.stroke();
            }
        }

        // Draw center line
        ctx.strokeStyle = options.centerLineColor || 'rgba(148, 163, 184, 0.2)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(0, centerY);
        ctx.lineTo(width, centerY);
        ctx.stroke();

        if (options.showTimeLabels && labelIntervalSeconds > 0 && labelHeight > 0) {
            ctx.fillStyle = options.labelColor || 'rgba(226, 232, 240, 0.8)';
            ctx.font = options.labelFont || '10px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'bottom';
            const firstLabel = Math.ceil(startTime / labelIntervalSeconds) * labelIntervalSeconds;
            const labelY = height - 2;
            for (let t = firstLabel; t <= startTime + timeRange; t += labelIntervalSeconds) {
                const x = (t - startTime) * pixelsPerSecond;
                ctx.fillText(this.formatTime(t), x, labelY);
            }
        }
    }

    getWaveformGridInterval(timeRange) {
        if (timeRange <= 60) return 5;
        if (timeRange <= 180) return 10;
        if (timeRange <= 600) return 30;
        if (timeRange <= 1200) return 60;
        if (timeRange <= 3600) return 300;
        return 600;
    }

    getWaveformPixelsPerSecond(timeRange) {
        if (timeRange <= 60) return 20;
        if (timeRange <= 180) return 12;
        if (timeRange <= 600) return 6;
        if (timeRange <= 1800) return 4;
        if (timeRange <= 3600) return 3;
        return 2;
    }

    /**
     * Format time as MM:SS or HH:MM:SS
     */
    formatTime(seconds) {
        const sign = seconds < 0 ? '-' : '';
        const totalSeconds = Math.floor(Math.abs(seconds));
        const mins = Math.floor(totalSeconds / 60);
        const secs = totalSeconds % 60;
        if (mins >= 60) {
            const hours = Math.floor(mins / 60);
            const remMins = mins % 60;
            return `${sign}${hours.toString().padStart(2, '0')}:${remMins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${sign}${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    /**
     * Render compact waveforms in component selector dialog
     */
    renderSelectorWaveforms(item, componentOptions) {
        const container = document.getElementById('selector-waveforms');
        if (!container) return;

        try {
            const offsets = componentOptions.map(c => c.offset);
            const minOffset = Math.min(...offsets, 0);
            const maxOffset = Math.max(...offsets, 0);
            
            // Calculate time range to show all offsets clearly
            const padding = 2; // seconds of padding
            const timeRange = Math.max(Math.abs(maxOffset - minOffset) + padding * 2, 6);
            const zeroPosition = Math.abs(minOffset - padding) / timeRange; // Where 0 (master start) is
            
            const rowHeight = 28;
            const totalHeight = (componentOptions.length + 1) * (rowHeight + 8) + 40;

            // Generate time markers
            const timeMarkers = [];
            const step = timeRange > 30 ? 10 : timeRange > 10 ? 5 : 1;
            for (let t = Math.floor(minOffset - padding); t <= Math.ceil(maxOffset + padding); t += step) {
                const pos = ((t - (minOffset - padding)) / timeRange) * 100;
                if (pos >= 0 && pos <= 100) {
                    timeMarkers.push({ time: t, pos });
                }
            }

            container.innerHTML = `
                <div style="position: relative; height: ${totalHeight}px;">
                    <!-- Time axis -->
                    <div style="position: relative; height: 20px; margin-bottom: 8px; border-bottom: 1px solid rgba(148, 163, 184, 0.2);">
                        ${timeMarkers.map(m => `
                            <div style="position: absolute; left: ${m.pos}%; transform: translateX(-50%); font-size: 9px; color: #64748b;">
                                ${m.time >= 0 ? '+' : ''}${m.time}s
                            </div>
                        `).join('')}
                        <!-- Zero marker -->
                        <div style="position: absolute; left: ${zeroPosition * 100}%; bottom: 0; width: 2px; height: 100%; background: #22c55e; z-index: 5;"></div>
                    </div>

                    <!-- Master reference bar -->
                    <div style="display: flex; align-items: center; margin-bottom: 8px; height: ${rowHeight}px;">
                        <div style="width: 70px; font-size: 11px; font-weight: 700; color: #22c55e; flex-shrink: 0;">MASTER</div>
                        <div style="flex: 1; position: relative; height: 100%; background: rgba(15, 23, 42, 0.5); border-radius: 4px; overflow: hidden;">
                            <!-- Master bar starts at 0 -->
                            <div style="position: absolute; left: ${zeroPosition * 100}%; right: 5%; height: 100%; background: linear-gradient(90deg, rgba(34, 197, 94, 0.4), rgba(34, 197, 94, 0.1)); border-left: 3px solid #22c55e; border-radius: 0 4px 4px 0;"></div>
                            <div style="position: absolute; left: ${zeroPosition * 100}%; top: 50%; transform: translate(-50%, -50%); background: #22c55e; color: #0f172a; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: 700; white-space: nowrap; z-index: 10;">0:00:00</div>
                        </div>
                    </div>

                    <!-- Component bars -->
                    ${componentOptions.map((comp, index) => {
                        // Component offset relative to timeline
                        const compStartPos = ((comp.offset - (minOffset - padding)) / timeRange) * 100;
                        const isAligned = Math.abs(comp.offset) < 0.1;
                        const barColor = isAligned ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)';
                        const borderColor = isAligned ? '#22c55e' : '#ef4444';
                        
                        return `
                            <div style="display: flex; align-items: center; margin-bottom: 8px; height: ${rowHeight}px;">
                                <div style="width: 70px; font-size: 10px; font-weight: 700; background: linear-gradient(135deg, #ff6b42, #dc143c); color: white; padding: 4px 8px; border-radius: 4px; text-align: center; flex-shrink: 0;">${comp.label}</div>
                                <div style="flex: 1; position: relative; height: 100%; background: rgba(15, 23, 42, 0.5); border-radius: 4px; overflow: hidden;">
                                    <!-- Component bar starts at its offset position -->
                                    <div style="position: absolute; left: ${compStartPos}%; right: 5%; height: 100%; background: linear-gradient(90deg, ${barColor}, rgba(100, 116, 139, 0.1)); border-left: 3px solid ${borderColor}; border-radius: 0 4px 4px 0;"></div>
                                    <!-- Offset label -->
                                    <div style="position: absolute; left: ${compStartPos}%; top: 50%; transform: translate(-50%, -50%); background: ${borderColor}; color: white; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: 700; white-space: nowrap; z-index: 10;">${comp.timecode}</div>
                                    <!-- Connection line to master -->
                                    ${Math.abs(comp.offset) > 0.1 ? `
                                        <div style="position: absolute; left: ${Math.min(zeroPosition * 100, compStartPos)}%; width: ${Math.abs(compStartPos - zeroPosition * 100)}%; top: 50%; height: 2px; background: repeating-linear-gradient(90deg, #fbbf24, #fbbf24 4px, transparent 4px, transparent 8px); z-index: 5;"></div>
                                    ` : ''}
                                </div>
                            </div>
                        `;
                    }).join('')}
                    
                    <!-- Legend -->
                    <div style="display: flex; gap: 16px; justify-content: center; margin-top: 12px; font-size: 10px; color: #94a3b8;">
                        <span><span style="display: inline-block; width: 12px; height: 12px; background: #22c55e; border-radius: 2px; vertical-align: middle; margin-right: 4px;"></span>Aligned</span>
                        <span><span style="display: inline-block; width: 12px; height: 12px; background: #ef4444; border-radius: 2px; vertical-align: middle; margin-right: 4px;"></span>Needs Correction</span>
                        <span><span style="display: inline-block; width: 12px; height: 2px; background: repeating-linear-gradient(90deg, #fbbf24, #fbbf24 4px, transparent 4px, transparent 8px); vertical-align: middle; margin-right: 4px;"></span>Offset Gap</span>
                    </div>
                </div>
            `;
        } catch (error) {
            console.error('Failed to render selector waveforms:', error);
            container.innerHTML = `
                <div style="text-align: center; padding: 20px; color: #64748b;">
                    <i class="fas fa-times-circle"></i>
                    <span style="margin-left: 8px;">Unable to render offset visualization</span>
                </div>
            `;
        }
    }

    /**
     * Generate enhanced details view with new design
     */
    generateEnhancedDetailsView(item, result, offsetSeconds, confidence, methodDisplayName, qualityScore, offsetFrames, itemFps) {
        // Debug logging
        console.log('[generateEnhancedDetailsView] result object:', result);
        console.log('[generateEnhancedDetailsView] result has method_results?', !!result?.method_results);
        console.log('[generateEnhancedDetailsView] result has consensus_offset?', !!result?.consensus_offset);

        // Determine confidence badge
        const confidenceBadge = confidence > 0.8 ? 'high-confidence' : confidence > 0.5 ? 'medium-confidence' : 'low-confidence';
        const confidenceText = confidence > 0.8 ? 'High Confidence' : confidence > 0.5 ? 'Medium Confidence' : 'Low Confidence';

        // Determine severity for operator guidance
        const offsetAbs = Math.abs(offsetSeconds);
        const severity = offsetAbs > 0.5 ? 'high' : offsetAbs > 0.1 ? 'medium' : 'low';
        const severityText = offsetAbs > 0.5 ? 'Critical' : offsetAbs > 0.1 ? 'Moderate' : 'Minor';

        const timecode = this.formatTimecode(offsetSeconds, itemFps);

        return `
            <div class="details-content-v2">
                <!-- Quick Summary Header -->
                <div class="details-summary">
                    <div class="summary-card">
                        <div class="summary-card-header">
                            <i class="fas fa-clock"></i>
                            <span>Sync Offset</span>
                        </div>
                        <div class="summary-card-value">${timecode}</div>
                        <div class="summary-card-label">${offsetFrames}</div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-card-header">
                            <i class="fas fa-chart-bar"></i>
                            <span>Confidence</span>
                        </div>
                        <div class="summary-card-value">${(confidence * 100).toFixed(0)}%</div>
                        <div class="summary-card-label">
                            <span class="status-badge-v2 ${confidenceBadge}">${confidenceText}</span>
                        </div>
                    </div>
                    <div class="summary-card">
                        <div class="summary-card-header">
                            <i class="fas fa-film"></i>
                            <span>Frame Rate</span>
                        </div>
                        <div class="summary-card-value">${itemFps}</div>
                        <div class="summary-card-label">fps (detected)</div>
                    </div>
                </div>

                <!-- Operator Guidance Panel -->
                ${this.generateOperatorGuidance(item, offsetSeconds, confidence, severity, severityText)}

                <!-- Expandable Sections -->
                <div class="details-section" id="section-waveform-${item.id}">
                    <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <div class="section-title">
                            <i class="fas fa-waveform"></i>
                            <span>Waveform Visualization</span>
                        </div>
                        <i class="fas fa-chevron-down section-toggle"></i>
                    </div>
                    <div class="section-content">
                        <div class="enhanced-waveform-visualization" id="enhanced-waveform-${item.id}">
                            <div class="waveform-loading">
                                <i class="fas fa-spinner fa-spin"></i>
                                <span>Generating waveform visualization...</span>
                            </div>
                        </div>
                    </div>
                </div>

                ${this.generatePerChannelSection(item, result)}

                ${this.generateMethodResultsSection(item, result)}

                ${this.generateMetadataSection(item, result, methodDisplayName, qualityScore)}

                <!-- Repair Controls Section -->
                <div class="details-section" id="section-repair-${item.id}">
                    <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <div class="section-title">
                            <i class="fas fa-wrench"></i>
                            <span>Repair Options</span>
                        </div>
                        <i class="fas fa-chevron-down section-toggle"></i>
                    </div>
                    <div class="section-content">
                        <div class="batch-repair-controls">
                            <div class="repair-buttons">
                                <label class="keepdur" style="margin-right:12px;display:flex;align-items:center;gap:6px;">
                                    <input type="checkbox" id="keep-duration-${item.id}" checked>
                                    <span>Keep duration</span>
                                </label>
                                <button class="repair-btn auto" onclick="app.repairBatchItem('${item.id}', 'auto')">Auto Repair</button>
                                <button class="repair-btn manual" onclick="app.repairBatchItem('${item.id}', 'manual')">Manual Repair</button>
                            </div>
                            <div class="perch-repair">
                                <h4><i class="fas fa-stream"></i> Per-Channel Repair</h4>
                                <div class="perch-row">
                                    <label>Output Path</label>
                                    <input type="text" id="perch-out-${item.id}" placeholder="/absolute/output/path.mov" value="/mnt/data/amcmurray/Sync_dub/Sync_dub_final/repaired_sync_files/${item.dub.name.replace(/\.[^.]+$/, '')}_perch.mov">
                                    <label class="keepdur"><input type="checkbox" id="perch-keep-${item.id}" checked> Keep duration</label>
                                    <button class="repair-btn" id="perch-btn-${item.id}"><i class="fas fa-wrench"></i> Run Per-Channel Repair</button>
                                </div>
                                <div class="hint">Uses per-channel offsets reported above. Video is copied; audio re-encoded PCM 48k.</div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Raw Data Section -->
                <div class="details-section" id="section-raw-${item.id}">
                    <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                        <div class="section-title">
                            <i class="fas fa-code"></i>
                            <span>Raw Analysis Data</span>
                        </div>
                        <i class="fas fa-chevron-down section-toggle"></i>
                    </div>
                    <div class="section-content">
                        <div class="analysis-json-data">
                            <div class="json-container">
                                <pre class="json-display">${result ? JSON.stringify(result, null, 2) : 'No raw analysis data available'}</pre>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Generate operator guidance panel
     */
    generateOperatorGuidance(item, offsetSeconds, confidence, severity, severityText) {
        const offsetAbs = Math.abs(offsetSeconds);

        let recommendation = '';
        let actions = '';

        if (offsetAbs < 0.05 && confidence > 0.8) {
            recommendation = 'Files appear to be in sync. No repair needed.';
            actions = '<button class="guidance-btn">Export Report</button>';
        } else if (offsetAbs < 0.5 && confidence > 0.7) {
            recommendation = 'Minor sync offset detected. Consider applying automatic repair for optimal synchronization.';
            actions = `
                <button class="guidance-btn primary" onclick="app.repairBatchItem('${item.id}', 'auto')">
                    <i class="fas fa-magic"></i> Auto-Repair
                </button>
                <button class="guidance-btn" onclick="app.handleActionButton('qc', '${item.id}', null)">
                    <i class="fas fa-microscope"></i> Review in QC
                </button>
            `;
        } else if (confidence < 0.5) {
            recommendation = 'Low confidence detection. Manual review recommended before applying repairs. Check audio quality and try different analysis methods.';
            actions = `
                <button class="guidance-btn primary" onclick="app.handleActionButton('qc', '${item.id}', null)">
                    <i class="fas fa-microscope"></i> Manual Review Required
                </button>
            `;
        } else {
            recommendation = 'Significant sync offset detected. Manual review in QC interface is recommended to verify detection accuracy before repair.';
            actions = `
                <button class="guidance-btn primary" onclick="app.handleActionButton('qc', '${item.id}', null)">
                    <i class="fas fa-microscope"></i> Review in QC
                </button>
                <button class="guidance-btn" onclick="app.handleActionButton('repair', '${item.id}', null)">
                    <i class="fas fa-wrench"></i> Open Repair
                </button>
            `;
        }

        return `
            <div class="operator-guidance">
                <div class="guidance-header">
                    <i class="fas fa-lightbulb"></i>
                    <h3>Recommended Action</h3>
                    <span class="priority-badge ${severity}">${severityText} Priority</span>
                </div>
                <div class="guidance-content">
                    ${recommendation}
                </div>
                <div class="guidance-actions">
                    ${actions}
                </div>
            </div>
        `;
    }

    /**
     * Generate per-channel analysis section
     */
    generatePerChannelSection(item, result) {
        const perChannelResults = result?.per_channel_results || {};
        const hasPerChannel = Object.keys(perChannelResults).length > 0;

        if (!hasPerChannel) return '';

        const channelCards = Object.entries(perChannelResults).map(([channel, data]) => {
            const offset = data?.offset_seconds || 0;
            const conf = data?.confidence || 0;
            const fps = item.frameRate || this.detectedFrameRate;
            const timecode = this.formatTimecode(offset, fps);

            return `
                <div class="channel-card">
                    <div class="channel-name">${channel}</div>
                    <div class="channel-offset">${timecode}</div>
                    <div class="channel-confidence">Confidence: ${(conf * 100).toFixed(0)}%</div>
                </div>
            `;
        }).join('');

        return `
            <div class="details-section" id="section-channels-${item.id}">
                <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <div class="section-title">
                        <i class="fas fa-stream"></i>
                        <span>Per-Channel Analysis</span>
                    </div>
                    <i class="fas fa-chevron-down section-toggle"></i>
                </div>
                <div class="section-content">
                    <div class="channel-grid">
                        ${channelCards}
                    </div>
                </div>
            </div>
        `;
    }

    /**
     * Generate method results section
     */
    generateMethodResultsSection(item, result) {
        const methodResults = result?.method_results || [];
        if (methodResults.length === 0) return '';

        const fps = item.frameRate || this.detectedFrameRate;
        const rows = methodResults.map(method => {
            const offset = method?.offset_seconds || 0;
            const conf = method?.confidence || 0;
            const name = method?.method || 'Unknown';
            const timecode = this.formatTimecode(offset, fps);

            return `
                <tr>
                    <td class="method-name-cell">${name}</td>
                    <td class="method-offset-cell">${timecode}</td>
                    <td class="method-confidence-cell">${(conf * 100).toFixed(1)}%</td>
                </tr>
            `;
        }).join('');

        return `
            <div class="details-section" id="section-methods-${item.id}">
                <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <div class="section-title">
                        <i class="fas fa-microscope"></i>
                        <span>Detection Methods</span>
                    </div>
                    <i class="fas fa-chevron-down section-toggle"></i>
                </div>
                <div class="section-content">
                    <table class="methods-table">
                        <thead>
                            <tr>
                                <th>Method</th>
                                <th>Offset</th>
                                <th>Confidence</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    }

    /**
     * Generate metadata section
     */
    generateMetadataSection(item, result, methodDisplayName, qualityScore) {
        return `
            <div class="details-section" id="section-metadata-${item.id}">
                <div class="section-header" onclick="this.parentElement.classList.toggle('expanded')">
                    <div class="section-title">
                        <i class="fas fa-info-circle"></i>
                        <span>Analysis Metadata</span>
                    </div>
                    <i class="fas fa-chevron-down section-toggle"></i>
                </div>
                <div class="section-content">
                    <div class="metadata-grid">
                        <div class="metadata-item">
                            <div class="metadata-label">Detection Method</div>
                            <div class="metadata-value">${methodDisplayName}</div>
                        </div>
                        <div class="metadata-item">
                            <div class="metadata-label">Audio Quality</div>
                            <div class="metadata-value">${(qualityScore * 100).toFixed(0)}%</div>
                        </div>
                        <div class="metadata-item">
                            <div class="metadata-label">Master File</div>
                            <div class="metadata-value">${item.master.name}</div>
                        </div>
                        <div class="metadata-item">
                            <div class="metadata-label">Dub File</div>
                            <div class="metadata-value">${item.dub.name}</div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }
    
    closeBatchDetails() {
        const detailsDiv = this.elements.batchDetails;
        
        // Reset expand button state
        if (detailsDiv.dataset.currentItem) {
            const expandBtn = document.querySelector(`tr[data-item-id="${detailsDiv.dataset.currentItem}"] .expand-btn`);
            if (expandBtn) {
                expandBtn.classList.remove('expanded');
            }
        }
        // Exit fullscreen if active
        try {
            if (detailsDiv.classList.contains('fullscreen')) {
                const fsBtn = document.getElementById('toggle-fullscreen-btn');
                if (fsBtn) { try { fsBtn.click(); } catch {} }
            }
        } catch {}

        detailsDiv.style.display = 'none';
        detailsDiv.dataset.currentItem = '';
        this.updateBatchDetailsSplit(false);
        
        // Reset Quadrant 2 batch details view
        const q2Placeholder = document.getElementById('batch-details-placeholder');
        const q2Content = document.getElementById('batch-details-content');
        if (q2Placeholder && q2Content) {
            q2Placeholder.style.display = 'flex';
            q2Content.style.display = 'none';
            q2Content.innerHTML = '';
        }
        
        this.addLog('info', 'Analysis details closed');
    }

    updateBatchDetailsSplit(show) {
        const splitter = this.elements.batchSplitter;
        const details = this.elements.batchDetails;
        if (!splitter || !details) return;

        splitter.style.display = show ? 'flex' : 'none';
        if (!show) return;

        try {
            const saved = Number(localStorage.getItem('batch-details-height'));
            if (Number.isFinite(saved) && saved > 0) {
                details.style.height = `${saved}px`;
                details.style.maxHeight = 'none';
            } else {
                details.style.height = '';
                details.style.maxHeight = '';
            }
        } catch {}
    }

    toggleBatchFullscreen(force) {
        const body = document.body;
        const shouldEnable = typeof force === 'boolean'
            ? force
            : !body.classList.contains('batch-table-fullscreen');

        body.classList.toggle('batch-table-fullscreen', shouldEnable);
        body.classList.toggle('no-scroll', shouldEnable);

        const btn = this.elements.toggleBatchFullscreen;
        if (btn) {
            btn.classList.toggle('active', shouldEnable);
            btn.setAttribute('aria-pressed', shouldEnable ? 'true' : 'false');
            btn.innerHTML = shouldEnable
                ? '<i class="fas fa-compress"></i> Exit Full Screen'
                : '<i class="fas fa-expand"></i> Full Screen';
        }
    }
    
    removeBatchItem(itemId) {
        if (this.batchProcessing) {
            this.addLog('warning', 'Cannot remove items while processing');
            return;
        }
        
        const index = this.batchQueue.findIndex(item => item.id.toString() === itemId);
        if (index !== -1) {
            const item = this.batchQueue[index];
            this.batchQueue.splice(index, 1);
            this.updateBatchTable();
            this.updateBatchSummary();
            this.closeBatchDetails();
            this.addLog('info', `Removed from batch: ${item.master.name}`);
            this.persistBatchQueue().catch(() => {});
        }
    }

    loadBatchQueue() {
        // Load from server-side storage (Redis) for cross-browser sync
        this.loadBatchQueueFromServer();
    }
    
    /**
     * Load batch queue from server (Redis) - ensures all browsers see same state
     */
    async loadBatchQueueFromServer() {
        try {
            const response = await fetch(`${this.FASTAPI_BASE}/batch-queue`);
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    // Server is authoritative - use its data even if empty
                    this.batchQueue = data.items || [];
                    this.batchQueue.forEach(item => {
                        if (item.type === 'componentized' && !item.offsetMode) {
                            item.offsetMode = this.componentizedOffsetMode || 'mixdown';
                        }
                    });
                    this.updateBatchTable();
                    this.updateBatchSummary();
                    
                    if (this.batchQueue.length > 0) {
                        console.log(`Loaded ${this.batchQueue.length} batch item(s) from server`);
                        this.addLog('info', `Synced ${this.batchQueue.length} job(s) from server`);
                        // Auto-refresh stale "processing" jobs
                        this.refreshStaleJobs();
                    } else {
                        console.log('Server returned empty batch queue');
                        // Also clear localStorage to stay in sync
                        try { localStorage.removeItem('sync-analyzer-batch-queue'); } catch {}
                    }
                    return;
                }
            }
            // Fallback to localStorage only if server request FAILED
            this.loadBatchQueueFromLocalStorage();
        } catch (e) {
            console.warn('Failed to load from server, falling back to localStorage:', e);
            this.loadBatchQueueFromLocalStorage();
        }
    }
    
    /**
     * Fallback: Load from localStorage
     */
    loadBatchQueueFromLocalStorage() {
        try {
            const saved = localStorage.getItem('sync-analyzer-batch-queue');
            if (saved) {
                const data = JSON.parse(saved);
                const items = data?.items || [];
                if (items.length > 0) {
                    this.batchQueue = items;
                    this.batchQueue.forEach(item => {
                        if (item.type === 'componentized' && !item.offsetMode) {
                            item.offsetMode = this.componentizedOffsetMode || 'mixdown';
                        }
                    });
                    this.updateBatchTable();
                    this.updateBatchSummary();
                    console.log(`Restored ${items.length} batch item(s) from localStorage (fallback)`);
                    
                    // Try to sync localStorage data to server
                    this.persistBatchQueue();
                    this.refreshStaleJobs();
                    return;
                }
            }
        } catch (e) {
            console.warn('Failed to load from localStorage:', e);
        }
    }
    
    /**
     * Generate unique client ID
     */
    generateClientId() {
        return 'client_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    /**
     * Start periodic sync for cross-browser updates
     */
    startPeriodicSync() {
        // Sync every 10 seconds when not actively processing
        this.syncInterval = setInterval(() => {
            if (!this.batchProcessing) {
                this.syncFromServer();
                this.pollForNewApiJobs();
            }
        }, 10000);
        
        // Also sync when window gains focus
        window.addEventListener('focus', () => {
            if (!this.batchProcessing) {
                this.syncFromServer();
                this.pollForNewApiJobs();
            }
        });
        
        // Initial poll for API jobs
        setTimeout(() => this.pollForNewApiJobs(), 2000);
    }
    
    /**
     * Poll for new jobs submitted via API (not through UI)
     */
    async pollForNewApiJobs() {
        try {
            const response = await fetch(`${this.FASTAPI_BASE}/job-registry?since_hours=24`);
            if (!response.ok) return;
            
            const data = await response.json();
            if (!data.success || !data.jobs) return;
            
            // Check for jobs not in our batch queue
            const existingJobIds = new Set(
                this.batchQueue
                    .filter(item => item.analysisId)
                    .map(item => item.analysisId)
            );
            
            let addedCount = 0;
            
            for (const job of data.jobs) {
                // Skip if already in queue
                if (existingJobIds.has(job.job_id)) {
                    // Update status if changed
                    const existing = this.batchQueue.find(item => item.analysisId === job.job_id);
                    if (existing && job.status !== existing.status) {
                        existing.status = job.status === 'completed' ? 'completed' : 
                                         job.status === 'failed' ? 'failed' : existing.status;
                        existing.progress = job.progress || existing.progress;
                        if (job.result) {
                            existing.result = job.result;
                            existing.componentResults = job.result.component_results || [];
                        }
                        if (job.error) existing.error = job.error;
                        this.updateBatchTableRow(existing);
                    }
                    continue;
                }
                
                // Create new batch item from API job
                const newItem = {
                    id: Date.now() + Math.random(),
                    type: job.type || 'componentized',
                    status: job.status === 'completed' ? 'completed' : 
                           job.status === 'failed' ? 'failed' : 
                           job.status === 'processing' ? 'processing' : 'queued',
                    progress: job.progress || 0,
                    master: {
                        path: job.master_file,
                        name: job.master_name || job.master_file.split('/').pop()
                    },
                    components: (job.components || []).map((c, i) => ({
                        path: c.path || c,
                        label: c.label || `a${i}`,
                        name: c.name || (c.path || c).split('/').pop()
                    })),
                    componentResults: job.result?.component_results || [],
                    result: job.result,
                    error: job.error,
                    analysisId: job.job_id,
                    offsetMode: job.offset_mode || 'channel_aware',
                    createdAt: job.created_at,
                    source: 'api'  // Mark as API-submitted
                };
                
                this.batchQueue.push(newItem);
                addedCount++;
            }
            
            if (addedCount > 0) {
                this.updateBatchTable();
                this.updateBatchSummary();
                await this.persistBatchQueue();
                this.addLog('info', `📡 Discovered ${addedCount} job(s) from API`);
            }
        } catch (e) {
            // Silent fail - polling is optional
            console.debug('API job poll failed:', e);
        }
    }
    
    /**
     * Sync batch queue from server (pull updates from other browsers)
     */
    async syncFromServer() {
        try {
            const response = await fetch(`${this.FASTAPI_BASE}/batch-queue`);
            if (!response.ok) return;
            
            const data = await response.json();
            if (!data.success || !data.items) return;
            
            // Check if server has newer data
            const serverItems = data.items;
            const localItemIds = new Set(this.batchQueue.map(i => i.id));
            const serverItemIds = new Set(serverItems.map(i => i.id));
            
            // Check for changes
            let hasChanges = false;
            
            // Check for status updates on existing items
            for (const serverItem of serverItems) {
                const localItem = this.batchQueue.find(i => i.id === serverItem.id);
                if (localItem) {
                    // Update status if server has newer status
                    if (serverItem.status !== localItem.status || 
                        serverItem.progress !== localItem.progress) {
                        Object.assign(localItem, serverItem);
                        hasChanges = true;
                    }
                } else if (!localItemIds.has(serverItem.id)) {
                    // New item from another browser
                    this.batchQueue.push(serverItem);
                    hasChanges = true;
                }
            }
            
            // Check for items deleted in other browsers
            for (const localItem of [...this.batchQueue]) {
                if (!serverItemIds.has(localItem.id)) {
                    this.batchQueue = this.batchQueue.filter(i => i.id !== localItem.id);
                    hasChanges = true;
                }
            }
            
            if (hasChanges) {
                console.log('Synced batch queue from server');
                this.updateBatchTable();
                this.updateBatchSummary();
            }
        } catch (e) {
            // Silent fail - sync is optional
        }
    }
    
    /**
     * Refresh status of jobs that are stuck in "processing" state
     */
    async refreshStaleJobs() {
        const processingJobs = this.batchQueue.filter(item => 
            item.status === 'processing' && item.analysisId
        );
        
        if (processingJobs.length === 0) return;
        
        this.addLog('info', `Checking status of ${processingJobs.length} processing job(s)...`);
        
        for (const item of processingJobs) {
            try {
                const response = await fetch(`${this.FASTAPI_BASE}/analysis/${item.analysisId}`);
                if (!response.ok) {
                    // Job not found - mark as failed/orphaned
                    item.status = 'failed';
                    item.error = 'Job not found on server (may have been cleared)';
                    this.updateBatchTableRow(item);
                    continue;
                }
                
                const jobData = await response.json();
                
                if (jobData.status === 'completed' || jobData.result) {
                    // Job completed - update status and results
                    item.status = 'completed';
                    item.progress = 100;
                    
                    if (jobData.result) {
                        const result = jobData.result;
                        if (item.type === 'componentized' && result.component_results) {
                            item.componentResults = result.component_results.map(cr => ({
                                component: cr.component_label || cr.component,
                                offset_seconds: cr.offset_seconds,
                                confidence: cr.confidence,
                                timecode: cr.timecode,
                                findings: cr.findings || []
                            }));
                        } else {
                            item.result = {
                                offset_seconds: result.offset_seconds,
                                confidence: result.confidence,
                                method: result.method,
                                timecode: result.timecode
                            };
                        }
                    }
                    
                    this.addLog('success', `Job "${item.master?.name}" completed (refreshed)`);
                } else if (jobData.status === 'failed') {
                    item.status = 'failed';
                    let errorMsg = jobData.error || 'Job failed';
                    if (typeof errorMsg === 'object') {
                        errorMsg = errorMsg.message || errorMsg.detail || JSON.stringify(errorMsg);
                    }
                    item.error = errorMsg;
                    this.addLog('error', `Job "${item.master?.name}" failed: ${item.error}`);
                }
                // If still processing, leave it - it might actually be running
                
                this.updateBatchTableRow(item);
            } catch (err) {
                console.warn(`Failed to refresh job ${item.analysisId}:`, err);
            }
        }
        
        await this.persistBatchQueue();
        this.updateBatchSummary();
    }

    async initBatchQueue() {
        // Batch queue is already loaded by loadBatchQueue() -> loadBatchQueueFromServer()
        // This function just reconnects to any active/processing jobs
        console.log(`initBatchQueue: ${this.batchQueue.length} items in queue`);
        
        // Check for active jobs to reconnect to
        this.reconnectToActiveJobs();
    }

    /**
     * Check for active/orphaned jobs and reconnect to them.
     * This enables seamless reconnection after page refresh.
     * 
     * With Celery/Redis, jobs persist across server restarts.
     * We check both:
     * 1. Server's active jobs endpoint (Celery tasks)
     * 2. Batch items with analysisId/jobId that are still 'processing'
     */
    async reconnectToActiveJobs() {
        try {
            console.log('Checking for jobs to reconnect to...');
            
            // First, check batch items that have job IDs and are marked as processing
            const processingItems = this.batchQueue.filter(item => 
                (item.analysisId || item.jobId) && 
                (item.status === 'processing' || item.status === 'queued')
            );
            
            if (processingItems.length > 0) {
                this.addLog('info', `Found ${processingItems.length} job(s) to check status...`);
                
                for (const item of processingItems) {
                    const jobId = item.analysisId || item.jobId;
                    await this.checkAndReconnectJob(jobId, item);
                }
            }
            
            // Also fetch active jobs from server (may find jobs we don't have locally)
            try {
                const resp = await fetch(`${this.FASTAPI_BASE}/jobs/active`);
                if (resp.ok) {
                    const data = await resp.json();
                    const activeJobs = data.jobs || [];
                    
                    for (const job of activeJobs) {
                        // Check if we already have this job in batch queue
                        const existing = this.batchQueue.find(item => 
                            item.analysisId === job.job_id || item.jobId === job.job_id
                        );
                        if (!existing) {
                            await this.reconnectToJob(job);
                        }
                    }
                }
            } catch (e) {
                console.log('Could not fetch active jobs from server:', e.message);
            }
            
            // Check for orphaned jobs
            await this.checkOrphanedJobs();
            
        } catch (e) {
            console.warn('Failed to check for active jobs:', e);
        }
    }
    
    /**
     * Check a job's status and update the batch item accordingly.
     * If still processing, start polling. If completed, update results.
     */
    async checkAndReconnectJob(jobId, batchItem) {
        try {
            const resp = await fetch(`${this.FASTAPI_BASE}/jobs/${jobId}`);
            if (!resp.ok) {
                console.log(`Job ${jobId} not found on server`);
                return;
            }
            
            const jobData = await resp.json();
            
            if (jobData.status === 'completed') {
                // Job finished while we were away - update with results
                this.addLog('success', `Job ${jobId} completed - updating results`);
                batchItem.status = 'completed';
                batchItem.progress = 100;
                
                if (jobData.result) {
                    this.applyJobResultToBatchItem(batchItem, jobData.result);
                }
                
                this.updateBatchTableRow(batchItem);
                this.updateBatchSummary();
                this.persistBatchQueue().catch(() => {});
                
            } else if (jobData.status === 'failed') {
                // Job failed
                batchItem.status = 'failed';
                batchItem.error = jobData.error || 'Job failed';
                this.updateBatchTableRow(batchItem);
                this.updateBatchSummary();
                this.addLog('error', `Job ${jobId} failed: ${batchItem.error}`);
                
            } else if (jobData.status === 'processing' || jobData.status === 'queued') {
                // Job still running - start polling
                this.addLog('info', `Reconnecting to running job: ${jobId}`);
                batchItem.status = 'processing';
                batchItem.progress = jobData.progress || batchItem.progress || 0;
                this.updateBatchTableRow(batchItem);
                
                // Start polling for this job
                this.pollJobUntilComplete(jobId, batchItem);
            }
            
        } catch (e) {
            console.warn(`Error checking job ${jobId}:`, e);
        }
    }
    
    /**
     * Apply job results to a batch item (for completed jobs found after reconnection)
     */
    applyJobResultToBatchItem(item, result) {
        if (item.type === 'componentized') {
            const componentResults = Array.isArray(result.component_results) ? result.component_results : [];
            item.componentResults = componentResults.map((res, idx) => ({
                component: res.component || item.components[idx]?.label || `C${idx + 1}`,
                componentName: res.componentName || item.components[idx]?.name || `component_${idx + 1}`,
                offset_seconds: res.offset_seconds || 0,
                confidence: res.confidence || 0,
                frameRate: item.frameRate,
                quality_score: res.quality_score || 0,
                method_results: res.method_results || [],
                status: res.status || 'completed'
            }));
            
            item.result = {
                offset_seconds: result.mixdown_offset_seconds || result.overall_offset?.offset_seconds || 0,
                confidence: result.mixdown_confidence || result.overall_offset?.confidence || 0,
                method_used: result.method_used || result.offset_mode || 'componentized',
                componentResults: item.componentResults
            };
        } else {
            item.result = result;
        }
    }
    
    /**
     * Poll a job until it completes (used for reconnection)
     */
    async pollJobUntilComplete(jobId, batchItem) {
        const maxPollTime = 10 * 60 * 1000; // 10 minutes
        const pollInterval = 2000; // 2 seconds
        const startTime = Date.now();
        
        const poll = async () => {
            if (Date.now() - startTime > maxPollTime) {
                batchItem.status = 'failed';
                batchItem.error = 'Polling timed out';
                this.updateBatchTableRow(batchItem);
                this.addLog('error', `Job ${jobId} timed out`);
                return;
            }
            
            try {
                const resp = await fetch(`${this.FASTAPI_BASE}/jobs/${jobId}`);
                const jobData = await resp.json();
                
                // Update progress
                if (jobData.progress > 0) {
                    batchItem.progress = jobData.progress;
                    batchItem.progressMessage = jobData.status_message;
                    this.updateBatchTableRow(batchItem);
                }
                
                if (jobData.status === 'completed') {
                    batchItem.status = 'completed';
                    batchItem.progress = 100;
                    if (jobData.result) {
                        this.applyJobResultToBatchItem(batchItem, jobData.result);
                    }
                    this.updateBatchTableRow(batchItem);
                    this.updateBatchSummary();
                    this.persistBatchQueue().catch(() => {});
                    this.addLog('success', `Job ${jobId} completed`);
                    return;
                    
                } else if (jobData.status === 'failed') {
                    batchItem.status = 'failed';
                    batchItem.error = jobData.error || 'Job failed';
                    this.updateBatchTableRow(batchItem);
                    this.updateBatchSummary();
                    this.addLog('error', `Job ${jobId} failed: ${batchItem.error}`);
                    return;
                    
                } else {
                    // Still processing, poll again
                    setTimeout(poll, pollInterval);
                }
                
            } catch (e) {
                console.warn(`Poll error for ${jobId}:`, e);
                setTimeout(poll, pollInterval * 2); // Back off
            }
        };
        
        poll();
    }

    /**
     * Reconnect to a single active job via SSE.
     */
    async reconnectToJob(job) {
        const jobId = job.job_id;
        const status = job.status;
        
        // Find matching batch item by analysisId
        let batchItem = this.batchQueue.find(item => item.analysisId === jobId);
        
        // If no match, try to reconstruct from request params
        if (!batchItem && job.request_params) {
            const params = job.request_params;
            batchItem = this.batchQueue.find(item => 
                item.master?.path === params.master_file && 
                item.dub?.path === params.dub_file
            );
        }
        
        if (!batchItem) {
            // Create a placeholder batch item for this orphan job
            if (job.request_params) {
                const params = job.request_params;
                batchItem = {
                    id: Date.now(),
                    master: { path: params.master_file, name: params.master_file.split('/').pop() },
                    dub: { path: params.dub_file, name: params.dub_file.split('/').pop() },
                    status: 'processing',
                    progress: job.progress || 0,
                    analysisId: jobId,
                    type: 'standard',
                    addedAt: job.created_at
                };
                this.batchQueue.push(batchItem);
                this.updateBatchTable();
                this.addLog('info', `Restored job ${jobId} to batch queue`);
            } else {
                this.addLog('warn', `Cannot reconnect to job ${jobId}: no request params`);
                return;
            }
        }
        
        // Update batch item status
        batchItem.status = 'processing';
        batchItem.progress = job.progress || batchItem.progress || 0;
        batchItem.analysisId = jobId;
        this.updateBatchTableRow(batchItem);
        
        // Only reconnect SSE for processing jobs
        if (status !== 'processing') {
            return;
        }
        
        this.addLog('info', `Reconnecting to job: ${jobId}`);
        this.analysisInProgress = true;
        this.updateAnalyzeButton();
        this.updateStatus('analyzing', `Reconnected to analysis: ${batchItem.dub?.name || jobId}`);
        
        // Establish SSE connection
        this.establishSSEConnection(jobId, batchItem);
    }

    /**
     * Establish SSE connection for job progress updates.
     */
    establishSSEConnection(analysisId, batchItem) {
        const streamUrl = `${this.FASTAPI_BASE}/analysis/${analysisId}/progress/stream`;
        let es = null;
        
        try {
            es = new EventSource(streamUrl);
        } catch (e) {
            console.warn('EventSource not supported, falling back to polling');
            this.pollJobProgress(analysisId, batchItem);
            return;
        }
        
        let closed = false;
        const closeES = () => {
            try { es && es.close(); } catch {}
            es = null;
            closed = true;
        };
        
        es.onmessage = (evt) => {
            try {
                const s = JSON.parse(evt.data || '{}');
                
                // Update progress
                if (typeof s.progress === 'number') {
                    batchItem.progress = Math.max(batchItem.progress, Math.floor(s.progress));
                    this.updateBatchTableRow(batchItem);
                }
                
                // Show status messages
                if (s.status_message && s.status_message !== batchItem._lastStatusMessage) {
                    const progressPercent = typeof s.progress === 'number' ? Math.floor(s.progress) : 0;
                    this.addProgressLog(s.status_message, progressPercent);
                    batchItem._lastStatusMessage = s.status_message;
                }
                
                // Handle completion
                if (s.status === 'completed') {
                    batchItem.progress = 100;
                    batchItem.status = 'completed';
                    this.updateBatchTableRow(batchItem);
                    
                    if (batchItem._lastStatusMessage) {
                        this.addProgressLog(batchItem._lastStatusMessage, 100);
                    }
                    
                    closeES();
                    this.handleJobCompletion(analysisId, batchItem, s.result);
                    return;
                }
                
                // Handle failure
                if (s.status === 'failed' || s.status === 'cancelled') {
                    closeES();
                    this.handleJobFailure(batchItem, s.message || `Job ${s.status}`);
                }
            } catch (parseErr) {
                console.warn('SSE parse error:', parseErr);
            }
        };
        
        es.addEventListener('end', () => {
            if (!closed) {
                closeES();
                // Fetch final state
                this.fetchJobResult(analysisId, batchItem);
            }
        });
        
        es.onerror = () => {
            // SSE connection lost - fall back to polling
            closeES();
            this.pollJobProgress(analysisId, batchItem);
        };
    }

    /**
     * Poll job progress when SSE is not available.
     */
    async pollJobProgress(analysisId, batchItem) {
        let retryDelay = 1000;
        const maxDelay = 10000;
        
        while (true) {
            try {
                const r = await fetch(`${this.FASTAPI_BASE}/analysis/${analysisId}`);
                if (!r.ok) {
                    throw new Error(`Poll failed: HTTP ${r.status}`);
                }
                
                const s = await r.json();
                
                if (typeof s.progress === 'number') {
                    batchItem.progress = Math.max(batchItem.progress, Math.floor(s.progress));
                    this.updateBatchTableRow(batchItem);
                }
                
                if (s.status === 'completed') {
                    this.handleJobCompletion(analysisId, batchItem, s.result);
                    return;
                }
                
                if (s.status === 'failed' || s.status === 'cancelled') {
                    this.handleJobFailure(batchItem, s.message || `Job ${s.status}`);
                    return;
                }
                
                await new Promise(res => setTimeout(res, retryDelay));
                retryDelay = Math.min(maxDelay, Math.floor(retryDelay * 1.6));
                
            } catch (err) {
                console.error('Polling error:', err);
                this.handleJobFailure(batchItem, err.message);
                return;
            }
        }
    }

    /**
     * Fetch final job result from server.
     */
    async fetchJobResult(analysisId, batchItem) {
        try {
            const r = await fetch(`${this.FASTAPI_BASE}/analysis/${analysisId}`);
            if (!r.ok) {
                throw new Error(`Fetch failed: HTTP ${r.status}`);
            }
            
            const s = await r.json();
            
            if (s.status === 'completed') {
                this.handleJobCompletion(analysisId, batchItem, s.result);
            } else if (s.status === 'failed') {
                this.handleJobFailure(batchItem, s.message || 'Job failed');
            } else {
                // Still in progress, start polling
                this.pollJobProgress(analysisId, batchItem);
            }
        } catch (err) {
            this.handleJobFailure(batchItem, err.message);
        }
    }

    /**
     * Handle successful job completion.
     */
    async handleJobCompletion(analysisId, batchItem, result) {
        const res = result || {};
        const co = res.consensus_offset || {};
        
        const adapted = {
            offset_seconds: co.offset_seconds ?? 0,
            confidence: co.confidence ?? 0,
            quality_score: res.overall_confidence ?? 0,
            method_used: 'Consensus',
            analysis_id: res.analysis_id || analysisId,
            created_at: res.completed_at || res.created_at || null,
            analysis_methods: Array.isArray(res.method_results) ? res.method_results.map(m => m.method) : []
        };
        
        batchItem.status = 'completed';
        batchItem.progress = 100;
        batchItem.result = adapted;
        this.updateBatchTableRow(batchItem);
        
        this.addLog('success', `Analysis completed: ${this.formatOffsetDisplay(adapted.offset_seconds, true, batchItem.frameRate || this.detectedFrameRate)}`);
        
        this.analysisInProgress = false;
        this.updateAnalyzeButton();
        this.updateStatus('ready', 'Ready');
        this.updateBatchSummary();
        
        await this.persistBatchQueue().catch(() => {});
        
        // Dispatch completion event
        document.dispatchEvent(new CustomEvent('analysisComplete', {
            detail: { analysisId, result: adapted, batchItem }
        }));
    }

    /**
     * Handle job failure.
     */
    handleJobFailure(batchItem, errorMessage) {
        batchItem.status = 'failed';
        batchItem.error = errorMessage;
        this.updateBatchTableRow(batchItem);
        
        this.addLog('error', `Analysis failed: ${errorMessage}`);
        
        this.analysisInProgress = false;
        this.updateAnalyzeButton();
        this.updateStatus('error', 'Analysis failed');
        this.updateBatchSummary();
        
        // Dispatch error event
        document.dispatchEvent(new CustomEvent('analysisError', {
            detail: { error: errorMessage, batchItem }
        }));
    }

    /**
     * Check for orphaned jobs and notify user.
     */
    async checkOrphanedJobs() {
        try {
            const resp = await fetch(`${this.FASTAPI_BASE}/jobs/orphaned`);
            if (!resp.ok) return;
            
            const data = await resp.json();
            const orphanedJobs = data.jobs || [];
            
            if (orphanedJobs.length > 0) {
                this.addLog('warn', `Found ${orphanedJobs.length} orphaned job(s) from server restart. Use the retry button to restart.`);
                
                // Update batch items with orphaned status
                for (const job of orphanedJobs) {
                    let batchItem = this.batchQueue.find(item => item.analysisId === job.job_id);
                    if (batchItem) {
                        batchItem.status = 'orphaned';
                        batchItem.error = 'Server restarted during processing';
                        this.updateBatchTableRow(batchItem);
                    }
                }
                this.updateBatchSummary();
            }
        } catch (e) {
            console.warn('Failed to check for orphaned jobs:', e);
        }
    }

    /**
     * Retry a failed or orphaned job.
     */
    async retryJob(itemId) {
        const item = this.batchQueue.find(i => i.id.toString() === itemId);
        if (!item) {
            this.addLog('error', 'Cannot retry: item not found');
            return;
        }

        // For batch items, reset status and process directly
        // The FastAPI job retry endpoint is only for single-file analysis jobs
        try {
            this.addLog('info', `Retrying ${item.type === 'componentized' ? 'componentized' : 'batch'} item: ${item.master.name}`);

            // Reset item state
            item.status = 'queued';
            item.progress = 0;
            item.error = null;
            item.result = null;
            if (item.type === 'componentized') {
                item.componentResults = [];
                item.currentComponent = null;
            }
            delete item.analysisId;

            this.updateBatchTableRow(item);
            this.updateBatchSummary();
            await this.persistBatchQueue();

            this.addLog('success', `Item reset to queued: ${item.master.name}. Click "Process Batch" to retry.`);

        } catch (err) {
            this.addLog('error', `Retry failed: ${err.message}`);
        }
    }

    /**
     * Restart a completed job - re-run analysis from scratch
     */
    async restartJob(itemId) {
        const item = this.batchQueue.find(i => i.id.toString() === itemId);
        if (!item) {
            this.addLog('error', 'Cannot restart: item not found');
            return;
        }

        if (item.status !== 'completed') {
            this.addLog('warning', `Cannot restart: item status is "${item.status}", not "completed"`);
            return;
        }

        try {
            this.addLog('info', `Restarting completed ${item.type === 'componentized' ? 'componentized' : 'batch'} item: ${item.master.name}`);

            // Store previous result for reference (optional - could display "previous" vs "new")
            item.previousResult = item.result;
            if (item.type === 'componentized') {
                item.previousComponentResults = item.componentResults;
            }

            // Reset item state
            item.status = 'queued';
            item.progress = 0;
            item.error = null;
            item.result = null;
            if (item.type === 'componentized') {
                item.componentResults = [];
                item.currentComponent = null;
            }
            delete item.analysisId;

            this.updateBatchTableRow(item);
            this.updateBatchSummary();
            await this.persistBatchQueue();

            this.addLog('success', `Item reset to queued: ${item.master.name}. Click "Process Batch" to re-run analysis.`);

        } catch (err) {
            this.addLog('error', `Restart failed: ${err.message}`);
        }
    }

    async persistBatchQueue() {
        try {
            const payload = { 
                items: this.batchQueue, 
                lastUpdated: new Date().toISOString(),
                clientId: this.clientId || 'unknown'
            };

            // Save to server as PRIMARY storage (for cross-browser sync)
            try {
                const resp = await fetch(`${this.FASTAPI_BASE}/batch-queue`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                if (resp.ok) {
                    console.log('Batch queue synced to server');
                }
            } catch (serverErr) {
                console.warn('Server sync failed:', serverErr);
            }

            // Also save to localStorage as BACKUP (for offline/fallback)
            try {
                localStorage.setItem('sync-analyzer-batch-queue', JSON.stringify(payload));
            } catch (storageErr) {
                console.warn('localStorage save failed:', storageErr);
            }
        } catch (e) {
            console.warn('Persist batch queue error:', e);
        }
    }

    async rehydrateBatchResults(force = false) {
        const enc = encodeURIComponent;
        for (const item of this.batchQueue) {
            const hasResult = item && item.result && typeof item.result.offset_seconds === 'number';
            if (!force && hasResult) continue;
            try {
                const url = `${this.FASTAPI_BASE}/reports/search?master_file=${enc(item.master.path)}&dub_file=${enc(item.dub.path)}&prefer_high_confidence=true`;
                const r = await fetch(url);
                if (!r.ok) continue;
                const j = await r.json();
                const rec = j && j.report ? j.report : null;
                if (!rec) continue;
                const adapted = {
                    offset_seconds: Number(rec.consensus_offset_seconds || 0),
                    confidence: Number(rec.confidence_score || 0),
                    method_used: 'Consensus',
                    quality_score: Number(rec.confidence_score || 0),
                    analysis_id: rec.analysis_id,
                    created_at: rec.created_at
                };
                item.analysisId = rec.analysis_id || item.analysisId;
                item.result = adapted;
                item.status = item.status === 'queued' ? 'completed' : item.status;
                item.progress = item.progress || 100;
                this.updateBatchTableRow(item);
            } catch (e) {
                // non-fatal
            }
        }
        this.updateBatchSummary();
        await this.persistBatchQueue().catch(() => {});
    }
    
    async repairBatchItem(itemId, mode = 'auto') {
        const item = this.batchQueue.find(item => item.id.toString() === itemId);
        if (!item || !item.result) {
            this.addLog('error', 'Cannot repair: invalid item or no analysis results');
            return;
        }
        
        try {
            this.addLog('info', `Starting ${mode} repair for: ${item.dub.name}`);
            // Decide keep duration from UI toggle if present, otherwise use item setting from CSV
            const keepToggle = document.getElementById(`keep-duration-${item.id}`);
            const keepDuration = keepToggle ? !!keepToggle.checked : (item.keepDuration !== undefined ? item.keepDuration : true);

            // Prefer per-channel offsets from analysis; otherwise synthesize uniform mapping
            const res = item.result || {};
            const per = res.per_channel_results && typeof res.per_channel_results === 'object' && Object.keys(res.per_channel_results).length
                ? res.per_channel_results
                : (() => {
                    const off = Number(item.result.offset_seconds || 0) || 0;
                    const roles = ['FL','FR','FC','LFE','SL','SR','S0','S1','S2','S3','S4','S5'];
                    const m = {};
                    roles.forEach(r => m[r] = { offset_seconds: off });
                    return m;
                  })();

            // Call FastAPI repair per-channel endpoint (API <- UI)
            const response = await fetch(`${this.FASTAPI_BASE}/repair/repair/per-channel`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_path: item.dub.path,
                    per_channel_results: per,
                    keep_duration: keepDuration
                })
            });

            const result = await response.json().catch(() => ({}));

            if (response.ok && result && result.success) {
                this.addLog('success', `Repair completed: ${result.output_file}`);
                item.repaired = true;
                item.repairedFile = result.output_file;
                this.updateBatchTableRow(item);
            } else {
                const err = result && result.error ? result.error : `${response.status}`;
                this.addLog('error', `Repair failed: ${err}`);
            }
            
        } catch (error) {
            this.addLog('error', `Repair error: ${error.message}`);
        }
    }

    // Repair all completed batch items
    async repairAllCompleted() {
        const completedItems = this.batchQueue.filter(item =>
            item.status === 'completed' &&
            item.result &&
            !item.repaired
        );

        if (completedItems.length === 0) {
            this.addLog('warning', 'No completed analyses available to repair');
            return;
        }

        this.addLog('info', `Starting batch repair for ${completedItems.length} completed items...`);

        let successCount = 0;
        let failCount = 0;

        for (const item of completedItems) {
            try {
                this.addLog('info', `Repairing: ${item.dub.name}`);

                // Use keepDuration from item if set, otherwise default to true
                const keepDuration = item.keepDuration !== undefined ? item.keepDuration : true;

                // Prepare per-channel offsets
                const res = item.result || {};
                const per = res.per_channel_results && typeof res.per_channel_results === 'object' && Object.keys(res.per_channel_results).length
                    ? res.per_channel_results
                    : (() => {
                        const off = Number(item.result.offset_seconds || 0) || 0;
                        const roles = ['FL','FR','FC','LFE','SL','SR','S0','S1','S2','S3','S4','S5'];
                        const m = {};
                        roles.forEach(r => m[r] = { offset_seconds: off });
                        return m;
                    })();

                // Call repair API
                const response = await fetch(`${this.FASTAPI_BASE}/repair/repair/per-channel`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_path: item.dub.path,
                        per_channel_results: per,
                        keep_duration: keepDuration
                    })
                });

                const result = await response.json().catch(() => ({}));

                if (response.ok && result && result.success) {
                    this.addLog('success', `Repaired: ${result.output_file}`);
                    item.repaired = true;
                    item.repairedFile = result.output_file;
                    this.updateBatchTableRow(item);
                    successCount++;
                } else {
                    const err = result && result.error ? result.error : `${response.status}`;
                    this.addLog('error', `Repair failed for ${item.dub.name}: ${err}`);
                    failCount++;
                }

                // Small delay between repairs to avoid overwhelming the server
                await new Promise(resolve => setTimeout(resolve, 100));

            } catch (error) {
                this.addLog('error', `Repair error for ${item.dub.name}: ${error.message}`);
                failCount++;
            }
        }

        this.addLog('success', `Batch repair complete: ${successCount} succeeded, ${failCount} failed`);
        await this.persistBatchQueue().catch(() => {});
    }

    // Configuration methods
    initializeConfiguration() {
        this.updateConfidenceValue();
        this.toggleAiConfig();
        // Set detection methods state based on offset mode (Channel-Aware disables them)
        this.updateDetectionMethodsState();
        this.setOperatorMode();
    }
    
    resetConfiguration() {
        // Reset to default values
        this.elements.sampleRate.value = '48000';
        this.elements.windowSize.value = '30';
        this.elements.confidenceThreshold.value = '0.7';
        this.elements.nMfcc.value = '13';
        this.elements.generateJson.checked = true;
        this.elements.generateVisualizations.checked = false;
        this.elements.enableGpu.checked = true;
        this.elements.verboseLogging.checked = false;
        this.elements.outputDirectory.value = './ui_sync_reports/';
        
        this.updateConfidenceValue();
        this.toggleAiConfig();
        // Update detection methods based on current offset mode
        // (Channel-Aware will gray them out, others will enable Onset+Spectral)
        this.updateDetectionMethodsState();
        this.addLog('info', 'Configuration reset to defaults');
    }
    
    updateConfidenceValue() {
        const value = Math.round(this.elements.confidenceThreshold.value * 100);
        this.elements.confidenceValue.textContent = `${value}%`;
    }
    
    toggleAiConfig() {
        if (!this.elements.methodAi || !this.elements.aiConfig) return;
        const isEnabled = this.elements.methodAi.checked;
        this.elements.aiConfig.style.display = isEnabled ? 'block' : 'none';
        
        if (isEnabled) {
            this.addLog('info', 'AI analysis enabled - select model type below');
        }
    }
    
    updateMethodSelection() {
        const selectedMethods = [];
        
        // GPU mode is exclusive - fastest single-method detection (auto-verifies if needed)
        if (this.elements.methodGpu && this.elements.methodGpu.checked) {
            selectedMethods.push('gpu');
            // Uncheck other methods when GPU is selected (exclusive mode)
            if (this.elements.methodMfcc) this.elements.methodMfcc.checked = false;
            if (this.elements.methodOnset) this.elements.methodOnset.checked = false;
            if (this.elements.methodSpectral) this.elements.methodSpectral.checked = false;
            if (this.elements.methodAi) this.elements.methodAi.checked = false;
            if (this.elements.methodFingerprint) this.elements.methodFingerprint.checked = false;
            this.currentMethods = selectedMethods;
            this.addLog('info', '🚀 GPU Fast mode enabled - Wav2Vec2 single-pass detection');
            return;
        }
        
        // Fingerprint mode is exclusive - robust audio fingerprinting
        if (this.elements.methodFingerprint && this.elements.methodFingerprint.checked) {
            selectedMethods.push('fingerprint');
            // Uncheck other methods when Fingerprint is selected (exclusive mode)
            if (this.elements.methodMfcc) this.elements.methodMfcc.checked = false;
            if (this.elements.methodOnset) this.elements.methodOnset.checked = false;
            if (this.elements.methodSpectral) this.elements.methodSpectral.checked = false;
            if (this.elements.methodAi) this.elements.methodAi.checked = false;
            if (this.elements.methodGpu) this.elements.methodGpu.checked = false;
            this.currentMethods = selectedMethods;
            this.addLog('info', '🔊 Fingerprint mode enabled - Chromaprint robust detection');
            return;
        }
        
        if (this.elements.methodMfcc.checked) selectedMethods.push('mfcc');
        if (this.elements.methodOnset.checked) selectedMethods.push('onset');
        if (this.elements.methodSpectral.checked) selectedMethods.push('spectral');
        if (this.elements.methodAi && this.elements.methodAi.checked) selectedMethods.push('ai');
        
        // If traditional methods selected, uncheck exclusive modes (GPU, Fingerprint)
        if (selectedMethods.length > 0) {
            if (this.elements.methodGpu) this.elements.methodGpu.checked = false;
            if (this.elements.methodFingerprint) this.elements.methodFingerprint.checked = false;
        }
        
        if (selectedMethods.length === 0) {
            this.elements.methodMfcc.checked = true;
            selectedMethods.push('mfcc');
            this.updateToggleVisualFeedback(this.elements.methodMfcc);
            this.addLog('warning', 'At least one detection method must be selected - defaulting to MFCC');
        }
        
        this.currentMethods = selectedMethods;
        this.addLog('info', `Selected detection methods: ${selectedMethods.join(', ').toUpperCase()}`);
    }
    
    updateToggleVisualFeedback(checkbox) {
        // Find the method item container
        const methodItem = checkbox.closest('.method-item') || checkbox.closest('.toggle-item');
        if (methodItem) {
            if (checkbox.checked) {
                methodItem.classList.add('active');
            } else {
                methodItem.classList.remove('active');
            }
        }
    }

    updateDetectionMethodsState() {
        // Gray out detection methods ONLY when:
        // - In Componentized mode AND Channel-Aware offset mode is selected
        // Enable detection methods when:
        // - In Standard analysis mode (single file), OR
        // - In Componentized mode with Standard/Mixdown/Anchor offset mode
        const analysisMode = this.analysisMode || 'standard';
        const offsetMode = this.componentizedOffsetMode;
        const shouldDisable = analysisMode === 'componentized' && offsetMode === 'channel_aware';
        
        const methodContainer = document.getElementById('method-selection-container');
        const channelAwareNote = document.getElementById('channel-aware-note');
        
        console.log('[updateDetectionMethodsState] analysisMode:', analysisMode, 'offsetMode:', offsetMode, 'shouldDisable:', shouldDisable);
        
        if (methodContainer) {
            if (shouldDisable) {
                console.log('[updateDetectionMethodsState] Disabling methods (Componentized + Channel-Aware)');
                methodContainer.style.opacity = '0.4';
                methodContainer.style.pointerEvents = 'none';
                // Disable and uncheck all checkboxes to show they're not used (except GPU which overrides)
                [this.elements.methodMfcc, this.elements.methodOnset, this.elements.methodSpectral, this.elements.methodAi].forEach(cb => {
                    if (cb) {
                        cb.disabled = true;
                        cb.checked = false;
                        this.updateToggleVisualFeedback(cb);
                    }
                });
                // GPU Fast mode should ALWAYS be available and override channel-aware
                if (this.elements.methodGpu) {
                    this.elements.methodGpu.disabled = false;
                    // Re-enable the GPU row visually
                    const gpuContainer = this.elements.methodGpu.closest('.method-item');
                    if (gpuContainer) {
                        gpuContainer.style.opacity = '1';
                        gpuContainer.style.pointerEvents = 'auto';
                    }
                }
                this.updateMethodSelection();
            } else {
                console.log('[updateDetectionMethodsState] Enabling methods');
                methodContainer.style.opacity = '1';
                methodContainer.style.pointerEvents = 'auto';
                // Re-enable checkboxes and restore default selection
                [this.elements.methodMfcc, this.elements.methodOnset, this.elements.methodSpectral, this.elements.methodAi, this.elements.methodGpu, this.elements.methodFingerprint].forEach(cb => {
                    if (cb) cb.disabled = false;
                });
                // Restore at least one method if none selected (and exclusive modes aren't checked)
                const gpuChecked = this.elements.methodGpu && this.elements.methodGpu.checked;
                const exclusiveModeOn = gpuChecked;
                if (!exclusiveModeOn && !this.elements.methodMfcc.checked && !this.elements.methodOnset.checked &&
                    !this.elements.methodSpectral.checked && (!this.elements.methodAi || !this.elements.methodAi.checked)) {
                    this.elements.methodOnset.checked = true;
                    this.elements.methodSpectral.checked = true;
                    this.updateToggleVisualFeedback(this.elements.methodOnset);
                    this.updateToggleVisualFeedback(this.elements.methodSpectral);
                }
                this.updateMethodSelection();
            }
        } else {
            console.warn('[updateDetectionMethodsState] methodContainer not found!');
        }
        
        if (channelAwareNote) {
            channelAwareNote.style.display = shouldDisable ? 'inline' : 'none';
        }
    }

    setOperatorMode() {
        try {
            // Load saved preference on first call
            if (!this.hasSetOperatorModeFromStorage && this.elements.operatorMode) {
                try {
                    const saved = localStorage.getItem('sync-analyzer-operator-mode');
                    if (saved !== null) {
                        this.elements.operatorMode.checked = saved === 'true';
                    }
                } catch (e) {
                    console.warn('Failed to load operator mode preference:', e);
                }
                this.hasSetOperatorModeFromStorage = true;
            }

            const on = !!(this.elements.operatorMode && this.elements.operatorMode.checked);
            this.operatorMode = on;

            // Update document class for CSS targeting
            document.body.classList.toggle('operator-mode', on);
            document.body.classList.toggle('technical-mode', !on);

            // Control visibility of operator-friendly elements
            const operatorElements = [
                '.action-recommendations-panel',
                '.drift-severity-guide',
                '.operator-console',
                '#operator-timeline'
            ];

            operatorElements.forEach(selector => {
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    if (el) el.style.display = on ? '' : 'none';
                });
            });

            // Control visibility of technical elements
            const technicalElements = [
                '.analysis-json-data',
                '.technical-details',
                '.debug-info'
            ];

            technicalElements.forEach(selector => {
                const elements = document.querySelectorAll(selector);
                elements.forEach(el => {
                    if (el) el.style.display = !on ? '' : 'none';
                });
            });

            // Update existing analysis results display if any are shown
            document.querySelectorAll('.batch-item').forEach(item => {
                const id = item.dataset.itemId;
                if (id) {
                    this.updateDisplayModeForItem(id, on);
                }
            });

            // Save preference
            try {
                localStorage.setItem('sync-analyzer-operator-mode', on ? 'true' : 'false');
            } catch (e) {
                console.warn('Failed to save operator mode preference:', e);
            }

            this.addLog('info', `${on ? '👤 Operator' : '🔧 Technical'} mode ${on ? 'enabled' : 'disabled'}`);

        } catch (e) {
            console.warn('Operator mode toggle failed:', e);
        }
    }

    /**
     * Update display mode for a specific analysis item
     */
    updateDisplayModeForItem(itemId, operatorMode) {
        // Update action recommendations visibility
        const recPanel = document.getElementById(`recommendations-${itemId}`);
        if (recPanel) {
            recPanel.style.display = operatorMode ? '' : 'none';
        }

        // Update analysis JSON data visibility
        const jsonPanel = document.querySelector(`#item-${itemId} .analysis-json-data`);
        if (jsonPanel) {
            jsonPanel.style.display = operatorMode ? 'none' : '';
        }

        // Regenerate recommendations if switching to operator mode
        if (operatorMode && recPanel && recPanel.querySelector('.recommendations-loading')) {
            const item = this.batchItems.find(it => it.id === itemId);
            if (item && item.result) {
                this.generateActionRecommendations(item);
            }
        }
    }
    
    getAnalysisConfig() {
        const aiModel = document.querySelector('input[name="ai-model"]:checked')?.value || 'wav2vec2';
        const enableDriftDetection = this.elements.enableDriftDetection?.checked || false;

        // Only add correlation if drift detection is enabled
        const methods = this.currentMethods || ['mfcc'];
        if (enableDriftDetection && !methods.includes('correlation')) {
            methods.push('correlation');
        }

        return {
            methods: methods,
            sampleRate: parseInt(this.elements.sampleRate.value),
            windowSize: parseFloat(this.elements.windowSize.value),
            confidenceThreshold: parseFloat(this.elements.confidenceThreshold.value),
            nMfcc: parseInt(this.elements.nMfcc.value),
            generateJson: this.elements.generateJson.checked,
            generateVisualizations: this.elements.generateVisualizations.checked,
            enableGpu: this.elements.enableGpu.checked,
            verboseLogging: this.elements.verboseLogging.checked,
            enableDriftDetection: enableDriftDetection,
            outputDirectory: this.elements.outputDirectory.value,
            aiModel: (this.elements.methodAi && this.elements.methodAi.checked) ? aiModel : null,
            channelStrategy: this.elements.channelStrategy?.value || 'mono_downmix',
            targetChannels: (this.elements.targetChannels?.value || '').split(',').map(s => s.trim()).filter(Boolean)
        };
    }
    
    // Enhanced details methods
    exportResults() {
        const currentItem = this.elements.batchDetails.dataset.currentItem;
        if (!currentItem) return;
        
        const item = this.batchQueue.find(item => item.id.toString() === currentItem);
        if (!item || !item.result) {
            this.addLog('error', 'No results available to export');
            return;
        }
        
        const exportData = {
            timestamp: new Date().toISOString(),
            files: {
                master: item.master,
                dub: item.dub
            },
            analysis: item.result,
            configuration: this.getAnalysisConfig()
        };
        
        const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sync_analysis_${item.id}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        
        this.addLog('success', `Results exported: sync_analysis_${item.id}.json`);
    }
    
    compareResults() {
        const currentItem = this.elements.batchDetails.dataset.currentItem;
        if (!currentItem) return;
        
        const completedItems = this.batchQueue.filter(item => item.status === 'completed' && item.result);
        if (completedItems.length < 2) {
            this.addLog('warning', 'Need at least 2 completed analyses to compare results');
            return;
        }
        
        this.addLog('info', `Compare mode: Select another analysis from ${completedItems.length} completed items`);
        // In a real implementation, this would show a comparison UI
    }

    // Waveform visualization methods
    toggleSyncView(itemId) {
        const beforeEl = document.querySelector(`#dub-track-${itemId} .sync-before`);
        const afterEl = document.querySelector(`#dub-track-${itemId} .sync-after`);
        const toggleBtn = document.getElementById(`toggle-sync-${itemId}`);
        
        if (beforeEl && afterEl && toggleBtn) {
            const showingBefore = beforeEl.style.display !== 'none';
            
            if (showingBefore) {
                beforeEl.style.display = 'none';
                afterEl.style.display = 'flex';
                toggleBtn.innerHTML = '<i class="fas fa-undo"></i> Show Before';
                this.addLog('info', 'Showing dub audio AFTER sync correction');
            } else {
                beforeEl.style.display = 'flex';
                afterEl.style.display = 'none';
                toggleBtn.innerHTML = '<i class="fas fa-exchange-alt"></i> Toggle Before/After';
                this.addLog('info', 'Showing dub audio BEFORE sync correction');
            }
        }
    }
    
    playPreview(itemId) {
        const item = this.batchQueue.find(item => item.id.toString() === itemId);
        if (item) {
            this.addLog('info', `Playing preview: ${item.master.name} vs ${item.dub.name}`);
            const fps = item.frameRate || this.detectedFrameRate;
            this.addLog('info', `Detected offset: ${this.formatOffsetDisplay(item.result.offset_seconds, true, fps)}`);
            // In a real implementation, this would play audio samples
            // For now, just show preview information
        }
    }

    /**
     * Initialize the enhanced waveform visualization
     */
    async initializeEnhancedWaveform(item, offsetSeconds) {
        try {
            const container = document.getElementById(`enhanced-waveform-${item.id}`);
            if (!container) {
                console.warn('Enhanced waveform container not found');
                return;
            }

            this.addLog('info', 'Generating exact waveform representation...');

            // Prepare drift timeline data for markers (prefer timeline, fallback to drift_analysis or chunk_details)
            const toTimeline = (res) => {
                if (!res || typeof res !== 'object') return [];
                if (Array.isArray(res.timeline) && res.timeline.length) return res.timeline;
                if (res.drift_analysis && Array.isArray(res.drift_analysis.timeline) && res.drift_analysis.timeline.length) return res.drift_analysis.timeline;
                if (Array.isArray(res.chunk_details)) {
                    return res.chunk_details.map(ch => ({
                        start_time: ch.start_time,
                        end_time: ch.end_time,
                        offset_seconds: ch.offset_detection?.offset_seconds ?? ch.offset_seconds ?? 0,
                        confidence: ch.offset_detection?.confidence ?? ch.confidence ?? null,
                        reliable: !!ch.reliable,
                        quality: ch.quality || null
                    }));
                }
                return [];
            };
            const timelineData = toTimeline(item.result || {});

            // Generate the enhanced waveform visualization
            await this.waveformVisualizer.generateSyncWaveforms(
                `master-${item.id}`,
                `dub-${item.id}`,
                offsetSeconds,
                container,
                timelineData
            );

            // If item has file paths, prepare Chrome-compatible proxies and load those first
            if (item.master?.path && item.dub?.path) {
                let masterUrl = null;
                let dubUrl = null;
                let repairedUrl = null;
                try {
                    this.addLog('info', 'Preparing playback proxies for finished job...');
                    const prep = await fetch('/api/v1/proxy/prepare', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ master: item.master.path, dub: item.dub.path })
                    }).then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)));
                    if (prep && prep.success) {
                        masterUrl = prep.master_url;
                        dubUrl = prep.dub_url;
                        this.addLog('success', 'Proxies prepared for finished job');
                    }
                } catch (e) {
                    this.addLog('warning', `Proxy prepare failed for finished job: ${e.message}. Falling back to raw paths.`);
                }

                // Fallback to raw URLs if proxy prep failed
                if (!masterUrl || !dubUrl) {
                    const enc = encodeURIComponent;
                    masterUrl = `/api/v1/files/raw?path=${enc(item.master.path)}`;
                    dubUrl = `/api/v1/files/raw?path=${enc(item.dub.path)}`;
                }

                // If we have a repaired file for this item, prepare a URL for it too
                if (item.repaired && item.repairedFile) {
                    try {
                        const p = await fetch('/api/v1/proxy/prepare', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ master: item.master.path, dub: item.repairedFile })
                        }).then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)));
                        if (p && p.success) repairedUrl = p.dub_url;
                    } catch {}
                    if (!repairedUrl) {
                        const enc = encodeURIComponent;
                        repairedUrl = `/api/v1/files/raw?path=${enc(item.repairedFile)}`;
                    }
                }

                try {
                    this.addLog('info', `Loading audio URLs for playback...`);
                    console.log('Audio URL load attempt:', { masterUrl, dubUrl });
                    const loader = async (url, type) => {
                        // Prefer engine direct load for reliability
                        if (this.waveformVisualizer) {
                            if (!this.waveformVisualizer.audioEngine) {
                                // Create engine on the fly and wire callbacks if extension present
                                this.waveformVisualizer.audioEngine = new CoreAudioEngine();
                                if (typeof this.waveformVisualizer.setupAudioEngineCallbacks === 'function') {
                                    this.waveformVisualizer.setupAudioEngineCallbacks();
                                }
                            }
                            if (this.waveformVisualizer.audioEngine && typeof this.waveformVisualizer.audioEngine.loadAudioUrl === 'function') {
                                return this.waveformVisualizer.audioEngine.loadAudioUrl(url, type);
                            }
                            if (typeof this.waveformVisualizer.loadAudioUrl === 'function') {
                                return this.waveformVisualizer.loadAudioUrl(url, type);
                            }
                        }
                        window.showToast?.('error', `No audio loader available for ${type} — ${url}`, 'Audio Load');
                        throw new Error('No audio URL loader available');
                    };
                    await Promise.all([
                        loader(masterUrl, 'master'),
                        loader(dubUrl, 'dub')
                    ]);
                    // After loading real audio, regenerate the unified timeline to reflect real peaks
                    const unifiedContainer = container.querySelector('.unified-waveform-container');
                    if (unifiedContainer) {
                        // Store paths on DOM for later playback attempts
                        unifiedContainer.dataset.masterPath = item.master.path;
                        unifiedContainer.dataset.dubPath = item.dub.path;
                        unifiedContainer.dataset.masterUrl = masterUrl;
                        unifiedContainer.dataset.dubUrl = dubUrl;
                        if (repairedUrl) unifiedContainer.dataset.repairedUrl = repairedUrl;
                        if (item.repaired && item.repairedFile) unifiedContainer.dataset.repairedPath = item.repairedFile;
                        await this.waveformVisualizer.generateUnifiedTimeline(
                            `master-${item.id}`,
                            `dub-${item.id}`,
                            offsetSeconds,
                            container,
                            timelineData
                        );
                    }
                    this.addLog('success', 'Real audio loaded for finished job');
                } catch (e) {
                    console.warn('Audio URL load failed:', e);
                    this.addLog('warning', `Could not auto-load audio from job paths: ${e.message}`);
                    window.showToast?.('error', `Auto-load failed: ${e.message}`, 'Audio Load');
                }
            }

            // Update analysis metrics in the waveform display
            this.updateWaveformMetrics(item);

            this.addLog('success', 'Enhanced waveform visualization completed');

            // Generate action recommendations for operators
            this.generateActionRecommendations(item);

        } catch (error) {
            console.error('Error initializing enhanced waveform:', error);
            this.addLog('error', `Waveform generation failed: ${error.message}`);
        }
    }

    /**
     * Update the analysis metrics displayed in the waveform
     */
    updateWaveformMetrics(item) {
        try {
            const result = item.result;
            if (!result) return;

            // Update correlation score
            const correlationEl = document.getElementById(`correlation-master-${item.id}-dub-${item.id}`);
            if (correlationEl) {
                const correlation = result.correlation || 0.85; // Default fallback
                correlationEl.textContent = `${(correlation * 100).toFixed(1)}%`;
                correlationEl.className = `metric-value correlation-score ${correlation > 0.8 ? 'high' : correlation > 0.6 ? 'medium' : 'low'}`;
            }

            // Update confidence score
            const confidenceEl = document.getElementById(`confidence-master-${item.id}-dub-${item.id}`);
            if (confidenceEl) {
                const confidence = result.confidence || 0;
                confidenceEl.textContent = `${(confidence * 100).toFixed(0)}%`;
                confidenceEl.className = `metric-value confidence-score ${confidence > 0.8 ? 'high' : confidence > 0.5 ? 'medium' : 'low'}`;
            }

            // Update quality score
            const qualityEl = document.getElementById(`quality-master-${item.id}-dub-${item.id}`);
            if (qualityEl) {
                const quality = result.quality_score || 0;
                qualityEl.textContent = `${(quality * 100).toFixed(0)}%`;
                qualityEl.className = `metric-value quality-score ${quality > 0.7 ? 'high' : quality > 0.4 ? 'medium' : 'low'}`;
            }

        } catch (error) {
            console.error('Error updating waveform metrics:', error);
        }
    }

    /**
     * Generate operator-friendly action recommendations
     */
    generateActionRecommendations(item) {
        try {
            const container = document.getElementById(`recommendations-${item.id}`);
            if (!container) return;

            const result = item.result;
            const itemFps = item.frameRate || this.detectedFrameRate;
            if (!result) {
                container.innerHTML = '<div class="recommendations-error">No analysis data available</div>';
                return;
            }

            // Extract key metrics
            const offsetSeconds = Math.abs(result.offset_seconds || 0);
            // Use backend's pre-calculated milliseconds to avoid precision loss
            const offsetMs = result.offset_milliseconds !== undefined
                ? Math.abs(result.offset_milliseconds)
                : offsetSeconds * 1000;
            const confidence = result.confidence || 0;
            const qualityScore = result.quality_score || 0;
            const timelineData = result.timeline || [];
            const driftAnalysis = result.drift_analysis || {};

            // Determine severity and primary action
            let severity, priority, primaryAction, icon;
            if (offsetMs <= 40) {
                severity = 'in_sync';
                priority = 'low';
                primaryAction = 'No immediate action required';
                icon = '✅';
            } else if (offsetMs <= 100) {
                severity = 'minor';
                priority = 'low';
                primaryAction = 'Consider minor correction';
                icon = '⚠️';
            } else if (offsetMs <= 1000) {
                severity = 'issue';
                priority = 'medium';
                primaryAction = 'Sync correction recommended';
                icon = '🟠';
            } else {
                severity = 'major';
                priority = 'high';
                primaryAction = 'Immediate sync correction required';
                icon = '🔴';
            }

            // Build recommendations based on analysis
            const recommendations = [];

            if (severity === 'in_sync') {
                recommendations.push({
                    type: 'success',
                    icon: '✅',
                    title: 'Sync Quality: Excellent',
                    description: `Audio is perfectly synchronized (${this.formatOffsetDisplay(result.offset_seconds, true, itemFps)})`,
                    action: 'No correction needed. File is ready for delivery.'
                });
            } else {
                // Add primary correction recommendation
                const framesDetectedRec = Math.round(Math.abs(result.offset_seconds) * itemFps);
                const frameSign = result.offset_seconds < 0 ? '-' : '+';
                recommendations.push({
                    type: severity === 'minor' ? 'info' : severity === 'issue' ? 'warning' : 'error',
                    icon: icon,
                    title: `Sync Issue: ${result.offset_seconds >= 0 ? '+' : ''}${result.offset_seconds.toFixed(3)}s (${frameSign}${framesDetectedRec}f @ ${itemFps}fps)`,
                    description: `${result.offset_seconds > 0 ? 'Dub audio is ahead of master' : 'Dub audio is behind master'}`,
                    action: confidence > 0.8 ?
                        `Use Auto Repair with high confidence (${(confidence * 100).toFixed(0)}%)` :
                        `Manual review recommended - confidence only ${(confidence * 100).toFixed(0)}%`
                });
            }

            // Quality-based recommendations
            if (qualityScore < 0.4) {
                recommendations.push({
                    type: 'warning',
                    icon: '🔍',
                    title: 'Audio Quality: Poor',
                    description: 'Low audio clarity detected in analysis',
                    action: 'Consider using different analysis method or check source audio quality'
                });
            } else if (qualityScore < 0.7) {
                recommendations.push({
                    type: 'info',
                    icon: '🎵',
                    title: 'Audio Quality: Mixed',
                    description: 'Some segments have unclear audio',
                    action: 'Review timeline markers for problematic sections'
                });
            }

            // Drift-based recommendations
            if (driftAnalysis.has_drift) {
                const maxDriftSec = Math.max(...timelineData.map(t => Math.abs(t.offset_seconds || 0)));
                const maxDriftFrames = Math.round(maxDriftSec * itemFps);
                recommendations.push({
                    type: 'warning',
                    icon: '📊',
                    title: `Variable Drift Detected`,
                    description: `Drift varies from ${this.formatOffsetDisplay(result.offset_seconds, false)} to ${maxDriftSec.toFixed(3)}s (${maxDriftFrames}f @ ${itemFps}fps) across timeline`,
                    action: 'Use per-channel repair for complex sync patterns'
                });
            }

            // Confidence-based recommendations
            if (confidence < 0.5) {
                recommendations.push({
                    type: 'error',
                    icon: '⚠️',
                    title: 'Low Detection Confidence',
                    description: `Analysis confidence is only ${(confidence * 100).toFixed(0)}%`,
                    action: 'Manual review required before applying any corrections'
                });
            }

            // Generate HTML
            const html = `
                <div class="recommendations-header">
                    <h3><i class="fas fa-lightbulb"></i> Action Recommendations</h3>
                    <div class="priority-badge priority-${priority}">
                        ${priority.toUpperCase()} PRIORITY
                    </div>
                </div>
                <div class="recommendations-list">
                    ${recommendations.map(rec => `
                        <div class="recommendation-item ${rec.type}">
                            <div class="rec-icon">${rec.icon}</div>
                            <div class="rec-content">
                                <div class="rec-title">${rec.title}</div>
                                <div class="rec-description">${rec.description}</div>
                                <div class="rec-action"><strong>Action:</strong> ${rec.action}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
                <div class="recommendations-footer">
                    <div class="next-steps">
                        <strong>Recommended Next Step:</strong> ${primaryAction}
                    </div>
                </div>
            `;

            container.innerHTML = html;

            this.addLog('info', `Generated ${recommendations.length} action recommendations`);

        } catch (error) {
            console.error('Error generating action recommendations:', error);
            const container = document.getElementById(`recommendations-${item.id}`);
            if (container) {
                container.innerHTML = '<div class="recommendations-error">Failed to generate recommendations</div>';
            }
        }
    }

    initializeQCInterface() {
        this.qcInterface = new QCInterface();
        
        // Set up QC interface callbacks
        this.qcInterface.onApprove = (data) => {
            console.log('Sync approved:', data);
            this.showToast('success', 'Sync analysis approved', 'QC Review');
        };
        
        this.qcInterface.onFlag = (data) => {
            console.log('Sync flagged:', data);
            this.showToast('warning', 'Sync analysis flagged for review', 'QC Review');
        };
        
        this.qcInterface.onReject = (data) => {
            console.log('Sync rejected:', data);
            this.showToast('error', 'Sync analysis rejected', 'QC Review');
        };

        // Add QC button click handler
        document.addEventListener('click', (e) => {
            if (e.target.closest('.qc-open-btn')) {
                this.openQCInterface(e.target.closest('.qc-open-btn'));
            }
        });

        console.log('QC Interface initialized');
    }

    initializeRepairQCInterface() {
        this.repairQC = new RepairQCInterface({ apiBase: this.FASTAPI_BASE });
        // Open handler
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.repair-qc-open-btn');
            if (!btn) return;
            this.openRepairQCInterface(btn);
        });
        console.log('Repair QC Interface initialized');
    }

    async openRepairQCInterface(button) {
        try {
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Opening...';

            const masterPath = button.dataset.masterPath;
            const dubPath = button.dataset.dubPath;
            // Find the batch item to extract per-channel results if present
            const row = button.closest('tr.batch-row');
            let item = null;
            if (row) {
                const id = row.getAttribute('data-item-id');
                item = this.batchQueue.find(i => String(i.id) === String(id));
            }
            const res = item?.result || {};
            const itemFps = item?.frameRate || this.detectedFrameRate;

            const syncData = {
                masterFile: masterPath ? masterPath.split('/').pop() : (this.selectedMaster?.name || 'Master'),
                dubFile: dubPath ? dubPath.split('/').pop() : (this.selectedDub?.name || 'Dub'),
                detectedOffset: parseFloat(button.dataset.offset || '0') || 0,
                confidence: res.confidence || 0,
                masterUrl: this.getAudioUrlForFile(masterPath || this.selectedMaster?.path, 'master'),
                dubUrl: this.getAudioUrlForFile(dubPath || this.selectedDub?.path, 'dub'),
                perChannel: res.per_channel_results || null,
                dubPath: dubPath,
                timeline: res.timeline || [],
                operatorTimeline: res.operator_timeline || null,
                frameRate: itemFps
            };

            await this.repairQC.open(syncData, { apiBase: this.FASTAPI_BASE });
        } catch (e) {
            this.showToast('error', `Failed to open Repair QC: ${e.message}`, 'Repair QC');
        } finally {
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-toolbox"></i> Repair QC';
        }
    }

    getAudioUrlForFile(filePath, role = 'master') {
        if (!filePath) return null;
        
        // Check file extension to determine if we need audio extraction
        const ext = filePath.toLowerCase().split('.').pop();
        const videoExtensions = ['mov', 'mp4', 'avi', 'mkv', 'wmv', 'mxf'];
        const audioExtensions = ['wav', 'mp3', 'flac', 'm4a', 'aiff', 'ogg', 'aac', 'ec3', 'eac3', 'adm', 'iab'];
        
        if (videoExtensions.includes(ext)) {
            // Use audio proxy endpoint for video files (WAV for WebAudio decode)
            console.log(`Using audio proxy (wav) for video file: ${filePath} (role=${role})`);
            return `/api/v1/files/proxy-audio?path=${encodeURIComponent(filePath)}&format=wav&role=${role}`;
        } else if (audioExtensions.includes(ext)) {
            // Use raw endpoint for audio files
            console.log(`Using raw endpoint for audio file: ${filePath}`);
            return `/api/v1/files/raw?path=${encodeURIComponent(filePath)}`;
        } else {
            // Unknown format, try raw endpoint
            console.warn(`Unknown file format: ${ext}, trying raw endpoint`);
            return `/api/v1/files/raw?path=${encodeURIComponent(filePath)}`;
        }
    }

    async openQCInterface(button) {
        console.log('QC button clicked, processing...');
        
        try {
            // Show immediate feedback
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Opening...';
            
            const masterId = button.dataset.masterId;
            const dubId = button.dataset.dubId;
            const offset = parseFloat(button.dataset.offset || '0');
            
            // Check if we have batch data (from table) or current selection data
            const masterPath = button.dataset.masterPath;
            const dubPath = button.dataset.dubPath;
            
            let syncData;
            
            if (masterPath && dubPath) {
                // Data from batch table - use smart URL generation
                // Try to find the matching batch item to pass through timeline data
                let matchedItem = null;
                if (this.batchQueue && masterPath && dubPath) {
                    matchedItem = this.batchQueue.find(i => i.master?.path === masterPath && i.dub?.path === dubPath);
                }
                const res = matchedItem?.result || {};
                const itemFps = matchedItem?.frameRate || this.detectedFrameRate;
                syncData = {
                    masterFile: masterPath.split('/').pop(),
                    dubFile: dubPath.split('/').pop(),
                    detectedOffset: offset,
                    confidence: typeof res.confidence === 'number' ? res.confidence : 0.85,
                    masterUrl: this.getAudioUrlForFile(masterPath, 'master'),
                    dubUrl: this.getAudioUrlForFile(dubPath, 'dub'),
                    timeline: res.timeline || [],
                    operatorTimeline: res.operator_timeline || null,
                    frameRate: itemFps
                };
            } else {
                // Data from current selection (waveform interface)
                syncData = {
                    masterFile: this.selectedMaster?.name || 'Unknown Master',
                    dubFile: this.selectedDub?.name || 'Unknown Dub',
                    detectedOffset: offset,
                    confidence: 0.85, // Mock confidence - would come from analysis
                    masterUrl: this.getAudioUrlForFile(this.selectedMaster?.path, 'master'),
                    dubUrl: this.getAudioUrlForFile(this.selectedDub?.path, 'dub'),
                    timeline: [],
                    operatorTimeline: null,
                    frameRate: this.detectedFrameRate
                };
            }

            console.log('Opening QC interface with data:', syncData);
            
            // Check if QC interface exists
            if (!this.qcInterface) {
                throw new Error('QC Interface not initialized');
            }
            
            // Open the interface (now async but non-blocking)
            await this.qcInterface.open(syncData);
            
            console.log('QC interface opened successfully');
            
        } catch (error) {
            console.error('Failed to open QC interface:', error);
            this.showToast('error', `Failed to open QC interface: ${error.message}`, 'QC Review');
        } finally {
            // Reset button state
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-microscope"></i> QC';
        }
    }

    /**
     * Open componentized QC interface showing ALL components in multi-track view
     */
    async openComponentizedQCInterface(item) {
        console.log('Opening componentized QC interface for item:', item);

        try {
            if (!item.componentResults || item.componentResults.length === 0) {
                this.showToast('warning', 'No component results available for QC', 'Componentized QC');
                return;
            }

            // Build component data array with all tracks
            const fps = item.frameRate || this.detectedFrameRate || 23.976;
            const components = item.componentResults.map((result, index) => {
                const component = item.components[index];
                return {
                    name: component?.name || result.component || `Component ${index + 1}`,
                    dubFile: component?.path || result.dub_path,
                    dubUrl: this.getAudioUrlForFile(component?.path || result.dub_path, 'dub'),
                    detectedOffset: result.offset_seconds,
                    confidence: result.confidence,
                    timeline: result.timeline || [],
                    operatorTimeline: result.operator_timeline || null
                };
            });

            // Open QC interface with ALL components
            const syncData = {
                analysisId: item.id || item.job_id,
                masterFile: item.master?.name || item.master_file,
                masterUrl: this.getAudioUrlForFile(item.master?.path || item.master_path, 'master'),
                // Pass first component as primary dub for backward compatibility
                dubFile: components[0]?.name,
                dubUrl: components[0]?.dubUrl,
                detectedOffset: components[0]?.detectedOffset || 0,
                confidence: components[0]?.confidence || 0,
                frameRate: fps,
                // Pass all components for multi-track view
                components: components,
                componentResults: item.componentResults,
                isComponentized: true
            };

            console.log('Opening QC interface with ALL components:', syncData);
            console.log('Component count:', components.length);

            if (!this.qcInterface) {
                throw new Error('QC Interface not initialized');
            }

            await this.qcInterface.open(syncData);
            console.log('Componentized QC interface opened with', components.length, 'tracks');

        } catch (error) {
            console.error('Failed to open componentized QC interface:', error);
            this.showToast('error', `Failed to open componentized QC: ${error.message}`, 'Componentized QC');
        }
    }

    /**
     * Open componentized repair interface for all components
     */
    async openComponentizedRepairInterface(item) {
        console.log('Opening componentized repair interface for item:', item);

        try {
            if (!item.componentResults || item.componentResults.length === 0) {
                this.showToast('warning', 'No component results available for repair', 'Componentized Repair');
                return;
            }

            // Create a component selector dialog
            const componentOptions = item.componentResults.map((result, index) => {
                const component = item.components[index];
                const fps = result.frameRate || item.frameRate || this.detectedFrameRate;
                const timecode = this.formatTimecode(result.offset_seconds, fps);

                return {
                    label: result.component,
                    name: component.name,
                    path: component.path,
                    offset: result.offset_seconds,
                    confidence: result.confidence,
                    timecode: timecode,
                    result: result
                };
            });

            // Show component selector with waveform visualization
            const selectedComponent = await this.showComponentSelector(componentOptions, 'Select Component for Repair', item);

            if (!selectedComponent) {
                return; // User cancelled
            }

            // Open repair interface for the selected component
            const fps = selectedComponent.result.frameRate || item.frameRate || this.detectedFrameRate;
            const syncData = {
                masterFile: item.master.name,
                dubFile: selectedComponent.name,
                detectedOffset: selectedComponent.offset,
                confidence: selectedComponent.confidence,
                masterUrl: this.getAudioUrlForFile(item.master.path, 'master'),
                dubUrl: this.getAudioUrlForFile(selectedComponent.path, 'dub'),
                masterPath: item.master.path,
                dubPath: selectedComponent.path,
                timeline: selectedComponent.result.timeline || [],
                operatorTimeline: selectedComponent.result.operator_timeline || null,
                frameRate: fps
            };

            console.log('Opening repair interface with componentized data:', syncData);

            if (!this.repairQC) {
                throw new Error('Repair Interface not initialized');
            }

            await this.repairQC.open(syncData, { apiBase: this.FASTAPI_BASE });
            console.log('Componentized repair interface opened successfully');

        } catch (error) {
            console.error('Failed to open componentized repair interface:', error);
            this.showToast('error', `Failed to open componentized repair: ${error.message}`, 'Componentized Repair');
        }
    }

    /**
     * Show a dialog to select a component from the list
     */
    async showComponentSelector(componentOptions, title = 'Select Component', item = null) {
        return new Promise((resolve) => {
            // Create modal overlay
            const overlay = document.createElement('div');
            overlay.className = 'component-selector-overlay';
            overlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.7);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                animation: fadeIn 0.2s ease;
            `;

            // Create modal dialog - wider to fit content
            const dialog = document.createElement('div');
            dialog.className = 'component-selector-dialog';
            dialog.style.cssText = `
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border: 1px solid rgba(255, 107, 66, 0.3);
                border-radius: 12px;
                padding: 24px;
                width: 90%;
                max-width: 900px;
                max-height: 90vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                animation: slideIn 0.3s ease;
            `;

            // Get master file name from item - truncate if too long
            const masterFileName = item?.master?.name || 'Master File';
            const truncatedMaster = masterFileName.length > 60 ? masterFileName.substring(0, 57) + '...' : masterFileName;
            const totalComponents = componentOptions.length;

            dialog.innerHTML = `
                <!-- Header Section -->
                <div style="margin-bottom: 20px; border-bottom: 1px solid rgba(255, 107, 66, 0.2); padding-bottom: 16px;">
                    <h3 style="margin: 0 0 10px 0; color: #ff6b42; font-size: 18px; display: flex; align-items: center; gap: 10px; font-weight: 600;">
                        <i class="fas fa-layer-group"></i>
                        ${title}
                    </h3>
                    <div style="display: flex; align-items: center; gap: 16px; font-size: 12px; color: #94a3b8; flex-wrap: wrap;">
                        <div style="display: flex; align-items: center; gap: 6px; max-width: 100%; overflow: hidden;" title="${masterFileName}">
                            <i class="fas fa-file-audio" style="color: #60a5fa; flex-shrink: 0;"></i>
                            <span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${truncatedMaster}</span>
                        </div>
                        <div style="display: flex; align-items: center; gap: 6px; flex-shrink: 0;">
                            <i class="fas fa-th-list"></i>
                            <span>${totalComponents} component${totalComponents !== 1 ? 's' : ''}</span>
                        </div>
                    </div>
                </div>

                <!-- Search/Filter -->
                <div style="margin-bottom: 16px;">
                    <div style="position: relative;">
                        <i class="fas fa-search" style="position: absolute; left: 12px; top: 50%; transform: translateY(-50%); color: #64748b; font-size: 14px;"></i>
                        <input
                            type="text"
                            id="component-search"
                            placeholder="Search components (e.g., a0, a1, a2...)"
                            style="
                                width: 100%;
                                padding: 10px 12px 10px 36px;
                                background: rgba(15, 23, 42, 0.6);
                                border: 1px solid rgba(148, 163, 184, 0.3);
                                border-radius: 6px;
                                color: #e2e8f0;
                                font-size: 14px;
                                outline: none;
                                transition: all 0.2s ease;
                            "
                        >
                    </div>
                </div>

                <!-- Stacked Waveforms Preview - Compact -->
                <div id="selector-waveforms" style="margin-bottom: 14px; background: rgba(15, 23, 42, 0.5); border-radius: 6px; padding: 10px; border: 1px solid rgba(255, 107, 66, 0.2);">
                    <div class="waveform-loading" style="text-align: center; padding: 12px; color: #64748b; font-size: 12px;">
                        <i class="fas fa-spinner fa-spin"></i>
                        <span style="margin-left: 6px;">Loading waveforms...</span>
                    </div>
                </div>

                <!-- Component Grid -->
                <div class="component-options" style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; max-height: 300px; overflow-y: auto; padding-right: 8px;">
                    ${componentOptions.map((comp, index) => {
                        const confidencePercent = (comp.confidence * 100).toFixed(0);
                        const confidenceColor = comp.confidence >= 0.8 ? '#22c55e' : comp.confidence >= 0.5 ? '#f59e0b' : '#ef4444';
                        const offsetSeconds = Math.abs(comp.offset).toFixed(3);
                        const offsetSign = comp.offset >= 0 ? '+' : '-';
                        // Truncate long file names
                        const truncatedName = comp.name.length > 50 ? comp.name.substring(0, 47) + '...' : comp.name;

                        return `
                        <button class="component-option-btn" data-index="${index}" data-name="${comp.name.toLowerCase()}" data-label="${comp.label.toLowerCase()}" style="
                            display: flex;
                            flex-direction: column;
                            padding: 12px;
                            background: linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(30, 41, 59, 0.4) 100%);
                            border: 2px solid rgba(255, 107, 66, 0.2);
                            border-radius: 8px;
                            color: #e2e8f0;
                            cursor: pointer;
                            transition: all 0.2s ease;
                            text-align: left;
                            position: relative;
                            overflow: hidden;
                        ">
                            <!-- Component Label Badge -->
                            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                                <span style="
                                    display: inline-flex;
                                    align-items: center;
                                    justify-content: center;
                                    padding: 4px 10px;
                                    background: linear-gradient(135deg, #ff6b42, #dc143c);
                                    color: white;
                                    border-radius: 5px;
                                    font-weight: 700;
                                    font-size: 12px;
                                    box-shadow: 0 2px 8px rgba(255, 107, 66, 0.3);
                                ">${comp.label}</span>
                                <i class="fas fa-chevron-right" style="color: #ff6b42; opacity: 0.4; font-size: 14px;"></i>
                            </div>

                            <!-- File Name - Truncated -->
                            <div style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid rgba(148, 163, 184, 0.2);" title="${comp.name}">
                                <div style="color: #cbd5e1; font-size: 11px; line-height: 1.3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                                    ${truncatedName}
                                </div>
                            </div>

                            <!-- Metrics Grid - Compact -->
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                                <!-- Offset -->
                                <div style="background: rgba(15, 23, 42, 0.5); padding: 6px; border-radius: 5px; border: 1px solid rgba(255, 107, 66, 0.2);">
                                    <div style="font-size: 9px; color: #94a3b8; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.3px;">
                                        <i class="fas fa-clock"></i> Offset
                                    </div>
                                    <div style="font-size: 12px; font-weight: 600; color: #ff6b42;">
                                        ${comp.timecode}
                                    </div>
                                    <div style="font-size: 9px; color: #64748b; margin-top: 1px;">
                                        ${offsetSign}${offsetSeconds}s
                                    </div>
                                </div>

                                <!-- Confidence -->
                                <div style="background: rgba(15, 23, 42, 0.5); padding: 6px; border-radius: 5px; border: 1px solid ${confidenceColor}33;">
                                    <div style="font-size: 9px; color: #94a3b8; margin-bottom: 2px; text-transform: uppercase; letter-spacing: 0.3px;">
                                        <i class="fas fa-check-circle"></i> Quality
                                    </div>
                                    <div style="font-size: 12px; font-weight: 600; color: ${confidenceColor};">
                                        ${confidencePercent}%
                                    </div>
                                    <div style="font-size: 9px; color: #64748b; margin-top: 1px;">
                                        ${comp.confidence >= 0.8 ? 'Excellent' : comp.confidence >= 0.5 ? 'Good' : 'Fair'}
                                    </div>
                                </div>
                            </div>
                        </button>
                        `;
                    }).join('')}
                </div>

                <!-- Footer Actions - Compact -->
                <div style="display: flex; gap: 10px; margin-top: 16px; justify-content: flex-end; padding-top: 16px; border-top: 1px solid rgba(148, 163, 184, 0.2);">
                    <button class="cancel-btn" style="
                        padding: 10px 20px;
                        background: rgba(100, 116, 139, 0.2);
                        border: 1px solid rgba(100, 116, 139, 0.3);
                        border-radius: 6px;
                        color: #94a3b8;
                        cursor: pointer;
                        transition: all 0.2s ease;
                        font-weight: 500;
                        font-size: 13px;
                    ">
                        <i class="fas fa-times"></i> Cancel
                    </button>
                </div>
            `;

            overlay.appendChild(dialog);
            document.body.appendChild(overlay);

            // Render waveforms if item is provided
            if (item && item.componentResults) {
                setTimeout(() => {
                    this.renderSelectorWaveforms(item, componentOptions);
                }, 50);
            }

            // Search/Filter functionality
            const searchInput = dialog.querySelector('#component-search');
            const optionBtns = dialog.querySelectorAll('.component-option-btn');

            if (searchInput) {
                searchInput.addEventListener('input', (e) => {
                    const searchTerm = e.target.value.toLowerCase();

                    optionBtns.forEach(btn => {
                        const name = btn.dataset.name || '';
                        const label = btn.dataset.label || '';
                        const matches = name.includes(searchTerm) || label.includes(searchTerm);

                        btn.style.display = matches ? 'flex' : 'none';
                    });
                });

                // Focus and highlight on hover
                searchInput.addEventListener('focus', () => {
                    searchInput.style.borderColor = 'rgba(255, 107, 66, 0.5)';
                    searchInput.style.boxShadow = '0 0 0 3px rgba(255, 107, 66, 0.1)';
                });
                searchInput.addEventListener('blur', () => {
                    searchInput.style.borderColor = 'rgba(148, 163, 184, 0.3)';
                    searchInput.style.boxShadow = 'none';
                });
            }

            // Add hover effects and click handlers
            optionBtns.forEach(btn => {
                btn.addEventListener('mouseenter', () => {
                    btn.style.background = 'linear-gradient(135deg, rgba(255, 107, 66, 0.15) 0%, rgba(220, 20, 60, 0.1) 100%)';
                    btn.style.borderColor = 'rgba(255, 107, 66, 0.6)';
                    btn.style.transform = 'translateY(-2px) scale(1.02)';
                    btn.style.boxShadow = '0 8px 20px rgba(255, 107, 66, 0.2)';
                });
                btn.addEventListener('mouseleave', () => {
                    btn.style.background = 'linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(30, 41, 59, 0.4) 100%)';
                    btn.style.borderColor = 'rgba(255, 107, 66, 0.2)';
                    btn.style.transform = 'translateY(0) scale(1)';
                    btn.style.boxShadow = 'none';
                });
                btn.addEventListener('click', () => {
                    const index = parseInt(btn.dataset.index);
                    document.body.removeChild(overlay);
                    resolve(componentOptions[index]);
                });
            });

            // Cancel button
            const cancelBtn = dialog.querySelector('.cancel-btn');
            cancelBtn.addEventListener('mouseenter', () => {
                cancelBtn.style.background = 'rgba(100, 116, 139, 0.3)';
                cancelBtn.style.borderColor = 'rgba(100, 116, 139, 0.5)';
            });
            cancelBtn.addEventListener('mouseleave', () => {
                cancelBtn.style.background = 'rgba(100, 116, 139, 0.2)';
                cancelBtn.style.borderColor = 'rgba(100, 116, 139, 0.3)';
            });
            cancelBtn.addEventListener('click', () => {
                document.body.removeChild(overlay);
                resolve(null);
            });

            // Close on overlay click
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    document.body.removeChild(overlay);
                    resolve(null);
                }
            });

            // Close on Escape key
            const escapeHandler = (e) => {
                if (e.key === 'Escape') {
                    document.body.removeChild(overlay);
                    document.removeEventListener('keydown', escapeHandler);
                    resolve(null);
                }
            };
            document.addEventListener('keydown', escapeHandler);
        });
    }
}

// Additional CSS for results display
const additionalCSS = `
.results-summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 20px;
}

.result-card {
    background: #1a1a1a;
    border: 1px solid #4a5568;
    border-radius: 8px;
    padding: 16px;
    text-align: center;
}

.result-card h3 {
    color: #a0aec0;
    margin-bottom: 8px;
    font-size: 0.9rem;
}

.result-value {
    font-size: 1.8rem;
    font-weight: bold;
    margin-bottom: 4px;
}

.result-value.good { color: #38a169; }
.result-value.warning { color: #fbb040; }
.result-value.critical { color: #f56565; }

.result-detail {
    color: #a0aec0;
    font-size: 0.85rem;
}

/* Enhanced sync offset display */
.sync-offset .result-detail {
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.offset-ms {
    font-weight: 500;
}

.offset-frames {
    font-size: 0.75rem;
    color: #718096;
    font-family: 'Courier New', monospace;
    line-height: 1.2;
}

.confidence-bar {
    width: 100%;
    height: 6px;
    background: #4a5568;
    border-radius: 3px;
    overflow: hidden;
    margin-top: 8px;
}

.confidence-fill {
    height: 100%;
    background: linear-gradient(90deg, #38a169, #48bb78);
    transition: width 0.3s ease;
}

.recommendations {
    background: #1a1a1a;
    border: 1px solid #4a5568;
    border-radius: 8px;
    padding: 16px;
}

.recommendations h3 {
    color: #e2e8f0;
    margin-bottom: 12px;
}

.recommendation {
    padding: 8px 12px;
    margin-bottom: 8px;
    background: #2d3748;
    border-radius: 6px;
    border-left: 4px solid #38a169;
}

.status-dot.analyzing {
    background: #fbb040;
}

.status-dot.ready {
    background: #38a169;
}

.status-dot.error {
    background: #f56565;
}

.status-dot.warning {
    background: #fbb040;
}

/* Expand button styles */
.expand-btn {
    background: transparent;
    border: 1px solid #4a5568;
    border-radius: 4px;
    color: #a0aec0;
    padding: 4px 8px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: all 0.2s ease;
}

.expand-btn:hover:not(:disabled) {
    background: #4a5568;
    color: #e2e8f0;
    border-color: #718096;
}

.expand-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
}

.expand-btn i {
    transition: transform 0.2s ease;
}

.expand-btn.expanded i {
    transform: rotate(90deg);
}

/* Extra compact repair buttons */
.batch-repair-controls .repair-btn {
    padding: 4px 8px;
    font-size: 0.7rem;
    min-width: auto;
    height: 24px;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    white-space: nowrap;
    line-height: 1;
}

.batch-repair-controls .repair-buttons {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

.batch-repair-controls h3 {
    font-size: 0.9rem;
    margin-bottom: 6px;
}

/* Waveform Visualization Styles */
.waveform-visualization {
    margin: 20px 0;
    background: #1a1a1a;
    border: 1px solid #4a5568;
    border-radius: 8px;
    overflow: hidden;
}

.waveform-visualization h3 {
    background: #4a5568;
    color: #e2e8f0;
    padding: 10px 16px;
    margin: 0;
    font-size: 1rem;
    border-bottom: 1px solid #718096;
}

.waveform-visualization h3 i {
    color: #38a169;
    margin-right: 8px;
}

.waveform-container {
    padding: 16px;
}

.waveform-controls {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 16px;
    flex-wrap: wrap;
}

.waveform-btn {
    padding: 6px 12px;
    font-size: 0.8rem;
    background: #2d3748;
    border: 1px solid #4a5568;
    color: #e2e8f0;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s ease;
}

.waveform-btn:hover {
    background: #4a5568;
    border-color: #718096;
}

.offset-display {
    color: #fbb040;
    font-weight: bold;
    font-size: 0.9rem;
    margin-left: auto;
}

.waveform-display {
    position: relative;
    background: #0d1117;
    border: 1px solid #21262d;
    border-radius: 6px;
    min-height: 200px;
}

.waveform-track {
    display: flex;
    align-items: center;
    padding: 12px;
    border-bottom: 1px solid #21262d;
}

.waveform-track:last-child {
    border-bottom: none;
}

.track-label {
    width: 60px;
    color: #a0aec0;
    font-size: 0.9rem;
    font-weight: bold;
}

.waveform-canvas {
    flex: 1;
    height: 80px;
    background: linear-gradient(to right, #1a1a1a 0%, #2d3748 50%, #1a1a1a 100%);
    border: 1px solid #4a5568;
    border-radius: 4px;
    position: relative;
    overflow: hidden;
}

.waveform-placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #718096;
    font-size: 0.8rem;
}

.waveform-placeholder i {
    font-size: 1.5rem;
    margin-bottom: 4px;
    color: #4a5568;
}

.sync-indicator {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 2px;
    pointer-events: none;
}

.sync-line {
    width: 2px;
    height: 100%;
    background: #f56565;
    box-shadow: 0 0 4px rgba(245, 101, 101, 0.5);
}

.sync-label {
    position: absolute;
    top: -20px;
    left: -15px;
    background: #f56565;
    color: white;
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 0.7rem;
    white-space: nowrap;
}

.master-track .waveform-canvas {
    background: linear-gradient(to right, #1a1a1a 0%, #38a169 20%, #38a169 80%, #1a1a1a 100%);
}

.dub-track .sync-before .waveform-canvas,
.dub-track .sync-before {
    background: linear-gradient(to right, #1a1a1a 0%, #fbb040 20%, #fbb040 80%, #1a1a1a 100%);
}

.dub-track .sync-after {
    background: linear-gradient(to right, #1a1a1a 0%, #38a169 20%, #38a169 80%, #1a1a1a 100%);
}

/* JSON Analysis Data Styles */
.analysis-json-data {
    margin-top: 20px;
    background: #1a1a1a;
    border: 1px solid #4a5568;
    border-radius: 8px;
    overflow: hidden;
}

.analysis-json-data h3 {
    background: #4a5568;
    color: #e2e8f0;
    padding: 10px 16px;
    margin: 0;
    font-size: 1rem;
    border-bottom: 1px solid #718096;
}

.analysis-json-data h3 i {
    color: #38a169;
    margin-right: 8px;
}

.json-container {
    max-height: 300px;
    overflow-y: auto;
    background: #0d1117;
}

.json-display {
    color: #e6edf3;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 0.85rem;
    line-height: 1.4;
    margin: 0;
    padding: 16px;
    white-space: pre-wrap;
    word-wrap: break-word;
    background: #0d1117;
    border: none;
}

/* JSON Syntax Highlighting */
.json-display {
    color: #e6edf3;
}

.json-container::-webkit-scrollbar {
    width: 8px;
}

.json-container::-webkit-scrollbar-track {
    background: #21262d;
}

.json-container::-webkit-scrollbar-thumb {
    background: #4a5568;
    border-radius: 4px;
}

.json-container::-webkit-scrollbar-thumb:hover {
    background: #718096;
}
`;

// Inject additional CSS
const style = document.createElement('style');
style.textContent = additionalCSS;
document.head.appendChild(style);





document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Loading SyncAnalyzerUI v2.0 with compact repair buttons and JSON data display');
    window.app = new SyncAnalyzerUI();
    // Global helper for non-UI modules
    window.showToast = (level, msg, title) => window.app?.showToast(level, msg, title);
});

