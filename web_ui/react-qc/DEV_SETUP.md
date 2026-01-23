# React QC Interface - Development Setup

## Quick Start

For **development mode**, build React locally before starting the dev container:

```bash
cd sync-dub/web_ui/react-qc
npm install
npm run build
```

Then start the dev container - the built `dist-qc/` folder will be mounted via volumes.

## Why Build Locally in Dev?

- **Faster iteration**: No need to rebuild Docker when React code changes
- **Hot reload**: Make changes and rebuild instantly
- **Volume mounting**: The entire `sync-dub` directory is mounted, so local builds are used

## Docker Build Behavior

- **Dev mode**: React build is skipped (`SKIP_REACT_BUILD=1`) since volumes override it anyway
- **Production mode**: React is built during Docker build for a self-contained image

## Workflow

1. Make changes to React code in `sync-dub/web_ui/react-qc/src/`
2. Run `npm run build` locally
3. Refresh browser - changes are immediately available (no Docker rebuild needed)

## Troubleshooting

If `dist-qc/` is missing:
```bash
cd sync-dub/web_ui/react-qc
npm run build
```

The build output goes to `sync-dub/web_ui/dist-qc/` which is served by FastAPI.
