// Minimal static server that gzips like GitHub Pages does. usage: node gzserve.js <dir> <port>
const http = require('http'), fs = require('fs'), path = require('path'), zlib = require('zlib');
const [dir, port] = [process.argv[2], +process.argv[3]];
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.css': 'text/css', '.json': 'application/json', '.md': 'text/markdown' };
const cache = new Map();
http.createServer((req, res) => {
  let p = decodeURIComponent(req.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(dir, p); if (!f.startsWith(dir) || !fs.existsSync(f)) { res.writeHead(404); return res.end(); }
  if (!cache.has(f)) cache.set(f, zlib.gzipSync(fs.readFileSync(f), { level: 6 }));
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(f)] || 'application/octet-stream', 'Content-Encoding': 'gzip', 'Cache-Control': 'max-age=600' });
  res.end(cache.get(f));
}).listen(port, () => console.log('gz server on', port));
