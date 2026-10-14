# -*- coding: utf-8 -*-
"""错过消息提醒"""
import time
from flask import request, jsonify


def register_routes(app, deps):
    get_db = deps['get_db']
    require_auth = deps['require_auth']
    make_room = deps['make_room']

    with app.app_context():
        db = get_db()
        cols = [r[1] for r in db.execute('PRAGMA table_info(users)').fetchall()]
        if 'last_active' not in cols:
            db.execute('ALTER TABLE users ADD COLUMN last_active REAL DEFAULT 0')
            db.commit()
            print("[nf7] users.last_active 已加")

    @app.route('/api/missed_since_last_visit')
    def api_missed():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        row = db.execute("SELECT last_active FROM users WHERE username = ?", (me,)).fetchone()
        last = (row['last_active'] or 0) if row else 0
        now = time.time()
        # 距离上次访问超过 30 秒才算"离开过"
        if now - last < 30:
            db.execute("UPDATE users SET last_active = ? WHERE username = ?", (now, me))
            db.commit()
            return jsonify({'ok': True, 'count': 0, 'items': []})
        # 查所有私聊房间的未读消息
        friends = db.execute("SELECT user_a, user_b FROM friends WHERE user_a = ? OR user_b = ?", (me, me)).fetchall()
        items = []
        total = 0
        for f in friends:
            other = f['user_b'] if f['user_a'] == me else f['user_a']
            room = make_room(me, other)
            cnt = db.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE room = ? AND sender = ? AND created_at > ?",
                (room, other, last)
            ).fetchone()['c']
            if cnt > 0:
                total += cnt
                lm = db.execute(
                    "SELECT content, created_at FROM messages WHERE room = ? AND sender = ? AND created_at > ? ORDER BY id DESC LIMIT 1",
                    (room, other, last)
                ).fetchone()
                items.append({
                    'type': 'private',
                    'from': other,
                    'count': cnt,
                    'last': (lm['content'] if lm else '')[:40],
                    'time': lm['created_at'] if lm else 0
                })
        # 查群聊
        groups = db.execute("SELECT group_id FROM group_members WHERE username = ?", (me,)).fetchall()
        for g in groups:
            gid = g['group_id']
            room = 'group_' + str(gid)
            cnt = db.execute(
                "SELECT COUNT(*) AS c FROM messages WHERE room = ? AND sender != ? AND created_at > ?",
                (room, me, last)
            ).fetchone()['c']
            if cnt > 0:
                total += cnt
                gi = db.execute("SELECT name FROM groups WHERE id = ?", (gid,)).fetchone()
                items.append({
                    'type': 'group',
                    'id': gid,
                    'name': gi['name'] if gi else '群聊',
                    'count': cnt
                })
        # 更新 last_active
        db.execute("UPDATE users SET last_active = ? WHERE username = ?", (now, me))
        db.commit()
        items.sort(key=lambda x: -x.get('time', 0))
        return jsonify({'ok': True, 'count': total, 'items': items[:20]})

    @app.route('/api/heartbeat', methods=['POST'])
    def api_heartbeat():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        db.execute("UPDATE users SET last_active = ? WHERE username = ?", (time.time(), me))
        db.commit()
        return jsonify({'ok': True})

    print("[new_features7] 错过消息 已注册")
