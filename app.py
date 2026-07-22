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
import time
import random

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

# ================= DATABASE & FILE PATHS =================
IS_RENDER = os.environ.get('RENDER') == 'true'

if IS_RENDER:
    BASE_DIR = "/tmp"
    print("🔧 Running on Render - using /tmp for storage")
else:
    BASE_DIR = r"E:\Budget Tracker"
    print("🔧 Running locally - using E:\Budget Tracker")

DATABASE_PATH = os.path.join(BASE_DIR, "database", "budget.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PROFILES_DIR = os.path.join(STATIC_DIR, "profiles")

# Create database directory
os.makedirs(os.path.join(BASE_DIR, "database"), exist_ok=True)

for folder in [STATIC_DIR, UPLOAD_DIR, PROFILES_DIR]:
    os.makedirs(folder, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_DIR

print(f"✅ Database Location: {DATABASE_PATH}")
print(f"✅ Static Files: {STATIC_DIR}")
print(f"✅ Running on Render: {IS_RENDER}")

# ================= DATABASE FUNCTIONS =================
def get_db_connection():
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH) if os.path.dirname(DATABASE_PATH) else '.', exist_ok=True)
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
        
        test_conn = sqlite3.connect(DATABASE_PATH)
        test_conn.cursor().execute("SELECT 1")
        test_conn.close()
        print("✅ Database is writable")
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        raise

init_db()

# ================= GLOBAL VARIABLE =================
budget_limit = 5000

# ================= DAILY SUGGESTIONS DATABASE =================
DAILY_SUGGESTIONS = {
    "morning": [
        {"activity": "🌅 Wake up early", "save": "Save electricity by using natural light", "tip": "₹500/month saved on electricity"},
        {"activity": "☕ Home-made coffee/tea", "save": "Skip outside coffee", "tip": "₹600/month saved"},
        {"activity": "🥣 Eat breakfast at home", "save": "Avoid outside food", "tip": "₹1000/month saved"},
        {"activity": "🚶 Walk to nearby places", "save": "Save fuel money", "tip": "₹300/month saved"},
        {"activity": "📝 Plan your day", "save": "Avoid impulse spending", "tip": "₹2000/month saved"}
    ],
    "afternoon": [
        {"activity": "🍱 Pack lunch from home", "save": "Avoid ordering food", "tip": "₹1500/month saved"},
        {"activity": "💧 Drink water instead of soft drinks", "save": "Healthy and cheap", "tip": "₹300/month saved"},
        {"activity": "📚 Read instead of shopping", "save": "Avoid unnecessary purchases", "tip": "₹1000/month saved"},
        {"activity": "🚌 Use public transport", "save": "Save petrol/diesel", "tip": "₹800/month saved"},
        {"activity": "🛒 Make shopping list", "save": "Avoid impulse buying", "tip": "₹1500/month saved"}
    ],
    "evening": [
        {"activity": "🏋️ Exercise at home", "save": "Save gym membership", "tip": "₹1000/month saved"},
        {"activity": "🍳 Cook dinner at home", "save": "Save restaurant money", "tip": "₹2000/month saved"},
        {"activity": "📺 Watch free content", "save": "Cancel OTT subscriptions", "tip": "₹500/month saved"},
        {"activity": "🌿 Grow small plants", "save": "Save on vegetables", "tip": "₹300/month saved"},
        {"activity": "💡 Use LED bulbs", "save": "Save electricity bill", "tip": "₹200/month saved"}
    ],
    "weekly": [
        {"activity": "🛒 Bulk grocery shopping", "save": "Buy in bulk to save", "tip": "₹500/month saved"},
        {"activity": "🚗 Carpool with colleagues", "save": "Share fuel costs", "tip": "₹600/month saved"},
        {"activity": "🏠 DIY home repairs", "save": "Save service charges", "tip": "₹500/month saved"},
        {"activity": "📱 Use prepaid plan", "save": "Control mobile expenses", "tip": "₹200/month saved"},
        {"activity": "💳 Track all expenses", "save": "Identify waste", "tip": "₹1000/month saved"}
    ]
}

