#!/usr/bin/env python3
"""Debug ADM processing pipeline to find the issue"""
import sys
import os
import subprocess
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

def check_eat_process():
    """Check if eat-process is available and working"""
    print("=" * 60)
    print("🔍 Step 1: Checking eat-process availability")
    print("=" * 60)
    
    result = subprocess.run(['which', 'eat-process'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ eat-process found: {result.stdout.strip()}")
    else:
        print(f"❌ eat-process NOT in PATH")
        return False
    
    result = subprocess.run(['eat-process', '--help'], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✅ eat-process is executable")
        return True
    else:
        print(f"❌ eat-process failed: {result.stderr}")
        return False

def test_adm_rendering():
    """Test ADM rendering with eat-process"""
    print("\n" + "=" * 60)
    print("🎬 Step 2: Testing ADM rendering")
    print("=" * 60)
    
    adm_file = '/mnt/data/amcmurray/_outofsync_master_files/WonderWoman_Trailer_Dub_Master_out_of_sync_8_7.wav'
    config_file = '/mnt/data/amcmurray/Sync_dub/v1.3-presentation/sync_analyzer/dolby/adm_render_config.json'
    output_file = tempfile.mktemp(suffix='.wav', prefix='debug_adm_rendered_')
    
    print(f"Input:  {adm_file}")
    print(f"Config: {config_file}")
    print(f"Output: {output_file}")
    print()
    
    # Check input file
    if not os.path.exists(adm_file):
        print(f"❌ Input file not found!")
        return None
    
    file_size_mb = os.path.getsize(adm_file) / (1024*1024)
    print(f"✅ Input file exists: {file_size_mb:.2f} MB")
    
    # Check config
    if not os.path.exists(config_file):
        print(f"❌ Config file not found!")
        return None
    print(f"✅ Config file exists")
    
    # Run eat-process
    cmd = [
        'eat-process',
        config_file,
        '-o', 'input.path', adm_file,
        '-o', 'output.path', output_file
    ]
    
    print(f"\n🚀 Running: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print("STDOUT:")
    print(result.stdout)
    print("\nSTDERR:")
    print(result.stderr)
    print(f"\nReturn code: {result.returncode}")
    
    if result.returncode == 0 and os.path.exists(output_file):
        output_size_mb = os.path.getsize(output_file) / (1024*1024)
        print(f"\n✅ ADM rendered successfully: {output_size_mb:.2f} MB")
        
        # Check output with ffprobe
        probe_cmd = ['ffprobe', '-v', 'error', '-show_entries',
                     'stream=channels,sample_rate,duration', '-of', 'default=noprint_wrappers=1',
                     output_file]
        probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
        print(f"\nRendered file info:")
        print(probe_result.stdout)
        
        return output_file
    else:
        print(f"\n❌ ADM rendering failed!")
        return None

def test_fallback_extraction():
    """Test fallback channel extraction"""
    print("\n" + "=" * 60)
    print("🔄 Step 3: Testing fallback channel extraction")
    print("=" * 60)
    
    import wave
    
    adm_file = '/mnt/data/amcmurray/_outofsync_master_files/WonderWoman_Trailer_Dub_Master_out_of_sync_8_7.wav'
    output_file = tempfile.mktemp(suffix='.wav', prefix='debug_fallback_')
    
    try:
        with wave.open(adm_file, 'rb') as wav_in:
            params = wav_in.getparams()
            print(f"ADM WAV properties:")
            print(f"  Channels: {params.nchannels}")
            print(f"  Sample rate: {params.framerate} Hz")
            print(f"  Sample width: {params.sampwidth} bytes")
            print(f"  Frames: {params.nframes}")
            print(f"  Duration: {params.nframes / params.framerate:.2f} seconds")
            
            # Extract first 2 channels
            frames = wav_in.readframes(params.nframes)
            bytes_per_sample = params.sampwidth
            total_channels = params.nchannels
            frame_size = bytes_per_sample * total_channels
            
            print(f"\nExtracting first 2 channels (L/R)...")
            stereo_data = bytearray()
            for i in range(0, len(frames), frame_size):
                ch1 = frames[i:i+bytes_per_sample]
                ch2 = frames[i+bytes_per_sample:i+2*bytes_per_sample]
                stereo_data.extend(ch1)
                stereo_data.extend(ch2)
            
            with wave.open(output_file, 'wb') as wav_out:
                wav_out.setnchannels(2)
                wav_out.setsampwidth(params.sampwidth)
                wav_out.setframerate(params.framerate)
                wav_out.writeframes(bytes(stereo_data))
            
            output_size_mb = len(stereo_data) / (1024*1024)
            print(f"✅ Fallback extraction completed: {output_size_mb:.2f} MB")
            
            # Check output
            probe_cmd = ['ffprobe', '-v', 'error', '-show_entries',
                         'stream=channels,sample_rate,duration', '-of', 'default=noprint_wrappers=1',
                         output_file]
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
            print(f"\nExtracted file info:")
            print(probe_result.stdout)
            
            return output_file
            
    except Exception as e:
        print(f"❌ Fallback extraction failed: {e}")
        return None

def compare_audio_files(file1, file2):
    """Compare two audio files to see if they're different"""
    print("\n" + "=" * 60)
    print("🔍 Step 4: Comparing rendered vs fallback audio")
    print("=" * 60)
    
    if not file1 or not file2:
        print("❌ Can't compare - one or both files missing")
        return
    
    # Get checksums
    import hashlib
    
    with open(file1, 'rb') as f:
        hash1 = hashlib.md5(f.read()).hexdigest()
    
    with open(file2, 'rb') as f:
        hash2 = hashlib.md5(f.read()).hexdigest()
    
    print(f"EBU rendered: {hash1}")
    print(f"Fallback:     {hash2}")
    
    if hash1 == hash2:
        print("\n⚠️  FILES ARE IDENTICAL!")
        print("This means eat-process might not be working correctly")
    else:
        print("\n✅ FILES ARE DIFFERENT")
        print("EBU ADM Toolbox is producing different output (good!)")

def main():
    print("🔬 ADM PIPELINE DEBUGGING")
    print("=" * 60)
    print()
    
    # Step 1: Check eat-process
    eat_available = check_eat_process()
    
    if not eat_available:
        print("\n❌ eat-process is not available - this is the problem!")
        print("\nTo fix:")
        print("  1. Check if /mnt/data/amcmurray/eat-process exists")
        print("  2. Run: sudo ln -sf /mnt/data/amcmurray/eat-process /usr/local/bin/eat-process")
        print("  3. Test: eat-process --help")
        return 1
    
    # Step 2: Test ADM rendering
    rendered_file = test_adm_rendering()
    
    # Step 3: Test fallback
    fallback_file = test_fallback_extraction()
    
    # Step 4: Compare
    compare_audio_files(rendered_file, fallback_file)
    
    print("\n" + "=" * 60)
    print("🎯 DEBUGGING COMPLETE")
    print("=" * 60)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())

