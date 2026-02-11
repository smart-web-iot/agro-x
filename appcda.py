from flask import Flask, request, redirect, session, render_template_string, jsonify, send_file
from flask_jwt_extended import JWTManager, create_access_token
import sqlite3, random, datetime, io, csv, requests, smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import os
import time
import hashlib

# ================= NGROK SETUP =================
try:
    from pyngrok import ngrok
    NGROK_AVAILABLE = True
    
    # YOUR NGROK TOKEN - Replace with your actual token
    YOUR_NGROK_TOKEN = "39UZMapceJYdPhTeC05a0j7Tneo_2sibvecLDw8vvry4o9aFC"
    
    if YOUR_NGROK_TOKEN and YOUR_NGROK_TOKEN != "PASTE_YOUR_TOKEN_HERE":
        ngrok.set_auth_token(YOUR_NGROK_TOKEN)
        print("✅ Ngrok authtoken configured successfully!")
    else:
        print("⚠️ Please set your ngrok authtoken in the code")
        NGROK_AVAILABLE = False
except ImportError:
    print("⚠️ pyngrok not installed. Installing...")
    import subprocess
    subprocess.check_call(["pip", "install", "pyngrok"])
    from pyngrok import ngrok
    NGROK_AVAILABLE = True

# ... [Rest of your code] ...


# ================= CONFIG =================
# ================= CONFIG =================
app = Flask(__name__)
app.secret_key = "SMART_AGRI_SECRET_2024"
app.config["JWT_SECRET_KEY"] = "JWT_SECRET_2024"
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=24)

# ========== NGROK BYPASS HEADERS ==========
@app.after_request
def add_security_headers(response):
    # ये headers ngrok warning page को bypass करेंगे
    response.headers['X-Frame-Options'] = 'ALLOWALL'
    response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' *;"
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = '*'
    response.headers['Access-Control-Allow-Methods'] = '*'
    return response
# ==========================================

jwt = JWTManager(app)
DB_PATH = "agri.db"

# ================= ADMIN PASSWORD =================
ADMIN_PASSWORD = "Agro-x@123"
ADMIN_SESSION_TIMEOUT = 1800  # 30 minutes in seconds

# ================= DATABASE FIX =================
def fix_database():
    """Fix database schema issues"""
    import os
    if os.path.exists(DB_PATH):
        # Rename old database
        backup_path = DB_PATH + ".backup"
        if os.path.exists(backup_path):
            os.remove(backup_path)
        os.rename(DB_PATH, backup_path)
        print(f"✓ Backed up old database to {backup_path}")
        print("✓ Creating new database with correct schema...")

# ================= DATABASE =================
def db():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = db()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        farmer_id TEXT UNIQUE,
        email TEXT UNIQUE NOT NULL,
        farm_location TEXT,
        farm_size TEXT,
        crop_type TEXT,
        email_verified INTEGER DEFAULT 0,
        verification_code TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS products(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pid TEXT UNIQUE,
        name TEXT,
        price REAL,
        description TEXT,
        category TEXT,
        stock INTEGER DEFAULT 0,
        image_urls TEXT,
        specifications TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.execute("""
    CREATE TABLE IF NOT EXISTS orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE,
        farmer_id TEXT,
        products TEXT,
        total_amount REAL,
        shipping_address TEXT,
        status TEXT DEFAULT 'pending',
        payment_method TEXT,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create indexes for better performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_mobile ON users(mobile)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    
    # Insert default products if not exists
    default_products = [
        ("soil", "Soil Moisture Sensor", 400.0, "High accuracy soil moisture sensor for smart farming.", "sensors", 50, "https://i.imgur.com/yCUdT8U.jpeg,https://i.imgur.com/lY4h7BV.jpeg", "Accuracy: ±2%, Range: 0-100%, Power: 3.3-5V"),
        ("drip", "Drip Irrigation Kit (1 Plant)", 10.0, "Low-cost drip irrigation kit for individual plants.", "irrigation", 200, "https://i.imgur.com/E9IOgIb.jpeg", "Material: PVC, Length: 10m, Diameter: 4mm"),
        ("sprinkler", "Sprinkler Kit", 15.0, "Uniform water distribution sprinkler system.", "irrigation", 100, "https://i.imgur.com/fcm7KGf.jpeg", "Coverage: 10m radius, Pressure: 2-4 bar"),
        ("nitrogen", "Nitrogen Liquid (1 Ltr)", 300.0, "Boosts plant growth and leaf development.", "nutrients", 150, "https://i.imgur.com/UJggekb.jpeg", "N Content: 46%, Purity: 99.9%"),
        ("phosphorus", "Phosphorus Liquid (1 Ltr)", 300.0, "Enhances root strength and flowering.", "nutrients", 150, "https://i.imgur.com/NwYVnBw.jpeg", "P2O5 Content: 52%, Purity: 99.8%"),
        ("potassium", "Potassium Liquid (1 Ltr)", 300.0, "Improves crop resistance and quality.", "nutrients", 150, "https://i.imgur.com/Mn6AhWj.jpeg", "K2O Content: 60%, Purity: 99.7%"),
        ("phkit", "pH Buffer Kit", 2400.0, "Professional pH stabilization kit.", "sensors", 30, "https://i.imgur.com/hGdk4Xg.jpeg", "Range: 0-14 pH, Accuracy: ±0.01"),
        ("agrodevice", "Agro-x Device", 100000.0, "Complete autonomous smart agriculture system.", "systems", 10, "https://i.imgur.com/rwne61s.jpeg,https://i.imgur.com/ANEZ6gw.jpeg", "CPU: Quad-core, Storage: 64GB, Connectivity: WiFi/4G")
    ]
    
    for pid, name, price, desc, category, stock, images, specs in default_products:
        conn.execute("""
        INSERT OR IGNORE INTO products (pid, name, price, description, category, stock, image_urls, specifications)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pid, name, price, desc, category, stock, images, specs))
    
    conn.commit()
    conn.close()

# Fix database and initialize
fix_database()
init_db()
print("✓ Database initialized successfully!")

def generate_farmer_id(mobile):
    return "AGX" + mobile[-6:]

def generate_verification_code():
    """Generate a simple 6-digit verification code"""
    return str(random.randint(100000, 999999))

# ================= ADMIN SESSION MANAGEMENT =================
def check_admin_session():
    """Check if admin session is valid"""
    if not session.get("admin_authenticated"):
        return False
    
    last_activity = session.get("admin_last_activity", 0)
    current_time = time.time()
    
    # Check if session expired
    if current_time - last_activity > ADMIN_SESSION_TIMEOUT:
        session.pop("admin_authenticated", None)
        session.pop("admin_last_activity", None)
        return False
    
    # Update last activity time
    session["admin_last_activity"] = current_time
    return True

def update_admin_session():
    """Update admin session activity time"""
    if session.get("admin_authenticated"):
        session["admin_last_activity"] = time.time()

# ================= SENSOR (RANDOM) =================
def sensor_data():
    return {
        "N": random.randint(10, 80),
        "P": random.randint(10, 80),
        "K": random.randint(10, 80),
        "TDS": random.randint(100, 1000),
        "water_temp": random.randint(15, 45),
        "air_temp": random.randint(15, 40),
        "air_humidity": random.randint(20, 90),
        "CO2": random.randint(300, 1000),
        "turbidity": random.randint(0, 100),
        "tank_level": random.randint(0, 100),
        "battery": random.randint(20, 100),
        "ph": round(random.uniform(5, 8), 2),
        "moisture": random.randint(10, 100)
    }

# ================= OPENWEATHER FETCH (FIXED) =================
def get_weather_details():
    WEATHER_API_KEY = "2f84dd62c2a50fdf68cfe5e370b5befd"
    WEATHER_CITY = "Mumbai"
    
    url = (f"https://api.openweathermap.org/data/2.5/weather"
           f"?q={WEATHER_CITY}&appid={WEATHER_API_KEY}&units=metric")

    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()

        return {
            "temp": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"],
            "wind_speed": data["wind"]["speed"],
            "weather": data["weather"][0]["main"],
            "description": data["weather"][0]["description"],
            "sunrise": datetime.datetime.fromtimestamp(data["sys"]["sunrise"]).strftime("%H:%M"),
            "sunset": datetime.datetime.fromtimestamp(data["sys"]["sunset"]).strftime("%H:%M")
        }
    except Exception as e:
        print("Weather API Error:", e)
        return {
            "temp": 28.0,
            "feels_like": 30.0,
            "humidity": 65,
            "pressure": 1013,
            "wind_speed": 12.0,
            "weather": "Sunny",
            "description": "clear sky",
            "sunrise": "06:30",
            "sunset": "18:45"
        }

# ================= ALERT LOGIC =================
def ai_alerts(d, w):
    alerts = []
    if d["moisture"] < 20: alerts.append("Critical: Moisture Extremely Low")
    if d["water_temp"] > 40: alerts.append("Warning: High Water Temp")
    if d["battery"] < 25: alerts.append("Safety: Low Battery")
    if d["tank_level"] < 20: alerts.append("Warning: Low Tank Level")
    if d["CO2"] > 900: alerts.append("Safety: High CO2 Level")
    if isinstance(w["temp"], (int, float)) and w["temp"] > 40:
        alerts.append("Weather Alert: High Temperature")
    if isinstance(w["humidity"], (int, float)) and w["humidity"] < 30:
        alerts.append("Weather Alert: Low Humidity")
    return alerts

# ================= SHOP DATA =================
def get_products_from_db():
    """Get products from database"""
    conn = db()
    cursor = conn.execute("SELECT * FROM products")
    products = {}
    for row in cursor.fetchall():
        products[row[1]] = {  # pid as key
            "name": row[2],
            "price": row[3],
            "desc": row[4],
            "category": row[5],
            "stock": row[6],
            "images": row[7].split(','),
            "specs": row[8]
        }
    conn.close()
    return products

PRODUCTS = get_products_from_db()

def calculate_discount(total):
    discount = 0
    label = ""
    if total >= 50000:
        discount = round(total * 0.20, 2)
        label = "🎉 20% Mega Discount Applied!"
    elif total >= 10000:
        discount = round(total * 0.10, 2)
        label = "🎊 10% Discount Applied!"
    return discount, label

