import urllib.request
import gzip
url = 'https://www.python.org/downloads/'
response = urllib.request.urlopen(url)
raw_content = response.read()
# Try to decompress if gzip
try:
    content = gzip.decompress(raw_content).decode()
except:
    content = raw_content.decode('utf-8', errors='replace')
# Print first 3000 characters
print(content[:3000])