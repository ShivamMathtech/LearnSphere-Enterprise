import time
import urllib.request
import webbrowser

for _ in range(60):
    try:
        urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=1)
        urllib.request.urlopen('http://localhost:5173', timeout=1)
        webbrowser.open('http://localhost:5173')
        print('Frontend: http://localhost:5173 | API docs: http://127.0.0.1:8000/docs')
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit('Startup timed out. Inspect the API and Web terminal windows for the error.')
