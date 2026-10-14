# -*- coding: utf-8 -*-
"""第1批：正在输入 / 定时发送 / 动态视频 / 头像挂件"""
import time
from flask import request, jsonify


def register_routes(app, deps):
    get_db = deps['get_db']
    require_auth = deps['require_auth']
    are_friends = deps['are_friends']
    make_room = deps['make_room']
    is_group_member = deps['is_group_member']
    group_room = deps['group_room']

    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS typing_status (
                room TEXT NOT NULL,
                username TEXT NOT NULL,
                updated_at REAL NOT NULL,
                PRIMARY KEY (room, username)
            );
            CREATE TABLE IF NOT EXISTS scheduled_msgs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                room TEXT NOT NULL,
                content TEXT NOT NULL,
                send_at REAL NOT NULL,
                created_at REAL NOT NULL,
                sent INTEGER DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS idx_sched_time ON scheduled_msgs(sent, send_at);
        ''')
        cols = [r[1] for r in db.execute('PRAGMA table_info(users)').fetchall()]
        if 'avatar_frame' not in cols:
            db.execute("ALTER TABLE users ADD COLUMN avatar_frame TEXT DEFAULT ''")
            db.commit()
        # 动态视频字段
        mcols = [r[1] for r in db.execute('PRAGMA table_info(moments)').fetchall()]
        if 'video_url' not in mcols:
            db.execute("ALTER TABLE moments ADD COLUMN video_url TEXT DEFAULT ''")
            db.commit()
        print("[nf8] 表结构已就绪")

    # ===== 1. 正在输入 =====
    @app.route('/api/typing', methods=['POST'])
    def api_typing():
        me = require_auth()
        if not me:
            return jsonify({'ok': False}), 401
        data = request.get_json() or {}
        room = (data.get('room') or '').strip()
        if not room:
            return jsonify({'ok': False, 'error': '缺少 room'}), 400
        db = get_db()
        db.execute("INSERT OR REPLACE INTO typing_status (room, username, updated_at) VALUES (?, ?, ?)",
                   (room, me, time.time()))
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/typing/check')
    def api_typing_check():
        me = require_auth()
        if not me:
            return jsonify({'ok': False}), 401
        room = (request.args.get('room') or '').strip()
        if not room:
            return jsonify({'ok': False, 'error': '缺少 room'}), 400
        db = get_db()
        cutoff = time.time() - 4
        rows = db.execute("SELECT username FROM typing_status WHERE room = ? AND username != ? AND updated_at > ?",
                          (room, me, cutoff)).fetchall()
        return jsonify({'ok': True, 'typing': [r['username'] for r in rows]})

    # ===== 2. 定时发送 =====
    @app.route('/api/schedule_msg', methods=['POST'])
    def api_schedule_msg():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        room = (data.get('room') or '').strip()
        content = (data.get('content') or '').strip()[:2000]
        try:
            delay_min = int(data.get('delay_min', 0))
        except (TypeError, ValueError):
            delay_min = 0
        if not room or not content:
            return jsonify({'ok': False, 'error': '参数不完整'}), 400
        if delay_min < 1 or delay_min > 24 * 60:
            return jsonify({'ok': False, 'error': '延迟需在 1 分钟到 24 小时'}), 400
        db = get_db()
        db.execute("INSERT INTO scheduled_msgs (username, room, content, send_at, created_at) VALUES (?, ?, ?, ?, ?)",
                   (me, room, content, time.time() + delay_min * 60, time.time()))
        db.commit()
        return jsonify({'ok': True, 'at': time.strftime('%H:%M', time.localtime(time.time() + delay_min * 60))})

    @app.route('/api/scheduled/list')
    def api_scheduled_list():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        rows = db.execute("SELECT id, room, content, send_at FROM scheduled_msgs WHERE username = ? AND sent = 0 ORDER BY send_at ASC",
                          (me,)).fetchall()
        return jsonify({'ok': True, 'list': [dict(r) for r in rows]})

    @app.route('/api/scheduled/cancel', methods=['POST'])
    def api_scheduled_cancel():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        try:
            mid = int(data.get('id'))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': '参数错误'}), 400
        db = get_db()
        db.execute("DELETE FROM scheduled_msgs WHERE id = ? AND username = ?", (mid, me))
        db.commit()
        return jsonify({'ok': True})

    # ===== 3. 动态发视频 =====
    @app.route('/api/moment/post_video', methods=['POST'])
    def api_moment_post_video():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        content = (data.get('content') or '').strip()[:500]
        video_url = (data.get('video_url') or '').strip()[:300]
        image_url = (data.get('image_url') or '').strip()[:300]
        if not content and not video_url and not image_url:
            return jsonify({'ok': False, 'error': '内容不能为空'}), 400
        db = get_db()
        cur = db.execute(
            "INSERT INTO moments (username, content, image_url, video_url, likes, created_at) VALUES (?, ?, ?, ?, '', ?)",
            (me, content, image_url, video_url, time.time())
        )
        db.commit()
        return jsonify({'ok': True, 'id': cur.lastrowid})

    # ===== 4. 头像挂件 =====
    FRAMES = [
        {'id': '',           'name': '无',       'price': 0},
        {'id': 'frame_hat',  'name': '🎩 礼帽',   'price': 50},
        {'id': 'frame_crown','name': '👑 皇冠',   'price': 200},
        {'id': 'frame_flower','name': '🌸 樱花',  'price': 80},
        {'id': 'frame_fire', 'name': '🔥 火焰',   'price': 120},
        {'id': 'frame_star', 'name': '⭐ 星星',   'price': 60},
        {'id': 'frame_ghost','name': '👻 幽灵',   'price': 150},
    ]

    @app.route('/api/frame/list')
    def api_frame_list():
        me = require_auth()
        db = get_db()
        row = None
        if me:
            row = db.execute("SELECT avatar_frame, points FROM users WHERE username = ?", (me,)).fetchone()
        return jsonify({'ok': True, 'frames': FRAMES, 'current': (row['avatar_frame'] if row else '') or '', 'points': (row['points'] if row else 0) or 0})

    @app.route('/api/frame/buy', methods=['POST'])
    def api_frame_buy():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        fid = (data.get('id') or '').strip()
        frame = next((f for f in FRAMES if f['id'] == fid), None)
        if not frame:
            return jsonify({'ok': False, 'error': '挂件不存在'}), 404
        if frame['price'] <= 0:
            return jsonify({'ok': False, 'error': '无需购买'}), 400
        db = get_db()
        u = db.execute("SELECT points FROM users WHERE username = ?", (me,)).fetchone()
        pts = (u['points'] if u else 0) or 0
        if pts < frame['price']:
            return jsonify({'ok': False, 'error': '积分不足'}), 400
        db.execute("UPDATE users SET points = points - ? WHERE username = ?", (frame['price'], me))
        db.execute("UPDATE users SET avatar_frame = ? WHERE username = ?", (fid, me))
        db.commit()
        return jsonify({'ok': True})

    @app.route('/api/frame/equip', methods=['POST'])
    def api_frame_equip():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        fid = (data.get('id') or '').strip()
        db = get_db()
        db.execute("UPDATE users SET avatar_frame = ? WHERE username = ?", (fid, me))
        db.commit()
        return jsonify({'ok': True})

    print("[new_features8] 第1批路由 已注册")
