# QC Player Migration to React + Waveform-Playlist v5

## Overview

This migration moves the QC player from vanilla JavaScript with waveform-playlist v4 to React with waveform-playlist v5.

## Current Status

✅ React infrastructure set up (Vite, TypeScript)
✅ Basic QC Interface component created
✅ Integration bridge for vanilla JS compatibility
⏳ Need to install dependencies and build
⏳ Need to integrate into app.html
⏳ Need to update existing QC interface calls

## Next Steps

1. **Install Dependencies**
   ```bash
   cd sync-dub/web_ui/react-qc
   npm install
   ```

2. **Build React App**
   ```bash
   npm run build
   ```

3. **Update app.html**
   - Add script tag to load compiled React QC component
   - Keep existing QC interface code as fallback during migration

4. **Update QC Interface Calls**
   - Replace `qcInterface.open(syncData)` with `window.openQCInterface(syncData)`
   - Or keep both during transition period

5. **Test**
   - Test simple 2-track playback
   - Test componentized multi-track playback
   - Verify Before/After fix modes work
   - Check volume/mute controls

## Architecture

- **React Components**: Modern React hooks-based architecture
- **waveform-playlist v5**: Uses `@waveform-playlist/browser` package
- **Integration**: Bridge allows vanilla JS to call React component
- **Build**: Vite compiles to `dist-qc/` directory

## Benefits

- ✅ Unlimited tracks (not limited to 2)
- ✅ Better TypeScript support
- ✅ Modern React hooks API
- ✅ Built-in zoom, effects, annotations support
- ✅ Better performance with React optimizations
