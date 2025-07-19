from flask import Flask, render_template_string, request, redirect, url_for, session, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app)
UPLOAD_FOLDER = 'static/sounds'
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

chat_log = []  # Format: {'username':..., 'text':..., 'color':..., 'timestamp':...}
banned_ips = set()
shutdown = False
dark_mode = True

def is_allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Templates
lander_page = '''
<!DOCTYPE html>
<html><head><title>Lander</title></head>
<body style="background:black; color:white; font-family:sans-serif;">
<h2>Enter Secret Phrase</h2>
<form method="POST"><input name="phrase" autofocus style="padding:8px;"><button style="padding:8px;">Enter</button></form>
</body></html>
'''

username_page = '''
<!DOCTYPE html>
<html><head><title>Username</title></head>
<body style="background:black; color:white; font-family:sans-serif;">
<h2>Choose a Username</h2>
<form method="POST"><input name="username" autofocus style="padding:8px;"><button style="padding:8px;">Enter</button></form>
</body></html>
'''

chat_page = '''
<!DOCTYPE html>
<html>
<head>
    <title>FriendGroup Chat</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.7.2/socket.io.min.js"></script>
    <style>
        body { background-color: #121212; color: white; font-family: sans-serif; padding: 20px; }
        input, button {
            padding: 10px; border: none; border-radius: 10px; margin: 5px;
        }
        input { width: 60%; background: #222; color: white; }
        button { background: #333; color: white; cursor: pointer; }
        button:hover { background: #555; }
        #chat { max-height: 70vh; overflow-y: auto; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div id="chat"></div>
    <form id="msgform">
        <input id="msg" autocomplete="off" placeholder="Type a message...">
        <button>Send</button>
    </form>
    <script>
        var socket = io();
        var myName = "{{username}}";
        socket.on('connect', () => {
            socket.emit('join', myName);
        });
        socket.on('message', data => {
            const p = document.createElement("p");
            p.style.color = data.color || "white";
            p.innerText = `${data.username}: ${data.text}`;
            document.getElementById("chat").appendChild(p);
        });
        socket.on('play_audio', url => {
            const audio = new Audio(url);
            audio.play();
        });
        document.getElementById("msgform").onsubmit = e => {
            e.preventDefault();
            const msg = document.getElementById("msg").value;
            socket.emit("chat", {username: myName, text: msg});
            document.getElementById("msg").value = "";
        };
    </script>
</body>
</html>
'''

admin_page = '''
<!DOCTYPE html>
<html>
<head><title>Admin Panel</title></head>
<body style="background:black; color:white; font-family:sans-serif; padding:20px;">
<h1>Admin Panel</h1>
<ul>
  <li><a href="/FriendGroup?color=red">ColorChat (Red)</a></li>
  <li><form method="POST" action="/admin/ban"><input name="ip"><button>Ban</button></form></li>
  <li><form method="POST" action="/admin/unban"><input name="ip"><button>Unban</button></form></li>
  <li><form method="POST" action="/admin/clear"><button>Clear Chat</button></form></li>
  <li><form method="POST" action="/admin/shutdown"><button>Toggle Shutdown</button></form></li>
  <li><form method="POST" action="/admin/toggle"><button>Toggle Dark/Light Mode</button></form></li>
  <li>
    <form method="POST" action="/admin/sound" enctype="multipart/form-data">
      <input type="file" name="sound">
      <button>PlaySound</button>
    </form>
  </li>
</ul>
</body>
</html>
'''

@app.route('/')
def root(): return redirect('/lander')

@app.route('/lander', methods=['GET', 'POST'])
def lander():
    if request.method == 'POST':
        phrase = request.form.get('phrase', '')
        if phrase == 'sharktooth':
            return redirect('/admin')
        elif phrase == 'TheFans':
            return redirect('/usrname')
    return render_template_string(lander_page)

@app.route('/usrname', methods=['GET', 'POST'])
def usrname():
    if request.method == 'POST':
        session['username'] = request.form['username']
        return redirect('/FriendGroup')
    return render_template_string(username_page)

@app.route('/FriendGroup')
def chat():
    if shutdown or request.remote_addr in banned_ips:
        return "Access Denied", 403
    session['color'] = request.args.get('color', 'white')
    return render_template_string(chat_page, username=session.get('username', 'Guest'))

@app.route('/admin')
def admin(): return render_template_string(admin_page)

@app.route('/admin/ban', methods=['POST'])
def ban():
    banned_ips.add(request.form['ip'])
    return redirect('/admin')

@app.route('/admin/unban', methods=['POST'])
def unban():
    banned_ips.discard(request.form['ip'])
    return redirect('/admin')

@app.route('/admin/clear', methods=['POST'])
def clear_chat():
    global chat_log
    chat_log = []
    return redirect('/admin')

@app.route('/admin/shutdown', methods=['POST'])
def shutdown_toggle():
    global shutdown
    shutdown = not shutdown
    return redirect('/admin')

@app.route('/admin/toggle', methods=['POST'])
def toggle_mode():
    global dark_mode
    dark_mode = not dark_mode
    return redirect('/admin')

@app.route('/admin/sound', methods=['POST'])
def play_sound():
    file = request.files.get('sound')
    if file and is_allowed(file.filename):
        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)
        socketio.emit('play_audio', f'/{path}')
    return redirect('/admin')

@socketio.on('join')
def on_join(name):
    print(f"{name} joined.")

@socketio.on('chat')
def on_chat(data):
    now = datetime.utcnow()
    # Remove expired messages
    global chat_log
    chat_log = [msg for msg in chat_log if now - msg['timestamp'] < timedelta(hours=10)]

    message = {
        'username': data['username'],
        'text': data['text'],
        'color': session.get('color', 'white'),
        'timestamp': now
    }
    chat_log.append(message)
    emit('message', message, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5050)