# ================= SMART ITEMS DATABASE =================
SMART_ITEMS = {
    "idli": {"alternative": "Home-made Idli 🥣", "reason": "Home food usually costs less", "benefit": "Healthy breakfast + lower spending", "motivation": "Healthy mornings create healthy savings 🌞"},
    "dosai": {"alternative": "Idli 🥣", "reason": "Less oil and lower cost", "benefit": "Healthy and saves money", "motivation": "Small savings create big results 💪"},
    "dosa": {"alternative": "Idli 🥣", "reason": "Less oil and lower cost", "benefit": "Healthy and saves money", "motivation": "Small savings create big results 💪"},
    "chips": {"alternative": "Fruits 🍎", "reason": "Chips are processed snacks", "benefit": "Better nutrition + savings", "motivation": "Healthy snacks, healthy life 🌟"},
    "petrol": {"alternative": "Public Transport 🚌", "reason": "Fuel costs increase over time", "benefit": "Reduce travel expenses", "motivation": "Travel smart 🌍"},
    "diesel": {"alternative": "Public Transport 🚌", "reason": "Fuel costs increase over time", "benefit": "Reduce travel expenses", "motivation": "Travel smart 🌍"},
    "tea": {"alternative": "Home-made Tea ☕", "reason": "Daily outside tea adds up", "benefit": "Reduce repeated expenses", "motivation": "₹20/day ≈ ₹600/month 💰"},
    "coffee": {"alternative": "Milk/Home Coffee 🥛", "reason": "Outside coffee is expensive", "benefit": "Lower cost", "motivation": "Save little, gain more 🚀"},
    "biscuit": {"alternative": "Home-made Snacks 🍪", "reason": "Packaged snacks are expensive", "benefit": "Healthy + savings", "motivation": "Homemade is always better ❤️"},
    "biscuits": {"alternative": "Home-made Snacks 🍪", "reason": "Packaged snacks are expensive", "benefit": "Healthy + savings", "motivation": "Homemade is always better ❤️"},
    "lunch": {"alternative": "Home-made Lunch 🍱", "reason": "Outside food is expensive", "benefit": "Save ₹1500/month", "motivation": "Packed with love ❤️"},
    "dinner": {"alternative": "Home-made Dinner 🍳", "reason": "Restaurant food is costly", "benefit": "Save ₹2000/month", "motivation": "Cook with love, save money 💰"},
    "movie": {"alternative": "Netflix/Amazon Prime 📺", "reason": "Theatre tickets are expensive", "benefit": "Save ₹500/month", "motivation": "Watch from home comfortably 🏠"},
    "zomato": {"alternative": "Cook at Home 🍳", "reason": "Delivery charges add up", "benefit": "Save ₹1000/month", "motivation": "Fresh and healthy food 🌿"},
    "swiggy": {"alternative": "Cook at Home 🍳", "reason": "Delivery charges add up", "benefit": "Save ₹1000/month", "motivation": "Fresh and healthy food 🌿"},
    "uber": {"alternative": "Public Transport 🚌", "reason": "Cab charges are high", "benefit": "Save ₹2000/month", "motivation": "Travel like a local 🌍"},
    "ola": {"alternative": "Public Transport 🚌", "reason": "Cab charges are high", "benefit": "Save ₹2000/month", "motivation": "Travel like a local 🌍"},
    "cigarette": {"alternative": "Stop Smoking 🚭", "reason": "Health is wealth", "benefit": "Save ₹3000/month + good health", "motivation": "Quit smoking, save life 💪"},
    "cigarettes": {"alternative": "Stop Smoking 🚭", "reason": "Health is wealth", "benefit": "Save ₹3000/month + good health", "motivation": "Quit smoking, save life 💪"},
    "alcohol": {"alternative": "Healthy Juice 🧃", "reason": "Alcohol is expensive", "benefit": "Save ₹5000/month + good health", "motivation": "Stay healthy, stay wealthy 💪"},
    "beer": {"alternative": "Healthy Juice 🧃", "reason": "Alcohol is expensive", "benefit": "Save ₹5000/month + good health", "motivation": "Stay healthy, stay wealthy 💪"},
    "branded": {"alternative": "Local Brands 🏷️", "reason": "Branded items are overpriced", "benefit": "Save 50% on shopping", "motivation": "Value for money 💰"},
    "gym": {"alternative": "Home Workout 🏋️", "reason": "Gym membership is expensive", "benefit": "Save ₹1000/month", "motivation": "Exercise at home 🏠"},
    "subscription": {"alternative": "Cancel Unused Subscriptions ❌", "reason": "You're paying for unused services", "benefit": "Save ₹500/month", "motivation": "Only pay for what you use 💡"},
    "netflix": {"alternative": "Free Alternatives 📺", "reason": "Multiple OTT subscriptions add up", "benefit": "Save ₹500/month", "motivation": "Share with friends 👥"},
    "amazon": {"alternative": "Plan Shopping 📝", "reason": "Impulse shopping is dangerous", "benefit": "Save ₹2000/month", "motivation": "List before you shop 📋"},
    "flipkart": {"alternative": "Plan Shopping 📝", "reason": "Impulse shopping is dangerous", "benefit": "Save ₹2000/month", "motivation": "List before you shop 📋"},
    "pizza": {"alternative": "Home-made Pizza 🍕", "reason": "Restaurant pizza is expensive", "benefit": "Save ₹500/month", "motivation": "Cook with family 👨‍👩‍👧"},
    "burger": {"alternative": "Home-made Burger 🍔", "reason": "Fast food is expensive", "benefit": "Save ₹500/month", "motivation": "Healthy homemade burgers 🌿"},
    "biriyani": {"alternative": "Home-made Biriyani 🍚", "reason": "Restaurant biriyani is costly", "benefit": "Save ₹600/month", "motivation": "Homemade is tastier ❤️"},
    "biryani": {"alternative": "Home-made Biriyani 🍚", "reason": "Restaurant biriyani is costly", "benefit": "Save ₹600/month", "motivation": "Homemade is tastier ❤️"},
    "chai": {"alternative": "Home-made Tea ☕", "reason": "Daily chai adds up", "benefit": "Save ₹600/month", "motivation": "₹20/day × 30 = ₹600 💰"},
    "coldrink": {"alternative": "Water/Juice 🧃", "reason": "Cold drinks are unhealthy", "benefit": "Save ₹300/month", "motivation": "Stay healthy, stay fit 🌿"},
    "icecream": {"alternative": "Home-made Ice Cream 🍦", "reason": "Store ice cream is expensive", "benefit": "Save ₹300/month", "motivation": "Make at home with love ❤️"},
    "chocolate": {"alternative": "Fruits 🍎", "reason": "Chocolates are expensive", "benefit": "Save ₹200/month", "motivation": "Healthy and sweet 🌿"},
    "cake": {"alternative": "Home-made Cake 🎂", "reason": "Store cake is expensive", "benefit": "Save ₹400/month", "motivation": "Bake with love ❤️"},
    "pastry": {"alternative": "Home-made Pastry 🍰", "reason": "Store pastry is expensive", "benefit": "Save ₹300/month", "motivation": "Homemade is better ❤️"},
    "sandwich": {"alternative": "Home-made Sandwich 🥪", "reason": "Store sandwich is expensive", "benefit": "Save ₹500/month", "motivation": "Fresh and healthy 🌿"},
    "noodles": {"alternative": "Home-made Noodles 🍜", "reason": "Restaurant noodles are expensive", "benefit": "Save ₹400/month", "motivation": "Make at home with veggies 🌿"},
    "pasta": {"alternative": "Home-made Pasta 🍝", "reason": "Restaurant pasta is expensive", "benefit": "Save ₹400/month", "motivation": "Italian at home 🇮🇹"},
    "friedrice": {"alternative": "Home-made Fried Rice 🍚", "reason": "Restaurant is expensive", "benefit": "Save ₹500/month", "motivation": "Chinese at home 🥢"},
    "fried rice": {"alternative": "Home-made Fried Rice 🍚", "reason": "Restaurant is expensive", "benefit": "Save ₹500/month", "motivation": "Chinese at home 🥢"},
    "maggi": {"alternative": "Home-made Maggi 🍜", "reason": "Store Maggi is expensive", "benefit": "Save ₹200/month", "motivation": "Make at home 🏠"},
    "egg": {"alternative": "Buy in Bulk 🥚", "reason": "Buying single is costly", "benefit": "Save ₹100/month", "motivation": "Bulk is better 💰"},
    "milk": {"alternative": "Buy in Bulk 🥛", "reason": "Buying single is costly", "benefit": "Save ₹150/month", "motivation": "Bulk is better 💰"},
    "curd": {"alternative": "Home-made Curd 🥛", "reason": "Store curd is expensive", "benefit": "Save ₹200/month", "motivation": "Make at home 🏠"},
    "yogurt": {"alternative": "Home-made Curd 🥛", "reason": "Store yogurt is expensive", "benefit": "Save ₹200/month", "motivation": "Make at home 🏠"},
    "butter": {"alternative": "Home-made Butter 🧈", "reason": "Store butter is expensive", "benefit": "Save ₹150/month", "motivation": "Make at home 🏠"},
    "jam": {"alternative": "Home-made Jam 🍓", "reason": "Store jam is expensive", "benefit": "Save ₹100/month", "motivation": "Make at home 🏠"},
    "honey": {"alternative": "Local Honey 🍯", "reason": "Branded honey is expensive", "benefit": "Save ₹200/month", "motivation": "Local is better 🌿"},
    "oil": {"alternative": "Buy in Bulk 🛢️", "reason": "Small packs are expensive", "benefit": "Save ₹300/month", "motivation": "Bulk is better 💰"},
    "sugar": {"alternative": "Buy in Bulk 🍚", "reason": "Small packs are expensive", "benefit": "Save ₹100/month", "motivation": "Bulk is better 💰"},
    "salt": {"alternative": "Buy in Bulk 🧂", "reason": "Small packs are expensive", "benefit": "Save ₹50/month", "motivation": "Bulk is better 💰"},
    "masala": {"alternative": "Buy in Bulk 🌶️", "reason": "Small packs are expensive", "benefit": "Save ₹150/month", "motivation": "Bulk is better 💰"},
    "spices": {"alternative": "Buy in Bulk 🌿", "reason": "Small packs are expensive", "benefit": "Save ₹200/month", "motivation": "Bulk is better 💰"},
    "veg": {"alternative": "Weekly Market 🥬", "reason": "Daily market is expensive", "benefit": "Save ₹400/month", "motivation": "Weekly shopping saves time & money 💰"},
    "vegetable": {"alternative": "Weekly Market 🥬", "reason": "Daily market is expensive", "benefit": "Save ₹400/month", "motivation": "Weekly shopping saves time & money 💰"},
    "vegetables": {"alternative": "Weekly Market 🥬", "reason": "Daily market is expensive", "benefit": "Save ₹400/month", "motivation": "Weekly shopping saves time & money 💰"},
    "fruit": {"alternative": "Weekly Market 🍎", "reason": "Daily market is expensive", "benefit": "Save ₹300/month", "motivation": "Weekly shopping saves time & money 💰"},
    "fruits": {"alternative": "Weekly Market 🍎", "reason": "Daily market is expensive", "benefit": "Save ₹300/month", "motivation": "Weekly shopping saves time & money 💰"},
    "soap": {"alternative": "Buy in Bulk 🧼", "reason": "Small packs are expensive", "benefit": "Save ₹100/month", "motivation": "Bulk is better 💰"},
    "shampoo": {"alternative": "Buy in Bulk 🧴", "reason": "Small packs are expensive", "benefit": "Save ₹150/month", "motivation": "Bulk is better 💰"},
    "toothpaste": {"alternative": "Buy in Bulk 🪥", "reason": "Small packs are expensive", "benefit": "Save ₹100/month", "motivation": "Bulk is better 💰"},
    "toothbrush": {"alternative": "Buy in Bulk 🪥", "reason": "Small packs are expensive", "benefit": "Save ₹50/month", "motivation": "Bulk is better 💰"}
}

