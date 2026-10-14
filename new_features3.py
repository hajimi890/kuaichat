# -*- coding: utf-8 -*-
"""九宫格锁 + 用户设置"""
import time, hashlib, secrets
from flask import request, jsonify


def register_routes(app, deps):
    get_db = deps['get_db']
    require_auth = deps['require_auth']

    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS pattern_lock (
                username TEXT PRIMARY KEY,
                pattern_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                enabled INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                locked_until REAL DEFAULT 0,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS user_settings (
                username TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                updated_at REAL NOT NULL,
                PRIMARY KEY (username, key)
            );
        ''')
        db.commit()

    def _hash_pattern(pattern, salt):
        return hashlib.sha256((salt + '::' + pattern).encode('utf-8')).hexdigest()

    @app.route('/api/pattern/status')
    def api_pattern_status():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        row = db.execute("SELECT enabled FROM pattern_lock WHERE username = ?", (me,)).fetchone()
        enabled = bool(row and row['enabled'])
        return jsonify({'ok': True, 'enabled': enabled})

    @app.route('/api/pattern/set', methods=['POST'])
    def api_pattern_set():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        pattern = (data.get('pattern') or '').strip()
        if not pattern or len(pattern) < 4 or len(pattern) > 9:
            return jsonify({'ok': False, 'error': '密码至少 4 个点'}), 400
        if not all(c.isdigit() and '1' <= c <= '9' for c in pattern):
            return jsonify({'ok': False, 'error': '格式错误'}), 400
        salt = secrets.token_hex(16)
        h = _hash_pattern(pattern, salt)
        db = get_db()
        db.execute('''INSERT OR REPLACE INTO pattern_lock
            (username, pattern_hash, salt, enabled, failed_count, locked_until, updated_at)
            VALUES (?, ?, ?, 1, 0, 0, ?)''', (me, h, salt, time.time()))
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/pattern/verify', methods=['POST'])
    def api_pattern_verify():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        pattern = (data.get('pattern') or '').strip()
        if not pattern:
            return jsonify({'ok': False, 'error': '请输入密码'}), 400
        db = get_db()
        row = db.execute("SELECT * FROM pattern_lock WHERE username = ?", (me,)).fetchone()
        if not row or not row['enabled']:
            return jsonify({'ok': True, 'skipped': True})
        now = time.time()
        if row['locked_until'] and row['locked_until'] > now:
            return jsonify({'ok': False, 'error': '锁定中，请稍后', 'locked_until': row['locked_until']}), 429
        calc = _hash_pattern(pattern, row['salt'])
        if calc == row['pattern_hash']:
            db.execute("UPDATE pattern_lock SET failed_count = 0, locked_until = 0 WHERE username = ?", (me,))
            db.commit()
            return jsonify({'ok': True})
        fails = (row['failed_count'] or 0) + 1
        locked_until = 0
        if fails >= 5:
            locked_until = now + 300
        db.execute("UPDATE pattern_lock SET failed_count = ?, locked_until = ? WHERE username = ?",
                   (fails, locked_until, me))
        db.commit()
        return jsonify({'ok': False, 'error': '密码错误', 'failed': fails,
                        'locked_until': locked_until})

    @app.route('/api/pattern/disable', methods=['POST'])
    def api_pattern_disable():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        db.execute("UPDATE pattern_lock SET enabled = 0 WHERE username = ?", (me,))
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/settings/get')
    def api_settings_get():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        rows = db.execute("SELECT key, value FROM user_settings WHERE username = ?", (me,)).fetchall()
        return jsonify({'ok': True, 'settings': {r['key']: r['value'] for r in rows}})

    @app.route('/api/settings/set', methods=['POST'])
    def api_settings_set():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        key = (data.get('key') or '').strip()[:64]
        value = str(data.get('value', ''))[:500]
        if not key:
            return jsonify({'ok': False, 'error': '缺少 key'}), 400
        db = get_db()
        db.execute('''INSERT OR REPLACE INTO user_settings (username, key, value, updated_at)
            VALUES (?, ?, ?, ?)''', (me, key, value, time.time()))
        db.commit()
        return jsonify({'ok': True})

    print("[new_features3] 九宫格锁 + 设置 路由已注册")
