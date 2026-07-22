# ================= UPDATED IMPORTS =================
from flask import Flask, render_template, request, redirect, Response, session, jsonify, flash, send_from_directory
import sqlite3
import os
import csv
import traceback
import sys
import logging
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask_mail import Mail, Message
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from collections import Counter, defaultdict
import json
import datetime

# ================= LOGGING =================
logging.basicConfig(level=logging.DEBUG)
print("🚀 Starting Budget Tracker...")

app = Flask(__name__)
app.secret_key = "budgettracker"

# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'vishnugowtham392@gmail.com'
app.config['MAIL_PASSWORD'] = 'brdxtgyqobiwjeel'
app.config['MAIL_DEFAULT_SENDER'] = 'vishnugowtham392@gmail.com'
app.config['MAIL_MAX_EMAILS'] = None
app.config['MAIL_ASCII_ATTACHMENTS'] = False
mail = Mail(app)

# ================= DATABASE & FILE PATHS - DETECTS RENDER VS LOCAL =================
# Check if running on Render
IS_RENDER = os.environ.get('RENDER') == 'true'

if IS_RENDER:
    # On Render - use /tmp (writable)
    BASE_DIR = "/tmp"
    print("🔧 Running on Render - using /tmp for storage")
else:
    # On Local - use your Windows path
    BASE_DIR = r"E:\Budget Tracker"
    print("🔧 Running locally - using E:\Budget Tracker")

# Database file path
DATABASE_PATH = os.path.join(BASE_DIR, "budget.db")  # Note: No "database" folder on Render

# Static folders
if IS_RENDER:
    STATIC_DIR = os.path.join(BASE_DIR, "static")
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
    PROFILES_DIR = os.path.join(STATIC_DIR, "profiles")
else:
    # Local paths with folders
    STATIC_DIR = os.path.join(BASE_DIR, "static")
    UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
    PROFILES_DIR = os.path.join(STATIC_DIR, "profiles")

# Create all necessary directories
for folder in [STATIC_DIR, UPLOAD_DIR, PROFILES_DIR]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_DIR

print(f"✅ Database Location: {DATABASE_PATH}")
print(f"✅ Static Files: {STATIC_DIR}")
print(f"✅ Uploads: {UPLOAD_DIR}")
print(f"✅ Profiles: {PROFILES_DIR}")
print(f"✅ Running on Render: {IS_RENDER}")

