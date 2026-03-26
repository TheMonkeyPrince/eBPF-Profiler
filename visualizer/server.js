const express = require('express');
const path = require('path');
const fs = require('fs').promises;

const app = express();
const PORT = process.env.PORT || 3000;

const analysisDir = path.join(__dirname, '..', 'profiler', 'out', 'analysis');

app.use(express.static(path.join(__dirname, 'public')));

app.get('/api/files', async (req, res) => {
  try {
    const files = await fs.readdir(analysisDir);
    const jsonFiles = files.filter(f => f.endsWith('.json'));
    res.json(jsonFiles);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/file/:name', async (req, res) => {
  try {
    const name = req.params.name;
    if (!name || !name.endsWith('.json')) return res.status(400).json({ error: 'invalid name' });

    const filePath = path.join(analysisDir, name);
    const resolved = path.resolve(filePath);
    const resolvedBase = path.resolve(analysisDir) + path.sep;
    if (!resolved.startsWith(resolvedBase)) return res.status(400).json({ error: 'invalid path' });

    const content = await fs.readFile(resolved, 'utf8');
    const parsed = JSON.parse(content);
    res.json(parsed);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Serve kernel source files from the linux/ directory. Query params: path, start, end
app.get('/api/source', async (req, res) => {
  try {
    const relPath = req.query.path;
    if (!relPath) return res.status(400).json({ error: 'missing path' });

    const start = req.query.start ? parseInt(req.query.start, 10) : null;
    const end = req.query.end ? parseInt(req.query.end, 10) : null;

    const filePath = path.join(__dirname, '..', 'linux', relPath);
    const resolved = path.resolve(filePath);
    const linuxBase = path.resolve(path.join(__dirname, '..', 'linux')) + path.sep;
    if (!resolved.startsWith(linuxBase)) return res.status(400).json({ error: 'invalid path' });

    const content = await fs.readFile(resolved, 'utf8');
    const lines = content.split(/\r?\n/);
    res.json({ path: relPath, lines, start, end });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Fallback to index.html for client routes
app.get('/file', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'file.html'));
});

// Serve source viewer page at /source so links like /source?path=... load correctly
app.get('/source', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'source.html'));
});

// Fallback to index.html for client routes (use middleware to avoid path-to-regexp issues)
app.use((req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => {
  console.log(`Visualizer running at http://localhost:${PORT}`);
});
