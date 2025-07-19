from flask import Flask, render_template_string, request, redirect, session, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
import os
import time

app = Flask(__name__)
app.secret_key = "secret"
socketio = SocketIO(app)
UPLOAD_FOLDER = 'static/sounds'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

messages = []
banned_ips = set()
shutdown_mode = False
dark_mode = True
admin_ip = None

@app.route('/')
def home():
    return redirect('/lander')

@app.route('/lander', methods=['GET', 'POST'])
def lander():
    if request.method == 'POST':
        phrase = request.form.get('phrase')
        if phrase == "TheFans":
            return redirect('/usrname')
        elif phrase == "sharktooth":
            session['admin'] = True
            global admin_ip
            admin_ip = request.remote_addr
            return redirect('/admin')
    return render_template_string(LANDER_HTML)

@app.route('/usrname', methods=['GET', 'POST'])
def usrname():
    if request.method == 'POST':
        username = request.form.get('username')
        session['username'] = username
        return redirect('/FriendGroup')
    return render_template_string(USRNAME_HTML)

@app.route('/FriendGroup')
def friend_group():
    if shutdown_mode and request.remote_addr != admin_ip:
        return redirect('/lander')
    if request.remote_addr in banned_ips:
        return "You are banned."
    return render_template_string(CHAT_HTML, username=session.get('username', 'Anonymous'), dark=dark_mode)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin'):
        return redirect('/lander')
    return render_template_string(ADMIN_HTML, messages=messages)

@app.route('/admin/action', methods=['POST'])
def admin_action():
    action = request.form.get('action')
    if action == 'clear':
        messages.clear()
        socketio.emit('clear_messages')
    elif action == 'shutdown':
        global shutdown_mode
        shutdown_mode = not shutdown_mode
    elif action == 'toggle':
        global dark_mode
        dark_mode = not dark_mode
    elif action == 'ban':
        ip = request.form.get('ip')
        banned_ips.add(ip)
    elif action == 'unban':
        ip = request.form.get('ip')
        banned_ips.discard(ip)
    elif action == 'colorchat':
        session['username'] = f"<span style='color:red'>{session.get('username')}</span>"
        return redirect('/FriendGroup')
    return redirect('/admin')

@app.route('/admin/upload', methods=['POST'])
def upload_sound():
    file = request.files['file']
    if file:
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)
        socketio.emit('play_sound', {'path': f'/static/sounds/{filename}'})
    return redirect('/admin')

@socketio.on('send_message')
def handle_message(data):
    timestamp = time.time()
    msg = {'username': session.get('username', 'Anonymous'), 'text': data['text'], 'time': timestamp}
    messages.append(msg)
    socketio.emit('message', msg)

@socketio.on('request_messages')
def send_old_messages():
    now = time.time()
    valid = [m for m in messages if now - m['time'] < 36000]  # 10 hrs
    emit('all_messages', valid)

# HTML Templates ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓

LANDER_HTML = """
<!doctype html><html><head><title>Lander</title></head>
<body style="background:black;color:white;text-align:center;">
<h2>Enter Secret Phrase</h2>
<form method="POST"><input name="phrase"><br><br><button>Submit</button></form>
</body></html>
"""

USRNAME_HTML = """
<!doctype html><html><head><title>Username</title></head>
<body style="background:black;color:white;text-align:center;">
<h2>Choose a Username</h2>
<form method="POST"><input name="username"><br><br><button>Enter Chat</button></form>
</body></html>
"""

CHAT_HTML = """
<!doctype html><html>
<head>
<title>FriendGroup</title>
<script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
<style>
body { background: black; color: white; font-family: sans-serif; text-align: center; }
input, button { border-radius: 12px; padding: 10px; border: none; margin: 5px; }
button { background: #444; color: white; }
</style>
</head>
<body>
<h2>Chatroom: FriendGroup</h2>
<div id="chatbox" style="height:300px;overflow:auto;border:1px solid white;margin:10px;padding:10px;"></div>
<form id="msgform">
    <input id="msg" autocomplete="off"><button>Send</button>
</form>
<audio id="audioPlayer" hidden></audio>
<script>
const socket = io();
socket.emit('request_messages');
socket.on('message', msg => {
    const line = document.createElement("div");
    line.innerHTML = `<b>${msg.username}:</b> ${msg.text}`;
    document.getElementById("chatbox").appendChild(line);
});
socket.on('all_messages', msgs => {
    document.getElementById("chatbox").innerHTML = "";
    msgs.forEach(msg => {
        const line = document.createElement("div");
        line.innerHTML = `<b>${msg.username}:</b> ${msg.text}`;
        document.getElementById("chatbox").appendChild(line);
    });
});
socket.on('clear_messages', () => {
    document.getElementById("chatbox").innerHTML = "";
});
socket.on('play_sound', data => {
    const audio = document.getElementById("audioPlayer");
    audio.src = data.path;
    audio.play();
});
document.getElementById("msgform").onsubmit = e => {
    e.preventDefault();
    const msg = document.getElementById("msg").value;
    if (msg) socket.emit('send_message', { text: msg });
    document.getElementById("msg").value = "";
};
</script>
</body></html>
"""

ADMIN_HTML = """
<!doctype html><html>
<head><title>Admin Panel</title></head>
<body style="background:#111;color:white;text-align:center;font-family:sans-serif;">
<h1>Admin Panel</h1>
<form method="POST" action="/admin/action">
    <button name="action" value="colorchat">ColorChat (Red Username)</button><br><br>
    <button name="action" value="clear">Clear Chat</button><br><br>
    <button name="action" value="shutdown">Toggle Shutdown</button><br><br>
    <button name="action" value="toggle">Toggle Light/Dark Mode</button><br><br>
    <input name="ip" placeholder="User IP to ban/unban"><br>
    <button name="action" value="ban">Ban hammer</button>
    <button name="action" value="unban">Unbanner</button><br><br>
</form>
<h3>Play Sound to All Users</h3>
<form method="POST" action="/admin/upload" enctype="multipart/form-data">
    <input type="file" name="file" accept="audio/*">
    <button type="submit">PlaySound</button>
</form>
</body></html>
"""

# Run the app
if __name__ == '__main__':
    socketio.run(app, host="0.0.0.0", port=8080)
