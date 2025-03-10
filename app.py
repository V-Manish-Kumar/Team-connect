from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_login import login_user, LoginManager, login_required, current_user, logout_user, UserMixin
from flask_socketio import SocketIO, join_room, leave_room, send
from datetime import datetime
import random
import os
from string import ascii_uppercase
import secrets
from flask_cors import CORS
import google.generativeai as genai
from traceback import format_exc
from functools import wraps

# App setup remains unchanged
app = Flask(__name__)

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Your_Password'
app.config['MYSQL_DB'] = 'flask_login'
app.config['UPLOAD_FOLDER'] = 'file_uploads'
app.config['SECRET_KEY'] = secrets.token_hex(16)

mysql = MySQL(app)
socketio = SocketIO(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User and ErrorLog classes
class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

class ErrorLog:
    def __init__(self, id, timestamp, error_message, stack_trace, endpoint, admin_id):
        self.id = id
        self.timestamp = timestamp
        self.error_message = error_message
        self.stack_trace = stack_trace
        self.endpoint = endpoint
        self.admin_id = admin_id

@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    cur.close()
    if user:
        return User(id=user[0], username=user[1], email=user[2])
    return None

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            flash("You must be logged in as an admin to access this page.", "error")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

# Error logging function
def log_error(error_message, endpoint, admin_id=None):
    """Log errors to database only"""
    stack_trace = format_exc()
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO error_logs (timestamp, error_message, stack_trace, endpoint, admin_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (datetime.now(), str(error_message), stack_trace, endpoint, admin_id))
        mysql.connection.commit()
        cur.close()
    except Exception as db_error:
        print(f"Failed to log to database: {db_error}\nOriginal error: {error_message}\n{stack_trace}")

# Admin dashboard (without error logs)
@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    return render_template('admin_dashboard.html', admin_name=session['admin_name'])

# New route for error logs
@app.route('/admin/error_logs')
@admin_required
def error_logs():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM error_logs ORDER BY timestamp DESC LIMIT 50")
        error_logs = [ErrorLog(row[0], row[1], row[2], row[3], row[4], row[5]) 
                     for row in cur.fetchall()]
        cur.close()
        return render_template('error_logs.html', error_logs=error_logs)
    except Exception as e:
        log_error(f"Failed to load error logs: {e}", "/admin/error_logs", session.get('admin_id'))
        flash('Error loading error logs', 'error')
        return render_template('error_logs.html', error_logs=[])

# Admin login with error logging
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        try:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM admin_users WHERE email = %s", (email,))
            admin = cur.fetchone()
            cur.close()

            if admin and check_password_hash(admin[3], password):
                session['admin_id'] = admin[0]
                session['admin_name'] = admin[1]
                flash('Admin login successful!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid email or password.', 'error')
        except Exception as e:
            log_error(f"Admin login failed: {e}", "/admin/login", session.get('admin_id'))
            flash('Error during login', 'error')
    
    return render_template('admin_login.html')

@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "INSERT INTO admin_users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_password)
            )
            mysql.connection.commit()
            flash('Admin registered successfully!', 'success')
            return redirect(url_for('admin_register'))
        except Exception as e:
            flash('Error: Unable to register admin. Email might already exist.', 'error')
            print(e)
        finally:
            cur.close()
    
    return render_template('admin_register.html')

@app.route('/admin/manage_users', methods=['GET', 'POST'])
@admin_required
def manage_users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users")
    users = cur.fetchall()
    cur.close()
    return render_template('manage_users.html', users=users)

@app.route('/admin/add_user', methods=['GET', 'POST'])
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (username, email, hashed_password)
            )
            mysql.connection.commit()
            flash('User added successfully!', 'success')
            return redirect(url_for('manage_users'))
        except Exception as e:
            flash('Error: Unable to add user. Email might already exist.', 'error')
            print(e)
        finally:
            cur.close()
    
    return render_template('add_user.html')