# ================= DATABASE FUNCTIONS =================
def get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email TEXT,
                password TEXT,
                photo TEXT DEFAULT 'default.png'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT,
                title TEXT,
                amount REAL,
                type TEXT,
                category TEXT,
                item TEXT,
                date TEXT
            )
        """)
        conn.commit()
        conn.close()
        print(f"✅ Database initialized successfully at: {DATABASE_PATH}")
        
        # Verify database is writable
        test_conn = sqlite3.connect(DATABASE_PATH)
        test_conn.cursor().execute("SELECT 1")
        test_conn.close()
        print("✅ Database is writable")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise

# Initialize the database
init_db()

# ================= GLOBAL VARIABLE =================
budget_limit = 5000

# ================= ROUTES =================
@app.route('/health')
def health():
    return "OK", 200

@app.errorhandler(Exception)
def handle_exception(e):
    error_msg = str(e)
    print(f"❌ Error: {error_msg}")
    print(traceback.format_exc())
    return f"Error: {error_msg}", 500

# ================= SHOW DATABASE LOCATION =================
@app.route('/show-db-location')
def show_db_location():
    """Show where database is stored - perfect for staff demonstration"""
    if 'user' not in session:
        return redirect('/login')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all users
        cursor.execute("SELECT id, username, email, photo FROM users")
        users = cursor.fetchall()
        
        # Get all transactions
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_transactions = cursor.fetchone()[0]
        
        # Get current user's transactions
        cursor.execute("SELECT COUNT(*) FROM transactions WHERE username=?", (session['user'],))
        user_transactions = cursor.fetchone()[0]
        
        # Get database file size
        db_size = os.path.getsize(DATABASE_PATH) if os.path.exists(DATABASE_PATH) else 0
        db_size_mb = db_size / (1024 * 1024)
        
        # Get all transactions for display
        cursor.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 20")
        recent_transactions = cursor.fetchall()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Database Location - Budget Tracker</title>
            <style>
                body {{ font-family: 'Segoe UI', Arial; padding: 20px; background: #f4f6f9; }}
                .card {{ background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #28a745; }}
                .db-info {{ background: #e8f5e9; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #28a745; }}
                .db-path {{ background: #263238; color: #fff; padding: 15px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 14px; word-break: break-all; }}
                .file-info {{ background: #e3f2fd; padding: 15px; border-radius: 8px; margin: 10px 0; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background: #28a745; color: white; }}
                tr:hover {{ background-color: #f5f5f5; }}
                .back {{ display: inline-block; padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; margin: 10px 5px; }}
                .back:hover {{ background: #218838; }}
                .download-btn {{ background: #17a2b8; }}
                .download-btn:hover {{ background: #138496; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 15px; margin: 15px 0; }}
                .stat-box {{ background: #f8f9fa; padding: 15px; border-radius: 8px; text-align: center; border: 1px solid #dee2e6; }}
                .stat-number {{ font-size: 24px; font-weight: bold; color: #28a745; }}
                .stat-label {{ color: #6c757d; font-size: 14px; }}
                .folder-structure {{ background: #f8f9fa; padding: 15px; border-radius: 8px; font-family: 'Courier New', monospace; font-size: 13px; }}
            </style>
        </head>
        <body>
            <div class="card">
                <h1>🗄️ Database Storage Location</h1>
                <a href="/" class="back">⬅ Back to Dashboard</a>
                <a href="/download-db" class="back download-btn">⬇️ Download Database</a>
                
                <div class="db-info">
                    <h3>📂 Database File Location:</h3>
                    <div class="db-path">{DATABASE_PATH}</div>
                    <div class="file-info">
                        <strong>✅ File exists:</strong> {os.path.exists(DATABASE_PATH)} &nbsp;|&nbsp;
                        <strong>📦 File size:</strong> {db_size_mb:.2f} MB &nbsp;|&nbsp;
                        <strong>🔄 Last modified:</strong> {datetime.datetime.fromtimestamp(os.path.getmtime(DATABASE_PATH)).strftime('%Y-%m-%d %H:%M:%S') if os.path.exists(DATABASE_PATH) else 'N/A'} &nbsp;|&nbsp;
                        <strong>✏️ Writable:</strong> {os.access(DATABASE_PATH, os.W_OK) if os.path.exists(DATABASE_PATH) else 'N/A'}
                    </div>
                </div>
                
                <div class="folder-structure">
                    <strong>📁 Project Folder Structure:</strong><br>
                    {'/tmp/' if IS_RENDER else 'E:\\Budget Tracker\\'}<br>
                    ├── 📄 budget.db  ← Your data is stored here!<br>
                    ├── 📁 static\<br>
                    │   └── 📁 profiles\<br>
                    └── 📁 uploads\<br>
                </div>
                
                <div class="stats">
                    <div class="stat-box">
                        <div class="stat-number">{len(users)}</div>
                        <div class="stat-label">Total Users</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{total_transactions}</div>
                        <div class="stat-label">Total Transactions</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-number">{user_transactions}</div>
                        <div class="stat-label">Your Transactions</div>
                    </div>
                </div>
        """
        
        if len(users) > 0:
            html += """
                <h3>👤 Registered Users:</h3>
                <table>
                    <tr><th>ID</th><th>Username</th><th>Email</th><th>Photo</th></tr>
            """
            for user in users:
                html += f"<tr><td>{user[0]}</td><td>{user[1]}</td><td>{user[2]}</td><td>{user[3]}</td></tr>"
            html += "</table>"
        else:
            html += """
                <div style="background: #fff3cd; padding: 15px; border-radius: 8px; margin: 10px 0;">
                    ⚠️ No users found in database. Sign up to create your first account!
                </div>
            """
        
        if len(recent_transactions) > 0:
            html += """
                <h3>📋 Recent Transactions (Last 20):</h3>
                <table>
                    <tr><th>ID</th><th>Title</th><th>Amount</th><th>Type</th><th>Category</th><th>Item</th><th>Date</th><th>User</th></tr>
            """
            for t in recent_transactions:
                html += f"<tr><td>{t[0]}</td><td>{t[2]}</td><td>₹{t[3]}</td><td>{t[4]}</td><td>{t[5]}</td><td>{t[6]}</td><td>{t[7]}</td><td>{t[1]}</td></tr>"
            html += "</table>"
        
        html += """
            </div>
        </body>
        </html>
        """
        
        conn.close()
        return html
        
    except Exception as e:
        return f"Error: {str(e)}"

