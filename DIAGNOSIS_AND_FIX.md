# Diagnosis: 115s Offset Issue

## What's Wrong

1. **False Peak Detection**: The algorithm analyzes the ENTIRE file (45+ minutes) and finds a correlation peak at 115s, but this is matching similar audio content later in the file, not the actual sync point.

2. **Correct Peak Found**: When analyzing just the first 300 seconds, the algorithm correctly finds the peak at ~31s.

3. **SmartVerifier Not Catching It**: A 115s offset only triggers 25% severity (needs 30% to verify), so false peaks aren't being caught.

4. **Low Peak Prominence**: The correlation peak ratio is only 1.00x (top peak vs second peak), which means multiple peaks are equally strong - this is a red flag for false peaks.

## The Correct Approach

### Option 1: Limit Correlation Window (RECOMMENDED)
Instead of correlating the entire file, limit to the first portion:
- Analyze first 2-5 minutes of both files
- This finds the true sync point (program start)
- Avoids false peaks from similar content later in the file

### Option 2: Use Multiple Anchor Points
- Find multiple correlation peaks in different sections
- Use the one closest to the start of the file
- Verify consistency across anchors

### Option 3: Improve Peak Validation
- Check peak prominence ratio (should be >2.0x)
- Reject peaks with low prominence
- Try alternative search if primary peak fails validation

## The Fix Plan

1. **Limit correlation window** to first 2-5 minutes (most important)
2. **Add peak prominence validation** - reject peaks with ratio <2.0x
3. **Lower SmartVerifier threshold** - require verification for offsets >30s
4. **Add sanity checks** - reject offsets >50% of file duration

## Why This Happens

Long files (45+ minutes) often have:
- Similar audio patterns repeated throughout
- Music, dialogue, or sound effects that repeat
- The algorithm finds a strong correlation later in the file (115s) that's actually just similar content, not the sync point

The true sync point is usually near the start (after bars/tone), which is why limiting to the first few minutes works better.
