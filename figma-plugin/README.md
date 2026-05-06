# Aura Export - Figma Plugin

Export your Figma designs directly to the Aura backend for React + Tailwind CSS conversion, **without any API rate limits**.

## Why Use This Plugin?

| Feature | REST API | Plugin |
|---------|----------|--------|
| Rate Limits | 6 calls/month (View/Collab) | **None!** |
| API Token Required | Yes | **No** |
| Speed | Network dependent | **Faster** |
| Data Access | Limited by API | **Complete** |

## Installation

### Step 1: Build the Plugin

```bash
cd figma-plugin
npm install
npm run build
```

This creates the `dist/` folder with the compiled plugin.

### Step 2: Install in Figma Desktop

1. **Open Figma Desktop App** (this plugin requires the desktop app)
2. Go to **Menu → Plugins → Development → Import plugin from manifest**
3. Navigate to and select `figma-plugin/manifest.json`
4. The plugin is now installed!

## Usage

### Step 1: Start the Aura Backend

Make sure the Aura backend is running:

```bash
# From the project root
source .venv/bin/activate
python -m uvicorn backend.main:app --reload --port 8000
```

### Step 2: Open Your Design in Figma

Open the Figma file you want to convert to React.

### Step 3: Run the Plugin

1. Go to **Menu → Plugins → Development → Aura Export**
2. Enter the **Backend URL** (default: `http://localhost:8000`)
3. Enter a **Project Name** (e.g., `my-landing-page`)
4. Select your **UI Library** (Tailwind CSS, Material UI, or Chakra UI)
5. Click **"Export to Aura"**

### Step 4: Wait for Conversion

The plugin will:
1. Extract all design data (frames, colors, fonts, images)
2. Send to the Aura backend
3. Backend generates React + Tailwind CSS code

You can check the conversion progress at:
```
http://localhost:8000/api/projects/{project_id}/status
```

## What Gets Exported?

The plugin extracts:
- ✅ All pages and frames
- ✅ Complete node hierarchy
- ✅ Text content (verbatim)
- ✅ Colors (exact hex values)
- ✅ Fonts (family, size, weight)
- ✅ Layout (auto-layout, padding, spacing)
- ✅ Effects (shadows, blur)
- ✅ Images (as base64)
- ✅ Corner radius and strokes

## Development

### Project Structure

```
figma-plugin/
├── manifest.json       # Plugin configuration
├── src/
│   ├── code.ts        # Main extraction logic
│   └── ui.html        # Plugin UI
├── dist/              # Built files (generated)
├── package.json       # Dependencies
└── tsconfig.json      # TypeScript config
```

### Build Commands

```bash
# Build once
npm run build

# Watch for changes (auto-rebuild)
npm run watch

# Type check
npm run typecheck
```

### Modifying the Plugin

1. Edit files in `src/`
2. Run `npm run build`
3. In Figma, go to **Menu → Plugins → Development → Aura Export** to test

## Troubleshooting

### Plugin not appearing in Figma?
- Make sure you're using **Figma Desktop App** (not browser)
- Re-import the manifest: Menu → Plugins → Development → Import plugin from manifest

### "Network error" when exporting?
- Check that the Aura backend is running
- Verify the Backend URL is correct
- Check browser console for CORS errors

### Large designs timing out?
- The plugin has a ~30 second execution limit
- Try exporting individual pages instead of the entire file
- Images are the slowest to export - consider using fewer high-res images

## API Endpoint

The plugin sends data to:
```
POST /api/figma/plugin-upload
```

Request body:
```json
{
  "project_name": "my-project",
  "ui_library": "tailwind",
  "design_data": {
    "fileName": "My Design",
    "pages": [...],
    "colors": {...},
    "fonts": [...],
    "images": {...},
    "stats": {...}
  }
}
```

## License

MIT
