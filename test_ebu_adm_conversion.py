#!/usr/bin/env python3
"""Test ADM rendering with EBU ADM Toolbox"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from sync_analyzer.dolby.atmos_converter import convert_atmos_to_mp4
import tempfile

def test_ebu_adm_rendering():
    input_file = '/mnt/data/amcmurray/_outofsync_master_files/WonderWoman_Trailer_Dub_Master_out_of_sync_8_7.wav'
    output_mp4 = tempfile.mktemp(suffix='.mp4', prefix='atmos_ebu_test_')
    
    print('🎬 Testing ADM rendering with EBU ADM Toolbox...')
    print(f'Input:  {input_file}')
    print(f'Output: {output_mp4}')
    print()
    
    result = convert_atmos_to_mp4(input_file, output_mp4, fps=24.0)
    
    if result:
        print(f'\n✅ SUCCESS!')
        print(f'MP4 created: {result["mp4_path"]}')
        
        import os
        if os.path.exists(result['mp4_path']):
            size_mb = os.path.getsize(result['mp4_path']) / (1024*1024)
            print(f'File size: {size_mb:.2f} MB')
            print(f'Metadata: {result["metadata"].bed_configuration}, {result["metadata"].channels} channels')
            
            # Test extraction
            print('\n🔊 Testing audio extraction...')
            test_extract = tempfile.mktemp(suffix='.wav', prefix='extracted_')
            import subprocess
            extract_cmd = [
                'ffmpeg', '-i', result['mp4_path'], '-vn',
                '-ar', '22050', '-ac', '1', '-acodec', 'pcm_s16le',
                '-y', test_extract
            ]
            subprocess.run(extract_cmd, capture_output=True)
            
            if os.path.exists(test_extract):
                extract_size = os.path.getsize(test_extract) / (1024*1024)
                print(f'✅ Extracted mono 22050Hz WAV: {extract_size:.2f} MB')
                print('✅ Ready for sync analysis!')
            else:
                print('❌ Extraction failed')
    else:
        print('\n❌ Conversion failed')
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(test_ebu_adm_rendering())

