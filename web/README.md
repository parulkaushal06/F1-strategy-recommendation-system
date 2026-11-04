# RACECRAFT web frontend

This is the Next.js 16 / React 19 / TypeScript frontend for the RACECRAFT historical F1 dashboard. It communicates with the FastAPI backend in the repository's `src/api/main.py` through `src/lib/api.ts`.

## Development

Run the API separately from the repository root. It needs the ignored cleaned dataset and model files; see the root [README](../README.md) for the data build and artifact requirements.

```bash
npm ci
npm run dev
```

The frontend opens at `http://localhost:3000` and defaults to an API at `http://localhost:8000`. To configure another backend, create `.env.local` in this directory:

```dotenv
NEXT_PUBLIC_API_URL=https://your-api.example.com
```

## Available scripts

| Command | Description |
|---|---|
| `npm run dev` | Local development server |
| `npm run lint` | ESLint |
| `npx tsc --noEmit` | TypeScript type check |
| `npm run build` | Production build |
| `npm run start` | Serve a production build |

The application routes are Home, Race Hub, Strategy, Compare, and Results. Home and Results use static 2023 content; the main strategy/race exploration pages use the backend API. More project architecture and endpoint details are documented in [docs/11_dashboard.md](../docs/11_dashboard.md).
