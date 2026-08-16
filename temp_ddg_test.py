import urllib.request
import re

req = urllib.request.Request(
    'https://html.duckduckgo.com/html/?q=python',
    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
)
html = urllib.request.urlopen(req, timeout=10).read().decode('utf-8', errors='ignore')

matches = re.findall(r'<a[^>]*class="[^"]*result[^"]*"[^>]*>', html)
print(f"Found {len(matches)} matching tags:\n")
for m in matches[:10]:
    print(m)