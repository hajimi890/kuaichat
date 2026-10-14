(function () {
  'use strict';
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
  function toast(m, e) { if (typeof window.showToast === 'function') return window.showToast(m, e); alert(m); }
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
  function getRoom() {
    var gs = $('groupChatScreen'), cs = $('chatScreen');
    if (gs && !gs.classList.contains('hidden') && window.currentGroup) return 'group_' + window.currentGroup.id;
    if (cs && !cs.classList.contains('hidden') && window.currentRoom) return window.currentRoom;
    return '';
  }

  window.transcribeVoice = function (url) {
    authFetch('/api/voice/transcribe', { method: 'POST', body: JSON.stringify({ url: url }) })
      .then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) return toast(d.error, true);
        modal('语音转文字', '<div style="font-size:14px;line-height:1.8;">' + esc(d.text) + '</div>', null, '关闭');
      });
  };

  window.jumpToUnread = function () {
    var room = getRoom(); if (!room) return;
    authFetch('/api/room/unread_anchor?room=' + encodeURIComponent(room))
      .then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) return;
        var mid = d.first_unread_id;
        var c = $('chatContainer') || $('groupChatContainer');
        if (!c || !mid) return;
        var el = c.querySelector('.msg-row[data-mid="' + mid + '"]');
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.style.background = '#fff3cd'; setTimeout(function () { el.style.background = ''; }, 1500);
        } else toast('未找到未读消息');
      });
  };

  window.showMomentLikes = function (mid) {
    authFetch('/api/moment/likes?moment_id=' + mid).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      var html = '<div style="max-height:300px;overflow-y:auto;">';
      if (!d.likes.length) html += '<div style="text-align:center;color:#90a4ae;padding:20px;">还没有人点赞</div>';
      d.likes.forEach(function (u) {
        html += '<div style="display:flex;align-items:center;gap:10px;padding:8px 0;">' +
          '<div style="width:36px;height:36px;border-radius:12px;background:linear-gradient(135deg,#42a5f5,#1e88e5);color:#fff;display:flex;align-items:center;justify-content:center;font-weight:600;">' + (u.username[0] || '?').toUpperCase() + '</div>' +
          '<div style="font-size:14px;color:#0d3d6b;">' + esc(u.username) + '</div></div>';
      });
      html += '</div>';
      modal('点赞列表', html, null, '关闭');
    });
  };

  window.replyComment = function (momentId, parentId, parentUser) {
    var html = '<div style="font-size:12px;color:#90a4ae;margin-bottom:6px;">回复 ' + esc(parentUser) + '：</div>' +
      '<textarea id="replyCommentInput" placeholder="说点什么..." maxlength="200" style="width:100%;min-height:80px;background:#f5faff;border:1.5px solid #d4e4f7;border-radius:12px;padding:10px;font-family:inherit;font-size:14px;box-sizing:border-box;"></textarea>';
    modal('回复评论', html, function () {
      var c = ($('replyCommentInput') && $('replyCommentInput').value || '').trim();
      if (!c) return toast('请输入内容', true);
      authFetch('/api/moment/comment/reply', { method: 'POST', body: JSON.stringify({ moment_id: momentId, parent_id: parentId, content: c }) })
        .then(function (r) { return r.json(); }).then(function (d) {
          if (!d.ok) throw new Error(d.error || '失败');
          toast('已回复'); $('modalOverlay').classList.add('hidden');
          if (typeof refreshMoments === 'function') refreshMoments();
        }).catch(function (e) { toast(e.message, true); });
    }, '发送');
  };
})();
