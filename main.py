# Flask Chat App with Admin Panel, PlaySound, Stats, Password-Protected Usernames
from flask import Flask, request, render_template_string, redirect, session, send_file, jsonify
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename
import os
import time
import uuid

app = Flask(__name__)
app.secret_key = 'thefans'
socketio = SocketIO(app)

# ------------------- Data Stores -------------------
chat_history = []
banned_ips = set()
banned_users = set()
user_messages = {}
user_passwords = {}
user_colors = {}
shutdown_enabled = False
global_theme = 'dark'

# ------------------- Templates -------------------
# Only including one template here due to space. Others can be added on request
chat_template = """
<!DOCTYPE html>
<html>
<head>
    <title>FriendGroup</title>
    <style>
        body {
            font-family: 'Segoe UI', sans-serif;
            background-color: {% if theme == 'dark' %}#1e1e1e{% else %}#f0f0f0{% endif %};
            color: {% if theme == 'dark' %}white{% else %}black{% endif %};
            text-align: center;
        }
        input, button, textarea {
            border-radius: 10px;
            padding: 10px;
            margin: 5px;
            border: none;
            font-size: 16px;
        }
        #chat { height: 300px; overflow-y: scroll; border: 1px solid gray; margin: 10px; padding: 5px; }
        .msg { margin: 4px; padding: 4px; border-radius: 10px; background: #333; color: white; }
    </style>
</head>
<body>
    <h2>Welcome, {{username}}!</h2>
    <div id="chat"></div>
    <input id="msg" placeholder="Type message...">
    <button onclick="send()">Send</button>
    <br>
    <button onclick="location.href='/stats'">View Chat Stats</button>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script>
        const socket = io();
        const chat = document.getElementById('chat');
        const msgInput = document.getElementById('msg');
        socket.on("chat", data => {
            const msg = document.createElement("div");
            msg.className = 'msg';
            msg.innerHTML = "<b style='color:" + data.color + "'>" + data.user + "</b>: " + data.msg;
            chat.appendChild(msg);
            chat.scrollTop = chat.scrollHeight;
        });
        function send() {
            const msg = msgInput.value;
            if (msg) {
                socket.emit("chat", msg);
                msgInput.value = "";
            }
        }
    </script>
</body>
</html>
"""

# ------------------- Routes -------------------
@app.route('/')
def index():
    return redirect('/lander')

@app.route('/lander', methods=['GET', 'POST'])
def lander():
    if request.method == 'POST':
        phrase = request.form.get('phrase', '')
        if phrase == 'sharktooth':
            return redirect('/admin')
        elif phrase == 'TheFans':
            return redirect('/usrname')
        else:
            return "Incorrect phrase", 403
    return '''<form method="POST"><input name="phrase" placeholder="Enter Secret Phrase"><button>Enter</button></form>'''

@app.route('/usrname', methods=['GET', 'POST'])
def usrname():
    if request.method == 'POST':
        uname = request.form['username']
        passwd = request.form['password']
        if uname in user_passwords and user_passwords[uname] != passwd:
            return "Incorrect password for this username", 403
        user_passwords[uname] = passwd
        session['username'] = uname
        return redirect('/FriendGroup')
    return '''
    <form method="POST">
        <input name="username" placeholder="Choose Username"><br>
        <input name="password" type="password" placeholder="Set Password"><br>
        <button>Enter Chat</button>
    </form>'''

@app.route('/FriendGroup')
def friendgroup():
    if shutdown_enabled and session.get('admin') != True:
        return "Chat is in shutdown mode"
    ip = request.remote_addr
    uname = session.get('username', f"Guest-{ip}")
    if ip in banned_ips or uname in banned_users:
        return "You are banned"
    return render_template_string(chat_template, username=uname, theme=global_theme)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    session['admin'] = True
    return '''
    <h2>Admin Panel</h2>
    <form action="/admin/ban" method="POST">
        <input name="user" placeholder="Ban Username">
        <button>Ban</button>
    </form>
    <form action="/admin/unban" method="POST">
        <input name="user" placeholder="Unban Username">
        <button>Unban</button>
    </form>
    <form action="/admin/broadcast" method="POST">
        <input name="message" placeholder="Broadcast Message">
        <button>Send</button>
    </form>
    <form action="/admin/clear" method="POST"><button>Clear Chat</button></form>
    <form action="/admin/shutdown" method="POST"><button>Toggle Shutdown</button></form>
    <form action="/admin/toggle" method="POST"><button>Toggle Theme</button></form>
    <form action="/admin/sound" method="POST" enctype="multipart/form-data">
        <input type="file" name="audio">
        <button>Play Sound</button>
    </form>
    <form action="/FriendGroup?color=red"><button>ColorChat</button></form>
    '''

@app.route('/admin/ban', methods=['POST'])
def ban():
    uname = request.form['user']
    banned_users.add(uname)
    return redirect('/admin')

@app.route('/admin/unban', methods=['POST'])
def unban():
    uname = request.form['user']
    banned_users.discard(uname)
    return redirect('/admin')

@app.route('/admin/clear', methods=['POST'])
def clear_chat():
    chat_history.clear()
    return redirect('/admin')

@app.route('/admin/shutdown', methods=['POST'])
def toggle_shutdown():
    global shutdown_enabled
    shutdown_enabled = not shutdown_enabled
    return redirect('/admin')

@app.route('/admin/toggle', methods=['POST'])
def toggle_theme():
    global global_theme
    global_theme = 'light' if global_theme == 'dark' else 'dark'
    return redirect('/admin')

@app.route('/admin/broadcast', methods=['POST'])
def broadcast():
    msg = request.form['message']
    socketio.emit("chat", {'user': 'ADMIN', 'msg': msg, 'color': 'red'})
    return redirect('/admin')

@app.route('/admin/sound', methods=['POST'])
def play_sound():
    file = request.files['audio']
    filename = f"temp_{uuid.uuid4().hex}.wav"
    path = os.path.join("static", filename)
    file.save(path)
    socketio.emit("play_sound", {"url": f"/static/{filename}"})
    return redirect('/admin')

@app.route('/stats')
def stats():
    sorted_users = sorted(user_messages.items(), key=lambda x: x[1], reverse=True)
    return "<h2>Chat Leaderboard</h2>" + "<br>".join([f"{u}: {c} messages" for u, c in sorted_users])

# ------------------- SocketIO -------------------
@socketio.on("chat")
def handle_chat(msg):
    uname = session.get('username', 'Unknown')
    ip = request.remote_addr
    if ip in banned_ips or uname in banned_users or shutdown_enabled:
        return
    user_messages[uname] = user_messages.get(uname, 0) + 1
    color = request.args.get("color", user_colors.get(uname, "white"))
    user_colors[uname] = color
    socketio.emit("chat", {'user': uname, 'msg': msg, 'color': color})

# ------------------- Run -------------------
if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=5050)
