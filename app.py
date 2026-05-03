from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
import requests
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'romeo_super_secret_key_2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, 'romeo_data.db')

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT, ip_address TEXT, country TEXT, city TEXT, visit_time TEXT)''')
            
    c.execute('''CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)''')
            
    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, platform_name TEXT, account_link TEXT, username_label TEXT)''')

    # السطرين دول بيعملوا تحديث ذكي لقاعدة البيانات عشان يضيفوا خانة المكان (location) من غير ما يمسحوا حساباتك القديمة
    c.execute("PRAGMA table_info(accounts)")
    columns = [col[1] for col in c.fetchall()]
    if 'location' not in columns:
        c.execute("ALTER TABLE accounts ADD COLUMN location TEXT DEFAULT 'bottom'")

    c.execute('SELECT COUNT(*) FROM admin')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO admin (username, password) VALUES (?, ?)', ('romeo', '123'))
        
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def home():
    visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    country, city = "Unknown", "Unknown"

    if visitor_ip and visitor_ip != '127.0.0.1':
        try:
            res = requests.get(f'http://ip-api.com/json/{visitor_ip}?fields=status,country,city').json()
            if res.get('status') == 'success':
                country, city = res.get('country'), res.get('city')
        except:
            pass

    visit_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('INSERT INTO visits (ip_address, country, city, visit_time) VALUES (?, ?, ?, ?)',
              (visitor_ip, country, city, visit_time))
              
    c.execute('SELECT * FROM accounts')
    my_accounts = c.fetchall()
    
    conn.commit()
    conn.close()

    return render_template('index.html', accounts=my_accounts)


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('SELECT username, password FROM admin WHERE id = 1')
        admin_data = c.fetchone()
        conn.close()

        if request.form['username'] != admin_data[0] or request.form['password'] != admin_data[1]:
            error = 'البيانات غلط، حاول تاني!'
        else:
            session['logged_in'] = True
            return redirect(url_for('admin_control'))
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin-control')
def admin_control():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    c = conn.cursor()
    c.execute('SELECT * FROM visits ORDER BY visit_time DESC')
    all_visits = c.fetchall()
    c.execute('SELECT username FROM admin WHERE id = 1')
    current_username = c.fetchone()['username']
    c.execute('SELECT * FROM accounts')
    all_accounts = c.fetchall()
    conn.close()
    
    return render_template('admin.html', visits=all_visits, current_username=current_username, accounts=all_accounts)

@app.route('/update-admin', methods=['POST'])
def update_admin():
    if session.get('logged_in'):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('UPDATE admin SET username = ?, password = ? WHERE id = 1', 
                  (request.form.get('new_username'), request.form.get('new_password')))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_control'))

@app.route('/add-account', methods=['POST'])
def add_account():
    if session.get('logged_in'):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        # ضفنا المكان (location) مع الحفظ
        c.execute('INSERT INTO accounts (platform_name, account_link, username_label, location) VALUES (?, ?, ?, ?)',
                  (request.form['platform'], request.form['link'], request.form['label'], request.form['location']))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_control'))

@app.route('/delete-account/<int:account_id>')
def delete_account(account_id):
    if session.get('logged_in'):
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
        conn.commit()
        conn.close()
    return redirect(url_for('admin_control'))

@app.route('/edit-account/<int:account_id>', methods=['GET', 'POST'])
def edit_account(account_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row 
    c = conn.cursor()
    
    if request.method == 'POST':
        c.execute('UPDATE accounts SET platform_name=?, account_link=?, username_label=?, location=? WHERE id=?',
                  (request.form['platform'], request.form['link'], request.form['label'], request.form['location'], account_id))
        conn.commit()
        conn.close()
        return redirect(url_for('admin_control'))
    
    c.execute('SELECT * FROM accounts WHERE id = ?', (account_id,))
    account = c.fetchone()
    conn.close()
    return render_template('edit_account.html', account=account)

if __name__ == '__main__':
    app.run(debug=True, port=8080)

