from flask import Flask, render_template_string, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
import os

app = Flask(__name__)
app.secret_key = 'supersecretkey'
socketio = SocketIO(app)

# HTML Templates
lander_html = '''
<!DOCTYPE html>
<html>
<head>
  <title>Enter Secret</title>
  <style>
    body {
      background-color: #121212;
      color: white;
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      font-family: sans-serif;
    }
    form {
      background-color: #1e1e1e;
      padding: 30px;
      border-radius: 15px;
      box-shadow: 0 0 10px #000;
    }
    input[type="text"], input[type="submit"] {
      padding: 10px;
      border-radius: 10px;
      border: none;
      margin-top: 10px;
      width: 100%;
      font-size: 16px;
    }
    input[type="submit"] {
      background-color: #2196f3;
      color: white;
      cursor: pointer;
    }
    .error { color: red; }
  </style>
</head>
<body>
  <form method="post">
    <h2>Enter Secret Phrase</h2>
    <input type="text" name="phrase" placeholder="Secret phrase" required>
    <input type="submit" value="Enter">
    {% if error %}
      <p class="error">{{ error }}</p>
    {% endif %}
  </form>
</body>
</html>
'''

chat_html = '''
<!DOCTYPE html>
<html>
<head>
  <title>FriendGroup Chat</title>
  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
  <style>
    body {
      margin: 0;
      background-color: #121212;
      color: white;
      font-family: sans-serif;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    #chat {
      flex-grow: 1;
      overflow-y: auto;
      padding: 20px;
    }
    #form {
      display: flex;
      padding: 10px;
      background: #1e1e1e;
      border-top: 1px solid #333;
    }
    #message {
      flex: 1;
      padding: 10px;
      border-radius: 10px;
      border: none;
      font-size: 16px;
      background: #2c2c2c;
      color: white;
    }
    #send {
      padding: 10px 20px;
      border: none;
      background: #2196f3;
      color: white;
      font-size: 16px;
      border-radius: 10px;
      margin-left: 10px;
      cursor: pointer;
    }
    .msg {
      margin-bottom: 10px;
    }
  </style>
</head>
<body>
  <div id="chat"></div>
  <form id="form">
    <input id="message" autocomplete="off" placeholder="Type a message..." />
    <button id="send">Send</button>
  </form>
  <script>
    const socket = io();
    const form = document.getElementById('form');
    const messageInput = document.getElementById('message');
    const chat = document.getElementById('chat');

    form.addEventListener('submit', function(e) {
      e.preventDefault();
      if (messageInput.value.trim() !== "") {
        socket.emit('message', messageInput.value);
        messageInput.value = '';
      }
    });

    socket.on('message', function(msg) {
      const div = document.createElement('div');
      div.classList.add('msg');
      div.textContent = msg;
      chat.appendChild(div);
      chat.scrollTop = chat.scrollHeight;
    });
  </script>
</body>
</html>
'''

# Routes
@app.route('/lander', methods=['GET', 'POST'])
def lander():
    error = None
    if request.method == 'POST':
        phrase = request.form.get('phrase')
        if phrase == 'TheFans':
            session['authenticated'] = True
            return redirect(url_for('chat'))
        else:
            error = "Wrong phrase!"
    return render_template_string(lander_html, error=error)

@app.route('/FriendGroup')
def chat():
    if not session.get('authenticated'):
        return redirect(url_for('lander'))
    return render_template_string(chat_html)

# Socket Events
@socketio.on('message')
def handle_message(msg):
    emit('message', msg, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
