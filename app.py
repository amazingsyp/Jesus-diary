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
    c.execute('''CREATE TABLE IF NOT EXISTS diaries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 user_id INTEGER NOT NULL,
                 date TEXT NOT NULL,
                 content TEXT NOT NULL,
                 comment TEXT,
                 FOREIGN KEY (user_id) REFERENCES users (id))''')
    # 마스터 계정 생성
    c.execute("SELECT * FROM users WHERE username = 'master'")
    master_user = c.fetchone()
    if not master_user:
        c.execute("INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)", ('master', 'master_password', 1))
    conn.commit()
    conn.close()

# 예수님의 말씀 댓글 생성 함수
def generate_comment(diary_content):
    client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
    
    system_prompt = "당신은 예수님입니다. 일기 내용과 관련하여 성경을 바탕으로 한 기독교적인 따뜻한 위로와 격려의 말씀을 해주세요."
    user_prompt = f"다음은 일기 내용입니다: {diary_content}\n이 일기에 대해 예수님께서 하실 말씀을 부탁드립니다."
    
    try:
        response = client.messages.create(
            model='claude-3-opus-20240229',
            max_tokens=1000,
            temperature=0.7,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ]
        )
        comment = response['content'].strip()
    except anthropic.APIError as e:
        print(f'API Error: {e}')
        comment = '예수님의 말씀을 생성하는 데 실패했습니다.'
    
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
    c.execute("SELECT * FROM diaries WHERE user_id = ?", (session['user_id'],))
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
    c.execute("DELETE FROM diaries WHERE id = ?", (diary_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('diaries'))

# 어드민 페이지 라우트
@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = c.fetchone()
    if not user[3]:
        return "접근 권한이 없습니다."
    c.execute("SELECT * FROM diaries")
    diaries = c.fetchall()
    conn.close()
    return render_template('admin.html', diaries=diaries)
if __name__ == '__main__':
    init_db()
    app.run(debug=True)