# ================= DOWNLOAD DATABASE =================
@app.route('/download-db')
def download_db():
    """Download the database file for demonstration"""
    if 'user' not in session:
        return redirect('/login')
    
    try:
        if os.path.exists(DATABASE_PATH):
            return send_from_directory(
                os.path.dirname(DATABASE_PATH),
                os.path.basename(DATABASE_PATH),
                as_attachment=True,
                download_name='budget.db'
            )
        else:
            return "Database file not found!", 404
    except Exception as e:
        return f"Error downloading database: {str(e)}", 500

# ================= EMAIL WARNING FUNCTION =================
def send_warning_email(email, username, expense, budget_limit):
    print("=" * 60)
    print("📧 SEND_WARNING_EMAIL() CALLED")
    print(f"📧 To: {email}")
    print(f"📧 Username: {username}")
    print(f"📧 Expense: ₹{expense}")
    print(f"📧 Budget Limit: ₹{budget_limit}")
    print("=" * 60)
    
    if not email or email == "":
        print("❌ No email address found!")
        return False, "No email address found"
    
    try:
        msg = Message(
            subject="🚨 Budget Alert - Budget Analysis System",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = f"""
Hello {username},

🚨 Budget Limit Alert 🚨

Your budget limit has been exceeded.

📊 Budget Summary:
• Budget Limit: ₹{budget_limit}
• Current Expense: ₹{expense}
• Excess Amount: ₹{expense - budget_limit}

💡 Suggestions to Reduce Spending:
1. Track your daily expenses
2. Avoid unnecessary shopping
3. Cook at home instead of ordering
4. Use public transport
5. Cancel unused subscriptions

Stay on track! 💰

- Budget Analysis System
        """
        print("📧 Sending email to:", email)
        mail.send(msg)
        print("✅ Email sent successfully to:", email)
        return True, f"Email sent to {email}"
    except Exception as e:
        print("❌ Mail Error:", str(e))
        return False, str(e)

# ================= TEST EMAIL ROUTE =================
@app.route('/test-email')
def test_email():
    try:
        msg = Message(
            subject="✅ Test Email from Budget Tracker",
            sender=app.config['MAIL_USERNAME'],
            recipients=[app.config['MAIL_USERNAME']]
        )
        msg.body = "✅ Test email from Budget Tracker!"
        mail.send(msg)
        return "✅ Test email sent! Check your inbox."
    except Exception as e:
        return f"❌ Failed: {str(e)}"

# ================= SIGNUP =================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == "POST":
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        
        if not username or not email or not password:
            flash("All fields are required!")
            return render_template("signup.html")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT username FROM users WHERE username=?", (username,))
            existing_user = cursor.fetchone()
            
            if existing_user:
                flash("Username already exists! Please choose another.")
                conn.close()
                return render_template("signup.html")
            
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", (username, email, password))
            conn.commit()
            conn.close()
            
            print(f"✅ New user created: {username} at {datetime.datetime.now()}")
            print(f"✅ Data saved to: {DATABASE_PATH}")
            flash("✅ Account created successfully! Please login.")
            return redirect('/login')
        except Exception as e:
            print(f"Signup error: {e}")
            flash(f"Error: {str(e)}")
            return render_template("signup.html")
    
    return render_template("signup.html")

# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not username or not password:
            error = "Username and password are required!"
        else:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE username=?", (username,))
                user = cursor.fetchone()
                conn.close()
                
                if user:
                    # user[1] = username, user[2] = email, user[3] = password
                    if user[3] == password:
                        session['user'] = username
                        print(f"✅ User logged in: {username}")
                        return redirect('/')
                    else:
                        error = "Invalid Password! Please try again."
                else:
                    error = "Username not found! Please sign up first."
            except Exception as e:
                print(f"Login error: {e}")
                error = "Database error. Please try again."
    
    return render_template("login.html", error=error)

# ================= LOGOUT =================
@app.route('/logout')
def logout():
    username = session.get('user')
    print(f"👋 User logged out: {username}")
    session.clear()
    return redirect('/login')

# ================= SET LIMIT =================
@app.route('/set_limit', methods=['POST'])
def set_limit():
    global budget_limit
    budget_limit = int(request.form['limit'])
    
    if budget_limit < 1000:
        budget_limit = 1000
    elif budget_limit > 10000:
        budget_limit = 10000
    
    flash(f"✅ Budget limit set to ₹{budget_limit}")
    return redirect('/')

# ================= PROFILE SETTINGS =================
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect('/login')
    
    username = session['user']
    conn = get_db_connection()
    cur = conn.cursor()
    
    if request.method == "POST":
        new_username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        
        print(f"📝 Profile Update - Username: {new_username}, Email: {email}")
        
        photo = request.files.get('photo')
        filename = None
        
        if photo and photo.filename != "":
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(UPLOAD_DIR, filename))
            cur.execute("""
                UPDATE users 
                SET username=?, email=?, password=?, photo=? 
                WHERE username=?
            """, (new_username, email, password, filename, username))
        else:
            cur.execute("""
                UPDATE users 
                SET username=?, email=?, password=? 
                WHERE username=?
            """, (new_username, email, password, username))
        
        conn.commit()
        session['user'] = new_username
        username = new_username
        print(f"✅ Profile updated for: {username}")
        flash("✅ Profile updated successfully!")
        return redirect('/profile')
    
    # Fetch user data - CORRECT ORDER
    # Database columns: id(0), username(1), email(2), password(3), photo(4)
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    conn.close()
    
    # Debug to verify data is correct
    if user:
        print(f"👤 User Data - ID: {user[0]}, Username: {user[1]}, Email: {user[2]}, Password: {user[3]}, Photo: {user[4]}")
        print(f"📧 Email from database: '{user[2]}'")
        print(f"🔑 Password from database: '{user[3]}'")
    else:
        print("❌ User not found!")
    
    return render_template("profile.html", user=user)

