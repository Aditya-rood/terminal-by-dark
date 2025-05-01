import eventlet
eventlet.monkey_patch()

import os
import pty
import select
import threading
import subprocess
from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
socketio = SocketIO(app)

shell_pid, shell_fd = pty.fork()
if shell_pid == 0:
    os.execvp("bash", ["bash"])

background_processes = {}

def run_python_background(filename):
    try:
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if not os.path.isfile(path):
            return f"File not found: {filename}"

        proc = subprocess.Popen(["python3", path],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                text=True)
        background_processes[filename] = proc
        return f"Running {filename} in background (PID {proc.pid})"
    except Exception as e:
        return f"Error running {filename}: {str(e)}"

HTML = '''
<!DOCTYPE html>
<html>
<head>
  <title>Web Terminal</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm/css/xterm.css" />
  <script src="https://cdn.jsdelivr.net/npm/xterm/lib/xterm.js"></script>
  <script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
  <style>
    body { margin: 0; background: #000; color: white; font-family: monospace; }
    #terminal { height: 90vh; width: 100%; }
    #upload-form { padding: 10px; background: #111; }
    #hiddenInput { position: absolute; top: -100px; opacity: 0; }
  </style>
</head>
<body>
  <div id="upload-form">
    <form id="uploadForm" enctype="multipart/form-data">
      <input type="file" name="file" />
      <button type="submit">Upload</button>
    </form>
  </div>
  <div id="terminal"></div>
  <textarea id="hiddenInput"></textarea>

<script>
  const term = new Terminal();
  term.open(document.getElementById('terminal'));

  const socket = io();
  const hiddenInput = document.getElementById('hiddenInput');

  term.write('Welcome to Python Web Terminal\\r\\n');

  term.onData(data => {
    socket.emit('input', data);
  });

  socket.on('output', data => {
    term.write(data);
  });

  // Enable mobile keyboard
  document.getElementById('terminal').addEventListener('touchstart', () => {
    hiddenInput.focus();
  });

  hiddenInput.addEventListener('input', () => {
    socket.emit('input', hiddenInput.value);
    hiddenInput.value = '';
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
    return 'No file selected'

@socketio.on('input')
def on_input(data):
    data = data.strip()
    if data.startswith('python ') and data.endswith('.py'):
        filename = data.split('python ')[1]
        message = run_python_background(filename)
        emit('output', message + '\n')
    elif data == 'jobs':
        message = 'Background Jobs:\n'
        for name, proc in background_processes.items():
            status = 'Running' if proc.poll() is None else 'Finished'
            message += f"{name} (PID {proc.pid}) - {status}\n"
        emit('output', message)
    else:
        os.write(shell_fd, (data + '\n').encode())

def read_from_shell():
    while True:
        try:
            r, _, _ = select.select([shell_fd], [], [], 0.1)
            if shell_fd in r:
                output = os.read(shell_fd, 1024).decode(errors='ignore')
                socketio.emit('output', output)
        except:
            break

threading.Thread(target=read_from_shell, daemon=True).start()

if __name__ == '__main__':
    print("Running on http://0.0.0.0:5000")
    socketio.run(app, host='0.0.0.0', port=5000)
