from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os
import anthropic
import secrets
from flask_mail import Mail, Message

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Claude API 키 설정
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')

# 이메일 설정
app.config['MAIL_SERVER'] = 'smtp.example.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'your_email@example.com'
app.config['MAIL_PASSWORD'] = 'your_email_password'

mail = Mail(app)

# 데이터베이스 연결 및 초기화 함수
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    # email 열이 없는 경우 추가
    c.execute("PRAGMA table_info(users)")
    if 'email' not in [column[1] for column in c.fetchall()]:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT")

    # reset_token 열이 없는 경우 추가
    c.execute("PRAGMA table_info(users)")
    if 'reset_token' not in [column[1] for column in c.fetchall()]:
        c.execute("ALTER TABLE users ADD COLUMN reset_token TEXT")

    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT NOT NULL,
                 password TEXT NOT NULL,
                 email TEXT,
                 reset_token TEXT,
                 is_admin INTEGER NOT NULL DEFAULT 0)''')
    
    # deleted_at 열이 없는 경우 추가
    c.execute('''PRAGMA table_info(diaries)''')
    if 'deleted_at' not in [column[1] for column in c.fetchall()]:
        c.execute('''ALTER TABLE diaries ADD COLUMN deleted_at TEXT''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS diaries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER NOT NULL,
                 date TEXT NOT NULL,
                 content TEXT NOT NULL,
                 comment TEXT,
                 deleted_at TEXT,
                 FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    # 마스터 계정 생성
    c.execute("SELECT * FROM users WHERE username = 'master'")
    master_user = c.fetchone()
    if not master_user:
        c.execute("INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, ?)", ('master', 'master_password', 'master@example.com', 1))
    conn.commit()
    conn.close()

# 어드민 여부 확인 함수
def is_admin(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    is_admin_value = c.fetchone()[0]
    conn.close()
    return is_admin_value

# 예수님의 말씀 댓글 생성 함수
def generate_comment(diary_content):
    client = anthropic.Client(api_key=CLAUDE_API_KEY)

    prompt = f"\n\nHuman: 다음은 일기 내용입니다: {diary_content}\n당신은 예수님입니다. 이 일기에 대해 성경 말씀을 바탕으로 아주 따뜻한 위로와 격려의 말씀을 전해주세요.\n\nAssistant:"
    messages = [{"role": "user", "content": prompt}]
    
    response = client.messages.create(
        max_tokens=800, 
        messages=messages,
        model="claude-3-opus-20240229"
    )

    comment = ''.join([block.text for block in response.content])

    return comment

# 루트 URL
@app.route('/')
def index():
    return render_template('index.html')

# 로그인 라우트
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = c.fetchone()
        conn.close()
        if user:
            session['user_id'] = user[0]
            return redirect(url_for('diaries'))
        else:
            return "Invalid username or password"
    return render_template('login.html')

# 회원가입 라우트
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        if user:
            conn.close()
            return "이미 존재하는 아이디입니다."
        c.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, password, email))
        conn.commit()
        conn.close()
        return redirect(url_for('login'))
    return render_template('register.html')

# 일기 목록 라우트
@app.route('/diaries')
def diaries():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM diaries WHERE user_id = ? AND deleted_at IS NULL", (session['user_id'],))
    diaries = c.fetchall()
    conn.close()
    return render_template('diaries.html', diaries=diaries)

# 일기 작성 라우트
@app.route('/write', methods=['GET', 'POST'])
def write():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        date = request.form['date']
        content = request.form['content']
        comment = generate_comment(content)
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO diaries (user_id, date, content, comment) VALUES (?, ?, ?, ?)", (session['user_id'], date, content, comment))
        conn.commit()
        conn.close()
        return redirect(url_for('diaries'))
    return render_template('diary.html')