# ================= UPLOAD CSV =================
@app.route('/upload', methods=['POST'])
def upload():
    if 'user' not in session:
        return redirect('/login')
    
    if 'file' not in request.files:
        return "No file uploaded"
    
    file = request.files['file']
    
    if file.filename == '':
        return "No file selected"
    
    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_DIR, filename)
    file.save(path)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    with open(path, 'r') as f:
        reader = csv.reader(f)
        next(reader)
        
        for row in reader:
            if len(row) < 6:
                continue
            
            title = row[0]
            try:
                amount = float(row[1])
            except:
                amount = 0
            
            t_type = row[2]
            category = row[3]
            item = row[4]
            date = row[5]
            
            cursor.execute("INSERT INTO transactions (username,title,amount,type,category,item,date) VALUES(?,?,?,?,?,?,?)", (session['user'], title, amount, t_type, category, item, date))
    
    conn.commit()
    conn.close()
    print(f"✅ CSV uploaded for user: {session['user']}")
    
    return redirect('/')

# ================= HOME =================
@app.route('/', methods=['GET', 'POST'])
def home():
    if 'user' not in session:
        return redirect('/login')
    
    username = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT email, photo FROM users WHERE username=?", (username,))
        user_data = cursor.fetchone()
        user_email = user_data[0] if user_data else ""
        user_photo = user_data[1] if user_data and user_data[1] else "default.png"
    except Exception as e:
        print(f"Error fetching user data: {e}")
        user_email = ""
        user_photo = "default.png"
    
    if request.method == "POST":
        title = request.form['title']
        amount = float(request.form['amount'])
        ttype = request.form['type']
        
        if ttype == "income":
            category = "Income"
            item = "Income Source"
        else:
            category = request.form.get('category', 'Other')
            item = request.form.get('item', "")
        
        date = request.form['date']
        
        cursor.execute("INSERT INTO transactions (username,title,amount,type,category,item,date) VALUES(?,?,?,?,?,?,?)", (username, title, amount, ttype, category, item, date))
        conn.commit()
        print(f"✅ Transaction added: {title} - ₹{amount} - {ttype} for {username}")
        print(f"✅ Data saved to: {DATABASE_PATH}")
    
    cursor.execute("SELECT * FROM transactions WHERE username=?", (username,))
    transactions = cursor.fetchall()
    
    total = 0
    income = 0
    expense = 0
    monthly_data = {}
    category_data = {}
    
    for t in transactions:
        amt = t[3]
        ttype = t[4]
        category = t[5]
        date = str(t[6])
        
        month = date[:7]
        
        total += amt
        if ttype == "income":
            income += amt
        else:
            expense += amt
            category_data[category] = category_data.get(category, 0) + amt
        
        monthly_data[month] = monthly_data.get(month, 0) + abs(amt)
    
    # ================= BUDGET CHECK & EMAIL ALERT =================
    warning = "✅ Budget Under Control"
    email_status = ""
    
    if expense > budget_limit:
        warning = "⚠️ Budget Exceeded!"
        print("=" * 60)
        print("🚨 BUDGET EXCEEDED!")
        print(f"👤 User: {username}")
        print(f"💰 Expense: ₹{expense}")
        print(f"📊 Budget Limit: ₹{budget_limit}")
        print(f"📧 User Email: {user_email}")
        print("=" * 60)
        
        if user_email:
            success, message = send_warning_email(user_email, username, expense, budget_limit)
            if success:
                email_status = f"✅ Budget warning email sent to {user_email}"
                flash(email_status)
            else:
                email_status = f"❌ Failed to send email: {message}"
                flash(email_status)
        else:
            email_status = "⚠️ No email address found. Please update your profile."
            flash(email_status)
    
    # ================= AI EXPENSE PREDICTION =================
    future_expense = int(expense * 1.10)
    
    if expense < income:
        prediction_status = "📈 Good Financial Growth"
        prediction_msg = "Your savings pattern is improving. Keep maintaining spending discipline."
    elif expense == income:
        prediction_status = "⚠️ Balanced Spending"
        prediction_msg = "Income and expenses are equal. Try increasing savings."
    else:
        prediction_status = "🚨 High Expense Alert"
        prediction_msg = "Expenses are increasing. Reduce unnecessary spending."
    
    saving_goal = int(income * 0.20)
    
    top_category = "None"
    if category_data:
        top_category = max(category_data, key=category_data.get)
    
    category_total = {}
    most_expense = 0
    most_item = "None"
    
    for t in transactions:
        amount = float(t[3])
        ttype = t[4]
        category = t[5]
        item = t[6] if len(t) > 6 else ""
        
        if ttype == "expense":
            category_total[category] = category_total.get(category, 0) + amount
            if amount > most_expense:
                most_expense = amount
                most_item = item if item else "Unknown"
    
    top_spent_category = "None"
    if category_total:
        top_spent_category = max(category_total, key=category_total.get)
    
    estimated_save = int(expense * 0.10)
    
    insight = f"""
📊 Top Spending Category: {top_spent_category}
🍽 Most Expensive Item: {most_item} (₹{most_expense})
💰 Estimated Monthly Savings: ₹{estimated_save}
"""
    
    suggestions = []
    
    smart_items = {
        "idli": {"alternative": "Home-made Idli 🥣", "reason": "Home food usually costs less", "benefit": "Healthy breakfast + lower spending", "motivation": "Healthy mornings create healthy savings 🌞"},
        "dosai": {"alternative": "Idli 🥣", "reason": "Less oil and lower cost", "benefit": "Healthy and saves money", "motivation": "Small savings create big results 💪"},
        "chips": {"alternative": "Fruits 🍎", "reason": "Chips are processed snacks", "benefit": "Better nutrition + savings", "motivation": "Healthy snacks, healthy life 🌟"},
        "petrol": {"alternative": "Public Transport 🚌", "reason": "Fuel costs increase over time", "benefit": "Reduce travel expenses", "motivation": "Travel smart 🌍"},
        "tea": {"alternative": "Home-made Tea ☕", "reason": "Daily outside tea adds up", "benefit": "Reduce repeated expenses", "motivation": "₹20/day ≈ ₹600/month 💰"},
        "coffee": {"alternative": "Milk/Home Coffee 🥛", "reason": "Outside coffee is expensive", "benefit": "Lower cost", "motivation": "Save little, gain more 🚀"},
    }
    
    for t in transactions:
        try:
            item = str(t[6]).lower() if len(t) > 6 else ""
        except:
            item = ""
        
        amount = float(t[3])
        date = t[7] if len(t) > 7 else t[6]
        
        if item in smart_items:
            data = smart_items[item]
            save_money = int(amount * 0.20)
            
            msg = f"""
💡 {date}

{item.title()} → Try {data['alternative']}

📌 Reason: {data['reason']}
✅ Benefit: {data['benefit']}
💰 Expected Saving: ₹{save_money}
🔥 Motivation: {data['motivation']}
"""
            suggestions.append(msg)
    
    if not suggestions:
        suggestions.append("✅ Spending looks balanced. Keep saving! 💪")
    
    # ================= CHART GENERATION =================
    try:
        # Income vs Expense Pie Chart
        chart_path = os.path.join(STATIC_DIR, "chart.png")
        plt.figure(figsize=(8, 6))
        if income > 0 or expense > 0:
            plt.pie([income if income > 0 else 1, expense if expense > 0 else 1], 
                    labels=["Income", "Expense"], 
                    autopct="%1.1f%%",
                    colors=['#2ecc71', '#e74c3c'],
                    explode=(0.05, 0.05),
                    shadow=True)
            plt.title("📊 Income vs Expense Analysis", fontsize=16, fontweight='bold')
        else:
            plt.text(0.5, 0.5, "No Data Available", ha="center", va="center", fontsize=14)
        plt.savefig(chart_path, bbox_inches='tight', dpi=100)
        plt.close()
        print(f"✅ Pie chart saved: {chart_path}")
        
        # Monthly Expense Bar Chart
        monthly_chart_path = os.path.join(STATIC_DIR, "monthly_chart.png")
        plt.figure(figsize=(10, 6))
        if monthly_data:
            months = sorted(monthly_data.keys())
            values = [monthly_data[m] for m in months]
            bars = plt.bar(months, values, color='#3498db', alpha=0.7)
            plt.title("📈 Monthly Expense Analysis", fontsize=16, fontweight='bold')
            plt.xlabel("Month", fontsize=12)
            plt.ylabel("Expense (₹)", fontsize=12)
            plt.xticks(rotation=30, ha='right')
            
            # Add value labels on bars
            for bar, value in zip(bars, values):
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height,
                        f'₹{int(value)}', ha='center', va='bottom', fontsize=10)
            
            plt.grid(axis='y', linestyle='--', alpha=0.3)
        else:
            plt.text(0.5, 0.5, "No Monthly Data Available", ha="center", va="center", fontsize=14)
        plt.tight_layout()
        plt.savefig(monthly_chart_path, bbox_inches='tight', dpi=100)
        plt.close()
        print(f"✅ Monthly chart saved: {monthly_chart_path}")
        
        # Category Distribution Pie Chart
        category_chart_path = os.path.join(STATIC_DIR, "category_chart.png")
        plt.figure(figsize=(8, 8))
        if category_data:
            filtered_data = {k: v for k, v in category_data.items() if v > 0}
            if filtered_data:
                colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F']
                plt.pie(filtered_data.values(), 
                        labels=filtered_data.keys(), 
                        autopct="%1.1f%%",
                        colors=colors[:len(filtered_data)],
                        shadow=True,
                        startangle=90)
                plt.title("📊 Category-wise Expense Distribution", fontsize=16, fontweight='bold')
            else:
                plt.text(0.5, 0.5, "No Expense Data", ha="center", va="center", fontsize=14)
        else:
            plt.text(0.5, 0.5, "No Category Data Available", ha="center", va="center", fontsize=14)
        plt.savefig(category_chart_path, bbox_inches='tight', dpi=100)
        plt.close()
        print(f"✅ Category chart saved: {category_chart_path}")
        
        print("✅ Charts generated successfully!")
        
    except Exception as e:
        print(f"❌ Chart generation error: {e}")
        import traceback
        traceback.print_exc()
    
    conn.close()
    
    return render_template(
        "index.html",
        username=username,
        user_email=user_email,
        user_photo=user_photo,
        transactions=transactions,
        total=total,
        income=income,
        expense=expense,
        warning=warning,
        budget_limit=budget_limit,
        progress=50,
        advice="Track your spending regularly",
        top_category=top_category,
        top_spent_category=top_spent_category,
        most_item=most_item,
        estimated_save=estimated_save,
        suggestions=suggestions,
        insight=insight,
        future_expense=future_expense,
        prediction_status=prediction_status,
        prediction_msg=prediction_msg,
        saving_goal=saving_goal,
        category_data=category_data,
        email_status=email_status
    )

