# Profiler Visualizer

Simple Node + Express app that lists files in `profiler/out/analysis` and provides a viewer.

Quick start:

1. cd visualizer
2. npm install
3. npm start

Open http://localhost:3000

Notes:
- The frontend uses the Tailwind CDN for styling.
- The server serves `GET /api/files` and `GET /api/file/:name`.
