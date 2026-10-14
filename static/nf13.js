(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
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
    if (!t) return;
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

  window.openForwardBatch = function () {
    var selected = [];
    document.querySelectorAll('.msg-checkbox:checked').forEach(function (cb) {
      var row = cb.closest('.msg-row');
      if (row && row.dataset.mid) selected.push(row.dataset.mid);
    });
    if (selected.length === 0) return toast('请先勾选要转发的消息', true);
    Promise.all([
      authFetch('/api/friends').then(function (r) { return r.json(); }),
      authFetch('/api/group/list').then(function (r) { return r.json(); })
    ]).then(function (arr) {
      var friends = arr[0].ok ? arr[0].friends : [];
      var groups = arr[1].ok ? arr[1].groups : [];
      var html = '<div style="max-height:300px;overflow-y:auto;"><div style="font-size:12px;color:#90a4ae;margin:8px 0;">好友</div>';
      friends.forEach(function (f) { html += '<div class="fwd-target" data-type="user" data-id="' + f.username + '" style="padding:10px;border-radius:10px;cursor:pointer;">' + f.username + '</div>'; });
      html += '<div style="font-size:12px;color:#90a4ae;margin:8px 0;">群聊</div>';
      groups.forEach(function (g) { html += '<div class="fwd-target" data-type="group" data-id="' + g.id + '" style="padding:10px;border-radius:10px;cursor:pointer;">' + g.name + '</div>'; });
      html += '</div>';
      modal('合并转发到', html, null, '取消');
      setTimeout(function () {
        document.querySelectorAll('.fwd-target').forEach(function (el) {
          el.onclick = function () {
            authFetch('/api/messages/forward_batch', {
              method: 'POST',
              body: JSON.stringify({ ids: selected, target_type: el.dataset.type, target_id: el.dataset.id })
            }).then(function (r) { return r.json(); }).then(function (d) {
              if (!d.ok) throw new Error(d.error || '失败');
              toast('✅ 已合并转发 ' + selected.length + ' 条');
              $('modalOverlay').classList.add('hidden');
            }).catch(function (e) { toast(e.message, true); });
          };
        });
      }, 50);
    });
  };

  window.openDailyTasks = function () {
    authFetch('/api/tasks/today').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      var html = '<div style="font-size:12px;color:#90a4ae;margin-bottom:10px;">每天 0 点重置</div>';
      d.tasks.forEach(function (t) {
        html += '<div style="display:flex;align-items:center;padding:12px;border-bottom:1px solid #f0f7fe;">' +
          '<div style="flex:1;"><div style="font-size:14px;font-weight:600;color:#0d3d6b;">' + t.name + '</div>' +
          '<div style="font-size:11px;color:#ff9800;margin-top:2px;">+' + t.points + ' 积分</div></div>' +
          '<button type="button" data-key="' + t.key + '" data-done="' + (t.done ? '1' : '0') + '" class="task-claim" style="background:' + (t.done ? '#f5faff;color:#90a4ae;border:1px solid #e3f2fd' : '#42a5f5;color:#fff;border:none') + ';border-radius:8px;padding:8px 16px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;">' +
          (t.done ? '已完成' : '领取') + '</button></div>';
      });
      modal('每日任务', html, null, '关闭');
      setTimeout(function () {
        document.querySelectorAll('.task-claim').forEach(function (b) {
          b.onclick = function () {
            if (b.dataset.done === '1') return;
            authFetch('/api/tasks/claim', { method: 'POST', body: JSON.stringify({ key: b.dataset.key }) })
              .then(function (r) { return r.json(); }).then(function (d2) {
                if (!d2.ok) throw new Error(d2.error || '失败');
                toast('✅ 领取成功 +' + d2.points);
                window.openDailyTasks();
              }).catch(function (e) { toast(e.message, true); });
          };
        });
      }, 50);
    });
  };

  window.openAchievements = function () {
    authFetch('/api/achievements/check', { method: 'POST' }).then(function () {
      return authFetch('/api/achievements').then(function (r) { return r.json(); });
    }).then(function (d) {
      if (!d.ok) return toast('加载失败', true);
      var html = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-height:420px;overflow-y:auto;">';
      d.list.forEach(function (a) {
        var opacity = a.unlocked ? '1' : '.35';
        html += '<div style="background:#f5faff;border:1.5px solid ' + (a.unlocked ? '#42a5f5' : '#e3f2fd') + ';border-radius:12px;padding:12px;text-align:center;opacity:' + opacity + ';">' +
          '<div style="font-size:28px;color:' + (a.unlocked ? '#ffc107' : '#90a4ae') + ';margin-bottom:6px;"><i class="fas ' + a.icon + '"></i></div>' +
          '<div style="font-size:13px;font-weight:600;color:#0d3d6b;">' + a.name + '</div>' +
          '<div style="font-size:11px;color:#90a4ae;margin-top:3px;">' + a.desc + '</div>' +
          (a.unlocked ? '<div style="font-size:10px;color:#1bbf8b;margin-top:4px;">✅ 已解锁</div>' : '') +
          '</div>';
      });
      html += '</div>';
      modal('我的成就', html, null, '关闭');
    });
  };

  window.openDateSearch = function () {
    var room = getRoom();
    if (!room) return toast('请先进入聊天', true);
    var html = '<div style="font-size:13px;color:#546e7a;margin-bottom:8px;">选择日期：</div>' +
      '<input type="date" id="dateSearchInput" class="modal-input" style="width:100%;box-sizing:border-box;margin-top:0;">';
    modal('按日期搜索', html, function () {
      var date = $('dateSearchInput') && $('dateSearchInput').value;
      if (!date) return toast('请选日期', true);
      authFetch('/api/messages/search_by_date?room=' + encodeURIComponent(room) + '&date=' + date)
        .then(function (r) { return r.json(); }).then(function (d) {
          if (!d.ok) throw new Error(d.error || '失败');
          $('modalOverlay').classList.add('hidden');
          var list = (d.messages || []).map(function (m) {
            var t = new Date(m.created_at * 1000);
            return '[' + (t.getHours() < 10 ? '0' : '') + t.getHours() + ':' + (t.getMinutes() < 10 ? '0' : '') + t.getMinutes() + '] ' + m.sender + ': ' + m.content;
          }).join('\n');
          modal('搜索 ' + date + '（' + d.count + ' 条）', '<pre style="font-size:12px;line-height:1.7;white-space:pre-wrap;word-break:break-word;max-height:400px;overflow-y:auto;">' + list.replace(/[<>&]/g, function(c){return {'<':'&lt;','>':'&gt;','&':'&amp;'}[c];}) + '</pre>', null, '关闭');
        }).catch(function (e) { toast(e.message, true); });
    }, '搜索');
  };

  function injectMe() {
    if ($('nf_batch2')) return true;
    var meView = $('viewMe');
    if (!meView) return false;
    var group = null, gs = meView.querySelectorAll('.setting-group');
    for (var i = 0; i < gs.length; i++) {
      var h3 = gs[i].querySelector('h3');
      if (h3 && h3.textContent.indexOf('新功能') >= 0) { group = gs[i]; break; }
    }
    if (!group) return false;
    if (!$('nf_batch2')) {
      var r1 = document.createElement('div');
      r1.id = 'nf_batch2';
      r1.className = 'setting-row';
      r1.innerHTML = '<span><i class="fas fa-tasks"></i>每日任务</span><span class="right">></span>';
      r1.onclick = window.openDailyTasks;
      group.appendChild(r1);
      var r2 = document.createElement('div');
      r2.className = 'setting-row';
      r2.id = 'nf_ach';
      r2.innerHTML = '<span><i class="fas fa-medal"></i>我的成就</span><span class="right">></span>';
      r2.onclick = window.openAchievements;
      group.appendChild(r2);
    }
    return true;
  }
  var tries = 0;
  var timer = setInterval(function () { tries++; if (injectMe() || tries > 60) clearInterval(timer); }, 1000);
  injectMe();
  console.log('[nf13] 第2批已加载');
})();