# ================= CHATBOT =================
@app.route('/chatbot', methods=['POST'])
def chatbot():
    msg = request.form['message'].lower().strip()
    username = session['user']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE username=?", (username,))
    transactions = cursor.fetchall()
    conn.close()
    
    total_income = 0
    total_expense = 0
    categories = {}
    
    for t in transactions:
        amount = float(t[3])
        t_type = t[4]
        category = t[5]
        
        if t_type == "income":
            total_income += amount
        else:
            total_expense += amount
            categories[category] = categories.get(category, 0) + amount
    
    balance = total_income - total_expense
    
    if categories:
        top_category = max(categories, key=categories.get)
    else:
        top_category = "No expenses"
    
    if "total income" in msg:
        reply = f"💰 Your total income is ₹{total_income}"
    elif "total expense" in msg:
        reply = f"💸 Your total expense is ₹{total_expense}"
    elif "balance" in msg:
        reply = f"🏦 Your current balance is ₹{balance}"
    elif "budget" in msg:
        remaining = budget_limit - total_expense
        reply = f"📊 Remaining budget: ₹{remaining}"
    elif "top category" in msg or "highest expense" in msg:
        reply = f"📈 Highest spending category: {top_category}"
    elif "hi" in msg or "hello" in msg or "hey" in msg:
        reply = f"👋 Hello {username}! Welcome back."
    else:
        reply = "🤖 Ask me about your income, expense, balance, or budget!"
    
    return jsonify({"reply": reply})

