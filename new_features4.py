# -*- coding: utf-8 -*-
"""步数记录"""
import time
from flask import request, jsonify


def register_routes(app, deps):
    get_db = deps['get_db']
    require_auth = deps['require_auth']

    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                day TEXT NOT NULL,
                steps INTEGER NOT NULL DEFAULT 0,
                updated_at REAL NOT NULL,
                UNIQUE(username, day)
            );
            CREATE INDEX IF NOT EXISTS idx_steps_day ON steps(day, steps DESC);
        ''')
        db.commit()

    @app.route('/api/steps/today')
    def api_steps_today():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        today = time.strftime('%Y-%m-%d')
        db = get_db()
        row = db.execute("SELECT steps FROM steps WHERE username = ? AND day = ?", (me, today)).fetchone()
        return jsonify({'ok': True, 'steps': row['steps'] if row else 0, 'day': today})

    @app.route('/api/steps/add', methods=['POST'])
    def api_steps_add():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        try:
            delta = int(data.get('delta', 1))
        except (TypeError, ValueError):
            delta = 1
        delta = max(1, min(1000, delta))
        today = time.strftime('%Y-%m-%d')
        now = time.time()
        db = get_db()
        row = db.execute("SELECT id, steps FROM steps WHERE username = ? AND day = ?", (me, today)).fetchone()
        if row:
            db.execute("UPDATE steps SET steps = steps + ?, updated_at = ? WHERE id = ?", (delta, now, row['id']))
            new_steps = row['steps'] + delta
        else:
            db.execute("INSERT INTO steps (username, day, steps, updated_at) VALUES (?, ?, ?, ?)", (me, today, delta, now))
            new_steps = delta
        db.commit()
        return jsonify({'ok': True, 'steps': new_steps})

    @app.route('/api/steps/rank')
    def api_steps_rank():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        today = time.strftime('%Y-%m-%d')
        db = get_db()
        rows = db.execute("SELECT username, steps FROM steps WHERE day = ? ORDER BY steps DESC LIMIT 20", (today,)).fetchall()
        result = []
        for i, r in enumerate(rows, 1):
            result.append({'rank': i, 'username': r['username'], 'steps': r['steps']})
        my = db.execute("SELECT steps FROM steps WHERE username = ? AND day = ?", (me, today)).fetchone()
        my_steps = my['steps'] if my else 0
        my_rank = None
        if my_steps > 0:
            cnt = db.execute("SELECT COUNT(*) AS c FROM steps WHERE day = ? AND steps > ?", (today, my_steps)).fetchone()['c']
            my_rank = cnt + 1
        return jsonify({'ok': True, 'day': today, 'list': result, 'my_steps': my_steps, 'my_rank': my_rank})

    print("[new_features4] 步数 路由已注册")
