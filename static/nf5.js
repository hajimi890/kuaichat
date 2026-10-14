(function () {
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s || '').replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function authFetch(url, opts) {
    opts = opts || {};
    var h = opts.headers || {};
    var t = localStorage.getItem('kuaichat_token') || '';
    if (t) h['Authorization'] = 'Bearer ' + t;
    if (opts.body && typeof opts.body === 'string' && !h['Content-Type']) h['Content-Type'] = 'application/json';
    opts.headers = h;
    return fetch(url, opts);
  }
  function toast(m, e) { if (window.showToast) return window.showToast(m, e); alert(m); }
  function modal(title, html, onOK, okText) {
    var t = $('modalTitle'), m = $('modalMessage'), inp = $('modalInput');
    var bc = $('modalConfirm'), bx = $('modalCancel'), mi = $('modalIcon');
    if (!t) { alert(title); return; }
    t.textContent = title; m.innerHTML = html; m.style.display = 'block';
    if (inp) inp.classList.add('hidden');
    if (mi) { mi.className = 'modal-icon'; mi.innerHTML = '<i class="fas fa-star"></i>'; }
    bc.className = 'modal-btn confirm'; bc.textContent = okText || '确定'; bc.style.display = 'block';
    bx.textContent = '关闭'; bx.style.display = 'block';
    bc.onclick = function () { if (onOK) onOK(); else $('modalOverlay').classList.add('hidden'); };
    bx.onclick = function () { $('modalOverlay').classList.add('hidden'); };
    $('modalOverlay').classList.remove('hidden');
  }
  var NAMES = { '2048': '2048', 'snake': '贪吃蛇', 'memory': '翻牌记忆', 'rps': '石头剪刀布', 'gomoku': '五子棋' };

  window.openGameRank = function (gid, gname) {
    authFetch('/api/game/score/rank?game_id=' + encodeURIComponent(gid) + '&limit=20')
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) return toast(d.error, true);
        var html = '<div style="text-align:center;margin-bottom:12px;">' +
          '<div style="font-size:15px;font-weight:700;color:#0d3d6b;">🏆 ' + esc(gname || gid) + '</div>' +
          '<div style="font-size:12px;color:#90a4ae;margin-top:4px;">我的最高：<b style="color:#42a5f5;">' + d.my_score + '</b>' +
          (d.my_rank ? ' · 第 ' + d.my_rank + ' 名' : ' · 暂无') + '</div></div><div style="max-height:400px;overflow-y:auto;">';
        if (!d.list.length) html += '<div style="text-align:center;color:#90a4ae;padding:30px;">还没人玩过，快来抢第一！</div>';
        else d.list.forEach(function (it) {
          var medal = it.rank === 1 ? '🥇' : it.rank === 2 ? '🥈' : it.rank === 3 ? '🥉' : ' ' + it.rank + '.';
          var isMe = it.username === (localStorage.getItem('kuaichat_username') || '');
          html += '<div style="display:flex;align-items:center;gap:10px;padding:10px;border-bottom:1px solid #f0f7fe;' + (isMe ? 'background:#e3f2fd;border-radius:8px;' : '') + '">' +
            '<div style="font-size:16px;font-weight:700;color:#ff9800;min-width:36px;">' + medal + '</div>' +
            '<div style="flex:1;font-size:14px;color:#0d3d6b;font-weight:600;">' + esc(it.username) + (isMe ? ' (我)' : '') + '</div>' +
            '<div style="font-size:15px;font-weight:700;color:#42a5f5;">' + it.score + '</div></div>';
        });
        html += '</div>';
        modal('排行榜', html, null, '关闭');
      }).catch(function () { toast('网络错误', true); });
  };

  window.openMyScores = function () {
    authFetch('/api/game/score/mine').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      var html = '<div style="max-height:400px;overflow-y:auto;">';
      if (!d.scores.length) html += '<div style="text-align:center;color:#90a4ae;padding:30px;">还没玩过游戏</div>';
      else d.scores.forEach(function (s) {
        html += '<div style="display:flex;align-items:center;gap:10px;padding:12px;border-bottom:1px solid #f0f7fe;">' +
          '<div style="flex:1;"><div style="font-size:14px;font-weight:600;color:#0d3d6b;">' + esc(NAMES[s.game_id] || s.game_id) + '</div>' +
          '<div style="font-size:11px;color:#90a4ae;margin-top:2px;">玩了 ' + s.plays + ' 次</div></div>' +
          '<div style="font-size:17px;font-weight:700;color:#ff9800;">' + s.best + '</div>' +
          '<button class="view-rank-btn" data-gid="' + esc(s.game_id) + '" data-gname="' + esc(NAMES[s.game_id] || s.game_id) + '" style="background:#e3f2fd;color:#1976d2;border:none;border-radius:8px;padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;">排行榜</button></div>';
      });
      html += '</div>';
      modal('我的游戏成绩', html, null, '关闭');
      setTimeout(function () {
        document.querySelectorAll('.view-rank-btn').forEach(function (b) {
          b.onclick = function () { window.openGameRank(b.dataset.gid, b.dataset.gname); };
        });
      }, 100);
    });
  };

  window.submitGameScore = function (gid, score, extra) {
    return authFetch('/api/game/score/submit', {
      method: 'POST', body: JSON.stringify({ game_id: gid, score: score, extra: extra || '' })
    }).then(function (r) { return r.json(); }).then(function (d) {
      if (d.ok && d.new_record) toast('🎉 新纪录：' + d.best + ' 分！');
      return d;
    }).catch(function () { return { ok: false }; });
  };

  window.openFeedback = function () {
    authFetch('/api/feedback/mine').then(function (r) { return r.json(); }).then(function (d) {
      var items = d.ok ? d.items : [];
      var html = '<div style="font-size:13px;color:#546e7a;margin-bottom:8px;">反馈类型：</div>' +
        '<select id="fbCategory" class="modal-input" style="width:100%;box-sizing:border-box;margin-top:0;">' +
        '<option value="bug">🐛 Bug 反馈</option>' +
        '<option value="feature">✨ 功能建议</option>' +
        '<option value="experience">💡 体验优化</option>' +
        '<option value="other" selected>💬 其他</option></select>' +
        '<div style="font-size:13px;color:#546e7a;margin:12px 0 8px;">详细内容：</div>' +
        '<textarea id="fbContent" placeholder="请描述..." maxlength="2000" style="width:100%;min-height:100px;background:#f5faff;border:1.5px solid #d4e4f7;border-radius:12px;padding:10px;font-family:inherit;font-size:14px;box-sizing:border-box;"></textarea>' +
        '<div style="font-size:13px;color:#546e7a;margin:12px 0 8px;">联系方式（选填）：</div>' +
        '<input id="fbContact" class="modal-input" placeholder="邮箱/QQ/微信" style="width:100%;box-sizing:border-box;margin-top:0;">';
      if (items.length) {
        html += '<div style="font-size:13px;color:#546e7a;margin:16px 0 8px;">我的反馈历史：</div><div style="max-height:220px;overflow-y:auto;border:1px solid #f0f7fe;border-radius:12px;">';
        items.slice(0, 20).forEach(function (it) {
          var st = it.status === 'pending' ? '待处理' : it.status === 'replied' ? '已回复' : it.status === 'closed' ? '已关闭' : it.status;
          var sc = it.status === 'pending' ? '#ff9800' : it.status === 'replied' ? '#1bbf8b' : '#90a4ae';
          var cn = { bug: '🐛 Bug', feature: '✨ 建议', experience: '💡 体验', other: '💬 其他' };
          html += '<div style="padding:10px;border-bottom:1px solid #f0f7fe;">' +
            '<div style="display:flex;justify-content:space-between;font-size:12px;">' +
            '<span style="color:#1976d2;font-weight:600;">' + (cn[it.category] || it.category) + '</span>' +
            '<span style="color:' + sc + ';">' + st + '</span></div>' +
            '<div style="font-size:13px;color:#0d3d6b;margin-top:6px;word-break:break-word;">' + esc(it.content).slice(0, 100) + '</div>' +
            (it.admin_reply ? '<div style="font-size:12px;color:#1bbf8b;margin-top:6px;padding:8px;background:#e8f5e9;border-radius:8px;">管理员回复：' + esc(it.admin_reply) + '</div>' : '') +
            '<div style="font-size:11px;color:#90a4ae;margin-top:4px;">' + new Date(it.created_at * 1000).toLocaleString() + '</div></div>';
        });
        html += '</div>';
      }
      modal('意见反馈', html, function () {
        var cat = ($('fbCategory') && $('fbCategory').value) || 'other';
        var c = ($('fbContent') && $('fbContent').value || '').trim();
        var ct = ($('fbContact') && $('fbContact').value || '').trim();
        if (!c) return toast('请填写内容', true);
        if (c.length < 3) return toast('太短了', true);
        authFetch('/api/feedback/submit', {
          method: 'POST', body: JSON.stringify({ category: cat, content: c, contact: ct })
        }).then(function (r) { return r.json(); }).then(function (d2) {
          if (!d2.ok) throw new Error(d2.error || '失败');
          toast('✅ 反馈已提交'); $('modalOverlay').classList.add('hidden');
        }).catch(function (e) { toast(e.message, true); });
      }, '提交反馈');
    });
  };

  function injectEntries() {
    if ($('nf_feedback')) return true;
    var meView = $('viewMe');
    if (!meView) return false;
    var group = null, gs = meView.querySelectorAll('.setting-group');
    for (var i = 0; i < gs.length; i++) {
      var h3 = gs[i].querySelector('h3');
      if (h3 && h3.textContent.indexOf('新功能') >= 0) { group = gs[i]; break; }
    }
    if (!group) return false;
    if (!$('nf_myscores')) {
      var r1 = document.createElement('div');
      r1.className = 'setting-row'; r1.id = 'nf_myscores';
      r1.innerHTML = '<span><i class="fas fa-trophy"></i>我的游戏成绩</span><span class="right">></span>';
      r1.onclick = window.openMyScores;
      group.appendChild(r1);
    }
    if (!$('nf_feedback')) {
      var r2 = document.createElement('div');
      r2.className = 'setting-row'; r2.id = 'nf_feedback';
      r2.innerHTML = '<span><i class="fas fa-comment-dots"></i>意见反馈</span><span class="right">></span>';
      r2.onclick = window.openFeedback;
      group.appendChild(r2);
    }
    return true;
  }
  var tries = 0;
  var timer = setInterval(function () { tries++; if (injectEntries() || tries > 60) clearInterval(timer); }, 1000);
  injectEntries();
  console.log('[nf5] 已加载');
})();