# ================= AI CHATBOT RESPONSES =================
CHATBOT_RESPONSES = {
    "greeting": [
        "👋 Hello! I'm your Budget AI Assistant! How can I help you today?",
        "🤖 Hey there! Ready to save some money?",
        "💪 Hello! Let's make your finances better today!",
        "🌟 Welcome back! I'm here to help you save money!"
    ],
    "fun": [
        "😄 Why did the budget go to therapy? It had too many expenses!",
        "😂 What did the wallet say to the credit card? 'You're always taking me for granted!'",
        "🤣 How much does a budget weigh? Just a few cents!",
        "😅 What's a budget's favorite dance? The money-saving shuffle!",
        "😂 Why don't budgets tell secrets? Because they're always spent!",
        "🤣 What do you call a budget that's always right? A prophet (profit)!"
    ],
    "motivation": [
        "💪 Remember: Every rupee saved is a rupee earned!",
        "🌟 Small savings today = Big investments tomorrow!",
        "🚀 You're doing great! Keep tracking your expenses!",
        "🎯 Set a goal and watch your savings grow!",
        "💰 Rich people save first, spend later. Be like them!",
        "🔥 The best time to start saving was yesterday. The next best time is NOW!"
    ],
    "advice": [
        "📝 Track every expense - knowledge is power!",
        "🎯 Set a monthly budget and stick to it!",
        "🍱 Cook at home - it's healthier and cheaper!",
        "🚶 Walk or cycle for short distances - save fuel!",
        "📊 Review your expenses weekly - find waste!",
        "💳 Use cash instead of cards - feel the money leaving!"
    ],
    "entertainment": [
        "🎬 Movie recommendation: Watch 'The Pursuit of Happyness' - it's about never giving up!",
        "📚 Book recommendation: 'Rich Dad Poor Dad' - learn about money!",
        "🎵 Listen to 'Money' by Pink Floyd - classic rock song about money!",
        "🎮 Play saving games - make saving fun!",
        "📺 Watch finance YouTube channels - learn while entertained!"
    ],
    "daily_tip": [
        "🌅 Morning tip: Drink water before coffee - save ₹1000/year!",
        "🌞 Day tip: Walk during lunch break - save gym money!",
        "🌙 Night tip: Plan tomorrow's meals - save on food!",
        "📅 Weekly tip: Check all subscriptions - cancel unused ones!",
        "📆 Monthly tip: Review your bank statement - find hidden charges!"
    ]
}

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

