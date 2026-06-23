from flask import Flask, render_template, request, redirect, Response, session, jsonify
import sqlite3
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from flask_mail import Mail, Message
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

from collections import Counter

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
date TEXT
)
""")

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
        date = request.form['date']

        cursor.execute("""
            INSERT INTO transactions(username,title,amount,type,category,date)
            VALUES(?,?,?,?,?,?)
        """, (username, title, amount, t_type, category, date))

        conn.commit()

    # FETCH DATA
    cursor.execute(
        "SELECT * FROM transactions WHERE username=?",
        (username,)
    )

    transactions = cursor.fetchall()

    total = 0
    income = 0
    expense = 0
    monthly_data = {}

    for t in transactions:
        amount = t[3]
        t_type = t[4]
        month = t[6][:7]

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

    # ================= PIE CHART =================
    plt.figure()
    plt.pie(
        [income if income > 0 else 1, expense],
        labels=["Income", "Expense"],
        autopct="%1.1f%%"
    )
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
        top_category=top_category
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

    cursor.execute(
        "SELECT * FROM transactions WHERE username=?",
        (username,)
    )

    data = cursor.fetchall()
    conn.close()

    def generate():
        yield "Title,Amount,Type,Category,Date\n"
        for row in data:
            yield f"{row[2]},{row[3]},{row[4]},{row[5]},{row[6]}\n"

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
    app.run(host="0.0.0.0", port=5000)