@app.route('/admin/edit_user/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_user(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (id,))
    user = cur.fetchone()
    cur.close()
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password) if password else user[3]

        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE users SET username = %s, email = %s, password = %s WHERE id = %s
        """, (username, email, hashed_password, id))
        mysql.connection.commit()
        cur.close()

        flash('User updated successfully!', 'success')
        return redirect(url_for('manage_users'))

    return render_template('edit_user.html', user=user)

@app.route('/admin/delete_user/<int:id>', methods=['GET', 'POST'])
@admin_required
def delete_user(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM users WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('manage_users'))



@app.route('/')
def welcome():
    if current_user.is_authenticated: 
        return redirect(url_for('dashboard'))
    return render_template('welcome.html')

@app.route('/learn') 
def learn():
    return render_template('learn.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        
        if user and check_password_hash(user[3], password):
            user_obj = User(id=user[0], username=user[1], email=user[2])
            login_user(user_obj)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        hashed_password = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                       (username, email, hashed_password))
            mysql.connection.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Email already exists', 'error')
        finally:
            cur.close()
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required  
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("SELECT username FROM users WHERE id = %s", (current_user.id,))
    username = cur.fetchone()[0]
    cur.close()
    
    return render_template('dashboard.html', username=username)


@app.route('/logout') 
def logout():
    logout_user()  
    return redirect(url_for('login'))

@app.route("/meeting")
@login_required
def meeting():
    return render_template("meeting.html", username=current_user.username)

@app.route("/join", methods=["GET", "POST"])
@login_required
def join():
    if request.method == "POST":
        room_id = request.form.get("roomID")
        return redirect(f"/meeting?roomID={room_id}")

    return render_template("join.html", username=current_user.username)

@app.route('/create_room', methods=['GET', 'POST'])
@login_required
def create_room():
    if request.method == 'POST':
        room_name = request.form.get('room_name')
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO chat_rooms (name, created_by) VALUES (%s, %s)",
                   (room_name, current_user.id))
        mysql.connection.commit()
        room_id = cur.lastrowid
        cur.close()
        flash('Room created successfully!', 'success')
        return redirect(url_for('chat_room', room_id=room_id))
    return render_template('create_room.html')

rooms = {}

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        
        if code not in rooms:
            break
    return code

def save_message_to_db(room_code, username, message, message_type='message'):
    cur = mysql.connection.cursor()
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur.execute("""
        INSERT INTO messages (room_code, username, message, timestamp, message_type) 
        VALUES (%s, %s, %s, %s, %s)
    """, (room_code, username, message, current_time, message_type))
    mysql.connection.commit()
    cur.close()
    return current_time

def get_or_create_room(room_code):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM rooms WHERE room_code = %s", [room_code])
    room = cur.fetchone()
    
    if not room:
        cur.execute("INSERT INTO rooms (room_code, created_at) VALUES (%s, NOW())", [room_code])
        mysql.connection.commit()
    
    cur.close()
    
    if room_code not in rooms:
        rooms[room_code] = {"members": 0, "messages": []}

def get_room_messages(room_code):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT username, message, timestamp, message_type 
        FROM messages 
        WHERE room_code = %s 
        ORDER BY timestamp
    """, [room_code])
    messages = []
    for msg in cur.fetchall():
        messages.append({
            "name": msg[0],
            "message": msg[1],
            "timestamp": msg[2].strftime('%H:%M:%S'),
            "type": msg[3]
        })
    cur.close()
    return messages

@app.route("/chat", methods=["POST", "GET"])
@login_required
def home():
    if request.method == "POST":
        name = current_user.username 
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if join != False and not code:
            return render_template("home1.html", error="Please enter a room code.", code=code)

        room = code
        if create != False:
            room = generate_unique_code(4)
            get_or_create_room(room)
        else:
            cur = mysql.connection.cursor()
            cur.execute("SELECT * FROM rooms WHERE room_code = %s", [code])
            if not cur.fetchone():
                cur.close()
                return render_template("home1.html", error="Room does not exist.", code=code)
            cur.close()
            get_or_create_room(room)

        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home1.html")

@app.route("/chatroom")
@login_required
def room():
    room = session.get("room")
    if room is None:
        return redirect(url_for("home"))
    
    get_or_create_room(room)
    messages = get_room_messages(room)
    return render_template("room.html", code=room, messages=messages)

@socketio.on("message")
def message(data):
    if not current_user.is_authenticated:
        return
        
    room = session.get("room")
    if room not in rooms:
        return

    name = current_user.username
    current_time = save_message_to_db(room, name, data["data"])
    
    content = {
        "name": name,
        "message": data["data"],
        "timestamp": datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S'),
        "type": "message"
    }
    
    send(content, to=room)

@socketio.on("connect")
def connect(auth):
    if not current_user.is_authenticated:
        return
        
    room = session.get("room")
    name = current_user.username
    if not room or not name:
        return
        
    join_room(room)
    current_time = save_message_to_db(room, name, "has entered the room", "join")
    
    message_content = {
        "name": name,
        "message": "has entered the room",
        "timestamp": datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S'),
        "type": "join"
    }
    send(message_content, to=room)
    rooms[room]["members"] += 1

@socketio.on("disconnect")
def disconnect():
    if not current_user.is_authenticated:
        return
        
    room = session.get("room")
    name = current_user.username
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1

    current_time = save_message_to_db(room, name, "has left the room", "leave")
    message_content = {
        "name": name,
        "message": "has left the room",
        "timestamp": datetime.strptime(current_time, '%Y-%m-%d %H:%M:%S').strftime('%H:%M:%S'),
        "type": "leave"
    }
    send(message_content, to=room)
    print(f"{name} has left the room {room}")

