# Aura Agent Frontend

Professional React dashboard for managing Figma-to-React conversion projects.

## Features

- 📊 **Dashboard**: View all projects with real-time status updates
- 🎨 **Project Management**: Create new projects or add websites with component reuse
- 👁️ **Live Preview**: Preview generated websites in iframe
- 📦 **Component Library**: Browse and search reusable components
- 📈 **Statistics**: Track projects, components, and reuse metrics
- ⚡ **Real-time Updates**: Automatic status polling for active conversions

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **shadcn/ui** for beautiful, accessible components
- **TanStack Query** for server state management
- **React Router** for navigation
- **Tailwind CSS** for styling

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Backend API running on `http://localhost:8000`

### Installation

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

The frontend will be available at `http://localhost:3000`

## Project Structure

```
frontend/
├── src/
│   ├── api/          # API client and endpoints
│   ├── components/   # React components
│   │   └── ui/      # shadcn/ui components
│   ├── hooks/       # React Query hooks
│   ├── pages/       # Page components
│   ├── types/       # TypeScript types
│   └── utils/       # Utility functions
├── public/          # Static assets
└── package.json
```

## API Integration

The frontend communicates with the FastAPI backend at `http://localhost:8000`. All API calls are handled through:

- `src/api/client.ts` - Axios-based API client
- `src/hooks/` - React Query hooks for data fetching

## Key Pages

- **Dashboard** (`/`): Main page showing all projects and statistics
- **Project Detail** (`/projects/:id`): Detailed view with preview and status
- **Components** (`/components`): Browse the component library

## Development

The project uses Vite's proxy configuration to forward `/api` requests to the backend during development. See `vite.config.ts` for details.

## Building

```bash
npm run build
```

The production build will be in the `dist/` directory.
