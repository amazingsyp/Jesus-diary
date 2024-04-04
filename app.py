from flask import url_for

from flask import Flask, render_template, request, redirect, session
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Claude API 키 설정
CLAUDE_API_KEY = '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'
CLAUDE_API_URL = 'https://api.anthropic.com/v1/complete'

# 데이터베이스 연결 및 초기화 함수
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 username TEXT NOT NULL,
                 password TEXT NOT NULL,
                 is_admin INTEGER NOT NULL DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS diaries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER NOT NULL,
                 date TEXT NOT NULL,
                 content TEXT NOT NULL,
                 comment TEXT,
                 FOREIGN KEY (user_id) REFERENCES users (id))''')
    conn.commit()
    conn.close()

# 예수님의 말씀 댓글 생성 함수
def generate_comment(diary_content):
    headers = {
        'Content-Type': 'application/json',
        'X-API-Key': CLAUDE_API_KEY
    }
    data = {
        'prompt': f'다음은 일기 내용입니다: {diary_content}\n이 일기에 대해 예수님께서 해주실 말씀을 성경 구절과 함께 작성해 주세요.',
        'model': 'claude-v1',
        'max_tokens_to_sample': 150,
        'temperature': 0.7
    }
    response = requests.post(CLAUDE_API_URL, headers=headers, json=data)
    result = response.json()
    comment = result['completion'].strip()
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
            return redirect(url_for('index'))
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

# 일기 작성 라우트
@app.route('/write', methods=['GET', 'POST'])
def write():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        date = request.form['date']
        content = request.form['content']
        comment = generate_comment(content)  # 예수님의 말씀 댓글 생성
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute("INSERT INTO diaries (user_id, date, content, comment) VALUES (?, ?, ?, ?)", (session['user_id'], date, content, comment))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('diary.html')

if __name__ == '__main__':
    init_db()
    app.run(debug=True)




@app.route('/diaries')
def diaries():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM diaries WHERE user_id = ?", (session['user_id'],))
    diaries = c.fetchall()
    conn.close()
    return render_template('diaries.html', diaries=diaries)





@app.route('/edit/<int:diary_id>', methods=['GET', 'POST'])
def edit(diary_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    if request.method == 'POST':
        date = request.form['date']
        content = request.form['content']
        comment = generate_comment(content)  # 예수님의 말씀 댓글 생성
        c.execute("UPDATE diaries SET date = ?, content = ?, comment = ? WHERE id = ?", (date, content, comment, diary_id))
        conn.commit()
        conn.close()
        return redirect(url_for('diaries'))
    c.execute("SELECT * FROM diaries WHERE id = ?", (diary_id,))
    diary = c.fetchone()
    conn.close()
    return render_template('edit.html', diary=diary)




@app.route('/delete/<int:diary_id>')
def delete(diary_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("DELETE FROM diaries WHERE id = ?", (diary_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('diaries'))


def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    # ... (기존 코드)
    # 마스터 계정 생성
    c.execute("SELECT * FROM users WHERE username = 'master'")
    master_user = c.fetchone()
    if not master_user:
        c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", ('master', 'master_password', 1))
        conn.commit()
    conn.close()


@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    if not user[3]:  # user[3]은 is_admin 열을 의미합니다.
        return "접근 권한이 없습니다."
    c.execute("SELECT * FROM diaries")
    diaries = c.fetchall()
    conn.close()
    return render_template('admin.html', diaries=diaries)


