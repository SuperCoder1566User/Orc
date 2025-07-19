from flask import Flask, render_template_string, request, redirect, session, send_from_directory
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'secret'
socketio = SocketIO(app)
chat_history = []
banned_ips = set()
shutdown_mode = False
dark_mode = True

@app.route('/')
def home():
    return redirect('/lander')

@app.route('/lander', methods=['GET', 'POST'])
def lander():
    if request.method == 'POST':
        phrase = request.form.get('phrase')
        if phrase == 'TheFans':
            return redirect('/usrname')
        elif phrase == 'sharktooth':
            session['is_admin'] = True
            return redirect('/admin')
    return render_template_string("""
        <form method="post">
            <input name="phrase" placeholder="Secret Phrase">
            <button type="submit">Enter</button>
        </form>
    """)

@app.route('/usrname', methods=['GET', 'POST'])
def usrname():
    if shutdown_mode and not session.get('is_admin'):
        return redirect('/lander')
    if request.method == 'POST':
        session['username'] = request.form.get('username')
        return redirect('/FriendGroup')
    return render_template_string("""
        <form method="post">
            <input name="username" placeholder="Username">
            <button type="submit">Enter Chat</button>
        </form>
    """)

@app.route('/FriendGroup')
def chat():
    if shutdown_mode and not session.get('is_admin'):
        return redirect('/lander')
    ip = request.remote_addr
    if ip in banned_ips:
        return "You are banned."
    return render_template_string("""
        <div id="chat-box"></div>
        <input id="msg"><button onclick="send()">Send</button>
        <script src="//cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.0/socket.io.js"></script>
        <script>
        var socket = io();
        socket.on('message', msg => {
            let div = document.createElement('div');
            div.textContent = msg;
            document.getElementById('chat-box').appendChild(div);
        });
        function send() {
            let msg = document.getElementById('msg').value;
            socket.emit('message', msg);
        }
        </script>
    """)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        return redirect('/lander')
    return render_template_string("""
        <h1>Admin Panel</h1>
        <form method="post" action="/admin/colorchat"><button>ColorChat</button></form>
        <form method="post" action="/admin/ban"><input name="ip"><button>Ban hammer</button></form>
        <form method="post" action="/admin/unban"><input name="ip"><button>Unbanner</button></form>
        <form method="post" action="/admin/clearchat"><button>ClearChat</button></form>
        <form method="post" action="/admin/shutdown"><button>Shutdown</button></form>
        <form method="post" action="/admin/toggle"><button>Toggle Light/Dark Mode</button></form>
    """)

@app.route('/admin/<action>', methods=['POST'])
def admin_action(action):
    global chat_history, shutdown_mode, dark_mode
    if not session.get('is_admin'):
        return redirect('/lander')
    if action == 'colorchat':
        session['username'] = '<span style="color:red">' + session.get('username', 'Admin') + '</span>'
        return redirect('/FriendGroup')
    if action == 'ban':
        banned_ips.add(request.form.get('ip'))
    if action == 'unban':
        banned_ips.discard(request.form.get('ip'))
    if action == 'clearchat':
        chat_history.clear()
    if action == 'shutdown':
        shutdown_mode = not shutdown_mode
    if action == 'toggle':
        dark_mode = not dark_mode
    return redirect('/admin')

@socketio.on('message')
def handle_message(msg):
    timestamp = datetime.now()
    chat_history.append((session.get('username', 'Anonymous'), msg, timestamp))
    socketio.emit('message', f"{session.get('username', 'Anonymous')}: {msg}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=8080)
