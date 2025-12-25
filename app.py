from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
import os
from werkzeug.utils import secure_filename
import requests
from dotenv import load_dotenv


load_dotenv()

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'


db = mysql.connector.connect(
    host='localhost',
    user='root',
    password='root',
    database='world'  
)


app.config['UPLOAD_FOLDER'] = 'static/uploads/'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)


FAST2SMS_API_KEY = os.getenv('FAST2SMS_API_KEY')
FAST2SMS_URL = 'https://www.fast2sms.com/dev/api/send'

def send_sms(phone_number, message):
    headers = {
        'authorization': FAST2SMS_API_KEY,
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    params = {
        'sender_id': 'FSTSMS',
        'message': message,
        'language': 'english',
        'route': 'd',
        'numbers': phone_number
    }

    response = requests.post(FAST2SMS_URL, headers=headers, data=params)
    print(f"SMS Response: {response.status_code} - {response.text}")

@app.route('/')
def dash():
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()
    cursor.close()
    return render_template('dash.html', products=products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        gender = request.form['gender']
        mobile = request.form['mobile']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if password != confirm:
            flash('❌ Passwords do not match!')
        else:
            cursor = db.cursor(dictionary=True)
            cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
            if cursor.fetchone():
                flash('⚠️ Email already registered.')
            else:
                cursor.execute(
                    'INSERT INTO users (name, email, gender, mobile, password) VALUES (%s, %s, %s, %s, %s)',
                    (name, email, gender, mobile, password)
                )
                db.commit()
                flash('✅ Registration successful! Please login.')
                cursor.close()
                return redirect(url_for('login'))
            cursor.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = db.cursor(dictionary=True)
        cursor.execute('SELECT * FROM users WHERE email=%s AND password=%s', (email, password))
        user = cursor.fetchone()
        cursor.close()
        if user:
            session['user_id'] = user['id']
            session['email'] = email
            return redirect(url_for('board'))
        else:
            flash('❌ Invalid credentials. Please try again.')
    return render_template('login.html')

@app.route('/board')
def board():
    if 'user_id' not in session:
        flash("⚠️ Please login first.")
        return redirect(url_for('login'))
    return render_template('board.html')

@app.route('/orders')
def orders():
    if 'user_id' not in session:
        flash("⚠️ Please login first.")
        return redirect(url_for('login'))

    cursor = db.cursor(dictionary=True)
    cursor.execute('''
        SELECT orders.id, orders.status, products.price, orders.fullname,
               orders.address, orders.payment_method, products.title AS product_title
        FROM orders
        JOIN products ON orders.product_id = products.id
        WHERE orders.user_id = %s
    ''', (session['user_id'],))

    orders = cursor.fetchall()
    cursor.close()

    print("Fetched Orders:", orders)
    return render_template('orders.html', orders=orders)

@app.route('/seller', methods=['GET', 'POST'])
def seller():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        price = request.form['price']
        category = request.form['category']
        description = request.form['description']
        mobile = request.form['mobile']

        image_file = request.files['image']
        filename = ''
        if image_file:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image_file.save(image_path)

        seller_email = session['email']
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            'INSERT INTO products (title, price, category, description, image, seller_email, seller_mobile) VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (title, price, category, description, filename, seller_email, mobile)
        )
        db.commit()
        cursor.close()

        return render_template('seller_success.html')

    return render_template('seller.html')

@app.route('/buyer')
def buyer():
    search_query = request.args.get('search', '').lower()
    category_filter = request.args.get('category', 'all')

    cursor = db.cursor(dictionary=True)
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search_query:
        query += " AND LOWER(title) LIKE %s"
        params.append(f"%{search_query}%")

    if category_filter != 'all':
        query += " AND category = %s"
        params.append(category_filter)

    cursor.execute(query, params)
    products = cursor.fetchall()
    cursor.close()

    return render_template('buyer.html', products=products)

@app.route('/buynow/<int:product_id>', methods=['GET', 'POST'])
def buynow(product_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
    product = cursor.fetchone()
    cursor.close()

    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        address = request.form['address']
        payment_method = request.form['payment_method']

        
        card_number = request.form.get('card_number', '')
        expiry_date = request.form.get('expiry_date', '')
        cvv = request.form.get('cvv', '')
        upi_id = request.form.get('upi_id', '')

        
        cursor = db.cursor(dictionary=True)
        cursor.execute(
            'INSERT INTO orders (user_id, product_id, fullname, email, address, payment_method) VALUES (%s, %s, %s, %s, %s, %s)',
            (session['user_id'], product_id, fullname, email, address, payment_method)
        )
        db.commit()
        cursor.close()

        
        seller_mobile = product['seller_mobile']
        message = (
            f"Order Confirmed!\n"
            f"Product: {product['title']}\n"
            f"Buyer: {fullname}\n"
            f"Payment: {payment_method.upper()}"
        )
        send_sms(seller_mobile, message)
        print(f"Order confirmed for {product['title']} — SMS sent to {seller_mobile}")

        return render_template('order-success.html', product=product)

    return render_template('buynow.html', product=product)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dash.html')


if __name__ == '__main__':
    app.run(debug=True)
