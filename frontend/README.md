# StanFord-AI OS Frontend

React + TypeScript frontend built with Vite.

## Development

```bash
npm install
npm run dev
```

The Vite dev server proxies `/health`, `/auth`, `/tasks`, and `/executions` to the local backend at `http://127.0.0.1:8000`.

## Production build

```bash
npm run build
```

Output directory: `dist/`.

## Vercel deployment

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- Install command: `npm install`

Set the following environment variable in Vercel:

- `VITE_API_BASE_URL`: Full URL of the deployed backend, e.g. `https://your-render-service.onrender.com` (no trailing slash). Leave unset for local development.

## Validation

```bash
npm run lint
npm run test
npm run build
```
