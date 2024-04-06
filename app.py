from flask import Flask, render_template, request, redirect, session, url_for
import sqlite3
import os
import anthropic

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Claude API 키 설정
CLAUDE_API_KEY = os.environ.get('CLAUDE_API_KEY')

# 데이터베이스 연결 및 초기화 함수
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT NOT NULL,
                 password TEXT NOT NULL,
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
        c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", ('master', 'master_password', 1))
    conn.commit()
    conn.close()


import sqlite3

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

    prompt = f"\n\nHuman: 다음은 일기 내용입니다: {diary_content}\n당신은 예수님입니다. 이 일기에 대해 성경 말씀을 바탕으로 따뜻한 위로와 격려의 말씀을 전해주세요.\n\nAssistant:"
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
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
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

# 30일이 지난 일기 자동 삭제 함수
def delete_old_diaries():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM diaries WHERE deleted_at IS NOT NULL AND DATE(deleted_at, '+30 days') <= DATE('now')")
    conn.commit()
    conn.close()

# 어드민 여부 확인 함수
def is_admin(user_id):
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
    is_admin = c.fetchone()[0]
    conn.close()
    return is_admin


# 사용자 생성 라우트
@app.route('/admin/create', methods=['GET', 'POST'])
def create_user():
    if 'user_id' not in session or not is_admin(session['user_id']):
        return redirect(url_for('login'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_admin = 'is_admin' in request.form
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", (username, password, is_admin))
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
        is_admin_value = 'is_admin' in request.form  # 여기를 수정했습니다
        c.execute("UPDATE users SET username = ?, password = ?, is_admin = ? WHERE id = ?", (username, password, is_admin_value, user_id))
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
    c.execute("SELECT * FROM users")
    users = c.fetchall()
    conn.close()
    return render_template('admin.html', users=users)




@app.route('/recover/<int:diary_id>', methods=['GET'])
def recover(diary_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("UPDATE diaries SET deleted_at = NULL WHERE id = ?", (diary_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('diaries'))


if __name__ == '__main__':
    init_db()
    delete_old_diaries()
    app.run(host='0.0.0.0', port=8000, debug=True)