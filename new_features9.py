# -*- coding: utf-8 -*-
"""第2批：合并转发 / 每日任务 / 成就 / 日期搜索"""
import time, json as _json
from flask import request, jsonify


def register_routes(app, deps):
    get_db = deps['get_db']
    require_auth = deps['require_auth']
    are_friends = deps['are_friends']
    make_room = deps['make_room']
    is_group_member = deps['is_group_member']
    group_room = deps['group_room']
    parse_room = deps['parse_room']
    add_points = deps['add_points']

    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS daily_tasks (
                username TEXT NOT NULL,
                day TEXT NOT NULL,
                task_key TEXT NOT NULL,
                done_at REAL NOT NULL,
                PRIMARY KEY (username, day, task_key)
            );
            CREATE TABLE IF NOT EXISTS user_achievements (
                username TEXT NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at REAL NOT NULL,
                PRIMARY KEY (username, achievement_id)
            );
            CREATE TABLE IF NOT EXISTS achievements_meta (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                desc TEXT,
                icon TEXT
            );
        ''')
        ACH = [
            ('ach_first_msg', '初次开口', '发出第一条消息', 'fa-comment'),
            ('ach_10_friends', '社交达人', '添加 10 个好友', 'fa-user-friends'),
            ('ach_100_msgs', '话匣子', '累计发送 100 条消息', 'fa-comments'),
            ('ach_1000_msgs', '千言万语', '累计发送 1000 条消息', 'fa-scroll'),
            ('ach_sign_7', '坚持一周', '连续签到 7 天', 'fa-calendar-check'),
            ('ach_first_moment', '初次分享', '发布第一条动态', 'fa-image'),
            ('ach_level_3', '尊享会员', '积分达到 500', 'fa-crown'),
            ('ach_pet_owner', '铲屎官', '领养一只宠物', 'fa-paw'),
        ]
        for aid, name, desc, icon in ACH:
            db.execute("INSERT OR IGNORE INTO achievements_meta (id, name, desc, icon) VALUES (?, ?, ?, ?)", (aid, name, desc, icon))
        db.commit()
        print("[nf9] 第2批 表结构已就绪")

    @app.route('/api/messages/forward_batch', methods=['POST'])
    def api_forward_batch():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        ids = data.get('ids') or []
        target_type = (data.get('target_type') or '').strip()
        target_id = (data.get('target_id') or '').strip()
        if not isinstance(ids, list) or not ids or not target_type or not target_id:
            return jsonify({'ok': False, 'error': '参数不完整'}), 400
        db = get_db()
        collected = []
        for mid in ids[:30]:
            try: mid = int(mid)
            except: continue
            row = db.execute("SELECT sender, content FROM messages WHERE id = ?", (mid,)).fetchone()
            if row:
                collected.append({'sender': row['sender'], 'content': row['content']})
        if not collected:
            return jsonify({'ok': False, 'error': '没有可转发的消息'}), 400
        if target_type == 'user':
            if not are_friends(db, me, target_id):
                return jsonify({'ok': False, 'error': '对方不是好友'}), 403
            room = make_room(me, target_id)
        elif target_type == 'group':
            try: gid = int(target_id)
            except: return jsonify({'ok': False, 'error': '群 ID 无效'}), 400
            if not is_group_member(db, gid, me):
                return jsonify({'ok': False, 'error': '你不在该群'}), 403
            room = group_room(gid)
        else:
            return jsonify({'ok': False, 'error': '目标类型无效'}), 400
        payload = _json.dumps({'type': 'merged', 'items': collected, 'from': me}, ensure_ascii=False)
        cur = db.execute("INSERT INTO messages (room, sender, content, created_at) VALUES (?, ?, ?, ?)",
                         (room, me, payload, time.time()))
        db.commit()
        return jsonify({'ok': True, 'id': cur.lastrowid})

    TASKS = [
        {'key': 'task_msg', 'name': '发 5 条消息', 'points': 10},
        {'key': 'task_sign', 'name': '今日签到', 'points': 5},
        {'key': 'task_moment', 'name': '发布动态', 'points': 8},
        {'key': 'task_like', 'name': '点赞 2 次', 'points': 5},
    ]

    @app.route('/api/tasks/today')
    def api_tasks_today():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        today = time.strftime('%Y-%m-%d')
        db = get_db()
        done_rows = db.execute("SELECT task_key FROM daily_tasks WHERE username = ? AND day = ?", (me, today)).fetchall()
        done = set(r['task_key'] for r in done_rows)
        if 'task_msg' not in done:
            cnt = db.execute("SELECT COUNT(*) AS c FROM messages WHERE sender = ? AND created_at > ?",
                             (me, time.mktime(time.strptime(today, '%Y-%m-%d')))).fetchone()['c']
            if cnt >= 5:
                db.execute("INSERT OR IGNORE INTO daily_tasks (username, day, task_key, done_at) VALUES (?, ?, 'task_msg', ?)",
                           (me, today, time.time()))
                add_points(db, me, 10, '每日任务:发消息')
                db.commit()
                done.add('task_msg')
        result = []
        for t in TASKS:
            result.append({'key': t['key'], 'name': t['name'], 'points': t['points'], 'done': t['key'] in done})
        return jsonify({'ok': True, 'tasks': result})

    @app.route('/api/tasks/claim', methods=['POST'])
    def api_tasks_claim():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        key = (data.get('key') or '').strip()
        t = next((x for x in TASKS if x['key'] == key), None)
        if not t:
            return jsonify({'ok': False, 'error': '任务不存在'}), 404
        today = time.strftime('%Y-%m-%d')
        db = get_db()
        exists = db.execute("SELECT 1 FROM daily_tasks WHERE username = ? AND day = ? AND task_key = ?", (me, today, key)).fetchone()
        if exists:
            return jsonify({'ok': False, 'error': '今日已完成'}), 400
        db.execute("INSERT INTO daily_tasks (username, day, task_key, done_at) VALUES (?, ?, ?, ?)", (me, today, key, time.time()))
        add_points(db, me, t['points'], '每日任务:' + key)
        db.commit()
        return jsonify({'ok': True, 'points': t['points']})

    @app.route('/api/achievements')
    def api_achievements():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        metas = db.execute("SELECT id, name, desc, icon FROM achievements_meta").fetchall()
        unlocked = set(r['achievement_id'] for r in db.execute("SELECT achievement_id FROM user_achievements WHERE username = ?", (me,)).fetchall())
        out = []
        for m in metas:
            out.append({'id': m['id'], 'name': m['name'], 'desc': m['desc'], 'icon': m['icon'], 'unlocked': m['id'] in unlocked})
        return jsonify({'ok': True, 'list': out})

    @app.route('/api/achievements/check', methods=['POST'])
    def api_achievements_check():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        newly = []
        def unlock(aid):
            try:
                db.execute("INSERT INTO user_achievements (username, achievement_id, unlocked_at) VALUES (?, ?, ?)", (me, aid, time.time()))
                newly.append(aid)
            except Exception:
                pass
        u = db.execute("SELECT points FROM users WHERE username = ?", (me,)).fetchone()
        pts = (u['points'] if u else 0) or 0
        if pts >= 500: unlock('ach_level_3')
        mc = db.execute("SELECT COUNT(*) AS c FROM messages WHERE sender = ?", (me,)).fetchone()['c']
        if mc >= 1: unlock('ach_first_msg')
        if mc >= 100: unlock('ach_100_msgs')
        if mc >= 1000: unlock('ach_1000_msgs')
        fc = db.execute("SELECT COUNT(*) AS c FROM friends WHERE user_a = ? OR user_b = ?", (me, me)).fetchone()['c']
        if fc >= 10: unlock('ach_10_friends')
        moc = db.execute("SELECT COUNT(*) AS c FROM moments WHERE username = ?", (me,)).fetchone()['c']
        if moc >= 1: unlock('ach_first_moment')
        try:
            pc = db.execute("SELECT pet_type FROM users WHERE username = ?", (me,)).fetchone()
            if pc and pc['pet_type']: unlock('ach_pet_owner')
        except Exception:
            pass
        db.commit()
        return jsonify({'ok': True, 'new': newly})

    @app.route('/api/messages/search_by_date')
    def api_search_by_date():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        room = (request.args.get('room') or '').strip()
        date_str = (request.args.get('date') or '').strip()
        if not room or not date_str:
            return jsonify({'ok': False, 'error': '参数不完整'}), 400
        try:
            start = time.mktime(time.strptime(date_str, '%Y-%m-%d'))
        except Exception:
            return jsonify({'ok': False, 'error': '日期格式错误'}), 400
        end = start + 86400
        db = get_db()
        rows = db.execute(
            "SELECT id, sender, content, created_at FROM messages WHERE room = ? AND created_at >= ? AND created_at < ? ORDER BY id ASC LIMIT 500",
            (room, start, end)
        ).fetchall()
        result = []
        for r in rows:
            if (r['content'] or '').startswith('{'): continue
            result.append(dict(r))
        return jsonify({'ok': True, 'messages': result, 'count': len(result)})

    print("[new_features9] 第2批 路由 已注册")