# ================= CLEAR CACHE ROUTE - FIXED =================
@app.route('/clear-cache')
def clear_cache():
    if 'user' not in session:
        return redirect('/login')
    
    try:
        chart_files = ['chart.png', 'monthly_chart.png', 'category_chart.png']
        deleted = []
        for file in chart_files:
            file_path = os.path.join(STATIC_DIR, file)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted.append(file)
        
        if deleted:
            flash(f"✅ Cleared cache for: {', '.join(deleted)}")
        else:
            flash("✅ No cached charts found")
        
        return redirect('/')
        
    except Exception as e:
        flash(f"❌ Error clearing cache: {str(e)}")
        return redirect('/')

# ================= GET DAILY SUGGESTIONS =================
@app.route('/get-suggestions')
def get_suggestions():
    if 'user' not in session:
        return jsonify({"error": "Please login"}), 401
    
    current_hour = datetime.datetime.now().hour
    
    if 5 <= current_hour < 12:
        time_period = "morning"
    elif 12 <= current_hour < 17:
        time_period = "afternoon"
    elif 17 <= current_hour < 21:
        time_period = "evening"
    else:
        time_period = "weekly"
    
    suggestions = DAILY_SUGGESTIONS[time_period]
    random_suggestions = random.sample(suggestions, min(3, len(suggestions)))
    
    return jsonify({
        "time_period": time_period,
        "suggestions": random_suggestions
    })

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
        tips = [
            "🌅 Start your day with a budget plan",
            "☕ Make coffee at home - save ₹600/month",
            "🍱 Pack lunch - save ₹1500/month",
            "🚶 Walk short distances - save fuel",
            "💡 Turn off lights when not needed",
            "📱 Check your subscriptions monthly",
            "🛒 Make a shopping list and stick to it",
            "🏠 Cook dinner at home - save ₹2000/month"
        ]
        random_tips = random.sample(tips, min(3, len(tips)))
        tips_text = "\n".join([f"• {tip}" for tip in random_tips])
        
        fun_facts = [
            "💡 The average person spends ₹5000 on unnecessary items every month!",
            "💡 Saving ₹100 daily = ₹36,500 saved in a year!",
            "💡 70% of people don't track their expenses - you're already ahead!",
            "💡 The 50-30-20 rule: 50% needs, 30% wants, 20% savings!"
        ]
        fun_fact = random.choice(fun_facts)
        
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

