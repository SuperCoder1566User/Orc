from flask import Flask, render_template_string, request, redirect, session, url_for, send_from_directory
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "secret"
chat_messages = []
banned_ips = set()
user_ip_map = {}
shutdown_enabled = False
admin_logged_in = False
dark_mode_enabled = True
upload_folder = "static/sounds"
os.makedirs(upload_folder, exist_ok=True)

# HTML templates
lander_page = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{
      background-color: #121212;
      font-family: 'Segoe UI', sans-serif;
      color: white;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }}
    input, button {{
      border-radius: 20px;
      padding: 10px;
      border: none;
      margin: 10px;
      font-size: 16px;
    }}
  </style>
</head>
<body>
  <h2>Enter Secret Phrase:</h2>
  <form method="POST">
    <input name="phrase" placeholder="Secret phrase" required>
    <button type="submit">Enter</button>
  </form>
</body>
</html>
"""

username_page = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{
      background-color: #121212;
      font-family: 'Segoe UI', sans-serif;
      color: white;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      height: 100vh;
    }}
    input, button {{
      border-radius: 20px;
      padding: 10px;
      border: none;
      margin: 10px;
      font-size: 16px;
    }}
  </style>
</head>
<body>
  <h2>Choose a username:</h2>
  <form method="POST">
    <input name="username" placeholder="Username" required>
    <button type="submit">Continue</button>
  </form>
</body>
</html>
"""

chat_page = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{
      background-color: {bg};
      font-family: 'Segoe UI', sans-serif;
      color: {fg};
    }}
    .chat-box {{
      height: 400px;
      overflow-y: scroll;
      border: 2px solid {fg};
      padding: 10px;
      margin-bottom: 10px;
      border-radius: 20px;
    }}
    input, button {{
      border-radius: 20px;
      padding: 10px;
      border: none;
      margin: 5px;
      font-size: 16px;
    }}
  </style>
  <script>
    setInterval(() => {{
      fetch('/messages')
        .then(res => res.text())
        .then(html => {{
          document.getElementById('messages').innerHTML = html;
        }});
    }}, 1000);
  </script>
</head>
<body>
  <h2>Welcome, <span style="color:{color};">{username}</span></h2>
  <div class="chat-box" id="messages"></div>
  <form method="POST">
    <input name="msg" placeholder="Message" required>
    <button type="submit">Send</button>
  </form>
  <audio id="sound" src="/get-sound" autoplay></audio>
</body>
</html>
"""

admin_page = """
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{
      background-color: #121212;
      font-family: 'Segoe UI', sans-serif;
      color: white;
    }}
    button, input {{
      border-radius: 20px;
      padding: 10px;
      margin: 5px;
      font-size: 16px;
      border: none;
    }}
  </style>
</head>
<body>
  <h2>Admin Panel</h2>
  <form action="/admin/colorchat"><button>ColorChat</button></form>
  <form method="POST" action="/admin/ban"><input name="username" placeholder="Username to Ban"><button>Ban</button></form>
  <form method="POST" action="/admin/unban"><input name="username" placeholder="Username to Unban"><button>Unban</button></form>
  <form action="/admin/clear"><button>ClearChat</button></form>
  <form action="/admin/shutdown"><button>Shutdown</button></form>
  <form action="/admin/toggle"><button>Toggle Dark Mode</button></form>
  <form method="POST" action="/admin/sound" enctype="multipart/form-data">
    <input type="file" name="file"><button type="submit">PlaySound</button>
  </form>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def home():
    return redirect("/lander")

@app.route("/lander", methods=["GET", "POST"])
def lander():
    if request.method == "POST":
        phrase = request.form["phrase"]
        if phrase == "sharktooth":
            session["admin"] = True
            return redirect("/admin")
        elif phrase == "TheFans":
            return redirect("/usrname")
        else:
            return "Wrong Phrase", 403
    return render_template_string(lander_page)

@app.route("/usrname", methods=["GET", "POST"])
def usrname():
    if request.method == "POST":
        session["username"] = request.form["username"]
        user_ip_map[session["username"]] = request.remote_addr
        return redirect("/FriendGroup")
    return render_template_string(username_page)

@app.route("/FriendGroup", methods=["GET", "POST"])
def friend_group():
    if request.remote_addr in banned_ips or shutdown_enabled:
        return "Access Denied", 403
    if request.method == "POST":
        msg = request.form["msg"]
        chat_messages.append((session.get("username", "Guest"), msg, datetime.now()))
    now = datetime.now()
    chat_messages[:] = [m for m in chat_messages if now - m[2] < timedelta(hours=10)]
    username = session.get("username", "Guest")
    color = "red" if session.get("color") else "white"
    bg = "#121212" if dark_mode_enabled else "#FFFFFF"
    fg = "white" if dark_mode_enabled else "black"
    return render_template_string(chat_page, username=username, color=color, bg=bg, fg=fg)

@app.route("/messages")
def get_messages():
    return "<br>".join([f"<b>{u}:</b> {m}" for u, m, _ in chat_messages])

@app.route("/admin")
def admin_panel():
    if not session.get("admin"):
        return redirect("/lander")
    return render_template_string(admin_page)

@app.route("/admin/colorchat")
def colorchat():
    session["color"] = True
    return redirect("/FriendGroup")

@app.route("/admin/ban", methods=["POST"])
def ban_user():
    name = request.form["username"]
    ip = user_ip_map.get(name)
    if ip:
        banned_ips.add(ip)
    return redirect("/admin")

@app.route("/admin/unban", methods=["POST"])
def unban_user():
    name = request.form["username"]
    ip = user_ip_map.get(name)
    if ip and ip in banned_ips:
        banned_ips.remove(ip)
    return redirect("/admin")

@app.route("/admin/clear")
def clear_chat():
    chat_messages.clear()
    return redirect("/admin")

@app.route("/admin/shutdown")
def shutdown():
    global shutdown_enabled
    shutdown_enabled = True
    return redirect("/admin")

@app.route("/admin/toggle")
def toggle():
    global dark_mode_enabled
    dark_mode_enabled = not dark_mode_enabled
    return redirect("/admin")

@app.route("/admin/sound", methods=["POST"])
def upload_sound():
    file = request.files["file"]
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(upload_folder, filename))
        with open("current_sound.txt", "w") as f:
            f.write(filename)
    return redirect("/admin")

@app.route("/get-sound")
def get_sound():
    try:
        with open("current_sound.txt") as f:
            filename = f.read()
        return send_from_directory(upload_folder, filename)
    except:
        return ""

if __name__ == "__main__":
    app.run(debug=True)
