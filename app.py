import os
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
import subprocess
import eventlet
from werkzeug.utils import secure_filename

eventlet.monkey_patch()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socketio = SocketIO(app)

# Basic HTML + xterm.js frontend served via Python only
HTML = '''
<!DOCTYPE html>
<html>
<head>
  <title>Python Web Terminal</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm/css/xterm.css" />
  <script src="https://cdn.jsdelivr.net/npm/xterm/lib/xterm.js"></script>
  <script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
  <style>
    body { background: #000; margin: 0; color: white; font-family: monospace; }
    #terminal { height: 80vh; width: 100%; }
    #upload-box { padding: 10px; background: #111; }
  </style>
</head>
<body>
  <div id="upload-box">
    <form id="uploadForm" enctype="multipart/form-data">
      <input type="file" name="file" />
      <button type="submit">Upload</button>
    </form>
  </div>
  <div id="terminal"></div>

<script>
  const term = new Terminal();
  term.open(document.getElementById('terminal'));
  term.write('Welcome to Python Web Terminal\\r\\n');

  const socket = io();

  term.onData(data => {
    socket.emit('input', data);
  });

  socket.on('output', data => {
    term.write(data);
  });

  document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = new FormData(e.target);
    const res = await fetch('/upload', { method: 'POST', body: form });
    const msg = await res.text();
    term.write('\\r\\n' + msg + '\\r\\n');
  });
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('file')
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return f'File uploaded: {filename}'
    return 'No file uploaded'

@socketio.on('input')
def handle_input(data):
    try:
        result = subprocess.run(data, shell=True, capture_output=True, text=True)
        output = result.stdout + result.stderr
        emit('output', output)
    except Exception as e:
        emit('output', f"Error: {str(e)}")

if __name__ == '__main__':
    print("Server running at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000)