💡 Smart Suggestions for You:
{tips_text}

{fun_fact}

🎯 Daily Motivation:
"Small savings today become big investments tomorrow. You can do this!"

💰 Challenge: Can you reduce your spending by 10% this month?

- Budget Analysis System ❤️
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
        msg.body = """
✅ Test email from Budget Tracker!

Your email is working perfectly! 🎉

Fun Fact: Did you know that tracking your expenses can save you up to 30% of your income?

Keep saving! 💰
        """
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
            
            print(f"✅ New user created: {username}")
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
    
    cur.execute("SELECT * FROM users WHERE username=?", (username,))
    user = cur.fetchone()
    conn.close()
    
    if user:
        print(f"👤 User Data - ID: {user[0]}, Username: {user[1]}, Email: {user[2]}, Password: {user[3]}, Photo: {user[4]}")
    
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
    
    # ================= GENERATE SMART SUGGESTIONS =================
    for t in transactions:
        try:
            item = str(t[6]).lower() if len(t) > 6 else ""
        except:
            item = ""
        
        amount = float(t[3])
        date = t[7] if len(t) > 7 else t[6]
        
        if item in SMART_ITEMS:
            data = SMART_ITEMS[item]
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
    
    # Add daily suggestions if no specific items found
    if not suggestions:
        daily_tips = [
            "✅ Spending looks balanced. Keep saving! 💪",
            "🌟 Remember: Every rupee saved is a rupee earned!",
            "💡 Track every expense - knowledge is power!",
            "🎯 Set a monthly budget and stick to it!",
            "🍱 Cook at home - it's healthier and cheaper!",
            "🚶 Walk or cycle for short distances - save fuel!",
            "📊 Review your expenses weekly - find waste!",
            "💳 Use cash instead of cards - feel the money leaving!",
            "🌅 Wake up early and plan your day!",
            "☕ Make coffee at home - save ₹600/month!",
            "📝 Make a shopping list before going out!",
            "🏋️ Exercise at home - save gym membership!",
            "📺 Watch free content - cancel unused OTT!",
            "🌿 Grow small plants - save on vegetables!",
            "💡 Use LED bulbs - save electricity bill!"
        ]
        suggestions = random.sample(daily_tips, min(3, len(daily_tips)))
    
    # ================= CHART GENERATION =================
    try:
        chart_files = ['chart.png', 'monthly_chart.png', 'category_chart.png']
        for file in chart_files:
            file_path = os.path.join(STATIC_DIR, file)
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"🗑️ Deleted old chart: {file}")
        
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
    
    chart_timestamp = int(time.time())
    
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
        email_status=email_status,
        chart_timestamp=chart_timestamp
    )