# 일기 수정 라우트
@app.route('/edit/<int:diary_id>', methods=['GET', 'POST'])
def edit(diary_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        date = request.form['date']
        content = request.form['content']
        comment = generate_comment(content)
        c.execute("UPDATE diaries SET date = ?, content = ?, comment = ? WHERE id = ?", (date, content, comment, diary_id))
        conn.commit()
        conn.close()
        return redirect(url_for('diaries'))
    c.execute("SELECT * FROM diaries WHERE id = ?", (diary_id,))
    diary = c.fetchone()
    conn.close()
    return render_template('edit.html', diary=diary)

# 일기 삭제 라우트
@app.route('/delete/<int:diary_id>')
def delete(diary_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE diaries SET deleted_at = datetime('now') WHERE id = ?", (diary_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('diaries'))

# 휴지통 라우트
@app.route('/trash')
def trash():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM diaries WHERE user_id = ? AND deleted_at IS NOT NULL AND DATE(deleted_at, '+30 days') > DATE('now')", (session['user_id'],))
    diaries = c.fetchall()
    conn.close()
    return render_template('trash.html', diaries=diaries)

# 일기 복구 라우트
@app.route('/recover/<int:diary_id>')
def recover(diary_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE diaries SET deleted_at = NULL WHERE id = ?", (diary_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('trash'))

# 30일이 지난 일기 자동 삭제 함수
def delete_old_diaries():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM diaries WHERE deleted_at IS NOT NULL AND DATE(deleted_at, '+30 days') <= DATE('now')")
    conn.commit()
    conn.close()

# 사용자 생성 라우트
@app.route('/admin/create', methods=['GET', 'POST'])
def create_user():
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        is_admin = 'is_admin' in request.form
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, email, is_admin) VALUES (?, ?, ?, ?)", (username, password, email, is_admin))
        conn.commit()
        conn.close()
        return redirect(url_for('admin'))
    return render_template('create_user.html')

# 사용자 수정 라우트
@app.route('/admin/edit/<int:user_id>', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        is_admin_value = 'is_admin' in request.form
        c.execute("UPDATE users SET username = ?, password = ?, email = ?, is_admin = ? WHERE id = ?", (username, password, email, is_admin_value, user_id))
        conn.commit()
        conn.close()
        return redirect(url_for('admin'))
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return render_template('edit_user.html', user=user)

# 사용자 삭제 라우트
@app.route('/admin/delete/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# 어드민 페이지 라우트
@app.route('/admin')
def admin():
    if 'user_id' not in session or not is_admin(session['user_id']):
        return render_template('no_permission.html')
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("""
        SELECT users.*, COUNT(diaries.id) AS diary_count
        FROM users
        LEFT JOIN diaries ON users.id = diaries.user_id AND diaries.deleted_at IS NULL
        GROUP BY users.id
    """)
    users = c.fetchall()
    conn.close()
    return render_template('admin.html', users=users)

# 비밀번호 변경 라우트
@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id = ? AND password = ?", (session['user_id'], current_password))
        user = c.fetchone()
        if user and new_password == confirm_password:
            c.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, session['user_id']))
            conn.commit()
            conn.close()
            return "비밀번호가 성공적으로 변경되었습니다."
        else:
            conn.close()
            return "현재 비밀번호가 일치하지 않거나 새 비밀번호와 확인 비밀번호가 일치하지 않습니다."
    return render_template('change_password.html')

# 비밀번호 재설정 요청 라우트
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        if user:
            reset_token = secrets.token_urlsafe(16)
            c.execute("UPDATE users SET reset_token = ? WHERE email = ?", (reset_token, email))
            conn.commit()
            conn.close()
            reset_url = url_for('reset_password', token=reset_token, _external=True)
            msg = Message('비밀번호 재설정 요청', sender='your_email@example.com', recipients=[email])
            msg.body = f'비밀번호를 재설정하려면 다음 링크를 클릭하세요: {reset_url}'
            mail.send(msg)
            return "비밀번호 재설정 링크가 이메일로 전송되었습니다."
        else:
                    conn.close()
                    return "해당 이메일로 가입된 사용자가 없습니다."
    return render_template('forgot_password.html')

# 비밀번호 재설정 라우트
@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if request.method == 'POST':
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        if new_password == confirm_password:
            conn = sqlite3.connect('database.db')
            c = conn.cursor()
            c.execute("UPDATE users SET password = ?, reset_token = NULL WHERE reset_token = ?", (new_password, token))
            conn.commit()
            conn.close()
            return "비밀번호가 성공적으로 재설정되었습니다."
        else:
            return "새 비밀번호와 확인 비밀번호가 일치하지 않습니다."
    return render_template('reset_password.html', token=token)

# 아이디 찾기 라우트
@app.route('/forgot_username', methods=['GET', 'POST'])
def forgot_username():
    if request.method == 'POST':
        email = request.form['email']
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("SELECT username FROM users WHERE email = ?", (email,))
        user = c.fetchone()
        conn.close()
        if user:
            username = user[0]
            return f"귀하의 아이디는 {username}입니다."
        else:
            return "해당 이메일로 가입된 아이디가 없습니다."
    return render_template('forgot_username.html')

if __name__ == '__main__':
    init_db()
    delete_old_diaries()
    app.run(host='0.0.0.0', port=8000, debug=True)
