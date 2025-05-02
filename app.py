import os
import pty
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

# Global variable for the terminal process
shell = None

@socketio.on('connect')
def handle_connect():
    global shell
    # Spawn a new shell terminal (bash)
    shell = pty.spawn('/bin/bash', env=os.environ.copy())
    
    # Send terminal output to the frontend
    def read_output(fd):
        while True:
            output = os.read(fd, 1024)
            if len(output) == 0:
                break
            emit('output', output.decode('utf-8'), broadcast=True)

    # Start reading terminal output
    read_output(shell)

# WebSocket event for user input
@socketio.on('input')
def handle_input(data):
    if shell:
        os.write(shell, data.encode('utf-8'))  # Send user input to the shell

# WebSocket event for terminal resizing
@socketio.on('resize')
def handle_resize(size):
    if shell:
        pty.resize(shell, size['cols'], size['rows'])

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
