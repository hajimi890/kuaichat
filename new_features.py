# -*- coding: utf-8 -*-
import time, json as _json, io, base64, re
from flask import request, jsonify

def register_routes(app, deps):
    """由 app.py 末尾调用，deps 是依赖字典"""
    get_db = deps['get_db']
    require_auth = deps['require_auth']
    are_friends = deps['are_friends']
    is_group_member = deps['is_group_member']
    make_room = deps['make_room']
    group_room = deps['group_room']
    parse_room = deps['parse_room']
    clean_text = deps['clean_text']
    add_points = deps['add_points']
    touch_user = deps['touch_user']
    ONLINE_WINDOW = deps['ONLINE_WINDOW']

    @app.route("/api/qrcode/me")
    def api_qrcode_me():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        text = "kuaichat://add?id=" + str(me)
        try:
            import qrcode
            img = qrcode.make(text); buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            return jsonify({"ok": True, "data_url": "data:image/png;base64," + b64, "text": text})
        except Exception:
            return jsonify({"ok": True, "data_url": "", "text": text})

    @app.route("/api/qrcode/parse", methods=["POST"])
    def api_qrcode_parse():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()
        m = re.match(r"^kuaichat://add\?id=(.+)$", text)
        if not m: return jsonify({"ok": False, "error": "不是有效的快聊二维码"}), 400
        target = m.group(1).strip()
        if target == me: return jsonify({"ok": False, "error": "不能添加自己"}), 400
        db = get_db()
        if not db.execute("SELECT 1 FROM users WHERE username = ?", (target,)).fetchone():
            return jsonify({"ok": False, "error": "用户不存在"}), 404
        if are_friends(db, me, target):
            return jsonify({"ok": True, "already": True, "peer": target})
        return jsonify({"ok": True, "already": False, "peer": target})

    @app.route("/api/user/profile_by_name")
    def api_profile_by_name():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        name = (request.args.get("username") or "").strip()
        if not name: return jsonify({"ok": False, "error": "缺少参数"}), 400
        db = get_db()
        u = db.execute("SELECT username, avatar, bio, level_frame, last_seen FROM users WHERE username = ?", (name,)).fetchone()
        if not u: return jsonify({"ok": False, "error": "用户不存在"}), 404
        cutoff = time.time() - ONLINE_WINDOW
        return jsonify({"ok": True, "user": {
            "username": u["username"], "avatar": u["avatar"] or "",
            "bio": u["bio"] or "", "frame": u["level_frame"] or "default",
            "online": (u["last_seen"] or 0) > cutoff,
            "is_friend": are_friends(db, me, name) if me != name else True,
        }})

    @app.route("/api/mentions/unread")
    def api_mentions_unread():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        db = get_db()
        rows = db.execute("SELECT id, message_id, room, mentioned_by, created_at FROM mentions WHERE mentioned_user = ? AND is_read = 0 ORDER BY id DESC LIMIT 50", (me,)).fetchall()
        return jsonify({"ok": True, "mentions": [dict(r) for r in rows]})

    @app.route("/api/mentions/read", methods=["POST"])
    def api_mentions_read():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        data = request.get_json() or {}
        ids = data.get("ids") or []
        db = get_db()
        if ids:
            for mid in ids:
                try: db.execute("UPDATE mentions SET is_read = 1 WHERE id = ? AND mentioned_user = ?", (int(mid), me))
                except (TypeError, ValueError): pass
        else:
            db.execute("UPDATE mentions SET is_read = 1 WHERE mentioned_user = ?", (me,))
        db.commit()
        return jsonify({"ok": True})

    @app.route("/api/messages/forward", methods=["POST"])
    def api_messages_forward():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        data = request.get_json() or {}
        mid = data.get("message_id")
        target_type = (data.get("target_type") or "").strip()
        target_id = (data.get("target_id") or "").strip()
        if not mid or not target_type or not target_id:
            return jsonify({"ok": False, "error": "参数不完整"}), 400
        db = get_db()
        try: mid = int(mid)
        except (TypeError, ValueError): return jsonify({"ok": False, "error": "消息 ID 无效"}), 400
        src = db.execute("SELECT content FROM messages WHERE id = ?", (mid,)).fetchone()
        if not src: return jsonify({"ok": False, "error": "消息不存在"}), 404
        if target_type == "user":
            if not are_friends(db, me, target_id): return jsonify({"ok": False, "error": "对方不是你的好友"}), 403
            room = make_room(me, target_id)
        elif target_type == "group":
            try: gid = int(target_id)
            except (TypeError, ValueError): return jsonify({"ok": False, "error": "群 ID 无效"}), 400
            if not is_group_member(db, gid, me): return jsonify({"ok": False, "error": "你不在该群"}), 403
            room = group_room(gid)
        else:
            return jsonify({"ok": False, "error": "目标类型无效"}), 400
        cur = db.execute("INSERT INTO messages (room, sender, content, created_at) VALUES (?, ?, ?, ?)", (room, me, src["content"], time.time()))
        db.commit()
        return jsonify({"ok": True, "id": cur.lastrowid, "room": room})

    @app.route("/api/friends/online")
    def api_friends_online():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        names = request.args.get("names", "").strip()
        if not names: return jsonify({"ok": True, "online": {}})
        name_list = [n.strip() for n in names.split(",") if n.strip()][:200]
        cutoff = time.time() - ONLINE_WINDOW
        db = get_db(); result = {}
        if name_list:
            qs = ",".join("?" * len(name_list))
            rows = db.execute("SELECT username, last_seen FROM users WHERE username IN (" + qs + ")", name_list).fetchall()
            for r in rows:
                result[r["username"]] = (r["last_seen"] or 0) > cutoff
        return jsonify({"ok": True, "online": result})

    @app.route("/api/draft", methods=["GET", "POST"])
    def api_draft():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        db = get_db()
        db.execute("CREATE TABLE IF NOT EXISTS drafts (owner TEXT NOT NULL, room TEXT NOT NULL, content TEXT, updated_at REAL NOT NULL, PRIMARY KEY (owner, room))")
        db.commit()
        if request.method == "POST":
            data = request.get_json() or {}
            room = (data.get("room") or "").strip()
            content = (data.get("content") or "")[:2000]
            if not room: return jsonify({"ok": False, "error": "缺少房间"}), 400
            if not content:
                db.execute("DELETE FROM drafts WHERE owner = ? AND room = ?", (me, room))
            else:
                db.execute("INSERT OR REPLACE INTO drafts (owner, room, content, updated_at) VALUES (?, ?, ?, ?)", (me, room, content, time.time()))
            db.commit()
            return jsonify({"ok": True})
        room = (request.args.get("room") or "").strip()
        if room:
            row = db.execute("SELECT content FROM drafts WHERE owner = ? AND room = ?", (me, room)).fetchone()
            return jsonify({"ok": True, "content": row["content"] if row else ""})
        rows = db.execute("SELECT room, content, updated_at FROM drafts WHERE owner = ? ORDER BY updated_at DESC LIMIT 50", (me,)).fetchall()
        return jsonify({"ok": True, "drafts": [dict(r) for r in rows]})

    @app.route("/api/favorites", methods=["GET", "POST"])
    def api_favorites():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        db = get_db()
        db.execute("CREATE TABLE IF NOT EXISTS favorites (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, message_id INTEGER, room TEXT, content TEXT, created_at REAL NOT NULL)")
        db.commit()
        if request.method == "POST":
            data = request.get_json() or {}
            mid = data.get("message_id")
            room = (data.get("room") or "").strip()
            content = (data.get("content") or "")
            if mid:
                try:
                    mid = int(mid)
                    row = db.execute("SELECT content, room FROM messages WHERE id = ?", (mid,)).fetchone()
                    if row: content = row["content"]; room = row["room"]
                except (TypeError, ValueError): pass
            if not content: return jsonify({"ok": False, "error": "内容为空"}), 400
            cur = db.execute("INSERT INTO favorites (owner, message_id, room, content, created_at) VALUES (?, ?, ?, ?, ?)", (me, mid, room, content[:5000], time.time()))
            db.commit()
            return jsonify({"ok": True, "id": cur.lastrowid})
        rows = db.execute("SELECT id, message_id, room, content, created_at FROM favorites WHERE owner = ? ORDER BY id DESC LIMIT 200", (me,)).fetchall()
        return jsonify({"ok": True, "favorites": [dict(r) for r in rows]})

    @app.route("/api/favorites/delete", methods=["POST"])
    def api_favorites_delete():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        data = request.get_json() or {}
        try: fid = int(data.get("id"))
        except (TypeError, ValueError): return jsonify({"ok": False, "error": "参数错误"}), 400
        db = get_db()
        db.execute("DELETE FROM favorites WHERE id = ? AND owner = ?", (fid, me))
        db.commit()
        return jsonify({"ok": True})

    @app.route("/api/pinned_messages", methods=["GET", "POST"])
    def api_pinned_messages():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        db = get_db()
        db.execute("CREATE TABLE IF NOT EXISTS pinned_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT NOT NULL, message_id INTEGER NOT NULL, content TEXT, pinned_by TEXT NOT NULL, created_at REAL NOT NULL)")
        db.commit()
        if request.method == "POST":
            data = request.get_json() or {}
            room = (data.get("room") or "").strip()
            mid = data.get("message_id")
            action = (data.get("action") or "pin").strip()
            try: mid = int(mid)
            except (TypeError, ValueError): return jsonify({"ok": False, "error": "参数错误"}), 400
            if action == "unpin":
                db.execute("DELETE FROM pinned_messages WHERE room = ? AND message_id = ?", (room, mid))
                db.commit()
                return jsonify({"ok": True})
            row = db.execute("SELECT content FROM messages WHERE id = ?", (mid,)).fetchone()
            if not row: return jsonify({"ok": False, "error": "消息不存在"}), 404
            cur = db.execute("INSERT INTO pinned_messages (room, message_id, content, pinned_by, created_at) VALUES (?, ?, ?, ?, ?)", (room, mid, row["content"][:500], me, time.time()))
            db.commit()
            return jsonify({"ok": True, "id": cur.lastrowid})
        room = (request.args.get("room") or "").strip()
        if not room: return jsonify({"ok": True, "pinned": []})
        rows = db.execute("SELECT id, message_id, content, pinned_by, created_at FROM pinned_messages WHERE room = ? ORDER BY id DESC LIMIT 50", (room,)).fetchall()
        return jsonify({"ok": True, "pinned": [dict(r) for r in rows]})

    @app.route("/api/moment/likes")
    def api_moment_likes():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        try: mid = int(request.args.get("moment_id", 0))
        except ValueError: return jsonify({"ok": False, "error": "参数错误"}), 400
        db = get_db()
        row = db.execute("SELECT likes FROM moments WHERE id = ?", (mid,)).fetchone()
        if not row: return jsonify({"ok": False, "error": "动态不存在"}), 404
        names = [x for x in (row["likes"] or "").split(",") if x]
        result = []
        for n in names:
            u = db.execute("SELECT avatar, level_frame FROM users WHERE username = ?", (n,)).fetchone()
            result.append({"username": n, "avatar": u["avatar"] if u else "", "frame": (u["level_frame"] if u else "default") or "default"})
        return jsonify({"ok": True, "likes": result})

    @app.route("/api/moment/comment/reply", methods=["POST"])
    def api_moment_comment_reply():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        data = request.get_json() or {}
        try: mid = int(data.get("moment_id"))
        except (TypeError, ValueError): return jsonify({"ok": False, "error": "参数错误"}), 400
        parent_id = data.get("parent_id")
        try: parent_id = int(parent_id) if parent_id else None
        except (TypeError, ValueError): parent_id = None
        content = (data.get("content") or "").strip()[:200]
        if not content: return jsonify({"ok": False, "error": "评论不能为空"}), 400
        content, _ = clean_text(content)
        db = get_db()
        cols = [c[1] for c in db.execute("PRAGMA table_info(moment_comments)").fetchall()]
        if "parent_id" not in cols:
            db.execute("ALTER TABLE moment_comments ADD COLUMN parent_id INTEGER")
            db.commit()
        cur = db.execute("INSERT INTO moment_comments (moment_id, username, content, created_at, parent_id) VALUES (?, ?, ?, ?, ?)", (mid, me, content, time.time(), parent_id))
        db.commit()
        return jsonify({"ok": True, "id": cur.lastrowid})

    @app.route("/api/moment/visibility", methods=["GET", "POST"])
    def api_moment_visibility():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        db = get_db()
        db.execute("CREATE TABLE IF NOT EXISTS moment_visibility (owner TEXT NOT NULL, mode TEXT NOT NULL, payload TEXT, updated_at REAL NOT NULL, PRIMARY KEY (owner))")
        db.commit()
        if request.method == "POST":
            data = request.get_json() or {}
            mode = (data.get("mode") or "all").strip()
            if mode not in ("all", "friends", "whitelist", "blacklist"):
                return jsonify({"ok": False, "error": "模式无效"}), 400
            payload = _json.dumps(data.get("list") or [], ensure_ascii=False)
            db.execute("INSERT OR REPLACE INTO moment_visibility (owner, mode, payload, updated_at) VALUES (?, ?, ?, ?)", (me, mode, payload, time.time()))
            db.commit()
            return jsonify({"ok": True})
        row = db.execute("SELECT mode, payload FROM moment_visibility WHERE owner = ?", (me,)).fetchone()
        if not row: return jsonify({"ok": True, "mode": "all", "list": []})
        try: lst = _json.loads(row["payload"] or "[]")
        except Exception: lst = []
        return jsonify({"ok": True, "mode": row["mode"], "list": lst})

    @app.route("/api/group/vote/create", methods=["POST"])
    def api_group_vote_create():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        data = request.get_json() or {}
        try: gid = int(data.get("group_id"))
        except (TypeError, ValueError): return jsonify({"ok": False, "error": "群 ID 无效"}), 400
        title = (data.get("title") or "").strip()[:100]
        options = data.get("options") or []
        if not title or not isinstance(options, list) or len(options) < 2:
            return jsonify({"ok": False, "error": "投票需要标题和至少 2 个选项"}), 400
        options = [str(o).strip()[:60] for o in options if str(o).strip()][:10]
        if len(options) < 2: return jsonify({"ok": False, "error": "选项不足"}), 400
        db = get_db()
        if not is_group_member(db, gid, me): return jsonify({"ok": False, "error": "你不在该群"}), 403
        db.execute("CREATE TABLE IF NOT EXISTS group_votes (id INTEGER PRIMARY KEY AUTOINCREMENT, group_id INTEGER NOT NULL, title TEXT NOT NULL, options TEXT NOT NULL, creator TEXT NOT NULL, created_at REAL NOT NULL, closed INTEGER DEFAULT 0)")
        db.execute("CREATE TABLE IF NOT EXISTS group_vote_records (id INTEGER PRIMARY KEY AUTOINCREMENT, vote_id INTEGER NOT NULL, username TEXT NOT NULL, option_index INTEGER NOT NULL, created_at REAL NOT NULL, UNIQUE(vote_id, username))")
        db.commit()
        cur = db.execute("INSERT INTO group_votes (group_id, title, options, creator, created_at) VALUES (?, ?, ?, ?, ?)", (gid, title, _json.dumps(options, ensure_ascii=False), me, time.time()))
        vote_id = cur.lastrowid
        payload = {"type": "vote", "vote_id": vote_id, "title": title, "options": options, "creator": me}
        content = _json.dumps(payload, ensure_ascii=False)
        db.execute("INSERT INTO messages (room, sender, content, created_at) VALUES (?, ?, ?, ?)", (group_room(gid), me, content, time.time()))
        db.commit()
        return jsonify({"ok": True, "vote_id": vote_id})

    @app.route("/api/group/vote/info")
    def api_group_vote_info():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        try: vid = int(request.args.get("vote_id", 0))
        except ValueError: return jsonify({"ok": False, "error": "参数错误"}), 400
        db = get_db()
        row = db.execute("SELECT * FROM group_votes WHERE id = ?", (vid,)).fetchone()
        if not row: return jsonify({"ok": False, "error": "投票不存在"}), 404
        try: options = _json.loads(row["options"])
        except Exception: options = []
        recs = db.execute("SELECT username, option_index FROM group_vote_records WHERE vote_id = ?", (vid,)).fetchall()
        counts = [0] * len(options); my_vote = None; voters = [[] for _ in options]
        for r in recs:
            idx = r["option_index"]
            if 0 <= idx < len(counts):
                counts[idx] += 1; voters[idx].append(r["username"])
            if r["username"] == me: my_vote = idx
        return jsonify({"ok": True, "vote": {
            "id": row["id"], "title": row["title"], "options": options,
            "creator": row["creator"], "closed": bool(row["closed"]),
            "counts": counts, "my_vote": my_vote, "voters": voters, "total": len(recs)
        }})

    @app.route("/api/group/vote/cast", methods=["POST"])
    def api_group_vote_cast():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        data = request.get_json() or {}
        try:
            vid = int(data.get("vote_id")); idx = int(data.get("option_index"))
        except (TypeError, ValueError): return jsonify({"ok": False, "error": "参数错误"}), 400
        db = get_db()
        row = db.execute("SELECT group_id, closed, options FROM group_votes WHERE id = ?", (vid,)).fetchone()
        if not row: return jsonify({"ok": False, "error": "投票不存在"}), 404
        if row["closed"]: return jsonify({"ok": False, "error": "投票已结束"}), 400
        if not is_group_member(db, row["group_id"], me): return jsonify({"ok": False, "error": "你不在该群"}), 403
        try: options = _json.loads(row["options"])
        except Exception: options = []
        if idx < 0 or idx >= len(options): return jsonify({"ok": False, "error": "选项无效"}), 400
        exist = db.execute("SELECT option_index FROM group_vote_records WHERE vote_id = ? AND username = ?", (vid, me)).fetchone()
        if exist:
            db.execute("UPDATE group_vote_records SET option_index = ? WHERE vote_id = ? AND username = ?", (idx, vid, me))
        else:
            db.execute("INSERT INTO group_vote_records (vote_id, username, option_index, created_at) VALUES (?, ?, ?, ?)", (vid, me, idx, time.time()))
        db.commit()
        return jsonify({"ok": True})

    @app.route("/api/location/share", methods=["POST"])
    def api_location_share():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        data = request.get_json() or {}
        room = (data.get("room") or "").strip()
        lat = data.get("lat"); lng = data.get("lng")
        text = (data.get("text") or "我在这里").strip()[:50]
        if not room or lat is None or lng is None:
            return jsonify({"ok": False, "error": "参数不完整"}), 400
        try: lat = float(lat); lng = float(lng)
        except (TypeError, ValueError): return jsonify({"ok": False, "error": "坐标错误"}), 400
        typ, data2 = parse_room(room)
        if typ is None: return jsonify({"ok": False, "error": "无效房间"}), 400
        db = get_db()
        payload = {"type": "location", "lat": lat, "lng": lng, "text": text, "sender": me}
        content = _json.dumps(payload, ensure_ascii=False)
        cur = db.execute("INSERT INTO messages (room, sender, content, created_at) VALUES (?, ?, ?, ?)", (room, me, content, time.time()))
        db.commit()
        return jsonify({"ok": True, "id": cur.lastrowid})


    @app.route("/api/group/files")
    def api_group_files():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        try: gid = int(request.args.get("group_id", 0))
        except ValueError: return jsonify({"ok": False, "error": "参数错误"}), 400
        db = get_db()
        if not is_group_member(db, gid, me): return jsonify({"ok": False, "error": "你不在该群"}), 403
        rows = db.execute("SELECT id, sender, content, created_at FROM messages WHERE room = ? AND content LIKE ? ORDER BY id DESC LIMIT 200", (group_room(gid), "%\"type\":\"file\"%")).fetchall()
        files = []
        for r in rows:
            try:
                o = _json.loads(r["content"])
                files.append({"id": r["id"], "sender": r["sender"], "url": o.get("url",""), "name": o.get("name","文件"), "size": o.get("size",0), "created_at": r["created_at"]})
            except Exception:
                continue
        return jsonify({"ok": True, "files": files})


    @app.route("/api/voice/transcribe", methods=["POST"])
    def api_voice_transcribe():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        return jsonify({"ok": True, "text": "(语音转文字：服务器未配置识别引擎)", "engine": "none"})


    @app.route("/api/room/unread_anchor")
    def api_room_unread_anchor():
        me = require_auth()
        if not me: return jsonify({"ok": False, "error": "请先登录"}), 401
        room = (request.args.get("room") or "").strip()
        if not room: return jsonify({"ok": False, "error": "缺少房间"}), 400
        typ, data2 = parse_room(room)
        db = get_db()
        if typ == "private":
            if me not in data2: return jsonify({"ok": False, "error": "无效房间"}), 400
            other = data2[0] if data2[1] == me else data2[1]
            if not are_friends(db, me, other): return jsonify({"ok": False, "error": "不是好友"}), 403
            row = db.execute("SELECT id FROM messages WHERE room = ? AND sender != ? AND (read_by IS NULL OR read_by = '') ORDER BY id ASC LIMIT 1", (room, me)).fetchone()
        else:
            row = db.execute("SELECT id FROM messages WHERE room = ? ORDER BY id DESC LIMIT 1", (room,)).fetchone()
        first_unread = row["id"] if row else 0
        return jsonify({"ok": True, "first_unread_id": first_unread})


    print('[new_features] 全部 16 个功能已注册（已补齐）')
