import eventlet
eventlet.monkey_patch()

import os
import pty
import select
import subprocess
import threading

from flask import Flask, render_template_string, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

shell_pid, shell_fd = pty.fork()

if shell_pid == 0:
    # Child process: replace with bash
    os.execvp("bash", ["bash"])

# HTML UI + JS terminal
HTML = '''
<!DOCTYPE html>
<html>
<head>
  <title>Python Terminal</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/xterm/css/xterm.css" />
  <script src="https://cdn.jsdelivr.net/npm/xterm/lib/xterm.js"></script>
  <script src="https://cdn.socket.io/4.0.1/socket.io.min.js"></script>
  <style>
    body { margin: 0; background: #000; }
    #terminal { width: 100%; height: 100vh; }
  </style>
</head>
<body>
<div id="terminal"></div>
<script>
  const term = new Terminal();
  term.open(document.getElementById('terminal'));
  const socket = io();

  term.onData(data => {
    socket.emit('input', data);
  });

  socket.on('output', data => {
    term.write(data);
  });
</script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@socketio.on('input')
def on_input(data):
    os.write(shell_fd, data.encode())

def read_from_shell():
    while True:
        try:
            rlist, _, _ = select.select([shell_fd], [], [], 0.1)
            if shell_fd in rlist:
                output = os.read(shell_fd, 1024).decode(errors='ignore')
                socketio.emit('output', output)
        except OSError:
            break

# Background thread to read shell output
threading.Thread(target=read_from_shell, daemon=True).start()

if __name__ == '__main__':
    print("Terminal running at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000)
