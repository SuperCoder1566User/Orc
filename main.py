from flask import Flask, request, redirect, render_template_string, make_response, send_file
import os
import time
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)

# Storage
messages = []
users = {}
banned_ips = set()
ban_messages = {}
username_ip_map = {}
broadcasts = []
admin_only_mode = False
dark_mode = False

# Settings
CHAT_EXPIRY_SECONDS = 36000  # 10 hours

html_base = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{{ title }}</title>
    <style>
        body {
            background-color: {% if dark %}#121212{% else %}#ffffff{% endif %};
            color: {% if dark %}#ffffff{% else %}#000000{% endif %};
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 20px;
        }
        input[type="text"], input[type="file"] {
            border-radius: 10px;
            padding: 8px;
            margin: 5px;
            border: 1px solid #ccc;
        }
        button {
            border-radius: 10px;
            padding: 10px;
            margin: 5px;
            background-color: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
        }
        button:hover {
            background-color: #45a049;
        }
        .message {
            margin-bottom: 10px;
        }
        .broadcast {
            font-size: 18px;
            font-weight: bold;
            background-color: yellow;
            color: black;
            padding: 5px;
            border-radius: 5px;
        }
        .admin {
            font-weight: bold;
            font-size: 18px;
        }
        .red {
            color: red;
        }
    </style>
</head>
<body>
<h1>{{ title }}</h1>
{{ body }}
</body>
</html>
'''

def current_time():
    return time.time()

def cleanup_expired():
    cutoff = current_time() - CHAT_EXPIRY_SECONDS
    global messages
    messages = [m for m in messages if m['timestamp'] > cutoff]

def is_banned(ip):
    return ip in banned_ips

@app.route('/')
def index():
    return redirect('/lander')

@app.route('/lander', methods=['GET', 'POST'])
def lander():
    ip = request.remote_addr
    if request.method == 'POST':
        phrase = request.form.get('phrase')
        if phrase == 'TheFans':
            return redirect('/usrname')
        elif phrase == 'sharktooth':
            return redirect('/admin')
    return render_template_string(html_base, title="Enter Secret Phrase", dark=dark_mode, body="""
        <form method="POST">
            <input type="text" name="phrase" placeholder="Secret Phrase">
            <button type="submit">Enter</button>
        </form>
    """)

@app.route('/usrname', methods=['GET', 'POST'])
def usrname():
    if request.method == 'POST':
        uname = request.form.get('uname')
        resp = make_response(redirect('/FriendGroup'))
        resp.set_cookie('username', uname)
        username_ip_map[uname] = request.remote_addr
        return resp
    return render_template_string(html_base, title="Choose Username", dark=dark_mode, body="""
        <form method="POST">
            <input type="text" name="uname" placeholder="Username">
            <button type="submit">Join</button>
        </form>
    """)

@app.route('/FriendGroup', methods=['GET', 'POST'])
def chat():
    ip = request.remote_addr
    if admin_only_mode and ip not in banned_ips and request.cookies.get('username') != 'admin':
        return redirect('/lander')
    if is_banned(ip):
        msg = ban_messages.get(ip, "You are banned.")
        return render_template_string(html_base, title="Banned", dark=dark_mode, body=f"<p>{msg}</p>")

    uname = request.cookies.get('username')
    if not uname:
        return redirect('/usrname')

    if request.method == 'POST':
        content = request.form.get('msg')
        messages.append({'user': uname, 'msg': content, 'timestamp': current_time(), 'admin': uname=='admin'})
    cleanup_expired()
    all_msgs = '<br>'.join(
        [f"<div class='message {'admin' if m['admin'] else ''}'><b class='{'admin' if m['admin'] else ''}'>{m['user']}:</b> {m['msg']}</div>" for m in messages] +
        [f"<div class='broadcast'>{b}</div>" for b in broadcasts]
    )
    return render_template_string(html_base, title="Chat Room", dark=dark_mode, body=f"""
        <form method="POST">
            <input type="text" name="msg" placeholder="Your Message">
            <button type="submit">Send</button>
        </form>
        <hr>
        {all_msgs}
    """)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    global admin_only_mode, dark_mode
    ip = request.remote_addr
    if request.method == 'POST':
        action = request.form.get('action')
        uname = request.form.get('target')
        msg = request.form.get('broadcast')
        reason = request.form.get('reason')

        if action == 'ColorChat':
            resp = make_response(redirect('/FriendGroup'))
            resp.set_cookie('username', uname)
            messages.append({'user': uname, 'msg': 'joined as admin.', 'timestamp': current_time(), 'admin': True})
            return resp
        elif action == 'Ban':
            ip_to_ban = username_ip_map.get(uname)
            if ip_to_ban:
                banned_ips.add(ip_to_ban)
                ban_messages[ip_to_ban] = reason or "Banned."
        elif action == 'Unban':
            ip_to_unban = username_ip_map.get(uname)
            if ip_to_unban:
                banned_ips.discard(ip_to_unban)
                ban_messages.pop(ip_to_unban, None)
        elif action == 'ClearChat':
            messages.clear()
        elif action == 'Shutdown':
            admin_only_mode = not admin_only_mode
        elif action == 'Toggle':
            dark_mode = not dark_mode
        elif action == 'Broadcast' and msg:
            broadcasts.append(msg)

    user_list = '<br>'.join(f"{u}: {ip}" for u, ip in username_ip_map.items())
    return render_template_string(html_base, title="Admin Panel", dark=dark_mode, body=f"""
        <form method="POST">
            <input type="text" name="target" placeholder="Username">
            <button name="action" value="ColorChat">ColorChat</button><br>
            <input type="text" name="reason" placeholder="Ban Reason">
            <button name="action" value="Ban">Ban hammer</button>
            <button name="action" value="Unban">Unbanner</button><br>
            <button name="action" value="ClearChat">ClearChat</button>
            <button name="action" value="Shutdown">Shutdown</button>
            <button name="action" value="Toggle">Toggle</button><br>
            <input type="text" name="broadcast" placeholder="Broadcast Message">
            <button name="action" value="Broadcast">Broadcast</button>
        </form>
        <hr>
        <h3>Username-IP Map:</h3>
        {user_list}
    """)

if __name__ == '__main__':
    app.run(debug=True, port=5050)
