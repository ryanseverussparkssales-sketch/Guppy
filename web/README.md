# Guppy Web UI

A comprehensive web-based interface for the Guppy AI Assistant API.

## Features

- **Chat Interface** - Conversational AI with real-time responses
- **Instance Management** - Create and manage AI instances
- **Library** - Save and organize prompts and artifacts
- **Models Management** - Configure local and cloud AI models
- **Tools View** - Available actions and integrations
- **Voice Settings** - TTS and STT configuration
- **System Status** - Real-time health monitoring
- **Settings** - Personalization and configuration

## Tech Stack

- **Framework**: React 18 with TypeScript
- **State Management**: Zustand
- **Styling**: CSS with CSS variables
- **API Client**: Axios
- **Build Tool**: Vite
- **Icons**: Lucide React
- **Routing**: React Router

## Getting Started

### Prerequisites

- Node.js 18+
- npm, yarn, or pnpm

### Installation

```bash
cd web
npm install
```

### Development

```bash
npm run dev
```

The app will be available at `http://localhost:5173`. It proxies API calls to `http://localhost:8081`.

### Build

```bash
npm run build
```

Output goes to `../static` directory for serving from FastAPI.

## Development Tips

- **CSS Variables**: All colors and sizes defined in `src/index.css`
- **Dark Mode**: Automatic based on system preference
- **Responsive**: Mobile-first design, works on all devices
- **State Management**: Use `useAppStore()` for global state
- **API Calls**: Use `api` client from `src/api/client.ts`

## Project Structure

```
web/
├── src/
│   ├── components/       # Reusable UI components
│   ├── views/           # Page components
│   ├── api/             # API client and hooks
│   ├── store.ts         # Global state management
│   ├── App.tsx          # Main app component
│   ├── main.tsx         # Entry point
│   └── index.css        # Global styles
├── index.html           # HTML entry point
├── vite.config.ts       # Build configuration
├── tsconfig.json        # TypeScript configuration
└── package.json         # Dependencies
```

## API Integration

The web UI connects to the Guppy FastAPI backend at `http://localhost:8081`. 

Key endpoints:
- `GET /` - Health check
- `POST /auth/verify` - Get authentication token
- `POST /chat` - Send chat message
- `GET /status` - Get system status
- `GET /startup/check` - Check startup readiness

See `src/api/client.ts` for configuration.

## Customization

### Colors

Edit CSS variables in `src/index.css`:

```css
--color-bg-primary: #0f0f0f;
--color-accent: #3b82f6;
/* ... etc */
```

### Adding New Views

1. Create `src/views/MyView.tsx`
2. Add route in `src/App.tsx`
3. Add nav item in `src/components/Sidebar.tsx`

### Styling

- Use CSS variables for consistency
- Mobile-first approach with `@media (max-width: 768px)`
- Prefer CSS modules for component-scoped styles

## Future Enhancements

- [ ] Voice input/output
- [ ] File upload/download
- [ ] Real-time collaboration
- [ ] Advanced search
- [ ] Plugin system
- [ ] Analytics dashboard
- [ ] User authentication UI
- [ ] Persistent chat history

## License

MIT
