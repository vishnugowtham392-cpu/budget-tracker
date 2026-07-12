# ================= UPDATED IMPORTS =================
from flask import Flask, render_template, request, redirect, Response, session, jsonify, flash
import sqlite3
import os
import csv
import traceback
from werkzeug.utils import secure_filename
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot asplt
from flask_mail import Mail, Message
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from collections import Counter, defaultdict

app = Flask(__name__)
app.secret_key = "budgettracker"

# ================= DATABASE CONNECTION (SQLITE ONLY) =================
# Get the absolute path to the database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database", "budget.db")

def get_db_connection():
    """Get SQLite database connection"""
    try:
        # Ensure database directory exists
        os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
        
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        raise

def init_db():
    """Initialize database tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                email TEXT,
                photo TEXT DEFAULT 'default.png'
            )
        """)
        
        # Create transactions table
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
        print(f"📁 Database path: {DATABASE_PATH}")
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        print(traceback.format_exc())
        raise

# ================= UPLOAD SETTINGS =================
app.config['UPLOAD_FOLDER'] = "static/uploads"

# ================= EMAIL CONFIG =================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'yourgmail@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'
mail = Mail(app)

budget_limit = 5000

# ================= FOLDERS =================
os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "uploads"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static", "profiles"), exist_ok=True)
os.makedirs(os.path.join(BASE_DIR, "static", "uploads"), exist_ok=True)

# ================= DATABASE INIT =================
init_db()

