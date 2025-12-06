from flask import Flask, render_template, request, redirect, jsonify, url_for, flash, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from gtts import gTTS
import os
import time

# ================== FLASK APP ==================
app = Flask(__name__)
app.secret_key = 'supersecretkey'

# ================== DATABASE CONNECTION ==================
def get_db_connection():
    conn = sqlite3.connect('color.db')
    conn.row_factory = sqlite3.Row
    return conn

# ================== INITIALIZE TABLE ==================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL
                    )''')
    conn.commit()
    conn.close()

# ================== LOAD COLORS ==================
index = ['color', 'color_name', 'hex', 'R', 'G', 'B']
df_colors = pd.read_csv('colors.csv', names=index, header=None)

# ✅ Drop any rows where R, G, or B is NaN
df_colors = df_colors.dropna(subset=["R", "G", "B"])

# ================== COLOR DETECTION ==================
def getColorName(R, G, B):
    minimum = 10000
    cname = ""
    hex_code = ""
    for i in range(len(df_colors)):
        # Convert to int safely
        try:
            r_val = int(df_colors.loc[i, "R"])
            g_val = int(df_colors.loc[i, "G"])
            b_val = int(df_colors.loc[i, "B"])
        except:
            continue
        d = abs(R - r_val) + abs(G - g_val) + abs(B - b_val)
        if d < minimum:
            minimum = d
            cname = df_colors.loc[i, 'color_name']
            hex_code = df_colors.loc[i, 'hex']
    return cname, hex_code

# Store last color spoken (avoid repeat speech)
last_color_spoken = None

# ================== ROUTES ==================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# ================== COLOR DETECTION + AUDIO ==================
@app.route('/get_color_name', methods=['POST'])
def get_color_name():
    global last_color_spoken
    data = request.get_json()
    r = int(data['r'])
    g = int(data['g'])
    b = int(data['b'])
    lang = data.get('lang', 'en')

    cname, hex_code = getColorName(r, g, b)

    # Split multilingual name (English | Kannada | Telugu | Hindi)
    parts = [p.strip() for p in cname.split('|')]
    color_name = parts[0]

    if lang == 'kn' and len(parts) > 1:
        color_name = parts[1]
        text = f"ಇದು {color_name} ಬಣ್ಣ"
        lang_code = 'kn'
    elif lang == 'te' and len(parts) > 2:
        color_name = parts[2]
        text = f"ఇది {color_name} రంగు"
        lang_code = 'te'
    elif lang == 'hi' and len(parts) > 3:
        color_name = parts[3]
        text = f"यह {color_name} रंग है"
        lang_code = 'hi'
    else:
        text = f"This is {color_name} color"
        lang_code = 'en'

    # ✅ Avoid repeating same color voice
    if last_color_spoken == color_name:
        return jsonify({'color_name': color_name, 'hex': hex_code, 'audio': '', 'display_text': text})
    last_color_spoken = color_name

    # ✅ Unique audio file for each detection
    timestamp = str(int(time.time() * 1000))
    audio_path = f"static/audio/color_{lang_code}_{timestamp}.mp3"

    try:
        tts = gTTS(text=text, lang=lang_code)
        tts.save(audio_path)
    except Exception as e:
        print("TTS Error:", e)
        audio_path = ""

    return jsonify({
        'color_name': color_name,
        'hex': hex_code,
        'audio': f'/{audio_path}' if audio_path else '',
        'display_text': text
    })

# ================== REGISTER ==================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
            conn.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists. Try a different one.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')

# ================== LOGIN ==================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['logged_in'] = True
            session['email'] = email
            return redirect(url_for('predict'))
        else:
            error_message = "Invalid credentials, please try again!"

    return render_template('login.html', error_message=error_message)

# ================== PREDICT PAGE ==================
@app.route('/predict')
def predict():
    if not session.get('logged_in'):
        flash("You must be logged in to access this page.", "warning")
        return redirect(url_for('login'))
    return render_template('predict.html')

# ================== LOGOUT ==================
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# ================== MAIN ==================
if __name__ == '__main__':
    init_db()
    if not os.path.exists('static/audio'):
        os.makedirs('static/audio')
    print("✅ Flask app started successfully")
    app.run(debug=True)