# ================= PDF =================
@app.route('/pdf')
def pdf():
    username = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE username=?", (username,))
    data = cursor.fetchall()
    conn.close()
    
    file = os.path.join(STATIC_DIR, "report.pdf")
    doc = SimpleDocTemplate(file, pagesize=A4)
    styles = getSampleStyleSheet()
    content = []
    content.append(Paragraph("💰 BUDGET ANALYSIS REPORT", styles['Title']))
    content.append(Spacer(1, 20))
    
    income = sum([t[3] for t in data if t[4] == "income"])
    expense = sum([t[3] for t in data if t[4] == "expense"])
    balance = income - expense
    
    content.append(Paragraph(f"User: {username}", styles['Normal']))
    content.append(Paragraph(f"Income: {income}", styles['Normal']))
    content.append(Paragraph(f"Expense: {expense}", styles['Normal']))
    content.append(Paragraph(f"Balance: {balance}", styles['Normal']))
    content.append(Spacer(1, 20))
    
    for row in data:
        if len(row) > 7:
            line = f"{row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} | {row[7]}"
        else:
            line = f"{row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]}"
        content.append(Paragraph(line, styles['Normal']))
        content.append(Spacer(1, 5))
    
    doc.build(content)
    return redirect(f"/static/report.pdf")

