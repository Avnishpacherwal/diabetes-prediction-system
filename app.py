from flask import Flask, render_template, request, redirect, session
import numpy as np
import sqlite3
import pickle
import hashlib
import os


app = Flask(__name__)
app.secret_key = "secret123"

# Load ML model
model = pickle.load(open('model.pkl', 'rb'))
scaler = pickle.load(open('scaler.pkl', 'rb'))

# ---------------- DATABASE ----------------
def get_db():
    return sqlite3.connect('users.db', check_same_thread=False)


def init_db():
    conn = get_db()

    conn.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        username TEXT UNIQUE,
        email TEXT UNIQUE,
        password TEXT,
        age INTEGER,
        gender TEXT
    )
    ''')

    conn.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        glucose REAL,
        bmi REAL,
        age INTEGER,pr
        risk REAL,
        level TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.close()


init_db()

# ---------------- LOGIN ----------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form['username']
        pwd = hashlib.sha256(request.form['password'].encode()).hexdigest()

        conn = get_db()
        cursor = conn.cursor()

        # LOGIN USING USERNAME OR EMAIL
        cursor.execute(
            "SELECT * FROM users WHERE username=? OR email=?",
            (user_input, user_input)
        )
        data = cursor.fetchone()
        conn.close()

        if not data:
            return redirect('/register?msg=user_not_found')

        if data[4] != pwd:   # password index fixed
            return render_template("login.html", msg="Incorrect password")

        # store username in session
        session['user'] = data[2]

        if data[5] is None or data[6] is None:
            return redirect('/setup')

        return redirect('/home')

    return render_template('login.html')


# ---------------- REGISTER ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    msg = None

    if request.method == 'GET':
        if request.args.get('msg') == 'user_not_found':
            msg = "User not found. Please register first."

    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        pwd = hashlib.sha256(request.form['password'].encode()).hexdigest()

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (name, username, email, password, age, gender) VALUES (?, ?, ?, ?, ?, ?)",
                (name, username, email, pwd, None, None)
            )
            conn.commit()
        except:
            conn.close()
            return render_template('register.html', msg="Username or Email already exists")

        conn.close()
        return redirect('/')

    return render_template('register.html', msg=msg)


# ---------------- SETUP ----------------
@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if 'user' not in session:
        return redirect('/')

    if request.method == 'POST':
        age = int(request.form['age'])
        gender = request.form['gender']

        conn = get_db()
        conn.execute(
            "UPDATE users SET age=?, gender=? WHERE username=?",
            (age, gender, session['user'])
        )
        conn.commit()
        conn.close()

        return redirect('/home')

    return render_template('setup.html')


# ---------------- HOME ----------------
@app.route('/home')
def home():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT name, email, age, gender FROM users WHERE username=?",
        (session['user'],)
    )
    user_data = cursor.fetchone()
    conn.close()

    return render_template(
        'index.html',
        name=user_data[0],
        email=user_data[1],
        age=user_data[2],
        gender=user_data[3]
    )


# ---------------- PREDICT ----------------
@app.route('/predict', methods=['POST'])
def predict():
    if 'user' not in session:
        return redirect('/')

    try:
        preg = float(request.form.get('preg', 0) or 0)
        glucose = float(request.form['glucose'])
        bp = float(request.form['bp'])
        skin = float(request.form.get('skin', 0) or 0)
        insulin = float(request.form.get('insulin', 0) or 0)
        bmi = float(request.form.get('bmi', 0) or 0)

        dpf_input = request.form['dpf']
        dpf = 0.5 if dpf_input == "1" else 0.2

        age = float(request.form['age'])

        # ---------------- VALIDATION ----------------

        if glucose < 70 or glucose > 300:
            return "Invalid Glucose Range"

        if bp < 40 or bp > 200:
            return "Invalid Blood Pressure Range"

        if bmi < 10 or bmi > 60:
            return "Invalid BMI Range"

        if insulin < 0 or insulin > 900:
            return "Invalid Insulin Range"

        data = [preg, glucose, bp, skin, insulin, bmi, dpf, age]

        input_data = np.asarray(data).reshape(1, -1)
        std_data = scaler.transform(input_data)

        prob = model.predict_proba(std_data)[0][1] * 100

        # Symptoms impact
        symptoms = request.form.getlist('symptoms')
        if len(symptoms) >= 3:
            prob += 15

        prob = min(prob, 100)

    except Exception as e:
        return f"Prediction Error: {str(e)}"

    # Risk level
    if prob < 30:
        risk = "Low Risk"
    elif prob < 70:
        risk = "Moderate Risk"
    else:
        risk = "High Risk"

    # Recommendations
    tips = []

    if glucose > 140:
        tips.append("Control sugar intake (reduce sweets & carbs)")

    if bmi > 25:
        tips.append("Maintain healthy weight through exercise")

    if bp > 90:
        tips.append("Monitor blood pressure regularly")

    if 30 <= prob < 70:
        tips.append("Adopt a balanced diet (low sugar, high fiber)")
        tips.append("Exercise at least 30 minutes daily")
        tips.append("Schedule regular health checkups")

    if not tips:
        tips.append("Healthy range. Maintain lifestyle.")

    # Save history
    conn = get_db()
    conn.execute(
        "INSERT INTO history (username, glucose, bmi, age, risk, level) VALUES (?, ?, ?, ?, ?, ?)",
        (session['user'], glucose, bmi, age, prob, risk)
    )
    conn.commit()
    conn.close()

    return render_template(
        'result.html',
        prediction=round(prob, 2),
        risk=risk,
        tips=tips
    )


# ---------------- HISTORY ----------------
@app.route('/history')
def history():
    if 'user' not in session:
        return redirect('/')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history WHERE username=?", (session['user'],))
    rows = cursor.fetchall()
    conn.close()

    return render_template(
        'history.html',
        data=rows,
        email=session['user']
    )


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ---------------- RUN ----------------


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)