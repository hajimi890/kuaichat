from flask import Flask, request, jsonify, render_template, g, send_file, send_from_directory
import sqlite3
import time
import os
import uuid
import hashlib
import hmac
import secrets
import re
import json as _json
import random
import urllib.request
import urllib.error

# 邮件服务（Resend）API 密钥：部署时通过环境变量 RESEND_API_KEY 提供，请勿硬编码
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
RESEND_FROM    = '快聊 <noreply@e.fastchat.cc.cd>'
RESEND_URL     = 'https://api.resend.com/emails'

app = Flask(__name__)


@app.errorhandler(Exception)
def _handle_uncaught(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return jsonify({'ok': False, 'error': e.description}), e.code
    app.logger.exception('Unhandled error')
    return jsonify({'ok': False, 'error': '服务器内部错误'}), 500


@app.before_request
def _process_scheduled_msgs():
    # 每次请求时顺便检查有没有到点的定时消息
    try:
        if request.path.startswith('/api/'):
            db = get_db()
            now = time.time()
            rows = db.execute("SELECT id, username, room, content FROM scheduled_msgs WHERE sent = 0 AND send_at <= ? LIMIT 10", (now,)).fetchall()
            for r in rows:
                try:
                    db.execute("INSERT INTO messages (room, sender, content, created_at) VALUES (?, ?, ?, ?)",
                               (r['room'], r['username'], r['content'], now))
                    db.execute("UPDATE scheduled_msgs SET sent = 1 WHERE id = ?", (r['id'],))
                except Exception:
                    pass
            if rows:
                db.commit()
    except Exception:
        pass


@app.after_request
def add_no_cache(resp):
    if resp.content_type and resp.content_type.startswith('text/html'):
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    return resp


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'kuaichat.db')
DOWNLOAD_DIR = os.path.join(BASE_DIR, 'downloads')
UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)
ONLINE_WINDOW = 30
MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
ALLOWED_VIDEO_EXTS = {'.mp4', '.webm', '.mov', '.m4v'}
ALLOWED_FILE_EXTS = {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
                     '.txt', '.md', '.csv', '.json', '.zip', '.rar', '.7z',
                     '.mp3', '.wav', '.m4a'}

TOKEN_TTL = 30 * 24 * 3600
LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW = 300
PWD_MIN_LEN = 6
PWD_MAX_LEN = 32

HUMAN_SECRET = secrets.token_hex(32)
_human_tokens = {}

# 管理后台密码：部署时通过环境变量 ADMIN_PASSWORD 提供，请勿硬编码
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
_admin_tokens = {}

LEVEL_LIMITS = {
    0: {'name': '入门', 'min': 0,   'max_file_mb': 5,  'max_video_mb': 10, 'max_groups': 3,  'max_group_members': 20},
    1: {'name': '进阶', 'min': 50,  'max_file_mb': 10, 'max_video_mb': 15, 'max_groups': 5,  'max_group_members': 50},
    2: {'name': '高级', 'min': 200, 'max_file_mb': 15, 'max_video_mb': 20, 'max_groups': 10, 'max_group_members': 100},
    3: {'name': '尊享', 'min': 500, 'max_file_mb': 20, 'max_video_mb': 30, 'max_groups': 20, 'max_group_members': 200},
}

