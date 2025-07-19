from flask import Flask, render_template_string, request, redirect, session, send_from_directory
from flask_socketio import SocketIO, emit
import os
import uuid
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app)

# Data
chat_log = []
users = {}
banned_ips = {}
shutdown_mode = False
dark_mode = True
admin_ip = ""
leaderboard = {}
ip_user_map = {}

# Templates
html_base = """
<!DOCTYPE html>
<html>
<head>
    <title>{{ title }}</title>
    <style>
        body {{
            background-color: {{ 'black' if dark else 'white' }};
            color: {{ 'white' if dark else 'black' }};
            font-family: Arial, sans-serif;
        }}
        input, button, textarea {{
            border-radius: 12px;
            padding: 10px;
            margin: 5px;
            border: none;
            font-size: 16px;
        }}
        button {{
            background-color: #555;
            color: white;
            cursor: pointer;
        }}
        .admin {{
            font-weight: bold;
            font-size: 18px;
            color: red;
        }}
        .broadcast {{
            background-color: yellow;
            color: black;
            font-size: 20px;
            font-weight: bold;
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <h1>{{ title }}</h1>
    {{ body | safe }}
</body>
</html>
"""

# Route order:
@app.route("/")
def index():
    return redirect("/lander")

@app.route("/lander", methods=["GET", "POST"])
def lander():
    if request.method == "POST":
        phrase = request.form.get("phrase")
        if phrase == "TheFans":
            return redirect("/usrname")
        elif phrase == "sharktooth":
            session['admin'] = True
            return redirect("/admin")
    return render_template_string(html_base, title="Enter Secret Phrase", dark=dark_mode, body="""
        <form method="POST">
            <input name="phrase" placeholder="Secret Phrase">
            <button type="submit">Enter</button>
        </form>
    """)

@app.route("/usrname", methods=["GET", "POST"])
def usrname():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if username:
            session['username'] = username
            session['password'] = password  # Add password protection if needed later
            return redirect("/FriendGroup")
    return render_template_string(html_base, title="Choose Username", dark=dark_mode, body="""
        <form method="POST">
            <input name="username" placeholder="Username">
            <input name="password" placeholder="Password (optional)">
            <button type="submit">Join</button>
        </form>
    """)

@app.route("/FriendGroup")
def chatroom():
    ip = request.remote_addr
    if ip in banned_ips:
        return render_template_string(html_base, title="Banned", dark=dark_mode, body=f"<p>You are banned. Reason: {banned_ips[ip]}</p>")
    if shutdown_mode and not session.get("admin"):
        return redirect("/lander")
    return render_template_string(html_base, title="Group Chat", dark=dark_mode, body="""
        <div id="chatbox" style="height:300px;overflow:auto;border:1px solid gray;padding:10px;margin:10px 0;"></div>
        <form id="chatform">
            <input id="msg" placeholder="Type your message..." autocomplete="off">
            <button>Send</button>
        </form>
        <script src="https://cdn.socket.io/4.3.2/socket.io.min.js"></script>
        <script>
            var socket = io();
            var chatbox = document.getElementById("chatbox");
            socket.on("chat", function(msg) {
                var div = document.createElement("div");
                div.innerHTML = msg;
                chatbox.appendChild(div);
                chatbox.scrollTop = chatbox.scrollHeight;
            });
            socket.on("broadcast", function(msg) {
                var div = document.createElement("div");
                div.className = "broadcast";
                div.innerText = msg;
                chatbox.appendChild(div);
            });
            document.getElementById("chatform").onsubmit = function(e) {
                e.preventDefault();
                var msg = document.getElementById("msg").value;
                socket.emit("chat", msg);
                document.getElementById("msg").value = "";
            };
        </script>
    """)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("admin"):
        return redirect("/lander")
    global dark_mode, shutdown_mode
    ip_user_list = "<br>".join([f"{ip} → {usr}" for ip, usr in ip_user_map.items()])
    return render_template_string(html_base, title="Admin Panel", dark=dark_mode, body=f"""
        <form method="POST" enctype="multipart/form-data">
            <button name="action" value="ColorChat">ColorChat</button>
            <input name="colorchat_user" placeholder="Username"><br>
            <button name="action" value="Ban">Ban hammer</button>
            <input name="ban_user" placeholder="Username to Ban">
            <input name="ban_msg" placeholder="Custom Ban Message"><br>
            <button name="action" value="Unban">Unbanner</button>
            <input name="unban_user" placeholder="Username to Unban"><br>
            <button name="action" value="ClearChat">ClearChat</button>
            <button name="action" value="Shutdown">Shutdown</button>
            <button name="action" value="Toggle">Toggle Theme</button><br><br>
            <input name="broadcast_msg" placeholder="Broadcast Message">
            <button name="action" value="Broadcast">Broadcast</button>
        </form>
        <hr><b>Connected Users:</b><br>{ip_user_list}
    """)

@app.route("/admin", methods=["POST"])
def admin_post():
    action = request.form.get("action")
    global dark_mode, shutdown_mode, chat_log

    if action == "ColorChat":
        user = request.form.get("colorchat_user")
        if user:
            session['username'] = user
            session['admin'] = True
            session['color'] = "red"
            return redirect("/FriendGroup")
    elif action == "Ban":
        user = request.form.get("ban_user")
        reason = request.form.get("ban_msg", "You are banned.")
        for ip, usr in ip_user_map.items():
            if usr == user:
                banned_ips[ip] = reason
    elif action == "Unban":
        user = request.form.get("unban_user")
        for ip, usr in list(ip_user_map.items()):
            if usr == user and ip in banned_ips:
                del banned_ips[ip]
    elif action == "ClearChat":
        chat_log.clear()
    elif action == "Shutdown":
        shutdown_mode = not shutdown_mode
    elif action == "Toggle":
        dark_mode = not dark_mode
    elif action == "Broadcast":
        msg = request.form.get("broadcast_msg")
        socketio.emit("broadcast", msg)

    return redirect("/admin")

@socketio.on("chat")
def handle_chat(msg):
    username = session.get("username", "Anonymous")
    ip = request.remote_addr
    ip_user_map[ip] = username

    # Leaderboard
    leaderboard[username] = leaderboard.get(username, 0) + 1

    admin_class = "admin" if session.get("admin") else ""
    msg_html = f"<span class='{admin_class}'>{username}</span>: {msg}" if not session.get("color") else f"<span style='color:{session['color']}'>{username}</span>: {msg}"
    emit("chat", msg_html, broadcast=True)

# Run App
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
