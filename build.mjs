import { mkdirSync, copyFileSync, readFileSync, writeFileSync } from 'node:fs';

mkdirSync('dist/server', { recursive: true });
mkdirSync('dist/.openai', { recursive: true });
copyFileSync('.openai/hosting.json', 'dist/.openai/hosting.json');
const html = readFileSync('index.html', 'utf8');
const server = `const html = ${JSON.stringify(html)};\n\nexport default {\n  async fetch(request) {\n    const url = new URL(request.url);\n    if (url.pathname === '/' || url.pathname === '/index.html') {\n      return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8' } });\n    }\n    return new Response(html, { headers: { 'content-type': 'text/html; charset=utf-8' } });\n  }\n};\n`;
writeFileSync('dist/server/index.js', server, 'utf8');
