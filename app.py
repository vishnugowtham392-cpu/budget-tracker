from flask import Flask, render_template, request, redirect, Response, session, jsonify
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

# ================= DATABASE INIT =================
conn = sqlite3.connect("database/budget.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
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
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect("database/budget.db")
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users(username,password) VALUES(?,?)",
                (username, password)
            )
            conn.commit()
        except:
            conn.close()
            return "Username already exists"
        conn.close()
        return redirect('/login')
    return render_template("signup.html")

# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect("database/budget.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        )
        user = cursor.fetchone()
        conn.close()
        if user:
            session['user'] = username
            return redirect('/')
        return "Invalid Login"
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
    
    # SAFE FIX: Handle both old and new database schemas
    for t in transactions:
        amount = t[3]
        t_type = t[4]
        
        if len(t) > 7:
            month = str(t[7])[:7]
            item = str(t[6])
        else:
            month = str(t[6])[:7]
            item = "Unknown"
        
        total += amount
        if t_type == "income":
            income += amount
        else:
            expense += amount
        monthly_data[month] = monthly_data.get(month, 0) + abs(amount)
    
    # TOP CATEGORY
    categories = [t[5] for t in transactions]
    top_category = Counter(categories).most_common(1)[0][0] if categories else "None"
    
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
    
    # TOP CATEGORY
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
    
    conn.close()
    
    return render_template(
        "index.html",
        username=username,
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
        insight=insight
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
    app.run(host="0.0.0.0", port=port)