# ================= LANGUAGE SUPPORT =================
TRANSLATIONS = {
    'en': {
        'welcome': 'Welcome to Agro-x',
        'login': 'Login',
        'register': 'Register',
        'dashboard': 'Dashboard',
        'weather': 'Weather',
        'control_panel': 'Control Panel',
        'shop': 'Shop',
        'admin': 'Admin',
        'helpdesk': 'Helpdesk',
        'logout': 'Logout',
        'smart_agriculture': 'Smart Agriculture',
        'grow_smarter': 'Grow Smarter, Harvest Better',
        'ai_powered': 'AI-Powered',
        'smart_irrigation': 'Smart Irrigation',
        'real_time_analytics': 'Real-time Analytics',
        'automated_control': 'Automated Control',
        'home': 'Home',
        'name': 'Name',
        'mobile': 'Mobile',
        'password': 'Password',
        'email': 'Email',
        'farm_location': 'Farm Location',
        'farm_size': 'Farm Size',
        'crop_type': 'Crop Type',
        'create_account': 'Create Account',
        'already_have_account': 'Already have an account?',
        'login_here': 'Login here',
        'back_to_home': 'Back to Home',
        'invalid_credentials': 'Invalid credentials. Please try again.',
        'mobile_already_registered': 'Mobile number already registered.',
        'farmer_registration': 'Farmer Registration',
        'join_revolution': 'Join the smart agriculture revolution',
        'full_name': 'Full Name',
        'mobile_number': 'Mobile Number',
        'email_address': 'Email Address',
        'create_password': 'Create password',
        'village_district': 'Village / District',
        'in_acres': 'In acres',
        'enter_crop_type': 'e.g., Wheat, Rice, Vegetables',
        'create_farmer_account': 'Create Farmer Account',
        'smart_agriculture_dashboard': 'Smart Agriculture Dashboard',
        'weather_intelligence': 'Weather Intelligence',
        'real_time_weather': 'Real-time weather data for optimal farming decisions',
        'humidity': 'Humidity',
        'wind_speed': 'Wind Speed',
        'pressure': 'Pressure',
        'feels_like': 'Feels Like',
        'sunrise': 'Sunrise',
        'sunset': 'Sunset',
        'weather_updates': 'Weather data updates every 5 minutes',
        'smart_control_panel': 'Smart Control Panel',
        'manage_farm': 'Manage your farm operations with precision control and real-time automation',
        'nutrient_management': 'Nutrient Management',
        'water_management': 'Water Management',
        'climate_control': 'Climate Control',
        'emergency_controls': 'Emergency Controls',
        'system_status': 'System Status',
        'system_ready': 'System Ready',
        'administrator_panel': 'Administrator Panel',
        'manage_users': 'Manage users, monitor system activity, and configure settings',
        'total_users': 'Total Users',
        'active_farmers': 'Active Farmers',
        'crop_types': 'Crop Types',
        'system_uptime': 'System Uptime',
        'registered_users': 'Registered Users',
        'search_users': 'Search users...',
        'contact': 'Contact',
        'farmer_id': 'Farmer ID',
        'location': 'Location',
        'status': 'Status',
        'actions': 'Actions',
        'active': 'Active',
        'edit': 'Edit',
        'delete': 'Delete',
        'view_details': 'View Details',
        'admin_security': 'Admin panel access is logged and monitored for security purposes',
        'smart_farming_store': 'Smart Farming Store',
        'premium_equipment': 'Premium agricultural equipment and supplies for modern farming',
        'all_products': 'All Products',
        'sensors': 'Sensors',
        'irrigation': 'Irrigation',
        'nutrients': 'Nutrients',
        'complete_systems': 'Complete Systems',
        'add_to_cart': 'Add to Cart',
        'view_product': 'View',
        'continue_shopping': 'Continue Shopping',
        'your_cart': 'Your Shopping Cart',
        'review_items': 'Review your items and proceed to checkout',
        'clear_cart': 'Clear Cart',
        'order_summary': 'Order Summary',
        'subtotal': 'Subtotal',
        'shipping': 'Shipping',
        'tax': 'Tax',
        'total_amount': 'Total Amount',
        'secure_checkout': 'Secure checkout · 30-day returns',
        'shipping_information': 'Shipping Information',
        'enter_full_name': 'Enter your full name',
        'enter_mobile': 'Enter mobile number',
        'street_address': 'Street address',
        'landmark': 'Landmark',
        'nearby_landmark': 'Nearby landmark',
        'pincode': 'Pincode',
        'postal_code': 'Postal code',
        'alt_mobile': 'Alternative Mobile',
        'alt_contact': 'Alternate contact number',
        'proceed_to_payment': 'Proceed to Payment',
        'empty_cart': 'Your cart is empty',
        'add_products': 'Add some products to your cart and they will appear here',
        'start_shopping': 'Start Shopping',
        'complete_payment': 'Complete Payment',
        'secure_payment': 'Secure and fast payment processing',
        'choose_payment_method': 'Choose Payment Method',
        'scan_qr': 'Scan QR Code to Pay',
        'scan_with_upi': 'Scan with any UPI app to complete payment',
        'payment_done': 'Payment Done → Confirm',
        'download_invoice': 'Download Invoice',
        'payment_secure': 'Your payment is secure and encrypted',
        'order_confirmed': 'Order Confirmed!',
        'thank_you': 'Thank you for your purchase! Your order has been successfully processed and will be shipped within 3-5 business days.',
        'order_number': 'Order Number',
        'order_date': 'Order Date',
        'estimated_delivery': 'Estimated Delivery',
        'payment_status': 'Payment Status',
        'paid': 'Paid',
        'need_help': 'Need Help?',
        'customer_support': 'Our customer support team is here to assist you with any questions about your order.',
        'helpdesk_title': 'AI-Powered Helpdesk',
        'ask_question': 'Ask your farming questions and get instant AI-powered answers',
        'ask_placeholder': 'Type your question here... e.g., How to increase crop yield?',
        'get_answer': 'Get Answer',
        'clear': 'Clear',
        'ai_response': 'AI Response',
        'expert_support': 'Expert Support',
        'contact_support': 'Contact Support Team',
        'back_to_dashboard': 'Back to Dashboard',
        'verify_email': 'Verify Email',
        'email_verified': 'Email successfully verified!',
        'verification_failed': 'Email verification failed. Invalid or expired code.',
        'admin_password': 'Admin Password',
        'enter_admin_password': 'Enter admin password',
        'admin_access_denied': 'Admin access denied. Invalid password.',
        'inventory_management': 'Inventory Management',
        'manage_products': 'Manage Products',
        'add_new_product': 'Add New Product',
        'product_id': 'Product ID',
        'product_name': 'Product Name',
        'product_price': 'Price',
        'product_stock': 'Stock',
        'product_category': 'Category',
        'edit_product': 'Edit Product',
        'update_product': 'Update Product',
        'delete_product': 'Delete Product',
        'product_specifications': 'Specifications',
        'product_images': 'Images (comma separated URLs)',
        'save_product': 'Save Product',
        'cancel': 'Cancel',
        'confirm_delete': 'Are you sure you want to delete this product?',
        'product_added': 'Product added successfully!',
        'product_updated': 'Product updated successfully!',
        'product_deleted': 'Product deleted successfully!',
        'logout_admin': 'Logout Admin',
        'inventory': 'Inventory',
        'low_stock': 'Low Stock',
        'out_of_stock': 'Out of Stock',
        'in_stock': 'In Stock',
        'update_stock': 'Update Stock',
        'total_products': 'Total Products',
        'total_value': 'Total Inventory Value',
        'verification_code': 'Verification Code',
        'enter_verification_code': 'Enter 6-digit verification code',
        'verify_now': 'Verify Now',
        'verification_success': 'Account verified successfully! You can now login.',
        'registration_success': 'Registration successful! Please verify your account.',
        'verification_expired': 'Verification code invalid or expired.',
        'resend_code': 'Resend Code',
        'code_resent': 'New verification code sent.',
        'verify_account': 'Verify Your Account',
        'check_email_for_code': 'Check your email for the verification code',
        'verification_code_sent': 'Verification code has been sent to your email.',
        'email_already_verified': 'Email is already verified.',
        'email_already_registered': 'Email already registered. Please use a different email or login.'
    },
    'hi': {
        'welcome': 'एग्रो-एक्स में स्वागत है',
        'login': 'लॉगिन',
        'register': 'रजिस्टर',
        'dashboard': 'डैशबोर्ड',
        'weather': 'मौसम',
        'control_panel': 'कंट्रोल पैनल',
        'shop': 'दुकान',
        'admin': 'एडमिन',
        'helpdesk': 'हेल्पडेस्क',
        'logout': 'लॉगआउट',
        'smart_agriculture': 'स्मार्ट कृषि',
        'grow_smarter': 'अधिक समझदारी से उगाएं, बेहतर काटें',
        'ai_powered': 'एआई-संचालित',
        'smart_irrigation': 'स्मार्ट सिंचाई',
        'real_time_analytics': 'रियल-टाइम एनालिटिक्स',
        'automated_control': 'स्वचालित नियंत्रण',
        'home': 'होम',
        'name': 'नाम',
        'mobile': 'मोबाइल',
        'password': 'पासवर्ड',
        'email': 'ईमेल',
        'farm_location': 'फार्म स्थान',
        'farm_size': 'फार्म आकार',
        'crop_type': 'फसल प्रकार',
        'create_account': 'खाता बनाएं',
        'already_have_account': 'पहले से ही खाता है?',
        'login_here': 'यहां लॉगिन करें',
        'back_to_home': 'होम पर वापस जाएं',
        'invalid_credentials': 'अमान्य क्रेडेंशियल्स। कृपया पुनः प्रयास करें।',
        'mobile_already_registered': 'मोबाइल नंबर पहले से रजिस्टर्ड है।',
        'farmer_registration': 'किसान पंजीकरण',
        'join_revolution': 'स्मार्ट कृषि क्रांति में शामिल हों',
        'full_name': 'पूरा नाम',
        'mobile_number': 'मोबाइल नंबर',
        'email_address': 'ईमेल पता',
        'create_password': 'पासवर्ड बनाएं',
        'village_district': 'गांव / जिला',
        'in_acres': 'एकड़ में',
        'enter_crop_type': 'जैसे, गेहूं, चावल, सब्जियां',
        'create_farmer_account': 'किसान खाता बनाएं',
        'smart_agriculture_dashboard': 'स्मार्ट कृषि डैशबोर्ड',
        'weather_intelligence': 'मौसम बुद्धिमत्ता',
        'real_time_weather': 'इष्टतम कृषि निर्णयों के लिए रियल-टाइम मौसम डेटा',
        'humidity': 'नमी',
        'wind_speed': 'हवा की गति',
        'pressure': 'दबाव',
        'feels_like': 'अनुभव',
        'sunrise': 'सूर्योदय',
        'sunset': 'सूर्यास्त',
        'weather_updates': 'मौसम डेटा हर 5 मिनट में अपडेट होता है',
        'smart_control_panel': 'स्मार्ट कंट्रोल पैनल',
        'manage_farm': 'सटीक नियंत्रण और रियल-टाइम ऑटोमेशन के साथ अपने फार्म संचालन का प्रबंधन करें',
        'nutrient_management': 'पोषक तत्व प्रबंधन',
        'water_management': 'जल प्रबंधन',
        'climate_control': 'जलवायु नियंत्रण',
        'emergency_controls': 'आपातकालीन नियंत्रण',
        'system_status': 'सिस्टम स्थिति',
        'system_ready': 'सिस्टम तैयार',
        'administrator_panel': 'व्यवस्थापक पैनल',
        'manage_users': 'उपयोगकर्ताओं का प्रबंधन करें, सिस्टम गतिविधि की निगरानी करें और सेटिंग्स कॉन्फ़िगर करें',
        'total_users': 'कुल उपयोगकर्ता',
        'active_farmers': 'सक्रिय किसान',
        'crop_types': 'फसल प्रकार',
        'system_uptime': 'सिस्टम अपटाइम',
        'registered_users': 'पंजीकृत उपयोगकर्ता',
        'search_users': 'उपयोगकर्ताओं को खोजें...',
        'contact': 'संपर्क',
        'farmer_id': 'किसान आईडी',
        'location': 'स्थान',
        'status': 'स्थिति',
        'actions': 'कार्रवाई',
        'active': 'सक्रिय',
        'edit': 'संपादित करें',
        'delete': 'हटाएं',
        'view_details': 'विवरण देखें',
        'admin_security': 'सुरक्षा उद्देश्यों के लिए एडमिन पैनल पहुंच लॉग और मॉनिटर की जाती है',
        'smart_farming_store': 'स्मार्ट फार्मिंग स्टोर',
        'premium_equipment': 'आधुनिक कृषि के लिए प्रीमियम कृषि उपकरण और आपूर्ति',
        'all_products': 'सभी उत्पाद',
        'sensors': 'सेंसर',
        'irrigation': 'सिंचाई',
        'nutrients': 'पोषक तत्व',
        'complete_systems': 'पूर्ण सिस्टम',
        'add_to_cart': 'कार्ट में जोड़ें',
        'view_product': 'देखें',
        'continue_shopping': 'खरीदारी जारी रखें',
        'your_cart': 'आपकी शॉपिंग कार्ट',
        'review_items': 'अपनी वस्तुओं की समीक्षा करें और चेकआउट के लिए आगे बढ़ें',
        'clear_cart': 'कार्ट साफ करें',
        'order_summary': 'ऑर्डर सारांश',
        'subtotal': 'उप-योग',
        'shipping': 'शिपिंग',
        'tax': 'टैक्स',
        'total_amount': 'कुल राशि',
        'secure_checkout': 'सुरक्षित चेकआउट · 30-दिन की वापसी',
        'shipping_information': 'शिपिंग जानकारी',
        'enter_full_name': 'अपना पूरा नाम दर्ज करें',
        'enter_mobile': 'मोबाइल नंबर दर्ज करें',
        'street_address': 'स्ट्रीट पता',
        'landmark': 'लैंडमार्क',
        'nearby_landmark': 'नजदीकी लैंडमार्क',
        'pincode': 'पिनकोड',
        'postal_code': 'डाक कोड',
        'alt_mobile': 'वैकल्पिक मोबाइल',
        'alt_contact': 'वैकल्पिक संपर्क नंबर',
        'proceed_to_payment': 'भुगतान के लिए आगे बढ़ें',
        'empty_cart': 'आपकी कार्ट खाली है',
        'add_products': 'अपनी कार्ट में कुछ उत्पाद जोड़ें और वे यहां दिखाई देंगे',
        'start_shopping': 'खरीदारी शुरू करें',
        'complete_payment': 'भुगतान पूरा करें',
        'secure_payment': 'सुरक्षित और तेज़ भुगतान प्रसंस्करण',
        'choose_payment_method': 'भुगतान विधि चुनें',
        'scan_qr': 'भुगतान करने के लिए क्यूआर कोड स्कैन करें',
        'scan_with_upi': 'भुगतान पूरा करने के लिए किसी भी यूपीआई ऐप से स्कैन करें',
        'payment_done': 'भुगतान हो गया → पुष्टि करें',
        'download_invoice': 'इनवॉइस डाउनलोड करें',
        'payment_secure': 'आपका भुगतान सुरक्षित और एन्क्रिप्टेड है',
        'order_confirmed': 'ऑर्डर की पुष्टि हो गई!',
        'thank_you': 'आपकी खरीद के लिए धन्यवाद! आपका ऑर्डर सफलतापूर्वक संसाधित किया गया है और 3-5 कार्य दिवसों के भीतर शिप कर दिया जाएगा।',
        'order_number': 'ऑर्डर नंबर',
        'order_date': 'ऑर्डर तिथि',
        'estimated_delivery': 'अनुमानित डिलीवरी',
        'payment_status': 'भुगतान स्थिति',
        'paid': 'भुगतान किया गया',
        'need_help': 'मदद चाहिए?',
        'customer_support': 'आपके ऑर्डर के बारे में किसी भी प्रश्न में आपकी सहायता के लिए हमारी ग्राहक सहायता टीम यहां है।',
        'helpdesk_title': 'एआई-संचालित हेल्पडेस्क',
        'ask_question': 'अपने कृषि प्रश्न पूछें और तत्काल एआई-संचालित उत्तर प्राप्त करें',
        'ask_placeholder': 'अपना प्रश्न यहां टाइप करें... जैसे, फसल उपज कैसे बढ़ाएं?',
        'get_answer': 'उत्तर प्राप्त करें',
        'clear': 'साफ करें',
        'ai_response': 'एआई प्रतिक्रिया',
        'expert_support': 'विशेषज्ञ सहायता',
        'contact_support': 'सहायता टीम से संपर्क करें',
        'back_to_dashboard': 'डैशबोर्ड पर वापस जाएं',
        'verify_email': 'ईमेल सत्यापित करें',
        'email_verified': 'ईमेल सफलतापूर्वक सत्यापित!',
        'verification_failed': 'ईमेल सत्यापन विफल। अमान्य या समाप्त कोड।',
        'admin_password': 'व्यवस्थापक पासवर्ड',
        'enter_admin_password': 'व्यवस्थापक पासवर्ड दर्ज करें',
        'admin_access_denied': 'व्यवस्थापक पहुंच अस्वीकृत। अमान्य पासवर्ड।',
        'inventory_management': 'इन्वेंटरी प्रबंधन',
        'manage_products': 'उत्पाद प्रबंधित करें',
        'add_new_product': 'नया उत्पाद जोड़ें',
        'product_id': 'उत्पाद आईडी',
        'product_name': 'उत्पाद नाम',
        'product_price': 'कीमत',
        'product_stock': 'स्टॉक',
        'product_category': 'श्रेणी',
        'edit_product': 'उत्पाद संपादित करें',
        'update_product': 'उत्पाद अपडेट करें',
        'delete_product': 'उत्पाद हटाएं',
        'product_specifications': 'विशेषताएं',
        'product_images': 'छवियां (अल्पविराम से अलग यूआरएल)',
        'save_product': 'उत्पाद सहेजें',
        'cancel': 'रद्द करें',
        'confirm_delete': 'क्या आप वाकई इस उत्पाद को हटाना चाहते हैं?',
        'product_added': 'उत्पाद सफलतापूर्वक जोड़ा गया!',
        'product_updated': 'उत्पाद सफलतापूर्वक अपडेट किया गया!',
        'product_deleted': 'उत्पाद सफलतापूर्वक हटाया गया!',
        'logout_admin': 'एडमिन से लॉगआउट करें',
        'inventory': 'इन्वेंटरी',
        'low_stock': 'कम स्टॉक',
        'out_of_stock': 'स्टॉक खत्म',
        'in_stock': 'स्टॉक में',
        'update_stock': 'स्टॉक अपडेट करें',
        'total_products': 'कुल उत्पाद',
        'total_value': 'कुल इन्वेंटरी मूल्य',
        'verification_code': 'सत्यापन कोड',
        'enter_verification_code': '6-अंकीय सत्यापन कोड दर्ज करें',
        'verify_now': 'अभी सत्यापित करें',
        'verification_success': 'खाता सफलतापूर्वक सत्यापित! अब आप लॉगिन कर सकते हैं।',
        'registration_success': 'पंजीकरण सफल! कृपया अपना खाता सत्यापित करें।',
        'verification_expired': 'सत्यापन कोड अमान्य या समाप्त हो गया है।',
        'resend_code': 'कोड पुनः भेजें',
        'code_resent': 'नया सत्यापन कोड भेजा गया।',
        'verify_account': 'अपना खाता सत्यापित करें',
        'check_email_for_code': 'सत्यापन कोड के लिए अपना ईमेल जांचें',
        'verification_code_sent': 'सत्यापन कोड आपके ईमेल पर भेजा गया है।',
        'email_already_verified': 'ईमेल पहले से ही सत्यापित है।',
        'email_already_registered': 'ईमेल पहले से पंजीकृत है। कृपया एक अलग ईमेल का उपयोग करें या लॉगिन करें।'
    },
    'or': {
        'welcome': 'ଏଗ୍ରୋ-ଏକ୍ସକୁ ସ୍ଵାଗତ',
        'login': 'ଲଗଇନ୍',
        'register': 'ପଞ୍ଜିକରଣ',
        'dashboard': 'ଡ୍ୟାସବୋର୍ଡ',
        'weather': 'ପାଣିପାଗ',
        'control_panel': 'ନିୟନ୍ତ୍ରଣ ପ୍ୟାନେଲ୍',
        'shop': 'ଦୋକାନ',
        'admin': 'ପ୍ରଶାସକ',
        'helpdesk': 'ସହାୟତା କେଣ୍ଦ୍ର',
        'logout': 'ଲଗଆଉଟ୍',
        'smart_agriculture': 'ସ୍ମାର୍ଟ କୃଷି',
        'grow_smarter': 'ଅଧିକ ଚତୁର ହୋଇ ଚାଷ କରନ୍ତୁ, ଭଲ ଫସଲ କାଟନ୍ତୁ',
        'ai_powered': 'AI-ସଂଚାଳିତ',
        'smart_irrigation': 'ସ୍ମାର୍ଟ ଜଳସେଚନ',
        'real_time_analytics': 'ରିଅଲ୍-ଟାଇମ୍ ବିଶ୍ଳେଷଣ',
        'automated_control': 'ସ୍ୱୟଂଚାଳିତ ନିୟନ୍ତ୍ରଣ',
        'home': 'ମୁଖ୍ୟପୃଷ୍ଠା',
        'name': 'ନାମ',
        'mobile': 'ମୋବାଇଲ୍',
        'password': 'ପାସୱାର୍ଡ',
        'email': 'ଇମେଲ୍',
        'farm_location': 'ଚାଷ ଜମି ସ୍ଥାନ',
        'farm_size': 'ଚାଷ ଜମି ଆକାର',
        'crop_type': 'ଫସଲ ପ୍ରକାର',
        'create_account': 'ଆକାଉଣ୍ଟ୍ ତିଆରି କରନ୍ତୁ',
        'already_have_account': 'ପୂର୍ବରୁ ଆକାଉଣ୍ଟ୍ ଅଛି?',
        'login_here': 'ଏଠାରେ ଲଗଇନ୍ କରନ୍ତୁ',
        'back_to_home': 'ମୁଖ୍ୟପୃଷ୍ଠାକୁ ଫେରିଯାନ୍ତୁ',
        'invalid_credentials': 'ଅବୈଧ କ୍ରେଡେନସିଆଲ୍। ଦୟାକରି ପୁନର୍ବାର ଚେଷ୍ଟା କରନ୍ତୁ।',
        'mobile_already_registered': 'ମୋବାଇଲ୍ ନମ୍ବର ପୂର୍ବରୁ ପଞ୍ଜିକୃତ ହୋଇଛି।',
        'farmer_registration': 'କୃଷକ ପଞ୍ଜିକରଣ',
        'join_revolution': 'ସ୍ମାର୍ଟ କୃଷି ବିପ୍ଲବରେ ଯୋଗ ଦିଅନ୍ତୁ',
        'full_name': 'ପୂରା ନାମ',
        'mobile_number': 'ମୋବାଇଲ୍ ନମ୍ବର',
        'email_address': 'ଇମେଲ୍ ଠିକଣା',
        'create_password': 'ପାସୱାର୍ଡ ତିଆରି କରନ୍ତୁ',
        'village_district': 'ଗ୍ରାମ / ଜିଲ୍ଲା',
        'in_acres': 'ଏକର ରେ',
        'enter_crop_type': 'ଯେପରିକି, ଗହମ, ଚାଉଳ, ପନିପରିବା',
        'create_farmer_account': 'କୃଷକ ଆକାଉଣ୍ଟ୍ ତିଆରି କରନ୍ତୁ',
        'smart_agriculture_dashboard': 'ସ୍ମାର୍ଟ କୃଷି ଡ୍ୟାସବୋର୍ଡ',
        'weather_intelligence': 'ପାଣିପାଗ ବୁଦ୍ଧିମତ୍ତା',
        'real_time_weather': 'ଉତ୍ତମ କୃଷି ନିଷ୍ପତ୍ତି ପାଇଁ ରିଅଲ୍-ଟାଇମ୍ ପାଣିପାଗ ତଥ୍ୟ',
        'humidity': 'ଆର୍ଦ୍ରତା',
        'wind_speed': 'ପବନ ବେଗ',
        'pressure': 'ଚାପ',
        'feels_like': 'ଅନୁଭବ',
        'sunrise': 'ସୂର୍ଯ୍ୟୋଦୟ',
        'sunset': 'ସୂର୍ଯ୍ୟାସ୍ତ',
        'weather_updates': 'ପାଣିପାଗ ତଥ୍ୟ ପ୍ରତ୍ୟେକ 5 ମିନିଟ୍ରେ ଅପଡେଟ୍ ହୁଏ',
        'smart_control_panel': 'ସ୍ମାର୍ଟ ନିୟନ୍ତ୍ରଣ ପ୍ୟାନେଲ୍',
        'manage_farm': 'ସଠିକ୍ ନିୟନ୍ତ୍ରଣ ଏବଂ ରିଅଲ୍-ଟାଇମ୍ ଅଟୋମେସନ୍ ସହିତ ଆପଣଙ୍କ ଫାର୍ମ କାର୍ଯ୍ୟବାହୀକୁ ପରିଚାଳନା କରନ୍ତୁ',
        'nutrient_management': 'ପୋଷକ ପରିଚାଳନା',
        'water_management': 'ଜଳ ପରିଚାଳନା',
        'climate_control': 'ଜଳବାୟୁ ନିୟନ୍ତ୍ରଣ',
        'emergency_controls': 'ଜରୁରୀକାଳୀନ ନିୟନ୍ତ୍ରଣ',
        'system_status': 'ସିଷ୍ଟମ୍ ସ୍ଥିତି',
        'system_ready': 'ସିଷ୍ଟମ୍ ପ୍ରସ୍ତୁତ',
        'administrator_panel': 'ପ୍ରଶାସକ ପ୍ୟାନେଲ୍',
        'manage_users': 'ଉପଯୋଗକାରୀଙ୍କୁ ପରିଚାଳନା କରନ୍ତୁ, ସିଷ୍ଟମ୍ କାର୍ଯ୍ୟକଳାପ ନିରୀକ୍ଷଣ କରନ୍ତୁ ଏବଂ ସେଟିଂସ୍ ବିନ୍ୟାସ କରନ୍ତୁ',
        'total_users': 'ମୋଟ ଉପଯୋଗକାରୀ',
        'active_farmers': 'ସକ୍ରିୟ କୃଷକ',
        'crop_types': 'ଫସଲ ପ୍ରକାର',
        'system_uptime': 'ସିଷ୍ଟମ୍ ଅପଟାଇମ୍',
        'registered_users': 'ପଞ୍ଜିକୃତ ଉପଯୋଗକାରୀ',
        'search_users': 'ଉପଯୋଗକାରୀଙ୍କୁ ଖୋଜନ୍ତୁ...',
        'contact': 'ଯୋଗାଯୋଗ',
        'farmer_id': 'କୃଷକ ଆଇଡି',
        'location': 'ଅବସ୍ଥାନ',
        'status': 'ସ୍ଥିତି',
        'actions': 'କାର୍ଯ୍ୟ',
        'active': 'ସକ୍ରିୟ',
        'edit': 'ସମ୍ପାଦନ କରନ୍ତୁ',
        'delete': 'ଡିଲିଟ୍ କରନ୍ତୁ',
        'view_details': 'ବିବରଣୀ ଦେଖନ୍ତୁ',
        'admin_security': 'ସୁରକ୍ଷା ଉଦ୍ଦେଶ୍ୟ ପାଇଁ ଆଡମିନ୍ ପ୍ୟାନେଲ୍ ପ୍ରବେଶ ଲଗ୍ ଏବଂ ମନିଟର୍ କରାଯାଏ',
        'smart_farming_store': 'ସ୍ମାର୍ଟ ଫାର୍ମିଂ ଷ୍ଟୋର୍',
        'premium_equipment': 'ଆଧୁନିକ କୃଷି ପାଇଁ ପ୍ରିମିୟମ୍ କୃଷି ଉପକରଣ ଏବଂ ସରବରାହ',
        'all_products': 'ସମସ୍ତ ଉତ୍ପାଦ',
        'sensors': 'ସେନ୍ସର୍',
        'irrigation': 'ଜଳସେଚନ',
        'nutrients': 'ପୋଷକ',
        'complete_systems': 'ସମ୍ପୂର୍ଣ୍ଣ ସିଷ୍ଟମ୍',
        'add_to_cart': 'କାର୍ଟରେ ଯୋଡନ୍ତୁ',
        'view_product': 'ଦେଖନ୍ତୁ',
        'continue_shopping': 'କିଣାକିଣି ଜାରି ରଖନ୍ତୁ',
        'your_cart': 'ଆପଣଙ୍କର କିଣାକିଣି କାର୍ଟ',
        'review_items': 'ଆପଣଙ୍କର ଜିନିଷଗୁଡିକର ସମୀକ୍ଷା କରନ୍ତୁ ଏବଂ ଚେକଆଉଟ୍ ପାଇଁ ଆଗେଇ ଯାଆନ୍ତୁ',
        'clear_cart': 'କାର୍ଟ ଖାଲି କରନ୍ତୁ',
        'order_summary': 'ଅର୍ଡର ସାରାଂଶ',
        'subtotal': 'ଉପ-ସମୁଦାୟ',
        'shipping': 'ପରିବହନ',
        'tax': 'ଟିକସ',
        'total_amount': 'ମୋଟ ପରିମାଣ',
        'secure_checkout': 'ସୁରକ୍ଷିତ ଚେକଆଉଟ୍ · 30-ଦିନ ଫେରସ୍ତ',
        'shipping_information': 'ପରିବହନ ସୂଚନା',
        'enter_full_name': 'ଆପଣଙ୍କର ପୂରା ନାମ ପ୍ରବେଶ କରନ୍ତୁ',
        'enter_mobile': 'ମୋବାଇଲ୍ ନମ୍ବର ପ୍ରବେଶ କରନ୍ତୁ',
        'street_address': 'ରାସ୍ତା ଠିକଣା',
        'landmark': 'ଚିହ୍ନ',
        'nearby_landmark': 'ନିକଟବର୍ତ୍ତୀ ଚିହ୍ନ',
        'pincode': 'ପିନକୋଡ୍',
        'postal_code': 'ଡାକ ସଂକେତ',
        'alt_mobile': 'ବିକଳ୍ପ ମୋବାଇଲ୍',
        'alt_contact': 'ବିକଳ୍ପ ଯୋଗାଯୋଗ ନମ୍ବର',
        'proceed_to_payment': 'ଦେୟ ପାଇଁ ଆଗେଇ ଯାଆନ୍ତୁ',
        'empty_cart': 'ଆପଣଙ୍କ କାର୍ଟ ଖାଲି ଅଛି',
        'add_products': 'ଆପଣଙ୍କ କାର୍ଟରେ କିଛି ଉତ୍ପାଦ ଯୋଡନ୍ତୁ ଏବଂ ସେଗୁଡିକ ଏଠାରେ ଦେଖାଯିବ',
        'start_shopping': 'କିଣାକିଣି ଆରମ୍ଭ କରନ୍ତୁ',
        'complete_payment': 'ଦେୟ ସମ୍ପୂର୍ଣ୍ଣ କରନ୍ତୁ',
        'secure_payment': 'ସୁରକ୍ଷିତ ଏବଂ ଦ୍ରୁତ ଦେୟ ପ୍ରକ୍ରିୟାକରଣ',
        'choose_payment_method': 'ଦେୟ ପଦ୍ଧତି ବାଛନ୍ତୁ',
        'scan_qr': 'ଦେୟ କରିବା ପାଇଁ QR କୋଡ୍ ସ୍କାନ୍ କରନ୍ତୁ',
        'scan_with_upi': 'ଦେୟ ସମ୍ପୂର୍ଣ୍ଣ କରିବା ପାଇଁ ଯେକୌଣସି UPI ଆପ୍ ସହିତ ସ୍କାନ୍ କରନ୍ତୁ',
        'payment_done': 'ଦେୟ ହୋଇଗଲା → ନିଶ୍ଚିତ କରନ୍ତୁ',
        'download_invoice': 'ଇନଭଏସ୍ ଡାଉନଲୋଡ୍ କରନ୍ତୁ',
        'payment_secure': 'ଆପଣଙ୍କର ଦେୟ ସୁରକ୍ଷିତ ଏବଂ ଏନକ୍ରିପ୍ଟେଡ୍ ଅଛି',
        'order_confirmed': 'ଅର୍ଡର ନିଶ୍ଚିତ ହୋଇଛି!',
        'thank_you': 'ଆପଣଙ୍କର କ୍ରୟ ପାଇଁ ଧନ୍ୟବାଦ! ଆପଣଙ୍କର ଅର୍ଡର ସଫଳତାର ସହିତ ପ୍ରକ୍ରିୟାକୃତ ହୋଇଛି ଏବଂ 3-5 କାର୍ଯ୍ୟ ଦିନ ମଧ୍ୟରେ ପଠାଯିବ।',
        'order_number': 'ଅର୍ଡର ନମ୍ବର',
        'order_date': 'ଅର୍ଡର ତାରିଖ',
        'estimated_delivery': 'ଆନୁମାନିକ ବିତରଣ',
        'payment_status': 'ଦେୟ ସ୍ଥିତି',
        'paid': 'ଦେୟ କରାଯାଇଛି',
        'need_help': 'ସହାୟତା ଦରକାର?',
        'customer_support': 'ଆପଣଙ୍କର ଅର୍ଡର ବିଷୟରେ କୌଣସି ପ୍ରଶ୍ନ ପାଇଁ ଆମର ଗ୍ରାହକ ସହାୟତା ଦଳ ଏଠାରେ ଅଛି।',
        'helpdesk_title': 'AI-ସଂଚାଳିତ ସହାୟତା କେଣ୍ଦ୍ର',
        'ask_question': 'ଆପଣଙ୍କର କୃଷି ପ୍ରଶ୍ନ ପଚାରନ୍ତୁ ଏବଂ ତତକ୍ଷଣାତ୍ AI-ସଂଚାଳିତ ଉତ୍ତର ପାଆନ୍ତୁ',
        'ask_placeholder': 'ଆପଣଙ୍କର ପ୍ରଶ୍ନ ଏଠାରେ ଟାଇପ୍ କରନ୍ତୁ... ଯେପରିକି, ଫସଲ ଉତ୍ପାଦନ କିପରି ବଢାଇବେ?',
        'get_answer': 'ଉତ୍ତର ପାଆନ୍ତୁ',
        'clear': 'ସଫା କରନ୍ତୁ',
        'ai_response': 'AI ପ୍ରତିକ୍ରିୟା',
        'expert_support': 'ବିଶେଷଜ୍ଞ ସହାୟତା',
        'contact_support': 'ସହାୟତା ଦଳ ସହିତ ଯୋଗାଯୋଗ କରନ୍ତୁ',
        'back_to_dashboard': 'ଡ୍ୟାସବୋର୍ଡକୁ ଫେରିଯାନ୍ତୁ',
        'verify_email': 'ଇମେଲ୍ ସତ୍ୟାପନ କରନ୍ତୁ',
        'email_verified': 'ଇମେଲ୍ ସଫଳତାର ସହିତ ସତ୍ୟାପିତ!',
        'verification_failed': 'ଇମେଲ୍ ସତ୍ୟାପନ ବିଫଳ। ଅବୈଧ କିମ୍ବା ସମୟ ସମାପ୍ତ କୋଡ୍।',
        'admin_password': 'ପ୍ରଶାସକ ପାସୱାର୍ଡ',
        'enter_admin_password': 'ପ୍ରଶାସକ ପାସୱାର୍ଡ ପ୍ରବେଶ କରନ୍ତୁ',
        'admin_access_denied': 'ପ୍ରଶାସକ ପ୍ରବେଶ ପ୍ରତ୍ୟାଖ୍ୟାନ। ଅବୈଧ ପାସୱାର୍ଡ।',
        'inventory_management': 'ଇନଭେଣ୍ଟରି ପରିଚାଳନା',
        'manage_products': 'ଉତ୍ପାଦ ପରିଚାଳନା କରନ୍ତୁ',
        'add_new_product': 'ନୂତନ ଉତ୍ପାଦ ଯୋଡନ୍ତୁ',
        'product_id': 'ଉତ୍ପାଦ ଆଇଡି',
        'product_name': 'ଉତ୍ପାଦ ନାମ',
        'product_price': 'ମୂଲ୍ୟ',
        'product_stock': 'ଷ୍ଟକ୍',
        'product_category': 'ବର୍ଗ',
        'edit_product': 'ଉତ୍ପାଦ ସମ୍ପାଦନ କରନ୍ତୁ',
        'update_product': 'ଉତ୍ପାଦ ଅପଡେଟ୍ କରନ୍ତୁ',
        'delete_product': 'ଉତ୍ପାଦ ଡିଲିଟ୍ କରନ୍ତୁ',
        'product_specifications': 'ବିଶେଷତା',
        'product_images': 'ଛବି (ଅଲଗା କରି URL)',
        'save_product': 'ଉତ୍ପାଦ ସେଭ୍ କରନ୍ତୁ',
        'cancel': 'ବାତିଲ୍ କରନ୍ତୁ',
        'confirm_delete': 'ଆପଣ ନିଶ୍ଚିତ କି ଏହି ଉତ୍ପାଦ ଡିଲିଟ୍ କରିବାକୁ ଚାହୁଁଛନ୍ତି?',
        'product_added': 'ଉତ୍ପାଦ ସଫଳତାର ସହିତ ଯୋଡାଗଲା!',
        'product_updated': 'ଉତ୍ପାଦ ସଫଳତାର ସହିତ ଅପଡେଟ୍ ହେଲା!',
        'product_deleted': 'ଉତ୍ପାଦ ସଫଳତାର ସହିତ ଡିଲିଟ୍ ହେଲା!',
        'logout_admin': 'ପ୍ରଶାସକ ଲଗଆଉଟ୍',
        'inventory': 'ଇନଭେଣ୍ଟରି',
        'low_stock': 'କମ୍ ଷ୍ଟକ୍',
        'out_of_stock': 'ଷ୍ଟକ୍ ଶେଷ',
        'in_stock': 'ଷ୍ଟକ୍ ରେ',
        'update_stock': 'ଷ୍ଟକ୍ ଅପଡେଟ୍ କରନ୍ତୁ',
        'total_products': 'ମୋଟ ଉତ୍ପାଦ',
        'total_value': 'ମୋଟ ଇନଭେଣ୍ଟରି ମୂଲ୍ୟ',
        'verification_code': 'ସତ୍ୟାପନ କୋଡ୍',
        'enter_verification_code': '6-ଅଙ୍କିଆ ସତ୍ୟାପନ କୋଡ୍ ପ୍ରବେଶ କରନ୍ତୁ',
        'verify_now': 'ବର୍ତ୍ତମାନ ସତ୍ୟାପନ କରନ୍ତୁ',
        'verification_success': 'ଆକାଉଣ୍ଟ୍ ସଫଳତାର ସହିତ ସତ୍ୟାପିତ! ଆପଣ ବର୍ତ୍ତମାନ ଲଗଇନ୍ କରିପାରିବେ।',
        'registration_success': 'ପଞ୍ଜିକରଣ ସଫଳ! ଦୟାକରି ଆପଣଙ୍କର ଆକାଉଣ୍ଟ୍ ସତ୍ୟାପନ କରନ୍ତୁ।',
        'verification_expired': 'ସତ୍ୟାପନ କୋଡ୍ ଅମାନ୍ୟ କିମ୍ବା ସମୟ ସମାପ୍ତ ହୋଇଛି।',
        'resend_code': 'କୋଡ୍ ପୁନଃ ପଠାନ୍ତୁ',
        'code_resent': 'ନୂତନ ସତ୍ୟାପନ କୋଡ୍ ପଠାଯାଇଛି।',
        'verify_account': 'ଆପଣଙ୍କର ଆକାଉଣ୍ଟ୍ ସତ୍ୟାପନ କରନ୍ତୁ',
        'check_email_for_code': 'ସତ୍ୟାପନ କୋଡ୍ ପାଇଁ ଆପଣଙ୍କର ଇମେଲ୍ ଯାଞ୍ଚ କରନ୍ତୁ',
        'verification_code_sent': 'ସତ୍ୟାପନ କୋଡ୍ ଆପଣଙ୍କ ଇମେଲ୍ ପାଖରେ ପଠାଯାଇଛି।',
        'email_already_verified': 'ଇମେଲ୍ ପୂର୍ବରୁ ସତ୍ୟାପିତ ହୋଇଛି।',
        'email_already_registered': 'ଇମେଲ୍ ପୂର୍ବରୁ ପଞ୍ଜିକୃତ ହୋଇଛି। ଦୟାକରି ଏକ ଅଲଗା ଇମେଲ୍ ବ୍ୟବହାର କରନ୍ତୁ କିମ୍ବା ଲଗଇନ୍ କରନ୍ତୁ।'
    }
}

def get_language():
    return session.get('language', 'en')

def set_language(lang):
    session['language'] = lang

def translate(key, lang=None):
    if lang is None:
        lang = get_language()
    return TRANSLATIONS.get(lang, TRANSLATIONS['en']).get(key, key)

def get_translated_text(lang=None):
    if lang is None:
        lang = get_language()
    return TRANSLATIONS.get(lang, TRANSLATIONS['en'])

# ================= ROUTES =================
@app.route("/")
def intro_page():
    """New introduction page with company details"""
    lang = get_language()
    t = get_translated_text(lang)
    return render_template_string(INTRO_HTML, lang=lang, t=t)

@app.route("/home")
def start():
    lang = get_language()
    t = get_translated_text(lang)
    return render_template_string(START_HTML, lang=lang, t=t)

@app.route("/set_language/<lang>")
def change_language(lang):
    if lang in ['en', 'hi', 'or']:
        set_language(lang)
    return redirect(request.referrer or '/')

@app.route("/login", methods=["GET", "POST"])
def login():
    lang = get_language()
    t = get_translated_text(lang)
    
    if request.method == "POST":
        m = request.form["mobile"]
        p = request.form["password"]
        conn = db()
        u = conn.execute(
            "SELECT * FROM users WHERE (mobile=? OR farmer_id=?) AND password=?",
            (m, m, p)).fetchone()
        conn.close()
        
        if u:
            # Check if email is verified
            if u[10] == 0:  # email_verified column (index 10)
                # Store user info in session for verification
                session["pending_verification_id"] = u[0]
                session["pending_verification_email"] = u[6]
                return redirect("/verify")
            
            # Create session
            session["user_id"] = u[0]
            session["user_name"] = u[1]
            session["user_mobile"] = u[2]
            session["farmer_id"] = u[5]
            session["jwt"] = create_access_token(identity=u[0])
            
            return redirect("/dashboard")
        
        return render_template_string(LOGIN_HTML, error=t['invalid_credentials'], lang=lang, t=t)
    
    return render_template_string(LOGIN_HTML, lang=lang, t=t)

