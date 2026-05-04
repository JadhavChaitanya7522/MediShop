"""
Medical Shop Management Web Application
A beginner-friendly Flask application for managing medical shop operations
"""

import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'medical_shop_secret_key_2024'

# Session configuration
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True

# Admin credentials
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'

# Database configuration
DATABASE = 'database.db'

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create Medicines table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medicines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            company TEXT NOT NULL,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL,
            expiry_date TEXT NOT NULL
        )
    ''')
    
    # Create Sales table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_id TEXT NOT NULL,
            medicine_id INTEGER NOT NULL,
            medicine_name TEXT NOT NULL,
            quantity_sold INTEGER NOT NULL,
            total_price REAL NOT NULL,
            sale_date TEXT NOT NULL,
            FOREIGN KEY (medicine_id) REFERENCES medicines (id)
        )
    ''')
    
    # Add transaction_id column if it doesn't exist (for existing databases)
    try:
        cursor.execute('ALTER TABLE sales ADD COLUMN transaction_id TEXT NOT NULL DEFAULT ""')
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

# Initialize database on startup
if not os.path.exists(DATABASE):
    init_db()
else:
    # Run database migrations for existing databases
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if transaction_id column exists
    cursor.execute("PRAGMA table_info(sales)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'transaction_id' not in columns:
        cursor.execute('ALTER TABLE sales ADD COLUMN transaction_id TEXT NOT NULL DEFAULT ""')
        conn.commit()
        print("Migration: Added transaction_id column to sales table")
    
    conn.close()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Context processor to add logged_in status to all templates
@app.context_processor
def inject_user():
    return dict(logged_in=session.get('logged_in', False))

@app.route('/')
def home():
    """Home/Landing page"""
    return render_template('home.html')

@app.route('/medicines')
@login_required
def medicines():
    """Display all medicines - linked from dashboard"""
    return redirect(url_for('medicine_list'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and authentication"""
    # If already logged in, redirect to dashboard
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        print(f"Login attempt - Username: '{username}', Password: '{password}'")
        print(f"Expected - Username: '{ADMIN_USERNAME}', Password: '{ADMIN_PASSWORD}'")
        print(f"Match: {username == ADMIN_USERNAME and password == ADMIN_PASSWORD}")
        
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # Set session
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful! Welcome back.', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'error')
    
    # Render login template for GET requests or invalid POST attempts
    return render_template('login.html')
    

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Dashboard with statistics"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get total medicines count
    cursor.execute('SELECT COUNT(*) as count FROM medicines')
    total_medicines = cursor.fetchone()['count']
    
    # Get total sales count
    cursor.execute('SELECT COUNT(*) as count FROM sales')
    total_sales = cursor.fetchone()['count']
    
    # Get total revenue
    cursor.execute('SELECT COALESCE(SUM(total_price), 0) as total FROM sales')
    total_revenue = cursor.fetchone()['total']
    
    # Get low stock medicines (quantity < 10)
    cursor.execute('SELECT * FROM medicines WHERE quantity < 10 ORDER BY quantity ASC')
    low_stock = cursor.fetchall()
    low_stock_count = len(low_stock)
    
    # Get recent sales
    cursor.execute('SELECT * FROM sales ORDER BY sale_date DESC LIMIT 5')
    recent_sales = cursor.fetchall()
    
    # Get today's sales
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COALESCE(SUM(total_price), 0) as total FROM sales WHERE sale_date LIKE ?', (f'{today}%',))
    today_revenue = cursor.fetchone()['total']
    
    conn.close()
    
    return render_template('dashboard.html', 
                           total_medicines=total_medicines,
                           total_sales=total_sales,
                           total_revenue=total_revenue,
                           low_stock=low_stock,
                           low_stock_count=low_stock_count,
                           recent_sales=recent_sales,
                           today_revenue=today_revenue,
                           datetime=datetime)

@app.route('/add_medicine', methods=['GET', 'POST'])
@login_required
def add_medicine():
    """Add new medicine"""
    if request.method == 'POST':
        medicine_name = request.form['medicine_name']
        company = request.form['company']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])
        expiry_date = request.form['expiry_date']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO medicines (medicine_name, company, price, quantity, expiry_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (medicine_name, company, price, quantity, expiry_date))
        conn.commit()
        conn.close()
        
        flash('Medicine added successfully!', 'success')
        return redirect(url_for('medicine_list'))
    
    return render_template('add_medicine.html', datetime=datetime)

@app.route('/medicine_list')
@login_required
def medicine_list():
    """Display all medicines with search"""
    search_query = request.args.get('search', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if search_query:
        cursor.execute('''
            SELECT * FROM medicines 
            WHERE medicine_name LIKE ? OR company LIKE ?
            ORDER BY medicine_name ASC
        ''', (f'%{search_query}%', f'%{search_query}%'))
    else:
        cursor.execute('SELECT * FROM medicines ORDER BY medicine_name ASC')
    
    medicines = cursor.fetchall()
    conn.close()
    
    return render_template('medicine_list.html', medicines=medicines, search_query=search_query, datetime=datetime)

@app.route('/edit_medicine/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_medicine(id):
    """Edit medicine details"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        medicine_name = request.form['medicine_name']
        company = request.form['company']
        price = float(request.form['price'])
        quantity = int(request.form['quantity'])
        expiry_date = request.form['expiry_date']
        
        cursor.execute('''
            UPDATE medicines 
            SET medicine_name=?, company=?, price=?, quantity=?, expiry_date=?
            WHERE id=?
        ''', (medicine_name, company, price, quantity, expiry_date, id))
        conn.commit()
        conn.close()
        
        flash('Medicine updated successfully!', 'success')
        return redirect(url_for('medicine_list'))
    
    cursor.execute('SELECT * FROM medicines WHERE id = ?', (id,))
    medicine = cursor.fetchone()
    conn.close()
    
    return render_template('edit_medicine.html', medicine=medicine, datetime=datetime)

@app.route('/delete_medicine/<int:id>')
@login_required
def delete_medicine(id):
    """Delete medicine"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM medicines WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    
    flash('Medicine deleted successfully!', 'success')
    return redirect(url_for('medicine_list'))

@app.route('/add_sale', methods=['GET', 'POST'])
@login_required
def add_sale():
    """Add new sale"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all medicines with sufficient stock
    cursor.execute('SELECT * FROM medicines WHERE quantity > 0 ORDER BY medicine_name ASC')
    medicines = cursor.fetchall()
    
    # Convert Row objects to dictionaries for JSON serialization
    medicines_list = [dict(medicine) for medicine in medicines]
    
    if request.method == 'POST':
        # Get multiple medicines from form (new format with _ suffix)
        medicine_ids = request.form.getlist('medicine_id[]')
        quantity_solds = request.form.getlist('quantity_sold[]')
        
        # Check if we have items to process
        if not medicine_ids or not any(medicine_ids):
            flash('Error: Please add at least one medicine to the sale!', 'danger')
            conn.close()
            return redirect(url_for('add_sale'))
        
        sale_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Generate unique transaction_id for this sale
        import uuid
        transaction_id = f"TXN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"
        
        total_sale_amount = 0
        items_count = 0
        errors = []
        
        # Process each medicine
        for i in range(len(medicine_ids)):
            if not medicine_ids[i]:
                continue
                
            try:
                medicine_id = int(medicine_ids[i])
                quantity_sold = int(quantity_solds[i]) if i < len(quantity_solds) else 0
                
                if quantity_sold <= 0:
                    continue
                
                # Get medicine details
                cursor.execute('SELECT * FROM medicines WHERE id = ?', (medicine_id,))
                medicine = cursor.fetchone()
                
                if not medicine:
                    continue
                    
                if quantity_sold > medicine['quantity']:
                    errors.append(f'Error: Only {medicine["quantity"]} units of {medicine["medicine_name"]} available!')
                    continue
                
                line_total = medicine['price'] * quantity_sold
                
                # Insert sale record with transaction_id
                cursor.execute('''
                    INSERT INTO sales (transaction_id, medicine_id, medicine_name, quantity_sold, total_price, sale_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (transaction_id, medicine_id, medicine['medicine_name'], quantity_sold, line_total, sale_date))
                
                # Update medicine quantity
                new_quantity = medicine['quantity'] - quantity_sold
                cursor.execute('UPDATE medicines SET quantity = ? WHERE id = ?', (new_quantity, medicine_id))
                
                total_sale_amount += line_total
                items_count += 1
                
            except (ValueError, IndexError) as e:
                continue
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            conn.close()
            return redirect(url_for('add_sale'))
        
        if items_count == 0:
            flash('Error: No valid items in the sale!', 'danger')
            conn.close()
            return redirect(url_for('add_sale'))
        
        conn.commit()
        conn.close()
        
        flash(f'Sale recorded successfully! {items_count} item(s) - Total: ₹{total_sale_amount:.2f}', 'success')
        return redirect(url_for('sales_list'))
    
    conn.close()
    return render_template('add_sale.html', medicines=medicines_list, datetime=datetime)

@app.route('/sales_list')
@login_required
def sales_list():
    """Display all sales"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sales ORDER BY sale_date DESC')
    sales = cursor.fetchall()
    conn.close()
    
    return render_template('sales_list.html', sales=sales, datetime=datetime)

@app.route('/get_medicine_price/<int:medicine_id>')
@login_required
def get_medicine_price(medicine_id):
    """Get medicine price for AJAX request"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT price, quantity FROM medicines WHERE id = ?', (medicine_id,))
    medicine = cursor.fetchone()
    conn.close()
    
    if medicine:
        return {'price': medicine['price'], 'available': medicine['quantity']}
    return {'price': 0, 'available': 0}

if __name__ == '__main__':
    # Initialize database if not exists
    if not os.path.exists(DATABASE):
        init_db()
    app.run(debug=True)

