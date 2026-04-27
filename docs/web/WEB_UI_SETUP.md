# Guppy Web UI - Setup & Build Guide

A comprehensive, feature-rich web interface for the Guppy AI Assistant API. Built with React, TypeScript, and Vite.

## Quick Start

### 1. Install Dependencies

```bash
cd web
npm install
# or: yarn install, pnpm install
```

### 2. Development Server

```bash
npm run dev
```

- Web UI: http://localhost:5173
- API: http://localhost:8081 (proxied automatically)

### 3. Build for Production

```bash
npm run build
```

This creates optimized static files in the `static/` directory.

## Features

### Navigation (current as of 2026-04-27)

1. **Chat** (`AssistantView`) — Main conversational AI interface
   - Streaming SSE responses with Stop/Steer/TTS controls
   - Mode selector (auto / local / claude / code / steer)
   - Voice input/output (TTS toggle)
   - Message history with markdown rendering

2. **Launch Control** (`LauncherView`) — All local runtime management in one hub
   - **Agents tab** — Create/manage agent instances, assign models
   - **Models tab** — Local model inventory (Ollama + all 5 llamacpp backends with alive/offline state)
   - **Backends tab** — llamacpp server start/stop, VRAM bar, backend health
   - **Cloud tab** — Cloud provider status

3. **Personas** (`PersonasView`) — Persona configuration and switching

4. **Instructions** (`InstructionsView`) — System prompt / instruction management

5. **Tools** (`ToolsView`) — Available tool registry, enable/disable per workspace

6. **Settings** (`SettingsView`) — API keys (all 5 cloud providers), active provider, preferences

### Design Features

- **Dark & Light Mode** - Automatic theme based on system preference
- **Responsive Design** - Works on desktop, tablet, and mobile
- **Real-time Updates** - Live status and API polling
- **Keyboard Shortcuts** - Send message with Ctrl+Enter
- **Accessibility** - WCAG compliant
- **Fast Performance** - Vite build, optimized bundle

## Project Structure

```
web/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx    # Root layout (Sidebar + TopBar + outlet)
│   │   │   ├── Sidebar.tsx     # Navigation sidebar (Chat/LaunchControl/Personas/Instructions/Tools/Settings)
│   │   │   └── TopBar.tsx      # Header: workspace switcher + model picker (all providers) + status
│   │   └── chat/
│   │       └── MarkdownMessage.tsx  # Markdown renderer for chat messages
│   │
│   ├── views/                  # Page components (one per route)
│   │   ├── AssistantView.tsx   # /chat — streaming chat, mode selector, TTS
│   │   ├── LauncherView.tsx    # /launch — Agents + Models + Backends + Cloud tabs
│   │   ├── PersonasView.tsx    # /personas
│   │   ├── InstructionsView.tsx # /instructions
│   │   ├── ToolsView.tsx       # /tools
│   │   ├── SettingsView.tsx    # /settings — API keys, provider selection
│   │   ├── ModelsView.tsx      # (accessible but not primary nav)
│   │   └── VoicesView.tsx      # (accessible but not primary nav)
│   │
│   ├── hooks/
│   │   ├── useApi.ts           # SWR-backed hooks: useProviders, useActiveModel, useConnectionStatus
│   │   ├── useWorkspaces.ts    # Workspace CRUD and active workspace state
│   │   ├── useVoice.ts         # TTS playback and STT recording
│   │   └── useReminders.ts     # Reminders API
│   │
│   ├── api/
│   │   └── client.ts           # Axios client (base URL = window.location.origin)
│   │
│   ├── App.tsx                 # React Router routes
│   ├── main.tsx                # Entry point
│   └── index.css               # Global styles + Tailwind config
│
├── index.html
├── vite.config.ts              # Dev proxy: /api/* and /providers → localhost:8081
├── tsconfig.json
└── package.json

static/                         # Built output (committed, served by FastAPI)
├── index.html
└── assets/
    ├── index-*.js
    └── index-*.css
```

