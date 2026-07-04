from flask import Flask, render_template, request, redirect, Response, session, jsonify, flash
import sqlite3
import os
import csv
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from flask_mail import Mail, Message
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from collections import Counter, defaultdict

app = Flask(__name__)
app.secret_key = "budgettracker"

# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'yourgmail@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'
mail = Mail(app)

budget_limit = 5000

# ================= FOLDERS =================
os.makedirs("database", exist_ok=True)
os.makedirs("static", exist_ok=True)
os.makedirs("uploads", exist_ok=True)
os.makedirs("static/profiles", exist_ok=True)  # For profile photos

# ================= DATABASE INIT =================
def init_db():
    conn = sqlite3.connect("database/budget.db")
    cursor = conn.cursor()
    
    # ================= UPDATED USERS TABLE WITH PROFILE FEATURES =================
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
    
    try:
        cursor.execute("ALTER TABLE transactions ADD COLUMN item TEXT")
    except:
        pass
    
    conn.commit()
    conn.close()

init_db()

# ================= EMAIL WARNING =================
def send_warning_email(email, username, expense):
    try:
        msg = Message(
            "Budget Warning 🚨",
            sender=app.config['MAIL_USERNAME'],
            recipients=[email]
        )
        msg.body = f"""
Hello {username}
Your budget limit exceeded.
Expense: {expense}
Please reduce spending.
"""
        mail.send(msg)
    except Exception as e:
        print("Mail Error:", e)

# ================= SIGNUP =================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        email = request.form['email'].strip()
        
        if not username or not password or not email:
            return "All fields are required!"
        
        conn = sqlite3.connect("database/budget.db")
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO users(username, password, email)
                VALUES(?, ?, ?)
            """, (username, password, email))
            conn.commit()
            flash("Account created successfully! Please login.")
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            conn.close()
            return "Username already exists! Please choose another."
        except Exception as e:
            conn.close()
            return f"Error: {str(e)}"
    return render_template("signup.html")

# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        
        if not username or not password:
            return "Username and password are required!"
        
        conn = sqlite3.connect("database/budget.db")
        cursor = conn.cursor()
        
        # Check if user exists
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # Check password
            if user[2] == password:  # password is at index 2
                session['user'] = username
                return redirect('/')
            else:
                return "Invalid Password! Please try again."
        else:
            return "Username not found! Please sign up first."
    
    return render_template("login.html")

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
    return redirect('/')

# ================= PROFILE SETTINGS =================
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user' not in session:
        return redirect('/login')
    
    username = session['user']
    conn = sqlite3.connect("database/budget.db")
    cur = conn.cursor()
    
    if request.method == "POST":
        new_username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password'].strip()
        
        # Check if new username already exists (if changed)
        if new_username != username:
            cur.execute("SELECT username FROM users WHERE username=?", (new_username,))
            if cur.fetchone():
                conn.close()
                return "Username already exists! Please choose another."
        
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

# ================= UPLOAD CSV (SAFE VERSION) =================
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
    path = os.path.join("uploads", filename)
    file.save(path)
    
    conn = sqlite3.connect("database/budget.db")
    cursor = conn.cursor()
    
    with open(path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        
        for row in reader:
            # Safe check: skip rows with missing columns
            if len(row) < 6:
                continue
            
            title = row[0]
            
            # Safe amount conversion
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
    conn = sqlite3.connect("database/budget.db")
    cursor = conn.cursor()
    
    # GET USER PROFILE DATA
    cursor.execute("SELECT email, photo FROM users WHERE username=?", (username,))
    user_data = cursor.fetchone()
    user_email = user_data[0] if user_data else ""
    user_photo = user_data[1] if user_data and user_data[1] else "default.png"
    
    # ADD TRANSACTION
    if request.method == "POST":
        title = request.form['title']
        amount = float(request.form['amount'])
        t_type = request.form['type']
        category = request.form['category']
        item = request.form['item']
        date = request.form['date']
        
        cursor.execute("""
            INSERT INTO transactions (username,title,amount,type,category,item,date)
            VALUES(?,?,?,?,?,?,?)
        """, (username,title,amount,t_type,category,item,date))
        conn.commit()
    
    # FETCH DATA
    cursor.execute("SELECT * FROM transactions WHERE username=?", (username,))
    transactions = cursor.fetchall()
    
    total = 0
    income = 0
    expense = 0
    monthly_data = {}
    
    # ================= CATEGORY ANALYTICS =================
    category_data = {}
    
    # SAFE FIX: Handle both old and new database schemas
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
            # category calculation only for expenses
            category_data[category] = category_data.get(category, 0) + amt
        
        monthly_data[month] = monthly_data.get(month, 0) + abs(amt)
    
    # ================= SMART EXPENSE PREDICTION =================
    predicted_expense = round(expense + (expense * 0.1), 2)
    
    prediction_message = "Spending looks stable ✅"
    
    if expense > (budget_limit * 0.8):
        prediction_message = "⚠ Food or daily spending may increase"
    
    if total > 5000:
        prediction_message = "📈 Savings trend improving"
    
    # ================= TOP CATEGORY =================
    top_category = "None"
    if category_data:
        top_category = max(category_data, key=category_data.get)
    
    # WARNING
    warning = "✅ Budget Under Control"
    if expense > budget_limit:
        warning = "⚠ Budget Exceeded"
    
    # ================= SMART SUGGESTIONS =================
    suggestions = []
    
    food_swap = {
        "dosai": "Idli",
        "poori": "Idli",
        "pizza": "Home food",
        "burger": "Sandwich",
        "chips": "Fruits",
        "fried rice": "Meals",
        "biryani": "Home rice"
    }
    
    travel_swap = {
        "bike": "Bus",
        "petrol": "Bus",
        "car": "Train",
        "cab": "Bus"
    }
    
    for t in transactions:
        category = str(t[5]).lower()
        item = str(t[7]).lower()   # IMPORTANT FIX - item column
        amount = t[3]
        
        if category == "food":
            save = round(amount * 0.20)
            
            # Line 1 - High expense warning
            suggestions.append(
                f"🍽 {item.title()}: Food expense high → Save ₹{save}"
            )
            
            # Line 2 - Alternative suggestion
            if item in food_swap:
                suggestions.append(
                    f"💡 {item.title()} ku pathila {food_swap[item]} try pannunga"
                )
        
        elif category == "travel":
            save = round(amount * 0.15)
            
            suggestions.append(
                f"⛽ {item.title()}: Travel expense high → Save ₹{save}"
            )
            
            if item in travel_swap:
                suggestions.append(
                    f"💡 {item.title()} ku pathila {travel_swap[item]} use pannunga"
                )
    
    if not suggestions:
        suggestions.append("✅ Spending looks balanced")
    
    # ================= SMART INSIGHTS =================
    category_total = defaultdict(float)
    item_total = defaultdict(float)
    
    for t in transactions:
        category = t[5]
        item = t[7]  # item column
        amount = t[3]
        
        category_total[category] += amount
        item_total[item] += amount
    
    # TOP CATEGORY from insights
    top_spent_category = max(category_total, key=category_total.get) if category_total else "None"
    
    # TOP ITEM
    top_item = max(item_total, key=item_total.get) if item_total else "None"
    
    # TOTAL SAVINGS ESTIMATE (simple logic)
    estimated_savings = expense * 0.2
    
    insight = f"""
