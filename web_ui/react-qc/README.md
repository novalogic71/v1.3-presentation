# React QC Player Migration

This directory contains the React-based QC Interface using waveform-playlist v5.

## Setup

1. Install dependencies:
```bash
cd sync-dub/web_ui/react-qc
npm install
```

2. Development mode:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
```

The build output will be in `../dist-qc/` directory.

## Integration

The React QC component integrates with the existing vanilla JS codebase via:

1. **Custom Events**: The vanilla JS code can open QC interface by dispatching:
   ```javascript
   window.openQCInterface(syncData);
   ```

2. **Mount Point**: React component mounts to `#qc-react-root` element.

3. **Build Output**: After building, include the compiled JS in `app.html`:
   ```html
   <script type="module" src="dist-qc/qc-react.js"></script>
   ```

## Architecture

- **QCInterface.tsx**: Main component that wraps QCModal with WaveformPlaylistProvider
- **QCModal.tsx**: Modal UI component using waveform-playlist v5 components
- **bridge.ts**: Bridge between vanilla JS and React
- **types.ts**: TypeScript type definitions

## Features

- Multi-track support (unlimited tracks via waveform-playlist v5)
- Built-in zoom, seeking, and playback controls
- Volume and mute controls per track
- Before/After fix mode switching
- Modern React hooks-based architecture
