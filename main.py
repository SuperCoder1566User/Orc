from flask import Flask, render_template_string, request, redirect, session, send_file
from flask_socketio import SocketIO, emit
from datetime import datetime, timedelta
import os
import uuid

app = Flask(__name__)
app.secret_key = 'secret!'
socketio = SocketIO(app)

# Global state
messages = []
banned_ips = set()
shutdown_mode = False
dark_mode = True
sounds_to_play = []

# Constants
SECRET_PHRASE = "TheFans"
ADMIN_PHRASE = "sharktooth"
MESSAGE_LIFETIME = timedelta(hours=10)

# Routes
@app.route('/')
def index():
    return redirect('/lander')

@app.route('/lander', methods=['GET', 'POST'])
def lander():
    if request.method == 'POST':
        phrase = request.form.get('phrase')
        if phrase == ADMIN_PHRASE:
            session['admin'] = True
            return redirect('/admin')
        elif phrase == SECRET_PHRASE:
            return redirect('/usrname')
    return render_template_string(LANDER_HTML, dark=dark_mode)

@app.route('/usrname', methods=['GET', 'POST'])
def usrname():
    if shutdown_mode and not session.get('admin'):
        return redirect('/lander')
    if request.method == 'POST':
        username = request.form.get('username')
        if username:
            session['username'] = username
            session['color'] = 'white'
            return redirect('/FriendGroup')
    return render_template_string(USERNAME_HTML, dark=dark_mode)

@app.route('/FriendGroup')
def friendgroup():
    ip = request.remote_addr
    if shutdown_mode and not session.get('admin'):
        return redirect('/lander')
    if ip in banned_ips:
        return "You are banned."
    if 'username' not in session:
        return redirect('/usrname')
    return render_template_string(CHAT_HTML, username=session['username'],
                                  color=session.get('color', 'white'), dark=dark_mode)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin'):
        return redirect('/lander')
    return render_template_string(ADMIN_HTML, dark=dark_mode)

@app.route('/admin/colorchat')
def colorchat():
    session['color'] = 'red'
    return redirect('/FriendGroup')

@app.route('/admin/ban', methods=['POST'])
def ban():
    if session.get('admin'):
        ip = request.form.get('ip')
        banned_ips.add(ip)
    return redirect('/admin')

@app.route('/admin/unban', methods=['POST'])
def unban():
    if session.get('admin'):
        ip = request.form.get('ip')
        banned_ips.discard(ip)
    return redirect('/admin')

@app.route('/admin/clearchat')
def clearchat():
    if session.get('admin'):
        messages.clear()
    return redirect('/admin')

@app.route('/admin/shutdown')
def shutdown():
    global shutdown_mode
    if session.get('admin'):
        shutdown_mode = not shutdown_mode
    return redirect('/admin')

@app.route('/admin/toggle')
def toggle_mode():
    global dark_mode
    if session.get('admin'):
        dark_mode = not dark_mode
    return redirect('/admin')

@app.route('/admin/playsound', methods=['POST'])
def playsound():
    if 'sound' in request.files:
        f = request.files['sound']
        fname = f"{uuid.uuid4()}.wav"
        path = os.path.join('static', fname)
        f.save(path)
        sounds_to_play.append(fname)
        socketio.emit('play_sound', {'url': f'/static/{fname}'})
    return redirect('/admin')

# SocketIO events
@socketio.on('send_message')
def handle_message(data):
    username = session.get('username', 'Anonymous')
    color = session.get('color', 'white')
    now = datetime.utcnow()
    messages.append({
        'user': username,
        'text': data['text'],
        'color': color,
        'timestamp': now
    })
    # Remove old messages
    cutoff = now - MESSAGE_LIFETIME
    messages[:] = [m for m in messages if m['timestamp'] > cutoff]
    emit('receive_message', {'user': username, 'text': data['text'], 'color': color}, broadcast=True)

# HTML Templates
BASE_CSS = """
<style>
body {
    background-color: {% if dark %}#111{% else %}#eee{% endif %};
    color: {% if dark %}#fff{% else %}#111{% endif %};
    font-family: 'Segoe UI', sans-serif;
    padding: 30px;
}
input, button {
    border-radius: 20px;
    padding: 10px;
    font-size: 1em;
    border: 1px solid #888;
}
button {
    cursor: pointer;
    background-color: {% if dark %}#333{% else %}#ccc{% endif %};
    color: {% if dark %}#fff{% else %}#000{% endif %};
}
input[type="file"] {
    border: none;
}
</style>
"""

LANDER_HTML = BASE_CSS + """
<h2>Enter Secret Phrase</h2>
<form method="post">
    <input name="phrase" placeholder="Secret phrase">
    <button>Enter</button>
</form>
"""

USERNAME_HTML = BASE_CSS + """
<h2>Choose Your Username</h2>
<form method="post">
    <input name="username" placeholder="Username">
    <button>Continue</button>
</form>
"""

CHAT_HTML = BASE_CSS + """
<h2>Welcome, {{username}}</h2>
<div id="chat"></div>
<input id="msg" placeholder="Type message...">
<button onclick="send()">Send</button>
<audio id="soundPlayer" hidden></audio>
<script src="https://cdn.socket.io/4.0.0/socket.io.min.js"></script>
<script>
var socket = io();
socket.on('receive_message', function(data) {
    const d = document.createElement('div');
    d.innerHTML = `<b style="color:${data.color}">${data.user}</b>: ${data.text}`;
    document.getElementById('chat').appendChild(d);
});
socket.on('play_sound', function(data) {
    const player = document.getElementById("soundPlayer");
    player.src = data.url;
    player.play();
});
function send() {
    const val = document.getElementById('msg').value;
    if (val) socket.emit('send_message', {text: val});
    document.getElementById('msg').value = '';
}
</script>
"""

ADMIN_HTML = BASE_CSS + """
<h2>Admin Panel</h2>
<ul>
    <li><a href="/admin/colorchat"><button>ColorChat (Red)</button></a></li>
    <li><form method="post" action="/admin/ban"><input name="ip" placeholder="IP to ban"><button>Ban hammer</button></form></li>
    <li><form method="post" action="/admin/unban"><input name="ip" placeholder="IP to unban"><button>Unbanner</button></form></li>
    <li><a href="/admin/clearchat"><button>ClearChat</button></a></li>
    <li><a href="/admin/shutdown"><button>Shutdown</button></a></li>
    <li><a href="/admin/toggle"><button>Toggle Light/Dark</button></a></li>
    <li>
        <form action="/admin/playsound" method="post" enctype="multipart/form-data">
            <input type="file" name="sound" accept="audio/*">
            <button>PlaySound</button>
        </form>
    </li>
</ul>
"""

if __name__ == '__main__':
    os.makedirs('static', exist_ok=True)
    socketio.run(app, host='0.0.0.0', port=5000)
