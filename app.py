import os
import sys
import pty
import subprocess
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app)

# WebSocket Event to start terminal
@socketio.on('connect')
def handle_connect():
    # Spawn a new shell terminal
    shell = pty.spawn('/bin/bash', env=os.environ.copy())

    # Send output from terminal to frontend
    def read_output(fd):
        while True:
            output = os.read(fd, 1024)
            if len(output) == 0:
                break
            emit('output', output.decode('utf-8'), broadcast=True)

    # Start reading the output from the terminal
    read_output(shell)

# WebSocket Event for user input
@socketio.on('input')
def handle_input(data):
    try:
        os.write(shell, data.encode('utf-8'))  # Send input to terminal
    except Exception as e:
        emit('output', f"Error: {str(e)}")
        
# WebSocket event for resizing the terminal
@socketio.on('resize')
def handle_resize(size):
    cols, rows = size['cols'], size['rows']
    pty.resize(shell, cols, rows)

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