@app.route("/register", methods=["GET", "POST"])
def register():
    lang = get_language()
    t = get_translated_text(lang)
    
    if request.method == "POST":
        name = request.form["name"]
        mobile = request.form["mobile"]
        email = request.form["email"]
        password = request.form["password"]
        farm_location = request.form["farm_location"]
        farm_size = request.form["farm_size"]
        crop_type = request.form["crop_type"]
        
        # Generate farmer ID and verification code
        farmer_id = generate_farmer_id(mobile)
        verification_code = generate_verification_code()
        
        conn = db()
        try:
            # Check if mobile or email already exists
            existing = conn.execute(
                "SELECT mobile, email FROM users WHERE mobile=? OR email=?",
                (mobile, email)
            ).fetchone()
            
            if existing:
                if existing[0] == mobile:
                    conn.close()
                    return render_template_string(REGISTER_HTML, 
                        error=t['mobile_already_registered'], 
                        lang=lang, 
                        t=t)
                elif existing[1] == email:
                    conn.close()
                    return render_template_string(REGISTER_HTML,
                        error=t['email_already_registered'],
                        lang=lang,
                        t=t)
            
            # Insert new user
            conn.execute(
                """
                INSERT INTO users(name, mobile, email, password, role, farmer_id, farm_location, farm_size, crop_type, verification_code)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, 
                (name, mobile, email, password, "user", farmer_id, farm_location, farm_size, crop_type, verification_code)
            )
            conn.commit()
            
            # Get the new user ID
            user = conn.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
            user_id = user[0]
            conn.close()
            
            # Store verification info in session
            session["pending_verification_id"] = user_id
            session["pending_verification_email"] = email
            session["verification_code"] = verification_code
            
            return redirect("/verify")
                
        except sqlite3.IntegrityError as e:
            conn.close()
            if "UNIQUE constraint failed: users.mobile" in str(e):
                return render_template_string(REGISTER_HTML, 
                    error=t['mobile_already_registered'], 
                    lang=lang, 
                    t=t)
            elif "UNIQUE constraint failed: users.email" in str(e):
                return render_template_string(REGISTER_HTML,
                    error=t['email_already_registered'],
                    lang=lang,
                    t=t)
            else:
                return render_template_string(REGISTER_HTML,
                    error=f"Registration failed: {str(e)}",
                    lang=lang,
                    t=t)
        except Exception as e:
            conn.close()
            return render_template_string(REGISTER_HTML,
                error=f"Registration failed: {str(e)}",
                lang=lang,
                t=t)
    
    return render_template_string(REGISTER_HTML, lang=lang, t=t)

@app.route("/verify", methods=["GET", "POST"])
def verify():
    lang = get_language()
    t = get_translated_text(lang)
    
    # Check if there's a pending verification
    if not session.get("pending_verification_id"):
        return redirect("/register")
    
    user_id = session.get("pending_verification_id")
    email = session.get("pending_verification_email")
    stored_code = session.get("verification_code")
    
    if request.method == "POST":
        entered_code = request.form.get("verification_code")
        
        if entered_code == stored_code:
            # Verify the user
            conn = db()
            conn.execute(
                "UPDATE users SET email_verified = 1, verification_code = NULL WHERE id = ?",
                (user_id,)
            )
            conn.commit()
            
            # Get user info
            user = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
            conn.close()
            
            # Clear verification session
            session.pop("pending_verification_id", None)
            session.pop("pending_verification_email", None)
            session.pop("verification_code", None)
            
            # Create user session
            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_mobile"] = user[2]
            session["farmer_id"] = user[5]
            session["jwt"] = create_access_token(identity=user[0])
            
            return render_template_string("""
            <!DOCTYPE html>
            <html>
            <head>
                <title>{{ t.verification_success }}</title>
                <style>
                    body { 
                        font-family: Arial, sans-serif; 
                        text-align: center; 
                        padding: 50px; 
                        background: linear-gradient(135deg, #4CAF50, #2E7D32);
                        color: white;
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }
                    .container {
                        background: rgba(255, 255, 255, 0.1);
                        backdrop-filter: blur(10px);
                        padding: 40px;
                        border-radius: 20px;
                        max-width: 500px;
                        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    }
                    .success { 
                        color: #4CAF50; 
                        font-size: 48px;
                        margin: 20px 0; 
                    }
                    .button { 
                        display: inline-block; 
                        padding: 12px 24px; 
                        background: #4CAF50; 
                        color: white; 
                        text-decoration: none; 
                        border-radius: 5px; 
                        margin-top: 20px; 
                        font-weight: bold;
                        transition: transform 0.3s ease;
                    }
                    .button:hover {
                        transform: translateY(-2px);
                        background: #45a049;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="success">✅ {{ t.verification_success }}</div>
                    <p>Your account has been successfully verified!</p>
                    <p>You can now access all features of Agro-x.</p>
                    <a href="/dashboard" class="button">{{ t.back_to_dashboard }}</a>
                </div>
            </body>
            </html>
            """, lang=lang, t=t)
        else:
            return render_template_string(VERIFICATION_HTML, 
                error=t['verification_failed'],
                email=email,
                lang=lang,
                t=t)
    
    # GET request - show verification form
    return render_template_string(VERIFICATION_HTML, 
        email=email,
        lang=lang,
        t=t)

@app.route("/resend_code")
def resend_code():
    lang = get_language()
    t = get_translated_text(lang)
    
    if not session.get("pending_verification_id"):
        return redirect("/register")
    
    # Generate new code
    new_code = generate_verification_code()
    session["verification_code"] = new_code
    
    # Update in database
    user_id = session.get("pending_verification_id")
    conn = db()
    conn.execute(
        "UPDATE users SET verification_code = ? WHERE id = ?",
        (new_code, user_id)
    )
    conn.commit()
    conn.close()
    
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{{ t.code_resent }}</title>
        <style>
            body { 
                font-family: Arial, sans-serif; 
                text-align: center; 
                padding: 50px; 
                background: linear-gradient(135deg, #2196F3, #1976D2);
                color: white;
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                padding: 40px;
                border-radius: 20px;
                max-width: 500px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            }
            .success { 
                color: #4CAF50; 
                font-size: 32px;
                margin: 20px 0; 
            }
            .button { 
                display: inline-block; 
                padding: 12px 24px; 
                background: #2196F3; 
                color: white; 
                text-decoration: none; 
                border-radius: 5px; 
                margin-top: 20px; 
                font-weight: bold;
                transition: transform 0.3s ease;
            }
            .button:hover {
                transform: translateY(-2px);
                background: #1976D2;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="success">✅ {{ t.code_resent }}</div>
            <p>A new verification code has been sent.</p>
            <p>Please check your email for the new code.</p>
            <a href="/verify" class="button">{{ t.verify_now }}</a>
        </div>
    </body>
    </html>
    """, lang=lang, t=t)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
def dashboard():
    # Check if user is logged in
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    d = sensor_data()
    w = get_weather_details()
    return render_template_string(DASHBOARD_HTML,
                                  data=d,
                                  weather=w,
                                  alerts=ai_alerts(d, w),
                                  lang=lang,
                                  t=t)

@app.route("/dashboard_data")
def dashboard_data():
    d = sensor_data()
    w = get_weather_details()
    return jsonify({**d, **w, "alerts": ai_alerts(d, w)})

@app.route("/weather")
def weather_page():
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    return render_template_string(WEATHER_HTML, weather=get_weather_details(), lang=lang, t=t)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    lang = get_language()
    t = get_translated_text(lang)
    
    # Handle logout
    if request.args.get('logout'):
        session.pop("admin_authenticated", None)
        session.pop("admin_last_activity", None)
        return redirect("/admin")
    
    # Check admin session
    if not check_admin_session():
        # Check admin password
        if request.method == "POST":
            if request.form.get("admin_password") != ADMIN_PASSWORD:
                return render_template_string(ADMIN_LOGIN_HTML, error=t['admin_access_denied'], lang=lang, t=t)
            session["admin_authenticated"] = True
            session["admin_last_activity"] = time.time()
        
        if not session.get("admin_authenticated"):
            return render_template_string(ADMIN_LOGIN_HTML, lang=lang, t=t)
    
    # Update session activity
    update_admin_session()
    
    # Get users data
    conn = db()
    users = conn.execute(
        "SELECT name,mobile,farmer_id,farm_location,crop_type FROM users"
    ).fetchall()
    
    # Get products data for inventory
    products = conn.execute(
        "SELECT pid, name, price, stock, category FROM products ORDER BY category, name"
    ).fetchall()
    
    # Calculate inventory stats
    total_products = len(products)
    total_value = sum(p[2] * p[3] for p in products)
    low_stock = sum(1 for p in products if p[3] < 10 and p[3] > 0)
    out_of_stock = sum(1 for p in products if p[3] == 0)
    in_stock = sum(1 for p in products if p[3] >= 10)
    
    conn.close()
    
    # Get unique crop types count
    crop_types = []
    for user in users:
        if user[4] and user[4] not in crop_types:
            crop_types.append(user[4])

    return render_template_string(ADMIN_HTML, 
                                  users=users, 
                                  crop_count=len(crop_types),
                                  products=products,
                                  total_products=total_products,
                                  total_value=total_value,
                                  low_stock=low_stock,
                                  out_of_stock=out_of_stock,
                                  in_stock=in_stock,
                                  lang=lang,
                                  t=t)

@app.route("/admin/add_product", methods=["GET", "POST"])
def admin_add_product():
    lang = get_language()
    t = get_translated_text(lang)
    
    # Check admin session
    if not check_admin_session():
        return redirect("/admin")
    
    update_admin_session()
    
    if request.method == "POST":
        pid = request.form.get("pid")
        name = request.form.get("name")
        price = float(request.form.get("price"))
        description = request.form.get("description")
        category = request.form.get("category")
        stock = int(request.form.get("stock"))
        image_urls = request.form.get("image_urls")
        specifications = request.form.get("specifications")
        
        conn = db()
        try:
            conn.execute("""
                INSERT INTO products (pid, name, price, description, category, stock, image_urls, specifications)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pid, name, price, description, category, stock, image_urls, specifications))
            conn.commit()
            conn.close()
            
            # Refresh products cache
            global PRODUCTS
            PRODUCTS = get_products_from_db()
            
            return redirect("/admin?tab=inventory&success=Product added successfully!")
        except Exception as e:
            conn.close()
            return render_template_string(ADMIN_ADD_PRODUCT_HTML, 
                                         error="Failed to add product: " + str(e),
                                         lang=lang,
                                         t=t)
    
    return render_template_string(ADMIN_ADD_PRODUCT_HTML, lang=lang, t=t)

@app.route("/admin/edit_product/<pid>", methods=["GET", "POST"])
def admin_edit_product(pid):
    lang = get_language()
    t = get_translated_text(lang)
    
    # Check admin session
    if not check_admin_session():
        return redirect("/admin")
    
    update_admin_session()
    
    conn = db()
    
    if request.method == "POST":
        name = request.form.get("name")
        price = float(request.form.get("price"))
        description = request.form.get("description")
        category = request.form.get("category")
        stock = int(request.form.get("stock"))
        image_urls = request.form.get("image_urls")
        specifications = request.form.get("specifications")
        
        try:
            conn.execute("""
                UPDATE products 
                SET name=?, price=?, description=?, category=?, stock=?, image_urls=?, specifications=?, updated_at=CURRENT_TIMESTAMP
                WHERE pid=?
            """, (name, price, description, category, stock, image_urls, specifications, pid))
            conn.commit()
            conn.close()
            
            # Refresh products cache
            global PRODUCTS
            PRODUCTS = get_products_from_db()
            
            return redirect("/admin?tab=inventory&success=Product updated successfully!")
        except Exception as e:
            conn.close()
            return render_template_string(ADMIN_EDIT_PRODUCT_HTML, 
                                         product=None,
                                         error="Failed to update product: " + str(e),
                                         lang=lang,
                                         t=t)
    
    # GET request - load product data
    product = conn.execute("SELECT * FROM products WHERE pid=?", (pid,)).fetchone()
    conn.close()
    
    if not product:
        return redirect("/admin?tab=inventory&error=Product not found")
    
    product_dict = {
        "pid": product[1],
        "name": product[2],
        "price": product[3],
        "description": product[4],
        "category": product[5],
        "stock": product[6],
        "image_urls": product[7],
        "specifications": product[8]
    }
    
    return render_template_string(ADMIN_EDIT_PRODUCT_HTML, 
                                 product=product_dict,
                                 lang=lang,
                                 t=t)

@app.route("/admin/delete_product/<pid>")
def admin_delete_product(pid):
    # Check admin session
    if not check_admin_session():
        return redirect("/admin")
    
    conn = db()
    try:
        conn.execute("DELETE FROM products WHERE pid=?", (pid,))
        conn.commit()
        conn.close()
        
        # Refresh products cache
        global PRODUCTS
        PRODUCTS = get_products_from_db()
        
        return redirect("/admin?tab=inventory&success=Product deleted successfully!")
    except Exception as e:
        conn.close()
        return redirect("/admin?tab=inventory&error=Failed to delete product")

@app.route("/control_panel")
def control_panel():
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    return render_template_string(CONTROL_HTML, lang=lang, t=t)

@app.route("/qr")
def qr_page():
    return send_file('static/site_qr.png', mimetype='image/png')

@app.route("/manifest.json")
def manifest():
    return send_file('static/manifest.json')

@app.route("/export_csv")
def export_csv():
    d = sensor_data()
    w = get_weather_details()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Parameter", "Value"])
    for k, v in d.items():
        writer.writerow([k, v])
    for k, v in w.items():
        writer.writerow([k, v])

    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode()),
                     mimetype='text/csv',
                     as_attachment=True,
                     download_name='agri_data.csv')

# ================= SHOP ROUTES =================
@app.route("/shop")
def shop():
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    return render_template_string(SHOP_HTML, products=PRODUCTS, lang=lang, t=t)

@app.route("/product/<pid>")
def product(pid):
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    if pid not in PRODUCTS:
        return "Product not found", 404
    return render_template_string(PRODUCT_HTML, p=PRODUCTS[pid], pid=pid, lang=lang, t=t)

@app.route("/add_to_cart/<pid>")
def add_to_cart(pid):
    if not session.get("user_id"):
        return redirect("/login")
    
    cart = session.get("cart", {})
    cart[pid] = cart.get(pid, 0) + 1
    session["cart"] = cart
    return redirect("/cart")

@app.route("/update_qty/<pid>/<action>")
def update_qty(pid, action):
    if not session.get("user_id"):
        return redirect("/login")
    
    cart = session.get("cart", {})
    if pid in cart:
        if action == "plus":
            cart[pid] += 1
        elif action == "minus":
            cart[pid] -= 1
            if cart[pid] <= 0:
                del cart[pid]
    session["cart"] = cart
    return redirect("/cart")

@app.route("/clear_cart")
def clear_cart():
    session.pop("cart", None)
    session.pop("address", None)
    return redirect("/cart")

@app.route("/cart", methods=["GET","POST"])
def cart():
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    cart = session.get("cart", {})
    items=[]
    total=0

    for pid,qty in cart.items():
        if pid in PRODUCTS:
            p=PRODUCTS[pid]
            subtotal=p["price"]*qty
            total+=subtotal
            items.append((pid,p["name"],p["price"],qty,subtotal))

    discount, discount_label = calculate_discount(total)
    final_total = total - discount

    return render_template_string(
        CART_HTML,
        items=items,
        total=total,
        discount=discount,
        discount_label=discount_label,
        final_total=final_total,
        products=PRODUCTS,
        lang=lang,
        t=t
    )

@app.route("/checkout", methods=["POST"])
def checkout():
    if not session.get("user_id"):
        return redirect("/login")
    
    session["address"]=dict(request.form)
    return redirect("/payment")

@app.route("/payment")
def payment():
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    cart=session.get("cart",{})
    total=0
    for p,q in cart.items():
        if p in PRODUCTS:
            total += PRODUCTS[p]["price"] * q
    discount, label = calculate_discount(total)
    gst=round((total-discount)*0.18,2)
    final = total - discount + gst
    return render_template_string(
        PAYMENT_HTML,
        total=total,
        discount=discount,
        label=label,
        gst=gst,
        final=final,
        lang=lang,
        t=t
    )

@app.route("/confirm")
def confirm():
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    return render_template_string(CONFIRM_HTML, lang=lang, t=t, datetime=datetime)

@app.route("/download_bill")
def download_bill():
    if not session.get("user_id"):
        return redirect("/login")
    
    cart = session.get("cart", {})
    address = session.get("address", {})

    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("<b>AGRO-X</b>", styles["Title"]))
    elements.append(Paragraph(
        "CDA Sector-9, Kathajodi Enclave, Lane-6, A1/2<br/>"
        "Cuttack, Odisha - 753014<br/>"
        "📞 9692777847 | ✉ autocrop24@gmail.com<br/><br/>",
        styles["Normal"]
    ))

    elements.append(Paragraph("<b>INVOICE / BILL</b><br/><br/>", styles["Heading2"]))

    elements.append(Paragraph(
        f"<b>Name:</b> {address.get('name','')}<br/>"
        f"<b>Address:</b> {address.get('address','')}<br/>"
        f"<b>Pincode:</b> {address.get('pincode','')}<br/>"
        f"<b>Mobile:</b> {address.get('mobile','')}<br/><br/>",
        styles["Normal"]
    ))

    table_data = [["Product", "Price", "Qty", "Total"]]
    grand_total = 0

    for pid, qty in cart.items():
        if pid in PRODUCTS:
            p = PRODUCTS[pid]
            total = p["price"] * qty
            grand_total += total
            table_data.append([p["name"], f"₹ {p['price']}", qty, f"₹ {total}"])

    discount, discount_label = calculate_discount(grand_total)
    gst = round((grand_total - discount) * 0.18, 2)
    final_total = grand_total - discount + gst

    table_data.append(["", "", "Subtotal", f"₹ {grand_total}"])
    if discount > 0:
        table_data.append(["", "", discount_label, f"- ₹ {discount}"])
    table_data.append(["", "", "GST (18%)", f"₹ {gst}"])
    table_data.append(["", "", "Grand Total", f"₹ {final_total}"])

    table = Table(table_data, colWidths=[180, 80, 60, 80])
    table.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 1, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("FONT", (0,0), (-1,0), "Helvetica-Bold"),
        ("ALIGN", (1,1), (-1,-1), "CENTER"),
    ]))

    elements.append(table)
    elements.append(Paragraph("<br/><br/>Owner Signature:<br/>", styles["Normal"]))
    elements.append(Paragraph("<b>Agro-x</b>", styles["Normal"]))

    pdf.build(elements)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="agrox_bill.pdf",
        mimetype="application/pdf"
    )

# ================= HELPDESK =================
@app.route("/helpdesk",methods=["GET","POST"])
def helpdesk():
    if not session.get("user_id"):
        return redirect("/login")
    
    lang = get_language()
    t = get_translated_text(lang)
    reply=""
    if request.method=="POST":
        q=request.form["q"].lower()
        if "water" in q:
            reply="Drip irrigation is best when moisture is low."
        elif "fertilizer" in q:
            reply="Balanced NPK is recommended based on soil test."
        elif "ph" in q:
            reply="Ideal soil pH is 6.0 to 7.5."
        else:
            reply="Please contact Agro-x expert support."
    return render_template_string(HELP_HTML,reply=reply, lang=lang, t=t)

# ================= HTML TEMPLATES =================
INTRO_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agro-x | Solar-Agri Hybrid OS</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4caf50;
            --primary-dark: #2e7d32;
            --secondary: #2196f3;
            --accent: #ff9800;
            --dark: #1a1a1a;
            --light: #f8f9fa;
            --gray: #6c757d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0c3b2e 0%, #1b5e20 100%);
            color: white;
            min-height: 100vh;
            overflow-x: hidden;
        }

        .header {
            background: rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
            padding: 20px 40px;
            position: fixed;
            width: 100%;
            top: 0;
            z-index: 1000;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: white;
            font-weight: 700;
            font-size: 24px;
        }

        .logo i {
            color: var(--primary);
            font-size: 28px;
        }

        .nav-links {
            display: flex;
            gap: 30px;
            align-items: center;
        }

        .nav-link {
            color: rgba(255, 255, 255, 0.8);
            text-decoration: none;
            font-weight: 500;
            padding: 10px 20px;
            border-radius: 8px;
            transition: all 0.3s ease;
        }

        .nav-link:hover {
            color: white;
            background: rgba(255, 255, 255, 0.1);
        }

        .btn-primary {
            background: var(--primary);
            color: white;
            padding: 12px 30px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s ease;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }

        .hero {
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 120px 40px 40px;
            text-align: center;
            position: relative;
        }

        .hero-content {
            max-width: 1000px;
            z-index: 1;
        }

        .hero-title {
            font-size: 56px;
            font-weight: 800;
            margin-bottom: 20px;
            line-height: 1.2;
            background: linear-gradient(135deg, #4caf50, #2196f3);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-subtitle {
            font-size: 20px;
            line-height: 1.6;
            opacity: 0.9;
            margin-bottom: 40px;
        }

        .section {
            padding: 100px 40px;
            max-width: 1200px;
            margin: 0 auto;
        }

        .section-title {
            font-size: 42px;
            font-weight: 700;
            margin-bottom: 40px;
            text-align: center;
            color: var(--primary);
        }

        .section-subtitle {
            font-size: 18px;
            text-align: center;
            margin-bottom: 60px;
            opacity: 0.8;
            max-width: 800px;
            margin-left: auto;
            margin-right: auto;
        }

        .content-box {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .content-box h3 {
            font-size: 28px;
            margin-bottom: 20px;
            color: var(--accent);
        }

        .content-box p {
            font-size: 16px;
            line-height: 1.8;
            opacity: 0.9;
            margin-bottom: 20px;
        }

        .content-box ul {
            list-style-type: none;
            padding-left: 0;
        }

        .content-box li {
            padding: 10px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            font-size: 16px;
            opacity: 0.9;
        }

        .content-box li:last-child {
            border-bottom: none;
        }

        .content-box li i {
            color: var(--primary);
            margin-right: 10px;
        }

        .ceo-section {
            display: flex;
            align-items: center;
            gap: 50px;
            margin-bottom: 60px;
        }

        .ceo-photo {
            width: 300px;
            height: 300px;
            border-radius: 20px;
            object-fit: cover;
            border: 4px solid var(--primary);
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
        }

        .ceo-info {
            flex: 1;
        }

        .ceo-name {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 10px;
            color: var(--primary);
        }

        .ceo-title {
            font-size: 18px;
            opacity: 0.8;
            margin-bottom: 20px;
        }

        .ceo-quote {
            font-size: 18px;
            line-height: 1.6;
            font-style: italic;
            border-left: 4px solid var(--primary);
            padding-left: 20px;
            margin-top: 20px;
        }

        .models-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin-top: 50px;
        }

        .model-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 30px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: all 0.3s ease;
        }

        .model-card:hover {
            transform: translateY(-10px);
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--primary);
        }

        .model-icon {
            font-size: 48px;
            color: var(--primary);
            margin-bottom: 20px;
        }

        .model-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 15px;
            color: white;
        }

        .model-desc {
            font-size: 14px;
            opacity: 0.8;
            line-height: 1.6;
        }

        .vision-mission {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            margin-top: 50px;
        }

        .vm-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 30px;
            border-left: 5px solid var(--primary);
        }

        .vm-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 20px;
            color: var(--accent);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .vm-text {
            font-size: 16px;
            line-height: 1.8;
            opacity: 0.9;
        }

        .footer {
            background: rgba(0, 0, 0, 0.5);
            padding: 60px 40px;
            text-align: center;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .footer-links {
            display: flex;
            justify-content: center;
            gap: 40px;
            margin-bottom: 40px;
            flex-wrap: wrap;
        }

        .footer-link {
            color: rgba(255, 255, 255, 0.7);
            text-decoration: none;
            transition: color 0.3s ease;
        }

        .footer-link:hover {
            color: white;
        }

        .copyright {
            font-size: 14px;
            opacity: 0.7;
        }

        /* Language Selector */
        .language-selector {
            position: relative;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
            z-index: 1000;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        /* Responsive */
        @media (max-width: 768px) {
            .hero-title {
                font-size: 36px;
            }
            
            .ceo-section {
                flex-direction: column;
                text-align: center;
            }
            
            .ceo-photo {
                width: 200px;
                height: 200px;
            }
            
            .section {
                padding: 60px 20px;
            }
            
            .section-title {
                font-size: 32px;
            }
            
            .nav-links {
                display: none;
            }
            
            .vision-mission {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 480px) {
            .hero {
                padding: 100px 20px 20px;
            }
            
            .hero-title {
                font-size: 28px;
            }
            
            .content-box {
                padding: 20px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="nav-container">
            <a href="/" class="logo">
                <i class="fas fa-seedling"></i>
                Agro-x
            </a>
            
            <div class="nav-links">
                <a href="#vision" class="nav-link">Vision & Mission</a>
                <a href="#ceo" class="nav-link">Our Founder</a>
                <a href="#models" class="nav-link">Our Models</a>
                <a href="#challenges" class="nav-link">The Challenge</a>
                
                <!-- Language Selector -->
                <div class="language-selector">
                    <div class="lang-btn">
                        <i class="fas fa-globe"></i>
                        English
                        <i class="fas fa-chevron-down"></i>
                    </div>
                    <div class="lang-dropdown">
                        <a href="/set_language/en" class="lang-option">English</a>
                        <a href="/set_language/hi" class="lang-option">हिंदी</a>
                        <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
                    </div>
                </div>
                
                <a href="/home" class="btn-primary">
                    <i class="fas fa-sign-in-alt"></i>
                    Get Started
                </a>
            </div>
        </div>
    </header>

    <!-- Hero Section -->
    <section class="hero">
        <div class="hero-content">
            <h1 class="hero-title">Solar-Agri Hybrid OS</h1>
            <p class="hero-subtitle">
                World-first autonomous ecosystem bridging the gap between AI and Traditional Agriculture. 
                Empowering farmers with precision technology while guaranteeing 100% pesticide-free produce.
            </p>
            <a href="#challenges" class="btn-primary">
                <i class="fas fa-arrow-down"></i>
                Explore Our Innovation
            </a>
        </div>
    </section>

    <!-- Challenges Section -->
    <section class="section" id="challenges">
        <h2 class="section-title">The Critical Challenges</h2>
        <p class="section-subtitle">
            Modern agriculture is struggling under the weight of three critical challenges that threaten global food security
        </p>
        
        <div class="content-box">
            <h3>The Problem We Solve</h3>
            <p>
                Modern agriculture is struggling under the weight of three critical challenges: extreme climate unpredictability, 
                rapid soil degradation due to chemical over-application, and a lack of transparency in the organic food supply chain. 
                Traditional "Smart Farming" solutions often fail in rural environments because they are expensive, depend on a stable 
                power grid, and require constant internet connectivity.
            </p>
            
            <h3 style="margin-top: 30px;">Our Solution</h3>
            <p>
                This project introduces the <strong>Solar-Agri Hybrid OS</strong>, a world-first, end-to-end autonomous ecosystem 
                designed to empower farmers with precision technology while guaranteeing 100% pesticide-free produce for consumers.
            </p>
            
            <h3 style="margin-top: 30px;">Technical Innovation & Methodology</h3>
            <p>
                The core of this innovation lies in its <strong>Hybrid Infrastructure</strong>. To solve the problem of remote accessibility, 
                the system is <strong>100% Solar-Powered</strong> and features a <strong>dual-mode Online/Offline AI Controller</strong>. 
                This allows the system to process complex data and manage the farm even in areas with zero electricity and no internet.
            </p>
            
            <p>
                The hardware employs a <strong>high-precision sensor array</strong>—measuring NPK (Nitrogen, Phosphorus, Potassium), 
                pH, TDS, Turbidity, and Soil Moisture. Unlike standard systems, it uses an <strong>advanced Auto-Dosing Mechanism</strong> 
                (utilizing peristaltic and diaphragm pumps) to deliver exact nutrients directly to the roots.
            </p>
            
            <p>
                To combat climate stress, the system regulates water temperature from the storage tank to the final sprinkler nozzle, 
                preventing the psychological and physiological "thermal shock" that plants often face during extreme weather. 
                Furthermore, the system includes a <strong>Standalone Disease Detection Device</strong> that uses Edge-AI to identify 
                pests locally and suggest immediate organic remedies, eliminating the need for chemical pesticides.
            </p>
            
            <h3 style="margin-top: 30px;">The Certification & Grading Ecosystem</h3>
            <p>
                The project's most unique feature is the <strong>Plant Monitoring & Gradation Protocol</strong>. The system tracks 
                the plant through every developmental stage—from germination to remodel and finally harvesting. Farmers upload 
                real-time photographic evidence through the platform.
            </p>
            
            <p>
                To ensure absolute honesty, the system integrates a <strong>Human-in-the-Loop verification model</strong>. 
                An assigned Agriculture Officer monitors the AI data and can trigger a mandatory Field Visit if any discrepancy 
                is detected. Upon successful harvest, the company issues a <strong>Certified Grade</strong>, providing scientific 
                proof that the vegetables are 100% natural and pesticide-free.
            </p>
            
            <h3 style="margin-top: 30px;">Conclusion & Impact</h3>
            <p>
                The Solar-Agri Hybrid OS bridges the gap between sophisticated technology and ground-level farming. 
                By reducing human error and labor costs, it achieves a "Low-Investment, High-Yield" model. It is not just 
                a tool for irrigation, but a complete Trust Ecosystem that restores soil health, protects the environment 
                through organic practices, and ensures food safety for the global population. This integrated approach—combining 
                solar energy, offline AI, and multi-tier verification—positions this system as a pioneering solution in the 
                global Agri-Tech market.
            </p>
        </div>
    </section>

    <!-- Vision & Mission -->
    <section class="section" id="vision">
        <h2 class="section-title">Our Vision & Mission</h2>
        
        <div class="vision-mission">
            <div class="vm-card">
                <h3 class="vm-title"><i class="fas fa-eye"></i> Vision</h3>
                <p class="vm-text">
                    "To create a world where every farm is a self-sustaining smart ecosystem, ensuring that the soil remains 
                    fertile for generations and every household has access to 100% certified, pesticide-free, and nutrient-rich 
                    food through affordable global technology."
                </p>
            </div>
            
            <div class="vm-card">
                <h3 class="vm-title"><i class="fas fa-bullseye"></i> Mission</h3>
                <p class="vm-text">
                    "Our mission is to empower farmers by bridging the gap between Artificial Intelligence and Traditional Agriculture. 
                    We provide an all-in-one Solar-Powered Hybrid System that automates irrigation and nutrient dosing, detects diseases 
                    in real-time, and provides a transparent Certification Protocol to restore trust between the farmer and the consumer."
                </p>
            </div>
        </div>

        <div class="content-box" style="margin-top: 40px;">
            <h3><i class="fas fa-flag-checkered"></i> Our Goals</h3>
            <ul>
                <li><i class="fas fa-sun"></i> <strong>Zero-Grid Dependency:</strong> To make precision farming possible in the most remote areas using 100% Solar Energy and Offline AI capabilities.</li>
                <li><i class="fas fa-seedling"></i> <strong>Soil Health Restoration:</strong> To eliminate chemical overuse by using NPK-TDS-pH sensing and automated organic dosing to maintain perfect soil balance.</li>
                <li><i class="fas fa-user-tie"></i> <strong>Farmer Prosperity:</strong> To reduce labor costs and human error by 40% while increasing crop market value through our Integrated Grading & Certification System.</li>
                <li><i class="fas fa-thermometer-half"></i> <strong>Climate Resilience:</strong> To protect crops from thermal shock and "Root Rotting" by managing water temperature and automated drainage through predictive analytics.</li>
            </ul>
        </div>
    </section>

    <!-- CEO Section -->
    <section class="section" id="ceo">
        <h2 class="section-title">Our Founder & Lead Innovator</h2>
        
        <div class="ceo-section">
            <img src="https://i.imgur.com/z8pGU1Z.jpeg" alt="Somyasree Swain" class="ceo-photo">
            <div class="ceo-info">
                <h3 class="ceo-name">Somyasree Swain</h3>
                <p class="ceo-title">Founder, Lead Innovator | Student, PM SHRI KV No. 3 Mundali, Cuttack</p>
                
                <div class="content-box">
                    <p>
                        "While today's youth are gravitating towards software and corporate sectors, a massive innovation gap 
                        has emerged in the very backbone of our nation: Agriculture. For the past three years, my dedication 
                        has been to bridge this gap. I believe that Digital India should not just be for the cities, but for 
                        every acre of farmland in our country.
                    </p>
                    
                    <p>
                        Through relentless research at PM SHRI KV No. 3 Mundali, Cuttack, I have developed a holistic ecosystem 
                        that satisfies the vision of Viksit Bharat. From the Agro-X model—which serves everyone from small-scale 
                        land farmers to large commercial polyhouses—to the D² (Disease Detection Device), the world's first 
                        dedicated hardware for on-field diagnosis, my goal is to make the Indian farmer truly Atmanirbhar (Self-Reliant).
                    </p>
                    
                    <p class="ceo-quote">
                        This is a movement Made in Odisha and Made in India, proving that with solar power and AI, 
                        we can transform agriculture from a struggle into a high-tech, certified, and profitable profession.
                    </p>
                </div>
            </div>
        </div>
    </section>

    <!-- Product Models -->
    <section class="section" id="models">
        <h2 class="section-title">The Innovation Roadmap</h2>
        <p class="section-subtitle">Our Signature Models - A Complete Suite for Modern Agriculture</p>
        
        <div class="models-grid">
            <div class="model-card">
                <div class="model-icon">
                    <i class="fas fa-solar-panel"></i>
                </div>
                <h3 class="model-title">AGRO-X (Precision Infrastructure)</h3>
                <p class="model-desc">
                    <strong>Scale:</strong> Adaptable for Small, Medium, Large, and Commercial farms.<br>
                    <strong>Utility:</strong> Solar-powered automation for Polyhouses and Open-field farming. 
                    It handles everything from NPK dosing to temperature-controlled irrigation.
                </p>
            </div>
            
            <div class="model-card">
                <div class="model-icon">
                    <i class="fas fa-microscope"></i>
                </div>
                <h3 class="model-title">D² DEVICE (The Global First)</h3>
                <p class="model-desc">
                    <strong>Meaning:</strong> Disease Detection Device.<br>
                    <strong>Innovation:</strong> The first standalone hardware in the global market designed specifically 
                    to identify crop diseases at the edge without needing constant cloud dependency.
                </p>
            </div>
            
            <div class="model-card">
                <div class="model-icon">
                    <i class="fas fa-award"></i>
                </div>
                <h3 class="model-title">GRADATION SYSTEM (Under Process)</h3>
                <p class="model-desc">
                    <strong>The Trust Layer:</strong> A revolutionary system where farmers can certify their produce.<br>
                    <strong>Goal:</strong> By integrating AI photo tracking and Agriculture Officer verification, 
                    we provide a Certified Organic status, ensuring the produce is 100% natural and pesticide-free.
                </p>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div class="footer-links">
            <a href="#challenges" class="footer-link">The Challenge</a>
            <a href="#vision" class="footer-link">Vision & Mission</a>
            <a href="#ceo" class="footer-link">Our Founder</a>
            <a href="#models" class="footer-link">Our Models</a>
            <a href="/home" class="footer-link">Get Started</a>
            <a href="mailto:autocrop24@gmail.com" class="footer-link">Contact Us</a>
        </div>
        
        <div class="copyright">
            <p>© 2024 Agro-x. All rights reserved. | Solar-Agri Hybrid OS</p>
            <p>CDA Sector-9, Kathajodi Enclave, Lane-6, A1/2, Cuttack, Odisha - 753014</p>
            <p>📞 9692777847 | ✉ autocrop24@gmail.com</p>
        </div>
    </footer>

    <script>
        // Smooth scrolling for anchor links
        document.querySelectorAll('a[href^="#"]').forEach(anchor => {
            anchor.addEventListener('click', function (e) {
                e.preventDefault();
                const targetId = this.getAttribute('href');
                if (targetId === '#') return;
                
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    window.scrollTo({
                        top: targetElement.offsetTop - 80,
                        behavior: 'smooth'
                    });
                }
            });
        });

        // Header scroll effect
        window.addEventListener('scroll', () => {
            const header = document.querySelector('.header');
            if (window.scrollY > 50) {
                header.style.background = 'rgba(0, 0, 0, 0.8)';
                header.style.backdropFilter = 'blur(20px)';
            } else {
                header.style.background = 'rgba(0, 0, 0, 0.3)';
                header.style.backdropFilter = 'blur(10px)';
            }
        });

        // Animate elements on scroll
        const observerOptions = {
            threshold: 0.1,
            rootMargin: '0px 0px -50px 0px'
        };

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.style.opacity = '1';
                    entry.target.style.transform = 'translateY(0)';
                }
            });
        }, observerOptions);

        // Observe content boxes
        document.querySelectorAll('.content-box, .model-card, .vm-card').forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(20px)';
            el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            observer.observe(el);
        });
    </script>
</body>
</html>
"""

# Rest of the HTML templates remain exactly the same as in your original code...
# I'll keep them as is since you said you'll handle them

VERIFICATION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.verify_account }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #4CAF50, #2E7D32);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .verification-container {
            width: 100%;
            max-width: 400px;
        }

        .verification-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            color: #333;
        }

        .verification-header {
            text-align: center;
            margin-bottom: 30px;
        }

        .verification-icon {
            font-size: 48px;
            color: #4CAF50;
            margin-bottom: 15px;
        }

        .verification-title {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 10px;
            color: #2E7D32;
        }

        .verification-subtitle {
            font-size: 16px;
            color: #666;
            margin-bottom: 10px;
        }

        .code-display {
            background: #f8f9fa;
            border: 2px dashed #4CAF50;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            text-align: center;
            font-family: monospace;
            font-size: 24px;
            font-weight: 700;
            color: #333;
            letter-spacing: 5px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }

        .form-input {
            width: 100%;
            padding: 14px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9fa;
            text-align: center;
            letter-spacing: 5px;
            font-size: 18px;
        }

        .form-input:focus {
            outline: none;
            border-color: #4CAF50;
            background: white;
            box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
        }

        .btn-verify {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-top: 10px;
        }

        .btn-verify:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }

        .error-message {
            background: #ffebee;
            color: #c62828;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: {% if error %}block{% else %}none{% endif %};
        }

        .resend-link {
            text-align: center;
            margin-top: 20px;
        }

        .resend-link a {
            color: #4CAF50;
            text-decoration: none;
            font-weight: 500;
        }

        .resend-link a:hover {
            text-decoration: underline;
        }

        .demo-note {
            background: #e8f5e9;
            border: 1px solid #c8e6c9;
            border-radius: 8px;
            padding: 15px;
            margin-top: 20px;
            font-size: 14px;
            color: #2E7D32;
        }

        .demo-note strong {
            display: block;
            margin-bottom: 5px;
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="verification-container">
        <div class="verification-card">
            <div class="verification-header">
                <div class="verification-icon">
                    <i class="fas fa-shield-alt"></i>
                </div>
                <h1 class="verification-title">{{ t.verify_account }}</h1>
                <p class="verification-subtitle">{{ t.check_email_for_code }}</p>
                <p class="verification-subtitle">Email: {{ email }}</p>
            </div>

            {% if error %}
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i> {{ error }}
            </div>
            {% endif %}

            <!-- Demo Note -->
            <div class="demo-note">
                <strong>📝 Demo Note:</strong>
                <p>Since this is a demo, the verification code is:</p>
                <div class="code-display">{{ session.verification_code }}</div>
                <p>Enter this code in the field below to verify your account.</p>
            </div>

            <form method="post">
                <div class="form-group">
                    <label class="form-label">{{ t.enter_verification_code }}</label>
                    <input type="text" name="verification_code" class="form-input" 
                           placeholder="000000" required maxlength="6" pattern="[0-9]{6}">
                </div>

                <button type="submit" class="btn-verify">
                    <i class="fas fa-check-circle"></i>
                    {{ t.verify_now }}
                </button>
            </form>

            <div class="resend-link">
                <p>Didn't receive the code? <a href="/resend_code">{{ t.resend_code }}</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""

# The rest of the HTML templates (DASHBOARD_HTML, ADMIN_HTML, etc.) remain exactly the same
# I'm keeping them as is since they are already in your code
# Let me know if you need any of them modified
# ================= HTML TEMPLATES =================
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.dashboard }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --primary: #4caf50;
            --primary-dark: #2e7d32;
            --secondary: #2196f3;
            --danger: #f44336;
            --warning: #ff9800;
            --success: #4caf50;
            --dark: #1a1a1a;
            --light: #f8f9fa;
            --gray: #6c757d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: #f5f7fa;
            color: #333;
            min-height: 100vh;
            overflow-x: hidden;
        }

        .navbar {
            background: white;
            box-shadow: 0 2px 20px rgba(0, 0, 0, 0.1);
            position: sticky;
            top: 0;
            z-index: 1000;
            padding: 0 20px;
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
        }

        .nav-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }

        .logo-icon {
            font-size: 28px;
            color: var(--primary);
        }

        .logo-text {
            font-size: 22px;
            font-weight: 700;
            color: var(--dark);
        }

        .nav-menu {
            display: flex;
            gap: 25px;
            align-items: center;
        }

        .nav-link {
            color: var(--gray);
            text-decoration: none;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .nav-link:hover, .nav-link.active {
            color: var(--primary);
            background: rgba(76, 175, 80, 0.1);
        }

        .user-info {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 16px;
            background: var(--light);
            border-radius: 8px;
        }

        .user-avatar {
            width: 36px;
            height: 36px;
            background: var(--primary);
            color: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 30px 20px;
        }

        .dashboard-header {
            margin-bottom: 30px;
        }

        .welcome-text {
            font-size: 28px;
            font-weight: 700;
            color: var(--dark);
            margin-bottom: 10px;
        }

        .date-time {
            color: var(--gray);
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .weather-banner {
            background: linear-gradient(135deg, var(--secondary), #1976d2);
            color: white;
            padding: 20px;
            border-radius: 16px;
            margin-bottom: 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .weather-info {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .weather-icon {
            font-size: 48px;
        }

        .weather-details {
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }

        .weather-item {
            display: flex;
            flex-direction: column;
            align-items: center;
        }

        .weather-value {
            font-size: 20px;
            font-weight: 600;
        }

        .weather-label {
            font-size: 12px;
            opacity: 0.9;
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 16px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            transition: transform 0.3s ease;
            cursor: pointer;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .stat-title {
            font-size: 14px;
            color: var(--gray);
            font-weight: 500;
        }

        .stat-value {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 5px;
        }

        .stat-unit {
            font-size: 14px;
            color: var(--gray);
        }

        .stat-trend {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px;
        }

        .trend-up { color: var(--success); }
        .trend-down { color: var(--danger); }

        /* NPK Bars - FIXED SPACING */
.npk-container {
    background: white;
    border-radius: 16px;
    padding: 25px;
    margin-bottom: 30px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
}

.npk-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 25px;
    color: var(--dark);
    text-align: center;
    padding-bottom: 15px;
    border-bottom: 2px solid var(--light);
}

.npk-bars {
    display: flex;
    justify-content: space-around;
    align-items: flex-end;
    height: 220px;
    gap: 40px;
    padding: 0 20px;
}

.npk-bar-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100px;
}

.npk-bar-label {
    margin-bottom: 15px;
    font-weight: 700;
    color: var(--dark);
    font-size: 16px;
    text-align: center;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.npk-bar {
    width: 60px;
    background: #e0e0e0;
    border-radius: 8px 8px 0 0;
    position: relative;
    overflow: hidden;
    height: 160px;
    margin-bottom: 10px;
}

.npk-fill {
    position: absolute;
    bottom: 0;
    width: 100%;
    border-radius: 8px 8px 0 0;
    transition: height 1s ease-in-out;
}

.npk-fill.N {
    background: linear-gradient(to top, #4caf50, #81c784);
}

.npk-fill.P {
    background: linear-gradient(to top, #2196f3, #64b5f6);
}

.npk-fill.K {
    background: linear-gradient(to top, #ff9800, #ffb74d);
}

.npk-value {
    margin-top: 15px;
    font-size: 28px;
    font-weight: 700;
    height: 40px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.npk-value.N { color: #4caf50; }
.npk-value.P { color: #2196f3; }
.npk-value.K { color: #ff9800; }

/* Labels for NPK bars */
.npk-labels {
    display: flex;
    justify-content: space-around;
    margin-top: 20px;
    padding: 0 40px;
}

.npk-label {
    font-size: 14px;
    color: var(--gray);
    text-align: center;
    width: 100px;
}

@media (max-width: 768px) {
    .npk-bars {
        flex-direction: column;
        align-items: center;
        height: auto;
        gap: 30px;
        padding: 20px;
    }
    
    .npk-bar-container {
        width: 100%;
        max-width: 200px;
    }
    
    .npk-labels {
        flex-direction: column;
        align-items: center;
        gap: 10px;
    }
}
        .chart-container {
            background: white;
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }

        .chart-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: var(--dark);
            padding-bottom: 10px;
            border-bottom: 2px solid var(--light);
        }

        .alerts-section {
            background: white;
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }

        .alerts-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .alerts-title {
            font-size: 20px;
            font-weight: 600;
            color: var(--dark);
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .alert-count {
            background: var(--danger);
            color: white;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
        }

        .alerts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
        }

        .alert-card {
            padding: 15px;
            border-radius: 12px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .alert-icon {
            font-size: 24px;
            flex-shrink: 0;
        }

        .alert-content h4 {
            font-size: 14px;
            margin-bottom: 5px;
            font-weight: 600;
        }

        .alert-content p {
            font-size: 12px;
            color: var(--gray);
        }

        .critical { background: rgba(244, 67, 54, 0.1); border-left: 4px solid var(--danger); }
        .warning { background: rgba(255, 152, 0, 0.1); border-left: 4px solid var(--warning); }
        .safety { background: rgba(33, 150, 243, 0.1); border-left: 4px solid var(--secondary); }

        .quick-actions {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .action-card {
            background: white;
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            text-decoration: none;
            color: var(--dark);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }

        .action-card:hover {
            transform: translateY(-5px);
            border-color: var(--primary);
            box-shadow: 0 8px 30px rgba(76, 175, 80, 0.15);
        }

        .action-icon {
            font-size: 32px;
            color: var(--primary);
            margin-bottom: 15px;
        }

        .action-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 8px;
        }

        .action-desc {
            font-size: 13px;
            color: var(--gray);
        }

        /* Language Selector */
        .language-selector {
            position: relative;
        }

        .lang-btn {
            background: var(--light);
            border: 1px solid #e0e0e0;
            color: var(--gray);
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: #e9ecef;
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: white;
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            z-index: 1000;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: var(--dark);
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: var(--light);
        }

        @media (max-width: 768px) {
            .nav-container {
                flex-direction: column;
                gap: 15px;
                padding: 15px;
            }
            
            .nav-menu {
                flex-wrap: wrap;
                justify-content: center;
            }
            
            .weather-banner {
                flex-direction: column;
                gap: 20px;
                text-align: center;
            }
            
            .weather-info {
                flex-direction: column;
            }
            
            .stats-grid {
                grid-template-columns: 1fr;
            }
            
            .npk-bars {
                flex-direction: column;
                align-items: center;
                height: auto;
                gap: 30px;
                padding: 20px;
            }
            
            .npk-bar-container {
                width: 100%;
                max-width: 200px;
            }
            
            .npk-label-container {
                flex-direction: column;
                align-items: center;
                gap: 10px;
            }
            
            .language-selector {
                margin-top: 10px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Navigation -->
    <nav class="navbar">
        <div class="nav-container">
            <a href="/" class="nav-logo">
                <i class="fas fa-seedling logo-icon"></i>
                <span class="logo-text">Agro-x</span>
            </a>
            
            <div class="nav-menu">
                <a href="/dashboard" class="nav-link active">
                    <i class="fas fa-chart-line"></i>
                    {{ t.dashboard }}
                </a>
                <a href="/weather" class="nav-link">
                    <i class="fas fa-cloud-sun"></i>
                    {{ t.weather }}
                </a>
                <a href="/control_panel" class="nav-link">
                    <i class="fas fa-sliders-h"></i>
                    {{ t.control_panel }}
                </a>
                <a href="/shop" class="nav-link">
                    <i class="fas fa-shopping-cart"></i>
                    {{ t.shop }}
                </a>
                <a href="/admin" class="nav-link">
                    <i class="fas fa-cog"></i>
                    {{ t.admin }}
                </a>
                
                <!-- Language Selector -->
                <div class="language-selector">
                    <div class="lang-btn">
                        <i class="fas fa-globe"></i>
                        {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
                        <i class="fas fa-chevron-down"></i>
                    </div>
                    <div class="lang-dropdown">
                        <a href="/set_language/en" class="lang-option">English</a>
                        <a href="/set_language/hi" class="lang-option">हिंदी</a>
                        <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
                    </div>
                </div>
                
                <div class="user-info">
                    <div class="user-avatar">
                        <i class="fas fa-user"></i>
                    </div>
                    <span>Farmer</span>
                </div>
            </div>
        </div>
    </nav>

    <!-- Main Content -->
    <div class="container">
        <!-- Header -->
        <div class="dashboard-header">
            <h1 class="welcome-text">🌱 {{ t.smart_agriculture_dashboard }}</h1>
            <div class="date-time">
                <i class="far fa-calendar"></i>
                <span id="currentDateTime"></span>
            </div>
        </div>

        <!-- Weather Banner -->
        <div class="weather-banner">
            <div class="weather-info">
                <div class="weather-icon">
                    <i class="fas fa-sun"></i>
                </div>
                <div>
                    <div style="font-size: 32px; font-weight: 700;">{{ weather.temp }}°C</div>
                    <div>{{ weather.description|capitalize }}</div>
                </div>
            </div>
            <div class="weather-details">
                <div class="weather-item">
                    <div class="weather-value">{{ weather.humidity }}%</div>
                    <div class="weather-label">{{ t.humidity }}</div>
                </div>
                <div class="weather-item">
                    <div class="weather-value">{{ weather.wind_speed }} km/h</div>
                    <div class="weather-label">{{ t.wind_speed }}</div>
                </div>
                <div class="weather-item">
                    <div class="weather-value">{{ weather.pressure }} mb</div>
                    <div class="weather-label">{{ t.pressure }}</div>
                </div>
                <div class="weather-item">
                    <div class="weather-value">{{ weather.sunrise }}</div>
                    <div class="weather-label">{{ t.sunrise }}</div>
                </div>
                <div class="weather-item">
                    <div class="weather-value">{{ weather.sunset }}</div>
                    <div class="weather-label">{{ t.sunset }}</div>
                </div>
            </div>
        </div>

        <!-- NPK Bars with proper spacing -->
<div class="npk-container">
    <div class="npk-bars">
        <div class="npk-bar-container">
            <div class="npk-bar-label">Nitrogen (N)</div>
            <div class="npk-bar">
                <div class="npk-fill N" id="nBar" style="height: {{ data.N }}%"></div>
            </div>
            <div class="npk-value N" id="nValue">{{ data.N }}%</div>
        </div>
        <div class="npk-bar-container">
            <div class="npk-bar-label">Phosphorus (P)</div>
            <div class="npk-bar">
                <div class="npk-fill P" id="pBar" style="height: {{ data.P }}%"></div>
            </div>
            <div class="npk-value P" id="pValue">{{ data.P }}%</div>
        </div>
        <div class="npk-bar-container">
            <div class="npk-bar-label">Potassium (K)</div>
            <div class="npk-bar">
                <div class="npk-fill K" id="kBar" style="height: {{ data.K }}%"></div>
            </div>
            <div class="npk-value K" id="kValue">{{ data.K }}%</div>
        </div>
    </div>
    <div class="npk-labels">
        <div class="npk-label">Essential for leaf growth</div>
        <div class="npk-label">Important for root development</div>
        <div class="npk-label">Vital for overall plant health</div>
    </div>
</div>
        <!-- Stats Grid -->
        <div class="stats-grid">
            {% for key, value in data.items() %}
            {% if key not in ['N', 'P', 'K'] %}
            <div class="stat-card" onclick="focusChart('{{ key }}')">
                <div class="stat-header">
                    <div class="stat-title">{{ key|replace('_', ' ')|title }}</div>
                    <div class="stat-trend">
                        <i class="fas fa-arrow-up trend-up"></i>
                        <span>+2.5%</span>
                    </div>
                </div>
                <div class="stat-value">{{ value }}</div>
                <div class="stat-unit">
                    {% if key in ['tank_level', 'battery', 'moisture', 'air_humidity', 'turbidity'] %}
                    %
                    {% elif key in ['water_temp', 'air_temp'] %}
                    °C
                    {% elif key == 'ph' %}
                    pH
                    {% elif key in ['TDS', 'CO2'] %}
                    ppm
                    {% endif %}
                </div>
                <div class="progress-bar" style="margin-top: 15px; height: 4px; background: #e0e0e0; border-radius: 2px; overflow: hidden;">
                    {% set percentage = (value/100)*100 if key in ['tank_level', 'battery', 'moisture', 'air_humidity', 'turbidity'] else 50 %}
                    <div style="height: 100%; width: {{ percentage }}%; background: var(--primary);"></div>
                </div>
            </div>
            {% endif %}
            {% endfor %}
        </div>

        <!-- Charts -->
        <div class="chart-container">
            <h3 class="chart-title">NPK Levels Over Time</h3>
            <canvas id="npkChart" height="100"></canvas>
        </div>

        <!-- Alerts -->
        <div class="alerts-section">
            <div class="alerts-header">
                <h3 class="alerts-title">
                    <i class="fas fa-exclamation-triangle"></i>
                    Alerts & AI Suggestions
                    <span class="alert-count">{{ alerts|length }}</span>
                </h3>
                <button onclick="refreshAlerts()" style="background: none; border: none; color: var(--primary); cursor: pointer;">
                    <i class="fas fa-sync-alt"></i> Refresh
                </button>
            </div>
            
            <div class="alerts-grid" id="alertsContainer">
                {% for alert in alerts %}
                <div class="alert-card {% if 'Critical' in alert %}critical{% elif 'Warning' in alert %}warning{% else %}safety{% endif %}">
                    <div class="alert-icon">
                        {% if 'Critical' in alert %}
                        <i class="fas fa-exclamation-circle"></i>
                        {% elif 'Warning' in alert %}
                        <i class="fas fa-exclamation-triangle"></i>
                        {% else %}
                        <i class="fas fa-info-circle"></i>
                        {% endif %}
                    </div>
                    <div class="alert-content">
                        <h4>{{ alert.split(':')[0] }}</h4>
                        <p>{{ alert.split(':')[1] if ':' in alert else alert }}</p>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- Quick Actions -->
        <div class="quick-actions">
            <a href="/control_panel" class="action-card">
                <div class="action-icon">
                    <i class="fas fa-sliders-h"></i>
                </div>
                <div class="action-title">{{ t.control_panel }}</div>
                <div class="action-desc">Manage irrigation, nutrients & climate</div>
            </a>
            
            <a href="/export_csv" class="action-card">
                <div class="action-icon">
                    <i class="fas fa-download"></i>
                </div>
                <div class="action-title">Export Data</div>
                <div class="action-desc">Download CSV reports</div>
            </a>
            
            <a href="/shop" class="action-card">
                <div class="action-icon">
                    <i class="fas fa-shopping-cart"></i>
                </div>
                <div class="action-title">{{ t.shop }}</div>
                <div class="action-desc">Purchase farm equipment</div>
            </a>
            
            <a href="/helpdesk" class="action-card">
                <div class="action-icon">
                    <i class="fas fa-headset"></i>
                </div>
                <div class="action-title">{{ t.helpdesk }}</div>
                <div class="action-desc">AI assistant & support</div>
            </a>
        </div>
    </div>

    <script>
        // Update date and time
        function updateDateTime() {
            const now = new Date();
            const options = { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            };
            document.getElementById('currentDateTime').textContent = now.toLocaleDateString('en-US', options);
        }
        updateDateTime();
        setInterval(updateDateTime, 1000);

        // Initialize NPK Chart
        const npkCtx = document.getElementById('npkChart').getContext('2d');
        let npkChart = new Chart(npkCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Nitrogen (N)',
                        data: [],
                        borderColor: '#4caf50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Phosphorus (P)',
                        data: [],
                        borderColor: '#2196f3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        tension: 0.4,
                        fill: true
                    },
                    {
                        label: 'Potassium (K)',
                        data: [],
                        borderColor: '#ff9800',
                        backgroundColor: 'rgba(255, 152, 0, 0.1)',
                        tension: 0.4,
                        fill: true
                    }
                ]
            },
            options: {
                responsive: true,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100,
                        grid: {
                            drawBorder: false
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                },
                plugins: {
                    legend: {
                        position: 'top',
                    }
                }
            }
        });

        // Update dashboard data
        async function updateDashboard() {
            try {
                const response = await fetch('/dashboard_data');
                const data = await response.json();
                
                // Update NPK bars with animation
                ['N', 'P', 'K'].forEach(nutrient => {
                    const bar = document.getElementById(nutrient.toLowerCase() + 'Bar');
                    const value = document.getElementById(nutrient.toLowerCase() + 'Value');
                    if (bar && value) {
                        // Animate bar height
                        bar.style.height = data[nutrient] + '%';
                        // Update value with animation
                        value.textContent = data[nutrient] + '%';
                        
                        // Add glow effect if levels are critical
                        if (data[nutrient] < 30) {
                            bar.style.boxShadow = '0 0 10px #f44336';
                        } else if (data[nutrient] > 70) {
                            bar.style.boxShadow = '0 0 10px #4caf50';
                        } else {
                            bar.style.boxShadow = 'none';
                        }
                    }
                });
                
                // Update other stat cards
                document.querySelectorAll('.stat-card').forEach(card => {
                    const title = card.querySelector('.stat-title').textContent.toLowerCase().replace(' ', '_');
                    if (data[title] !== undefined) {
                        card.querySelector('.stat-value').textContent = data[title];
                        
                        // Update progress bar
                        const bar = card.querySelector('.progress-bar div');
                        let percentage;
                        if (title in ['tank_level', 'battery', 'moisture', 'air_humidity', 'turbidity']) {
                            percentage = (data[title] / 100) * 100;
                        } else {
                            percentage = 50;
                        }
                        bar.style.width = percentage + '%';
                    }
                });
                
                // Update chart
                const time = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                npkChart.data.labels.push(time);
                npkChart.data.datasets[0].data.push(data.N);
                npkChart.data.datasets[1].data.push(data.P);
                npkChart.data.datasets[2].data.push(data.K);
                
                if (npkChart.data.labels.length > 15) {
                    npkChart.data.labels.shift();
                    npkChart.data.datasets.forEach(dataset => dataset.data.shift());
                }
                
                npkChart.update();
                
                // Update alerts
                updateAlerts(data.alerts);
                
            } catch (error) {
                console.error('Error updating dashboard:', error);
            }
        }

        function updateAlerts(alerts) {
            const container = document.getElementById('alertsContainer');
            const countElement = document.querySelector('.alert-count');
            
            container.innerHTML = '';
            countElement.textContent = alerts.length;
            
            alerts.forEach(alert => {
                let alertClass = 'safety';
                let icon = 'fas fa-info-circle';
                
                if (alert.includes('Critical')) {
                    alertClass = 'critical';
                    icon = 'fas fa-exclamation-circle';
                } else if (alert.includes('Warning')) {
                    alertClass = 'warning';
                    icon = 'fas fa-exclamation-triangle';
                }
                
                const [type, message] = alert.split(': ');
                
                const alertCard = document.createElement('div');
                alertCard.className = `alert-card ${alertClass}`;
                alertCard.innerHTML = `
                    <div class="alert-icon">
                        <i class="${icon}"></i>
                    </div>
                    <div class="alert-content">
                        <h4>${type || 'Alert'}</h4>
                        <p>${message || alert}</p>
                    </div>
                `;
                
                container.appendChild(alertCard);
            });
        }

        function refreshAlerts() {
            updateDashboard();
        }

        function focusChart(parameter) {
            // Highlight the parameter in the chart
            alert(`Focusing on ${parameter} trends`);
        }

        // Initial update
        updateDashboard();
        // Update every 5 seconds
        setInterval(updateDashboard, 5000);
    </script>
</body>
</html>
"""

# ================= ADMIN INVENTORY TEMPLATES =================

ADMIN_ADD_PRODUCT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.add_new_product }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #1a237e 0%, #311b92 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
        }

        .back-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: white;
            text-decoration: none;
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            margin-bottom: 30px;
            transition: all 0.3s ease;
        }

        .back-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .form-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .form-header {
            text-align: center;
            margin-bottom: 30px;
        }

        .form-header h1 {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #ff6b6b, #4ecdc4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group.full-width {
            grid-column: 1 / -1;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.9);
        }

        .form-input, .form-textarea, .form-select {
            width: 100%;
            padding: 12px;
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            color: white;
            font-size: 16px;
            transition: all 0.3s ease;
        }

        .form-input:focus, .form-textarea:focus, .form-select:focus {
            outline: none;
            border-color: #4caf50;
            background: rgba(255, 255, 255, 0.15);
        }

        .form-textarea {
            min-height: 100px;
            resize: vertical;
        }

        .form-actions {
            display: flex;
            gap: 15px;
            margin-top: 30px;
        }

        .btn {
            padding: 15px 30px;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-primary {
            background: linear-gradient(135deg, #4caf50, #2e7d32);
            color: white;
            flex: 1;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.2);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .error-message {
            background: rgba(244, 67, 54, 0.2);
            color: #ffcdd2;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #f44336;
        }

        @media (max-width: 768px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .form-actions {
                flex-direction: column;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="container">
        <a href="/admin?tab=inventory" class="back-btn">
            <i class="fas fa-arrow-left"></i>
            {{ t.back_to_inventory }}
        </a>
        
        <div class="form-card">
            <div class="form-header">
                <h1>{{ t.add_new_product }}</h1>
                <p>Add a new product to your inventory</p>
            </div>
            
            {% if error %}
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i> {{ error }}
            </div>
            {% endif %}
            
            <form method="post">
                <div class="form-grid">
                    <div class="form-group">
                        <label class="form-label">{{ t.product_id }} *</label>
                        <input type="text" name="pid" class="form-input" required 
                               placeholder="e.g., soil, drip, nitrogen">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.product_name }} *</label>
                        <input type="text" name="name" class="form-input" required 
                               placeholder="Enter product name">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.product_price }} (₹) *</label>
                        <input type="number" name="price" class="form-input" required 
                               step="0.01" min="0" placeholder="0.00">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.product_category }} *</label>
                        <select name="category" class="form-select" required>
                            <option value="">Select category</option>
                            <option value="sensors">Sensors</option>
                            <option value="irrigation">Irrigation</option>
                            <option value="nutrients">Nutrients</option>
                            <option value="systems">Complete Systems</option>
                            <option value="other">Other</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.product_stock }} *</label>
                        <input type="number" name="stock" class="form-input" required 
                               min="0" placeholder="0">
                    </div>
                    
                    <div class="form-group full-width">
                        <label class="form-label">{{ t.product_images }} *</label>
                        <textarea name="image_urls" class="form-textarea" required 
                                  placeholder="Enter comma separated image URLs
Example: https://example.com/image1.jpg,https://example.com/image2.jpg"></textarea>
                    </div>
                    
                    <div class="form-group full-width">
                        <label class="form-label">{{ t.product_specifications }}</label>
                        <textarea name="specifications" class="form-textarea" 
                                  placeholder="Enter product specifications (optional)"></textarea>
                    </div>
                    
                    <div class="form-group full-width">
                        <label class="form-label">{{ t.description }} *</label>
                        <textarea name="description" class="form-textarea" required 
                                  placeholder="Enter product description"></textarea>
                    </div>
                </div>
                
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save"></i>
                        {{ t.save_product }}
                    </button>
                    <a href="/admin?tab=inventory" class="btn btn-secondary">
                        <i class="fas fa-times"></i>
                        {{ t.cancel }}
                    </a>
                </div>
            </form>
        </div>
    </div>
</body>
</html>
"""

ADMIN_EDIT_PRODUCT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.edit_product }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #1a237e 0%, #311b92 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
        }

        .back-btn {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: white;
            text-decoration: none;
            padding: 10px 20px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            margin-bottom: 30px;
            transition: all 0.3s ease;
        }

        .back-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .form-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .form-header {
            text-align: center;
            margin-bottom: 30px;
        }

        .form-header h1 {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #4ecdc4, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group.full-width {
            grid-column: 1 / -1;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.9);
        }

        .form-input, .form-textarea, .form-select {
            width: 100%;
            padding: 12px;
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            color: white;
            font-size: 16px;
            transition: all 0.3s ease;
        }

        .form-input:focus, .form-textarea:focus, .form-select:focus {
            outline: none;
            border-color: #4caf50;
            background: rgba(255, 255, 255, 0.15);
        }

        .form-textarea {
            min-height: 100px;
            resize: vertical;
        }

        .form-actions {
            display: flex;
            gap: 15px;
            margin-top: 30px;
        }

        .btn {
            padding: 15px 30px;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            border: none;
            font-size: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-primary {
            background: linear-gradient(135deg, #4caf50, #2e7d32);
            color: white;
            flex: 1;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.2);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .error-message {
            background: rgba(244, 67, 54, 0.2);
            color: #ffcdd2;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            border-left: 4px solid #f44336;
        }

        .readonly-input {
            background: rgba(255, 255, 255, 0.05) !important;
            color: rgba(255, 255, 255, 0.7) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
        }

        @media (max-width: 768px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .form-actions {
                flex-direction: column;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="container">
        <a href="/admin?tab=inventory" class="back-btn">
            <i class="fas fa-arrow-left"></i>
            {{ t.back_to_inventory }}
        </a>
        
        <div class="form-card">
            <div class="form-header">
                <h1>{{ t.edit_product }}</h1>
                <p>Edit product: {{ product.name if product else '' }}</p>
            </div>
            
            {% if error %}
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i> {{ error }}
            </div>
            {% endif %}
            
            {% if product %}
            <form method="post">
                <div class="form-grid">
                    <div class="form-group">
                        <label class="form-label">{{ t.product_id }}</label>
                        <input type="text" value="{{ product.pid }}" class="form-input readonly-input" readonly>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.product_name }} *</label>
                        <input type="text" name="name" class="form-input" required 
                               value="{{ product.name }}" placeholder="Enter product name">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.product_price }} (₹) *</label>
                        <input type="number" name="price" class="form-input" required 
                               step="0.01" min="0" value="{{ product.price }}" placeholder="0.00">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.product_category }} *</label>
                        <select name="category" class="form-select" required>
                            <option value="sensors" {% if product.category == 'sensors' %}selected{% endif %}>Sensors</option>
                            <option value="irrigation" {% if product.category == 'irrigation' %}selected{% endif %}>Irrigation</option>
                            <option value="nutrients" {% if product.category == 'nutrients' %}selected{% endif %}>Nutrients</option>
                            <option value="systems" {% if product.category == 'systems' %}selected{% endif %}>Complete Systems</option>
                            <option value="other" {% if product.category == 'other' %}selected{% endif %}>Other</option>
                        </select>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.product_stock }} *</label>
                        <input type="number" name="stock" class="form-input" required 
                               min="0" value="{{ product.stock }}" placeholder="0">
                    </div>
                    
                    <div class="form-group full-width">
                        <label class="form-label">{{ t.product_images }} *</label>
                        <textarea name="image_urls" class="form-textarea" required 
                                  placeholder="Enter comma separated image URLs">{{ product.image_urls }}</textarea>
                    </div>
                    
                    <div class="form-group full-width">
                        <label class="form-label">{{ t.product_specifications }}</label>
                        <textarea name="specifications" class="form-textarea" 
                                  placeholder="Enter product specifications">{{ product.specifications }}</textarea>
                    </div>
                    
                    <div class="form-group full-width">
                        <label class="form-label">{{ t.description }} *</label>
                        <textarea name="description" class="form-textarea" required 
                                  placeholder="Enter product description">{{ product.description }}</textarea>
                    </div>
                </div>
                
                <div class="form-actions">
                    <button type="submit" class="btn btn-primary">
                        <i class="fas fa-save"></i>
                        {{ t.update_product }}
                    </button>
                    <a href="/admin?tab=inventory" class="btn btn-secondary">
                        <i class="fas fa-times"></i>
                        {{ t.cancel }}
                    </a>
                </div>
            </form>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.admin }} {{ t.panel }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4caf50;
            --primary-dark: #2e7d32;
            --secondary: #2196f3;
            --danger: #f44336;
            --warning: #ff9800;
            --success: #4caf50;
            --dark: #1a1a1a;
            --light: #f8f9fa;
            --gray: #6c757d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #1a237e 0%, #311b92 100%);
            color: white;
            min-height: 100vh;
        }

        .navbar {
            background: rgba(0, 0, 0, 0.2);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .nav-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: white;
            font-weight: 600;
            font-size: 20px;
        }

        .back-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .back-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #ff6b6b, #4ecdc4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header p {
            font-size: 18px;
            opacity: 0.9;
        }

        /* Tabs Navigation */
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 40px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 10px;
        }

        .tab-btn {
            padding: 12px 24px;
            background: transparent;
            border: none;
            color: rgba(255, 255, 255, 0.7);
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .tab-btn:hover {
            background: rgba(255, 255, 255, 0.1);
            color: white;
        }

        .tab-btn.active {
            background: rgba(76, 175, 80, 0.2);
            color: #4caf50;
        }

        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        /* Stats Cards */
        .admin-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .stat-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.1);
        }

        .stat-value {
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .stat-label {
            font-size: 14px;
            opacity: 0.8;
        }

        /* Inventory Stats */
        .inventory-stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .inventory-stat-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .inventory-stat-value {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .inventory-stat-label {
            font-size: 14px;
            opacity: 0.8;
        }

        /* Tables Container */
        .tables-container {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            overflow-x: auto;
        }

        .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }

        .table-title {
            font-size: 24px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .search-box {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            padding: 10px 15px;
            color: white;
            width: 250px;
        }

        .search-box::placeholder {
            color: rgba(255, 255, 255, 0.6);
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        thead {
            background: rgba(255, 255, 255, 0.1);
        }

        th {
            padding: 15px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid rgba(255, 255, 255, 0.2);
        }

        td {
            padding: 15px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        tr:hover {
            background: rgba(255, 255, 255, 0.05);
        }

        .user-avatar {
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, #4caf50, #2196f3);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            margin-right: 15px;
        }

        .user-cell {
            display: flex;
            align-items: center;
        }

        .status-badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
        }

        .status-active {
            background: rgba(76, 175, 80, 0.2);
            color: #4caf50;
        }

        .status-inactive {
            background: rgba(244, 67, 54, 0.2);
            color: #f44336;
        }

        /* Product Status Badges */
        .stock-badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            display: inline-block;
        }

        .stock-high {
            background: rgba(76, 175, 80, 0.2);
            color: #4caf50;
        }

        .stock-low {
            background: rgba(255, 152, 0, 0.2);
            color: #ff9800;
        }

        .stock-out {
            background: rgba(244, 67, 54, 0.2);
            color: #f44336;
        }

        .action-buttons {
            display: flex;
            gap: 8px;
        }

        .action-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }

        .action-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .action-btn.edit {
            background: rgba(33, 150, 243, 0.2);
            border-color: rgba(33, 150, 243, 0.3);
        }

        .action-btn.delete {
            background: rgba(244, 67, 54, 0.2);
            border-color: rgba(244, 67, 54, 0.3);
        }

        .action-btn.add {
            background: rgba(76, 175, 80, 0.2);
            border-color: rgba(76, 175, 80, 0.3);
            padding: 10px 20px;
            font-weight: 600;
        }

        .add-product-btn {
            background: linear-gradient(135deg, #4caf50, #2e7d32);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 10px;
            text-decoration: none;
        }

        .add-product-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }

        /* Language Selector */
        .language-selector {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        .admin-logout {
            margin-left: 20px;
            background: rgba(244, 67, 54, 0.2);
            border: 1px solid rgba(244, 67, 54, 0.3);
            color: #ff6b6b;
            padding: 8px 15px;
            border-radius: 8px;
            text-decoration: none;
            font-size: 14px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .admin-logout:hover {
            background: rgba(244, 67, 54, 0.3);
        }

        /* Messages */
        .message {
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .message.success {
            background: rgba(76, 175, 80, 0.2);
            border-left: 4px solid #4caf50;
            color: #c8e6c9;
        }

        .message.error {
            background: rgba(244, 67, 54, 0.2);
            border-left: 4px solid #f44336;
            color: #ffcdd2;
        }

        @media (max-width: 768px) {
            .admin-stats, .inventory-stats {
                grid-template-columns: 1fr;
            }
            
            .table-header {
                flex-direction: column;
                gap: 15px;
                align-items: stretch;
            }
            
            .search-box {
                width: 100%;
            }
            
            table {
                display: block;
                overflow-x: auto;
            }
            
            .tabs {
                flex-wrap: wrap;
            }
            
            .tab-btn {
                flex: 1;
                min-width: 120px;
                justify-content: center;
            }
            
            .language-selector {
                top: 10px;
                right: 10px;
            }
            
            .header h1 {
                font-size: 36px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Language Selector -->
    <div class="language-selector">
        <div class="lang-btn">
            <i class="fas fa-globe"></i>
            {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
            <i class="fas fa-chevron-down"></i>
        </div>
        <div class="lang-dropdown">
            <a href="/set_language/en" class="lang-option">English</a>
            <a href="/set_language/hi" class="lang-option">हिंदी</a>
            <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
        </div>
    </div>
    
    <nav class="navbar">
        <div class="nav-container">
            <a href="/dashboard" class="nav-logo">
                <i class="fas fa-seedling"></i>
                Agro-x {{ t.admin }}
            </a>
            <div>
                <a href="/dashboard" class="back-btn">
                    <i class="fas fa-arrow-left"></i>
                    {{ t.back_to_dashboard }}
                </a>
                <a href="/admin?logout=true" class="admin-logout">
                    <i class="fas fa-sign-out-alt"></i>
                    {{ t.logout_admin }}
                </a>
            </div>
        </div>
    </nav>

    <div class="container">
        <div class="header">
            <h1>{{ t.administrator_panel }}</h1>
            <p>{{ t.manage_users }}</p>
        </div>

        <!-- Messages -->
        {% if request.args.get('success') %}
        <div class="message success">
            <i class="fas fa-check-circle"></i>
            {{ request.args.get('success') }}
        </div>
        {% endif %}
        
        {% if request.args.get('error') %}
        <div class="message error">
            <i class="fas fa-exclamation-circle"></i>
            {{ request.args.get('error') }}
        </div>
        {% endif %}

        <!-- Tabs Navigation -->
        <div class="tabs">
            <button class="tab-btn {% if not request.args.get('tab') or request.args.get('tab') == 'users' %}active{% endif %}" 
                    onclick="showTab('users')">
                <i class="fas fa-users"></i>
                {{ t.registered_users }}
            </button>
            <button class="tab-btn {% if request.args.get('tab') == 'inventory' %}active{% endif %}" 
                    onclick="showTab('inventory')">
                <i class="fas fa-boxes"></i>
                {{ t.inventory_management }}
            </button>
        </div>

        <!-- Users Tab -->
        <div id="usersTab" class="tab-content {% if not request.args.get('tab') or request.args.get('tab') == 'users' %}active{% endif %}">
            <div class="admin-stats">
                <div class="stat-card">
                    <div class="stat-value">{{ users|length }}</div>
                    <div class="stat-label">{{ t.total_users }}</div>
                </div>
                <div class="stat-card">
                    {% set farmer_count = 0 %}
                    {% for user in users %}
                        {% if user[2] and user[2].startswith('AGX') %}
                            {% set farmer_count = farmer_count + 1 %}
                        {% endif %}
                    {% endfor %}
                    <div class="stat-value">{{ farmer_count }}</div>
                    <div class="stat-label">{{ t.active_farmers }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{{ crop_count }}</div>
                    <div class="stat-label">{{ t.crop_types }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">24/7</div>
                    <div class="stat-label">{{ t.system_uptime }}</div>
                </div>
            </div>

            <div class="tables-container">
                <div class="table-header">
                    <div class="table-title">
                        <i class="fas fa-users"></i>
                        {{ t.registered_users }}
                    </div>
                    <input type="text" class="search-box" placeholder="{{ t.search_users }}" onkeyup="searchUsers()">
                </div>

                <table id="usersTable">
                    <thead>
                        <tr>
                            <th>{{ t.farmer }}</th>
                            <th>{{ t.contact }}</th>
                            <th>{{ t.farmer_id }}</th>
                            <th>{{ t.location }}</th>
                            <th>{{ t.crop_type }}</th>
                            <th>{{ t.status }}</th>
                            <th>{{ t.actions }}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for user in users %}
                        <tr>
                            <td>
                                <div class="user-cell">
                                    <div class="user-avatar">
                                        {{ user[0][0] if user[0] else 'F' }}
                                    </div>
                                    <div>
                                        <div style="font-weight: 500;">{{ user[0] or 'Unknown' }}</div>
                                        <div style="font-size: 12px; opacity: 0.7;">{{ t.farmer }}</div>
                                    </div>
                                </div>
                            </td>
                            <td>{{ user[1] or 'N/A' }}</td>
                            <td>
                                <code style="background: rgba(255, 255, 255, 0.1); padding: 4px 8px; border-radius: 4px;">{{ user[2] or 'N/A' }}</code>
                            </td>
                            <td>{{ user[3] or 'N/A' }}</td>
                            <td>
                                <span style="background: rgba(76, 175, 80, 0.2); color: #4caf50; padding: 4px 12px; border-radius: 20px; font-size: 12px;">
                                    {{ user[4] or 'Unknown' }}
                                </span>
                            </td>
                            <td>
                                <span class="status-badge status-active">{{ t.active }}</span>
                            </td>
                            <td>
                                <div class="action-buttons">
                                    <button class="action-btn edit" onclick="editUser('{{ user[2] }}')">
                                        <i class="fas fa-edit"></i>
                                    </button>
                                    <button class="action-btn delete" onclick="deleteUser('{{ user[2] }}')">
                                        <i class="fas fa-trash"></i>
                                    </button>
                                    <button class="action-btn" onclick="viewDetails('{{ user[2] }}')">
                                        <i class="fas fa-eye"></i>
                                    </button>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Inventory Tab -->
        <div id="inventoryTab" class="tab-content {% if request.args.get('tab') == 'inventory' %}active{% endif %}">
            <div class="inventory-stats">
                <div class="inventory-stat-card">
                    <div class="inventory-stat-value">{{ total_products }}</div>
                    <div class="inventory-stat-label">{{ t.total_products }}</div>
                </div>
                <div class="inventory-stat-card">
                    <div class="inventory-stat-value">₹ {{ "%.2f"|format(total_value) }}</div>
                    <div class="inventory-stat-label">{{ t.total_value }}</div>
                </div>
                <div class="inventory-stat-card">
                    <div class="inventory-stat-value">{{ in_stock }}</div>
                    <div class="inventory-stat-label">{{ t.in_stock }}</div>
                </div>
                <div class="inventory-stat-card">
                    <div class="inventory-stat-value">{{ low_stock }}</div>
                    <div class="inventory-stat-label">{{ t.low_stock }}</div>
                </div>
                <div class="inventory-stat-card">
                    <div class="inventory-stat-value">{{ out_of_stock }}</div>
                    <div class="inventory-stat-label">{{ t.out_of_stock }}</div>
                </div>
            </div>

            <div class="tables-container">
                <div class="table-header">
                    <div class="table-title">
                        <i class="fas fa-boxes"></i>
                        {{ t.manage_products }}
                    </div>
                    <div>
                        <a href="/admin/add_product" class="add-product-btn">
                            <i class="fas fa-plus"></i>
                            {{ t.add_new_product }}
                        </a>
                    </div>
                </div>

                <table id="productsTable">
                    <thead>
                        <tr>
                            <th>{{ t.product_id }}</th>
                            <th>{{ t.product_name }}</th>
                            <th>{{ t.product_price }}</th>
                            <th>{{ t.product_stock }}</th>
                            <th>{{ t.product_category }}</th>
                            <th>{{ t.status }}</th>
                            <th>{{ t.actions }}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for product in products %}
                        <tr>
                            <td>
                                <code style="background: rgba(255, 255, 255, 0.1); padding: 4px 8px; border-radius: 4px;">{{ product[0] }}</code>
                            </td>
                            <td style="font-weight: 500;">{{ product[1] }}</td>
                            <td>₹ {{ "%.2f"|format(product[2]) }}</td>
                            <td>{{ product[3] }}</td>
                            <td>
                                <span style="text-transform: capitalize; background: rgba(33, 150, 243, 0.2); color: #2196f3; padding: 4px 12px; border-radius: 20px; font-size: 12px;">
                                    {{ product[4] }}
                                </span>
                            </td>
                            <td>
                                {% if product[3] >= 10 %}
                                <span class="stock-badge stock-high">{{ t.in_stock }}</span>
                                {% elif product[3] > 0 and product[3] < 10 %}
                                <span class="stock-badge stock-low">{{ t.low_stock }}</span>
                                {% else %}
                                <span class="stock-badge stock-out">{{ t.out_of_stock }}</span>
                                {% endif %}
                            </td>
                            <td>
                                <div class="action-buttons">
                                    <a href="/admin/edit_product/{{ product[0] }}" class="action-btn edit">
                                        <i class="fas fa-edit"></i>
                                        {{ t.edit }}
                                    </a>
                                    <a href="/admin/delete_product/{{ product[0] }}" 
                                       class="action-btn delete"
                                       onclick="return confirm('{{ t.confirm_delete }}')">
                                        <i class="fas fa-trash"></i>
                                        {{ t.delete }}
                                    </a>
                                </div>
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div style="margin-top: 40px; text-align: center; opacity: 0.8;">
            <p><i class="fas fa-shield-alt"></i> {{ t.admin_security }}</p>
        </div>
    </div>

    <script>
        // Tab functionality
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + 'Tab').classList.add('active');
            
            // Update active tab button
            document.querySelectorAll('.tab-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
            // Update URL without reload
            const url = new URL(window.location);
            url.searchParams.set('tab', tabName);
            window.history.pushState({}, '', url);
        }

        // Check URL for tab parameter on load
        document.addEventListener('DOMContentLoaded', () => {
            const urlParams = new URLSearchParams(window.location.search);
            const tab = urlParams.get('tab');
            if (tab) {
                const tabBtn = document.querySelector(`.tab-btn[onclick="showTab('${tab}')"]`);
                if (tabBtn) {
                    tabBtn.click();
                }
            }
        });

        // Search functionality
        function searchUsers() {
            const input = document.querySelector('.search-box');
            const filter = input.value.toLowerCase();
            const rows = document.querySelectorAll('#usersTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            });
        }

        function searchProducts() {
            const input = document.querySelector('.search-box');
            const filter = input.value.toLowerCase();
            const rows = document.querySelectorAll('#productsTable tbody tr');
            
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(filter) ? '' : 'none';
            });
        }

        // User management functions
        function editUser(farmerId) {
            alert(`{{ t.edit }} {{ t.user }}: ${farmerId}`);
        }

        function deleteUser(farmerId) {
            if (confirm(`{{ t.confirm_delete }} ${farmerId}?`)) {
                alert(`{{ t.user }} ${farmerId} {{ t.would_be_deleted }}`);
            }
        }

        function viewDetails(farmerId) {
            alert(`{{ t.viewing_details }}: ${farmerId}`);
        }

        // Auto-refresh data every 30 seconds
        setInterval(() => {
            // In a real app, this would fetch updated data from the server
            console.log('Refreshing admin data...');
        }, 30000);

        // Session timeout warning
        let warningShown = false;
        setInterval(() => {
            // Show warning 2 minutes before timeout
            const warningTime = {{ ADMIN_SESSION_TIMEOUT }} - 120;
            const currentTime = Math.floor(Date.now() / 1000);
            const sessionStart = {{ session.get('admin_last_activity', 0) }};
            
            if (currentTime - sessionStart > warningTime && !warningShown) {
                warningShown = true;
                if (confirm('Your admin session will expire in 2 minutes. Do you want to extend it?')) {
                    // Refresh session by making a request
                    fetch('/admin', { method: 'HEAD' });
                    warningShown = false;
                }
            }
        }, 60000); // Check every minute
    </script>
</body>
</html>
"""
START_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agro-x | Smart Agriculture</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0c3b2e 0%, #1b5e20 100%);
            color: white;
            min-height: 100vh;
            overflow-x: hidden;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 0 20px;
        }

        .hero {
            min-height: 100vh;
            display: flex;
            align-items: center;
            position: relative;
            overflow: hidden;
        }

        .hero-bg {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: url('https://images.unsplash.com/photo-1500382017468-9049fed747ef?ixlib=rb-4.0.3&auto=format&fit=crop&w=2000&q=80') center/cover no-repeat;
            opacity: 0.2;
            z-index: -1;
        }

        .hero-content {
            width: 100%;
            max-width: 800px;
            margin: 0 auto;
            text-align: center;
            padding: 40px;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .logo {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 20px;
            color: #4caf50;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
        }

        .logo i {
            font-size: 56px;
        }

        .tagline {
            font-size: 20px;
            font-weight: 300;
            margin-bottom: 40px;
            line-height: 1.6;
            color: #e8f5e9;
        }

        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin: 40px 0;
        }

        .feature {
            background: rgba(255, 255, 255, 0.1);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
            transition: transform 0.3s ease;
        }

        .feature:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.15);
        }

        .feature i {
            font-size: 32px;
            color: #4caf50;
            margin-bottom: 15px;
        }

        .feature h3 {
            font-size: 18px;
            margin-bottom: 10px;
            color: #ffffff;
        }

        .feature p {
            font-size: 14px;
            color: #c8e6c9;
        }

        .cta-buttons {
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-top: 40px;
        }

        .btn {
            padding: 16px 40px;
            border-radius: 50px;
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 10px;
        }

        .btn-primary {
            background: #4caf50;
            color: white;
            border: 2px solid #4caf50;
        }

        .btn-primary:hover {
            background: transparent;
            color: #4caf50;
        }

        .btn-secondary {
            background: transparent;
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: white;
        }

        /* Language Selector */
        .language-selector {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 768px) {
            .hero-content {
                padding: 20px;
            }
            
            .logo {
                font-size: 36px;
            }
            
            .cta-buttons {
                flex-direction: column;
                align-items: center;
            }
            
            .btn {
                width: 100%;
                justify-content: center;
            }
            
            .language-selector {
                top: 10px;
                right: 10px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="hero">
        <div class="hero-bg"></div>
        
        <!-- Language Selector -->
        <div class="language-selector">
            <div class="lang-btn">
                <i class="fas fa-globe"></i>
                {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
                <i class="fas fa-chevron-down"></i>
            </div>
            <div class="lang-dropdown">
                <a href="/set_language/en" class="lang-option">English</a>
                <a href="/set_language/hi" class="lang-option">हिंदी</a>
                <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
            </div>
        </div>
        
        <div class="container">
            <div class="hero-content">
                <div class="logo">
                    <i class="fas fa-seedling"></i>
                    <span>Agro-x</span>
                </div>
                
                <div class="tagline">
                    <h2 style="font-size: 28px; margin-bottom: 20px; color: #4caf50;">{{ t.grow_smarter }}</h2>
                    <p>AI-powered autonomous farm monitoring and control system that stabilizes pH, nutrients, water quantity, and micro-climate for maximum yield with minimum effort.</p>
                </div>
                
                <div class="features">
                    <div class="feature">
                        <i class="fas fa-brain"></i>
                        <h3>{{ t.ai_powered }}</h3>
                        <p>Intelligent monitoring and automated control</p>
                    </div>
                    <div class="feature">
                        <i class="fas fa-tint"></i>
                        <h3>{{ t.smart_irrigation }}</h3>
                        <p>Optimal water usage with moisture sensors</p>
                    </div>
                    <div class="feature">
                        <i class="fas fa-chart-line"></i>
                        <h3>{{ t.real_time_analytics }}</h3>
                        <p>Live data visualization and insights</p>
                    </div>
                    <div class="feature">
                        <i class="fas fa-robot"></i>
                        <h3>{{ t.automated_control }}</h3>
                        <p>Hands-free farm management</p>
                    </div>
                </div>
                
                <div class="cta-buttons">
                    <a href="/login" class="btn btn-primary">
                        <i class="fas fa-sign-in-alt"></i>
                        {{ t.login }}
                    </a>
                    <a href="/register" class="btn btn-secondary">
                        <i class="fas fa-user-plus"></i>
                        {{ t.register }}
                    </a>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.login }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0c3b2e 0%, #1b5e20 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .login-container {
            width: 100%;
            max-width: 400px;
        }

        .login-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo-icon {
            font-size: 48px;
            color: #4caf50;
            margin-bottom: 10px;
        }

        .logo-text {
            font-size: 28px;
            font-weight: 700;
            color: #2e7d32;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }

        .form-input {
            width: 100%;
            padding: 14px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }

        .form-input:focus {
            outline: none;
            border-color: #4caf50;
            background: white;
            box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
        }

        .btn-login {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-top: 10px;
        }

        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }

        .error-message {
            background: #ffebee;
            color: #c62828;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: {% if error %}block{% else %}none{% endif %};
        }

        .links {
            text-align: center;
            margin-top: 25px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }

        .links a {
            color: #4caf50;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.3s ease;
        }

        .links a:hover {
            color: #2e7d32;
            text-decoration: underline;
        }

        .theme-toggle {
            position: absolute;
            top: 20px;
            right: 20px;
            background: rgba(255, 255, 255, 0.2);
            border: none;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 18px;
            transition: all 0.3s ease;
        }

        .theme-toggle:hover {
            background: rgba(255, 255, 255, 0.3);
        }

        body.dark-theme {
            background: linear-gradient(135deg, #0a291f 0%, #123814 100%);
        }

        body.dark-theme .login-card {
            background: rgba(30, 30, 30, 0.95);
            border-color: rgba(255, 255, 255, 0.1);
        }

        body.dark-theme .form-label {
            color: #e0e0e0;
        }

        body.dark-theme .form-input {
            background: rgba(255, 255, 255, 0.1);
            border-color: rgba(255, 255, 255, 0.2);
            color: white;
        }

        body.dark-theme .form-input:focus {
            border-color: #4caf50;
            background: rgba(255, 255, 255, 0.15);
        }

        body.dark-theme .links a {
            color: #81c784;
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <button class="theme-toggle" onclick="toggleTheme()">
        <i class="fas fa-moon"></i>
    </button>

    <div class="login-container">
        <div class="login-card">
            <div class="logo">
                <div class="logo-icon">
                    <i class="fas fa-seedling"></i>
                </div>
                <div class="logo-text">Agro-x</div>
            </div>

            {% if error %}
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i> {{ error }}
            </div>
            {% endif %}

            <form method="post">
                <div class="form-group">
                    <label class="form-label">{{ t.mobile }} {{ t.or }} {{ t.farmer_id }}</label>
                    <input type="text" name="mobile" class="form-input" placeholder="{{ t.enter_mobile }} {{ t.or }} {{ t.farmer_id }}" required>
                </div>

                <div class="form-group">
                    <label class="form-label">{{ t.password }}</label>
                    <input type="password" name="password" class="form-input" placeholder="{{ t.enter_password }}" required>
                </div>

                <button type="submit" class="btn-login">
                    <i class="fas fa-sign-in-alt"></i>
                    {{ t.login }} {{ t.to }} {{ t.dashboard }}
                </button>
            </form>

            <div class="links">
                <p>{{ t.already_have_account }} <a href="/register">{{ t.create_account }}</a></p>
                <p><a href="/">{{ t.back_to_home }}</a></p>
            </div>
        </div>
    </div>

    <script>
        function toggleTheme() {
            document.body.classList.toggle('dark-theme');
            const icon = document.querySelector('.theme-toggle i');
            if (document.body.classList.contains('dark-theme')) {
                icon.className = 'fas fa-sun';
                localStorage.setItem('theme', 'dark');
            } else {
                icon.className = 'fas fa-moon';
                localStorage.setItem('theme', 'light');
            }
        }

        // Load saved theme
        window.addEventListener('DOMContentLoaded', () => {
            const savedTheme = localStorage.getItem('theme');
            if (savedTheme === 'dark') {
                document.body.classList.add('dark-theme');
                document.querySelector('.theme-toggle i').className = 'fas fa-sun';
            }
        });
    </script>
</body>
</html>
"""

REGISTER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.register }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0c3b2e 0%, #1b5e20 100%);
            min-height: 100vh;
            padding: 40px 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .register-container {
            width: 100%;
            max-width: 500px;
        }

        .register-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.3);
        }

        .logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .logo-icon {
            font-size: 48px;
            color: #4caf50;
            margin-bottom: 10px;
        }

        .logo-text {
            font-size: 28px;
            font-weight: 700;
            color: #2e7d32;
            margin-bottom: 5px;
        }

        .logo-subtitle {
            color: #666;
            font-size: 14px;
        }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 20px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group.full-width {
            grid-column: 1 / -1;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 500;
            font-size: 14px;
        }

        .form-label i {
            color: #4caf50;
            margin-right: 8px;
        }

        .form-input {
            width: 100%;
            padding: 14px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
            background: #f8f9fa;
        }

        .form-input:focus {
            outline: none;
            border-color: #4caf50;
            background: white;
            box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
        }

        .btn-register {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #4caf50 0%, #2e7d32 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-top: 10px;
        }

        .btn-register:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }

        .error-message {
            background: #ffebee;
            color: #c62828;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: {% if error %}block{% else %}none{% endif %};
        }

        .success-message {
            background: #e8f5e9;
            color: #2e7d32;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: {% if success %}block{% else %}none{% endif %};
        }

        .links {
            text-align: center;
            margin-top: 25px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }

        .links a {
            color: #4caf50;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.3s ease;
        }

        .links a:hover {
            color: #2e7d32;
            text-decoration: underline;
        }

        @media (max-width: 600px) {
            .form-grid {
                grid-template-columns: 1fr;
            }
            
            .register-card {
                padding: 30px 20px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="register-container">
        <div class="register-card">
            <div class="logo">
                <div class="logo-icon">
                    <i class="fas fa-seedling"></i>
                </div>
                <div class="logo-text">{{ t.farmer_registration }}</div>
                <div class="logo-subtitle">{{ t.join_revolution }}</div>
            </div>

            {% if error %}
            <div class="error-message">
                <i class="fas fa-exclamation-circle"></i> {{ error }}
            </div>
            {% endif %}
            
            {% if success %}
            <div class="success-message">
                <i class="fas fa-check-circle"></i> {{ success }}
            </div>
            {% endif %}

            <form method="post">
                <div class="form-grid">
                    <div class="form-group">
                        <label class="form-label">
                            <i class="fas fa-user"></i> {{ t.full_name }}
                        </label>
                        <input type="text" name="name" class="form-input" placeholder="{{ t.enter_full_name }}" required>
                    </div>

                    <div class="form-group">
                        <label class="form-label">
                            <i class="fas fa-phone"></i> {{ t.mobile_number }}
                        </label>
                        <input type="tel" name="mobile" class="form-input" placeholder="{{ t.enter_mobile }}" required>
                    </div>

                    <div class="form-group full-width">
                        <label class="form-label">
                            <i class="fas fa-envelope"></i> {{ t.email_address }}
                        </label>
                        <input type="email" name="email" class="form-input" placeholder="{{ t.enter_email }}" required>
                    </div>

                    <div class="form-group">
                        <label class="form-label">
                            <i class="fas fa-lock"></i> {{ t.password }}
                        </label>
                        <input type="password" name="password" class="form-input" placeholder="{{ t.create_password }}" required>
                    </div>

                    <div class="form-group">
                        <label class="form-label">
                            <i class="fas fa-map-marker-alt"></i> {{ t.farm_location }}
                        </label>
                        <input type="text" name="farm_location" class="form-input" placeholder="{{ t.village_district }}" required>
                    </div>

                    <div class="form-group">
                        <label class="form-label">
                            <i class="fas fa-ruler-combined"></i> {{ t.farm_size }}
                        </label>
                        <input type="text" name="farm_size" class="form-input" placeholder="{{ t.in_acres }}" required>
                    </div>

                    <div class="form-group full-width">
                        <label class="form-label">
                            <i class="fas fa-leaf"></i> {{ t.crop_type }}
                        </label>
                        <input type="text" name="crop_type" class="form-input" placeholder="{{ t.enter_crop_type }}" required>
                    </div>
                </div>

                <button type="submit" class="btn-register">
                    <i class="fas fa-user-plus"></i>
                    {{ t.create_farmer_account }}
                </button>
            </form>

            <div class="links">
                <p>{{ t.already_have_account }} <a href="/login">{{ t.login_here }}</a></p>
                <p><a href="/">{{ t.back_to_home }}</a></p>
            </div>
        </div>
    </div>
</body>
</html>
"""
WEATHER_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.weather }} {{ t.details }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0c3b2e 0%, #1b5e20 100%);
            color: white;
            min-height: 100vh;
        }

        .navbar {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .nav-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: white;
            font-weight: 600;
            font-size: 20px;
        }

        .back-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .back-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        .weather-hero {
            text-align: center;
            margin-bottom: 40px;
        }

        .weather-hero h1 {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 10px;
        }

        .weather-hero p {
            font-size: 18px;
            opacity: 0.9;
        }

        .weather-main {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            padding: 40px;
            margin-bottom: 40px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .current-weather {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 40px;
        }

        .temp-display {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .temp-icon {
            font-size: 80px;
        }

        .temp-value {
            font-size: 72px;
            font-weight: 700;
        }

        .temp-details {
            font-size: 18px;
            opacity: 0.9;
        }

        .weather-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
        }

        .weather-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 25px;
            display: flex;
            align-items: center;
            gap: 20px;
            transition: transform 0.3s ease;
        }

        .weather-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.1);
        }

        .card-icon {
            font-size: 32px;
            width: 60px;
            height: 60px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .card-content {
            flex: 1;
        }

        .card-value {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .card-label {
            font-size: 14px;
            opacity: 0.8;
        }

        .sun-times {
            display: flex;
            gap: 40px;
            margin-top: 30px;
            padding-top: 30px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
        }

        .sun-time {
            text-align: center;
        }

        .sun-icon {
            font-size: 32px;
            margin-bottom: 10px;
        }

        .sun-value {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .sun-label {
            font-size: 14px;
            opacity: 0.8;
        }
        
        /* Language Selector */
        .language-selector {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 768px) {
            .current-weather {
                flex-direction: column;
                text-align: center;
                gap: 20px;
            }
            
            .weather-grid {
                grid-template-columns: 1fr;
            }
            
            .weather-hero h1 {
                font-size: 36px;
            }
            
            .temp-value {
                font-size: 48px;
            }
            
            .language-selector {
                top: 10px;
                right: 10px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Language Selector -->
    <div class="language-selector">
        <div class="lang-btn">
            <i class="fas fa-globe"></i>
            {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
            <i class="fas fa-chevron-down"></i>
        </div>
        <div class="lang-dropdown">
            <a href="/set_language/en" class="lang-option">English</a>
            <a href="/set_language/hi" class="lang-option">हिंदी</a>
            <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
        </div>
    </div>
    
    <nav class="navbar">
        <div class="nav-container">
            <a href="/dashboard" class="nav-logo">
                <i class="fas fa-seedling"></i>
                Agro-x {{ t.weather }}
            </a>
            <a href="/dashboard" class="back-btn">
                <i class="fas fa-arrow-left"></i>
                {{ t.back_to_dashboard }}
            </a>
        </div>
    </nav>

    <div class="container">
        <div class="weather-hero">
            <h1>{{ t.weather_intelligence }}</h1>
            <p>{{ t.real_time_weather }}</p>
        </div>

        <div class="weather-main">
            <div class="current-weather">
                <div class="temp-display">
                    <div class="temp-icon">
                        {% if weather.temp > 30 %}
                        <i class="fas fa-sun"></i>
                        {% elif weather.temp > 20 %}
                        <i class="fas fa-cloud-sun"></i>
                        {% else %}
                        <i class="fas fa-cloud"></i>
                        {% endif %}
                    </div>
                    <div>
                        <div class="temp-value">{{ weather.temp }}°C</div>
                        <div class="temp-details">{{ weather.description|capitalize }}</div>
                    </div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 24px; font-weight: 600; margin-bottom: 10px;">{{ weather.weather }}</div>
                    <div style="opacity: 0.9;">{{ t.feels_like }} {{ weather.feels_like }}°C</div>
                </div>
            </div>

            <div class="weather-grid">
                <div class="weather-card">
                    <div class="card-icon">
                        <i class="fas fa-tint"></i>
                    </div>
                    <div class="card-content">
                        <div class="card-value">{{ weather.humidity }}%</div>
                        <div class="card-label">{{ t.humidity }}</div>
                    </div>
                </div>

                <div class="weather-card">
                    <div class="card-icon">
                        <i class="fas fa-wind"></i>
                    </div>
                    <div class="card-content">
                        <div class="card-value">{{ weather.wind_speed }} km/h</div>
                        <div class="card-label">{{ t.wind_speed }}</div>
                    </div>
                </div>

                <div class="weather-card">
                    <div class="card-icon">
                        <i class="fas fa-weight-hanging"></i>
                    </div>
                    <div class="card-content">
                        <div class="card-value">{{ weather.pressure }} mb</div>
                        <div class="card-label">{{ t.pressure }}</div>
                    </div>
                </div>

                <div class="weather-card">
                    <div class="card-icon">
                        <i class="fas fa-thermometer-half"></i>
                    </div>
                    <div class="card-content">
                        <div class="card-value">{{ weather.feels_like }}°C</div>
                        <div class="card-label">{{ t.feels_like }}</div>
                    </div>
                </div>
            </div>

            <div class="sun-times">
                <div class="sun-time">
                    <div class="sun-icon">
                        <i class="fas fa-sunrise"></i>
                    </div>
                    <div class="sun-value">{{ weather.sunrise }}</div>
                    <div class="sun-label">{{ t.sunrise }}</div>
                </div>

                <div class="sun-time">
                    <div class="sun-icon">
                        <i class="fas fa-sunset"></i>
                    </div>
                    <div class="sun-value">{{ weather.sunset }}</div>
                    <div class="sun-label">{{ t.sunset }}</div>
                </div>
            </div>
        </div>

        <div style="text-align: center; margin-top: 40px; opacity: 0.8;">
            <p><i class="fas fa-info-circle"></i> {{ t.weather_updates }}</p>
        </div>
    </div>
</body>
</html>
"""

CONTROL_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.control_panel }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0a1929 0%, #001e3c 100%);
            color: white;
            min-height: 100vh;
        }

        .navbar {
            background: rgba(0, 30, 60, 0.8);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .nav-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: white;
            font-weight: 600;
            font-size: 20px;
        }

        .back-btn {
            background: rgba(76, 175, 80, 0.2);
            border: 1px solid rgba(76, 175, 80, 0.3);
            color: #4caf50;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .back-btn:hover {
            background: rgba(76, 175, 80, 0.3);
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        .header {
            text-align: center;
            margin-bottom: 40px;
        }

        .header h1 {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #4caf50, #2196f3);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .header p {
            font-size: 18px;
            opacity: 0.9;
            max-width: 600px;
            margin: 0 auto;
        }

        .control-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
            margin-bottom: 40px;
        }

        .control-group {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .group-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 25px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .group-title i {
            color: #4caf50;
        }

        .control-items {
            display: flex;
            flex-direction: column;
            gap: 15px;
        }

        .control-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            transition: all 0.3s ease;
        }

        .control-item:hover {
            background: rgba(255, 255, 255, 0.1);
            transform: translateX(5px);
        }

        .control-info {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .control-name {
            font-weight: 500;
            font-size: 16px;
        }

        .control-desc {
            font-size: 13px;
            opacity: 0.7;
        }

        .toggle-switch {
            position: relative;
            width: 60px;
            height: 30px;
        }

        .toggle-checkbox {
            opacity: 0;
            width: 0;
            height: 0;
        }

        .toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #666;
            transition: .4s;
            border-radius: 34px;
        }

        .toggle-slider:before {
            position: absolute;
            content: "";
            height: 22px;
            width: 22px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }

        .toggle-checkbox:checked + .toggle-slider {
            background-color: #4caf50;
        }

        .toggle-checkbox:checked + .toggle-slider:before {
            transform: translateX(30px);
        }

        .emergency-section {
            background: linear-gradient(135deg, rgba(244, 67, 54, 0.1), rgba(244, 67, 54, 0.2));
            border: 2px solid rgba(244, 67, 54, 0.3);
            border-radius: 20px;
            padding: 40px;
            text-align: center;
            margin-top: 40px;
        }

        .emergency-title {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 20px;
            color: #ff6b6b;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
        }

        .emergency-btn {
            background: linear-gradient(135deg, #f44336, #d32f2f);
            color: white;
            border: none;
            padding: 20px 50px;
            font-size: 18px;
            font-weight: 600;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 15px;
            margin: 0 auto;
        }

        .emergency-btn:hover {
            transform: translateY(-3px);
            box-shadow: 0 10px 30px rgba(244, 67, 54, 0.3);
        }

        .status-panel {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 20px;
            padding: 30px;
            margin-top: 40px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .status-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-content {
            font-size: 16px;
            opacity: 0.9;
            line-height: 1.6;
        }

        .status-indicator {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 8px 16px;
            background: rgba(76, 175, 80, 0.2);
            border-radius: 20px;
            font-size: 14px;
            font-weight: 500;
        }

        .status-indicator::before {
            content: "";
            width: 8px;
            height: 8px;
            background: #4caf50;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        /* Language Selector */
        .language-selector {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 768px) {
            .control-grid {
                grid-template-columns: 1fr;
            }
            
            .header h1 {
                font-size: 36px;
            }
            
            .emergency-section {
                padding: 30px 20px;
            }
            
            .language-selector {
                top: 10px;
                right: 10px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Language Selector -->
    <div class="language-selector">
        <div class="lang-btn">
            <i class="fas fa-globe"></i>
            {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
            <i class="fas fa-chevron-down"></i>
        </div>
        <div class="lang-dropdown">
            <a href="/set_language/en" class="lang-option">English</a>
            <a href="/set_language/hi" class="lang-option">हिंदी</a>
            <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
        </div>
    </div>
    
    <nav class="navbar">
        <div class="nav-container">
            <a href="/dashboard" class="nav-logo">
                <i class="fas fa-seedling"></i>
                Agro-x {{ t.control_panel }}
            </a>
            <a href="/dashboard" class="back-btn">
                <i class="fas fa-arrow-left"></i>
                {{ t.back_to_dashboard }}
            </a>
        </div>
    </nav>

    <div class="container">
        <div class="header">
            <h1>{{ t.smart_control_panel }}</h1>
            <p>{{ t.manage_farm }}</p>
        </div>

        <div class="control-grid">
            <div class="control-group">
                <div class="group-title">
                    <i class="fas fa-flask"></i>
                    {{ t.nutrient_management }}
                </div>
                <div class="control-items">
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">Nitrogen (N) Injection</div>
                            <div class="control-desc">Controls nitrogen levels in irrigation</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('N')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">Phosphorus (P) Injection</div>
                            <div class="control-desc">Controls phosphorus levels in irrigation</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('P')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">Potassium (K) Injection</div>
                            <div class="control-desc">Controls potassium levels in irrigation</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('K')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                </div>
            </div>

            <div class="control-group">
                <div class="group-title">
                    <i class="fas fa-tint"></i>
                    {{ t.water_management }}
                </div>
                <div class="control-items">
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">Water Supply</div>
                            <div class="control-desc">Main irrigation system control</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('Water Supply')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">pH Adjustment (+)</div>
                            <div class="control-desc">Increase pH level in water</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('pH +')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">pH Adjustment (-)</div>
                            <div class="control-desc">Decrease pH level in water</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('pH -')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                </div>
            </div>

            <div class="control-group">
                <div class="group-title">
                    <i class="fas fa-thermometer-half"></i>
                    {{ t.climate_control }}
                </div>
                <div class="control-items">
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">Heating System</div>
                            <div class="control-desc">Greenhouse temperature control</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('Heating')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">Cooling System</div>
                            <div class="control-desc">Temperature regulation</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('Cooling')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                    <div class="control-item">
                        <div class="control-info">
                            <div class="control-name">Mixture Control</div>
                            <div class="control-desc">Automated nutrient mixing</div>
                        </div>
                        <label class="toggle-switch">
                            <input type="checkbox" class="toggle-checkbox" onclick="toggleControl('Mixture')">
                            <span class="toggle-slider"></span>
                        </label>
                    </div>
                </div>
            </div>
        </div>

        <div class="emergency-section">
            <div class="emergency-title">
                <i class="fas fa-exclamation-triangle"></i>
                {{ t.emergency_controls }}
            </div>
            <p style="margin-bottom: 30px; opacity: 0.9; max-width: 600px; margin-left: auto; margin-right: auto;">
                Use this only in case of emergency. This will immediately shut down all systems and activate safety protocols.
            </p>
            <button class="emergency-btn" onclick="emergencyShutdown()">
                <i class="fas fa-power-off"></i>
                Emergency Shutdown
            </button>
        </div>

        <div class="status-panel">
            <div class="status-title">
                <i class="fas fa-info-circle"></i>
                {{ t.system_status }}
            </div>
            <div class="status-content">
                <div class="status-indicator">{{ t.system_ready }}</div>
                <p style="margin-top: 20px;">All systems are operational and ready for commands. Use the toggle switches above to control individual components. The emergency shutdown button will immediately halt all operations.</p>
            </div>
        </div>
    </div>

    <script>
        function toggleControl(name) {
            const checkbox = event.target;
            const state = checkbox.checked ? 'ON' : 'OFF';
            
            const statusElement = document.querySelector('.status-indicator');
            statusElement.innerHTML = `
                <span></span>
                ${name} turned <strong>${state}</strong>
            `;
            
            // Add visual feedback
            statusElement.style.background = state === 'ON' 
                ? 'rgba(76, 175, 80, 0.2)' 
                : 'rgba(33, 150, 243, 0.2)';
            statusElement.querySelector('span').style.background = state === 'ON' 
                ? '#4caf50' 
                : '#2196f3';
            
            // Log to console (in real app, this would be an API call)
            console.log(`${name} turned ${state}`);
        }

        function emergencyShutdown() {
            if (confirm('⚠️ ARE YOU SURE?\n\nThis will immediately shut down ALL systems including:\n• Irrigation systems\n• Nutrient injection\n• Climate control\n• All automated processes\n\nThis action cannot be undone automatically.')) {
                const statusElement = document.querySelector('.status-indicator');
                statusElement.innerHTML = `
                    <span style="background: #f44336;"></span>
                    EMERGENCY SHUTDOWN ACTIVATED
                `;
                statusElement.style.background = 'rgba(244, 67, 54, 0.2)';
                
                // Turn off all switches
                document.querySelectorAll('.toggle-checkbox').forEach(checkbox => {
                    checkbox.checked = false;
                });
                
                alert('✅ Emergency shutdown activated. All systems have been safely powered down.');
            }
        }

        // Auto Mode functionality
        document.addEventListener('DOMContentLoaded', () => {
            // Simulate auto mode by toggling random switches every 30 seconds
            setInterval(() => {
                const switches = document.querySelectorAll('.toggle-checkbox');
                const randomSwitch = switches[Math.floor(Math.random() * switches.length)];
                if (Math.random() > 0.7) { // 30% chance to toggle
                    randomSwitch.checked = !randomSwitch.checked;
                    randomSwitch.dispatchEvent(new Event('change'));
                }
            }, 30000);
        });
    </script>
</body>
</html>
"""
ADMIN_LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.admin }} {{ t.login }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #1a237e 0%, #311b92 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .admin-login-container {
            width: 100%;
            max-width: 400px;
        }

        .admin-login-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .admin-logo {
            text-align: center;
            margin-bottom: 30px;
        }

        .admin-logo-icon {
            font-size: 48px;
            color: #ff6b6b;
            margin-bottom: 10px;
        }

        .admin-logo-text {
            font-size: 28px;
            font-weight: 700;
            color: white;
        }

        .admin-logo-subtext {
            color: rgba(255, 255, 255, 0.7);
            font-size: 14px;
            margin-top: 5px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            color: rgba(255, 255, 255, 0.9);
            font-weight: 500;
            font-size: 14px;
        }

        .form-input {
            width: 100%;
            padding: 14px;
            background: rgba(255, 255, 255, 0.1);
            border: 2px solid rgba(255, 255, 255, 0.2);
            border-radius: 10px;
            font-size: 16px;
            color: white;
            transition: all 0.3s ease;
        }

        .form-input:focus {
            outline: none;
            border-color: #ff6b6b;
            background: rgba(255, 255, 255, 0.15);
            box-shadow: 0 0 0 3px rgba(255, 107, 107, 0.1);
        }

        .btn-admin-login {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, #ff6b6b, #ff4757);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-top: 10px;
        }

        .btn-admin-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(255, 107, 107, 0.3);
        }

        .error-message {
            background: rgba(244, 67, 54, 0.2);
            color: #ffcdd2;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
            display: {% if error %}block{% else %}none{% endif %};
            border-left: 4px solid #f44336;
        }

        .security-note {
            margin-top: 25px;
            padding-top: 20px;
            border-top: 1px solid rgba(255, 255, 255, 0.1);
            text-align: center;
            color: rgba(255, 255, 255, 0.7);
            font-size: 12px;
        }

        .back-link {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            color: rgba(255, 255, 255, 0.7);
            text-decoration: none;
            margin-top: 15px;
            transition: color 0.3s ease;
        }

        .back-link:hover {
            color: white;
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <div class="admin-login-container">
        <div class="admin-login-card">
            <div class="admin-logo">
                <div class="admin-logo-icon">
                    <i class="fas fa-shield-alt"></i>
                </div>
                <div class="admin-logo-text">Admin Access</div>
                <div class="admin-logo-subtext">Restricted Area - Authorized Personnel Only</div>
            </div>

            {% if error %}
            <div class="error-message">
                <i class="fas fa-exclamation-triangle"></i> {{ error }}
            </div>
            {% endif %}

            <form method="post">
                <div class="form-group">
                    <label class="form-label">
                        <i class="fas fa-key"></i> {{ t.admin_password }}
                    </label>
                    <input type="password" name="admin_password" class="form-input" 
                           placeholder="{{ t.enter_admin_password }}" required autocomplete="off">
                </div>

                <button type="submit" class="btn-admin-login">
                    <i class="fas fa-unlock"></i>
                    Access Admin Panel
                </button>
            </form>

            <div class="security-note">
                <p><i class="fas fa-info-circle"></i> All access attempts are logged and monitored</p>
                <a href="/dashboard" class="back-link">
                    <i class="fas fa-arrow-left"></i>
                    {{ t.back_to_dashboard }}
                </a>
            </div>
        </div>
    </div>
</body>
</html>
"""
SHOP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.shop }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #ff9900;
            --primary-dark: #ff8c00;
            --secondary: #146eb4;
            --dark: #0f1111;
            --light: #f8f9fa;
            --gray: #6c757d;
            --border: #ddd;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: #f5f7fa;
            color: var(--dark);
            min-height: 100vh;
        }

        /* Amazon-like Header */
        .amazon-header {
            background: var(--dark);
            padding: 10px 0;
            border-bottom: 1px solid #3a4553;
        }

        .header-container {
            max-width: 1500px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .amazon-logo {
            display: flex;
            align-items: center;
            text-decoration: none;
            color: white;
        }

        .amazon-logo i {
            font-size: 32px;
            color: var(--primary);
        }

        .amazon-logo-text {
            font-size: 24px;
            font-weight: 700;
            color: white;
            margin-left: 10px;
        }

        .amazon-logo-text span {
            color: var(--primary);
        }

        .search-container {
            flex: 1;
            max-width: 800px;
        }

        .search-form {
            display: flex;
        }

        .search-select {
            background: #f3f3f3;
            border: 1px solid #cdcdcd;
            border-right: none;
            border-radius: 4px 0 0 4px;
            padding: 12px;
            font-size: 14px;
            color: #555;
        }

        .search-input {
            flex: 1;
            padding: 12px;
            border: 1px solid #cdcdcd;
            font-size: 14px;
        }

        .search-button {
            background: var(--primary);
            border: none;
            border-radius: 0 4px 4px 0;
            padding: 12px 20px;
            color: var(--dark);
            cursor: pointer;
            font-size: 16px;
        }

        .header-right {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .header-item {
            display: flex;
            flex-direction: column;
            color: white;
            text-decoration: none;
        }

        .header-line1 {
            font-size: 12px;
            opacity: 0.9;
        }

        .header-line2 {
            font-size: 14px;
            font-weight: 600;
        }

        .cart-icon {
            position: relative;
            text-decoration: none;
            color: white;
        }

        .cart-count {
            position: absolute;
            top: -8px;
            right: -8px;
            background: var(--primary);
            color: var(--dark);
            font-size: 12px;
            font-weight: 600;
            width: 20px;
            height: 20px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        /* Sub Header */
        .sub-header {
            background: #232f3e;
            padding: 10px 0;
        }

        .sub-nav {
            max-width: 1500px;
            margin: 0 auto;
            padding: 0 20px;
            display: flex;
            gap: 25px;
        }

        .sub-nav-link {
            color: white;
            text-decoration: none;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 5px 10px;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .sub-nav-link:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        /* Main Container */
        .container {
            max-width: 1500px;
            margin: 0 auto;
            padding: 20px;
        }

        /* Hero Banner */
        .hero-banner {
            margin-bottom: 20px;
            border-radius: 8px;
            overflow: hidden;
        }

        .hero-slider {
            position: relative;
            width: 100%;
            height: 300px;
            background: linear-gradient(to right, #146eb4, #0f1111);
            color: white;
            padding: 40px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .hero-content h1 {
            font-size: 36px;
            margin-bottom: 10px;
        }

        .hero-content p {
            font-size: 18px;
            margin-bottom: 20px;
            opacity: 0.9;
        }

        .shop-now-btn {
            background: var(--primary);
            color: var(--dark);
            padding: 12px 30px;
            border-radius: 4px;
            text-decoration: none;
            font-weight: 600;
            display: inline-block;
            transition: background 0.3s ease;
        }

        .shop-now-btn:hover {
            background: var(--primary-dark);
        }

        /* Product Grid */
        .products-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }

        .product-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            position: relative;
            border: 1px solid var(--border);
        }

        .product-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }

        .product-image {
            width: 100%;
            height: 200px;
            object-fit: contain;
            margin-bottom: 15px;
        }

        .product-title {
            font-size: 16px;
            font-weight: 500;
            margin-bottom: 10px;
            height: 40px;
            overflow: hidden;
            color: #0f1111;
        }

        .product-rating {
            display: flex;
            align-items: center;
            gap: 5px;
            margin-bottom: 10px;
        }

        .stars {
            color: var(--primary);
        }

        .rating-count {
            color: #007185;
            font-size: 14px;
        }

        .product-price {
            font-size: 24px;
            font-weight: 700;
            color: #b12704;
            margin-bottom: 10px;
        }

        .prime-badge {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            color: #007185;
            font-size: 14px;
            margin-bottom: 10px;
        }

        .product-actions {
            display: flex;
            gap: 10px;
        }

        .btn-add-to-cart {
            flex: 1;
            background: #ffd814;
            border: none;
            border-radius: 20px;
            padding: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
        }

        .btn-add-to-cart:hover {
            background: #f7ca00;
        }

        .btn-buy-now {
            background: #ffa41c;
            border: none;
            border-radius: 20px;
            padding: 10px 20px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            font-size: 14px;
        }

        .btn-buy-now:hover {
            background: #ff8c00;
        }

        /* Categories */
        .categories-section {
            margin-bottom: 40px;
        }

        .categories-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            color: var(--dark);
        }

        .categories-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 20px;
        }

        .category-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            text-align: center;
            text-decoration: none;
            color: var(--dark);
            border: 1px solid var(--border);
            transition: all 0.3s ease;
        }

        .category-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }

        .category-icon {
            font-size: 32px;
            color: var(--primary);
            margin-bottom: 10px;
        }

        .category-name {
            font-weight: 500;
            font-size: 16px;
        }

        /* Featured Products */
        .featured-section {
            margin-bottom: 40px;
        }

        .section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }

        .section-title {
            font-size: 24px;
            font-weight: 600;
            color: var(--dark);
        }

        .see-all {
            color: #007185;
            text-decoration: none;
            font-size: 14px;
        }

        .see-all:hover {
            text-decoration: underline;
        }

        /* Footer */
        .amazon-footer {
            background: var(--dark);
            color: white;
            padding: 40px 0;
            margin-top: 40px;
        }

        .footer-container {
            max-width: 1500px;
            margin: 0 auto;
            padding: 0 20px;
        }

        .footer-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 40px;
            margin-bottom: 40px;
        }

        .footer-column h3 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 15px;
            color: white;
        }

        .footer-column ul {
            list-style: none;
        }

        .footer-column li {
            margin-bottom: 10px;
        }

        .footer-column a {
            color: #ddd;
            text-decoration: none;
            font-size: 14px;
        }

        .footer-column a:hover {
            text-decoration: underline;
        }

        .footer-bottom {
            text-align: center;
            padding-top: 20px;
            border-top: 1px solid #3a4553;
            color: #ddd;
            font-size: 12px;
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Amazon-like Header -->
    <header class="amazon-header">
        <div class="header-container">
            <a href="/dashboard" class="amazon-logo">
                <i class="fas fa-seedling"></i>
                <span class="amazon-logo-text">Agro<span>-x</span></span>
            </a>
            
            <div class="search-container">
                <form class="search-form" onsubmit="searchProducts(event)">
                    <select class="search-select">
                        <option>All Departments</option>
                        <option>Sensors</option>
                        <option>Irrigation</option>
                        <option>Nutrients</option>
                        <option>Complete Systems</option>
                    </select>
                    <input type="text" class="search-input" placeholder="Search for products...">
                    <button type="submit" class="search-button">
                        <i class="fas fa-search"></i>
                    </button>
                </form>
            </div>
            
            <div class="header-right">
                <a href="/dashboard" class="header-item">
                    <span class="header-line1">Hello</span>
                    <span class="header-line2">Dashboard</span>
                </a>
                
                <a href="/cart" class="header-item cart-icon">
                    <span style="font-size: 24px; position: relative;">
                        <i class="fas fa-shopping-cart"></i>
                        <span class="cart-count">0</span>
                    </span>
                    <span class="header-line2">Cart</span>
                </a>
            </div>
        </div>
    </header>
    
    <!-- Sub Header -->
    <nav class="sub-header">
        <div class="sub-nav">
            <a href="#" class="sub-nav-link">
                <i class="fas fa-bars"></i>
                All
            </a>
            <a href="#" class="sub-nav-link">
                <i class="fas fa-bolt"></i>
                Today's Deals
            </a>
            <a href="#" class="sub-nav-link">
                <i class="fas fa-truck"></i>
                Fast Delivery
            </a>
            <a href="#" class="sub-nav-link">
                <i class="fas fa-leaf"></i>
                Prime
            </a>
            <a href="#" class="sub-nav-link">
                <i class="fas fa-shopping-cart"></i>
                Sell
            </a>
        </div>
    </nav>

    <div class="container">
        <!-- Hero Banner -->
        <div class="hero-banner">
            <div class="hero-slider">
                <div class="hero-content">
                    <h1>Smart Farming Revolution</h1>
                    <p>Get premium agricultural equipment with Prime delivery</p>
                    <a href="#featured" class="shop-now-btn">Shop now</a>
                </div>
                <div style="font-size: 120px; color: rgba(255, 255, 255, 0.2);">
                    <i class="fas fa-tractor"></i>
                </div>
            </div>
        </div>

        <!-- Categories -->
        <div class="categories-section">
            <h2 class="categories-title">Shop by Category</h2>
            <div class="categories-grid">
                <a href="#sensors" class="category-card">
                    <div class="category-icon">
                        <i class="fas fa-microchip"></i>
                    </div>
                    <div class="category-name">Sensors</div>
                </a>
                <a href="#irrigation" class="category-card">
                    <div class="category-icon">
                        <i class="fas fa-tint"></i>
                    </div>
                    <div class="category-name">Irrigation</div>
                </a>
                <a href="#nutrients" class="category-card">
                    <div class="category-icon">
                        <i class="fas fa-flask"></i>
                    </div>
                    <div class="category-name">Nutrients</div>
                </a>
                <a href="#systems" class="category-card">
                    <div class="category-icon">
                        <i class="fas fa-robot"></i>
                    </div>
                    <div class="category-name">Complete Systems</div>
                </a>
            </div>
        </div>

        <!-- Featured Products -->
        <div class="featured-section" id="featured">
            <div class="section-header">
                <h2 class="section-title">Recommended for You</h2>
                <a href="#" class="see-all">See all</a>
            </div>
            
            <div class="products-grid">
                {% for pid, p in products.items() %}
                <div class="product-card">
                    <img src="{{ p.images[0] }}" alt="{{ p.name }}" class="product-image">
                    
                    <h3 class="product-title">{{ p.name }}</h3>
                    
                    <div class="product-rating">
                        <div class="stars">
                            {% for i in range(4) %}
                            <i class="fas fa-star"></i>
                            {% endfor %}
                            <i class="fas fa-star-half-alt"></i>
                        </div>
                        <span class="rating-count">{{ range(100, 501)|random }}</span>
                    </div>
                    
                    <div class="product-price">₹ {{ "{:,}".format(p.price) }}</div>
                    
                    <div class="prime-badge">
                        <i class="fas fa-shipping-fast"></i>
                        <span>FREE delivery</span>
                    </div>
                    
                    <div class="product-actions">
                        <button class="btn-add-to-cart" onclick="addToCart('{{ pid }}')">
                            <i class="fas fa-cart-plus"></i>
                            Add to Cart
                        </button>
                        <button class="btn-buy-now" onclick="buyNow('{{ pid }}')">
                            Buy Now
                        </button>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <!-- More Sections -->
        <div class="featured-section">
            <div class="section-header">
                <h2 class="section-title">Best Sellers in Farming</h2>
                <a href="#" class="see-all">See all</a>
            </div>
            
            <div class="products-grid">
                {% for pid, p in products.items() if p.price < 1000 %}
                <div class="product-card">
                    <img src="{{ p.images[0] }}" alt="{{ p.name }}" class="product-image">
                    
                    <h3 class="product-title">{{ p.name }}</h3>
                    
                    <div class="product-rating">
                        <div class="stars">
                            {% for i in range(5) %}
                            <i class="fas fa-star"></i>
                            {% endfor %}
                        </div>
                        <span class="rating-count">{{ range(50, 201)|random }}</span>
                    </div>
                    
                    <div class="product-price">₹ {{ "{:,}".format(p.price) }}</div>
                    
                    <div class="prime-badge">
                        <i class="fas fa-shipping-fast"></i>
                        <span>FREE delivery</span>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
    </div>

    <!-- Footer -->
    <footer class="amazon-footer">
        <div class="footer-container">
            <div class="footer-grid">
                <div class="footer-column">
                    <h3>Get to Know Us</h3>
                    <ul>
                        <li><a href="#">About Agro-x</a></li>
                        <li><a href="#">Careers</a></li>
                        <li><a href="#">Press Releases</a></li>
                        <li><a href="#">Agro-x Science</a></li>
                    </ul>
                </div>
                
                <div class="footer-column">
                    <h3>Connect with Us</h3>
                    <ul>
                        <li><a href="#">Facebook</a></li>
                        <li><a href="#">Twitter</a></li>
                        <li><a href="#">Instagram</a></li>
                    </ul>
                </div>
                
                <div class="footer-column">
                    <h3>Make Money with Us</h3>
                    <ul>
                        <li><a href="#">Sell on Agro-x</a></li>
                        <li><a href="#">Become an Affiliate</a></li>
                        <li><a href="#">Advertise Your Products</a></li>
                    </ul>
                </div>
                
                <div class="footer-column">
                    <h3>Let Us Help You</h3>
                    <ul>
                        <li><a href="#">Your Account</a></li>
                        <li><a href="#">Returns Centre</a></li>
                        <li><a href="#">100% Purchase Protection</a></li>
                        <li><a href="#">Help</a></li>
                    </ul>
                </div>
            </div>
            
            <div class="footer-bottom">
                <p>© 2024 Agro-x. All rights reserved.</p>
                <p>CDA Sector-9, Kathajodi Enclave, Cuttack, Odisha - 753014</p>
            </div>
        </div>
    </footer>

    <script>
        function searchProducts(e) {
            e.preventDefault();
            const searchTerm = document.querySelector('.search-input').value;
            alert(`Searching for: ${searchTerm}`);
        }

        function addToCart(pid) {
            // Simulate adding to cart
            const cartCount = document.querySelector('.cart-count');
            let count = parseInt(cartCount.textContent) || 0;
            cartCount.textContent = count + 1;
            
            // Show confirmation
            const product = document.querySelector(`[onclick="addToCart('${pid}')"]`);
            const originalText = product.innerHTML;
            product.innerHTML = '<i class="fas fa-check"></i> Added';
            product.style.background = '#4caf50';
            product.style.color = 'white';
            
            setTimeout(() => {
                product.innerHTML = originalText;
                product.style.background = '#ffd814';
                product.style.color = 'black';
            }, 1000);
            
            // Actually add to cart
            window.location.href = `/add_to_cart/${pid}`;
        }

        function buyNow(pid) {
            addToCart(pid);
            setTimeout(() => {
                window.location.href = `/cart`;
            }, 500);
        }

        // Initialize cart count
        function updateCartCount() {
            // In a real app, this would fetch from session
            const cartCount = document.querySelector('.cart-count');
            cartCount.textContent = Math.floor(Math.random() * 5);
        }

        document.addEventListener('DOMContentLoaded', updateCartCount);
    </script>
</body>
</html>
"""
PRODUCT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ p.name }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4caf50;
            --primary-dark: #2e7d32;
            --secondary: #2196f3;
            --dark: #1a1a1a;
            --light: #f8f9fa;
            --gray: #6c757d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: #f5f7fa;
            color: var(--dark);
        }

        .navbar {
            background: white;
            box-shadow: 0 2px 20px rgba(0, 0, 0, 0.1);
            padding: 0 20px;
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
        }

        .nav-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }

        .logo-icon {
            font-size: 28px;
            color: var(--primary);
        }

        .logo-text {
            font-size: 22px;
            font-weight: 700;
            color: var(--dark);
        }

        .nav-menu {
            display: flex;
            gap: 25px;
            align-items: center;
        }

        .nav-link {
            color: var(--gray);
            text-decoration: none;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .nav-link:hover {
            color: var(--primary);
            background: rgba(76, 175, 80, 0.1);
        }

        .back-btn {
            background: var(--light);
            color: var(--gray);
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .back-btn:hover {
            background: var(--primary);
            color: white;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        .product-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            background: white;
            border-radius: 24px;
            padding: 40px;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.08);
        }

        .product-gallery {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .main-image {
            width: 100%;
            height: 400px;
            object-fit: contain;
            border-radius: 16px;
            background: var(--light);
            padding: 20px;
        }

        .thumbnails {
            display: flex;
            gap: 15px;
            overflow-x: auto;
            padding: 10px 0;
        }

        .thumbnail {
            width: 80px;
            height: 80px;
            object-fit: cover;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }

        .thumbnail:hover, .thumbnail.active {
            border-color: var(--primary);
            transform: scale(1.05);
        }

        .product-info {
            display: flex;
            flex-direction: column;
        }

        .product-category {
            color: var(--primary);
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .product-title {
            font-size: 36px;
            font-weight: 700;
            margin-bottom: 20px;
            line-height: 1.2;
        }

        .product-rating {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
        }

        .stars {
            color: #ffc107;
        }

        .rating-text {
            color: var(--gray);
            font-size: 14px;
        }

        .product-price {
            font-size: 48px;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 30px;
        }

        .product-description {
            font-size: 16px;
            line-height: 1.6;
            color: var(--gray);
            margin-bottom: 30px;
        }

        .features-list {
            margin-bottom: 30px;
        }

        .feature-item {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
            font-size: 15px;
        }

        .feature-icon {
            color: var(--primary);
            font-size: 14px;
        }

        .product-actions {
            display: flex;
            gap: 15px;
            margin-bottom: 30px;
        }

        .btn-primary {
            flex: 1;
            padding: 18px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-primary:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(76, 175, 80, 0.3);
        }

        .btn-secondary {
            padding: 18px 30px;
            background: white;
            color: var(--primary);
            border: 2px solid var(--primary);
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-secondary:hover {
            background: var(--light);
        }

        .product-meta {
            display: flex;
            gap: 30px;
            margin-top: 30px;
            padding-top: 30px;
            border-top: 1px solid #e0e0e0;
        }

        .meta-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .meta-icon {
            font-size: 20px;
            color: var(--primary);
        }

        .meta-text {
            font-size: 14px;
            color: var(--gray);
        }

        .meta-text strong {
            color: var(--dark);
            display: block;
            font-size: 16px;
        }
        
        /* Language Selector */
        .language-selector {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 992px) {
            .product-container {
                grid-template-columns: 1fr;
            }
            
            .main-image {
                height: 300px;
            }
            
            .language-selector {
                top: 10px;
                right: 10px;
            }
        }

        @media (max-width: 576px) {
            .product-actions {
                flex-direction: column;
            }
            
            .product-title {
                font-size: 28px;
            }
            
            .product-price {
                font-size: 36px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Language Selector -->
    <div class="language-selector">
        <div class="lang-btn">
            <i class="fas fa-globe"></i>
            {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
            <i class="fas fa-chevron-down"></i>
        </div>
        <div class="lang-dropdown">
            <a href="/set_language/en" class="lang-option">English</a>
            <a href="/set_language/hi" class="lang-option">हिंदी</a>
            <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
        </div>
    </div>
    
    <nav class="navbar">
        <div class="nav-container">
            <a href="/dashboard" class="nav-logo">
                <i class="fas fa-seedling logo-icon"></i>
                <span class="logo-text">Agro-x</span>
            </a>
            
            <div class="nav-menu">
                <a href="/shop" class="back-btn">
                    <i class="fas fa-arrow-left"></i>
                    {{ t.back_to_dashboard }}
                </a>
            </div>
        </div>
    </nav>

    <div class="container">
        <div class="product-container">
            <div class="product-gallery">
                <img id="mainImage" src="{{ p.images[0] }}" alt="{{ p.name }}" class="main-image">
                
                <div class="thumbnails">
                    {% for img in p.images %}
                    <img src="{{ img }}" 
                         alt="{{ p.name }} - Image {{ loop.index }}"
                         class="thumbnail {% if loop.first %}active{% endif %}"
                         onclick="changeImage('{{ img }}', this)">
                    {% endfor %}
                </div>
            </div>
            
            <div class="product-info">
                <div class="product-category">
                    {% if p.price >= 10000 %}
                    Premium System
                    {% elif p.price >= 1000 %}
                    Professional Equipment
                    {% else %}
                    Farming Supplies
                    {% endif %}
                </div>
                
                <h1 class="product-title">{{ p.name }}</h1>
                
                <div class="product-rating">
                    <div class="stars">
                        <i class="fas fa-star"></i>
                        <i class="fas fa-star"></i>
                        <i class="fas fa-star"></i>
                        <i class="fas fa-star"></i>
                        <i class="fas fa-star-half-alt"></i>
                    </div>
                    <span class="rating-text">4.5 ({{ range(20, 101)|random }} reviews)</span>
                </div>
                
                <div class="product-price">₹ {{ p.price }}</div>
                
                <p class="product-description">
                    {{ p.desc }}
                </p>
                
                <div class="features-list">
                    <div class="feature-item">
                        <i class="fas fa-check feature-icon"></i>
                        <span>High precision and accuracy</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-check feature-icon"></i>
                        <span>Easy installation and setup</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-check feature-icon"></i>
                        <span>Compatible with Agro-x system</span>
                    </div>
                    <div class="feature-item">
                        <i class="fas fa-check feature-icon"></i>
                        <span>1 year manufacturer warranty</span>
                    </div>
                </div>
                
                <div class="product-actions">
                    <a href="/add_to_cart/{{ pid }}" class="btn-primary">
                        <i class="fas fa-cart-plus"></i>
                        {{ t.add_to_cart }}
                    </a>
                    <a href="/shop" class="btn-secondary">
                        <i class="fas fa-shopping-bag"></i>
                        {{ t.continue_shopping }}
                    </a>
                </div>
                
                <div class="product-meta">
                    <div class="meta-item">
                        <i class="fas fa-shipping-fast meta-icon"></i>
                        <div class="meta-text">
                            <strong>Free Shipping</strong>
                            On orders over ₹ 5000
                        </div>
                    </div>
                    
                    <div class="meta-item">
                        <i class="fas fa-undo meta-icon"></i>
                        <div class="meta-text">
                            <strong>30-Day Returns</strong>
                            Easy return policy
                        </div>
                    </div>
                    
                    <div class="meta-item">
                        <i class="fas fa-headset meta-icon"></i>
                        <div class="meta-text">
                            <strong>Expert Support</strong>
                            24/7 customer service
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function changeImage(src, element) {
            document.getElementById('mainImage').src = src;
            
            // Update active thumbnail
            document.querySelectorAll('.thumbnail').forEach(thumb => {
                thumb.classList.remove('active');
            });
            element.classList.add('active');
        }

        // Add to cart animation
        document.querySelector('.btn-primary').addEventListener('click', function(e) {
            if (!e.ctrlKey && !e.metaKey) {
                e.preventDefault();
                
                const btn = this;
                const originalHTML = btn.innerHTML;
                
                btn.innerHTML = '<i class="fas fa-check"></i> {{ t.added_to_cart }}';
                btn.style.background = '#2e7d32';
                
                setTimeout(() => {
                    window.location.href = btn.href;
                }, 500);
            }
        });
    </script>
</body>
</html>
"""

CART_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.your_cart }} | Agro-x</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4caf50;
            --primary-dark: #2e7d32;
            --secondary: #2196f3;
            --accent: #ff9800;
            --danger: #f44336;
            --dark: #1a1a1a;
            --light: #f8f9fa;
            --gray: #6c757d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: #f5f7fa;
            color: var(--dark);
        }

        .navbar {
            background: white;
            box-shadow: 0 2px 20px rgba(0, 0, 0, 0.1);
            padding: 0 20px;
        }

        .nav-container {
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
        }

        .nav-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
        }

        .logo-icon {
            font-size: 28px;
            color: var(--primary);
        }

        .logo-text {
            font-size: 22px;
            font-weight: 700;
            color: var(--dark);
        }

        .nav-menu {
            display: flex;
            gap: 25px;
            align-items: center;
        }

        .nav-link {
            color: var(--gray);
            text-decoration: none;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .nav-link:hover {
            color: var(--primary);
            background: rgba(76, 175, 80, 0.1);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        .cart-header {
            text-align: center;
            margin-bottom: 40px;
        }

        .cart-header h1 {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .cart-header p {
            font-size: 18px;
            color: var(--gray);
        }

        .cart-content {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 40px;
        }

        .cart-items {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }

        .cart-item {
            display: flex;
            gap: 20px;
            padding: 25px 0;
            border-bottom: 1px solid #e0e0e0;
        }

        .cart-item:last-child {
            border-bottom: none;
        }

        .item-image {
            width: 120px;
            height: 120px;
            object-fit: contain;
            border-radius: 12px;
            background: var(--light);
            padding: 10px;
        }

        .item-details {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }

        .item-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 15px;
        }

        .item-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 5px;
        }

        .item-price {
            font-size: 20px;
            font-weight: 700;
            color: var(--primary);
        }

        .item-actions {
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .quantity-control {
            display: flex;
            align-items: center;
            gap: 10px;
            background: var(--light);
            border-radius: 10px;
            padding: 5px;
        }

        .qty-btn {
            width: 36px;
            height: 36px;
            border: none;
            background: white;
            border-radius: 8px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.3s ease;
        }

        .qty-btn:hover {
            background: var(--primary);
            color: white;
        }

        .qty-value {
            font-size: 16px;
            font-weight: 600;
            min-width: 30px;
            text-align: center;
        }

        .remove-btn {
            color: var(--danger);
            background: none;
            border: none;
            font-size: 14px;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 5px;
            padding: 8px 12px;
            border-radius: 6px;
            transition: all 0.3s ease;
        }

        .remove-btn:hover {
            background: rgba(244, 67, 54, 0.1);
        }

        .cart-summary {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
            position: sticky;
            top: 40px;
            height: fit-content;
        }

        .summary-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 25px;
            padding-bottom: 15px;
            border-bottom: 2px solid var(--light);
        }

        .summary-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            font-size: 16px;
        }

        .summary-total {
            font-size: 20px;
            font-weight: 700;
            margin: 25px 0;
            padding-top: 20px;
            border-top: 2px solid var(--light);
        }

        .discount-badge {
            background: linear-gradient(135deg, #ff9800, #ff5722);
            color: white;
            padding: 10px 15px;
            border-radius: 10px;
            font-size: 14px;
            font-weight: 600;
            margin: 20px 0;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.02); }
            100% { transform: scale(1); }
        }

        .checkout-form {
            background: white;
            border-radius: 20px;
            padding: 30px;
            margin-top: 40px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
        }

        .form-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 25px;
        }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 25px;
        }

        .form-group {
            margin-bottom: 20px;
        }

        .form-group.full-width {
            grid-column: 1 / -1;
        }

        .form-label {
            display: block;
            margin-bottom: 8px;
            font-weight: 500;
            color: var(--dark);
        }

        .form-input {
            width: 100%;
            padding: 14px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            transition: all 0.3s ease;
        }

        .form-input:focus {
            outline: none;
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(76, 175, 80, 0.1);
        }

        .btn-checkout {
            width: 100%;
            padding: 18px;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
            border: none;
            border-radius: 12px;
            font-size: 18px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            margin-top: 20px;
        }

        .btn-checkout:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(76, 175, 80, 0.3);
        }

        .btn-clear {
            background: var(--light);
            color: var(--danger);
            border: 2px solid var(--danger);
            padding: 12px 25px;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 20px;
        }

        .btn-clear:hover {
            background: var(--danger);
            color: white;
        }

        .empty-cart {
            text-align: center;
            padding: 60px 20px;
        }

        .empty-icon {
            font-size: 80px;
            color: #e0e0e0;
            margin-bottom: 20px;
        }

        .empty-title {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 15px;
            color: var(--gray);
        }

        .empty-text {
            font-size: 18px;
            color: var(--gray);
            margin-bottom: 30px;
        }

        .btn-shop {
            display: inline-flex;
            align-items: center;
            gap: 10px;
            padding: 15px 30px;
            background: var(--primary);
            color: white;
            text-decoration: none;
            border-radius: 12px;
            font-weight: 600;
            font-size: 16px;
            transition: all 0.3s ease;
        }

        .btn-shop:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
        }
        
        /* Language Selector */
        .language-selector {
            position: relative;
        }

        .lang-btn {
            background: var(--light);
            border: 1px solid #e0e0e0;
            color: var(--gray);
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: #e9ecef;
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: white;
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
            z-index: 1000;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: var(--dark);
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: var(--light);
        }

        @media (max-width: 992px) {
            .cart-content {
                grid-template-columns: 1fr;
            }
            
            .form-grid {
                grid-template-columns: 1fr;
            }
        }

        @media (max-width: 576px) {
            .cart-item {
                flex-direction: column;
            }
            
            .item-image {
                width: 100%;
                height: 200px;
            }
            
            .cart-header h1 {
                font-size: 36px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <nav class="navbar">
        <div class="nav-container">
            <a href="/dashboard" class="nav-logo">
                <i class="fas fa-seedling logo-icon"></i>
                <span class="logo-text">Agro-x</span>
            </a>
            
            <div class="nav-menu">
                <a href="/shop" class="nav-link">
                    <i class="fas fa-shopping-cart"></i>
                    {{ t.continue_shopping }}
                </a>
                
                <!-- Language Selector -->
                <div class="language-selector">
                    <div class="lang-btn">
                        <i class="fas fa-globe"></i>
                        {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
                        <i class="fas fa-chevron-down"></i>
                    </div>
                    <div class="lang-dropdown">
                        <a href="/set_language/en" class="lang-option">English</a>
                        <a href="/set_language/hi" class="lang-option">हिंदी</a>
                        <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
                    </div>
                </div>
                
                <a href="/dashboard" class="nav-link">
                    <i class="fas fa-arrow-left"></i>
                    {{ t.back_to_dashboard }}
                </a>
            </div>
        </div>
    </nav>

    <div class="container">
        {% if items %}
        <div class="cart-header">
            <h1>{{ t.your_cart }}</h1>
            <p>{{ t.review_items }}</p>
        </div>

        <div class="cart-content">
            <div class="cart-items">
                <a href="/clear_cart" class="btn-clear">
                    <i class="fas fa-trash"></i>
                    {{ t.clear_cart }}
                </a>
                
                {% for pid, name, price, qty, subtotal in items %}
                <div class="cart-item">
                    <img src="{{ products[pid].images[0] }}" alt="{{ name }}" class="item-image">
                    
                    <div class="item-details">
                        <div class="item-header">
                            <div>
                                <h3 class="item-title">{{ name }}</h3>
                                <p style="color: var(--gray); font-size: 14px;">{{ t.product_id }}: {{ pid }}</p>
                            </div>
                            <div class="item-price">₹ {{ subtotal }}</div>
                        </div>
                        
                        <div class="item-actions">
                            <div class="quantity-control">
                                <a href="/update_qty/{{ pid }}/minus" class="qty-btn">−</a>
                                <span class="qty-value">{{ qty }}</span>
                                <a href="/update_qty/{{ pid }}/plus" class="qty-btn">+</a>
                            </div>
                            <span style="color: var(--gray);">× ₹ {{ price }} {{ t.each }}</span>
                            <a href="/update_qty/{{ pid }}/minus" class="remove-btn">
                                <i class="fas fa-times"></i>
                                {{ t.remove }}
                            </a>
                        </div>
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <div class="cart-summary">
                <h2 class="summary-title">{{ t.order_summary }}</h2>
                
                <div class="summary-row">
                    <span>{{ t.subtotal }}</span>
                    <span>₹ {{ total }}</span>
                </div>
                
                {% if discount > 0 %}
                <div class="discount-badge">
                    <i class="fas fa-gift"></i>
                    {{ discount_label }}
                </div>
                
                <div class="summary-row" style="color: var(--primary);">
                    <span>{{ t.discount }}</span>
                    <span>- ₹ {{ discount }}</span>
                </div>
                {% endif %}
                
                <div class="summary-row">
                    <span>{{ t.shipping }}</span>
                    <span>Free</span>
                </div>
                
                <div class="summary-row">
                    <span>{{ t.tax }}</span>
                    <span>Included</span>
                </div>
                
                <div class="summary-total">
                    <span>{{ t.total_amount }}</span>
                    <span>₹ {{ final_total }}</span>
                </div>
                
                <p style="font-size: 14px; color: var(--gray); text-align: center; margin: 20px 0;">
                    <i class="fas fa-lock"></i>
                    {{ t.secure_checkout }}
                </p>
            </div>
        </div>

        <div class="checkout-form">
            <h2 class="form-title">{{ t.shipping_information }}</h2>
            
            <form method="post" action="/checkout">
                <div class="form-grid">
                    <div class="form-group">
                        <label class="form-label">{{ t.full_name }} *</label>
                        <input type="text" name="name" class="form-input" placeholder="{{ t.enter_full_name }}" required>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.mobile_number }} *</label>
                        <input type="tel" name="mobile" class="form-input" placeholder="{{ t.enter_mobile }}" required>
                    </div>
                    
                    <div class="form-group full-width">
                        <label class="form-label">{{ t.address }} *</label>
                        <input type="text" name="address" class="form-input" placeholder="{{ t.street_address }}" required>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.landmark }}</label>
                        <input type="text" name="landmark" class="form-input" placeholder="{{ t.nearby_landmark }}">
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.pincode }} *</label>
                        <input type="text" name="pincode" class="form-input" placeholder="{{ t.postal_code }}" required>
                    </div>
                    
                    <div class="form-group">
                        <label class="form-label">{{ t.alt_mobile }}</label>
                        <input type="tel" name="alt_mobile" class="form-input" placeholder="{{ t.alt_contact }}">
                    </div>
                </div>
                
                <button type="submit" class="btn-checkout">
                    <i class="fas fa-lock"></i>
                    {{ t.proceed_to_payment }}
                </button>
            </form>
        </div>
        {% else %}
        <div class="empty-cart">
            <div class="empty-icon">
                <i class="fas fa-shopping-cart"></i>
            </div>
            <h2 class="empty-title">{{ t.empty_cart }}</h2>
            <p class="empty-text">{{ t.add_products }}</p>
            <a href="/shop" class="btn-shop">
                <i class="fas fa-store"></i>
                {{ t.start_shopping }}
            </a>
        </div>
        {% endif %}
    </div>

    <script>
        // Update quantity with animation
        document.querySelectorAll('.qty-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                const item = this.closest('.cart-item');
                const qtyValue = item.querySelector('.qty-value');
                
                // Add animation
                item.style.transform = 'scale(0.98)';
                setTimeout(() => {
                    item.style.transform = 'scale(1)';
                }, 300);
            });
        });

        // Form validation
        document.querySelector('form')?.addEventListener('submit', function(e) {
            const inputs = this.querySelectorAll('input[required]');
            let isValid = true;
            
            inputs.forEach(input => {
                if (!input.value.trim()) {
                    input.style.borderColor = 'var(--danger)';
                    isValid = false;
                } else {
                    input.style.borderColor = '#e0e0e0';
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                alert('{{ t.fill_required_fields }}');
            }
        });
    </script>
</body>
</html>
"""

PAYMENT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.payment }} | AutoCrop-X</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4caf50;
            --primary-dark: #2e7d32;
            --secondary: #2196f3;
            --accent: #ff9800;
            --dark: #1a1a1a;
            --light: #f8f9fa;
            --gray: #6c757d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #1a237e 0%, #311b92 100%);
            color: white;
            min-height: 100vh;
        }

        .navbar {
            background: rgba(0, 0, 0, 0.2);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .nav-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: white;
            font-weight: 600;
            font-size: 20px;
        }

        .back-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .back-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        .payment-header {
            text-align: center;
            margin-bottom: 40px;
        }

        .payment-header h1 {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, #4caf50, #2196f3);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .payment-header p {
            font-size: 18px;
            opacity: 0.9;
        }

        .payment-steps {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 40px;
        }

        .step {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 10px;
        }

        .step-number {
            width: 40px;
            height: 40px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
        }

        .step.active .step-number {
            background: var(--primary);
        }

        .step-label {
            font-size: 14px;
            opacity: 0.7;
        }

        .step.active .step-label {
            opacity: 1;
            font-weight: 500;
        }

        .payment-card {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            padding: 40px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin-bottom: 40px;
        }

        .payment-summary {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 16px;
            padding: 30px;
            margin-bottom: 30px;
        }

        .summary-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            font-size: 16px;
        }

        .summary-total {
            font-size: 24px;
            font-weight: 700;
            margin: 25px 0;
            padding-top: 20px;
            border-top: 2px solid rgba(255, 255, 255, 0.1);
        }

        .discount-badge {
            background: linear-gradient(135deg, #ff9800, #ff5722);
            color: white;
            padding: 12px 20px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            margin: 20px 0;
            display: flex;
            align-items: center;
            gap: 12px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.02); }
            100% { transform: scale(1); }
        }

        .payment-methods {
            margin-bottom: 30px;
        }

        .method-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .method-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }

        .method-card {
            background: rgba(255, 255, 255, 0.05);
            border: 2px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .method-card:hover, .method-card.active {
            border-color: var(--primary);
            background: rgba(76, 175, 80, 0.1);
        }

        .method-icon {
            font-size: 32px;
            margin-bottom: 10px;
            color: var(--primary);
        }

        .method-name {
            font-weight: 500;
            margin-bottom: 5px;
        }

        .method-desc {
            font-size: 12px;
            opacity: 0.7;
        }

        .qr-section {
            text-align: center;
            margin: 30px 0;
            padding: 30px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 16px;
        }

        .qr-code {
            width: 200px;
            height: 200px;
            background: white;
            padding: 15px;
            border-radius: 12px;
            margin: 0 auto 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .qr-code img {
            width: 170px;
            height: 170px;
        }

        .upi-id {
            background: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 12px;
            font-family: monospace;
            font-size: 18px;
            margin: 20px auto;
            max-width: 400px;
            word-break: break-all;
        }

        .action-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 30px;
        }

        .btn {
            padding: 18px;
            border-radius: 12px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            text-decoration: none;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
            border: none;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 30px rgba(76, 175, 80, 0.3);
        }

        .btn-secondary {
            background: rgba(255, 255, 255, 0.1);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.2);
        }

        .btn-secondary:hover {
            background: rgba(255, 255, 255, 0.2);
        }
        
        /* Language Selector */
        .language-selector {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 768px) {
            .action-buttons {
                grid-template-columns: 1fr;
            }
            
            .method-grid {
                grid-template-columns: 1fr;
            }
            
            .payment-header h1 {
                font-size: 36px;
            }
            
            .payment-steps {
                flex-wrap: wrap;
            }
            
            .language-selector {
                top: 10px;
                right: 10px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Language Selector -->
    <div class="language-selector">
        <div class="lang-btn">
            <i class="fas fa-globe"></i>
            {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
            <i class="fas fa-chevron-down"></i>
        </div>
        <div class="lang-dropdown">
            <a href="/set_language/en" class="lang-option">English</a>
            <a href="/set_language/hi" class="lang-option">हिंदी</a>
            <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
        </div>
    </div>
    
    <nav class="navbar">
        <div class="nav-container">
            <a href="/dashboard" class="nav-logo">
                <i class="fas fa-seedling"></i>
                AutoCrop-X {{ t.payment }}
            </a>
            <a href="/cart" class="back-btn">
                <i class="fas fa-arrow-left"></i>
                {{ t.back_to_dashboard }}
            </a>
        </div>
    </nav>

    <div class="container">
        <div class="payment-header">
            <h1>{{ t.complete_payment }}</h1>
            <p>{{ t.secure_payment }}</p>
        </div>

        <div class="payment-steps">
            <div class="step">
                <div class="step-number">1</div>
                <div class="step-label">{{ t.cart }}</div>
            </div>
            <div class="step">
                <div class="step-number">2</div>
                <div class="step-label">{{ t.shipping }}</div>
            </div>
            <div class="step active">
                <div class="step-number">3</div>
                <div class="step-label">{{ t.payment }}</div>
            </div>
            <div class="step">
                <div class="step-number">4</div>
                <div class="step-label">{{ t.confirmation }}</div>
            </div>
        </div>

        <div class="payment-card">
            <div class="payment-summary">
                <div class="summary-row">
                    <span>{{ t.order_total }}</span>
                    <span>₹ {{ total }}</span>
                </div>
                
                {% if discount > 0 %}
                <div class="discount-badge">
                    <i class="fas fa-gift"></i>
                    {{ label }}
                </div>
                
                <div class="summary-row" style="color: #4caf50;">
                    <span>{{ t.discount_applied }}</span>
                    <span>- ₹ {{ discount }}</span>
                </div>
                {% endif %}
                
                <div class="summary-row">
                    <span>GST (18%)</span>
                    <span>₹ {{ gst }}</span>
                </div>
                
                <div class="summary-row">
                    <span>{{ t.shipping }}</span>
                    <span>FREE</span>
                </div>
                
                <div class="summary-total">
                    <span>{{ t.amount_to_pay }}</span>
                    <span>₹ {{ final }}</span>
                </div>
            </div>

            <div class="payment-methods">
                <h3 class="method-title">
                    <i class="fas fa-credit-card"></i>
                    {{ t.choose_payment_method }}
                </h3>
                
                <div class="method-grid">
                    <div class="method-card active" onclick="selectMethod('upi')">
                        <div class="method-icon">
                            <i class="fas fa-qrcode"></i>
                        </div>
                        <div class="method-name">UPI</div>
                        <div class="method-desc">Instant Payment</div>
                    </div>
                    
                    <div class="method-card" onclick="selectMethod('card')">
                        <div class="method-icon">
                            <i class="fas fa-credit-card"></i>
                        </div>
                        <div class="method-name">Credit Card</div>
                        <div class="method-desc">Visa, MasterCard</div>
                    </div>
                    
                    <div class="method-card" onclick="selectMethod('netbanking')">
                        <div class="method-icon">
                            <i class="fas fa-university"></i>
                        </div>
                        <div class="method-name">Net Banking</div>
                        <div class="method-desc">All Banks</div>
                    </div>
                    
                    <div class="method-card" onclick="selectMethod('cod')">
                        <div class="method-icon">
                            <i class="fas fa-truck"></i>
                        </div>
                        <div class="method-name">Cash on Delivery</div>
                        <div class="method-desc">Pay when delivered</div>
                    </div>
                </div>
            </div>

            <div class="qr-section" id="upiSection">
                <div class="qr-code">
                    <img src="https://i.imgur.com/CuXUkIr.jpeg" alt="UPI QR Code">
                </div>
                
                <h3 style="margin-bottom: 15px;">{{ t.scan_qr }}</h3>
                <p style="opacity: 0.8; margin-bottom: 20px;">{{ t.scan_with_upi }}</p>
                
                <div class="upi-id">
                    somyasreeswain952-1@oksbi
                </div>
                
                <p style="font-size: 14px; opacity: 0.7; margin-top: 15px;">
                    <i class="fas fa-shield-alt"></i> Secure payment powered by Razorpay
                </p>
            </div>

            <div class="action-buttons">
                <a href="/confirm" class="btn btn-primary">
                    <i class="fas fa-check-circle"></i>
                    {{ t.payment_done }}
                </a>
                
                <a href="/download_bill" class="btn btn-secondary">
                    <i class="fas fa-file-pdf"></i>
                    {{ t.download_invoice }}
                </a>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 30px; opacity: 0.7; font-size: 14px;">
            <p><i class="fas fa-lock"></i> {{ t.payment_secure }}</p>
        </div>
    </div>

    <script>
        function selectMethod(method) {
            // Update active method
            document.querySelectorAll('.method-card').forEach(card => {
                card.classList.remove('active');
            });
            event.currentTarget.classList.add('active');
            
            // Show/hide sections based on method
            const upiSection = document.getElementById('upiSection');
            if (method === 'upi') {
                upiSection.style.display = 'block';
            } else {
                upiSection.style.display = 'none';
                alert(`Selected ${method.toUpperCase()} payment. In a real application, you would be redirected to the payment gateway.`);
            }
        }

        // Copy UPI ID to clipboard
        document.querySelector('.upi-id').addEventListener('click', function() {
            const upiId = 'somyasreeswain952-1@oksbi';
            navigator.clipboard.writeText(upiId).then(() => {
                const originalText = this.textContent;
                this.textContent = '✓ Copied to clipboard!';
                this.style.background = 'rgba(76, 175, 80, 0.3)';
                
                setTimeout(() => {
                    this.textContent = originalText;
                    this.style.background = 'rgba(255, 255, 255, 0.1)';
                }, 2000);
            });
        });

        // Payment timer
        let timeLeft = 900; // 15 minutes in seconds
        const timerElement = document.createElement('div');
        timerElement.style.cssText = `
            background: rgba(244, 67, 54, 0.1);
            border: 1px solid rgba(244, 67, 54, 0.3);
            border-radius: 12px;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
            font-weight: 600;
        `;
        
        function updateTimer() {
            const minutes = Math.floor(timeLeft / 60);
            const seconds = timeLeft % 60;
            timerElement.innerHTML = `
                <i class="fas fa-clock"></i>
                Complete payment within: ${minutes}:${seconds.toString().padStart(2, '0')}
            `;
            
            if (timeLeft > 0) {
                timeLeft--;
            } else {
                timerElement.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Payment session expired!';
                timerElement.style.background = 'rgba(244, 67, 54, 0.2)';
            }
        }
        
        // Add timer to payment card
        document.querySelector('.payment-card').insertBefore(
            timerElement, 
            document.querySelector('.payment-summary')
        );
        updateTimer();
        setInterval(updateTimer, 1000);
    </script>
</body>
</html>
"""

CONFIRM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.order_confirmed }} | AutoCrop-X</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4caf50;
            --primary-dark: #2e7d32;
            --secondary: #2196f3;
            --dark: #1a1a1a;
            --light: #f8f9fa;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0c3b2e 0%, #1b5e20 100%);
            color: white;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }

        .confirmation-card {
            background: rgba(255, 255, 255, 0.95);
            border-radius: 30px;
            padding: 50px;
            max-width: 600px;
            width: 100%;
            text-align: center;
            box-shadow: 0 30px 80px rgba(0, 0, 0, 0.3);
            animation: slideIn 0.6s ease-out;
            color: var(--dark);
        }

        @keyframes slideIn {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .success-icon {
            width: 100px;
            height: 100px;
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            border-radius: 50%;
            margin: 0 auto 30px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            color: white;
            animation: scaleIn 0.5s ease-out 0.3s both;
        }

        @keyframes scaleIn {
            from {
                transform: scale(0);
            }
            to {
                transform: scale(1);
            }
        }

        .confirmation-title {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 20px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .confirmation-message {
            font-size: 18px;
            line-height: 1.6;
            color: #666;
            margin-bottom: 40px;
        }

        .order-details {
            background: var(--light);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 40px;
            text-align: left;
        }

        .detail-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #e0e0e0;
        }

        .detail-row:last-child {
            border-bottom: none;
            margin-bottom: 0;
            padding-bottom: 0;
        }

        .detail-label {
            font-weight: 500;
            color: #666;
        }

        .detail-value {
            font-weight: 600;
            color: var(--dark);
        }

        .confirmation-actions {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }

        .btn {
            padding: 18px;
            border-radius: 15px;
            font-size: 16px;
            font-weight: 600;
            text-decoration: none;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
        }

        .btn-primary {
            background: linear-gradient(135deg, var(--primary), var(--primary-dark));
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-3px);
            box-shadow: 0 15px 30px rgba(76, 175, 80, 0.3);
        }

        .btn-secondary {
            background: white;
            color: var(--primary);
            border: 2px solid var(--primary);
        }

        .btn-secondary:hover {
            background: var(--light);
            transform: translateY(-3px);
        }

        .confirmation-footer {
            border-top: 1px solid #e0e0e0;
            padding-top: 30px;
        }

        .footer-title {
            font-size: 20px;
            font-weight: 600;
            margin-bottom: 15px;
            color: var(--dark);
        }

        .contact-info {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-top: 20px;
        }

        .contact-item {
            display: flex;
            align-items: center;
            gap: 10px;
            color: #666;
        }

        .contact-icon {
            color: var(--primary);
            font-size: 18px;
        }
        
        /* Language Selector */
        .language-selector {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 768px) {
            .confirmation-card {
                padding: 30px;
            }
            
            .confirmation-title {
                font-size: 36px;
            }
            
            .confirmation-actions {
                grid-template-columns: 1fr;
            }
            
            .contact-info {
                flex-direction: column;
                align-items: center;
                gap: 15px;
            }
            
            .language-selector {
                top: 10px;
                right: 10px;
            }
        }

        /* Confetti animation */
        .confetti {
            position: absolute;
            width: 10px;
            height: 10px;
            background: var(--primary);
            opacity: 0;
            animation: confettiFall 5s linear infinite;
        }

        @keyframes confettiFall {
            0% {
                transform: translateY(-100vh) rotate(0deg);
                opacity: 1;
            }
            100% {
                transform: translateY(100vh) rotate(720deg);
                opacity: 0;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Language Selector -->
    <div class="language-selector">
        <div class="lang-btn">
            <i class="fas fa-globe"></i>
            {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
            <i class="fas fa-chevron-down"></i>
        </div>
        <div class="lang-dropdown">
            <a href="/set_language/en" class="lang-option">English</a>
            <a href="/set_language/hi" class="lang-option">हिंदी</a>
            <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
        </div>
    </div>
    
    <!-- Confetti elements will be added by JavaScript -->
    
    <div class="confirmation-card">
        <div class="success-icon">
            <i class="fas fa-check"></i>
        </div>
        
        <h1 class="confirmation-title">{{ t.order_confirmed }}</h1>
        
        <p class="confirmation-message">
            {{ t.thank_you }}
        </p>
        
        <div class="order-details">
            <div class="detail-row">
                <span class="detail-label">{{ t.order_number }}</span>
                <span class="detail-value">ACX-{{ "%06d"|format(range(100000, 999999)|random) }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">{{ t.order_date }}</span>
                <span class="detail-value">{{ datetime.datetime.now().strftime("%B %d, %Y") }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">{{ t.estimated_delivery }}</span>
                <span class="detail-value">{{ (datetime.datetime.now() + datetime.timedelta(days=5)).strftime("%B %d, %Y") }}</span>
            </div>
            <div class="detail-row">
                <span class="detail-label">{{ t.payment_status }}</span>
                <span class="detail-value" style="color: var(--primary);">✅ {{ t.paid }}</span>
            </div>
        </div>
        
        <div class="confirmation-actions">
            <a href="/dashboard" class="btn btn-primary">
                <i class="fas fa-tachometer-alt"></i>
                {{ t.back_to_dashboard }}
            </a>
            
            <a href="/shop" class="btn btn-secondary">
                <i class="fas fa-shopping-cart"></i>
                {{ t.continue_shopping }}
            </a>
        </div>
        
        <div class="confirmation-footer">
            <h3 class="footer-title">{{ t.need_help }}</h3>
            <p style="color: #666; margin-bottom: 20px;">
                {{ t.customer_support }}
            </p>
            
            <div class="contact-info">
                <div class="contact-item">
                    <i class="fas fa-phone contact-icon"></i>
                    <span>9692777847</span>
                </div>
                <div class="contact-item">
                    <i class="fas fa-envelope contact-icon"></i>
                    <span>autocrop24@gmail.com</span>
                </div>
                <div class="contact-item">
                    <i class="fas fa-map-marker-alt contact-icon"></i>
                    <span>CDA Sector-9, Cuttack</span>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Create confetti
        function createConfetti() {
            const colors = ['#4caf50', '#2196f3', '#ff9800', '#e91e63', '#9c27b0'];
            
            for (let i = 0; i < 100; i++) {
                const confetti = document.createElement('div');
                confetti.className = 'confetti';
                confetti.style.left = Math.random() * 100 + 'vw';
                confetti.style.background = colors[Math.floor(Math.random() * colors.length)];
                confetti.style.width = Math.random() * 10 + 5 + 'px';
                confetti.style.height = Math.random() * 10 + 5 + 'px';
                confetti.style.animationDelay = Math.random() * 5 + 's';
                confetti.style.animationDuration = Math.random() * 3 + 3 + 's';
                document.body.appendChild(confetti);
            }
        }

        // Create celebration effect
        function createCelebration() {
            createConfetti();
            
            // Add some floating icons
            const icons = ['🎉', '✨', '🌟', '🎊', '🥳', '✅', '🚀'];
            for (let i = 0; i < 15; i++) {
                setTimeout(() => {
                    const icon = document.createElement('div');
                    icon.textContent = icons[Math.floor(Math.random() * icons.length)];
                    icon.style.position = 'fixed';
                    icon.style.fontSize = '24px';
                    icon.style.left = Math.random() * 100 + 'vw';
                    icon.style.top = '-50px';
                    icon.style.opacity = '0';
                    icon.style.animation = `floatDown ${Math.random() * 2 + 3}s linear forwards`;
                    document.body.appendChild(icon);
                    
                    setTimeout(() => icon.remove(), 5000);
                }, i * 200);
            }
        }

        // Add CSS for floating animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes floatDown {
                0% {
                    transform: translateY(0) rotate(0deg);
                    opacity: 0;
                }
                10% {
                    opacity: 1;
                }
                90% {
                    opacity: 1;
                }
                100% {
                    transform: translateY(100vh) rotate(360deg);
                    opacity: 0;
                }
            }
        `;
        document.head.appendChild(style);

        // Start celebration
        document.addEventListener('DOMContentLoaded', createCelebration);
        
        // Play success sound (optional)
        setTimeout(() => {
            try {
                // Create a simple success sound using Web Audio API
                const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = audioContext.createOscillator();
                const gainNode = audioContext.createGain();
                
                oscillator.connect(gainNode);
                gainNode.connect(audioContext.destination);
                
                oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime); // C5
                oscillator.frequency.setValueAtTime(659.25, audioContext.currentTime + 0.1); // E5
                oscillator.frequency.setValueAtTime(783.99, audioContext.currentTime + 0.2); // G5
                
                gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
                
                oscillator.start(audioContext.currentTime);
                oscillator.stop(audioContext.currentTime + 0.5);
            } catch (e) {
                // Audio context not supported or user blocked it
                console.log('Audio not available');
            }
        }, 500);
    </script>
</body>
</html>
"""

HELP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ t.helpdesk }} | AutoCrop-X</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --primary: #4caf50;
            --primary-dark: #2e7d32;
            --secondary: #2196f3;
            --dark: #1a1a1a;
            --light: #f8f9fa;
            --gray: #6c757d;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0c3b2e 0%, #1b5e20 100%);
            color: white;
            min-height: 100vh;
        }

        .navbar {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            padding: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .nav-container {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .nav-logo {
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: white;
            font-weight: 600;
            font-size: 20px;
        }

        .back-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-decoration: none;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .back-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }

        .help-header {
            text-align: center;
            margin-bottom: 40px;
        }

        .help-header h1 {
            font-size: 48px;
            font-weight: 700;
            margin-bottom: 10px;
            background: linear-gradient(135deg, var(--primary), var(--secondary));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .help-header p {
            font-size: 18px;
            opacity: 0.9;
            max-width: 600px;
            margin: 0 auto;
        }

        .help-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
        }

        .chat-section {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            padding: 40px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .chat-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .chat-messages {
            height: 400px;
            overflow-y: auto;
            margin-bottom: 30px;
            padding-right: 10px;
        }

        .message {
            margin-bottom: 20px;
            display: flex;
            gap: 15px;
        }

        .message.user {
            justify-content: flex-end;
        }

        .message-avatar {
            width: 40px;
            height: 40px;
            background: var(--primary);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 600;
            flex-shrink: 0;
        }

        .message-content {
            max-width: 70%;
        }

        .message.user .message-content {
            text-align: right;
        }

        .message-text {
            background: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 15px;
            line-height: 1.5;
        }

        .message.user .message-text {
            background: rgba(76, 175, 80, 0.2);
        }

        .message-time {
            font-size: 12px;
            opacity: 0.7;
            margin-top: 5px;
        }

        .chat-input {
            display: flex;
            gap: 15px;
        }

        .chat-input textarea {
            flex: 1;
            padding: 15px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 12px;
            color: white;
            font-size: 16px;
            resize: none;
            min-height: 60px;
        }

        .chat-input textarea:focus {
            outline: none;
            border-color: var(--primary);
        }

        .chat-input button {
            padding: 0 30px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .chat-input button:hover {
            background: var(--primary-dark);
            transform: translateY(-2px);
        }

        .faq-section {
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            padding: 40px;
            border: 1px solid rgba(255, 255, 255, 0.2);
        }

        .faq-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .faq-item {
            margin-bottom: 20px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            padding-bottom: 20px;
        }

        .faq-question {
            font-weight: 600;
            margin-bottom: 10px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .faq-answer {
            font-size: 14px;
            opacity: 0.9;
            line-height: 1.6;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }

        .faq-item.active .faq-answer {
            max-height: 200px;
        }

        .contact-section {
            grid-column: 1 / -1;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 24px;
            padding: 40px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin-top: 40px;
        }

        .contact-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 30px;
            display: flex;
            align-items: center;
            gap: 15px;
        }

        .contact-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 30px;
        }

        .contact-card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 25px;
            text-align: center;
            transition: all 0.3s ease;
        }

        .contact-card:hover {
            transform: translateY(-5px);
            background: rgba(255, 255, 255, 0.1);
        }

        .contact-icon {
            font-size: 32px;
            color: var(--primary);
            margin-bottom: 15px;
        }

        .contact-card h3 {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 10px;
        }

        .contact-card p {
            font-size: 14px;
            opacity: 0.9;
            line-height: 1.6;
        }
        
        /* Language Selector */
        .language-selector {
            position: absolute;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }

        .lang-btn {
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.3);
            color: white;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
            transition: all 0.3s ease;
        }

        .lang-btn:hover {
            background: rgba(255, 255, 255, 0.2);
        }

        .lang-dropdown {
            display: none;
            position: absolute;
            top: 100%;
            right: 0;
            background: rgba(0, 0, 0, 0.9);
            border-radius: 8px;
            padding: 10px;
            min-width: 120px;
        }

        .language-selector:hover .lang-dropdown {
            display: block;
        }

        .lang-option {
            display: block;
            color: white;
            padding: 8px 12px;
            text-decoration: none;
            border-radius: 4px;
            transition: background 0.3s ease;
        }

        .lang-option:hover {
            background: rgba(255, 255, 255, 0.1);
        }

        @media (max-width: 992px) {
            .help-container {
                grid-template-columns: 1fr;
            }
            
            .help-header h1 {
                font-size: 36px;
            }
            
            .language-selector {
                top: 10px;
                right: 10px;
            }
        }
    </style>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
<body>
    <!-- Language Selector -->
    <div class="language-selector">
        <div class="lang-btn">
            <i class="fas fa-globe"></i>
            {{ 'English' if lang == 'en' else 'हिंदी' if lang == 'hi' else 'ଓଡ଼ିଆ' }}
            <i class="fas fa-chevron-down"></i>
        </div>
        <div class="lang-dropdown">
            <a href="/set_language/en" class="lang-option">English</a>
            <a href="/set_language/hi" class="lang-option">हिंदी</a>
            <a href="/set_language/or" class="lang-option">ଓଡ଼ିଆ</a>
        </div>
    </div>
    
    <nav class="navbar">
        <div class="nav-container">
            <a href="/dashboard" class="nav-logo">
                <i class="fas fa-seedling"></i>
                AutoCrop-X {{ t.helpdesk }}
            </a>
            <a href="/dashboard" class="back-btn">
                <i class="fas fa-arrow-left"></i>
                {{ t.back_to_dashboard }}
            </a>
        </div>
    </nav>

    <div class="container">
        <div class="help-header">
            <h1>{{ t.helpdesk_title }}</h1>
            <p>{{ t.ask_question }}</p>
        </div>

        <div class="help-container">
            <div class="chat-section">
                <h2 class="chat-title">
                    <i class="fas fa-robot"></i>
                    AI Assistant
                </h2>
                
                <div class="chat-messages" id="chatMessages">
                    <div class="message ai">
                        <div class="message-avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="message-content">
                            <div class="message-text">
                                Hello! I'm your AutoCrop-X AI assistant. How can I help you with your farming questions today?
                            </div>
                            <div class="message-time">Just now</div>
                        </div>
                    </div>
                    
                    {% if reply %}
                    <div class="message user">
                        <div class="message-content">
                            <div class="message-text">{{ request.form.q if request.form.q else 'Question' }}</div>
                            <div class="message-time">Just now</div>
                        </div>
                        <div class="message-avatar">
                            <i class="fas fa-user"></i>
                        </div>
                    </div>
                    
                    <div class="message ai">
                        <div class="message-avatar">
                            <i class="fas fa-robot"></i>
                        </div>
                        <div class="message-content">
                            <div class="message-text">{{ reply }}</div>
                            <div class="message-time">Just now</div>
                        </div>
                    </div>
                    {% endif %}
                </div>
                
                <form method="post" class="chat-input">
                    <textarea name="q" placeholder="{{ t.ask_placeholder }}" required></textarea>
                    <button type="submit">
                        <i class="fas fa-paper-plane"></i>
                        {{ t.get_answer }}
                    </button>
                </form>
            </div>
            
            <div class="faq-section">
                <h2 class="faq-title">
                    <i class="fas fa-question-circle"></i>
                    Frequently Asked Questions
                </h2>
                
                <div class="faq-item active">
                    <div class="faq-question" onclick="toggleFAQ(this)">
                        How do I optimize water usage for my crops?
                        <i class="fas fa-chevron-down"></i>
                    </div>
                    <div class="faq-answer">
                        Use drip irrigation systems and soil moisture sensors. Water early morning or late evening to reduce evaporation. Adjust watering based on weather conditions and crop growth stage.
                    </div>
                </div>
                
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFAQ(this)">
                        What is the ideal pH level for soil?
                        <i class="fas fa-chevron-down"></i>
                    </div>
                    <div class="faq-answer">
                        Most crops thrive in soil with pH between 6.0 and 7.5. Use pH testing kits regularly and adjust using lime (to raise pH) or sulfur (to lower pH) as needed.
                    </div>
                </div>
                
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFAQ(this)">
                        How to increase crop yield naturally?
                        <i class="fas fa-chevron-down"></i>
                    </div>
                    <div class="faq-answer">
                        Practice crop rotation, use organic compost, ensure proper spacing between plants, implement integrated pest management, and use cover crops to improve soil health.
                    </div>
                </div>
                
                <div class="faq-item">
                    <div class="faq-question" onclick="toggleFAQ(this)">
                        When is the best time to harvest?
                        <i class="fas fa-chevron-down"></i>
                    </div>
                    <div class="faq-answer">
                        Harvest in early morning when temperatures are cool. Check for maturity signs: color change, firmness, and ease of separation from plant. Use sharp, clean tools.
                    </div>
                </div>
            </div>
            
            <div class="contact-section">
                <h2 class="contact-title">
                    <i class="fas fa-headset"></i>
                    {{ t.expert_support }}
                </h2>
                
                <div class="contact-grid">
                    <div class="contact-card">
                        <div class="contact-icon">
                            <i class="fas fa-phone"></i>
                        </div>
                        <h3>Call Us</h3>
                        <p>9692777847<br>Available 24/7 for emergencies</p>
                    </div>
                    
                    <div class="contact-card">
                        <div class="contact-icon">
                            <i class="fas fa-envelope"></i>
                        </div>
                        <h3>Email Support</h3>
                        <p>autocrop24@gmail.com<br>Response within 24 hours</p>
                    </div>
                    
                    <div class="contact-card">
                        <div class="contact-icon">
                            <i class="fas fa-map-marker-alt"></i>
                        </div>
                        <h3>Visit Us</h3>
                        <p>CDA Sector-9, Kathajodi Enclave<br>Cuttack, Odisha - 753014</p>
                    </div>
                    
                    <div class="contact-card">
                        <div class="contact-icon">
                            <i class="fas fa-calendar-alt"></i>
                        </div>
                        <h3>Schedule Consultation</h3>
                        <p>Book a free farm consultation with our agricultural experts</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // FAQ toggle functionality
        function toggleFAQ(element) {
            const faqItem = element.parentElement;
            faqItem.classList.toggle('active');
            
            const icon = element.querySelector('i');
            if (faqItem.classList.contains('active')) {
                icon.className = 'fas fa-chevron-up';
            } else {
                icon.className = 'fas fa-chevron-down';
            }
        }

        // Auto-scroll chat to bottom
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Add sample questions
        const sampleQuestions = [
            "How much water does wheat need?",
            "Best fertilizer for tomatoes?",
            "How to control pests naturally?",
            "When to plant rice in Odisha?",
            "How to test soil nutrients?"
        ];

        // Add sample questions to chat on page load
        document.addEventListener('DOMContentLoaded', () => {
            const chatContainer = document.getElementById('chatMessages');
            
            sampleQuestions.forEach((question, index) => {
                setTimeout(() => {
                    const questionElement = document.createElement('div');
                    questionElement.className = 'message user';
                    questionElement.innerHTML = `
                        <div class="message-content">
                            <div class="message-text" style="opacity: 0.7; font-style: italic;">${question}</div>
                            <div class="message-time">Click to ask</div>
                        </div>
                        <div class="message-avatar">
                            <i class="fas fa-user"></i>
                        </div>
                    `;
                    
                    questionElement.addEventListener('click', () => {
                        document.querySelector('textarea[name="q"]').value = question;
                    });
                    
                    chatContainer.appendChild(questionElement);
                }, index * 300);
            });
        });

        // Form submission animation
        document.querySelector('form').addEventListener('submit', function(e) {
            const textarea = this.querySelector('textarea');
            const button = this.querySelector('button');
            
            if (textarea.value.trim()) {
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
                button.disabled = true;
                
                // Simulate API call
                setTimeout(() => {
                    button.innerHTML = '<i class="fas fa-paper-plane"></i> {{ t.get_answer }}';
                    button.disabled = false;
                }, 1000);
            }
        });
    </script>
</body>
</html>
"""
# app.py के END में ये code add करें (if __name__ == "__main__": से पहले)

import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