# ================= AI CHATBOT WITH FUN & ENTERTAINMENT =================
@app.route('/chatbot', methods=['POST'])
def chatbot():
    msg = request.form['message'].lower().strip()
    username = session.get('user') if 'user' in session else "User"
    
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
    
    # ================= FINANCIAL QUESTIONS =================
    if "total income" in msg:
        reply = f"💰 Your total income is ₹{total_income}\n\n💡 Tip: Try to save at least 20% of this amount!"
    
    elif "total expense" in msg:
        reply = f"💸 Your total expense is ₹{total_expense}\n\n💡 Tip: Review your expenses to find where you can cut back!"
    
    elif "balance" in msg:
        if balance > 0:
            reply = f"🏦 Your current balance is ₹{balance}\n\n🎉 Great job maintaining a positive balance!"
        else:
            reply = f"🏦 Your current balance is ₹{balance}\n\n⚠️ You need to reduce your expenses!"
    
    elif "budget" in msg:
        remaining = budget_limit - total_expense
        if remaining > 0:
            reply = f"📊 Remaining budget: ₹{remaining}\n\n✅ You are within your budget limit!"
        else:
            reply = f"📊 Remaining budget: ₹{remaining}\n\n🚨 You have exceeded your budget limit!"
    
    elif "top category" in msg or "highest expense" in msg:
        reply = f"📈 Highest spending category: {top_category}\n\n💡 Try to reduce spending in this category!"
    
    # ================= FUN & ENTERTAINMENT =================
    elif "joke" in msg or "funny" in msg:
        jokes = [
            "Why did the budget go to therapy? It had too many expenses! 😂",
            "What did the wallet say to the credit card? You are always taking me for granted! 💳😄",
            "How much does a budget weigh? Just a few cents! 🤣",
            "Why dont budgets tell secrets? Because they are always spent! 😅",
            "Whats a budget favorite dance? The money-saving shuffle! 💃😂",
            "Why did the financial advisor break up with the budget? It was too controlling! 😂",
            "What do you call a budget that is always right? A prophet! 🤣"
        ]
        reply = random.choice(jokes) + "\n\n😂 Hope that made you laugh! Want another joke? Just say tell me a joke!"
    
    elif "motivation" in msg or "motivate" in msg or "inspire" in msg:
        motivational = [
            "💪 Remember: Every rupee saved is a rupee earned!",
            "🌟 Small savings today = Big investments tomorrow!",
            "🚀 You are doing great! Keep tracking your expenses!",
            "🎯 Set a goal and watch your savings grow!",
            "💰 Rich people save first, spend later. Be like them!",
            "🔥 The best time to start saving was yesterday. The next best time is NOW!",
            "💪 Your future self will thank you for saving today!",
            "🌟 You are stronger than your excuses!"
        ]
        reply = random.choice(motivational) + "\n\n🔥 You got this! Keep going!"
    
    elif "fun fact" in msg or "fact" in msg:
        facts = [
            "💡 The average person spends ₹5000 on unnecessary items every month!",
            "💡 Saving ₹100 daily = ₹36,500 saved in a year!",
            "💡 70% of people do not track their expenses - you are already ahead!",
            "💡 The 50-30-20 rule: 50% needs, 30% wants, 20% savings!",
            "💡 Indias savings rate is 30% of GDP - you can do better!",
            "💡 The average Indian spends ₹1500 on tea/coffee per month!",
            "💡 Cooking at home can save you ₹10,000 per month!"
        ]
        reply = random.choice(facts) + "\n\n🧠 Knowledge is power! Want more facts? Ask tell me a fact!"
    
    elif "advice" in msg or "tip" in msg:
        advice = [
            "📝 Track every expense - knowledge is power!",
            "🎯 Set a monthly budget and stick to it!",
            "🍱 Cook at home - it is healthier and cheaper!",
            "🚶 Walk or cycle for short distances - save fuel!",
            "📊 Review your expenses weekly - find waste!",
            "💳 Use cash instead of cards - feel the money leaving!",
            "🌅 Wake up early and plan your day for better savings!",
            "☕ Make coffee at home - save ₹600/month!",
            "📝 Make a shopping list before going out - avoid impulse buying!",
            "🏋️ Exercise at home - save gym membership fees!",
            "📺 Watch free content - cancel unused OTT subscriptions!"
        ]
        reply = random.choice(advice) + "\n\n💡 Try implementing this today!"
    
    elif "movie" in msg or "entertainment" in msg or "watch" in msg:
        movies = [
            "🎬 Watch The Pursuit of Happyness - it is about never giving up!",
            "🎬 Watch Slumdog Millionaire - a story of hope and money!",
            "🎬 Watch The Wolf of Wall Street - learn about money and excess!",
            "🎬 Watch Wall Street - the classic finance movie!",
            "🎬 Watch The Big Short - learn about the financial crisis!",
            "🎬 Watch Moneyball - data-driven success story!",
            "🎬 Watch The Founder - story of McDonalds success!",
            "🎬 Watch Hidden Figures - incredible true story of success!"
        ]
        reply = random.choice(movies) + "\n\n🍿 Happy watching! Let me know if you want more recommendations!"
    
    elif "book" in msg or "read" in msg:
        books = [
            "📚 Rich Dad Poor Dad by Robert Kiyosaki - the ultimate finance book!",
            "📚 Think and Grow Rich by Napoleon Hill - classic success book!",
            "📚 The Intelligent Investor by Benjamin Graham - for smart investing!",
            "📚 The Psychology of Money by Morgan Housel - understand money mindset!",
            "📚 Atomic Habits by James Clear - build saving habits!",
            "📚 The 5 AM Club by Robin Sharma - master your mornings!",
            "📚 The Alchemist by Paulo Coelho - follow your dreams!"
        ]
        reply = random.choice(books) + "\n\n📖 Happy reading! Want another book suggestion? Ask recommend a book!"
    
    elif "challenge" in msg or "game" in msg:
        challenges = [
            "🎯 Challenge: Save ₹1000 this week by avoiding outside food!",
            "🎯 Challenge: No online shopping for 7 days - save money and reduce waste!",
            "🎯 Challenge: Track every expense for 30 days - knowledge is power!",
            "🎯 Challenge: Cook all your meals at home for one week - save ₹2000!",
            "🎯 Challenge: Walk to work/college for 5 days - save fuel and stay fit!",
            "🎯 Challenge: Cancel 2 unused subscriptions today - save ₹500/month!"
        ]
        reply = random.choice(challenges) + "\n\n💪 Are you ready for the challenge? Say I accept to commit!"
    
    elif "saving" in msg or "save" in msg:
        saving_tips = [
            "💰 Tip: Save ₹100/day = ₹36,500/year!",
            "💰 Tip: Use the 50-30-20 rule: 50% needs, 30% wants, 20% savings!",
            "💰 Tip: Automate your savings - set up auto-transfer to savings account!",
            "💰 Tip: Save your daily change in a jar - it adds up fast!",
            "💰 Tip: Reduce one expense category by 20% this month!",
            "💰 Tip: Cook at home 5 days a week - save ₹5000/month!"
        ]
        reply = random.choice(saving_tips) + "\n\n🚀 Start saving today!"
    
    elif "hello" in msg or "hi" in msg or "hey" in msg:
        greetings = [
            f"👋 Hello {username}! Welcome back to Budget Tracker!",
            f"🤖 Hey {username}! Ready to save some money today?",
            f"💪 Hi {username}! Let us make your finances better!",
            f"🌟 Welcome back {username}! How can I help you today?"
        ]
        reply = random.choice(greetings) + "\n\n💡 Try asking me: total income, total expense, joke, motivation, advice, or challenge!"
    
    elif "how are you" in msg:
        replies = [
            "🤖 I am great! Helping people save money makes me happy! 😊",
            "💪 I am fantastic! Just had a virtual coffee and I am ready to help you save! ☕",
            "🌟 I am wonderful! Excited to help you achieve your financial goals! 💰"
        ]
        reply = random.choice(replies)
    
    elif "thank" in msg or "thanks" in msg:
        replies = [
            "😊 You are welcome! Happy to help you save money!",
            "💪 Anytime! Lets achieve your financial goals together!",
            "🌟 My pleasure! Keep tracking your expenses!"
        ]
        reply = random.choice(replies)
    
    elif "your name" in msg or "who are you" in msg:
        reply = "🤖 I am Budget AI Assistant - your personal financial advisor and savings coach! I am here to help you track expenses, save money, and achieve your financial goals. Plus, I know a few good jokes! 😄"
    
    elif "fun" in msg or "entertain" in msg:
        fun_responses = [
            "🎉 Lets have some fun with your finances!",
            "😄 Money does not have to be boring!",
            "🎮 Think of saving money as a game - try to beat your high score!",
            "💰 Saving money can be fun - celebrate every small win!"
        ]
        reply = random.choice(fun_responses) + "\n\n🎯 Try asking for a joke or motivation!"
    
    # ================= RANDOM RESPONSE FOR UNKNOWN =================
    else:
        random_responses = [
            f"🤔 Hmm, I did not quite get that, {username}. Try asking about:",
            "💡 I can help with questions like:",
            "🤖 I am not sure about that. Here are some things I can answer:"
        ]
        
        suggestions_list = [
            "💰 total income - to see your income",
            "💸 total expense - to see your expenses",
            "🏦 balance - to check your balance",
            "📊 budget - to check remaining budget",
            "📈 top category - to see highest spending",
            "😂 joke - for a good laugh",
            "💪 motivation - for daily inspiration",
            "📝 advice - for saving tips",
            "🎯 challenge - for saving challenges",
            "🎬 movie - for entertainment recommendations",
            "📚 book - for book recommendations"
        ]
        
        reply = random.choice(random_responses) + "\n\n" + "\n".join(random.sample(suggestions_list, 5))
    
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
    print(f"📁 Running on Render: {IS_RENDER}")
    print("=" * 60)
    print("📧 Email: vishnugowtham392@gmail.com")
    print("🔑 App Password: brdxtgyqobiwjeel")
    print("=" * 60)
    print("🌐 Server starting at: http://127.0.0.1:5000")
    print("=" * 60)
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)