PET_TYPES = {
    'cat':    {'name': '小猫', 'emoji': '🐱', 'img': 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f431.png'},
    'dog':    {'name': '小狗', 'emoji': '🐶', 'img': 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f436.png'},
    'rabbit': {'name': '兔子', 'emoji': '🐰', 'img': 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f430.png'},
    'panda':  {'name': '熊猫', 'emoji': '🐼', 'img': 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f43c.png'},
    'fox':    {'name': '狐狸', 'emoji': '🦊', 'img': 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f98a.png'},
    'dragon': {'name': '小龙', 'emoji': '🐲', 'img': 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/1f432.png'},
}

BAD_WORDS = [
    'sb', 's b', '煞笔', '傻逼', '沙比', '沙雕', '傻b', 'nmsl', '尼玛', '泥马', '尼马',
    'md', '妈的', '妈卖批', '妈批', '草泥马', '草泥馬', '操你', '草你', '草拟', '干你',
    'fuck', 'shit', 'asshole', 'bitch', 'dick', '智障', '弱智', '脑残', '滚蛋',
    '去死', '死全家', '你妈', '你爸', '你全家', '二百五', '傻子', '蠢货', '混蛋', '王八蛋',
    '狗东西', '狗日的', '扑街', '丢你', '卧槽', '我擦', '去你妈',
    '老冯没了', '死妈玩意', '受着呗', '那咋了', '普信女', '普信男',
]
EXACT_WORDS = ['乐子吧']
SOLO_WORDS = ['唐']

FREE_EMAIL_DOMAINS = {
    'qq.com', 'gmail.com', '163.com', '126.com', 'sina.com', 'sina.cn',
    'sohu.com', 'petalmail.com', 'huawei.com', 'outlook.com', 'hotmail.com',
    'live.com', 'foxmail.com', 'yeah.net', 'aliyun.com', '139.com',
    'wo.cn', '189.cn', 'icloud.com', 'me.com', 'yahoo.com', 'ymail.com',
}

DISPOSABLE_DOMAINS = {
    'temp-mail.org', '10minutemail.com', 'mail.tm', 'guerrillamail.com',
    'mailinator.com', 'yopmail.com', 'sharklasers.com', 'guerrillamailblock.com',
    'pokemail.net', 'spam4.me', 'temp-mail.io', 'tempmail.com', 'tempail.com',
    'throwawaymail.com', 'trashmail.com', 'maildrop.cc', 'getnada.com',
    'dispostable.com', 'mohmal.com', 'emailondeck.com', 'mintemail.com',
}


def _classify_email_domain(email):
    try:
        domain = email.split('@')[-1].lower().strip()
    except Exception:
        return 'unknown'
    if domain in FREE_EMAIL_DOMAINS:
        return 'free'
    if domain in DISPOSABLE_DOMAINS:
        return 'disposable'
    return 'unknown'


def _gen_invite_code(db):
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    for _ in range(30):
        c = ''.join(secrets.choice(alphabet) for _ in range(6))
        if not db.execute('SELECT 1 FROM applications WHERE invite_code = ?', (c,)).fetchone():
            return c
    return None


APP_INFO = {'name': '快聊', 'version': '1.8.0', 'tagline': '隐私至上 · 好友加密聊天'}


def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH, timeout=15)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()




# ==================== 宠物系统 ====================
def _pet_level(feed_count):
    return min(10, feed_count // 5)

@app.route('/api/pet/info')
def pet_info():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    username = (request.args.get('username') or me).strip()
    db = get_db()
    row = db.execute('SELECT pet_type, pet_name, pet_feed, pet_level FROM users WHERE username = ?', (username,)).fetchone()
    if not row: return jsonify({'ok': False, 'error': '用户不存在'}), 404
    ptype = row['pet_type'] or ''
    return jsonify({
        'ok': True, 'username': username,
        'pet_type': ptype, 'pet_name': row['pet_name'] or '',
        'pet_feed': row['pet_feed'] or 0, 'pet_level': row['pet_level'] or 0,
        'img': (PET_TYPES.get(ptype, {}).get('img') or '') if ptype else '',
        'emoji': (PET_TYPES.get(ptype, {}).get('emoji') or '') if ptype else '',
        'type_name': (PET_TYPES.get(ptype, {}).get('name') or '') if ptype else '',
        'all_types': PET_TYPES,
    })

@app.route('/api/pet/choose', methods=['POST'])
def pet_choose():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    ptype = (data.get('pet_type') or '').strip()
    if ptype not in PET_TYPES:
        return jsonify({'ok': False, 'error': '未知宠物类型'}), 400
    db = get_db()
    if db.execute('SELECT pet_type FROM users WHERE username = ?', (me,)).fetchone()['pet_type']:
        return jsonify({'ok': False, 'error': '你已经选过宠物了，不能更换'}), 400
    db.execute('UPDATE users SET pet_type = ? WHERE username = ?', (ptype, me))
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/pet/name', methods=['POST'])
def pet_name():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    newname = (data.get('pet_name') or '').strip()[:12]
    if not newname:
        return jsonify({'ok': False, 'error': '名字不能为空'}), 400
    cleaned, bad = clean_text(newname)
    if bad: newname = cleaned
    db = get_db()
    if not db.execute('SELECT pet_type FROM users WHERE username = ?', (me,)).fetchone()['pet_type']:
        return jsonify({'ok': False, 'error': '你还没有宠物'}), 400
    db.execute('UPDATE users SET pet_name = ? WHERE username = ?', (newname, me))
    db.commit()
    return jsonify({'ok': True})

@app.route('/api/pet/feed_legacy', methods=['POST'])
def pet_feed_legacy():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    target = (data.get('username') or me).strip()
    db = get_db()
    row = db.execute('SELECT pet_type, pet_feed FROM users WHERE username = ?', (target,)).fetchone()
    if not row or not row['pet_type']:
        return jsonify({'ok': False, 'error': '对方还没有宠物'}), 400
    is_self = (target == me)
    if not is_self:
        u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
        if (u['points'] or 0) < 1: return jsonify({'ok': False, 'error': '积分不足'}), 400
        db.execute('UPDATE users SET points = points - 1 WHERE username = ?', (me,))
        add_points(db, target, 1, me + ' 喂食')
    new_feed = (row['pet_feed'] or 0) + 1
    new_level = _pet_level(new_feed)
    old_level = _pet_level(row['pet_feed'] or 0)
    db.execute('UPDATE users SET pet_feed = ?, pet_level = ? WHERE username = ?', (new_feed, new_level, target))
    db.commit()
    msg = '宠物升级啦！Lv.' + str(new_level) if new_level > old_level else '喂食成功'
    return jsonify({'ok': True, 'feed': new_feed, 'level': new_level, 'message': msg})

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, last_seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS friends (user_a TEXT NOT NULL, user_b TEXT NOT NULL, created_at REAL NOT NULL, PRIMARY KEY (user_a, user_b));
            CREATE TABLE IF NOT EXISTS warnings (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, reason TEXT, is_read INTEGER DEFAULT 0, created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_warnings_user ON warnings(username, is_read);
            CREATE TABLE IF NOT EXISTS reports (id INTEGER PRIMARY KEY AUTOINCREMENT, reporter TEXT NOT NULL, target TEXT NOT NULL, reason TEXT NOT NULL, detail TEXT, email TEXT, chat_context TEXT, status TEXT DEFAULT 'pending', created_at REAL NOT NULL, handled_at REAL);
            CREATE INDEX IF NOT EXISTS idx_reports_target ON reports(target);
            CREATE TABLE IF NOT EXISTS shop_items(id TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price INTEGER NOT NULL, value TEXT);
            CREATE TABLE IF NOT EXISTS user_items(username TEXT NOT NULL, item_id TEXT NOT NULL, purchased_at REAL NOT NULL, PRIMARY KEY (username, item_id));
            CREATE TABLE IF NOT EXISTS gifts(id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT NOT NULL, receiver TEXT NOT NULL, item_id TEXT NOT NULL, name TEXT NOT NULL, icon TEXT, sent_at REAL NOT NULL, is_read INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS gifts_idx_receiver ON gifts(receiver);
            CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT NOT NULL, sender TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_room_id ON messages(room, id);
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT NOT NULL, created_at REAL NOT NULL, expires_at REAL NOT NULL, last_seen REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, owner TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS group_members (group_id INTEGER NOT NULL, username TEXT NOT NULL, joined_at REAL NOT NULL, PRIMARY KEY (group_id, username));
            CREATE TABLE IF NOT EXISTS moments (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, content TEXT, image_url TEXT, likes TEXT, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS moment_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, moment_id INTEGER NOT NULL, username TEXT NOT NULL, content TEXT NOT NULL, created_at REAL NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_moment_comments ON moment_comments(moment_id);
            CREATE TABLE IF NOT EXISTS group_announcements (group_id INTEGER PRIMARY KEY, content TEXT, updated_at REAL, updated_by TEXT);
            CREATE TABLE IF NOT EXISTS device_signup (device_id TEXT PRIMARY KEY, fingerprint TEXT, ip TEXT, username TEXT NOT NULL, signup_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS friend_requests (id INTEGER PRIMARY KEY AUTOINCREMENT, from_user TEXT NOT NULL, to_user TEXT NOT NULL, message TEXT, status TEXT NOT NULL DEFAULT 'pending', created_at REAL NOT NULL, handled_at REAL);
            CREATE TABLE IF NOT EXISTS mentions (id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER NOT NULL, room TEXT NOT NULL, mentioned_user TEXT NOT NULL, mentioned_by TEXT NOT NULL, created_at REAL NOT NULL, is_read INTEGER DEFAULT 0);
            CREATE TABLE IF NOT EXISTS points_log (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT NOT NULL, delta INTEGER NOT NULL, reason TEXT, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS email_codes (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, code TEXT NOT NULL, purpose TEXT DEFAULT 'login', expires_at REAL NOT NULL, used INTEGER DEFAULT 0, created_at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS applications (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL, message TEXT, status TEXT DEFAULT 'pending', invite_code TEXT, created_at REAL NOT NULL, handled_at REAL);
            CREATE INDEX IF NOT EXISTS idx_apps_status ON applications(status);
        ''')

        ucols = [r[1] for r in db.execute('PRAGMA table_info(users)').fetchall()]
        for col, typ in [('avatar', 'TEXT'), ('bio', 'TEXT'), ('password', 'TEXT'), ('pwd_salt', 'TEXT'), ('pwd_algo', 'TEXT')]:
            if col not in ucols:
                db.execute(f'ALTER TABLE users ADD COLUMN {col} {typ}')
        for col, typ, dft in [('theme', 'TEXT', "'default'"), ('bubble', 'TEXT', "'default'"), ('banned', 'INTEGER', '0'), ('muted_until', 'REAL', '0'), ('warning_count', 'INTEGER', '0')]:
            if col not in ucols:
                db.execute(f'ALTER TABLE users ADD COLUMN {col} {typ} DEFAULT {dft}')
        if 'invite_code' not in ucols:
            db.execute('ALTER TABLE users ADD COLUMN invite_code TEXT')
            db.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_invite_code ON users(invite_code) WHERE invite_code IS NOT NULL')
        if 'invited_by' not in ucols:
            db.execute('ALTER TABLE users ADD COLUMN invited_by TEXT')
        if 'points' not in ucols:
            db.execute('ALTER TABLE users ADD COLUMN points INTEGER DEFAULT 0')
        if 'gender' not in ucols:
            db.execute("ALTER TABLE users ADD COLUMN gender TEXT DEFAULT ''")
        if 'birthday' not in ucols:
            db.execute("ALTER TABLE users ADD COLUMN birthday TEXT DEFAULT ''")

        mcols = [r[1] for r in db.execute('PRAGMA table_info(messages)').fetchall()]
        if 'read_by' not in mcols:
            db.execute('ALTER TABLE messages ADD COLUMN read_by TEXT')
        if 'reply_to' not in mcols:
            db.execute('ALTER TABLE messages ADD COLUMN reply_to INTEGER')
        if 'deleted_by' not in mcols:
            db.execute('ALTER TABLE messages ADD COLUMN deleted_by TEXT')

        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["theme_sakura", "樱花粉", "theme", 100, "sakura"])
        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["theme_night", "星空夜", "theme", 150, "night"])
        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["theme_forest", "森林绿", "theme", 80, "forest"])
        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["bubble_cloud", "云朵", "bubble", 120, "cloud"])
        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["bubble_mini", "极简", "bubble", 60, "mini"])
        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["gift_rose", "玫瑰", "gift", 10, "fa-fan"])
        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["gift_cake", "蛋糕", "gift", 50, "fa-birthday-cake"])
        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["gift_diamond", "钻石", "gift", 200, "fa-gem"])
        db.execute('INSERT OR IGNORE INTO shop_items(id,name,category,price,value) VALUES (?,?,?,?,?)', ["gift_rocket", "火箭", "gift", 500, "fa-rocket"])
        db.commit()


def get_level(points):
    if points >= 500: return 3
    if points >= 200: return 2
    if points >= 50: return 1
    return 0


def get_privileges(points):
    level = get_level(points)
    limits = LEVEL_LIMITS[level]
    next_level = level + 1
    need = max(0, LEVEL_LIMITS[next_level]['min'] - points) if next_level in LEVEL_LIMITS else 0
    return {
        'points': points, 'level': level, 'level_name': limits['name'],
        'max_file_mb': limits['max_file_mb'], 'max_video_mb': limits['max_video_mb'],
        'max_groups': limits['max_groups'], 'max_group_members': limits['max_group_members'],
        'next_level_min': LEVEL_LIMITS.get(next_level, {}).get('min', 0),
        'points_to_next': need, 'all_levels': LEVEL_LIMITS,
    }


def gen_invite_code(db):
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    for _ in range(20):
        code = ''.join(secrets.choice(alphabet) for _ in range(6))
        if not db.execute('SELECT 1 FROM users WHERE invite_code = ?', (code,)).fetchone():
            return code
    return secrets.token_hex(4).upper()


def add_points(db, username, delta, reason=''):
    if not username or delta == 0: return
    db.execute('UPDATE users SET points = COALESCE(points, 0) + ? WHERE username = ?', (delta, username))
    db.execute('INSERT INTO points_log (username, delta, reason, created_at) VALUES (?, ?, ?, ?)', (username, delta, reason, time.time()))


PWD_ITERATIONS = 200_000


def hash_password_v2(password, salt_hex=None):
    if salt_hex is None: salt_hex = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt_hex), PWD_ITERATIONS)
    return dk.hex(), salt_hex


def hash_password_legacy(username, password):
    return hashlib.sha256(('kuaichat::v1::' + username + '::' + password).encode('utf-8')).hexdigest()


def verify_password(user_row, password):
    stored = user_row['password']
    if not stored: return False, False
    if user_row['pwd_algo'] == 'pbkdf2_sha256' and user_row['pwd_salt']:
        calc, _ = hash_password_v2(password, user_row['pwd_salt'])
        return hmac.compare_digest(calc, stored), False
    calc = hash_password_legacy(user_row['username'], password)
    ok = hmac.compare_digest(calc, stored)
    return ok, ok


def check_password_strength(password):
    if not isinstance(password, str): return False, '密码格式无效'
    if len(password) < PWD_MIN_LEN or len(password) > PWD_MAX_LEN:
        return False, f'密码长度需为 {PWD_MIN_LEN}-{PWD_MAX_LEN} 位'
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        return False, '密码必须同时包含字母和数字'
    return True, ''


def is_valid_username(name):
    if not name or len(name) > 60: return False, '长度需为 1-60 位'
    if re.match(r'^[\w\.\-\+]+@[\w\-]+\.[\w\.\-]+$', name): return True, ''
    if name.isdigit(): return False, '昵称不能是纯数字'
    if not re.search(r'[A-Za-z\u4e00-\u9fff]', name): return False, '昵称必须包含字母或汉字'
    if re.search(r'[<>"\'{}\[\]\\\/\|\`\~\!\@\#\$\%\^\&\*\(\)\+\=\;\:]', name): return False, '昵称包含不支持的字符'
    return True, ''


def _loose_pattern(w):
    chars = [re.escape(c) for c in w]
    return r'[\s\-\_\|\*\.\,\?\!\@\#\$\%\^\&\+\=\~`\'\"\(\)\[\]\{\}\<\>\/\\]*'.join(chars)


def clean_text(text):
    if not text: return text, False
    normalized = text.lower()
    norm = re.sub(r'[\s\-\_\|\*\.\,\?\!\@\#\$\%\^\&\+\=\~`\'\"\(\)\[\]\{\}\<\>\/\\]', '', normalized)
    hit = False
    for w in BAD_WORDS:
        if w and (w.lower() in normalized or w.lower() in norm): hit = True; break
    if not hit:
        for w in EXACT_WORDS:
            if w and (w.lower() in normalized or w.lower() in norm): hit = True; break
    if not hit:
        for w in SOLO_WORDS:
            if not w: continue
            pat = r'(?<![A-Za-z0-9\u4e00-\u9fff])' + re.escape(w) + r'(?![A-Za-z0-9\u4e00-\u9fff])'
            if re.search(pat, text): hit = True; break
    if not hit: return text, False
    cleaned = text
    for w in BAD_WORDS:
        if w: cleaned = re.sub(re.escape(w), '', cleaned, flags=re.IGNORECASE)
    for w in BAD_WORDS:
        if len(w) >= 2:
            try: cleaned = re.sub(_loose_pattern(w), '', cleaned, flags=re.IGNORECASE)
            except re.error: pass
    for w in EXACT_WORDS:
        if w:
            cleaned = re.sub(re.escape(w), '', cleaned, flags=re.IGNORECASE)
    return re.sub(r'\s{2,}', ' ', cleaned).strip(), True


def touch_user(db, username):
    db.execute('INSERT INTO users (username, last_seen) VALUES (?, ?) ON CONFLICT(username) DO UPDATE SET last_seen = excluded.last_seen', (username, time.time()))


def make_room(a, b): return '__'.join(sorted([a, b]))


def group_room(group_id): return f'group_{group_id}'


def parse_room(room):
    if not room: return None, None
    if room.startswith('group_'):
        try: return 'group', int(room[6:])
        except ValueError: return None, None
    parts = room.split('__')
    if len(parts) == 2: return 'private', parts
    return None, None


def are_friends(db, a, b):
    x, y = sorted([a, b])
    return db.execute('SELECT 1 FROM friends WHERE user_a = ? AND user_b = ?', (x, y)).fetchone() is not None


def is_group_member(db, group_id, username):
    return db.execute('SELECT 1 FROM group_members WHERE group_id = ? AND username = ?', (group_id, username)).fetchone() is not None


def get_group_info(db, group_id):
    row = db.execute('SELECT id, name, owner FROM groups WHERE id = ?', (group_id,)).fetchone()
    if not row: return None
    return {'id': row['id'], 'name': row['name'], 'owner': row['owner']}


def extract_mentions(text):
    if not text: return []
    found = re.findall(r'@([A-Za-z0-9_\u4e00-\u9fff]{1,20})', text)
    seen = set(); result = []
    for name in found:
        if name not in seen: seen.add(name); result.append(name)
    return result


def save_mentions(db, message_id, room, text, mentioned_by):
    names = extract_mentions(text)
    if not names: return
    now = time.time()
    for name in names:
        if name == mentioned_by: continue
        if not db.execute('SELECT 1 FROM users WHERE username = ?', (name,)).fetchone(): continue
        db.execute('INSERT INTO mentions (message_id, room, mentioned_user, mentioned_by, created_at) VALUES (?, ?, ?, ?, ?)', (message_id, room, name, mentioned_by, now))


def get_client_ip():
    fwd = request.headers.get('X-Forwarded-For', '')
    if fwd: return fwd.split(',')[0].strip()
    return request.remote_addr or 'unknown'


def check_device_and_ip(db, device_id, fingerprint, ip):
    if device_id:
        row = db.execute('SELECT username FROM device_signup WHERE device_id = ?', (device_id,)).fetchone()
        if row: return False, f"这台设备已经注册过账号「{row['username']}」了"
    if fingerprint:
        row = db.execute('SELECT username FROM device_signup WHERE fingerprint = ?', (fingerprint,)).fetchone()
        if row: return False, f"这台设备已经注册过账号「{row['username']}」了"
    if ip and ip != 'unknown':
        cutoff = time.time() - 86400
        cnt = db.execute('SELECT COUNT(*) AS c FROM device_signup WHERE ip = ? AND signup_at > ?', (ip, cutoff)).fetchone()['c']
        if cnt >= 2: return False, '当前网络下今天注册的账号太多了'
    return True, ''


def _verify_slide(duration_ms, points):
    if duration_ms < 500 or duration_ms > 15000: return False, '拖动时长异常'
    if not points or len(points) < 8: return False, '轨迹点太少'
    if points[0].get('x', 0) > 5: return False, '起点异常'
    if points[-1].get('x', 0) - points[0].get('x', 0) < 150: return False, '移动距离太短'
    speeds = []
    for i in range(1, len(points)):
        dx = points[i].get('x', 0) - points[i-1].get('x', 0)
        dt = points[i].get('t', 0) - points[i-1].get('t', 0)
        if dt > 0: speeds.append(abs(dx) / dt)
    if len(speeds) < 5: return False, '速度样本太少'
    avg = sum(speeds) / len(speeds)
    if avg == 0: return False, '速度为 0'
    cv = (sum((x - avg) ** 2 for x in speeds) / len(speeds)) ** 0.5 / avg
    if cv < 0.35: return False, '轨迹过于均匀'
    mid = len(speeds) // 2
    avg_f = sum(speeds[:mid]) / mid if mid else 0
    avg_b = sum(speeds[mid:]) / (len(speeds) - mid) if len(speeds) - mid else 0
    if avg_f <= 0 or avg_b <= 0: return False, '速度异常'
    if avg_b >= avg_f * 0.9: return False, '轨迹缺乏减速特征'
    if max(speeds) > 3.0: return False, '速度过快'
    pause = sum(1 for i in range(1, len(points)) if points[i].get('t', 0) - points[i-1].get('t', 0) > 80)
    if pause == 0: return False, '轨迹过于连续'
    return True, ''


def verify_human_token(token):
    if not token or '.' not in token: return False
    try: payload, sig = token.rsplit('.', 1); ts = int(payload)
    except (ValueError, TypeError): return False
    expected = hmac.new(HUMAN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected): return False
    if time.time() - ts > 600: return False
    if token not in _human_tokens: return False
    return True


def create_token(db, username):
    token = secrets.token_urlsafe(32)
    now = time.time()
    db.execute('INSERT INTO sessions (token, username, created_at, expires_at, last_seen) VALUES (?, ?, ?, ?, ?)', (token, username, now, now + TOKEN_TTL, now))
    return token


def get_session_user(token):
    if not token: return None
    db = get_db()
    row = db.execute('SELECT username, expires_at FROM sessions WHERE token = ?', (token,)).fetchone()
    if not row: return None
    if row['expires_at'] < time.time():
        db.execute('DELETE FROM sessions WHERE token = ?', (token,)); db.commit()
        return None
    return row['username']


def require_auth():
    token = ''
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '): token = auth[7:].strip()
    if not token: token = request.headers.get('X-Auth-Token', '').strip()
    if not token: token = (request.args.get('token') or '').strip()
    return get_session_user(token)


_login_attempts = {}


def check_login_rate(username):
    now = time.time()
    attempts = [t for t in _login_attempts.get(username, []) if now - t < LOGIN_WINDOW]
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        remaining = int(LOGIN_WINDOW - (now - attempts[0])) + 1
        _login_attempts[username] = attempts
        return False, remaining
    attempts.append(now)
    _login_attempts[username] = attempts
    return True, 0


@app.route('/')
def landing(): return render_template('landing.html', app=APP_INFO)


@app.route('/chat')
def chat(): return render_template('chat.html')


@app.route('/api/info')
def api_info(): return jsonify(APP_INFO)


@app.route('/api/human/verify', methods=['POST'])
def human_verify():
    data = request.get_json() or {}
    ok, err = _verify_slide(data.get('duration', 0), data.get('points', []))
    if not ok: return jsonify({'ok': False, 'error': err})
    ts = int(time.time())
    payload = f'{ts}'
    sig = hmac.new(HUMAN_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token = f'{payload}.{sig}'
    _human_tokens[token] = ts
    return jsonify({'ok': True, 'token': token})


@app.route('/download/<platform>')
def download(platform):
    mapping = {'android': 'kuaichat-android.apk', 'windows': '快聊Windows客户端打包包.zip'}
    if platform not in mapping: return jsonify({'ok': False, 'error': '不支持的平台'}), 404
    filepath = os.path.join(DOWNLOAD_DIR, mapping[platform])
    if not os.path.exists(filepath): return jsonify({'ok': False, 'error': '安装包尚未上传'}), 404
    mime = 'application/vnd.android.package-archive' if platform == 'android' else 'application/zip'
    return send_file(filepath, as_attachment=True, download_name=mapping[platform], mimetype=mime)


def _save_upload(f, allowed_exts, max_size, prefix):
    if f is None: return None, '未收到文件'
    ext = os.path.splitext(f.filename or '')[1].lower()
    if ext not in allowed_exts: return None, f'不支持的格式：{ext}'
    data = f.read()
    if not data: return None, '文件内容为空'
    if len(data) > max_size: return None, f'文件不能超过 {max_size // (1024*1024)}MB'
    filename = f"{prefix}_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), 'wb') as out: out.write(data)
    return '/uploads/' + filename, None


def _user_max_size(db, username, kind):
    u = db.execute('SELECT points FROM users WHERE username = ?', (username,)).fetchone()
    priv = get_privileges(u['points'] if u else 0)
    return priv['max_video_mb'] * 1024 * 1024 if kind == 'video' else priv['max_file_mb'] * 1024 * 1024


@app.route('/api/upload_legacy', methods=['POST'])
def upload_image_legacy():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    url, err = _save_upload(request.files.get('image'), ALLOWED_IMAGE_EXTS, MAX_IMAGE_SIZE, 'img')
    if err: return jsonify({'ok': False, 'error': err}), 400
    return jsonify({'ok': True, 'url': url})


@app.route('/api/upload_video_legacy', methods=['POST'])
def upload_video_legacy():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    max_size = _user_max_size(db, me, 'video')
    url, err = _save_upload(request.files.get('video'), ALLOWED_VIDEO_EXTS, max_size, 'vid')
    if err: return jsonify({'ok': False, 'error': err}), 400
    return jsonify({'ok': True, 'url': url})


@app.route('/api/upload_file', methods=['POST'])
def upload_file():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    max_size = _user_max_size(db, me, 'file')
    f = request.files.get('file')
    if f is None: return jsonify({'ok': False, 'error': '未收到文件'}), 400
    ext = os.path.splitext(f.filename or '')[1].lower()
    if ext not in ALLOWED_FILE_EXTS: return jsonify({'ok': False, 'error': f'不支持的格式：{ext}'}), 400
    data = f.read()
    if not data: return jsonify({'ok': False, 'error': '文件内容为空'}), 400
    if len(data) > max_size: return jsonify({'ok': False, 'error': f'文件不能超过 {max_size // (1024*1024)}MB'}), 413
    safe_name = re.sub(r'[^\w\u4e00-\u9fff\.\-]', '_', f.filename or 'file')[:60]
    filename = f"file_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}_{safe_name}"
    with open(os.path.join(UPLOAD_DIR, filename), 'wb') as out: out.write(data)
    return jsonify({'ok': True, 'url': '/uploads/' + filename, 'name': f.filename, 'size': len(data)})


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/api/profile', methods=['GET', 'POST'])
def profile():
    if request.method == 'POST':
        me = require_auth()
        if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        bio = (data.get('bio') or '').strip()[:80]
        avatar = (data.get('avatar') or '').strip()[:200]
        gender = (data.get('gender') or '').strip()
        birthday = (data.get('birthday') or '').strip()[:10]
        if gender not in ('', '男', '女', '保密'): gender = ''
        bio, _ = clean_text(bio)
        db = get_db()
        touch_user(db, me)
        db.execute('UPDATE users SET bio = ?, avatar = ?, gender = ?, birthday = ? WHERE username = ?', (bio, avatar, gender, birthday, me))
        db.commit()
        return jsonify({'ok': True})
    username = (request.args.get('username') or '').strip()
    if not username: return jsonify({'ok': False, 'error': '缺少参数'}), 400
    db = get_db()
    u = db.execute('SELECT username, bio, avatar, last_seen, points, level_frame, gender, birthday FROM users WHERE username = ?', (username,)).fetchone()
    if not u: return jsonify({'ok': False, 'error': '用户不存在'}), 404
    cutoff = time.time() - ONLINE_WINDOW
    me = require_auth()
    is_friend = are_friends(db, me, username) if me else False
    priv = get_privileges(u['points'] or 0)
    return jsonify({'ok': True, 'profile': {
        'username': u['username'], 'bio': u['bio'] or '', 'avatar': u['avatar'] or '',
        'online': (u['last_seen'] or 0) > cutoff, 'is_friend': is_friend,
        'level': priv['level'], 'level_name': priv['level_name'],
        'frame': u['level_frame'] or 'default',
    }})


@app.route('/api/avatar', methods=['POST'])
def upload_avatar():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    f = request.files.get('avatar')
    if f is None: return jsonify({'ok': False, 'error': '未收到头像'}), 400
    ext = os.path.splitext(f.filename or '')[1].lower()
    if ext not in ALLOWED_IMAGE_EXTS: return jsonify({'ok': False, 'error': '仅支持 jpg/png/gif/webp'}), 400
    data = f.read()
    if not data: return jsonify({'ok': False, 'error': '图片内容为空'}), 400
    if len(data) > MAX_IMAGE_SIZE: return jsonify({'ok': False, 'error': '头像不能超过 5MB'}), 413
    safe = ''.join(c for c in me if c.isalnum() or c in '-_')
    for oldf in os.listdir(UPLOAD_DIR):
        if oldf.startswith(f'avatar_{safe}.'):
            try: os.remove(os.path.join(UPLOAD_DIR, oldf))
            except OSError: pass
    filename = f'avatar_{safe}{ext}'
    with open(os.path.join(UPLOAD_DIR, filename), 'wb') as out: out.write(data)
    db = get_db()
    touch_user(db, me)
    db.execute('UPDATE users SET avatar = ? WHERE username = ?', (f'/uploads/{filename}', me))
    db.commit()
    return jsonify({'ok': True, 'url': '/uploads/' + filename})


@app.route('/api/invite/check')
def invite_check():
    code = (request.args.get('code') or '').strip().upper()
    if not code: return jsonify({'ok': False, 'error': '请输入邀请码'})
    db = get_db()
    r = db.execute('SELECT username FROM users WHERE invite_code = ?', (code,)).fetchone()
    if r: return jsonify({'ok': True, 'inviter': r['username']})
    return jsonify({'ok': False, 'error': '邀请码无效'})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    ok, err = is_valid_username(username)
    if not ok: return jsonify({'ok': False, 'error': err}), 400
    password = data.get('password') or ''
    db = get_db()
    row = db.execute('SELECT username, password, pwd_salt, pwd_algo FROM users WHERE username = ?', (username,)).fetchone()

    if not password:
        if row is None or not row['password']:
            invite_used = (data.get('invite_code') or '').strip().upper()
            inviter = None
            if invite_used == 'ADMIN2025':
                inviter = 'admin'
            elif invite_used:
                ir = db.execute('SELECT username FROM users WHERE invite_code = ?', (invite_used,)).fetchone()
                if ir: inviter = ir['username']
                else:
                    ar = db.execute("SELECT email FROM applications WHERE invite_code = ? AND status = 'approved'", (invite_used,)).fetchone()
                    if ar: inviter = 'admin'
            if inviter is None:
                return jsonify({'ok': False, 'error': '需要有效邀请码'}), 403
            db.execute('INSERT INTO users (username, last_seen, invite_code, invited_by, points) VALUES (?, ?, ?, ?, ?)',
                       (username, time.time(), gen_invite_code(db), inviter, 0))
            db.commit()
            return jsonify({'ok': True, 'need_setup': True, 'username': username})
        return jsonify({'ok': False, 'need_password': True, 'error': '该账号已设置密码'}), 401

    # ⭐ 先判断用户是否存在（新用户直接走注册流程，不受登录频率限制）
    if row is None or not row['password']:
        if row is None:
            invite_used = (data.get('invite_code') or '').strip().upper()
            inviter = None
            if invite_used == 'ADMIN2025': inviter = 'admin'
            elif invite_used:
                ir = db.execute('SELECT username FROM users WHERE invite_code = ?', (invite_used,)).fetchone()
                if ir: inviter = ir['username']
                else:
                    ar = db.execute("SELECT email FROM applications WHERE invite_code = ? AND status = 'approved'", (invite_used,)).fetchone()
                    if ar: inviter = 'admin'
            if inviter is None:
                return jsonify({'ok': False, 'error': '需要有效邀请码'}), 403
        touch_user(db, username); db.commit()
        return jsonify({'ok': True, 'need_setup': True, 'username': username})

    ok, need_upgrade = verify_password(row, password)
    if not ok: return jsonify({'ok': False, 'error': '密码错误'}), 401

    if need_upgrade:
        new_hash, new_salt = hash_password_v2(password)
        db.execute('UPDATE users SET password = ?, pwd_salt = ?, pwd_algo = ? WHERE username = ?', (new_hash, new_salt, 'pbkdf2_sha256', username))

    touch_user(db, username)
    token = create_token(db, username)
    db.commit()
    _login_attempts.pop(username, None)
    return jsonify({'ok': True, 'username': username, 'token': token, 'expires_in': TOKEN_TTL})


@app.route('/api/setup_password', methods=['POST'])
def setup_password():
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or len(username) > 60: return jsonify({'ok': False, 'error': '昵称无效'}), 400
    ok, err = check_password_strength(password)
    if not ok: return jsonify({'ok': False, 'error': err}), 400
    db = get_db()
    row = db.execute('SELECT password FROM users WHERE username = ?', (username,)).fetchone()
    if row and row['password']: return jsonify({'ok': False, 'error': '该账号已设置密码'}), 400
    new_hash, new_salt = hash_password_v2(password)
    exist = db.execute('SELECT username FROM users WHERE username = ?', (username,)).fetchone()
    if not exist:
        db.execute('INSERT INTO users (username, last_seen, invite_code, points) VALUES (?, ?, ?, 0)', (username, time.time(), gen_invite_code(db)))
    db.execute('UPDATE users SET password = ?, pwd_salt = ?, pwd_algo = ?, last_seen = ? WHERE username = ?',
               (new_hash, new_salt, 'pbkdf2_sha256', time.time(), username))
    db.commit()
    token = create_token(db, username)
    db.commit()
    return jsonify({'ok': True, 'username': username, 'token': token, 'expires_in': TOKEN_TTL})


@app.route('/api/logout', methods=['POST'])
def logout():
    token = ''
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '): token = auth[7:].strip()
    if not token: token = request.headers.get('X-Auth-Token', '').strip()
    if token:
        db = get_db(); db.execute('DELETE FROM sessions WHERE token = ?', (token,)); db.commit()
    return jsonify({'ok': True})


@app.route('/api/me')
def api_me():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '未登录'}), 401
    db = get_db()
    u = db.execute('SELECT username, invite_code, invited_by, points FROM users WHERE username = ?', (me,)).fetchone()
    if not u: return jsonify({'ok': False, 'error': '未登录'}), 401
    priv = get_privileges(u['points'] or 0)
    return jsonify({'ok': True, 'username': me, 'invite_code': u['invite_code'] or '', 'invited_by': u['invited_by'] or '', 'privileges': priv})


@app.route('/api/my_privileges')
def my_privileges():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    u = db.execute('SELECT username, invite_code, invited_by, points FROM users WHERE username = ?', (me,)).fetchone()
    if not u: return jsonify({'ok': False, 'error': '未登录'}), 401
    priv = get_privileges(u['points'] or 0)
    invited_count = db.execute('SELECT COUNT(*) AS c FROM users WHERE invited_by = ?', (me,)).fetchone()['c']
    return jsonify({'ok': True, 'username': me, 'invite_code': u['invite_code'] or '', 'invited_by': u['invited_by'] or '', 'invited_count': invited_count, 'privileges': priv})




@app.route('/api/rename', methods=['POST'])
def rename():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    new_name = (data.get('new_name') or '').strip()
    password = data.get('password') or ''
    ok, err = is_valid_username(new_name)
    if not ok: return jsonify({'ok': False, 'error': err}), 400
    if new_name == me: return jsonify({'ok': False, 'error': '新昵称与当前昵称相同'}), 400
    db = get_db()
    urow = db.execute('SELECT username, password, pwd_salt, pwd_algo FROM users WHERE username = ?', (me,)).fetchone()
    if not urow or not urow['password']: return jsonify({'ok': False, 'error': '账号异常'}), 401
    ok, _ = verify_password(urow, password)
    if not ok: return jsonify({'ok': False, 'error': '密码错误'}), 401
    if db.execute('SELECT 1 FROM users WHERE username = ?', (new_name,)).fetchone(): return jsonify({'ok': False, 'error': '该昵称已被占用'}), 409
    return jsonify({'ok': False, 'error': '改名功能暂时关闭'}), 400


@app.route('/api/contacts')
def contacts():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    touch_user(db, me); db.commit()
    cutoff = time.time() - ONLINE_WINDOW
    rows = db.execute('SELECT username, avatar, last_seen, level_frame FROM users WHERE username != ? ORDER BY last_seen DESC', (me,)).fetchall()
    users = []
    for r in rows:
        pending = db.execute("SELECT from_user FROM friend_requests WHERE status = 'pending' AND ((from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?))", (me, r['username'], r['username'], me)).fetchone()
        users.append({'username': r['username'], 'avatar': r['avatar'] or '', 'frame': r['level_frame'] or 'default', 'online': (r['last_seen'] or 0) > cutoff, 'is_friend': are_friends(db, me, r['username']), 'pending_from_me': bool(pending and pending['from_user'] == me), 'pending_to_me': bool(pending and pending['from_user'] != me)})
    return jsonify({'ok': True, 'users': users})


@app.route('/api/friends')
def friends_list():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db(); touch_user(db, me); db.commit()
    cutoff = time.time() - ONLINE_WINDOW
    rows = db.execute('SELECT user_a, user_b FROM friends WHERE user_a = ? OR user_b = ?', (me, me)).fetchall()
    result = []
    for r in rows:
        friend = r['user_b'] if r['user_a'] == me else r['user_a']
        u = db.execute('SELECT last_seen, avatar, level_frame FROM users WHERE username = ?', (friend,)).fetchone()
        lm = db.execute('SELECT content, created_at FROM messages WHERE room = ? ORDER BY id DESC LIMIT 1', (make_room(me, friend),)).fetchone()
        unread = db.execute("SELECT COUNT(*) AS c FROM messages WHERE room = ? AND sender = ? AND (read_by IS NULL OR read_by = '')", (make_room(me, friend), friend)).fetchone()['c']
        result.append({'username': friend, 'online': bool(u and (u['last_seen'] or 0) > cutoff), 'avatar': u['avatar'] if u else '', 'frame': (u['level_frame'] if u else 'default') or 'default', 'last_msg': lm['content'] if lm else None, 'last_time': lm['created_at'] if lm else None, 'unread': unread or 0})
    # 附加备注
    try:
        remark_rows = db.execute('SELECT peer, remark FROM friend_remarks WHERE owner = ?', (me,)).fetchall()
        remarks = {r['peer']: r['remark'] for r in remark_rows}
    except Exception:
        remarks = {}
    for r in result:
        r['remark'] = remarks.get(r['username'], '')

    result.sort(key=lambda x: (-(x['last_time'] or 0), x['username']))
    return jsonify({'ok': True, 'friends': result})


@app.route('/api/friend/request', methods=['POST'])
def friend_request():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    peer = (data.get('peer') or '').strip()
    msg = (data.get('message') or '').strip()[:80]
    if not peer or me == peer: return jsonify({'ok': False, 'error': '参数无效'}), 400
    db = get_db()
    if not db.execute('SELECT 1 FROM users WHERE username = ?', (peer,)).fetchone(): return jsonify({'ok': False, 'error': '用户不存在'}), 404
    if are_friends(db, me, peer): return jsonify({'ok': False, 'error': '你们已经是好友了'}), 400
    exist = db.execute("SELECT id, from_user FROM friend_requests WHERE status = 'pending' AND ((from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?))", (me, peer, peer, me)).fetchone()
    if exist:
        if exist['from_user'] == me: return jsonify({'ok': False, 'error': '已发送过请求'}), 400
        else: return jsonify({'ok': False, 'error': '对方已经给你发过请求'}), 400
    touch_user(db, me); touch_user(db, peer)
    cur = db.execute('INSERT INTO friend_requests (from_user, to_user, message, status, created_at) VALUES (?, ?, ?, ?, ?)', (me, peer, msg, 'pending', time.time()))
    db.commit()
    return jsonify({'ok': True, 'request_id': cur.lastrowid})


@app.route('/api/friend/requests')
def friend_requests_list():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db(); touch_user(db, me); db.commit()
    incoming = db.execute("SELECT id, from_user, message, created_at FROM friend_requests WHERE to_user = ? AND status = 'pending' ORDER BY created_at DESC", (me,)).fetchall()
    outgoing = db.execute("SELECT id, to_user, message, created_at FROM friend_requests WHERE from_user = ? AND status = 'pending' ORDER BY created_at DESC", (me,)).fetchall()
    in_list = [{'id': r['id'], 'username': r['from_user'], 'message': r['message'] or '', 'created_at': r['created_at']} for r in incoming]
    out_list = [{'id': r['id'], 'username': r['to_user'], 'message': r['message'] or '', 'created_at': r['created_at']} for r in outgoing]
    return jsonify({'ok': True, 'incoming': in_list, 'outgoing': out_list})


@app.route('/api/friend/request/accept', methods=['POST'])
def friend_request_accept():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: rid = int(data.get('request_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    req = db.execute("SELECT * FROM friend_requests WHERE id = ? AND to_user = ? AND status = 'pending'", (rid, me)).fetchone()
    if not req: return jsonify({'ok': False, 'error': '请求不存在或已处理'}), 404
    a, b = sorted([req['from_user'], req['to_user']])
    db.execute('INSERT OR IGNORE INTO friends (user_a, user_b, created_at) VALUES (?, ?, ?)', (a, b, time.time()))
    db.execute("UPDATE friend_requests SET status = 'accepted', handled_at = ? WHERE id = ?", (time.time(), rid))
    add_points(db, me, 5, f'与 {req["from_user"]} 成为好友')
    db.commit()
    return jsonify({'ok': True, 'friend': req['from_user']})


@app.route('/api/friend/request/reject', methods=['POST'])
def friend_request_reject():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: rid = int(data.get('request_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    db.execute("UPDATE friend_requests SET status = 'rejected', handled_at = ? WHERE id = ? AND to_user = ?", (time.time(), rid, me))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/friend/request/cancel', methods=['POST'])
def friend_request_cancel():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: rid = int(data.get('request_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    db.execute("DELETE FROM friend_requests WHERE id = ? AND from_user = ? AND status = 'pending'", (rid, me))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/friend/delete', methods=['POST'])
def friend_delete():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    peer = (data.get('peer') or '').strip()
    if not peer or peer == me: return jsonify({'ok': False, 'error': '参数无效'}), 400
    a, b = sorted([me, peer])
    db = get_db()
    db.execute('DELETE FROM friends WHERE user_a = ? AND user_b = ?', (a, b))
    db.execute('DELETE FROM messages WHERE room = ?', (make_room(me, peer),))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/history')
def history():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    room = (request.args.get('room') or '').strip()
    try: limit = int(request.args.get('limit', 60))
    except ValueError: limit = 60
    if not room: return jsonify({'ok': False, 'error': '缺少参数'}), 400
    typ, data2 = parse_room(room)
    if typ != 'private' or me not in data2: return jsonify({'ok': False, 'error': '无效房间'}), 400
    other = data2[0] if data2[1] == me else data2[1]
    db = get_db()
    if not are_friends(db, me, other): return jsonify({'ok': False, 'error': '不是好友'}), 403
    rows = db.execute('SELECT id, sender, content, created_at, read_by, reply_to, deleted_by FROM messages WHERE room = ? ORDER BY id DESC LIMIT ?', (room, limit)).fetchall()
    msgs = []
    for r in reversed(rows):
        if r['deleted_by'] and me in (r['deleted_by'] or '').split(','): continue
        m = {'id': r['id'], 'sender': r['sender'], 'content': r['content'], 'created_at': r['created_at'], 'read_by': r['read_by'], 'reply_to': r['reply_to']}
        if r['reply_to']:
            q = db.execute('SELECT sender, content FROM messages WHERE id = ?', (r['reply_to'],)).fetchone()
            if q: m['reply_sender'] = q['sender']; m['reply_content'] = q['content'][:60]
        msgs.append(m)
    return jsonify({'ok': True, 'messages': msgs})


@app.route('/api/send', methods=['POST'])
def send():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    room = (data.get('room') or '').strip()
    content = (data.get('content') or '').strip()
    reply_to = data.get('reply_to')
    if not room or not content: return jsonify({'ok': False, 'error': '参数不完整'}), 400
    if len(content) > 2000: return jsonify({'ok': False, 'error': '消息过长'}), 400
    typ, data2 = parse_room(room)
    if typ != 'private' or me not in data2: return jsonify({'ok': False, 'error': '无效房间'}), 400
    other = data2[0] if data2[1] == me else data2[1]
    db = get_db()
    if not are_friends(db, me, other): return jsonify({'ok': False, 'error': '对方不是你的好友'}), 403
    urow = db.execute('SELECT banned, muted_until FROM users WHERE username = ?', (me,)).fetchone()
    if urow and urow['banned']: return jsonify({'ok': False, 'error': '账号已被封禁'}), 403
    if urow and (urow['muted_until'] or 0) > time.time(): return jsonify({'ok': False, 'error': '你被禁言中'}), 403
    touch_user(db, me)
    is_special = content.startswith('{') and ('"type"' in content)
    filtered, hit_bad = (content, False) if is_special else clean_text(content)
    if hit_bad:
        if not filtered: filtered = '（消息含不当内容，已屏蔽）'
        cur = db.execute('INSERT INTO messages (room, sender, content, created_at, reply_to) VALUES (?, ?, ?, ?, ?)', (room, me, filtered, time.time(), reply_to))
        db.commit()
        return jsonify({'ok': True, 'id': cur.lastrowid, 'filtered': True, 'warning': '文明发言', 'content': filtered})
    cur = db.execute('INSERT INTO messages (room, sender, content, created_at, reply_to) VALUES (?, ?, ?, ?, ?)', (room, me, content, time.time(), reply_to))
    mid = cur.lastrowid
    if not is_special: save_mentions(db, mid, room, content, me)
    db.commit()
    # 触发推送
    try:
        pf = app.config.get('push_new_message')
        if pf: pf(room, me, content[:60] if isinstance(content, str) else '[消息]')
    except Exception as _e:
        print('[push invoke err]', _e)
    return jsonify({'ok': True, 'id': mid})


@app.route('/api/read', methods=['POST'])
def mark_read():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    room = (data.get('room') or '').strip()
    typ, data2 = parse_room(room)
    if typ != 'private' or me not in data2: return jsonify({'ok': False, 'error': '无效房间'}), 400
    db = get_db()
    cur = db.execute("UPDATE messages SET read_by = ? WHERE room = ? AND sender != ? AND (read_by IS NULL OR read_by = '')", (me, room, me))
    db.commit()
    return jsonify({'ok': True, 'read': cur.rowcount})


@app.route('/api/poll')
def poll():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    room = (request.args.get('room') or '').strip()
    try: since = int(request.args.get('since', 0))
    except ValueError: since = 0
    typ, data2 = parse_room(room)
    if typ != 'private' or me not in data2: return jsonify({'ok': False, 'error': '无效房间'}), 400
    other = data2[0] if data2[1] == me else data2[1]
    db = get_db()
    if not are_friends(db, me, other): return jsonify({'ok': False, 'error': '不是好友'}), 403
    touch_user(db, me); db.commit()
    rows = db.execute('SELECT id, sender, content, created_at, read_by, reply_to, deleted_by FROM messages WHERE room = ? AND id > ? ORDER BY id ASC LIMIT 100', (room, since)).fetchall()
    msgs = []
    for r in rows:
        if r['deleted_by'] and me in (r['deleted_by'] or '').split(','): continue
        m = {'id': r['id'], 'sender': r['sender'], 'content': r['content'], 'created_at': r['created_at'], 'read_by': r['read_by'], 'reply_to': r['reply_to']}
        if r['reply_to']:
            q = db.execute('SELECT sender, content FROM messages WHERE id = ?', (r['reply_to'],)).fetchone()
            if q: m['reply_sender'] = q['sender']; m['reply_content'] = q['content'][:60]
        msgs.append(m)
    read_ids = [r['id'] for r in db.execute("SELECT id FROM messages WHERE room = ? AND sender = ? AND read_by IS NOT NULL AND read_by != '' AND id <= ?", (room, me, since)).fetchall()]
    return jsonify({'ok': True, 'messages': msgs, 'read_ids': read_ids})


@app.route('/api/retract', methods=['POST'])
def retract():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    room = (data.get('room') or '').strip()
    try: mid = int(data.get('id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数无效'}), 400
    db = get_db()
    row = db.execute('SELECT sender, created_at FROM messages WHERE id = ? AND room = ?', (mid, room)).fetchone()
    if not row: return jsonify({'ok': False, 'error': '消息不存在'}), 404
    if row['sender'] != me: return jsonify({'ok': False, 'error': '只能撤回自己的消息'}), 403
    if time.time() - row['created_at'] > 120: return jsonify({'ok': False, 'error': '超过 2 分钟'}), 400
    db.execute('UPDATE messages SET content = ? WHERE id = ?', ('【该消息已撤回】', mid))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/message/delete', methods=['POST'])
def message_delete():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: mid = int(data.get('id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数无效'}), 400
    db = get_db()
    row = db.execute('SELECT sender, deleted_by FROM messages WHERE id = ?', (mid,)).fetchone()
    if not row: return jsonify({'ok': False, 'error': '消息不存在'}), 404
    if row['sender'] == me: db.execute('DELETE FROM messages WHERE id = ?', (mid,))
    else:
        existing = (row['deleted_by'] or '').split(',') if row['deleted_by'] else []
        existing = [x for x in existing if x]
        if me not in existing: existing.append(me)
        db.execute('UPDATE messages SET deleted_by = ? WHERE id = ?', (','.join(existing), mid))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/share', methods=['POST'])
def share():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    target_type = (data.get('target_type') or '').strip()
    target_id = (data.get('target_id') or '').strip()
    share_content = (data.get('share_content') or '').strip()[:1000]
    share_title = (data.get('share_title') or '').strip()[:80]
    if not target_type or not target_id: return jsonify({'ok': False, 'error': '参数不完整'}), 400
    db = get_db(); touch_user(db, me)
    payload = {'type': 'share', 'share_type': 'text', 'title': share_title or '分享内容', 'content': share_content, 'from': me, 'shared_at': time.time()}
    content = _json.dumps(payload, ensure_ascii=False)
    if target_type == 'user':
        if not are_friends(db, me, target_id): return jsonify({'ok': False, 'error': '对方不是你的好友'}), 403
        room = make_room(me, target_id)
    elif target_type == 'group':
        try: gid = int(target_id)
        except ValueError: return jsonify({'ok': False, 'error': '群 ID 无效'}), 400
        if not is_group_member(db, gid, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
        room = group_room(gid)
    else: return jsonify({'ok': False, 'error': '目标类型无效'}), 400
    cur = db.execute('INSERT INTO messages (room, sender, content, created_at) VALUES (?, ?, ?, ?)', (room, me, content, time.time()))
    db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'room': room})


@app.route('/api/shop/items')
def shop_items():
    me = require_auth()
    db = get_db()
    items = [dict(i) for i in db.execute('SELECT * FROM shop_items').fetchall()]

    # 把头像框也当成商品塞进去
    for f in FRAMES_CONFIG:
        if f['id'] == 'default':
            continue
        items.append({
            'id': 'frame_' + f['id'],
            'name': f['name'] + '头像框',
            'category': 'frame',
            'price': f['price'],
            'value': f['id'],
            'icon': 'fa-portrait',
            'style': f['style'],
            'min_level': f['min_level'],
        })

    owned = []
    user = None
    current_frame = 'default'
    if me:
        owned = [r['item_id'] for r in db.execute('SELECT item_id FROM user_items WHERE username = ?', (me,)).fetchall()]
        # 加上已购买的头像框
        try:
            frames_owned = [('frame_' + r['frame_id']) for r in db.execute('SELECT frame_id FROM user_frames WHERE username = ?', (me,)).fetchall()]
            owned = owned + frames_owned
        except Exception:
            pass
        user = db.execute('SELECT theme, bubble, points, level_frame FROM users WHERE username = ?', (me,)).fetchone()
        if user and user['level_frame']:
            current_frame = user['level_frame']

    return jsonify(
        ok=True,
        items=items,
        owned=owned,
        theme=(user['theme'] if user and user['theme'] else 'default'),
        bubble=(user['bubble'] if user and user['bubble'] else 'default'),
        frame=current_frame,
        points=(user['points'] if user else 0)
    )


@app.route('/api/shop/buy', methods=['POST'])
def shop_buy():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    item_id = (data.get('item_id') or '').strip()

    # ⭐ 头像框特殊处理
    if item_id.startswith('frame_'):
        fid = item_id[6:]
        frame = None
        for f in FRAMES_CONFIG:
            if f['id'] == fid:
                frame = f
                break
        if not frame: return jsonify({'ok': False, 'error': '头像框不存在'}), 404
        if frame['price'] <= 0: return jsonify({'ok': False, 'error': '该头像框免费'}), 400
        db = get_db()
        if db.execute('SELECT 1 FROM user_frames WHERE username = ? AND frame_id = ?', (me, fid)).fetchone():
            return jsonify({'ok': False, 'error': '已经拥有该头像框'}), 400
        u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
        pts = (u['points'] if u else 0) or 0
        if pts < frame['price']: return jsonify({'ok': False, 'error': '积分不足'}), 400
        db.execute('UPDATE users SET points = points - ? WHERE username = ?', (frame['price'], me))
        db.execute('INSERT INTO user_frames (username, frame_id, purchased_at) VALUES (?, ?, ?)', (me, fid, time.time()))
        add_points(db, me, 0, f"购买头像框 {frame['name']}")
        db.commit()
        return jsonify({'ok': True, 'item': {'id': item_id, 'name': frame['name'] + '头像框', 'price': frame['price']}})

    db = get_db()
    item = db.execute('SELECT * FROM shop_items WHERE id = ?', (item_id,)).fetchone()
    if not item: return jsonify({'ok': False, 'error': '商品不存在'}), 404
    if item['category'] == 'gift': return jsonify({'ok': False, 'error': '礼物请在聊天中送给好友'}), 400
    if db.execute('SELECT 1 FROM user_items WHERE username = ? AND item_id = ?', (me, item_id)).fetchone():
        return jsonify({'ok': False, 'error': '已经拥有该物品'}), 400
    u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
    pts = (u['points'] if u else 0) or 0
    if pts < item['price']: return jsonify({'ok': False, 'error': '积分不足'}), 400
    db.execute('UPDATE users SET points = points - ? WHERE username = ?', (item['price'], me))
    db.execute('INSERT OR IGNORE INTO user_items(username, item_id, purchased_at) VALUES (?, ?, ?)', (me, item_id, time.time()))
    db.execute('INSERT INTO points_log(username, delta, reason, created_at) VALUES (?, ?, ?, ?)', (me, -item['price'], f"购买{item['name']}", time.time()))
    db.commit()
    return jsonify({'ok': True, 'item': dict(item)})


@app.route('/api/shop/equip', methods=['POST'])
def shop_equip():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    item_id = (data.get('item_id') or '').strip()

    # ⭐ 头像框特殊处理
    if item_id.startswith('frame_'):
        fid = item_id[6:]
        frame = None
        for f in FRAMES_CONFIG:
            if f['id'] == fid:
                frame = f
                break
        if not frame: return jsonify({'ok': False, 'error': '头像框不存在'}), 404
        db = get_db()
        u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
        pts = (u['points'] if u else 0) or 0
        priv = get_privileges(pts)
        if priv['level'] < frame['min_level']:
            return jsonify({'ok': False, 'error': '需要等级 Lv.' + str(frame['min_level']) + ' 才能解锁'}), 403
        if frame['price'] > 0:
            if not db.execute('SELECT 1 FROM user_frames WHERE username = ? AND frame_id = ?', (me, fid)).fetchone():
                return jsonify({'ok': False, 'error': '你还没有购买此头像框'}), 403
        db.execute('UPDATE users SET level_frame = ? WHERE username = ?', (fid, me))
        db.commit()
        return jsonify({'ok': True})

    db = get_db()
    if item_id in ('', 'default'):
        db.execute("UPDATE users SET theme = 'default', bubble = 'default' WHERE username = ?", (me,))
        db.commit()
        return jsonify({'ok': True})
    item = db.execute('SELECT * FROM shop_items WHERE id = ?', (item_id,)).fetchone()
    if not item: return jsonify({'ok': False, 'error': '商品不存在'}), 404
    if not db.execute('SELECT 1 FROM user_items WHERE username = ? AND item_id = ?', (me, item_id)).fetchone():
        return jsonify({'ok': False, 'error': '你尚未购买此物品'}), 403
    if item['category'] == 'theme': db.execute('UPDATE users SET theme = ? WHERE username = ?', (item['value'], me))
    elif item['category'] == 'bubble': db.execute('UPDATE users SET bubble = ? WHERE username = ?', (item['value'], me))
    else: return jsonify({'ok': False, 'error': '该物品不可装备'}), 400
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/gift/send', methods=['POST'])
def gift_send():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    peer = (data.get('peer') or '').strip()
    item_id = (data.get('item_id') or '').strip()
    if not peer or not item_id: return jsonify({'ok': False, 'error': '参数不全'}), 400
    db = get_db()
    if not are_friends(db, me, peer): return jsonify({'ok': False, 'error': '不是好友'}), 403
    item = db.execute('SELECT * FROM shop_items WHERE id = ?', (item_id,)).fetchone()
    if not item or item['category'] != 'gift': return jsonify({'ok': False, 'error': '礼物不存在'}), 404
    u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
    pts = (u['points'] if u else 0) or 0
    if pts < item['price']: return jsonify({'ok': False, 'error': '积分不足'}), 400
    db.execute('UPDATE users SET points = points - ? WHERE username = ?', (item['price'], me))
    db.execute('INSERT INTO points_log(username, delta, reason, created_at) VALUES (?, ?, ?, ?)', (me, -item['price'], f"送给{peer}礼物{item['name']}", time.time()))
    db.execute('INSERT INTO gifts(sender, receiver, item_id, name, icon, sent_at, is_read) VALUES (?, ?, ?, ?, ?, ?, 0)', (me, peer, item_id, item['name'], item['value'], time.time()))
    payload = {'type': 'gift', 'item_id': item_id, 'name': item['name'], 'icon': item['value'], 'price': item['price'], 'sender': me}
    content = _json.dumps(payload, ensure_ascii=False)
    cur = db.execute('INSERT INTO messages(room, sender, content, created_at) VALUES (?, ?, ?, ?)', (make_room(me, peer), me, content, time.time()))
    db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid, 'message': '礼物已送出'})


@app.route('/api/gifts/unread')
def gifts_unread():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '未登录'}), 401
    db = get_db()
    rows = db.execute('SELECT id, sender, item_id, name, icon, sent_at FROM gifts WHERE receiver = ? AND is_read = 0', (me,)).fetchall()
    return jsonify({'ok': True, 'gifts': [dict(r) for r in rows]})


@app.route('/api/gifts/read', methods=['POST'])
def gifts_read():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    ids = data.get('ids', [])
    if not ids: return jsonify({'ok': True})
    try:
        qs = ','.join('?' * len(ids))
        db = get_db(); db.execute(f'UPDATE gifts SET is_read = 1 WHERE id IN ({qs})', ids); db.commit()
    except (TypeError, ValueError): pass
    return jsonify({'ok': True})


@app.route('/api/warnings')
def warnings_list():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    rows = db.execute('SELECT id, reason, created_at FROM warnings WHERE username = ? AND is_read = 0 ORDER BY id ASC', (me,)).fetchall()
    return jsonify({'ok': True, 'warnings': [dict(r) for r in rows]})


@app.route('/api/warnings/read', methods=['POST'])
def warnings_read():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    ids = data.get('ids') or []
    db = get_db()
    if ids:
        for wid in ids:
            try: db.execute('UPDATE warnings SET is_read = 1 WHERE id = ? AND username = ?', (int(wid), me))
            except (TypeError, ValueError): pass
    else: db.execute('UPDATE warnings SET is_read = 1 WHERE username = ?', (me,))
    db.commit()
    return jsonify({'ok': True})


# ==================== 群聊 ====================
@app.route('/api/group/create', methods=['POST'])
def group_create():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()[:30]
    members = data.get('members') or []
    if not name: return jsonify({'ok': False, 'error': '群名不能为空'}), 400
    db = get_db()
    u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
    priv = get_privileges(u['points'] if u else 0)
    cnt = db.execute('SELECT COUNT(*) AS c FROM groups WHERE owner = ?', (me,)).fetchone()['c']
    if cnt >= priv['max_groups']: return jsonify({'ok': False, 'error': f'最多创建 {priv["max_groups"]} 个群'}), 403
    now = time.time()
    cur = db.execute('INSERT INTO groups (name, owner, created_at) VALUES (?, ?, ?)', (name, me, now))
    group_id = cur.lastrowid
    db.execute('INSERT OR IGNORE INTO group_members (group_id, username, joined_at) VALUES (?, ?, ?)', (group_id, me, now))
    invited = []
    for m in members:
        m = (m or '').strip()
        if not m or m == me: continue
        if not are_friends(db, me, m): continue
        db.execute('INSERT OR IGNORE INTO group_members (group_id, username, joined_at) VALUES (?, ?, ?)', (group_id, m, now))
        invited.append(m)
    add_points(db, me, 10, f'创建群「{name}」')
    db.commit()
    return jsonify({'ok': True, 'group': {'id': group_id, 'name': name, 'owner': me, 'members': invited}})


@app.route('/api/group/list')
def group_list():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    rows = db.execute('''SELECT g.id, g.name, g.owner, (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) AS member_count, (SELECT MAX(id) FROM messages WHERE room = 'group_' || g.id) AS last_msg_id FROM groups g JOIN group_members gm ON gm.group_id = g.id WHERE gm.username = ? ORDER BY last_msg_id DESC NULLS LAST''', (me,)).fetchall()
    result = []
    for r in rows:
        gid = r['id']
        lm = db.execute('SELECT content, created_at, sender FROM messages WHERE room = ? ORDER BY id DESC LIMIT 1', (group_room(gid),)).fetchone()
        result.append({'id': gid, 'name': r['name'], 'owner': r['owner'], 'member_count': r['member_count'], 'last_msg': lm['content'] if lm else None, 'last_sender': lm['sender'] if lm else None, 'last_time': lm['created_at'] if lm else None})
    return jsonify({'ok': True, 'groups': result})


@app.route('/api/group/info')
def group_info():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    try: gid = int(request.args.get('group_id', 0))
    except ValueError: return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    if not is_group_member(db, gid, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
    info = get_group_info(db, gid)
    if not info: return jsonify({'ok': False, 'error': '群不存在'}), 404
    members = db.execute('SELECT gm.username, u.avatar, u.last_seen, u.level_frame FROM group_members gm LEFT JOIN users u ON u.username = gm.username WHERE gm.group_id = ? ORDER BY gm.joined_at ASC', (gid,)).fetchall()
    cutoff = time.time() - ONLINE_WINDOW
    member_list = [{'username': m['username'], 'avatar': m['avatar'] or '', 'frame': m['level_frame'] or 'default', 'online': (m['last_seen'] or 0) > cutoff} for m in members]
    return jsonify({'ok': True, 'group': {'id': info['id'], 'name': info['name'], 'owner': info['owner'], 'members': member_list}})


@app.route('/api/group/add', methods=['POST'])
def group_add():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: gid = int(data.get('group_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    peer = (data.get('peer') or '').strip()
    if not peer: return jsonify({'ok': False, 'error': '缺少成员'}), 400
    db = get_db()
    if not is_group_member(db, gid, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
    if not are_friends(db, me, peer): return jsonify({'ok': False, 'error': '只能邀请自己的好友'}), 403
    db.execute('INSERT OR IGNORE INTO group_members (group_id, username, joined_at) VALUES (?, ?, ?)', (gid, peer, time.time()))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/group/remove', methods=['POST'])
def group_remove():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: gid = int(data.get('group_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    target = (data.get('username') or me).strip()
    db = get_db()
    if not is_group_member(db, gid, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
    info = get_group_info(db, gid)
    if not info: return jsonify({'ok': False, 'error': '群不存在'}), 404
    if target == me:
        db.execute('DELETE FROM group_members WHERE group_id = ? AND username = ?', (gid, me))
        db.commit()
        cnt = db.execute('SELECT COUNT(*) AS c FROM group_members WHERE group_id = ?', (gid,)).fetchone()['c']
        if cnt == 0: db.execute('DELETE FROM groups WHERE id = ?', (gid,)); db.commit()
        return jsonify({'ok': True, 'left': True})
    if info['owner'] != me: return jsonify({'ok': False, 'error': '只有群主可以移除成员'}), 403
    db.execute('DELETE FROM group_members WHERE group_id = ? AND username = ?', (gid, target))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/group/send', methods=['POST'])
def group_send():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: gid = int(data.get('group_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    content = (data.get('content') or '').strip()
    reply_to = data.get('reply_to')
    if not content: return jsonify({'ok': False, 'error': '消息为空'}), 400
    if len(content) > 2000: return jsonify({'ok': False, 'error': '消息过长'}), 400
    db = get_db()
    if not is_group_member(db, gid, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
    touch_user(db, me)
    is_special = content.startswith('{') and ('"type"' in content)
    filtered, hit_bad = (content, False) if is_special else clean_text(content)
    if hit_bad:
        if not filtered: filtered = '（消息含不当内容，已屏蔽）'
        cur = db.execute('INSERT INTO messages (room, sender, content, created_at, reply_to) VALUES (?, ?, ?, ?, ?)', (group_room(gid), me, filtered, time.time(), reply_to))
        db.commit()
        return jsonify({'ok': True, 'id': cur.lastrowid, 'filtered': True, 'warning': '文明发言', 'content': filtered})
    cur = db.execute('INSERT INTO messages (room, sender, content, created_at, reply_to) VALUES (?, ?, ?, ?, ?)', (group_room(gid), me, content, time.time(), reply_to))
    mid = cur.lastrowid
    if not is_special: save_mentions(db, mid, group_room(gid), content, me)
    db.commit()
    # 触发推送
    try:
        pf = app.config.get('push_new_message')
        if pf: pf(group_room(gid), me, content[:60] if isinstance(content, str) else '[消息]')
    except Exception as _e:
        print('[push invoke err]', _e)
    return jsonify({'ok': True, 'id': mid})


@app.route('/api/group/history')
def group_history():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    try:
        gid = int(request.args.get('group_id', 0))
        limit = int(request.args.get('limit', 60))
    except ValueError: return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    if not is_group_member(db, gid, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
    rows = db.execute('SELECT id, sender, content, created_at, reply_to, deleted_by FROM messages WHERE room = ? ORDER BY id DESC LIMIT ?', (group_room(gid), limit)).fetchall()
    msgs = []
    for r in reversed(rows):
        if r['deleted_by'] and me in (r['deleted_by'] or '').split(','): continue
        m = {'id': r['id'], 'sender': r['sender'], 'content': r['content'], 'created_at': r['created_at'], 'reply_to': r['reply_to']}
        if r['reply_to']:
            q = db.execute('SELECT sender, content FROM messages WHERE id = ?', (r['reply_to'],)).fetchone()
            if q: m['reply_sender'] = q['sender']; m['reply_content'] = q['content'][:60]
        msgs.append(m)
    return jsonify({'ok': True, 'messages': msgs})


@app.route('/api/group/poll')
def group_poll():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    try:
        gid = int(request.args.get('group_id', 0))
        since = int(request.args.get('since', 0))
    except ValueError: return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    if not is_group_member(db, gid, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
    touch_user(db, me); db.commit()
    rows = db.execute('SELECT id, sender, content, created_at, reply_to, deleted_by FROM messages WHERE room = ? AND id > ? ORDER BY id ASC LIMIT 100', (group_room(gid), since)).fetchall()
    msgs = []
    for r in rows:
        if r['deleted_by'] and me in (r['deleted_by'] or '').split(','): continue
        m = {'id': r['id'], 'sender': r['sender'], 'content': r['content'], 'created_at': r['created_at'], 'reply_to': r['reply_to']}
        if r['reply_to']:
            q = db.execute('SELECT sender, content FROM messages WHERE id = ?', (r['reply_to'],)).fetchone()
            if q: m['reply_sender'] = q['sender']; m['reply_content'] = q['content'][:60]
        msgs.append(m)
    return jsonify({'ok': True, 'messages': msgs})


# ==================== 动态 ====================
@app.route('/api/moment/post', methods=['POST'])
def moment_post():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()[:500]
    image_url = (data.get('image_url') or '').strip()[:300]
    if not content and not image_url: return jsonify({'ok': False, 'error': '内容不能为空'}), 400
    content, _ = clean_text(content)
    db = get_db(); touch_user(db, me)
    cur = db.execute('INSERT INTO moments (username, content, image_url, likes, created_at) VALUES (?, ?, ?, ?, ?)', (me, content, image_url, '', time.time()))
    add_points(db, me, 3, '发布动态')
    db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@app.route('/api/moments')
def moments_list():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    try: limit = int(request.args.get('limit', 30))
    except ValueError: limit = 30
    db = get_db()
    rows = db.execute('SELECT id, username, content, image_url, likes, created_at FROM moments ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
    result = []
    for r in rows:
        u = db.execute('SELECT avatar, level_frame FROM users WHERE username = ?', (r['username'],)).fetchone()
        likes = [x for x in (r['likes'] or '').split(',') if x]
        cc = db.execute('SELECT COUNT(*) AS c FROM moment_comments WHERE moment_id = ?', (r['id'],)).fetchone()['c']
        result.append({'id': r['id'], 'username': r['username'], 'avatar': u['avatar'] if u else '', 'frame': (u['level_frame'] if u else 'default') or 'default', 'content': r['content'] or '', 'image_url': r['image_url'] or '', 'likes': likes, 'like_count': len(likes), 'comment_count': cc, 'liked_by_me': me in likes, 'created_at': r['created_at']})
    return jsonify({'ok': True, 'moments': result})


@app.route('/api/moment/like', methods=['POST'])
def moment_like():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: mid = int(data.get('moment_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    row = db.execute('SELECT likes, username FROM moments WHERE id = ?', (mid,)).fetchone()
    if not row: return jsonify({'ok': False, 'error': '动态不存在'}), 404
    likes = [x for x in (row['likes'] or '').split(',') if x]
    if me in likes: likes.remove(me)
    else:
        likes.append(me)
        if row['username'] != me: add_points(db, row['username'], 1, '动态被点赞')
    db.execute('UPDATE moments SET likes = ? WHERE id = ?', (','.join(likes), mid))
    db.commit()
    return jsonify({'ok': True, 'liked': me in likes, 'count': len(likes)})


@app.route('/api/moment/delete', methods=['POST'])
def moment_delete():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: mid = int(data.get('moment_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    row = db.execute('SELECT username FROM moments WHERE id = ?', (mid,)).fetchone()
    if not row: return jsonify({'ok': False, 'error': '动态不存在'}), 404
    if row['username'] != me: return jsonify({'ok': False, 'error': '只能删除自己的动态'}), 403
    db.execute('DELETE FROM moments WHERE id = ?', (mid,))
    db.execute('DELETE FROM moment_comments WHERE moment_id = ?', (mid,))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/moment/comment', methods=['POST'])
def moment_comment_post():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: mid = int(data.get('moment_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    content = (data.get('content') or '').strip()[:200]
    if not content: return jsonify({'ok': False, 'error': '评论不能为空'}), 400
    content, _ = clean_text(content)
    db = get_db()
    if not db.execute('SELECT 1 FROM moments WHERE id = ?', (mid,)).fetchone():
        return jsonify({'ok': False, 'error': '动态不存在'}), 404
    cur = db.execute('INSERT INTO moment_comments (moment_id, username, content, created_at) VALUES (?, ?, ?, ?)', (mid, me, content, time.time()))
    db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@app.route('/api/moment/comments')
def moment_comments_list():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    try: mid = int(request.args.get('moment_id', 0))
    except ValueError: return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    rows = db.execute('SELECT id, username, content, created_at FROM moment_comments WHERE moment_id = ? ORDER BY id ASC LIMIT 100', (mid,)).fetchall()
    result = []
    for r in rows:
        u = db.execute('SELECT avatar FROM users WHERE username = ?', (r['username'],)).fetchone()
        result.append({'id': r['id'], 'username': r['username'], 'avatar': u['avatar'] if u else '', 'content': r['content'], 'created_at': r['created_at']})
    return jsonify({'ok': True, 'comments': result})


@app.route('/api/moment/comment/delete', methods=['POST'])
def moment_comment_delete():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: cid = int(data.get('id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    row = db.execute('SELECT username FROM moment_comments WHERE id = ?', (cid,)).fetchone()
    if not row: return jsonify({'ok': False, 'error': '评论不存在'}), 404
    if row['username'] != me: return jsonify({'ok': False, 'error': '只能删除自己的评论'}), 403
    db.execute('DELETE FROM moment_comments WHERE id = ?', (cid,))
    db.commit()
    return jsonify({'ok': True})



@app.route('/api/group/announcement', methods=['GET', 'POST'])
def group_announcement():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    if request.method == 'POST':
        data = request.get_json() or {}
        try: gid = int(data.get('group_id'))
        except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
        content = (data.get('content') or '').strip()[:500]
        db = get_db()
        info = get_group_info(db, gid)
        if not info: return jsonify({'ok': False, 'error': '群不存在'}), 404
        if info['owner'] != me: return jsonify({'ok': False, 'error': '只有群主可以设置公告'}), 403
        db.execute('INSERT OR REPLACE INTO group_announcements (group_id, content, updated_at, updated_by) VALUES (?, ?, ?, ?)', (gid, content, time.time(), me))
        db.commit()
        return jsonify({'ok': True})
    try: gid = int(request.args.get('group_id', 0))
    except ValueError: return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    if not is_group_member(db, gid, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
    row = db.execute('SELECT content, updated_at, updated_by FROM group_announcements WHERE group_id = ?', (gid,)).fetchone()
    if not row: return jsonify({'ok': True, 'content': '', 'updated_at': 0, 'updated_by': ''})
    return jsonify({'ok': True, 'content': row['content'] or '', 'updated_at': row['updated_at'] or 0, 'updated_by': row['updated_by'] or ''})


# ==================== 管理员 ====================
def require_admin():
    token = ''
    auth = request.headers.get('Authorization', '')
    if auth.startswith('Bearer '): token = auth[7:].strip()
    if not token: token = (request.args.get('token') or '').strip()
    if not token: return False
    ts = _admin_tokens.get(token)
    if not ts: return False
    if time.time() - ts > 12 * 3600:
        _admin_tokens.pop(token, None); return False
    return True


@app.route('/admin')
def admin_page(): return render_template('admin.html')


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.get_json() or {}
    if (data.get('password') or '') != ADMIN_PASSWORD:
        return jsonify({'ok': False, 'error': '密码错误'}), 401
    token = secrets.token_urlsafe(32)
    _admin_tokens[token] = time.time()
    return jsonify({'ok': True, 'token': token})


@app.route('/api/admin/reports')
def admin_reports():
    if not require_admin(): return jsonify({'ok': False, 'error': '未登录'}), 401
    show_all = request.args.get('all') == '1'
    db = get_db()
    if show_all: rows = db.execute('SELECT * FROM reports ORDER BY id DESC LIMIT 300').fetchall()
    else: rows = db.execute("SELECT * FROM reports WHERE status='pending' ORDER BY id DESC LIMIT 300").fetchall()
    result = []
    for r in rows:
        result.append({'id': r['id'], 'reporter': r['reporter'], 'target': r['target'], 'reason': r['reason'], 'detail': r['detail'] or '', 'email': r['email'] or '', 'status': r['status'], 'created_at': r['created_at']})
    return jsonify({'ok': True, 'reports': result})


@app.route('/api/admin/report/handle', methods=['POST'])
def admin_handle_report():
    if not require_admin(): return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    try: rid = int(data.get('report_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    action = (data.get('action') or '').strip()
    db = get_db()
    rep = db.execute('SELECT * FROM reports WHERE id = ?', (rid,)).fetchone()
    if not rep: return jsonify({'ok': False, 'error': '举报不存在'}), 404
    target = rep['target']
    now = time.time()
    if action == 'reject':
        db.execute("UPDATE reports SET status='rejected', handled_at=? WHERE id=?", (now, rid))
        add_points(db, rep['reporter'], -2, '举报被驳回')
    elif action == 'warn':
        db.execute('INSERT INTO warnings (username, reason, is_read, created_at) VALUES (?, ?, 0, ?)', (target, '管理员警告', now))
        db.execute("UPDATE reports SET status='handled', handled_at=? WHERE id=?", (now, rid))
        add_points(db, rep['reporter'], 2, '举报成立')
    elif action == 'mute':
        db.execute('UPDATE users SET muted_until = ? WHERE username = ?', (now + 3600, target))
        db.execute("UPDATE reports SET status='handled', handled_at=? WHERE id=?", (now, rid))
        add_points(db, rep['reporter'], 2, '举报成立')
    elif action == 'ban':
        db.execute('UPDATE users SET banned = 1 WHERE username = ?', (target,))
        db.execute("UPDATE reports SET status='handled', handled_at=? WHERE id=?", (now, rid))
        add_points(db, rep['reporter'], 2, '举报成立')
    else: return jsonify({'ok': False, 'error': '未知操作'}), 400
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/user/unban', methods=['POST'])
def admin_unban():
    if not require_admin(): return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    db = get_db()
    db.execute('UPDATE users SET banned = 0, muted_until = 0 WHERE username = ?', (username,))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/users')
def admin_users():
    if not require_admin(): return jsonify({'ok': False, 'error': '未登录'}), 401
    db = get_db()
    rows = db.execute('SELECT username, banned, muted_until, warning_count, points FROM users ORDER BY last_seen DESC LIMIT 500').fetchall()
    result = [{'username': r['username'], 'banned': bool(r['banned']), 'muted_until': r['muted_until'] or 0, 'warning_count': r['warning_count'] or 0, 'points': r['points'] or 0} for r in rows]
    return jsonify({'ok': True, 'users': result})


@app.route('/api/admin/applications')
def api_admin_applications():
    if not require_admin(): return jsonify({'ok': False, 'error': '未登录'}), 401
    db = get_db()
    show_all = request.args.get('all') == '1'
    if show_all: rows = db.execute('SELECT * FROM applications ORDER BY id DESC LIMIT 200').fetchall()
    else: rows = db.execute("SELECT * FROM applications WHERE status = 'pending' ORDER BY id ASC LIMIT 200").fetchall()
    return jsonify({'ok': True, 'applications': [dict(r) for r in rows]})


@app.route('/api/admin/application/approve', methods=['POST'])
def api_admin_application_approve():
    if not require_admin(): return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    try: aid = int(data.get('id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    row = db.execute('SELECT * FROM applications WHERE id = ?', (aid,)).fetchone()
    if not row: return jsonify({'ok': False, 'error': '申请不存在'}), 404
    if row['status'] == 'approved' and row['invite_code']:
        return jsonify({'ok': True, 'invite_code': row['invite_code']})
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    code = None
    for _ in range(30):
        c = ''.join(secrets.choice(alphabet) for _ in range(6))
        if not db.execute('SELECT 1 FROM applications WHERE invite_code = ?', (c,)).fetchone():
            code = c; break
    if not code: return jsonify({'ok': False, 'error': '生成失败'}), 500
    db.execute("UPDATE applications SET status = 'approved', invite_code = ?, handled_at = ? WHERE id = ?", (code, time.time(), aid))
    db.commit()
    return jsonify({'ok': True, 'invite_code': code})


@app.route('/api/admin/application/reject', methods=['POST'])
def api_admin_application_reject():
    if not require_admin(): return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    try: aid = int(data.get('id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    db.execute("UPDATE applications SET status = 'rejected', handled_at = ? WHERE id = ?", (time.time(), aid))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/invite/batch', methods=['POST'])
def admin_invite_batch():
    if not require_admin(): return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    try: count = int(data.get('count', 10))
    except (TypeError, ValueError): count = 10
    count = max(1, min(50, count))
    db = get_db()
    alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    codes = []
    for _ in range(count):
        for _try in range(30):
            c = ''.join(secrets.choice(alphabet) for _ in range(6))
            if not db.execute('SELECT 1 FROM applications WHERE invite_code = ?', (c,)).fetchone():
                db.execute('INSERT INTO applications (email, message, status, invite_code, created_at, handled_at) VALUES (?, ?, ?, ?, ?, ?)',
                           ('(admin)', '批量生成', 'approved', c, time.time(), time.time()))
                codes.append(c)
                break
    db.commit()
    return jsonify({'ok': True, 'codes': codes})


@app.route('/api/apply', methods=['POST'])
def api_apply():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()[:100]
    message = (data.get('message') or '').strip()[:200]

    # 格式校验：本地部分 >= 3 位，不能是纯数字，域名要有合法的 TLD
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return jsonify({'ok': False, 'error': '邮箱格式不正确'}), 400
    local = email.split('@')[0]
    if len(local) < 1:
        return jsonify({'ok': False, 'error': '邮箱格式不正确'}), 400
    domain = email.split('@')[-1]
    if '.' not in domain or len(domain.split('.')[-1]) < 2:
        return jsonify({'ok': False, 'error': '邮箱格式不正确'}), 400

    db = get_db()
    cutoff = time.time() - 86400
    exist = db.execute(
        "SELECT id, status FROM applications WHERE email = ? AND created_at > ?",
        (email, cutoff)
    ).fetchone()
    if exist:
        return jsonify({'ok': False, 'error': '该邮箱已申请过，请等待审核'}), 429

    kind = _classify_email_domain(email)

    if kind == 'free':
        # 白名单 → 自动放行
        code = _gen_invite_code(db)
        if not code:
            return jsonify({'ok': False, 'error': '生成失败'}), 500
        db.execute(
            "INSERT INTO applications (email, message, status, invite_code, created_at, handled_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (email, message, 'approved', code, time.time(), time.time())
        )
        db.commit()
        return jsonify({'ok': True, 'auto_approved': True, 'invite_code': code})

    # 未知域名 / 临时邮箱 → 走滑块验证
    db.execute(
        "INSERT INTO applications (email, message, status, created_at) VALUES (?, ?, ?, ?)",
        (email, message, 'pending_verify', time.time())
    )
    db.commit()
    return jsonify({
        'ok': True,
        'auto_approved': False,
        'need_verify': True,
        'message': '该邮箱需要完成人机验证'
    })


@app.route('/api/apply/verify', methods=['POST'])
def api_apply_verify():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()
    human_token = (data.get('human_token') or '').strip()

    if not verify_human_token(human_token):
        return jsonify({'ok': False, 'error': '人机验证未通过'}), 403

    db = get_db()
    row = db.execute(
        "SELECT id, status FROM applications WHERE email = ? ORDER BY id DESC LIMIT 1",
        (email,)
    ).fetchone()
    if not row:
        return jsonify({'ok': False, 'error': '申请不存在'}), 404
    if row['status'] == 'approved':
        r2 = db.execute("SELECT invite_code FROM applications WHERE id = ?", (row['id'],)).fetchone()
        return jsonify({'ok': True, 'already': True, 'invite_code': r2['invite_code'] if r2 else ''})

    code = _gen_invite_code(db)
    if not code:
        return jsonify({'ok': False, 'error': '生成失败'}), 500
    db.execute(
        "UPDATE applications SET status = 'approved', invite_code = ?, handled_at = ? WHERE id = ?",
        (code, time.time(), row['id'])
    )
    db.commit()
    return jsonify({'ok': True, 'invite_code': code})


@app.route('/api/apply/status')
def api_apply_status():
    email = (request.args.get('email') or '').strip().lower()
    if not email:
        return jsonify({'ok': False, 'error': '缺少参数'}), 400
    db = get_db()
    row = db.execute(
        'SELECT status, invite_code FROM applications WHERE email = ? ORDER BY id DESC LIMIT 1',
        (email,)
    ).fetchone()
    if not row:
        return jsonify({'ok': False, 'error': '没有申请记录'}), 404
    return jsonify({
        'ok': True,
        'status': row['status'],
        'invite_code': row['invite_code'] or ''
    })



@app.route('/api/chat_background', methods=['GET', 'POST'])
def chat_background():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS chat_backgrounds (username TEXT PRIMARY KEY, url TEXT NOT NULL, updated_at REAL NOT NULL)')
    db.commit()
    if request.method == 'POST':
        data = request.get_json() or {}
        url = (data.get('url') or '').strip()[:300]
        if url:
            db.execute('INSERT OR REPLACE INTO chat_backgrounds (username, url, updated_at) VALUES (?, ?, ?)', (me, url, time.time()))
        else:
            db.execute('DELETE FROM chat_backgrounds WHERE username = ?', (me,))
        db.commit()
        return jsonify({'ok': True, 'url': url})
    row = db.execute('SELECT url FROM chat_backgrounds WHERE username = ?', (me,)).fetchone()
    return jsonify({'ok': True, 'url': row['url'] if row else ''})


@app.route('/api/chat_pin', methods=['GET', 'POST'])
def chat_pin():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS chat_pins (owner TEXT NOT NULL, target TEXT NOT NULL, pinned_at REAL NOT NULL, PRIMARY KEY (owner, target))')
    db.commit()
    if request.method == 'POST':
        data = request.get_json() or {}
        target = (data.get('target') or '').strip()
        action = (data.get('action') or 'pin').strip()
        if not target: return jsonify({'ok': False, 'error': '缺少 target'}), 400
        if action == 'unpin':
            db.execute('DELETE FROM chat_pins WHERE owner = ? AND target = ?', (me, target))
        else:
            db.execute('INSERT OR REPLACE INTO chat_pins (owner, target, pinned_at) VALUES (?, ?, ?)', (me, target, time.time()))
        db.commit()
        return jsonify({'ok': True})
    rows = db.execute('SELECT target, pinned_at FROM chat_pins WHERE owner = ? ORDER BY pinned_at DESC', (me,)).fetchall()
    return jsonify({'ok': True, 'pins': [dict(r) for r in rows]})


ALLOWED_AUDIO_EXTS = {'.mp3', '.m4a', '.wav', '.ogg', '.aac', '.flac'}

@app.route('/api/upload_music', methods=['POST'])
def upload_music():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    f = request.files.get('music')
    if f is None: return jsonify({'ok': False, 'error': '未收到文件'}), 400
    ext = os.path.splitext(f.filename or '')[1].lower()
    if ext not in ALLOWED_AUDIO_EXTS:
        return jsonify({'ok': False, 'error': '不支持的格式：' + ext}), 400
    data = f.read()
    if not data: return jsonify({'ok': False, 'error': '文件为空'}), 400
    if len(data) > 10 * 1024 * 1024:
        return jsonify({'ok': False, 'error': '音乐不能超过 10MB'}), 413
    filename = 'music_' + str(int(time.time() * 1000)) + '_' + uuid.uuid4().hex[:8] + ext
    with open(os.path.join(UPLOAD_DIR, filename), 'wb') as out:
        out.write(data)
    return jsonify({'ok': True, 'url': '/uploads/' + filename, 'name': f.filename, 'size': len(data)})


@app.route('/api/mute', methods=['GET', 'POST'])
def chat_mute():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS chat_mutes (owner TEXT NOT NULL, target TEXT NOT NULL, muted_at REAL NOT NULL, PRIMARY KEY (owner, target))')
    db.commit()
    if request.method == 'POST':
        data = request.get_json() or {}
        target = (data.get('target') or '').strip()
        action = (data.get('action') or 'mute').strip()
        if not target: return jsonify({'ok': False, 'error': '缺少 target'}), 400
        if action == 'unmute':
            db.execute('DELETE FROM chat_mutes WHERE owner = ? AND target = ?', (me, target))
        else:
            db.execute('INSERT OR REPLACE INTO chat_mutes (owner, target, muted_at) VALUES (?, ?, ?)', (me, target, time.time()))
        db.commit()
        return jsonify({'ok': True})
    rows = db.execute('SELECT target FROM chat_mutes WHERE owner = ?', (me,)).fetchall()
    return jsonify({'ok': True, 'mutes': [r['target'] for r in rows]})


@app.route('/api/chat/clear', methods=['POST'])
def chat_clear():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    target = (data.get('target') or '').strip()
    room_type = (data.get('type') or 'private').strip()
    if not target: return jsonify({'ok': False, 'error': '缺少 target'}), 400
    db = get_db()
    if room_type == 'group':
        try: gid = int(target)
        except ValueError: return jsonify({'ok': False, 'error': '群 ID 无效'}), 400
        if not is_group_member(db, gid, me):
            return jsonify({'ok': False, 'error': '你不在该群'}), 403
        room = group_room(gid)
    else:
        if not are_friends(db, me, target):
            return jsonify({'ok': False, 'error': '不是好友'}), 403
        room = make_room(me, target)
    rows = db.execute('SELECT id, deleted_by FROM messages WHERE room = ?', (room,)).fetchall()
    for r in rows:
        existing = (r['deleted_by'] or '').split(',') if r['deleted_by'] else []
        existing = [x for x in existing if x]
        if me not in existing:
            existing.append(me)
            db.execute('UPDATE messages SET deleted_by = ? WHERE id = ?', (','.join(existing), r['id']))
    db.commit()
    return jsonify({'ok': True, 'count': len(rows)})


@app.route('/api/friend_group', methods=['GET', 'POST'])
def friend_group():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS friend_groups (owner TEXT NOT NULL, peer TEXT NOT NULL, group_name TEXT NOT NULL, PRIMARY KEY (owner, peer))')
    db.commit()
    if request.method == 'POST':
        data = request.get_json() or {}
        peer = (data.get('peer') or '').strip()
        gname = (data.get('group_name') or '').strip()[:10]
        if not peer: return jsonify({'ok': False, 'error': '缺少 peer'}), 400
        if gname:
            db.execute('INSERT OR REPLACE INTO friend_groups (owner, peer, group_name) VALUES (?, ?, ?)', (me, peer, gname))
        else:
            db.execute('DELETE FROM friend_groups WHERE owner = ? AND peer = ?', (me, peer))
        db.commit()
        return jsonify({'ok': True})
    rows = db.execute('SELECT peer, group_name FROM friend_groups WHERE owner = ?', (me,)).fetchall()
    result = {}
    for r in rows:
        result[r['peer']] = r['group_name']
    return jsonify({'ok': True, 'groups': result})


@app.route('/api/group/mention_all', methods=['POST'])
def group_mention_all():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: gid = int(data.get('group_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    if not is_group_member(db, gid, me):
        return jsonify({'ok': False, 'error': '你不在该群'}), 403
    info = get_group_info(db, gid)
    if not info: return jsonify({'ok': False, 'error': '群不存在'}), 404
    if info['owner'] != me:
        return jsonify({'ok': False, 'error': '只有群主可以 @全体成员'}), 403
    payload = {'type': 'text', 'text': '@全体成员 '}
    import json as __json
    content = __json.dumps(payload, ensure_ascii=False)
    cur = db.execute('INSERT INTO messages (room, sender, content, created_at) VALUES (?, ?, ?, ?)', (group_room(gid), me, '@全体成员', time.time()))
    db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@app.route('/api/moment/post_multi', methods=['POST'])
def moment_post_multi():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()[:500]
    images = data.get('images') or []
    if not isinstance(images, list): images = []
    images = [str(u).strip()[:300] for u in images if u][:9]
    if not content and not images: return jsonify({'ok': False, 'error': '内容不能为空'}), 400
    content, _ = clean_text(content)
    db = get_db(); touch_user(db, me)
    image_url = _json.dumps(images, ensure_ascii=False) if images else ''
    cur = db.execute('INSERT INTO moments (username, content, image_url, likes, created_at) VALUES (?, ?, ?, ?, ?)', (me, content, image_url, '', time.time()))
    add_points(db, me, 3, '发布动态')
    db.commit()
    return jsonify({'ok': True, 'id': cur.lastrowid})


@app.route('/api/daily_sign', methods=['GET', 'POST'])
def daily_sign():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    db.execute('CREATE TABLE IF NOT EXISTS daily_signs (username TEXT NOT NULL, day TEXT NOT NULL, streak INTEGER DEFAULT 1, created_at REAL NOT NULL, PRIMARY KEY (username, day))')
    db.commit()
    today = time.strftime('%Y-%m-%d')
    if request.method == 'POST':
        exist = db.execute('SELECT 1 FROM daily_signs WHERE username = ? AND day = ?', (me, today)).fetchone()
        if exist:
            return jsonify({'ok': False, 'error': '今天已经签到过了'}), 400
        yesterday = time.strftime('%Y-%m-%d', time.localtime(time.time() - 86400))
        y = db.execute('SELECT streak FROM daily_signs WHERE username = ? AND day = ?', (me, yesterday)).fetchone()
        streak = (y['streak'] + 1) if y else 1
        base = 5
        bonus = min(streak - 1, 7)
        total = base + bonus
        db.execute('INSERT INTO daily_signs (username, day, streak, created_at) VALUES (?, ?, ?, ?)', (me, today, streak, time.time()))
        add_points(db, me, total, '每日签到')
        db.commit()
        return jsonify({'ok': True, 'points': total, 'streak': streak})
    row = db.execute('SELECT streak FROM daily_signs WHERE username = ? AND day = ?', (me, today)).fetchone()
    signed_today = bool(row)
    cur_streak = row['streak'] if row else 0
    total_days = db.execute('SELECT COUNT(*) AS c FROM daily_signs WHERE username = ?', (me,)).fetchone()['c']
    return jsonify({'ok': True, 'signed_today': signed_today, 'streak': cur_streak, 'total_days': total_days})


@app.route('/rules')
def rules_page():
    chapters = [
        ('第一章', '总则', ['欢迎使用快聊。本规则适用于所有注册用户。', '使用本服务即视为你已阅读并同意本规则全部条款。', '管理员保留随时修改规则的权利，修改后立即生效。']),
        ('第二章', '账号管理', ['一人一账号，禁止使用他人身份注册。', '昵称不能是纯数字、不能包含敏感词。', '密码请勿告诉他人。', '禁止出借、出租、买卖账号。', '禁止使用脚本、外挂批量注册或刷分。']),
        ('第三章', '聊天规范', ['禁止发布色情、暴力、诈骗、赌博内容。', '禁止发布政治敏感、宗教极端内容。', '禁止辱骂、人身攻击、歧视他人。', '禁止刷屏、发广告、外链、拉人。', '系统会自动过滤脏话。']),
        ('第四章', '隐私保护', ['聊天记录存储于服务器 SQLite。', '请勿在聊天中发送银行卡号、身份证号等敏感信息。', '上传图片、视频前请自行确认无隐私内容。', '禁止窥探、传播他人隐私。']),
        ('第五章', '好友与群聊', ['添加好友需对方同意。', '禁止利用好友功能进行骚扰、诈骗。', '群主对群内言论负管理责任。', '群主可移除违规成员。']),
        ('第六章', '积分规则', ['积分可通过发帖、邀请好友、加好友获得。', '积分不可转让、不可提现、不可兑换现金。', '使用外挂刷分的账号，积分清零并封禁。', '管理员有权调整积分规则。']),
        ('第七章', '宠物系统', ['宠物是站内的装饰性虚拟物品。', '喂食消耗积分，宠物等级提升。', '禁止用宠物名进行辱骂、色情、政治相关表达。']),
        ('第八章', '头像与外观', ['头像不能包含色情、暴力、政治敏感内容。', '头像框通过等级解锁或积分购买获得。', '禁止使用盗版、侵权头像。']),
        ('第九章', '红包规则', ['红包使用积分发送。', '每人只能抢一次同一个红包。', '24 小时未抢完自动退回。', '禁止利用红包进行赌博、洗积分。']),
        ('第十章', '消息与文件', ['图片、视频、文件请勿上传违法内容。', '单个文件上限根据等级 5-20 MB。', '图片/视频/语音 30 天后自动清理。', '禁止上传病毒、木马、恶意软件。']),
        ('第十一章', '违规处理', ['违规分三级：警告、禁言 1 小时、永久封禁。', '违规账号的积分、等级、宠物会被清零。', '情节严重的将上报相关部门。', '被举报 3 次以上的账号会被重点监控。']),
        ('第十二章', '举报处理', ['举报需提供合理理由，恶意举报会被扣分。', '管理员会根据举报内容进行裁定。', '裁定结果以管理员处理为准。']),
        ('第十三章', '通知与提醒', ['新消息提醒可以在「设置」里关闭。', '免打扰的聊天不会弹通知。', '好友上线时可能收到提示。', '所有通知均可在系统设置里关闭。']),
        ('第十四章', '免责声明', ['本产品仅供朋友之间交流使用，请勿用于商业用途。', '因不可抗力导致的服务中断，本站不承担责任。', '本规则最终解释权归快聊官方所有。']),
    ]
    html = '''<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>站内规则 - 快聊</title><style>
*{margin:0;padding:0;box-sizing:border-box;font-family:-apple-system,system-ui,sans-serif;}
body{background:linear-gradient(135deg,#e3f2fd 0%,#bbdefb 50%,#e1f5fe 100%);padding:16px;min-height:100vh;}
.wrap{max-width:640px;margin:0 auto;background:#fff;border-radius:20px;padding:24px 22px;box-shadow:0 12px 40px rgba(33,150,243,.15);}
h1{color:#1565c0;font-size:22px;margin-bottom:6px;text-align:center;}
.sub{color:#90a4ae;font-size:12px;text-align:center;margin-bottom:24px;}
.ch{margin-bottom:22px;padding-bottom:18px;border-bottom:1px solid #f0f7fe;}
.ch:last-child{border-bottom:none;}
.ch-title{font-size:15px;font-weight:700;color:#1976d2;margin-bottom:10px;display:flex;align-items:center;gap:8px;}
.ch-title .num{background:#e3f2fd;color:#1976d2;padding:2px 10px;border-radius:20px;font-size:11px;}
.ch-item{font-size:14px;color:#546e7a;line-height:1.9;padding-left:20px;position:relative;}
.ch-item::before{content:'•';position:absolute;left:6px;color:#90caf9;font-weight:700;}
.back-btn{display:block;margin:24px auto 0;background:linear-gradient(135deg,#42a5f5,#1e88e5);color:#fff;border:none;padding:12px 32px;border-radius:12px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;}
@media (prefers-color-scheme: dark){body{background:linear-gradient(135deg,#0b1622,#12293f,#0b1622);}.wrap{background:#0f1e2e;}h1{color:#7ec3f5;}.ch{border-color:#1c3347;}.ch-title{color:#7ec3f5;}.ch-title .num{background:#12293f;color:#7ec3f5;}.ch-item{color:#9db4c7;}}
</style></head><body><div class="wrap">
<h1>📜 站内规则</h1>
<div class="sub">快聊 · 隐私至上 · 好友加密聊天</div>
'''
    for num, name, items in chapters:
        html += '<div class="ch"><div class="ch-title"><span class="num">' + num + '</span><span>' + name + '</span></div>'
        for it in items:
            html += '<div class="ch-item">' + it + '</div>'
        html += '</div>'
    html += '<button class="back-btn" onclick="location.href=&quot;/chat&quot;">返回快聊</button>'
    html += '</div></body></html>'
    return html


init_db()

# ==================== 宠物修复 + 管理员群列表 ====================

@app.route('/api/pet/feed', methods=['POST'])
def pet_feed_v2():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    target = (data.get('username') or me).strip()
    db = get_db()
    row = db.execute('SELECT pet_type, pet_feed FROM users WHERE username = ?', (target,)).fetchone()
    if not row or not row['pet_type']:
        return jsonify({'ok': False, 'error': '对方还没有宠物'}), 400

    today = time.strftime('%Y-%m-%d')
    # 记录今日喂食次数（存到 pet_feed_log 表）
    db.execute('''CREATE TABLE IF NOT EXISTS pet_feed_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        target TEXT NOT NULL,
        day TEXT NOT NULL,
        created_at REAL NOT NULL
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_pet_feed_day ON pet_feed_log(username, target, day)')

    cnt = db.execute('SELECT COUNT(*) AS c FROM pet_feed_log WHERE username = ? AND target = ? AND day = ?',
                     (me, target, today)).fetchone()['c']

    if cnt >= 5:
        return jsonify({'ok': False, 'error': '你的宠物已经吃饱了，明天再来吧'}), 429

    is_self = (target == me)
    if is_self:
        return jsonify({'ok': False, 'error': '不能给自己的宠物喂食，快去好友那里喂吧'}), 400

    # 每次扣 10 分
    u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
    if (u['points'] or 0) < 10:
        return jsonify({'ok': False, 'error': '积分不足（每次喂食需要 10 积分）'}), 400
    db.execute('UPDATE users SET points = points - 10 WHERE username = ?', (me,))
    add_points(db, target, 5, f'{me} 喂食宠物')

    # 记一次喂食
    db.execute('INSERT INTO pet_feed_log (username, target, day, created_at) VALUES (?, ?, ?, ?)',
               (me, target, today, time.time()))

    new_feed = (row['pet_feed'] or 0) + 1
    new_level = min(10, new_feed // 5)
    old_level = min(10, (row['pet_feed'] or 0) // 5)
    db.execute('UPDATE users SET pet_feed = ?, pet_level = ? WHERE username = ?', (new_feed, new_level, target))
    db.commit()
    msg = '宠物升级啦！Lv.' + str(new_level) if new_level > old_level else '喂食成功（今日剩余 ' + str(4 - cnt) + ' 次）'
    return jsonify({'ok': True, 'feed': new_feed, 'level': new_level, 'message': msg})


@app.route('/api/pet/rename', methods=['POST'])
def pet_rename():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    newname = (data.get('pet_name') or '').strip()[:12]
    if not newname:
        return jsonify({'ok': False, 'error': '名字不能为空'}), 400
    cleaned, bad = clean_text(newname)
    if bad: newname = cleaned
    if not newname:
        return jsonify({'ok': False, 'error': '名字包含违规内容'}), 400
    db = get_db()
    row = db.execute('SELECT pet_type FROM users WHERE username = ?', (me,)).fetchone()
    if not row or not row['pet_type']:
        return jsonify({'ok': False, 'error': '你还没有宠物'}), 400
    db.execute('UPDATE users SET pet_name = ? WHERE username = ?', (newname, me))
    db.commit()
    return jsonify({'ok': True, 'pet_name': newname})


@app.route('/api/pet/feed_count')
def pet_feed_count():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    target = (request.args.get('username') or me).strip()
    db = get_db()
    today = time.strftime('%Y-%m-%d')
    try:
        cnt = db.execute('SELECT COUNT(*) AS c FROM pet_feed_log WHERE username = ? AND target = ? AND day = ?',
                         (me, target, today)).fetchone()['c']
    except Exception:
        cnt = 0
    return jsonify({'ok': True, 'count': cnt, 'remain': max(0, 5 - cnt)})


# ===== 管理员看所有群 =====
@app.route('/api/admin/groups')
def admin_groups_list():
    if not require_admin():
        return jsonify({'ok': False, 'error': '未登录'}), 401
    db = get_db()
    rows = db.execute('''SELECT g.id, g.name, g.owner, g.created_at,
        (SELECT COUNT(*) FROM group_members WHERE group_id = g.id) AS member_count,
        (SELECT COUNT(*) FROM messages WHERE room = 'group_' || g.id) AS msg_count
        FROM groups g ORDER BY g.id DESC LIMIT 500''').fetchall()
    return jsonify({'ok': True, 'groups': [dict(r) for r in rows]})


@app.route('/api/admin/group/delete', methods=['POST'])
def admin_group_delete():
    if not require_admin():
        return jsonify({'ok': False, 'error': '未登录'}), 401
    data = request.get_json() or {}
    try: gid = int(data.get('group_id'))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    db.execute('DELETE FROM group_members WHERE group_id = ?', (gid,))
    db.execute('DELETE FROM groups WHERE id = ?', (gid,))
    db.execute("DELETE FROM messages WHERE room = ?", (f'group_{gid}',))
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/admin/group/members')
def admin_group_members():
    if not require_admin():
        return jsonify({'ok': False, 'error': '未登录'}), 401
    try: gid = int(request.args.get('group_id', 0))
    except ValueError: return jsonify({'ok': False, 'error': '参数错误'}), 400
    db = get_db()
    rows = db.execute('SELECT username, joined_at FROM group_members WHERE group_id = ? ORDER BY joined_at ASC', (gid,)).fetchall()
    return jsonify({'ok': True, 'members': [dict(r) for r in rows]})


# ==================== 媒体压缩 + 过期删除 + 语音 ====================
import subprocess

try:
    from PIL import Image
except ImportError:
    Image = None
    print('[warn] PIL not installed, image compression disabled')


EXPIRE_DAYS = 30

def _cleanup_expired_media():
    """扫描 uploads 目录，删除超过 30 天的图片/视频/语音"""
    cutoff = time.time() - EXPIRE_DAYS * 86400
    if not os.path.isdir(UPLOAD_DIR):
        return
    for f in os.listdir(UPLOAD_DIR):
        fp = os.path.join(UPLOAD_DIR, f)
        try:
            if os.path.isfile(fp) and os.path.getmtime(fp) < cutoff:
                os.remove(fp)
        except OSError:
            pass


def _compress_image(filepath):
    """图片压缩"""
    if Image is None:
        return filepath
    try:
        img = Image.open(filepath)
        # 统一转 RGB（去掉透明通道，PNG 转 JPG）
        if img.mode in ('RGBA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        # 超过 1600px 的缩小
        if max(img.width, img.height) > 1600:
            img.thumbnail((1600, 1600), Image.LANCZOS)
        # 覆盖保存为 jpg
        new_path = os.path.splitext(filepath)[0] + '.jpg'
        img.save(new_path, 'JPEG', quality=85, optimize=True, progressive=True)
        if new_path != filepath and os.path.exists(filepath):
            os.remove(filepath)
        return new_path
    except Exception as e:
        print('[compress image err]', e)
        return filepath


def _compress_video(filepath):
    """视频压缩"""
    import shutil
    if not shutil.which('ffmpeg'):
        return filepath
    out = os.path.splitext(filepath)[0] + '_c.mp4'
    cmd = [
        'ffmpeg', '-y', '-i', filepath,
        '-c:v', 'libx264', '-crf', '23', '-preset', 'medium',
        '-movflags', '+faststart',
        '-c:a', 'aac', '-b:a', '96k',
        out
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        if r.returncode == 0 and os.path.exists(out):
            os.remove(filepath)
            return out
        else:
            print('[ffmpeg err]', r.stderr.decode()[:200])
            return filepath
    except Exception as e:
        print('[compress video err]', e)
        return filepath


@app.route('/api/upload', methods=['POST'])
def upload_image_v2():
    _cleanup_expired_media()
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    url, err = _save_upload(request.files.get('image'), ALLOWED_IMAGE_EXTS, MAX_IMAGE_SIZE, 'img')
    if err: return jsonify({'ok': False, 'error': err}), 400
    # 压缩
    filepath = os.path.join(UPLOAD_DIR, os.path.basename(url))
    new_path = _compress_image(filepath)
    new_url = '/uploads/' + os.path.basename(new_path)
    return jsonify({'ok': True, 'url': new_url})


@app.route('/api/upload_video', methods=['POST'])
def upload_video_v2():
    _cleanup_expired_media()
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    max_size = _user_max_size(db, me, 'video')
    url, err = _save_upload(request.files.get('video'), ALLOWED_VIDEO_EXTS, max_size, 'vid')
    if err: return jsonify({'ok': False, 'error': err}), 400
    filepath = os.path.join(UPLOAD_DIR, os.path.basename(url))
    new_path = _compress_video(filepath)
    new_url = '/uploads/' + os.path.basename(new_path)
    return jsonify({'ok': True, 'url': new_url})


@app.route('/api/upload_voice', methods=['POST'])
def upload_voice():
    _cleanup_expired_media()
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    f = request.files.get('voice')
    if f is None: return jsonify({'ok': False, 'error': '未收到语音'}), 400
    data = f.read()
    if not data: return jsonify({'ok': False, 'error': '内容为空'}), 400
    if len(data) > 5 * 1024 * 1024:
        return jsonify({'ok': False, 'error': '语音不能超过 5MB'}), 413
    ext = os.path.splitext(f.filename or '')[1].lower() or '.webm'
    if ext not in ('.webm', '.mp3', '.wav', '.m4a', '.ogg'):
        ext = '.webm'
    filename = f"voice_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}{ext}"
    with open(os.path.join(UPLOAD_DIR, filename), 'wb') as out:
        out.write(data)
    return jsonify({'ok': True, 'url': '/uploads/' + filename})


@app.route('/api/media/check')
def media_check():
    """前端检查媒体是否过期"""
    url = (request.args.get('url') or '').strip()
    if not url or not url.startswith('/uploads/'):
        return jsonify({'ok': False, 'expired': True})
    fname = url.replace('/uploads/', '')
    filepath = os.path.join(UPLOAD_DIR, fname)
    if not os.path.exists(filepath):
        return jsonify({'ok': True, 'expired': True})
    age = time.time() - os.path.getmtime(filepath)
    return jsonify({'ok': True, 'expired': age > EXPIRE_DAYS * 86400})


# ==================== 头像框 API ====================
FRAMES_CONFIG = [
    {'id': 'default', 'name': '默认蓝', 'min_level': 0, 'price': 0, 'style': 'linear-gradient(135deg, #42a5f5, #1e88e5)'},
    {'id': 'gold', 'name': '金色', 'min_level': 0, 'price': 100, 'style': 'linear-gradient(135deg, #ffd54f, #f57c00)'},
    {'id': 'silver', 'name': '银色', 'min_level': 0, 'price': 80, 'style': 'linear-gradient(135deg, #e0e0e0, #9e9e9e)'},
    {'id': 'diamond', 'name': '钻石色', 'min_level': 0, 'price': 200, 'style': 'linear-gradient(135deg, #b2ebf2, #00acc1, #4dd0e1)'},
]


@app.route('/api/frames/list')
def frames_list():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    u = db.execute('SELECT points, level_frame FROM users WHERE username = ?', (me,)).fetchone()
    if not u: return jsonify({'ok': False, 'error': '用户不存在'}), 404
    pts = u['points'] or 0
    current = u['level_frame'] or 'default'
    owned = []
    try:
        owned = [r['frame_id'] for r in db.execute('SELECT frame_id FROM user_frames WHERE username = ?', (me,)).fetchall()]
    except Exception:
        owned = []
    priv = get_privileges(pts)
    return jsonify({
        'ok': True,
        'frames': FRAMES_CONFIG,
        'points': pts,
        'level': priv['level'],
        'current': current,
        'owned': owned,
    })


@app.route('/api/frames/buy', methods=['POST'])
def frames_buy():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    fid = (data.get('frame_id') or '').strip()
    frame = None
    for f in FRAMES_CONFIG:
        if f['id'] == fid:
            frame = f
            break
    if not frame: return jsonify({'ok': False, 'error': '头像框不存在'}), 404
    if frame['price'] <= 0: return jsonify({'ok': False, 'error': '这个头像框不需要购买'}), 400
    db = get_db()
    u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
    pts = (u['points'] if u else 0) or 0
    if pts < frame['price']: return jsonify({'ok': False, 'error': '积分不足'}), 400
    if db.execute('SELECT 1 FROM user_frames WHERE username = ? AND frame_id = ?', (me, fid)).fetchone():
        return jsonify({'ok': False, 'error': '你已经拥有这个头像框'}), 400
    db.execute('UPDATE users SET points = points - ? WHERE username = ?', (frame['price'], me))
    db.execute('INSERT INTO user_frames (username, frame_id, purchased_at) VALUES (?, ?, ?)', (me, fid, time.time()))
    add_points(db, me, 0, f"购买头像框 {frame['name']}")
    db.commit()
    return jsonify({'ok': True})


@app.route('/api/frames/equip', methods=['POST'])
def frames_equip():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    fid = (data.get('frame_id') or 'default').strip()
    frame = None
    for f in FRAMES_CONFIG:
        if f['id'] == fid:
            frame = f
            break
    if not frame: return jsonify({'ok': False, 'error': '头像框不存在'}), 404
    db = get_db()
    u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
    pts = (u['points'] if u else 0) or 0
    priv = get_privileges(pts)
    if priv['level'] < frame['min_level']:
        return jsonify({'ok': False, 'error': f'需要等级 Lv.{frame["min_level"]} 才能解锁'}), 403
    if frame['price'] > 0:
        if not db.execute('SELECT 1 FROM user_frames WHERE username = ? AND frame_id = ?', (me, fid)).fetchone():
            return jsonify({'ok': False, 'error': '你还没有购买此头像框'}), 403
    db.execute('UPDATE users SET level_frame = ? WHERE username = ?', (fid, me))
    db.commit()
    return jsonify({'ok': True})


# ==================== 好友备注 ====================
@app.route('/api/friend/remark', methods=['POST'])
def friend_remark():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    peer = (data.get('peer') or '').strip()
    remark = (data.get('remark') or '').strip()[:20]
    if not peer or peer == me:
        return jsonify({'ok': False, 'error': '参数无效'}), 400
    db = get_db()
    if not are_friends(db, me, peer):
        return jsonify({'ok': False, 'error': '不是好友'}), 403
    # 建表（如果没建）
    db.execute('''CREATE TABLE IF NOT EXISTS friend_remarks (
        owner TEXT NOT NULL,
        peer TEXT NOT NULL,
        remark TEXT NOT NULL,
        updated_at REAL NOT NULL,
        PRIMARY KEY (owner, peer)
    )''')
    if remark:
        # 清理脏话
        cleaned, _ = clean_text(remark)
        if cleaned: remark = cleaned
        db.execute('INSERT OR REPLACE INTO friend_remarks (owner, peer, remark, updated_at) VALUES (?, ?, ?, ?)',
                   (me, peer, remark, time.time()))
    else:
        db.execute('DELETE FROM friend_remarks WHERE owner = ? AND peer = ?', (me, peer))
    db.commit()
    return jsonify({'ok': True, 'remark': remark})


@app.route('/api/friend/remarks')
def friend_remarks_list():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    db = get_db()
    try:
        rows = db.execute('SELECT peer, remark FROM friend_remarks WHERE owner = ?', (me,)).fetchall()
        result = {r['peer']: r['remark'] for r in rows}
    except Exception:
        result = {}
    return jsonify({'ok': True, 'remarks': result})


# ==================== 消息搜索 ====================
@app.route('/api/messages/search')
def messages_search():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    q = (request.args.get('q') or '').strip()[:50]
    room = (request.args.get('room') or '').strip()
    if not q: return jsonify({'ok': False, 'error': '请输入关键词'}), 400
    if not room: return jsonify({'ok': False, 'error': '缺少房间'}), 400
    typ, data2 = parse_room(room)
    db = get_db()
    if typ == 'private':
        if me not in data2: return jsonify({'ok': False, 'error': '无效房间'}), 400
        other = data2[0] if data2[1] == me else data2[1]
        if not are_friends(db, me, other):
            return jsonify({'ok': False, 'error': '不是好友'}), 403
    elif typ == 'group':
        if not is_group_member(db, data2, me):
            return jsonify({'ok': False, 'error': '你不在该群'}), 403
    else:
        return jsonify({'ok': False, 'error': '无效房间'}), 400

    like = '%' + q + '%'
    rows = db.execute(
        'SELECT id, sender, content, created_at FROM messages WHERE room = ? AND content LIKE ? ORDER BY id DESC LIMIT 100',
        (room, like)
    ).fetchall()
    result = []
    for r in rows:
        c = r['content'] or ''
        if c.startswith('{'):
            continue  # 跳过图片/视频/语音等 JSON 消息
        result.append({
            'id': r['id'],
            'sender': r['sender'],
            'content': c[:200],
            'created_at': r['created_at']
        })
    return jsonify({'ok': True, 'messages': result, 'count': len(result)})


# ==================== 积分红包 ====================
import random as _random

_rp_tables_ready = False

def _ensure_red_packet_tables(db):
    global _rp_tables_ready
    if _rp_tables_ready:
        return
    _rp_tables_ready = True
    db.execute('''CREATE TABLE IF NOT EXISTS red_packets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT NOT NULL,
        room TEXT NOT NULL,
        total_points INTEGER NOT NULL,
        total_count INTEGER NOT NULL,
        remain_points INTEGER NOT NULL,
        remain_count INTEGER NOT NULL,
        created_at REAL NOT NULL,
        expire_at REAL NOT NULL,
        message_id INTEGER
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS red_packet_grabs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        packet_id INTEGER NOT NULL,
        username TEXT NOT NULL,
        points INTEGER NOT NULL,
        created_at REAL NOT NULL,
        UNIQUE(packet_id, username)
    )''')


def _grab_random_amount(remain_points, remain_count):
    """二倍均值算法，保证每人至少 1 分"""
    if remain_count <= 1:
        return remain_points
    # 1 到 (remain_points / remain_count) * 2 之间
    max_amt = int(remain_points / remain_count * 2)
    if max_amt < 1: max_amt = 1
    amt = _random.randint(1, max_amt)
    # 保证后面每人至少 1 分
    if remain_points - amt < remain_count - 1:
        amt = remain_points - (remain_count - 1)
    return amt


@app.route('/api/redpacket/send', methods=['POST'])
def redpacket_send():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    room = (data.get('room') or '').strip()
    try:
        total = int(data.get('total_points', 0))
        count = int(data.get('total_count', 0))
    except (TypeError, ValueError):
        return jsonify({'ok': False, 'error': '参数错误'}), 400

    if not room: return jsonify({'ok': False, 'error': '缺少房间'}), 400
    if total < count: return jsonify({'ok': False, 'error': '总积分不能少于个数'}), 400
    if count < 1 or count > 100: return jsonify({'ok': False, 'error': '个数需在 1-100'}), 400
    if total > 100000: return jsonify({'ok': False, 'error': '总积分不能超过 10 万'}), 400

    typ, data2 = parse_room(room)
    db = get_db()
    if typ == 'private':
        if me not in data2: return jsonify({'ok': False, 'error': '无效房间'}), 400
        other = data2[0] if data2[1] == me else data2[1]
        if not are_friends(db, me, other): return jsonify({'ok': False, 'error': '不是好友'}), 403
    elif typ == 'group':
        if not is_group_member(db, data2, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403
    else:
        return jsonify({'ok': False, 'error': '无效房间'}), 400

    # 检查积分
    u = db.execute('SELECT points FROM users WHERE username = ?', (me,)).fetchone()
    pts = (u['points'] if u else 0) or 0
    if pts < total:
        return jsonify({'ok': False, 'error': '积分不足'}), 400

    _ensure_red_packet_tables(db)
    now = time.time()
    expire = now + 86400  # 24 小时

    # 扣积分
    db.execute('UPDATE users SET points = points - ? WHERE username = ?', (total, me))
    add_points(db, me, 0, f'发红包 {total} 分 {count} 个')

    # 记录红包
    cur = db.execute(
        'INSERT INTO red_packets (sender, room, total_points, total_count, remain_points, remain_count, created_at, expire_at) '
        'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
        (me, room, total, count, total, count, now, expire)
    )
    packet_id = cur.lastrowid

    # 发一条消息（红包消息）
    payload = {'type': 'redpacket', 'packet_id': packet_id, 'sender': me, 'total': total, 'count': count}
    content = _json.dumps(payload, ensure_ascii=False)
    mcur = db.execute(
        'INSERT INTO messages (room, sender, content, created_at) VALUES (?, ?, ?, ?)',
        (room, me, content, now)
    )
    mid = mcur.lastrowid
    db.execute('UPDATE red_packets SET message_id = ? WHERE id = ?', (mid, packet_id))
    db.commit()

    return jsonify({'ok': True, 'packet_id': packet_id, 'message_id': mid})


@app.route('/api/redpacket/info')
def redpacket_info():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    try: pid = int(request.args.get('packet_id', 0))
    except ValueError: return jsonify({'ok': False, 'error': '参数错误'}), 400

    db = get_db()
    _ensure_red_packet_tables(db)
    p = db.execute('SELECT * FROM red_packets WHERE id = ?', (pid,)).fetchone()
    if not p: return jsonify({'ok': False, 'error': '红包不存在'}), 404

    # 检查访问权限
    typ, data2 = parse_room(p['room'])
    if typ == 'private':
        if me not in data2: return jsonify({'ok': False, 'error': '无权查看'}), 403
    elif typ == 'group':
        if not is_group_member(db, data2, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403

    # 是否已经抢过
    mine = db.execute('SELECT points FROM red_packet_grabs WHERE packet_id = ? AND username = ?', (pid, me)).fetchone()
    # 抢包记录
    grabs = db.execute('SELECT username, points, created_at FROM red_packet_grabs WHERE packet_id = ? ORDER BY id ASC', (pid,)).fetchall()
    grabbed_list = [{'username': g['username'], 'points': g['points'], 'time': g['created_at']} for g in grabs]

    expired = time.time() > p['expire_at']
    finished = p['remain_count'] <= 0

    return jsonify({
        'ok': True,
        'packet': {
            'id': p['id'],
            'sender': p['sender'],
            'total_points': p['total_points'],
            'total_count': p['total_count'],
            'remain_points': p['remain_points'],
            'remain_count': p['remain_count'],
            'created_at': p['created_at'],
            'expire_at': p['expire_at'],
            'expired': expired,
            'finished': finished,
        },
        'my_grab': mine['points'] if mine else None,
        'grabs': grabbed_list,
    })


@app.route('/api/redpacket/grab', methods=['POST'])
def redpacket_grab():
    me = require_auth()
    if not me: return jsonify({'ok': False, 'error': '请先登录'}), 401
    data = request.get_json() or {}
    try: pid = int(data.get('packet_id', 0))
    except (TypeError, ValueError): return jsonify({'ok': False, 'error': '参数错误'}), 400

    db = get_db()
    _ensure_red_packet_tables(db)
    p = db.execute('SELECT * FROM red_packets WHERE id = ?', (pid,)).fetchone()
    if not p: return jsonify({'ok': False, 'error': '红包不存在'}), 404

    # 权限
    typ, data2 = parse_room(p['room'])
    if typ == 'private':
        if me not in data2: return jsonify({'ok': False, 'error': '无权查看'}), 403
    elif typ == 'group':
        if not is_group_member(db, data2, me): return jsonify({'ok': False, 'error': '你不在该群'}), 403

    if p['sender'] == me:
        return jsonify({'ok': False, 'error': '不能抢自己发的红包'}), 400
    if time.time() > p['expire_at']:
        return jsonify({'ok': False, 'error': '红包已过期'}), 400
    if p['remain_count'] <= 0:
        return jsonify({'ok': False, 'error': '红包已被抢完'}), 400

    # 是否抢过
    exist = db.execute('SELECT points FROM red_packet_grabs WHERE packet_id = ? AND username = ?', (pid, me)).fetchone()
    if exist:
        return jsonify({'ok': True, 'points': exist['points'], 'already': True})

    # 抢
    amt = _grab_random_amount(p['remain_points'], p['remain_count'])
    db.execute('UPDATE red_packets SET remain_points = remain_points - ?, remain_count = remain_count - 1 WHERE id = ?', (amt, pid))
    db.execute('INSERT INTO red_packet_grabs (packet_id, username, points, created_at) VALUES (?, ?, ?, ?)', (pid, me, amt, time.time()))
    add_points(db, me, amt, f'抢红包 #{pid}')
    db.commit()
    return jsonify({'ok': True, 'points': amt})

init_db()

# ========== 新功能注册（16 个） ==========
from new_features import register_routes as _nf_register
_nf_register(app, {
    'get_db': get_db,
    'require_auth': require_auth,
    'are_friends': are_friends,
    'is_group_member': is_group_member,
    'make_room': make_room,
    'group_room': group_room,
    'parse_room': parse_room,
    'clean_text': clean_text,
    'add_points': add_points,
    'touch_user': touch_user,
    'ONLINE_WINDOW': ONLINE_WINDOW,
})



# ========== 游戏排行 + 反馈 ==========
from new_features2 import register_routes as _nf2_register
_nf2_register(app, {
    'get_db': get_db,
    'require_auth': require_auth,
    'touch_user': touch_user,
    'clean_text': clean_text,
})


# ========== 九宫格锁 + 设置 ==========
from new_features3 import register_routes as _nf3_register
_nf3_register(app, {
    'get_db': get_db,
    'require_auth': require_auth,
})


# ========== 步数 ==========
from new_features4 import register_routes as _nf4_register
_nf4_register(app, {
    'get_db': get_db,
    'require_auth': require_auth,
})


# ========== Web Push 推送 ==========
from new_features5 import register_routes as _nf5_register
_nf5_register(app, {
    'get_db': get_db,
    'require_auth': require_auth,
})




# ========== 错过消息提醒 ==========
from new_features7 import register_routes as _nf7_register
_nf7_register(app, {
    'get_db': get_db,
    'require_auth': require_auth,
    'make_room': make_room,
})


# ========== 第1批：正在输入/定时/动态视频/挂件 ==========
from new_features8 import register_routes as _nf8_register
_nf8_register(app, {
    'get_db': get_db,
    'require_auth': require_auth,
    'are_friends': are_friends,
    'make_room': make_room,
    'is_group_member': is_group_member,
    'group_room': group_room,
})


# ========== 第2批 ==========
from new_features9 import register_routes as _nf9_register
_nf9_register(app, {
    'get_db': get_db,
    'require_auth': require_auth,
    'are_friends': are_friends,
    'make_room': make_room,
    'is_group_member': is_group_member,
    'group_room': group_room,
    'parse_room': parse_room,
    'add_points': add_points,
})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, threaded=True, debug=False)
