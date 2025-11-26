#!/usr/bin/env python3
"""Inspect ADM WAV file channel layout to find the correct bed channels"""
import sys
import wave
import subprocess
import tempfile
from pathlib import Path

def inspect_adm_file(adm_file):
    """Inspect ADM file and test different channel combinations"""
    print("=" * 70)
    print("🔍 ADM Channel Layout Inspector")
    print("=" * 70)
    print(f"File: {adm_file}")
    print()
    
    # Get basic info
    with wave.open(adm_file, 'rb') as wav:
        params = wav.getparams()
        print(f"Total channels: {params.nchannels}")
        print(f"Sample rate: {params.framerate} Hz")
        print(f"Duration: {params.nframes / params.framerate:.2f} seconds")
        print()
    
    # Test different channel pairs
    channel_pairs_to_test = [
        (0, 1, "Channels 1-2 (first pair)"),
        (2, 3, "Channels 3-4 (second pair)"),
        (4, 5, "Channels 5-6 (third pair)"),
        (6, 7, "Channels 7-8 (fourth pair)"),
        (8, 9, "Channels 9-10 (fifth pair)"),
    ]
    
    print("🧪 Testing different channel pairs...")
    print("=" * 70)
    
    results = []
    
    for ch1_idx, ch2_idx, description in channel_pairs_to_test:
        if ch1_idx >= params.nchannels or ch2_idx >= params.nchannels:
            continue
        
        print(f"\n📊 {description}")
        
        # Extract this pair
        output_file = tempfile.mktemp(suffix='.wav', prefix=f'test_ch{ch1_idx}_{ch2_idx}_')
        
        try:
            with wave.open(adm_file, 'rb') as wav_in:
                frames = wav_in.readframes(params.nframes)
                bytes_per_sample = params.sampwidth
                total_channels = params.nchannels
                frame_size = bytes_per_sample * total_channels
                
                # Extract specified channels
                stereo_data = bytearray()
                for i in range(0, len(frames), frame_size):
                    offset1 = i + (ch1_idx * bytes_per_sample)
                    offset2 = i + (ch2_idx * bytes_per_sample)
                    ch1 = frames[offset1:offset1+bytes_per_sample]
                    ch2 = frames[offset2:offset2+bytes_per_sample]
                    stereo_data.extend(ch1)
                    stereo_data.extend(ch2)
                
                with wave.open(output_file, 'wb') as wav_out:
                    wav_out.setnchannels(2)
                    wav_out.setsampwidth(params.sampwidth)
                    wav_out.setframerate(params.framerate)
                    wav_out.writeframes(bytes(stereo_data))
            
            # Check RMS levels
            cmd = [
                'ffmpeg', '-i', output_file, '-af', 
                'astats=metadata=1:reset=1', '-f', 'null', '-'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            # Parse RMS from output
            rms_values = []
            for line in result.stderr.split('\n'):
                if 'RMS level' in line or 'RMS peak' in line:
                    rms_values.append(line.strip())
            
            if rms_values:
                print(f"   Audio levels detected:")
                for rms in rms_values[:4]:
                    print(f"   {rms}")
                results.append((ch1_idx, ch2_idx, description, "✅ Has audio"))
            else:
                print(f"   ⚠️  Low/no audio detected")
                results.append((ch1_idx, ch2_idx, description, "❌ Silent/low"))
            
            # Clean up
            Path(output_file).unlink()
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append((ch1_idx, ch2_idx, description, f"❌ Error: {e}"))
    
    # Summary
    print("\n" + "=" * 70)
    print("📋 SUMMARY")
    print("=" * 70)
    for ch1, ch2, desc, status in results:
        print(f"{desc}: {status}")
    
    print("\n" + "=" * 70)
    print("💡 RECOMMENDATION")
    print("=" * 70)
    
    # Find first pair with audio
    for ch1, ch2, desc, status in results:
        if "✅" in status:
            print(f"✅ Use channels {ch1+1}-{ch2+1} for sync analysis")
            print(f"   (Array indices: {ch1}, {ch2})")
            print()
            print("To update the code:")
            print(f"   In atmos_converter.py, change:")
            print(f"   ch1 = frames[i:i+bytes_per_sample]")
            print(f"   ch2 = frames[i+bytes_per_sample:i+2*bytes_per_sample]")
            print()
            print(f"   To:")
            print(f"   offset1 = i + ({ch1} * bytes_per_sample)")
            print(f"   offset2 = i + ({ch2} * bytes_per_sample)")
            print(f"   ch1 = frames[offset1:offset1+bytes_per_sample]")
            print(f"   ch2 = frames[offset2:offset2+bytes_per_sample]")
            return ch1, ch2
    
    print("❌ No suitable channel pair found!")
    print("   The ADM file might need proper ADM rendering")
    return None, None

if __name__ == '__main__':
    adm_file = '/mnt/data/amcmurray/_outofsync_master_files/WonderWoman_Trailer_Dub_Master_out_of_sync_8_7.wav'
    
    if len(sys.argv) > 1:
        adm_file = sys.argv[1]
    
    inspect_adm_file(adm_file)

