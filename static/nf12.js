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

  // ===== 1. 正在输入 =====
  var typingTimer = null;
  function bindTyping(inputId) {
    var inp = $(inputId);
    if (!inp) return;
    inp.addEventListener('input', function () {
      var room = getRoom();
      if (!room) return;
      if (typingTimer) clearTimeout(typingTimer);
      typingTimer = setTimeout(function () {
        authFetch('/api/typing', { method: 'POST', body: JSON.stringify({ room: room }) }).catch(function () {});
        typingTimer = null;
      }, 1500);
    });
  }
  bindTyping('msgInput');
  bindTyping('groupMsgInput');

  // 轮询"对方正在输入"
  var typingPollRoom = null;
  setInterval(function () {
    var room = getRoom();
    if (!room || room === typingPollRoom) { /* 仍然查 */ }
    typingPollRoom = room;
    if (!room) return;
    authFetch('/api/typing/check?room=' + encodeURIComponent(room))
      .then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) return;
        var names = d.typing || [];
        var el = $('typingHint');
        if (!el) {
          el = document.createElement('div');
          el.id = 'typingHint';
          el.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);bottom:90px;background:rgba(13,61,107,.85);color:#fff;font-size:12px;padding:6px 14px;border-radius:20px;z-index:1500;display:none;';
          document.body.appendChild(el);
        }
        if (names.length > 0) {
          el.textContent = (names.length === 1 ? names[0] + ' 正在输入…' : names.length + ' 人正在输入…');
          el.style.display = 'block';
        } else {
          el.style.display = 'none';
        }
      }).catch(function () {});
  }, 2500);

  // ===== 2. 定时发送 =====
  window.openScheduleMsg = function () {
    var room = getRoom();
    if (!room) return toast('请先进入聊天', true);
    var html = '<div style="font-size:13px;color:#546e7a;margin-bottom:8px;">消息内容：</div>' +
      '<textarea id="schedContent" style="width:100%;min-height:80px;background:#f5faff;border:1.5px solid #d4e4f7;border-radius:12px;padding:10px;font-family:inherit;font-size:14px;box-sizing:border-box;" placeholder="要定时发送的内容"></textarea>' +
      '<div style="font-size:13px;color:#546e7a;margin:12px 0 8px;">延迟多久发？</div>' +
      '<select id="schedDelay" class="modal-input" style="width:100%;box-sizing:border-box;margin-top:0;">' +
      '<option value="1">1 分钟后</option>' +
      '<option value="5">5 分钟后</option>' +
      '<option value="30">30 分钟后</option>' +
      '<option value="60" selected>1 小时后</option>' +
      '<option value="180">3 小时后</option>' +
      '<option value="720">12 小时后</option>' +
      '<option value="1440">24 小时后</option>' +
      '</select>';
    modal('定时发送', html, function () {
      var content = ($('schedContent') && $('schedContent').value || '').trim();
      var delay = parseInt($('schedDelay').value);
      if (!content) return toast('请输入内容', true);
      authFetch('/api/schedule_msg', {
        method: 'POST',
        body: JSON.stringify({ room: room, content: content, delay_min: delay })
      }).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.ok) throw new Error(d.error || '失败');
        toast('✅ 已定时，将在 ' + d.at + ' 发送');
        $('modalOverlay').classList.add('hidden');
      }).catch(function (e) { toast(e.message, true); });
    }, '定时');
  };

  // ===== 4. 头像挂件 =====
  window.openFrameShop = function () {
    authFetch('/api/frame/list').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast('加载失败', true);
      var html = '<div style="text-align:center;font-size:13px;color:#90a4ae;margin-bottom:10px;">当前积分：<b style="color:#ff9800;">' + d.points + '</b></div>' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;max-height:400px;overflow-y:auto;">';
      d.frames.forEach(function (f) {
        var isCurrent = d.current === f.id;
        html += '<div style="background:#f5faff;border:1.5px solid ' + (isCurrent ? '#42a5f5' : '#e3f2fd') + ';border-radius:12px;padding:14px;text-align:center;">' +
          '<div style="font-size:32px;margin-bottom:8px;">' + (f.name.split(' ')[0] || '无') + '</div>' +
          '<div style="font-size:13px;font-weight:600;color:#0d3d6b;">' + f.name.split(' ').slice(1).join(' ') + '</div>' +
          '<div style="font-size:11px;color:#90a4ae;margin:4px 0;">' + (f.price > 0 ? f.price + ' 积分' : '免费') + '</div>' +
          '<button type="button" data-fid="' + f.id + '" data-price="' + f.price + '" data-cur="' + (isCurrent ? '1' : '0') + '" class="frame-act-btn" style="width:100%;background:' + (isCurrent ? '#e3f2fd;color:#1976d2;border:1px solid #bbdefb' : '#42a5f5;color:#fff;border:none') + ';border-radius:8px;padding:7px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;margin-top:6px;">' +
          (isCurrent ? '使用中' : (f.price === 0 ? '使用' : '购买并使用')) +
          '</button>' +
          '</div>';
      });
      html += '</div>';
      modal('头像挂件商店', html, null, '关闭');
      setTimeout(function () {
        document.querySelectorAll('.frame-act-btn').forEach(function (b) {
          b.onclick = function () {
            if (b.dataset.cur === '1') return;
            var fid = b.dataset.fid;
            var price = parseInt(b.dataset.price);
            if (price > 0) {
              if (!confirm('花 ' + price + ' 积分购买？')) return;
              authFetch('/api/frame/buy', { method: 'POST', body: JSON.stringify({ id: fid }) })
                .then(function (r) { return r.json(); }).then(function (d2) {
                  if (!d2.ok) throw new Error(d2.error || '失败');
                  toast('✅ 已购买并使用');
                  window.openFrameShop();
                }).catch(function (e) { toast(e.message, true); });
            } else {
              authFetch('/api/frame/equip', { method: 'POST', body: JSON.stringify({ id: fid }) })
                .then(function () { toast('已使用'); $('modalOverlay').classList.add('hidden'); })
                .catch(function () { toast('失败', true); });
            }
          };
        });
      }, 50);
    });
  };

  // ===== 我页面注入 =====
  function injectMe() {
    if ($('nf_batch1')) return true;
    var meView = $('viewMe');
    if (!meView) return false;
    var group = null, gs = meView.querySelectorAll('.setting-group');
    for (var i = 0; i < gs.length; i++) {
      var h3 = gs[i].querySelector('h3');
      if (h3 && h3.textContent.indexOf('新功能') >= 0) { group = gs[i]; break; }
    }
    if (!group) return false;
    if (!$('nf_batch1')) {
      var r1 = document.createElement('div');
      r1.id = 'nf_batch1';
      r1.className = 'setting-row';
      r1.innerHTML = '<span><i class="fas fa-hat-cowboy"></i>头像挂件商店</span><span class="right">></span>';
      r1.onclick = window.openFrameShop;
      group.appendChild(r1);
    }
    return true;
  }
  var tries = 0;
  var timer = setInterval(function () { tries++; if (injectMe() || tries > 60) clearInterval(timer); }, 1000);
  injectMe();

  console.log('[nf12] 第1批已加载');
})();