📊 Top Spending Category: {top_spent_category}
🍽 Most Expensive Item: {top_item}
💰 Estimated Monthly Savings: ₹{round(estimated_savings)}
"""
    
    # ================= PIE CHART =================
    plt.figure()
    plt.pie([income if income > 0 else 1, expense], labels=["Income", "Expense"], autopct="%1.1f%%")
    plt.savefig("static/chart.png")
    plt.close()
    
    # ================= MONTHLY CHART =================
    plt.figure(figsize=(8,5))
    months = sorted(monthly_data.keys())
    values = [monthly_data[m] for m in months]
    plt.bar(months, values)
    plt.title("Monthly Expense Analysis")
    plt.xticks(rotation=30)
    plt.tight_layout()
    plt.savefig("static/monthly_chart.png", bbox_inches='tight')
    plt.close()
    
    # ================= CATEGORY CHART =================
    if category_data:
        plt.figure()
        plt.pie(
            category_data.values(),
            labels=category_data.keys(),
            autopct="%1.1f%%"
        )
        plt.title("Category Analytics")
        plt.savefig("static/category_chart.png")
        plt.close()
    
    conn.close()
    
    # ================= RENDER TEMPLATE WITH ALL DATA =================
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
        suggestions=suggestions,
        insight=insight,
        predicted_expense=predicted_expense,
        prediction_message=prediction_message,
        category_data=category_data
    )

# ================= CHATBOT =================
@app.route('/chatbot', methods=['POST'])
def chatbot():
    msg = request.form['message'].lower()
    if "income" in msg:
        reply = "Income means money you earn 💰"
    elif "expense" in msg:
        reply = "Expense means money you spend 💸"
    elif "budget" in msg:
        reply = "Budget is your spending limit ⚙"
    else:
        reply = "Ask about income, expense, budget"
    return jsonify({"reply": reply})

# ================= PDF =================
@app.route('/pdf')
def pdf():
    username = session['user']
    conn = sqlite3.connect("database/budget.db")
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
    conn = sqlite3.connect("database/budget.db")
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
    
    return Response(
        generate(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment; filename=budget.csv"}
    )

# ================= DELETE =================
@app.route('/delete/<int:id>')
def delete(id):
    conn = sqlite3.connect("database/budget.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect('/')

# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)