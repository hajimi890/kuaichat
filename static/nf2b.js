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

  window.forwardMessage = function (mid) {
    Promise.all([
      authFetch('/api/friends').then(function (r) { return r.json(); }),
      authFetch('/api/group/list').then(function (r) { return r.json(); })
    ]).then(function (arr) {
      var friends = arr[0].ok ? arr[0].friends : [];
      var groups = arr[1].ok ? arr[1].groups : [];
      var html = '<div style="max-height:300px;overflow-y:auto;"><div style="font-size:12px;color:#90a4ae;margin:8px 0;">好友</div>';
      friends.forEach(function (f) { html += '<div class="fwd-target" data-type="user" data-id="' + esc(f.username) + '" style="padding:10px;border-radius:10px;cursor:pointer;">' + esc(f.username) + '</div>'; });
      html += '<div style="font-size:12px;color:#90a4ae;margin:8px 0;">群聊</div>';
      groups.forEach(function (g) { html += '<div class="fwd-target" data-type="group" data-id="' + g.id + '" style="padding:10px;border-radius:10px;cursor:pointer;">' + esc(g.name) + '</div>'; });
      html += '</div>';
      modal('转发给', html, null, '取消');
      setTimeout(function () {
        document.querySelectorAll('.fwd-target').forEach(function (el) {
          el.onclick = function () {
            authFetch('/api/messages/forward', { method: 'POST', body: JSON.stringify({ message_id: mid, target_type: el.dataset.type, target_id: el.dataset.id }) })
              .then(function (r) { return r.json(); }).then(function (d) {
                if (!d.ok) throw new Error(d.error || '失败');
                toast('已转发'); $('modalOverlay').classList.add('hidden');
              }).catch(function (e) { toast(e.message, true); });
          };
        });
      }, 100);
    });
  };

  window.refreshOnlineStatus = function () {
    var list = $('friendList'); if (!list) return;
    var names = [];
    list.querySelectorAll('.user-item').forEach(function (item) {
      var nm = item.querySelector('.user-info .name');
      if (nm) names.push(nm.textContent.trim());
    });
    if (!names.length) return;
    authFetch('/api/friends/online?names=' + encodeURIComponent(names.join(',')))
      .then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) return;
        list.querySelectorAll('.user-item').forEach(function (item) {
          var nm = item.querySelector('.user-info .name'); if (!nm) return;
          var av = item.querySelector('.avatar'); if (!av) return;
          if (d.online[nm.textContent.trim()]) av.classList.add('online'); else av.classList.remove('online');
        });
      }).catch(function () {});
  };

  window.openMomentVisibility = function () {
    authFetch('/api/moment/visibility').then(function (r) { return r.json(); }).then(function (d) {
      var cur = d.ok ? d.mode : 'all';
      var html = '<div style="font-size:13px;color:#546e7a;line-height:2;">' +
        '<label style="display:block;"><input type="radio" name="vis" value="all" ' + (cur === 'all' ? 'checked' : '') + '> 所有人可见</label>' +
        '<label style="display:block;"><input type="radio" name="vis" value="friends" ' + (cur === 'friends' ? 'checked' : '') + '> 仅好友可见</label>' +
        '<label style="display:block;"><input type="radio" name="vis" value="whitelist" ' + (cur === 'whitelist' ? 'checked' : '') + '> 白名单可见</label>' +
        '<label style="display:block;"><input type="radio" name="vis" value="blacklist" ' + (cur === 'blacklist' ? 'checked' : '') + '> 黑名单不可见</label></div>';
      modal('朋友圈可见范围', html, function () {
        var sel = document.querySelector('input[name="vis"]:checked'); if (!sel) return;
        authFetch('/api/moment/visibility', { method: 'POST', body: JSON.stringify({ mode: sel.value, list: [] }) })
          .then(function (r) { return r.json(); }).then(function (d2) {
            if (!d2.ok) throw new Error(d2.error || '失败');
            toast('已保存'); $('modalOverlay').classList.add('hidden');
          }).catch(function (e) { toast(e.message, true); });
      }, '保存');
    });
  };
})();
