# ================= UPDATED IMPORTS =================
from flask import Flask, render_template, request, redirect, Response, session, jsonify, flash
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
app.config['MAIL_PASSWORD'] = 'your_16_char_app_password'  # REPLACE WITH APP PASSWORD
app.config['MAIL_DEFAULT_SENDER'] = 'vishnugowtham392@gmail.com'
app.config['MAIL_MAX_EMAILS'] = None
app.config['MAIL_ASCII_ATTACHMENTS'] = False
mail = Mail(app)

# ================= DATABASE CONNECTION =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database", "budget.db")

def get_db_connection():
    try:
        os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
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
                password TEXT,
                email TEXT,
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
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise

# ================= FOLDERS =================
os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static", "profiles"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static", "uploads"), exist_ok=True)

app.config['UPLOAD_FOLDER'] = "static/uploads"
budget_limit = 5000
init_db()

# ================= HEALTH CHECK =================
@app.route('/health')
def health():
    return "OK", 200

# ================= ERROR HANDLING =================
@app.errorhandler(Exception)
def handle_exception(e):
    error_msg = str(e)
    print(f"❌ Error: {error_msg}")
    print(traceback.format_exc())
    return f"Error: {error_msg}", 500

# ================= EMAIL WARNING FUNCTION =================
def send_budget_warning_email(email, username, expense, budget_limit):
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
        password = request.form['password'].strip()
        email = request.form['email'].strip()
        
        if not username or not password or not email:
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
            
            cursor.execute("""
                INSERT INTO users (username, password, email)
                VALUES (?, ?, ?)
            """, (username, password, email))
            
            conn.commit()
            conn.close()
            
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
                    if user[2] == password:
                        session['user'] = username
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
        
        photo = request.files.get('photo')
        filename = None
        
        if photo and photo.filename != "":
            filename = secure_filename(photo.filename)
            photo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            cur.execute("""
                UPDATE users
                SET username=?,
                    email=?,
                    password=?,
                    photo=?
                WHERE username=?
            """, (new_username, email, password, filename, username))
        else:
            cur.execute("""
                UPDATE users
                SET username=?,
                    email=?,
                    password=?
                WHERE username=?
            """, (new_username, email, password, username))
        
        conn.commit()
        session['user'] = new_username
        username = new_username
    
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    conn.close()
    
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
    path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
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
            
            cursor.execute("""
                INSERT INTO transactions
                (username,title,amount,type,category,item,date)
                VALUES(?,?,?,?,?,?,?)
            """, (session['user'], title, amount, t_type, category, item, date))
    
    conn.commit()
    conn.close()
    
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
        
        cursor.execute("""
            INSERT INTO transactions (username,title,amount,type,category,item,date)
            VALUES(?,?,?,?,?,?,?)
        """, (username, title, amount, ttype, category, item, date))
        conn.commit()
    
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
            success, message = send_budget_warning_email(user_email, username, expense, budget_limit)
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
    
    try:
        plt.figure()
        if income > 0 or expense > 0:
            plt.pie([income if income > 0 else 1, expense if expense > 0 else 1], 
                    labels=["Income", "Expense"], autopct="%1.1f%%")
        else:
            plt.text(0.5, 0.5, "No Data Available", ha="center", va="center", fontsize=14)
        plt.savefig("static/chart.png")
        plt.close()
        
        plt.figure(figsize=(8,5))
        if monthly_data:
            months = sorted(monthly_data.keys())
            values = [monthly_data[m] for m in months]
            plt.bar(months, values)
            plt.title("Monthly Expense Analysis")
            plt.xticks(rotation=30)
        else:
            plt.text(0.5, 0.5, "No Monthly Data", ha="center", va="center", fontsize=14)
        plt.tight_layout()
        plt.savefig("static/monthly_chart.png", bbox_inches='tight')
        plt.close()
        
        plt.figure(figsize=(6,6))
        if category_data:
            filtered_data = {k: v for k, v in category_data.items() if v > 0}
            if filtered_data:
                plt.pie(filtered_data.values(), labels=filtered_data.keys(), autopct="%1.1f%%")
                plt.title("Category Analytics")
            else:
                plt.text(0.5, 0.5, "No Expense Data", ha="center", va="center", fontsize=14)
        else:
            plt.text(0.5, 0.5, "No Category Data", ha="center", va="center", fontsize=14)
        plt.savefig("static/category_chart.png")
        plt.close()
        
    except Exception as e:
        print(f"Chart generation error: {e}")
    
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

# ================= DEBUG DATABASE ROUTE =================
@app.route('/debug/db')
def debug_db():
    if 'user' not in session:
        return redirect('/login')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM transactions WHERE username=?", (session['user'],))
    transactions = cursor.fetchall()
    
    cursor.execute("SELECT id, username, email FROM users")
    users = cursor.fetchall()
    conn.close()
    
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Database Debug</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #f4f6f9; }
            .card { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 0 10px lightgray; }
            h1 { color: #28a745; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background: #28a745; color: white; }
            .back { display: inline-block; padding: 10px 20px; background: #28a745; color: white; text-decoration: none; border-radius: 5px; }
            .back:hover { background: #218838; }
        </style>
    </head>
    <body>
        <div class="card">
            <h1>📊 Database Debug</h1>
            <a href="/" class="back">⬅ Back to Dashboard</a>
        </div>
        
        <div class="card">
            <h2>👤 Users</h2>
            <p>Total Users: <b>""" + str(len(users)) + """</b></p>
            <table>
                <tr><th>ID</th><th>Username</th><th>Email</th></tr>
    """
    
    for u in users:
        html += f"<tr><td>{u[0]}</td><td>{u[1]}</td><td>{u[2]}</td></tr>"
    
    html += """
            </table>
        </div>
        
        <div class="card">
            <h2>📋 Transactions</h2>
            <p>Total Transactions: <b>""" + str(len(transactions)) + """</b></p>
            <table>
                <tr><th>ID</th><th>Title</th><th>Amount</th><th>Type</th><th>Category</th><th>Item</th><th>Date</th></tr>
    """
    
    for t in transactions:
        html += f"<tr><td>{t[0]}</td><td>{t[2]}</td><td>₹{t[3]}</td><td>{t[4]}</td><td>{t[5]}</td><td>{t[6]}</td><td>{t[7]}</td></tr>"
    
    html += """
            </table>
        </div>
    </body>
    </html>
    """
    
    return html

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
    
    file = "static/report.pdf"
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
    return redirect("/static/report.pdf")

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
    return redirect('/')

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)