from flask import Flask, render_template_string, request, redirect, session, url_for, send_from_directory
from datetime import datetime, timedelta
import os, json, uuid, time
from werkzeug.utils import secure_filename
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'super_secret_key'

# ========== CONFIG ==========
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {'wav', 'mp3', 'ogg'}
MESSAGE_TIMEOUT = 36000  # 10 hours
admin_secret = "sharktooth"

# ========== STATE ==========
chat_messages = []
banned_ips = set()
username_ip_map = {}
dark_mode = True
shutdown = False
broadcasts = []
custom_ban_messages = {}
admin_username = "Admin"
play_sounds = []

# ========== UTILS ==========

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def is_admin():
    return session.get("is_admin", False)

def get_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)

# ========== ROUTES ==========

@app.route('/')
def home():
    return redirect('/lander')

@app.route('/lander', methods=['GET', 'POST'])
def lander():
    ip = get_ip()
    if shutdown and not is_admin():
        return "🔒 Site is currently shut down."

    if request.method == 'POST':
        phrase = request.form.get('phrase')
        if phrase == 'TheFans':
            return redirect('/usrname')
        elif phrase == admin_secret:
            session["is_admin"] = True
            return redirect('/admin')
    return render_template_string(html_base, title="Enter Secret Phrase", dark=dark_mode, body="""
        <form method="POST" class="flex flex-col gap-4 items-center">
            <input name="phrase" placeholder="Secret Phrase" class="rounded-xl p-2 w-60 text-black">
            <button class="rounded-xl bg-blue-500 px-4 py-2 text-white hover:bg-blue-700">Enter</button>
        </form>
    """)

@app.route('/usrname', methods=['GET', 'POST'])
def usrname():
    if shutdown and not is_admin():
        return "🔒 Site is currently shut down."

    if request.method == 'POST':
        username = request.form.get('username')
        if username:
            session['username'] = username
            username_ip_map[username] = get_ip()
            return redirect('/FriendGroup')
    return render_template_string(html_base, title="Choose Username", dark=dark_mode, body="""
        <form method="POST" class="flex flex-col gap-4 items-center">
            <input name="username" placeholder="Enter Username" class="rounded-xl p-2 w-60 text-black">
            <button class="rounded-xl bg-green-500 px-4 py-2 text-white hover:bg-green-700">Start Chatting</button>
        </form>
    """)

@app.route('/FriendGroup', methods=['GET', 'POST'])
def chat():
    ip = get_ip()
    username = session.get('username')

    if not username or (ip in banned_ips and not is_admin()):
        return "⛔ Access Denied."

    if request.method == 'POST':
        text = request.form.get('message')
        now = datetime.utcnow()
        if text:
            chat_messages.append({
                'user': username,
                'text': text,
                'timestamp': now.timestamp()
            })

    now = datetime.utcnow().timestamp()
    messages = [m for m in chat_messages if now - m['timestamp'] < MESSAGE_TIMEOUT]
    display_messages = "\n".join([
        f"<b style='font-size: {'1.2em' if m['user'] == admin_username else '1em'};'>{m['user']}</b>: {m['text']}"
        for m in messages
    ])
    display_broadcasts = "<br>".join([f"<div class='text-yellow-400 font-bold text-lg'>{b}</div>" for b in broadcasts])

    audio_players = "\n".join([f"<audio autoplay src='/uploads/{f}'></audio>" for f in play_sounds])

    return render_template_string(html_base, title="Group Chat", dark=dark_mode, body=f"""
        {display_broadcasts}
        {audio_players}
        <div class="mb-4">{display_messages}</div>
        <form method="POST" class="flex gap-4">
            <input name="message" class="rounded-xl p-2 w-full text-black">
            <button class="rounded-xl bg-purple-500 text-white px-4 py-2">Send</button>
        </form>
    """)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not is_admin():
        return "⛔ Forbidden"

    message = ""

    if request.method == 'POST':
        action = request.form.get('action')
        value = request.form.get('value')

        if action == 'ColorChat':
            session['username'] = f"<span style='color:red;font-weight:bold'>{value}</span>"
            return redirect('/FriendGroup')
        elif action == 'BanIP':
            banned_ips.add(username_ip_map.get(value, value))
        elif action == 'UnbanIP':
            banned_ips.discard(username_ip_map.get(value, value))
        elif action == 'ClearChat':
            chat_messages.clear()
        elif action == 'Shutdown':
            global shutdown
            shutdown = not shutdown
        elif action == 'Toggle':
            global dark_mode
            dark_mode = not dark_mode
        elif action == 'Broadcast':
            broadcasts.append(value)
        elif action == 'CustomBan':
            custom_ban_messages[username_ip_map.get(value, value)] = request.form.get('banmsg')
        elif action == 'PlaySound':
            file = request.files['soundfile']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(path)
                play_sounds.append(filename)
                message = f"✅ Uploaded {filename}"

    users_html = "".join([f"<li>{u} — {ip}</li>" for u, ip in username_ip_map.items()])

    return render_template_string(html_base, title="Admin Panel", dark=dark_mode, body=f"""
        <div class="grid gap-4">
            <form method="POST" class="flex gap-2">
                <input name="value" placeholder="Red Username" class="rounded-xl p-2 text-black">
                <button name="action" value="ColorChat" class="rounded-xl bg-red-500 text-white px-4">ColorChat</button>
            </form>
            <form method="POST" class="flex gap-2">
                <input name="value" placeholder="User/IP" class="rounded-xl p-2 text-black">
                <button name="action" value="BanIP" class="rounded-xl bg-black text-white px-4">Ban hammer</button>
                <button name="action" value="UnbanIP" class="rounded-xl bg-green-500 text-white px-4">Unbanner</button>
            </form>
            <form method="POST" class="flex gap-2">
                <button name="action" value="ClearChat" class="rounded-xl bg-yellow-400 text-black px-4">ClearChat</button>
                <button name="action" value="Shutdown" class="rounded-xl bg-gray-600 text-white px-4">Shutdown</button>
                <button name="action" value="Toggle" class="rounded-xl bg-purple-600 text-white px-4">Toggle Mode</button>
            </form>
            <form method="POST" class="flex gap-2">
                <input name="value" placeholder="Broadcast Message" class="rounded-xl p-2 text-black w-full">
                <button name="action" value="Broadcast" class="rounded-xl bg-blue-700 text-white px-4">Broadcast</button>
            </form>
            <form method="POST" enctype="multipart/form-data" class="flex gap-2">
                <input type="file" name="soundfile" class="rounded-xl text-white">
                <button name="action" value="PlaySound" class="rounded-xl bg-indigo-600 text-white px-4">PlaySound</button>
            </form>
            <div class="mt-6 text-white">
                <b>Users & IPs:</b>
                <ul>{users_html}</ul>
            </div>
            <div class="text-green-400">{message}</div>
        </div>
    """)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

# ========== HTML TEMPLATE ==========
html_base = """
<!DOCTYPE html>
<html class="{{ 'dark' if dark else '' }}">
<head>
    <title>{{ title }}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white p-10 font-sans">
    <div class="max-w-xl mx-auto">
        <h1 class="text-3xl font-bold mb-6">{{ title }}</h1>
        {{ body|safe }}
    </div>
</body>
</html>
"""

# ========== RUN ==========
if __name__ == "__main__":
    app.run(debug=True, port=5050)