# ================= ERROR HANDLING =================
@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all exceptions and return error message"""
    error_msg = str(e)
    print(f"❌ Error: {error_msg}")
    print(traceback.format_exc())
    return f"Error: {error_msg}", 500

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
            flash("All fields are required!")
            return render_template("signup.html")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users(username, password, email)
                VALUES(?, ?, ?)
            """, (username, password, email))
            conn.commit()
            flash("Account created successfully! Please login.")
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash("Username already exists! Please choose another.")
            return render_template("signup.html")
        except Exception as e:
            print(f"Signup error: {e}")
            flash("An error occurred. Please try again.")
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
                    # Check password (index 2)
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
        
        # Handle photo upload
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
    
    # GET USER PROFILE DATA
    try:
        cursor.execute("SELECT email, photo FROM users WHERE username=?", (username,))
        user_data = cursor.fetchone()
        user_email = user_data[0] if user_data else ""
        user_photo = user_data[1] if user_data and user_data[1] else "default.png"
    except Exception as e:
        print(f"Error fetching user data: {e}")
        user_email = ""
        user_photo = "default.png"
    
    # ================= ADD TRANSACTION =================
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
    
    # FETCH DATA
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
    
    # ================= AI EXPENSE PREDICTION =================
    future_expense = int(expense * 1.10)
    
    if expense < income:
        prediction_status = "📈 Good Financial Growth"
        prediction_msg = "Your savings pattern is improving. Keep maintaining spending discipline."
    elif expense == income:
        prediction_status = "⚠ Balanced Spending"
        prediction_msg = "Income and expenses are equal. Try increasing savings."
    else:
        prediction_status = "🚨 High Expense Alert"
        prediction_msg = "Expenses are increasing. Reduce unnecessary spending."
    
    saving_goal = int(income * 0.20)
    
    # ================= TOP CATEGORY =================
    top_category = "None"
    if category_data:
        top_category = max(category_data, key=category_data.get)
    
    # WARNING
    warning = "✅ Budget Under Control"
    if expense > budget_limit:
        warning = "⚠ Budget Exceeded"
    
    # ================= SMART INSIGHTS =================
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
    
    # ================= SMART AI SAVING SYSTEM =================
    smart_items = {
        "idli": {
            "alternative": "Home-made Idli 🥣",
            "reason": "Home food usually costs less",
            "benefit": "Healthy breakfast + lower spending",
            "motivation": "Healthy mornings create healthy savings 🌞"
        },
        "dosai": {
            "alternative": "Idli 🥣",
            "reason": "Less oil and lower cost",
            "benefit": "Healthy and saves money",
            "motivation": "Small savings create big results 💪"
        },
        "dosa": {
            "alternative": "Idli 🥣",
            "reason": "Less oil and lower cost",
            "benefit": "Healthy and saves money",
            "motivation": "Small savings create big results 💪"
        },
        "poori": {
            "alternative": "Chapathi 🌮",
            "reason": "Poori contains more oil",
            "benefit": "Healthier option",
            "motivation": "Choose smart food choices 🏃"
        },
        "puri": {
            "alternative": "Chapathi 🌮",
            "reason": "Poori contains more oil",
            "benefit": "Healthier option",
            "motivation": "Choose smart food choices 🏃"
        },
        "pongal": {
            "alternative": "Ragi Porridge 🌾",
            "reason": "Nutritious and economical",
            "benefit": "Energy + savings",
            "motivation": "Healthy body, healthy wallet ✨"
        },
        "uppuma": {
            "alternative": "Oats Porridge 🥣",
            "reason": "Uppuma contains more oil",
            "benefit": "Better nutrition + savings",
            "motivation": "Healthy food, healthy life 💪"
        },
        "upma": {
            "alternative": "Oats Porridge 🥣",
            "reason": "Upma contains more oil",
            "benefit": "Better nutrition + savings",
            "motivation": "Healthy food, healthy life 💪"
        },
        "chapathi": {
            "alternative": "Home-made Chapathi 🌮",
            "reason": "Outside chapathi costs more",
            "benefit": "Save money + healthy food",
            "motivation": "Home food is always best 🏠"
        },
        "chapati": {
            "alternative": "Home-made Chapathi 🌮",
            "reason": "Outside chapathi costs more",
            "benefit": "Save money + healthy food",
            "motivation": "Home food is always best 🏠"
        },
        "omelette": {
            "alternative": "Boiled Egg 🥚",
            "reason": "Omelette uses more oil",
            "benefit": "Healthy protein + less oil",
            "motivation": "Healthy eating, healthy savings 💪"
        },
        "bread": {
            "alternative": "Home-made Chapathi 🌮",
            "reason": "Bread is processed food",
            "benefit": "Fresh and healthy food",
            "motivation": "Fresh food is always better 🏠"
        },
        "briyani": {
            "alternative": "Meals 🍛",
            "reason": "Briyani often costs more",
            "benefit": "Balanced food + save money",
            "motivation": "Reduce cost without losing satisfaction 😄"
        },
        "biryani": {
            "alternative": "Meals 🍛",
            "reason": "Briyani often costs more",
            "benefit": "Balanced food + save money",
            "motivation": "Reduce cost without losing satisfaction 😄"
        },
        "fried rice": {
            "alternative": "Lemon Rice 🍋",
            "reason": "Simple foods cost less",
            "benefit": "Save money + lighter food",
            "motivation": "Simple habits grow savings 💰"
        },
        "noodles": {
            "alternative": "Veg Pasta 🍝",
            "reason": "Noodles are processed food",
            "benefit": "Healthy alternative + savings",
            "motivation": "Eat healthy, save money 🌟"
        },
        "meals": {
            "alternative": "Mini Meals 🍽",
            "reason": "Large meals increase spending",
            "benefit": "Reduce unnecessary expense",
            "motivation": "Spend wisely 🎯"
        },
        "thali": {
            "alternative": "Mini Meals 🍽",
            "reason": "Large thali costs more",
            "benefit": "Save money + less food waste",
            "motivation": "Eat less, save more 💰"
        },
        "pizza": {
            "alternative": "Home-made Pizza 🍕",
            "reason": "Outside pizza costs more",
            "benefit": "Same taste + less cost",
            "motivation": "Make pizza at home 🏠"
        },
        "burger": {
            "alternative": "Sandwich 🥪",
            "reason": "Fast food is expensive",
            "benefit": "Healthy + savings",
            "motivation": "Homemade is always better 🏠"
        },
        "sandwich": {
            "alternative": "Home-made Sandwich 🥪",
            "reason": "Outside sandwich costs more",
            "benefit": "Fresh and healthy",
            "motivation": "Home food is always fresh 🏠"
        },
        "chips": {
            "alternative": "Fruits 🍎",
            "reason": "Chips are processed snacks",
            "benefit": "Better nutrition + savings",
            "motivation": "Healthy snacks, healthy life 🌟"
        },
        "biscuit": {
            "alternative": "Home-made Snacks 🍪",
            "reason": "Packaged biscuits are expensive",
            "benefit": "Save money + eat healthy",
            "motivation": "Home snacks are best 🏠"
        },
        "samosa": {
            "alternative": "Idli 🥣",
            "reason": "Samosa is oily and expensive",
            "benefit": "Healthy food + savings",
            "motivation": "Choose healthy snacks 💪"
        },
        "vada": {
            "alternative": "Idli 🥣",
            "reason": "Vada is deep fried",
            "benefit": "Less oil + save money",
            "motivation": "Healthy choices matter 🌟"
        },
        "bonda": {
            "alternative": "Idli 🥣",
            "reason": "Bonda is oily",
            "benefit": "Healthy alternative + savings",
            "motivation": "Smart snack choices 💪"
        },
        "bondas": {
            "alternative": "Idli 🥣",
            "reason": "Bonda is oily",
            "benefit": "Healthy alternative + savings",
            "motivation": "Smart snack choices 💪"
        },
        "pakoda": {
            "alternative": "Fruits 🍎",
            "reason": "Pakoda is deep fried",
            "benefit": "Healthy + save money",
            "motivation": "Choose fruits over fried 🍎"
        },
        "cutlet": {
            "alternative": "Boiled Vegetables 🥗",
            "reason": "Cutlet is oily",
            "benefit": "Healthy + savings",
            "motivation": "Eat healthy, stay fit 💪"
        },
        "tea": {
            "alternative": "Home-made Tea ☕",
            "reason": "Daily outside tea adds up",
            "benefit": "Reduce repeated expenses",
            "motivation": "₹20/day ≈ ₹600/month 💰"
        },
        "chai": {
            "alternative": "Home-made Tea ☕",
            "reason": "Daily outside tea adds up",
            "benefit": "Reduce repeated expenses",
            "motivation": "₹20/day ≈ ₹600/month 💰"
        },
        "coffee": {
            "alternative": "Milk/Home Coffee 🥛",
            "reason": "Outside coffee is expensive",
            "benefit": "Lower cost",
            "motivation": "Save little, gain more 🚀"
        },
        "cafe": {
            "alternative": "Milk/Home Coffee 🥛",
            "reason": "Outside coffee is expensive",
            "benefit": "Lower cost",
            "motivation": "Save little, gain more 🚀"
        },
        "cool drink": {
            "alternative": "Lemon Juice 🍋",
            "reason": "Cool drinks are unhealthy",
            "benefit": "Healthy + savings",
            "motivation": "Choose natural drinks 🌿"
        },
        "soda": {
            "alternative": "Lemon Juice 🍋",
            "reason": "Soda is unhealthy",
            "benefit": "Healthy + savings",
            "motivation": "Natural is always better 🌿"
        },
        "juice": {
            "alternative": "Home-made Juice 🥤",
            "reason": "Outside juice costs more",
            "benefit": "Save money + healthy",
            "motivation": "Home juice is best 🏠"
        },
        "milkshake": {
            "alternative": "Home-made Milkshake 🥛",
            "reason": "Outside milkshake costs more",
            "benefit": "Save money + healthy",
            "motivation": "Make milkshake at home 🏠"
        },
        "parotta": {
            "alternative": "Chapathi 🌮",
            "reason": "Heavy oily foods affect health",
            "benefit": "Better digestion + savings",
            "motivation": "Healthy nights matter 🌙"
        },
        "paratha": {
            "alternative": "Chapathi 🌮",
            "reason": "Heavy oily foods affect health",
            "benefit": "Better digestion + savings",
            "motivation": "Healthy nights matter 🌙"
        },
        "shawarma": {
            "alternative": "Chapathi Roll 🌯",
            "reason": "Fast food costs more",
            "benefit": "Healthy and economical",
            "motivation": "Smart food, smart future 💪"
        },
        "kfc": {
            "alternative": "Home-made Chicken 🍗",
            "reason": "Fast food is expensive",
            "benefit": "Same taste + less cost",
            "motivation": "Make at home 🏠"
        },
        "fried chicken": {
            "alternative": "Home-made Chicken 🍗",
            "reason": "Fast food is expensive",
            "benefit": "Same taste + less cost",
            "motivation": "Make at home 🏠"
        },
        "mutton": {
            "alternative": "Chicken 🍗",
            "reason": "Mutton is expensive",
            "benefit": "Lower cost + healthy",
            "motivation": "Choose affordable protein 💰"
        },
        "movie": {
            "alternative": "Watch OTT 📺",
            "reason": "Theatre ticket + snacks increase spending",
            "benefit": "Lower entertainment cost",
            "motivation": "Enjoy more, spend less 🎬"
        },
        "cinema": {
            "alternative": "Watch OTT 📺",
            "reason": "Theatre ticket + snacks increase spending",
            "benefit": "Lower entertainment cost",
            "motivation": "Enjoy more, spend less 🎬"
        },
        "theatre": {
            "alternative": "Watch with OTT Subscription 📺",
            "reason": "Travel + tickets + snacks increase expense",
            "benefit": "Entertainment at lower cost",
            "motivation": "Entertainment + savings balance 💰"
        },
        "popcorn": {
            "alternative": "Home Snacks 🍿",
            "reason": "Theatre snacks are expensive",
            "benefit": "Same enjoyment with lower cost",
            "motivation": "Small snack savings become big savings 😄"
        },
        "gaming": {
            "alternative": "Free Games 🎮",
            "reason": "Paid games increase expenses",
            "benefit": "Same fun + savings",
            "motivation": "Free games are also fun 🎮"
        },
        "pub": {
            "alternative": "Home Party 🏠",
            "reason": "Pubs are expensive",
            "benefit": "Save money + enjoy with friends",
            "motivation": "Home parties are better 🎉"
        },
        "club": {
            "alternative": "Home Party 🏠",
            "reason": "Clubs are expensive",
            "benefit": "Save money",
            "motivation": "Home parties are more fun 🎉"
        },
        "netflix": {
            "alternative": "Watch Free Content 📺",
            "reason": "Multiple subscriptions cost more",
            "benefit": "Save on subscriptions",
            "motivation": "Watch content wisely 📺"
        },
        "amazon prime": {
            "alternative": "Watch Free Content 📺",
            "reason": "Multiple subscriptions cost more",
            "benefit": "Save on subscriptions",
            "motivation": "Watch content wisely 📺"
        },
        "hotstar": {
            "alternative": "Watch Free Content 📺",
            "reason": "Multiple subscriptions cost more",
            "benefit": "Save on subscriptions",
            "motivation": "Watch content wisely 📺"
        },
        "petrol": {
            "alternative": "Public Transport 🚌",
            "reason": "Fuel costs increase over time",
            "benefit": "Reduce travel expenses",
            "motivation": "Travel smart 🌍"
        },
        "diesel": {
            "alternative": "Public Transport 🚌",
            "reason": "Fuel costs increase over time",
            "benefit": "Reduce travel expenses",
            "motivation": "Travel smart 🌍"
        },
        "bus": {
            "alternative": "Cycle/Shared Auto 🚲",
            "reason": "Daily bus fare adds up",
            "benefit": "Save on daily travel",
            "motivation": "Cycle more, save more 🌿"
        },
        "auto": {
            "alternative": "Public Bus 🚌",
            "reason": "Auto fares are higher",
            "benefit": "Save on travel",
            "motivation": "Choose cheaper transport 💰"
        },
        "cab": {
            "alternative": "Public Transport 🚌",
            "reason": "Cab is expensive",
            "benefit": "Save money on travel",
            "motivation": "Save money, travel smart 🚌"
        },
        "uber": {
            "alternative": "Public Transport 🚌",
            "reason": "Uber is expensive",
            "benefit": "Save money on travel",
            "motivation": "Choose cheaper options 🚌"
        },
        "ola": {
            "alternative": "Public Transport 🚌",
            "reason": "Ola is expensive",
            "benefit": "Save money on travel",
            "motivation": "Choose cheaper options 🚌"
        },
        "rapido": {
            "alternative": "Public Bus 🚌",
            "reason": "Rapido is expensive for long distance",
            "benefit": "Save money",
            "motivation": "Use bus for longer trips 🚌"
        },
        "bike": {
            "alternative": "Public Transport 🚌",
            "reason": "Bike maintenance + fuel costs",
            "benefit": "Reduce expenses",
            "motivation": "Travel smart, save money 💰"
        },
        "car": {
            "alternative": "Public Transport 🚌",
            "reason": "Car maintenance + fuel + parking",
            "benefit": "Save a lot on travel",
            "motivation": "Public transport saves money 🌍"
        },
        "flight": {
            "alternative": "Train Journey 🚂",
            "reason": "Flights are expensive",
            "benefit": "Save money on travel",
            "motivation": "Train journeys are scenic and cheap 🚂"
        },
        "water bottle": {
            "alternative": "Carry Water Bottle 🚰",
            "reason": "Daily purchases increase cost",
            "benefit": "Reduce daily expenses",
            "motivation": "Daily savings become monthly savings 💧"
        },
        "mobile recharge": {
            "alternative": "Long-term Plan 📱",
            "reason": "Frequent recharges cost more",
            "benefit": "Better value",
            "motivation": "Spend once and save more 💡"
        },
        "phone recharge": {
            "alternative": "Long-term Plan 📱",
            "reason": "Frequent recharges cost more",
            "benefit": "Better value",
            "motivation": "Spend once and save more 💡"
        },
        "electricity": {
            "alternative": "Use Energy Efficient Devices 💡",
            "reason": "High electricity bills",
            "benefit": "Reduce monthly bills",
            "motivation": "Save power, save money 💡"
        },
        "water": {
            "alternative": "Use Water Wisely 💧",
            "reason": "Wasting water increases bills",
            "benefit": "Reduce water bills",
            "motivation": "Save water, save money 💧"
        },
        "gas": {
            "alternative": "Use Induction Cooktop 🔥",
            "reason": "Gas prices increase",
            "benefit": "Save on fuel",
            "motivation": "Use efficient cooking 🔥"
        },
        "cylinders": {
            "alternative": "Use Induction Cooktop 🔥",
            "reason": "Gas cylinder prices increase",
            "benefit": "Save money",
            "motivation": "Use efficient cooking 🔥"
        },
        "oil": {
            "alternative": "Buy in Bulk 🛒",
            "reason": "Small packets cost more",
            "benefit": "Save money",
            "motivation": "Bulk buying saves money 💰"
        },
        "rice": {
            "alternative": "Buy in Bulk 🛒",
            "reason": "Small packets cost more",
            "benefit": "Save money",
            "motivation": "Bulk buying saves money 💰"
        },
        "wheat": {
            "alternative": "Buy in Bulk 🛒",
            "reason": "Small packets cost more",
            "benefit": "Save money",
            "motivation": "Bulk buying saves money 💰"
        },
        "sugar": {
            "alternative": "Buy in Bulk 🛒",
            "reason": "Small packets cost more",
            "benefit": "Save money",
            "motivation": "Bulk buying saves money 💰"
        },
        "flour": {
            "alternative": "Buy in Bulk 🛒",
            "reason": "Small packets cost more",
            "benefit": "Save money",
            "motivation": "Bulk buying saves money 💰"
        },
        "dal": {
            "alternative": "Buy in Bulk 🛒",
            "reason": "Small packets cost more",
            "benefit": "Save money",
            "motivation": "Bulk buying saves money 💰"
        },
        "clothes": {
            "alternative": "Season Sale Shopping 👕",
            "reason": "Regular prices are high",
            "benefit": "Save on shopping",
            "motivation": "Sale shopping saves money 🛍"
        },
        "shirt": {
            "alternative": "Season Sale Shopping 👕",
            "reason": "Regular prices are high",
            "benefit": "Save on shopping",
            "motivation": "Sale shopping saves money 🛍"
        },
        "pants": {
            "alternative": "Season Sale Shopping 👖",
            "reason": "Regular prices are high",
            "benefit": "Save on shopping",
            "motivation": "Sale shopping saves money 🛍"
        },
        "shoes": {
            "alternative": "Season Sale Shopping 👟",
            "reason": "Regular prices are high",
            "benefit": "Save on shopping",
            "motivation": "Sale shopping saves money 🛍"
        },
        "jeans": {
            "alternative": "Season Sale Shopping 👖",
            "reason": "Regular prices are high",
            "benefit": "Save on shopping",
            "motivation": "Sale shopping saves money 🛍"
        },
        "t-shirt": {
            "alternative": "Season Sale Shopping 👕",
            "reason": "Regular prices are high",
            "benefit": "Save on shopping",
            "motivation": "Sale shopping saves money 🛍"
        },
        "mobile": {
            "alternative": "Buy During Sale 📱",
            "reason": "Regular prices are higher",
            "benefit": "Save money on electronics",
            "motivation": "Wait for sale to save 💰"
        },
        "laptop": {
            "alternative": "Buy During Sale 💻",
            "reason": "Regular prices are higher",
            "benefit": "Save money on electronics",
            "motivation": "Wait for sale to save 💰"
        },
        "tv": {
            "alternative": "Buy During Sale 📺",
            "reason": "Regular prices are higher",
            "benefit": "Save money on electronics",
            "motivation": "Wait for sale to save 💰"
        },
        "earphones": {
            "alternative": "Buy During Sale 🎧",
            "reason": "Regular prices are higher",
            "benefit": "Save money",
            "motivation": "Wait for sale to save 💰"
        },
        "headphones": {
            "alternative": "Buy During Sale 🎧",
            "reason": "Regular prices are higher",
            "benefit": "Save money",
            "motivation": "Wait for sale to save 💰"
        },
        "medicine": {
            "alternative": "Generic Medicine 💊",
            "reason": "Branded medicines cost more",
            "benefit": "Same effect + savings",
            "motivation": "Generic medicines are equally effective 💊"
        },
        "tablet": {
            "alternative": "Generic Medicine 💊",
            "reason": "Branded medicines cost more",
            "benefit": "Same effect + savings",
            "motivation": "Generic medicines are equally effective 💊"
        },
        "doctor": {
            "alternative": "Government Hospital 🏥",
            "reason": "Private doctors are expensive",
            "benefit": "Save on medical bills",
            "motivation": "Government hospitals are affordable 🏥"
        },
        "salon": {
            "alternative": "Home Grooming 💇",
            "reason": "Salon visits are expensive",
            "benefit": "Save money",
            "motivation": "Learn home grooming 💇"
        },
        "haircut": {
            "alternative": "Local Barber 💇",
            "reason": "Premium salons cost more",
            "benefit": "Save money",
            "motivation": "Local barbers are cheaper 💇"
        },
        "makeup": {
            "alternative": "Home Makeup 💄",
            "reason": "Professional makeup costs more",
            "benefit": "Save money",
            "motivation": "Learn home makeup 💄"
        },
        "books": {
            "alternative": "Library Books 📚",
            "reason": "New books are expensive",
            "benefit": "Save money on books",
            "motivation": "Libraries are treasure 🏛"
        },
        "courses": {
            "alternative": "Free Online Courses 📖",
            "reason": "Paid courses are expensive",
            "benefit": "Same knowledge + free",
            "motivation": "Learn for free 🎓"
        },
        "tution": {
            "alternative": "Online Learning 📖",
            "reason": "Tuition fees are high",
            "benefit": "Save money on education",
            "motivation": "Learn online for free 🎓"
        },
        "gym": {
            "alternative": "Home Workout 💪",
            "reason": "Gym membership is expensive",
            "benefit": "Save money + flexible timing",
            "motivation": "Home workout is also effective 💪"
        },
        "protein": {
            "alternative": "Natural Protein 🥗",
            "reason": "Protein powders are expensive",
            "benefit": "Save money + natural",
            "motivation": "Natural food is best 🥗"
        },
        "hotel": {
            "alternative": "Hostel/Home Stay 🏠",
            "reason": "Hotels are expensive",
            "benefit": "Save on accommodation",
            "motivation": "Budget stays are good 🏠"
        },
        "tour": {
            "alternative": "Budget Travel 🎒",
            "reason": "Luxury tours are expensive",
            "benefit": "Save money",
            "motivation": "Budget travel is fun 🎒"
        },
        "foreign trip": {
            "alternative": "Domestic Trip 🇮🇳",
            "reason": "Foreign trips are expensive",
            "benefit": "Save money + explore India",
            "motivation": "India has many beautiful places 🇮🇳"
        }
    }
    
    # ================= GENERATE SMART SUGGESTIONS =================
    suggestions = []
    
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
    
    # ================= CHARTS (FIXED - DYNAMIC) =================
    try:
        # 1. Income vs Expense Pie Chart
        plt.figure()
        if income > 0 or expense > 0:
            plt.pie([income if income > 0 else 1, expense if expense > 0 else 1], 
                    labels=["Income", "Expense"], autopct="%1.1f%%")
        else:
            plt.text(0.5, 0.5, "No Data Available", ha="center", va="center", fontsize=14)
        plt.savefig("static/chart.png")
        plt.close()
        
        # 2. Monthly Expense Bar Chart
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
        
        # 3. Category Analytics Pie Chart (FIXED - Dynamic Categories)
        plt.figure(figsize=(6,6))
        if category_data:
            # Dynamically create labels and values from actual data
            labels = list(category_data.keys())
            values = list(category_data.values())
            
            # Only show categories with values > 0
            filtered_data = {k: v for k, v in category_data.items() if v > 0}
            
            if filtered_data:
                plt.pie(filtered_data.values(), 
                        labels=filtered_data.keys(), 
                        autopct="%1.1f%%")
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
        category_data=category_data
    )

# ================= DEBUG DATABASE ROUTE =================
@app.route('/debug/db')
def debug_db():
    if 'user' not in session:
        return redirect('/login')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all transactions for the user
    cursor.execute("SELECT * FROM transactions WHERE username=?", (session['user'],))
    transactions = cursor.fetchall()
    
    # Get user info
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
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)