# ================= CSV DOWNLOAD =================
@app.route('/download')
def download():
    username = session['user']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions WHERE username=?", (username,))
    data = cursor.fetchall()
    conn.close()
    
    def generate():
        yield "Title,Amount,Type,Category,Item,Date\n"
        for row in data:
            if len(row) > 7:
                yield f"{row[2]},{row[3]},{row[4]},{row[5]},{row[6]},{row[7]}\n"
            else:
                yield f"{row[2]},{row[3]},{row[4]},{row[5]},{row[6]},\n"
    
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=budget.csv"})

# ================= DELETE =================
@app.route('/delete/<int:id>')
def delete(id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id=?", (id,))
    conn.commit()
    conn.close()
    print(f"✅ Transaction {id} deleted")
    return redirect('/')

# ================= SERVE STATIC FILES =================
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(STATIC_DIR, filename)

# ================= RUN =================
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 BUDGET TRACKER APPLICATION")
    print("=" * 60)
    print(f"📁 Database Location: {DATABASE_PATH}")
    print(f"📁 Static Files: {STATIC_DIR}")
    print(f"📁 Uploads: {UPLOAD_DIR}")
    print(f"📁 Profiles: {PROFILES_DIR}")
    print(f"📁 Running on Render: {IS_RENDER}")
    print("=" * 60)
    print("🌐 Server starting at: http://127.0.0.1:5000")
    print("🔑 Login to access your budget tracker")
    print("=" * 60)
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)