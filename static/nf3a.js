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

  window.openCreateVote = function () {
    var gid = window.currentGroup && window.currentGroup.id;
    if (!gid) return toast('请先进入群聊', true);
    var html = '<div style="font-size:13px;color:#546e7a;margin-bottom:8px;">投票主题：</div>' +
      '<input id="voteTitle" class="modal-input" placeholder="周末聚餐" style="width:100%;box-sizing:border-box;">' +
      '<div style="font-size:13px;color:#546e7a;margin:12px 0 8px;">选项（每行一个）：</div>' +
      '<textarea id="voteOptions" placeholder="火锅&#10;烤肉" style="width:100%;min-height:100px;background:#f5faff;border:1.5px solid #d4e4f7;border-radius:12px;padding:10px;font-family:inherit;font-size:14px;box-sizing:border-box;"></textarea>';
    modal('发起群投票', html, function () {
      var title = ($('voteTitle') && $('voteTitle').value || '').trim();
      var options = ($('voteOptions') && $('voteOptions').value || '').split('\n').map(function (x) { return x.trim(); }).filter(Boolean);
      if (!title) return toast('请输入主题', true);
      if (options.length < 2) return toast('至少 2 个选项', true);
      authFetch('/api/group/vote/create', { method: 'POST', body: JSON.stringify({ group_id: gid, title: title, options: options }) })
        .then(function (r) { return r.json(); }).then(function (d) {
          if (!d.ok) throw new Error(d.error || '失败');
          toast('投票已发起'); $('modalOverlay').classList.add('hidden');
          if (typeof openGroupChat === 'function' && window.currentGroup) openGroupChat(window.currentGroup);
        }).catch(function (e) { toast(e.message, true); });
    }, '发起投票');
  };

  window.openVote = function (voteId) {
    authFetch('/api/group/vote/info?vote_id=' + voteId).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      var v = d.vote, total = v.total || 0;
      var html = '<div style="font-size:15px;font-weight:700;color:#0d3d6b;margin-bottom:12px;">' + esc(v.title) + '</div>' +
        '<div style="font-size:12px;color:#90a4ae;margin-bottom:12px;">共 ' + total + ' 人投票 · 发起人：' + esc(v.creator) + '</div>';
      v.options.forEach(function (opt, i) {
        var pct = total ? Math.round(v.counts[i] / total * 100) : 0;
        var isMine = v.my_vote === i;
        html += '<div class="vote-opt" data-i="' + i + '" style="padding:12px;border-radius:12px;border:1.5px solid ' + (isMine ? '#42a5f5' : '#e3f2fd') + ';background:' + (isMine ? '#e3f2fd' : '#f5faff') + ';margin-bottom:8px;cursor:pointer;">' +
          '<div style="display:flex;justify-content:space-between;"><span>' + esc(opt) + (isMine ? ' ✓' : '') + '</span><span>' + v.counts[i] + ' 票 ' + pct + '%</span></div></div>';
      });
      modal('群投票', html, null, '关闭');
      setTimeout(function () {
        document.querySelectorAll('.vote-opt').forEach(function (el) {
          el.onclick = function () {
            var i = parseInt(el.dataset.i);
            authFetch('/api/group/vote/cast', { method: 'POST', body: JSON.stringify({ vote_id: voteId, option_index: i }) })
              .then(function (r) { return r.json(); }).then(function (d2) {
                if (!d2.ok) throw new Error(d2.error || '失败');
                toast('已投票'); $('modalOverlay').classList.add('hidden'); window.openVote(voteId);
              }).catch(function (e) { toast(e.message, true); });
          };
        });
      }, 100);
    });
  };

  window.shareLocation = function () {
    var room = getRoom(); if (!room) return toast('请先进入聊天', true);
    if (!navigator.geolocation) return toast('不支持定位', true);
    toast('正在获取位置...');
    navigator.geolocation.getCurrentPosition(function (pos) {
      authFetch('/api/location/share', { method: 'POST', body: JSON.stringify({ room: room, lat: pos.coords.latitude, lng: pos.coords.longitude, text: '我在这里' }) })
        .then(function (r) { return r.json(); }).then(function (d) { if (!d.ok) throw new Error(d.error || '失败'); toast('位置已发送'); })
        .catch(function (e) { toast(e.message, true); });
    }, function (err) { toast('定位失败：' + err.message + '（请允许定位）', true); }, { timeout: 10000, enableHighAccuracy: true });
  };

  window.openGroupFiles = function () {
    var gid = window.currentGroup && window.currentGroup.id;
    if (!gid) return toast('请先进入群聊', true);
    authFetch('/api/group/files?group_id=' + gid).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      var html = '<div style="max-height:400px;overflow-y:auto;">';
      if (!d.files.length) html += '<div style="text-align:center;color:#90a4ae;padding:20px;">还没有共享文件</div>';
      d.files.forEach(function (f) {
        html += '<div style="padding:10px;border-bottom:1px solid #f0f7fe;display:flex;gap:10px;align-items:center;">' +
          '<i class="fas fa-file" style="color:#1976d2;font-size:20px;"></i>' +
          '<div style="flex:1;min-width:0;"><div style="font-size:13px;font-weight:600;color:#0d3d6b;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + esc(f.name) + '</div>' +
          '<div style="font-size:11px;color:#90a4ae;">' + esc(f.sender) + ' · ' + fmtSize(f.size) + '</div></div>' +
          '<a href="' + f.url + '" download style="color:#1e88e5;font-size:12px;text-decoration:none;">下载</a></div>';
      });
      html += '</div>';
      modal('群文件', html, null, '关闭');
    });
  };
})();
