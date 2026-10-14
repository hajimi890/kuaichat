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

  window.favoriteMessage = function (mid) {
    authFetch('/api/favorites', { method: 'POST', body: JSON.stringify({ message_id: mid }) })
      .then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) throw new Error(d.error || '失败');
        toast('已收藏');
      }).catch(function (e) { toast(e.message, true); });
  };

  window.openFavorites = function () {
    authFetch('/api/favorites').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      var html = '<div style="max-height:400px;overflow-y:auto;">';
      if (!d.favorites.length) html += '<div style="text-align:center;color:#90a4ae;padding:20px;">还没有收藏</div>';
      else d.favorites.forEach(function (f) {
        html += '<div style="padding:10px;border-bottom:1px solid #f0f7fe;">' +
          '<div style="font-size:13px;color:#0d3d6b;word-break:break-word;">' + esc(f.content || '').slice(0, 200) + '</div>' +
          '<div style="font-size:11px;color:#90a4ae;margin-top:4px;">' + new Date(f.created_at * 1000).toLocaleString() + ' <button class="fav-del" data-id="' + f.id + '" style="float:right;background:none;border:none;color:#e53935;cursor:pointer;">删除</button></div></div>';
      });
      html += '</div>';
      modal('我的收藏', html, null, '关闭');
      setTimeout(function () {
        document.querySelectorAll('.fav-del').forEach(function (b) {
          b.onclick = function () {
            authFetch('/api/favorites/delete', { method: 'POST', body: JSON.stringify({ id: b.dataset.id }) })
              .then(function () { toast('已删除'); b.parentNode.parentNode.remove(); });
          };
        });
      }, 100);
    });
  };

  window.pinMessage = function (mid) {
    var room = getRoom(); if (!room) return toast('请先进入聊天', true);
    authFetch('/api/pinned_messages', { method: 'POST', body: JSON.stringify({ room: room, message_id: mid, action: 'pin' }) })
      .then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) throw new Error(d.error || '失败');
        toast('已置顶');
      }).catch(function (e) { toast(e.message, true); });
  };

  window.openPinnedMessages = function () {
    var room = getRoom(); if (!room) return toast('请先进入聊天', true);
    authFetch('/api/pinned_messages?room=' + encodeURIComponent(room))
      .then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) return toast(d.error, true);
        var html = '<div style="max-height:400px;overflow-y:auto;">';
        if (!d.pinned.length) html += '<div style="text-align:center;color:#90a4ae;padding:20px;">还没有置顶消息</div>';
        else d.pinned.forEach(function (p) {
          html += '<div style="padding:10px;border-bottom:1px solid #f0f7fe;font-size:13px;color:#0d3d6b;">' +
            '<b>' + esc(p.pinned_by) + '</b>：' + esc(p.content || '').slice(0, 100) +
            ' <button class="unpin-btn" data-id="' + p.message_id + '" style="float:right;background:none;border:none;color:#e53935;cursor:pointer;">取消</button></div>';
        });
        html += '</div>';
        modal('置顶消息', html, null, '关闭');
        setTimeout(function () {
          document.querySelectorAll('.unpin-btn').forEach(function (b) {
            b.onclick = function () {
              authFetch('/api/pinned_messages', { method: 'POST', body: JSON.stringify({ room: room, message_id: b.dataset.id, action: 'unpin' }) })
                .then(function () { toast('已取消'); b.parentNode.remove(); });
            };
          });
        }, 100);
      });
  };

  var selectMode = false, selectedIds = new Set();
  window.toggleSelectMode = function () {
    selectMode = !selectMode; selectedIds.clear();
    var c = $('chatContainer') || $('groupChatContainer');
    if (!c) return;
    c.querySelectorAll('.msg-row').forEach(function (row) {
      var mid = row.dataset.mid; if (!mid) return;
      if (selectMode) {
        if (!row.querySelector('.msg-checkbox')) {
          var cb = document.createElement('input');
          cb.type = 'checkbox'; cb.className = 'msg-checkbox';
          cb.style.cssText = 'position:absolute;left:-24px;top:12px;width:18px;height:18px;';
          row.style.position = 'relative';
          row.insertBefore(cb, row.firstChild);
          cb.onchange = function () { if (cb.checked) selectedIds.add(mid); else selectedIds.delete(mid); };
        }
        row.querySelector('.msg-checkbox').style.display = 'block';
      } else {
        var c2 = row.querySelector('.msg-checkbox');
        if (c2) c2.style.display = 'none';
      }
    });
    toast(selectMode ? '多选已开启' : '已退出多选');
    if (selectMode) {
      if (!$('batchDeleteBar')) {
        var bar = document.createElement('div');
        bar.id = 'batchDeleteBar';
        bar.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:#fff;border-radius:14px;box-shadow:0 8px 24px rgba(0,0,0,.2);padding:10px 16px;display:flex;gap:10px;z-index:300;';
        bar.innerHTML = '<button id="doBatchDelete" style="background:#e53935;color:#fff;border:none;border-radius:10px;padding:10px 20px;font-weight:600;font-family:inherit;cursor:pointer;">删除已选</button>' +
          '<button id="cancelBatchDelete" style="background:#f5faff;color:#546e7a;border:1px solid #e3f2fd;border-radius:10px;padding:10px 20px;font-weight:600;font-family:inherit;cursor:pointer;">取消</button>';
        document.body.appendChild(bar);
        $('doBatchDelete').onclick = function () {
          var ids = Array.from(selectedIds);
          if (!ids.length) return toast('未选择', true);
          if (!confirm('删除选中的 ' + ids.length + ' 条？')) return;
          authFetch('/api/messages/batch_delete', { method: 'POST', body: JSON.stringify({ ids: ids }) })
            .then(function (r) { return r.json(); }).then(function (d) {
              if (!d.ok) throw new Error(d.error || '失败');
              toast('已删除 ' + d.deleted + ' 条');
              var cc = $('chatContainer') || $('groupChatContainer');
              if (cc) cc.querySelectorAll('.msg-row').forEach(function (row) { if (ids.indexOf(row.dataset.mid) >= 0) row.remove(); });
              window.toggleSelectMode();
            }).catch(function (e) { toast(e.message, true); });
        };
        $('cancelBatchDelete').onclick = window.toggleSelectMode;
      }
    } else {
      var bb = $('batchDeleteBar'); if (bb) bb.remove();
    }
  };
})();
