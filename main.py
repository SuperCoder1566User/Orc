from flask import Flask, request, render_template_string, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///chatapp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------- DATABASE MODELS ----------
class Config(db.Model):
    key = db.Column(db.String, primary_key=True)
    value = db.Column(db.String)

class User(db.Model):
    username = db.Column(db.String, primary_key=True)
    ip = db.Column(db.String)
    is_admin = db.Column(db.Boolean, default=False)
    color = db.Column(db.String, default="white")

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user = db.Column(db.String)
    text = db.Column(db.String)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class Ban(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip = db.Column(db.String, unique=True)
    message = db.Column(db.String, default="You are banned.")

class Broadcast(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

# ---------- HELPERS ----------
def get_config(key, default):
    item = Config.query.get(key)
    return item.value if item else default

def set_config(key, value):
    item = Config.query.get(key)
    if item:
        item.value = value
    else:
        item = Config(key=key, value=value)
        db.session.add(item)
    db.session.commit()

def expire_messages():
    cutoff = datetime.utcnow() - timedelta(hours=10)
    Message.query.filter(Message.timestamp < cutoff).delete()
    db.session.commit()

def current_user():
    uname = session.get('username')
    return User.query.get(uname) if uname else None

def is_banned(ip):
    return Ban.query.filter_by(ip=ip).first()

# ---------- ROUTES ----------
@app.route('/')
def home():
    return redirect('/lander')

@app.route('/lander', methods=['GET', 'POST'])
def lander():
    if get_config('shutdown', 'off') == 'on':
        return "Site is currently disabled"

    if request.method == 'POST':
        phrase = request.form['phrase']
        if phrase == get_config('user_phrase', 'TheFans'):
            return redirect('/usrname')
        if phrase == get_config('admin_phrase', 'sharktooth'):
            session['admin'] = True
            return redirect('/admin')

    return render_template_string(TPL_BASE, title="Enter Phrase", body="""
        <form method='POST'>
            <input name='phrase' placeholder='Secret Phrase'><br>
            <button>Enter</button>
        </form>
    """)

@app.route('/usrname', methods=['GET', 'POST'])
def usrname():
    if request.method == 'POST':
        uname = request.form['username']
        ip = request.remote_addr
        if not User.query.get(uname):
            user = User(username=uname, ip=ip)
            db.session.add(user)
            db.session.commit()
        session['username'] = uname
        return redirect('/chat')

    return render_template_string(TPL_BASE, title="Chat Room", body="""
        {% for b in bcasts %}
            <div class='broadcast'>{{ b.text }}</div>
        {% endfor %}
        <form method='POST'>
            <input name='msg' placeholder='Message'>
            <button>Send</button>
        </form>
        {% for m in msgs %}
            <div style="color: {{ 'red' if m.user == config('colorchat', '') else 'white' }};">
                <b style="{{ 'font-weight:bold;font-size:1.2em;' if m.user == config('adminuser', '') else '' }}">
                    {{ m.user }}:
                </b> {{ m.text }}
            </div>
        {% endfor %}
    """, msgs=msgs, bcasts=bcasts, config=get_config)




@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'username' not in session:
        return redirect('/lander')

    user = current_user()
    if not user:
        return redirect('/usrname')

    ban = is_banned(user.ip)
    if ban:
        return ban.message

    if request.method == 'POST':
        msg = request.form.get('msg')
        if msg:
            m = Message(user=user.username, text=msg)
            db.session.add(m)
            db.session.commit()

    expire_messages()
    msgs = Message.query.order_by(Message.timestamp).all()
    bcasts = Broadcast.query.order_by(Broadcast.timestamp).all()
    return render_template_string(TPL_BASE, title="Chat Room", body="""
        {% for b in bcasts %}
            <div class='broadcast'>{{ b.text }}</div>
        {% endfor %}
        <form method='POST'><input name='msg' placeholder='Message'><button>Send</button></form>
        {% for m in msgs %}
            <div style="color: {{ 'red' if m.user == config('colorchat', '') else 'white' }};">
                <b style="{{ 'font-weight:bold;font-size:1.2em;' if m.user == config('adminuser', '') else '' }}">
                    {{ m.user }}:
                </b> {{ m.text }}
            </div>
        {% endfor %}
    """, msgs=msgs, bcasts=bcasts, config=get_config)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('admin'):
        return redirect('/lander')

    users = User.query.all()
    bans = Ban.query.all()
    phrases = {
        'user': get_config('user_phrase', 'TheFans'),
        'admin': get_config('admin_phrase', 'sharktooth'),
        'theme': get_config('theme', 'dark'),
        'shutdown': get_config('shutdown', 'off')
    }

    if request.method == 'POST':
        f = request.form
        if f.get('set_user_phrase'):
            set_config('user_phrase', f['user_phrase'])
        if f.get('set_admin_phrase'):
            set_config('admin_phrase', f['admin_phrase'])
        if f.get('colorchat'):
            set_config('colorchat', f['color_target'])
        if f.get('broadcast'):
            db.session.add(Broadcast(text=f['broadcast_msg']))
            db.session.commit()
        if f.get('ban'):
            user = User.query.get(f['ban_user'])
            if user:
                db.session.add(Ban(ip=user.ip, message=f['ban_msg']))
                db.session.commit()
        if f.get('unban'):
            user = User.query.get(f['unban_user'])
            if user:
                Ban.query.filter_by(ip=user.ip).delete()
                db.session.commit()
        if f.get('toggle_dark'):
            set_config('theme', 'light' if phrases['theme'] == 'dark' else 'dark')
        if f.get('shutdown_toggle'):
            set_config('shutdown', 'off' if phrases['shutdown'] == 'on' else 'on')

    return render_template_string(TPL_BASE, title="Admin Panel", body=render_template_string("""
        <h3>Current Social Phrases</h3>
        User: <input name='user_phrase' value='{{phrases.user}}'>
        <button name='set_user_phrase'>Set</button><br>
        Admin: <input name='admin_phrase' value='{{phrases.admin}}'>
        <button name='set_admin_phrase'>Set</button><br><hr>

        <h3>Ban / Unban User</h3>
        <select name='ban_user'> {% for u in users %}<option>{{u.username}}</option>{% endfor %}</select>
        <input name='ban_msg' placeholder='Custom ban message'>
        <button name='ban'>Ban</button><br>
        <select name='unban_user'> {% for u in users %}<option>{{u.username}}</option>{% endfor %}</select>
        <button name='unban'>Unban</button><hr>

        <h3>ColorChat</h3>
        <input name='color_target' placeholder='Username to Red'>
        <button name='colorchat'>Set Red Chat</button><hr>

        <h3>Broadcast Message</h3>
        <input name='broadcast_msg' placeholder='Your message'>
        <button name='broadcast'>Broadcast</button><hr>

        <h3>Site Settings</h3>
        <button name='toggle_dark'>Toggle Theme</button>
        <button name='shutdown_toggle'>Toggle Shutdown Mode</button>
    """, users=users, phrases=phrases))

# ---------- TEMPLATE ----------
TPL_BASE = """
<!doctype html><html><head><style>
body { font-family: 'Segoe UI'; background: #121212; color: white; padding: 20px; }
input, select, button { border-radius: 12px; padding: 8px; margin: 5px; border: none; }
button { background: #4caf50; color: white; cursor: pointer; }
.broadcast { font-size: 18px; font-weight: bold; color: yellow; margin: 5px 0; }
</style><title>{{ title }}</title></head><body>
<h1>{{ title }}</h1>
{{ body|safe }}
</body></html>
"""

# ---------- RUN ----------
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)

