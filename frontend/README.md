# Clinic Voice AI frontend

React 19 + Vite + Tailwind frontend for the clinic voice agent.

## Routes

- `/` - public patient call page
- `/admin/login` - staff sign in
- `/admin/live` - admin call page with benchmark run label
- `/admin/appointments` - patient bookings
- `/admin/calls` - call log and transcripts
- `/admin/clinic` - clinic profile and FAQ editor
- `/admin/latency` - latency dashboard

Admin routes use an HttpOnly JWT cookie. The API client sends
`credentials: "include"` and clears the session on a 401.

## Development

```powershell
npm install
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`. Set
`VITE_API_URL` only when you want to call the API directly instead:

```env
VITE_API_URL=http://localhost:8000
```

Leave it empty for Vercel, where `vercel.json` rewrites `/api/*` to the Render
API so cookies stay same-origin.

## Checks

```powershell
npm run lint
npm run build
```
