/**
 * Type definitions for QC Interface
 */

export interface SyncData {
  masterUrl?: string;
  dubUrl?: string;
  masterFile?: string;
  dubFile?: string;
  masterPath?: string;  // Full path for FFmpeg repair
  dubPath?: string;     // Full path for FFmpeg repair
  detectedOffset?: number;
  confidence?: number;
  analysisId?: string;
  analysis_id?: string;
  frameRate?: number;
  components?: ComponentData[];
  componentResults?: ComponentData[];
  timeline?: any[];
  operatorTimeline?: any;
  operator_timeline?: any;
  perChannel?: PerChannelResults | null;  // Per-channel results for componentized repair
}

export interface ComponentData {
  dubUrl?: string;
  dub_url?: string;
  audioUrl?: string;
  name?: string;
  path?: string;        // Full path for FFmpeg repair
  dubFile?: string;
  dub_file?: string;
  detectedOffset?: number;
  detected_offset?: number;
  offset?: number;
  offset_seconds?: number;
  confidence?: number;
}

export interface PerChannelResults {
  [channelRole: string]: {
    offset_seconds: number;
    confidence?: number;
  };
}

/**
 * Repair request types for FFmpeg backend
 */
export interface StandardRepairRequest {
  file_path: string;
  offset_seconds: number;
  output_path?: string;
  keep_duration?: boolean;
}

export interface PerChannelRepairRequest {
  file_path: string;
  per_channel_results: PerChannelResults;
  output_path?: string;
  keep_duration?: boolean;
}

export interface RepairResponse {
  success: boolean;
  output_file?: string;
  output_size?: number;
  keep_duration?: boolean;
  error?: string;
}
