/**
 * Waveform Cache using IndexedDB
 * Caches extracted waveform peaks to avoid re-extraction
 * LRU eviction at 50MB limit
 */

class WaveformCache {
    constructor() {
        this.dbName = 'SyncDubWaveformCache';
        this.storeName = 'waveforms';
        this.version = 1;
        this.db = null;
        this.maxSizeBytes = 50 * 1024 * 1024; // 50MB
        this.initialized = false;
        this.initPromise = this.init();
    }

    /**
     * Initialize IndexedDB
     */
    async init() {
        if (this.initialized) return;

        return new Promise((resolve, reject) => {
            const request = indexedDB.open(this.dbName, this.version);

            request.onerror = () => {
                console.error('Failed to open IndexedDB:', request.error);
                reject(request.error);
            };

            request.onsuccess = () => {
                this.db = request.result;
                this.initialized = true;
                console.log('WaveformCache initialized');
                resolve();
            };

            request.onupgradeneeded = (event) => {
                const db = event.target.result;

                // Create object store with composite key (filePath + peaksPerSecond)
                if (!db.objectStoreNames.contains(this.storeName)) {
                    const store = db.createObjectStore(this.storeName, { keyPath: 'cacheKey' });

                    // Index for LRU eviction (last accessed time)
                    store.createIndex('lastAccessed', 'lastAccessed', { unique: false });

                    // Index for file path lookups
                    store.createIndex('filePath', 'filePath', { unique: false });

                    console.log('Created waveform cache object store');
                }
            };
        });
    }

    /**
     * Generate cache key from file path and extraction parameters
     */
    generateCacheKey(filePath, peaksPerSecond = 100) {
        // Use file path + peaks per second as key
        // In production, could add file hash or modification time
        return `waveform:${filePath}:${peaksPerSecond}`;
    }

