(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s || '').replace(/[&<>"']/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }
  function fmtSize(b) { if (!b) return '0B'; if (b < 1024) return b + 'B'; if (b < 1048576) return (b/1024).toFixed(1) + 'KB'; return (b/1048576).toFixed(1) + 'MB'; }
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

  window.openMyQrcode = function () {
    authFetch('/api/qrcode/me').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error || '失败', true);
      var html = '<div style="text-align:center;">';
      if (d.data_url) html += '<img src="' + d.data_url + '" style="width:200px;height:200px;border-radius:12px;display:block;margin:0 auto 12px;">';
      else html += '<div style="padding:30px;color:#90a4ae;">未安装 qrcode 库</div>';
      html += '<div style="font-size:13px;color:#546e7a;word-break:break-all;">' + esc(d.text) + '</div></div>';
      modal('我的二维码', html, null, '知道了');
    }).catch(function () { toast('网络错误', true); });
  };

  window.openScanAdd = function () {
    var html = '<div style="font-size:13px;color:#546e7a;margin-bottom:10px;">粘贴二维码文本：</div>' +
      '<input id="scanInput" class="modal-input" placeholder="kuaichat://add?id=..." style="width:100%;box-sizing:border-box;">';
    modal('扫一扫加好友', html, function () {
      var text = ($('scanInput') && $('scanInput').value || '').trim();
      if (!text) return toast('请输入', true);
      authFetch('/api/qrcode/parse', { method: 'POST', body: JSON.stringify({ text: text }) })
        .then(function (r) { return r.json(); }).then(function (d) {
          if (!d.ok) return toast(d.error || '失败', true);
          $('modalOverlay').classList.add('hidden');
          if (d.already) return toast('你们已经是好友了');
          return authFetch('/api/friend/request', { method: 'POST', body: JSON.stringify({ peer: d.peer, message: '通过二维码添加' }) })
            .then(function (r) { return r.json(); }).then(function (rd) {
              if (!rd.ok) throw new Error(rd.error || '失败');
              toast('已发送好友请求');
            });
        }).catch(function (e) { toast(e.message || '失败', true); });
    }, '添加');
  };

  window.showUserProfile = function (name) {
    authFetch('/api/user/profile_by_name?username=' + encodeURIComponent(name))
      .then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) return toast(d.error || '不存在', true);
        var u = d.user;
        var html = '<div style="text-align:center;">' +
          '<div style="font-size:16px;font-weight:700;color:#0d3d6b;">' + esc(u.username) + '</div>' +
          '<div style="font-size:12px;color:' + (u.online ? '#1bbf8b' : '#90a4ae') + ';">' + (u.online ? '● 在线' : '○ 离线') + '</div>' +
          (u.bio ? '<div style="font-size:13px;color:#546e7a;margin-top:10px;">' + esc(u.bio) + '</div>' : '') + '</div>';
        modal('用户资料', html, null, '关闭');
      });
  };

  window.openMentions = function () {
    authFetch('/api/mentions/unread').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      if (!d.mentions.length) return toast('没有未读 @');
      var html = '<div style="max-height:400px;overflow-y:auto;">';
      d.mentions.forEach(function (m) {
        html += '<div style="padding:10px;border-bottom:1px solid #f0f7fe;font-size:13px;color:#1976d2;">' + esc(m.mentioned_by) + ' 在 ' + esc(m.room) + ' @了你</div>';
      });
      html += '</div>';
      modal('未读 @', html, null, '关闭');
      authFetch('/api/mentions/read', { method: 'POST', body: JSON.stringify({}) }).catch(function () {});
    });
  };
})();
