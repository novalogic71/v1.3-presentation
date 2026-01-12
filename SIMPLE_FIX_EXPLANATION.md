# Simple Fix Explanation

## The Problem (In Plain English)

Your files are 45+ minutes long. The algorithm tries to find where the audio syncs by comparing the ENTIRE file. But long files have similar audio patterns repeated throughout (music, dialogue, etc.), so it finds a "match" at 115 seconds that's actually just similar content, not the real sync point.

When we test just the first 300 seconds, it correctly finds ~31 seconds - that's the real sync point!

## The Fix (Simple Version)

**Limit the analysis to the first 2-5 minutes of audio** instead of the entire file. This:
- Finds the true sync point (near the start, after bars/tone)
- Avoids false peaks from similar content later
- Works faster
- More reliable

## Where to Make the Change

In `sync_analyzer/core/audio_sync_detector.py`, in the `analyze_sync()` method around line 967-989:

**BEFORE** (current - analyzes entire file):
```python
master_audio, _ = self.load_and_preprocess_audio(master_path)
dub_audio, _ = self.load_and_preprocess_audio(dub_path)
# ... then extracts features from entire audio
master_features = self.extract_audio_features(master_audio_for_analysis)
dub_features = self.extract_audio_features(dub_audio)
```

**AFTER** (fixed - limits to first 5 minutes):
```python
master_audio, _ = self.load_and_preprocess_audio(master_path)
dub_audio, _ = self.load_and_preprocess_audio(dub_path)

# LIMIT to first 5 minutes to avoid false peaks
MAX_ANALYSIS_DURATION = 300  # 5 minutes in seconds
master_samples_limit = int(MAX_ANALYSIS_DURATION * self.sample_rate)
dub_samples_limit = int(MAX_ANALYSIS_DURATION * self.sample_rate)

if len(master_audio_for_analysis) > master_samples_limit:
    master_audio_for_analysis = master_audio_for_analysis[:master_samples_limit]
    logger.info(f"Limited master audio to first {MAX_ANALYSIS_DURATION}s for correlation")
    
if len(dub_audio) > dub_samples_limit:
    dub_audio = dub_audio[:dub_samples_limit]
    logger.info(f"Limited dub audio to first {MAX_ANALYSIS_DURATION}s for correlation")

# Now extract features from limited audio
master_features = self.extract_audio_features(master_audio_for_analysis)
dub_features = self.extract_audio_features(dub_audio)
```

## Why This Works

1. **Sync points are near the start**: After bars/tone, the program content starts - that's where sync matters
2. **Avoids false matches**: Later in the file, similar audio patterns confuse the algorithm
3. **Faster**: Less audio to process
4. **More accurate**: Your test showed ~31s is correct when analyzing first 300s

## Additional Improvements Needed

1. **Add peak prominence check**: Reject peaks where top peak is <2x stronger than second peak
2. **Lower SmartVerifier threshold**: Require verification for offsets >30s (currently needs 30% severity, 115s only gets 25%)
3. **Add sanity check**: Reject offsets >50% of file duration

But the MAIN fix is limiting correlation to the first portion of files.