CORS(app)

genai.configure(api_key="Your_gemini_key")

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-pro",
    generation_config=generation_config,
)

chat_session = None

@app.route('/start-chat', methods=['POST'])
def start_chat():
    global chat_session
    chat_session = model.start_chat(history=[])
    return jsonify({"message": "Chat session started"})

@app.route('/send-message', methods=['POST'])
def send_message():
    global chat_session
    if not chat_session:
        chat_session = model.start_chat(history=[])
    
    data = request.json
    user_message = data.get('message')
    
    try:
        response = chat_session.send_message(user_message)
        return jsonify({"response": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route("/aibot")
@login_required
def aibot():
    return render_template("chatbot.html")



@app.route('/task')
@login_required
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM tasks")
    tasks = cur.fetchall()
    cur.close()
    return render_template('task.html', tasks=tasks, get_remaining_time=get_remaining_time)

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_task():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        status = request.form['status']
        deadline = request.form['deadline']
        
        deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M') if deadline else None

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO tasks (title, description, status, deadline) VALUES (%s, %s, %s, %s)", 
                   (title, description, status, deadline))
        mysql.connection.commit()
        cur.close()

        return redirect(url_for('index'))
    return render_template('add_task.html')

@app.route('/delete/<int:id>')
@login_required
def delete_task(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM tasks WHERE id = %s", (id,))
    mysql.connection.commit()
    cur.close()
    return redirect(url_for('index'))

@app.route('/update/<int:id>', methods=['GET', 'POST'])
@login_required
def update_task(id):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        status = request.form['status']
        deadline = request.form['deadline']
        deadline = datetime.strptime(deadline, '%Y-%m-%dT%H:%M') if deadline else None

        cur.execute("UPDATE tasks SET title = %s, description = %s, status = %s, deadline = %s WHERE id = %s", 
                   (title, description, status, deadline, id))
        mysql.connection.commit()
        cur.close()
        return redirect(url_for('index'))

    cur.execute("SELECT * FROM tasks WHERE id = %s", (id,))
    task = cur.fetchone()
    cur.close()
    return render_template('add_task.html', task=task)

def get_remaining_time(deadline):
    if deadline:
        now = datetime.now()
        remaining = deadline - now
        if remaining.total_seconds() <= 0:
            return "Overdue"
        days = remaining.days
        hours = remaining.seconds // 3600
        minutes = (remaining.seconds % 3600) // 60
        if days > 0:
            return f"{days} days remaining"
        elif hours > 0:
            return f"{hours} hours remaining"
        else:
            return f"{minutes} minutes remaining"
    return "No deadline set"

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/file')
@login_required
def fileshare():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM files ORDER BY upload_date DESC")
    files = cur.fetchall()
    cur.close()
    return render_template('share_file.html', files=files)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'file' not in request.files:
        flash('No file selected')
        return redirect(url_for('fileshare'))
    
    file = request.files['file']
    if file.filename == '':
        flash('No file selected')
        return redirect(url_for('fileshare'))

    if file:
        filename = secure_filename(file.filename)
        unique_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        
        cur = mysql.connection.cursor()
        cur.execute('''
            INSERT INTO files (filename, original_filename, upload_date, file_size)
            VALUES (%s, %s, %s, %s)
        ''', (unique_filename, filename, datetime.now(), os.path.getsize(file_path)))
        mysql.connection.commit()
        cur.close()
        
        flash('File uploaded successfully')
        return redirect(url_for('fileshare'))
    
@app.route('/delete/<filename>')
@login_required
def delete_file(filename):
    cur = mysql.connection.cursor()
    cur.execute("SELECT filename FROM files WHERE filename = %s", (filename,))
    result = cur.fetchone()
    
    if result:
        cur.execute("DELETE FROM files WHERE filename = %s", (filename,))
        mysql.connection.commit()
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            flash('File deleted successfully')
        else:
            flash('File not found in storage')
    else:
        flash('File not found in database')
    
    cur.close()
    return redirect(url_for('fileshare'))

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    cur = mysql.connection.cursor()
    cur.execute("SELECT original_filename FROM files WHERE filename = %s", (filename,))
    result = cur.fetchone()
    
    if result:
        original_filename = result[0]
        cur.execute("UPDATE files SET download_count = download_count + 1 WHERE filename = %s", (filename,))
        mysql.connection.commit()
        cur.close()
        
        return send_file(
            os.path.join(app.config['UPLOAD_FOLDER'], filename),
            as_attachment=True,
            download_name=original_filename
        )
    
    cur.close()
    flash('File not found')
    return redirect(url_for('fileshare'))


if __name__ == '__main__':
    socketio.run(app, debug=True)
