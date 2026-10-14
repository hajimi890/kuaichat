# -*- coding: utf-8 -*-
"""Web Push 推送"""
import os, io, json as _json, time
from flask import request, jsonify


def register_routes(app, deps):
    get_db = deps['get_db']
    require_auth = deps['require_auth']

    # 读 VAPID 密钥
    VAPID_PUBLIC = ''
    VAPID_PRIVATE = ''
    kf = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vapid_keys.txt')
    if os.path.exists(kf):
        with io.open(kf, 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('PUBLIC='):
                    VAPID_PUBLIC = line.strip().split('=', 1)[1]
                elif line.startswith('PRIVATE='):
                    VAPID_PRIVATE = line.split('=', 1)[1]
    # 私钥是多行 PEM，重新读一遍完整
    if os.path.exists(kf):
        with io.open(kf, 'r', encoding='utf-8') as f:
            content = f.read()
            if 'PRIVATE=' in content and '-----BEGIN' in content:
                VAPID_PRIVATE = content.split('PRIVATE=', 1)[1]

    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS push_subs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_seen REAL
            );
            CREATE INDEX IF NOT EXISTS idx_push_subs_user ON push_subs(username);
        ''')
        db.commit()

    @app.route('/api/push/public_key')
    def api_push_public_key():
        return jsonify({'ok': True, 'publicKey': VAPID_PUBLIC})

    @app.route('/api/push/subscribe', methods=['POST'])
    def api_push_subscribe():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        sub = data.get('subscription') or {}
        endpoint = (sub.get('endpoint') or '').strip()
        keys = sub.get('keys') or {}
        p256dh = (keys.get('p256dh') or '').strip()
        auth = (keys.get('auth') or '').strip()
        if not endpoint or not p256dh or not auth:
            return jsonify({'ok': False, 'error': '订阅数据不完整'}), 400
        db = get_db()
        # 先删同 endpoint 旧记录
        db.execute("DELETE FROM push_subs WHERE endpoint = ?", (endpoint,))
        db.execute(
            "INSERT INTO push_subs (username, endpoint, p256dh, auth, created_at) VALUES (?, ?, ?, ?, ?)",
            (me, endpoint, p256dh, auth, time.time())
        )
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/push/unsubscribe', methods=['POST'])
    def api_push_unsubscribe():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        endpoint = (data.get('endpoint') or '').strip()
        if endpoint:
            db = get_db()
            db.execute("DELETE FROM push_subs WHERE endpoint = ? AND username = ?", (endpoint, me))
            db.commit()
        return jsonify({'ok': True})

    @app.route('/api/push/test', methods=['POST'])
    def api_push_test():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        sent = _send_push_to_user(get_db(), me, '🔔 测试推送', '这是一条测试消息')
        return jsonify({'ok': True, 'sent': sent})

    # 供 app.py 里的 send / group_send 调用
    def push_new_message(room, sender, content_preview):
        """给房间里的所有其他人发推送"""
        try:
            db = get_db()
            if room.startswith('group_'):
                gid = int(room[6:])
                rows = db.execute("SELECT username FROM group_members WHERE group_id = ? AND username != ?", (gid, sender)).fetchall()
                usernames = [r['username'] for r in rows]
                title = '群消息'
            else:
                parts = room.split('__')
                if len(parts) != 2: return
                other = parts[0] if parts[1] == sender else parts[1]
                usernames = [other]
                title = sender
            for u in usernames:
                _send_push_to_user(db, u, title, content_preview[:60])
        except Exception as e:
            print('[push err]', e)

    def _send_push_to_user(db, username, title, body):
        if not VAPID_PRIVATE or not VAPID_PUBLIC:
            return 0
        try:
            from pywebpush import webpush, WebPushException
        except ImportError:
            print('[push] pywebpush 未安装')
            return 0
        rows = db.execute("SELECT endpoint, p256dh, auth FROM push_subs WHERE username = ?", (username,)).fetchall()
        sent = 0
        payload = _json.dumps({
            'title': title,
            'body': body,
            'url': '/chat',
            'tag': 'msg_' + str(int(time.time()))
        }, ensure_ascii=False)
        for r in rows:
            try:
                webpush(
                    subscription_info={
                        'endpoint': r['endpoint'],
                        'keys': {'p256dh': r['p256dh'], 'auth': r['auth']}
                    },
                    data=payload,
                    vapid_private_key=VAPID_PRIVATE,
                    vapid_claims={'sub': 'mailto:admin@fastchat.cc.cd'}
                )
                sent += 1
            except Exception as e:
                err_msg = str(e)
                # 410 Gone → 订阅失效，删除
                if '410' in err_msg or '404' in err_msg:
                    db.execute("DELETE FROM push_subs WHERE endpoint = ?", (r['endpoint'],))
                else:
                    print('[push err]', err_msg[:120])
        if sent:
            db.commit()
        return sent

    # 暴露给 app.py
    app.config['push_new_message'] = push_new_message

    print(f"[new_features5] 推送 路由已注册 (public_key={'有' if VAPID_PUBLIC else '无'})")