    /**
     * Get waveform data from cache
     * @param {string} filePath - Path to audio file
     * @param {number} peaksPerSecond - Peaks per second (default 100)
     * @returns {Promise<object|null>} Waveform data or null if not cached
     */
    async get(filePath, peaksPerSecond = 100) {
        try {
            await this.initPromise;
            if (!this.db) return null;

            const cacheKey = this.generateCacheKey(filePath, peaksPerSecond);

            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction([this.storeName], 'readwrite');
                const store = transaction.objectStore(this.storeName);
                const request = store.get(cacheKey);

                request.onsuccess = () => {
                    const result = request.result;

                    if (result) {
                        // Update last accessed time for LRU
                        result.lastAccessed = Date.now();
                        store.put(result);

                        // Convert stored arrays back to Float32Array
                        const waveformData = {
                            peaks: new Float32Array(result.peaks),
                            rms: new Float32Array(result.rms),
                            duration: result.duration,
                            sampleRate: result.sampleRate,
                            samplesPerPixel: result.samplesPerPixel,
                            width: result.width,
                            originalLength: result.originalLength,
                            cached: true
                        };

                        console.log(`Cache HIT for ${filePath} (${cacheKey})`);
                        resolve(waveformData);
                    } else {
                        console.log(`Cache MISS for ${filePath} (${cacheKey})`);
                        resolve(null);
                    }
                };

                request.onerror = () => {
                    console.warn('Cache read error:', request.error);
                    resolve(null); // Don't fail, just return cache miss
                };
            });
        } catch (error) {
            console.warn('Cache get error:', error);
            return null;
        }
    }

    /**
     * Store waveform data in cache
     * @param {string} filePath - Path to audio file
     * @param {object} waveformData - Waveform data to cache
     * @param {number} peaksPerSecond - Peaks per second (default 100)
     */
    async set(filePath, waveformData, peaksPerSecond = 100) {
        try {
            await this.initPromise;
            if (!this.db) return;

            const cacheKey = this.generateCacheKey(filePath, peaksPerSecond);

            // Calculate size (rough estimate)
            const peaksSize = waveformData.peaks.byteLength;
            const rmsSize = waveformData.rms.byteLength;
            const metadataSize = 200; // Rough estimate for metadata
            const entrySize = peaksSize + rmsSize + metadataSize;

            // Check if we need to evict entries
            await this.evictIfNeeded(entrySize);

            // Store waveform data
            const cacheEntry = {
                cacheKey: cacheKey,
                filePath: filePath,
                peaksPerSecond: peaksPerSecond,
                peaks: Array.from(waveformData.peaks), // Convert Float32Array to regular array for storage
                rms: Array.from(waveformData.rms),
                duration: waveformData.duration,
                sampleRate: waveformData.sampleRate,
                samplesPerPixel: waveformData.samplesPerPixel,
                width: waveformData.width,
                originalLength: waveformData.originalLength,
                size: entrySize,
                lastAccessed: Date.now(),
                createdAt: Date.now()
            };

            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction([this.storeName], 'readwrite');
                const store = transaction.objectStore(this.storeName);
                const request = store.put(cacheEntry);

                request.onsuccess = () => {
                    console.log(`Cached waveform for ${filePath} (${(entrySize / 1024).toFixed(1)}KB)`);
                    resolve();
                };

                request.onerror = () => {
                    console.warn('Cache write error:', request.error);
                    resolve(); // Don't fail the overall operation
                };
            });
        } catch (error) {
            console.warn('Cache set error:', error);
        }
    }

    /**
     * Evict least recently used entries if needed
     * @param {number} requiredSpace - Bytes needed for new entry
     */
    async evictIfNeeded(requiredSpace) {
        try {
            const currentSize = await this.getTotalSize();

            if (currentSize + requiredSpace <= this.maxSizeBytes) {
                return; // No eviction needed
            }

            console.log(`Cache eviction needed: ${(currentSize / 1024 / 1024).toFixed(1)}MB + ${(requiredSpace / 1024).toFixed(1)}KB > ${(this.maxSizeBytes / 1024 / 1024).toFixed(1)}MB`);

            // Get all entries sorted by last accessed (oldest first)
            const entries = await this.getAllEntriesSorted();

            let freedSpace = 0;
            const toDelete = [];

            // Evict oldest entries until we have enough space
            for (const entry of entries) {
                if (currentSize - freedSpace + requiredSpace <= this.maxSizeBytes) {
                    break;
                }
                toDelete.push(entry.cacheKey);
                freedSpace += entry.size;
            }

            // Delete entries
            if (toDelete.length > 0) {
                await this.deleteEntries(toDelete);
                console.log(`Evicted ${toDelete.length} entries, freed ${(freedSpace / 1024 / 1024).toFixed(1)}MB`);
            }
        } catch (error) {
            console.warn('Eviction error:', error);
        }
    }

    /**
     * Get total cache size
     */
    async getTotalSize() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.storeName], 'readonly');
            const store = transaction.objectStore(this.storeName);
            const request = store.getAll();

            request.onsuccess = () => {
                const entries = request.result;
                const totalSize = entries.reduce((sum, entry) => sum + (entry.size || 0), 0);
                resolve(totalSize);
            };

            request.onerror = () => {
                console.warn('Failed to get cache size:', request.error);
                resolve(0);
            };
        });
    }

    /**
     * Get all entries sorted by last accessed (oldest first)
     */
    async getAllEntriesSorted() {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.storeName], 'readonly');
            const store = transaction.objectStore(this.storeName);
            const index = store.index('lastAccessed');
            const request = index.getAll();

            request.onsuccess = () => {
                resolve(request.result);
            };

            request.onerror = () => {
                console.warn('Failed to get sorted entries:', request.error);
                resolve([]);
            };
        });
    }

    /**
     * Delete multiple cache entries
     */
    async deleteEntries(cacheKeys) {
        return new Promise((resolve, reject) => {
            const transaction = this.db.transaction([this.storeName], 'readwrite');
            const store = transaction.objectStore(this.storeName);

            for (const key of cacheKeys) {
                store.delete(key);
            }

            transaction.oncomplete = () => {
                resolve();
            };

            transaction.onerror = () => {
                console.warn('Failed to delete entries:', transaction.error);
                resolve(); // Don't fail
            };
        });
    }

    /**
     * Clear entire cache
     */
    async clear() {
        try {
            await this.initPromise;
            if (!this.db) return;

            return new Promise((resolve, reject) => {
                const transaction = this.db.transaction([this.storeName], 'readwrite');
                const store = transaction.objectStore(this.storeName);
                const request = store.clear();

                request.onsuccess = () => {
                    console.log('Waveform cache cleared');
                    resolve();
                };

                request.onerror = () => {
                    console.warn('Failed to clear cache:', request.error);
                    resolve();
                };
            });
        } catch (error) {
            console.warn('Cache clear error:', error);
        }
    }

    /**
     * Get cache statistics
     */
    async getStats() {
        try {
            await this.initPromise;
            if (!this.db) {
                return { enabled: false };
            }

            const transaction = this.db.transaction([this.storeName], 'readonly');
            const store = transaction.objectStore(this.storeName);

            return new Promise((resolve, reject) => {
                const request = store.getAll();

                request.onsuccess = () => {
                    const entries = request.result;
                    const totalSize = entries.reduce((sum, entry) => sum + (entry.size || 0), 0);

                    resolve({
                        enabled: true,
                        entryCount: entries.length,
                        totalSizeBytes: totalSize,
                        totalSizeMB: (totalSize / 1024 / 1024).toFixed(2),
                        maxSizeMB: (this.maxSizeBytes / 1024 / 1024).toFixed(0),
                        usage: ((totalSize / this.maxSizeBytes) * 100).toFixed(1) + '%'
                    });
                };

                request.onerror = () => {
                    resolve({ enabled: false, error: request.error });
                };
            });
        } catch (error) {
            return { enabled: false, error: error.message };
        }
    }
}

// Create global singleton instance
window.WaveformCache = WaveformCache;
window.waveformCache = new WaveformCache();