## Configuration

### Environment Variables

Create a `.env.local` file in the `web/` directory:

```env
VITE_API_URL=http://localhost:8081
VITE_APP_NAME=Guppy
```

### Vite Configuration

Edit `web/vite.config.ts` to customize:
- Dev server port (default: 5173)
- Build output directory (default: ../static)
- API proxy settings
- Environment variables

### CSS Customization

Edit `web/src/index.css` to customize colors and typography:

```css
:root {
  --color-bg-primary: #0f0f0f;
  --color-text-primary: #ffffff;
  --color-accent: #3b82f6;
  /* ... etc */
}
```

## Development

### Adding a New View

1. Create `src/views/MyView.tsx`:

```tsx
export default function MyView() {
  return (
    <div className="view-container">
      <div className="view-header">
        <h2>My View</h2>
      </div>
      {/* Content */}
    </div>
  )
}
```

2. Create `src/views/MyView.css`:

```css
/* Styles for MyView */
```

3. Add to `src/App.tsx`:

```tsx
<Route path="/myview" element={<MyView />} />
```

4. Add to `src/components/Sidebar.tsx`:

```tsx
{ path: '/myview', label: 'My View', icon: MyIcon },
```

### API Integration

Use the `api` client from `src/api/client.ts`:

```tsx
import api from '../api/client'

// GET request
const response = await api.get('/status')

// POST request
const response = await api.post('/chat', { message: 'hello' })

// With error handling
try {
  const data = await api.get('/endpoint')
} catch (error) {
  console.error('API error:', error)
}
```

### State Management

Use Zustand for global state:

```tsx
import { useAppStore } from '../store'

function MyComponent() {
  const { messages, addMessage } = useAppStore()
  
  // Use state and actions
}
```

## Production Deployment

### 1. Build the Web UI

```bash
cd web
npm install
npm run build
```

### 2. Start the API Server

```bash
$env:PYTHONPATH="."; $env:GUPPY_DEV_MODE="1"; $env:GUPPY_JWT_SECRET="your-secret"; .venv\Scripts\uvicorn app:app --host 0.0.0.0 --port 8081
```

The web UI will be automatically served at `http://localhost:8081/`

### 3. Environment Variables

Set these for production:

```bash
GUPPY_JWT_SECRET=your-secure-secret-key
GUPPY_DEV_MODE=0
ANTHROPIC_API_KEY=your-api-key
```

## Performance Tips

- **Code Splitting**: Routes are automatically code-split by Vite
- **Image Optimization**: Use Lucide icons (SVG) instead of images
- **Lazy Loading**: Consider React.lazy() for heavy components
- **API Caching**: Implement response caching for status endpoints
- **CSS Variables**: Reduces bundle size vs. CSS-in-JS

## Troubleshooting

### API Connection Issues

1. Check API server is running on port 8081
2. Verify CORS is configured (it is by default)
3. Check browser console for errors

### Build Errors

```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
npm run build
```

### Hot Reload Not Working

```bash
# Restart dev server
npm run dev
```

## Browser Support

- Chrome/Edge 90+
- Firefox 88+
- Safari 14+
- Mobile browsers (iOS Safari, Chrome Mobile)

## Next Steps

1. **Customize colors** in `src/index.css`
2. **Add branding** (logo, title) in components
3. **Implement voice** using Web Audio API
4. **Add file uploads** to chat interface
5. **Create admin panel** for system management
6. **Add dark/light mode toggle**
7. **Implement user authentication UI**
8. **Add analytics tracking**

## Resources

- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Vite Guide](https://vitejs.dev/guide/)
- [Zustand Docs](https://github.com/pmndrs/zustand)
- [Axios Docs](https://axios-http.com/docs/intro)

## Support

For issues or questions:
1. Check the README in `web/README.md`
2. Review component source code
3. Check browser console for errors
4. Verify API server is running and accessible

---

**Version**: 2.0.0  
**Last Updated**: 2026-04-27
