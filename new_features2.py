# -*- coding: utf-8 -*-
"""游戏排行 + 反馈"""
import time
import json as _json
from flask import request, jsonify


def register_routes(app, deps):
    get_db = deps['get_db']
    require_auth = deps['require_auth']
    touch_user = deps['touch_user']
    clean_text = deps['clean_text']

    # ===== 建表（用 app_context，避免 Working outside context） =====
    with app.app_context():
        db = get_db()
        db.executescript('''
            CREATE TABLE IF NOT EXISTS game_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                username TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                extra TEXT,
                created_at REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_game_scores_rank ON game_scores(game_id, score DESC);
            CREATE INDEX IF NOT EXISTS idx_game_scores_user ON game_scores(username, game_id);
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'other',
                content TEXT NOT NULL,
                contact TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                admin_reply TEXT,
                created_at REAL NOT NULL,
                handled_at REAL
            );
            CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(username, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status, created_at DESC);
        ''')
        db.commit()

    # ===== 1. 提交游戏得分 =====
    @app.route('/api/game/score/submit', methods=['POST'])
    def api_game_score_submit():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        game_id = (data.get('game_id') or '').strip()[:32]
        score = data.get('score')
        extra = (data.get('extra') or '').strip()[:200]
        if not game_id:
            return jsonify({'ok': False, 'error': '缺少 game_id'}), 400
        try:
            score = int(score)
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': '分数无效'}), 400
        if score < 0 or score > 99999999:
            return jsonify({'ok': False, 'error': '分数超范围'}), 400
        db = get_db()
        touch_user(db, me)
        row = db.execute(
            "SELECT id, score FROM game_scores WHERE game_id = ? AND username = ? ORDER BY score DESC LIMIT 1",
            (game_id, me)
        ).fetchone()
        if row and row['score'] >= score:
            db.commit()
            return jsonify({'ok': True, 'best': row['score'], 'new_record': False})
        if row:
            db.execute("UPDATE game_scores SET score = ?, extra = ?, created_at = ? WHERE id = ?",
                       (score, extra, time.time(), row['id']))
        else:
            db.execute(
                "INSERT INTO game_scores (game_id, username, score, extra, created_at) VALUES (?, ?, ?, ?, ?)",
                (game_id, me, score, extra, time.time())
            )
        db.commit()
        return jsonify({'ok': True, 'best': score, 'new_record': True})

    # ===== 2. 游戏排行榜 =====
    @app.route('/api/game/score/rank')
    def api_game_score_rank():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        game_id = (request.args.get('game_id') or '').strip()[:32]
        if not game_id:
            return jsonify({'ok': False, 'error': '缺少 game_id'}), 400
        try:
            limit = int(request.args.get('limit', 20))
        except ValueError:
            limit = 20
        limit = max(1, min(100, limit))
        db = get_db()
        rows = db.execute(
            "SELECT username, score, extra, created_at FROM game_scores "
            "WHERE game_id = ? ORDER BY score DESC, created_at ASC LIMIT ?",
            (game_id, limit)
        ).fetchall()
        result = []
        for i, r in enumerate(rows, 1):
            result.append({'rank': i, 'username': r['username'], 'score': r['score'],
                           'extra': r['extra'] or '', 'created_at': r['created_at']})
        my_row = db.execute(
            "SELECT score FROM game_scores WHERE game_id = ? AND username = ? ORDER BY score DESC LIMIT 1",
            (game_id, me)
        ).fetchone()
        my_rank = None
        if my_row:
            cnt = db.execute(
                "SELECT COUNT(*) AS c FROM game_scores WHERE game_id = ? AND score > ?",
                (game_id, my_row['score'])
            ).fetchone()['c']
            my_rank = cnt + 1
        return jsonify({'ok': True, 'game_id': game_id, 'list': result,
                        'my_rank': my_rank, 'my_score': my_row['score'] if my_row else 0})

    # ===== 3. 我的游戏成绩 =====
    @app.route('/api/game/score/mine')
    def api_game_score_mine():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        rows = db.execute(
            "SELECT game_id, MAX(score) AS best, COUNT(*) AS plays FROM game_scores "
            "WHERE username = ? GROUP BY game_id ORDER BY best DESC",
            (me,)
        ).fetchall()
        return jsonify({'ok': True, 'scores': [dict(r) for r in rows]})

    # ===== 4. 提交反馈 =====
    @app.route('/api/feedback/submit', methods=['POST'])
    def api_feedback_submit():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        data = request.get_json() or {}
        category = (data.get('category') or 'other').strip()[:20]
        if category not in ('bug', 'feature', 'experience', 'other'):
            category = 'other'
        content = (data.get('content') or '').strip()[:2000]
        contact = (data.get('contact') or '').strip()[:100]
        if not content:
            return jsonify({'ok': False, 'error': '反馈内容不能为空'}), 400
        try:
            content, _ = clean_text(content)
        except Exception:
            pass
        if not content:
            return jsonify({'ok': False, 'error': '内容包含违规词'}), 400
        db = get_db()
        touch_user(db, me)
        cutoff = time.time() - 3600
        cnt = db.execute(
            "SELECT COUNT(*) AS c FROM feedback WHERE username = ? AND created_at > ?",
            (me, cutoff)
        ).fetchone()['c']
        if cnt >= 5:
            return jsonify({'ok': False, 'error': '提交太频繁（每小时最多 5 条）'}), 429
        cur = db.execute(
            "INSERT INTO feedback (username, category, content, contact, status, created_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?)",
            (me, category, content, contact, time.time())
        )
        db.commit()
        return jsonify({'ok': True, 'id': cur.lastrowid, 'message': '反馈已提交，感谢你的建议！'})

    # ===== 5. 我的反馈 =====
    @app.route('/api/feedback/mine')
    def api_feedback_mine():
        me = require_auth()
        if not me:
            return jsonify({'ok': False, 'error': '请先登录'}), 401
        db = get_db()
        rows = db.execute(
            "SELECT id, category, content, contact, status, admin_reply, created_at, handled_at "
            "FROM feedback WHERE username = ? ORDER BY created_at DESC LIMIT 50",
            (me,)
        ).fetchall()
        return jsonify({'ok': True, 'items': [dict(r) for r in rows]})

    # ===== 6. 管理员：反馈列表 =====
    @app.route('/api/admin/feedback/list')
    def api_admin_feedback_list():
        try:
            import app as _app
            require_admin = _app.require_admin
        except Exception:
            return jsonify({'ok': False, 'error': '管理员模块未加载'}), 500
        if not require_admin():
            return jsonify({'ok': False, 'error': '未登录'}), 401
        show_all = request.args.get('all') == '1'
        db = get_db()
        if show_all:
            rows = db.execute(
                "SELECT id, username, category, content, contact, status, admin_reply, created_at, handled_at "
                "FROM feedback ORDER BY id DESC LIMIT 200"
            ).fetchall()
        else:
            rows = db.execute(
                "SELECT id, username, category, content, contact, status, admin_reply, created_at, handled_at "
                "FROM feedback WHERE status = 'pending' ORDER BY id DESC LIMIT 200"
            ).fetchall()
        return jsonify({'ok': True, 'items': [dict(r) for r in rows]})

    # ===== 7. 管理员：处理反馈 =====
    @app.route('/api/admin/feedback/handle', methods=['POST'])
    def api_admin_feedback_handle():
        try:
            import app as _app
            require_admin = _app.require_admin
        except Exception:
            return jsonify({'ok': False, 'error': '管理员模块未加载'}), 500
        if not require_admin():
            return jsonify({'ok': False, 'error': '未登录'}), 401
        data = request.get_json() or {}
        try:
            fid = int(data.get('id'))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': '参数错误'}), 400
        action = (data.get('action') or 'reply').strip()
        reply = (data.get('reply') or '').strip()[:500]
        db = get_db()
        if action == 'reply':
            db.execute(
                "UPDATE feedback SET status = 'replied', admin_reply = ?, handled_at = ? WHERE id = ?",
                (reply, time.time(), fid)
            )
        elif action == 'close':
            db.execute(
                "UPDATE feedback SET status = 'closed', handled_at = ? WHERE id = ?",
                (time.time(), fid)
            )
        elif action == 'delete':
            db.execute("DELETE FROM feedback WHERE id = ?", (fid,))
        else:
            return jsonify({'ok': False, 'error': '未知操作'}), 400
        db.commit()
        return jsonify({'ok': True})

    print("[new_features2] 游戏排行 + 反馈 路由已注册")
