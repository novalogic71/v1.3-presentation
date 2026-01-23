/**
 * Repair API Service
 * Handles FFmpeg-based repair operations via the FastAPI backend
 */

import { 
  StandardRepairRequest, 
  PerChannelRepairRequest, 
  RepairResponse,
  PerChannelResults 
} from '../types';

// API base URL - defaults to same origin
const API_BASE = '/api/v1';

/**
 * Apply a standard (single offset) repair to the dub file
 * Used for standard analysis mode
 */
export async function applyStandardRepair(
  filePath: string,
  offsetSeconds: number,
  outputPath?: string,
  keepDuration: boolean = true
): Promise<RepairResponse> {
  const request: StandardRepairRequest = {
    file_path: filePath,
    offset_seconds: offsetSeconds,
    output_path: outputPath,
    keep_duration: keepDuration,
  };

  try {
    const response = await fetch(`${API_BASE}/repair/standard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Repair failed: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Standard repair error:', error);
    throw error;
  }
}

/**
 * Apply per-channel repair to the dub file
 * Used for componentized analysis mode
 */
export async function applyPerChannelRepair(
  filePath: string,
  perChannelResults: PerChannelResults,
  outputPath?: string,
  keepDuration: boolean = true
): Promise<RepairResponse> {
  const request: PerChannelRepairRequest = {
    file_path: filePath,
    per_channel_results: perChannelResults,
    output_path: outputPath,
    keep_duration: keepDuration,
  };

  try {
    const response = await fetch(`${API_BASE}/repair/per-channel`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Per-channel repair failed: ${response.status}`);
    }

    return await response.json();
  } catch (error) {
    console.error('Per-channel repair error:', error);
    throw error;
  }
}

/**
 * Calculate adjusted offsets from track positions in the waveform editor
 * The master track (index 0) is the reference, so its offset is always 0
 * Dub tracks have their offset calculated based on their clip positions
 * 
 * @param tracks - Array of track objects with name and clips
 * @param _originalOffsets - Original per-channel offsets (reserved for future use)
 * @param _detectedOffset - Original detected offset (reserved for future use)
 */
export function calculateAdjustedOffsets(
  tracks: Array<{ name: string; clips: Array<{ startTime: number }> }>,
  _originalOffsets: PerChannelResults | null,
  _detectedOffset: number = 0
): PerChannelResults {
  const adjustedOffsets: PerChannelResults = {};

  // Skip the first track (master) and process dub tracks
  tracks.forEach((track, index) => {
    if (index === 0) return; // Skip master track

    const trackName = track.name;
    const clipStartTime = track.clips?.[0]?.startTime || 0;
    
    // The adjusted offset is the clip's start position
    // If the clip was moved from its original position, this represents the new offset
    // Positive startTime = clip starts later (add delay)
    // Zero startTime = no offset adjustment
    const adjustedOffset = clipStartTime;

    // Try to match the track name to a channel role
    // Common patterns: a0, a1, FL, FR, S0, S1, Component 1, etc.
    const channelRole = extractChannelRole(trackName);
    
    adjustedOffsets[channelRole] = {
      offset_seconds: adjustedOffset,
      confidence: 1.0, // User-adjusted = full confidence
    };
  });

  return adjustedOffsets;
}

/**
 * Extract channel role from track name
 */
function extractChannelRole(trackName: string): string {
  // Try to extract component name like a0, a1, etc.
  const componentMatch = trackName.match(/[_\-\s](a\d+)/i);
  if (componentMatch) {
    return componentMatch[1].toLowerCase();
  }

  // Try to extract stream index like S0, S1, etc.
  const streamMatch = trackName.match(/[_\-\s]?S(\d+)/i);
  if (streamMatch) {
    return `S${streamMatch[1]}`;
  }

  // Try channel names like FL, FR, etc.
  const channelMatch = trackName.match(/\b(FL|FR|FC|LFE|SL|SR|BL|BR|c\d+)\b/i);
  if (channelMatch) {
    return channelMatch[1].toUpperCase();
  }

  // Fall back to cleaned track name
  return trackName.replace(/[^a-zA-Z0-9]/g, '_').substring(0, 20);
}

/**
 * Generate default output path for repaired file
 */
export function generateOutputPath(inputPath: string, suffix: string = '_repaired'): string {
  const lastDotIndex = inputPath.lastIndexOf('.');
  const baseName = lastDotIndex > 0 ? inputPath.substring(0, lastDotIndex) : inputPath;
  const extension = lastDotIndex > 0 ? inputPath.substring(lastDotIndex) : '';
  return `${baseName}${suffix}${extension}`;
}

/**
 * Check if the repair mode should be per-channel or standard
 */
export function isPerChannelMode(syncData: {
  components?: Array<unknown>;
  componentResults?: Array<unknown>;
  perChannel?: PerChannelResults | null;
}): boolean {
  return !!(
    (syncData.components && syncData.components.length > 0) ||
    (syncData.componentResults && syncData.componentResults.length > 0) ||
    syncData.perChannel
  );
}
