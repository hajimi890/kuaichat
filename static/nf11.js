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

  var lastMsgId = 0;
  var originalTitle = document.title;
  var titleTimer = null;
  var soundEnabled = localStorage.getItem('kuaichat_notify_sound') !== 'off';

  // ===== 声音 =====
  var audioCtx = null;
  function playBeep() {
    if (!soundEnabled) return;
    try {
      if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      // 两个短促的蜂鸣
      [0, 0.15].forEach(function (delay) {
        var osc = audioCtx.createOscillator();
        var gain = audioCtx.createGain();
        osc.connect(gain); gain.connect(audioCtx.destination);
        osc.frequency.value = 880;
        osc.type = 'sine';
        var t0 = audioCtx.currentTime + delay;
        gain.gain.setValueAtTime(0.001, t0);
        gain.gain.exponentialRampToValueAtTime(0.3, t0 + 0.01);
        gain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.12);
        osc.start(t0); osc.stop(t0 + 0.13);
      });
    } catch (e) {}
  }

  // ===== 震动 =====
  function vibrate() {
    if (navigator.vibrate) {
      navigator.vibrate([200, 100, 200]);
    }
  }

  // ===== 标题闪烁 =====
  function flashTitle() {
    if (titleTimer) return;
    var flip = false;
    titleTimer = setInterval(function () {
      document.title = flip ? originalTitle : '💬 新消息 · 快聊';
      flip = !flip;
    }, 800);
  }
  function stopFlashTitle() {
    if (titleTimer) { clearInterval(titleTimer); titleTimer = null; }
    document.title = originalTitle;
  }
  // 页面聚焦时停止闪烁
  window.addEventListener('focus', stopFlashTitle);

  // ===== 弹窗 =====
  function showNotification(title, body, onClick) {
    var box = document.createElement('div');
    box.style.cssText = 'position:fixed;top:20px;right:20px;left:20px;max-width:360px;margin:0 auto;background:#fff;border-radius:16px;box-shadow:0 12px 36px rgba(0,0,0,.18);padding:14px 18px;z-index:2147483400;cursor:pointer;opacity:0;transform:translateY(-20px);transition:all .3s;border-left:4px solid #42a5f5;';
    box.innerHTML =
      '<div style="font-size:14px;font-weight:700;color:#0d3d6b;margin-bottom:4px;">' + title + '</div>' +
      '<div style="font-size:13px;color:#546e7a;line-height:1.5;word-break:break-word;">' + body + '</div>';
    box.onclick = function () {
      box.style.opacity = '0';
      box.style.transform = 'translateY(-20px)';
      setTimeout(function () { box.remove(); }, 300);
      stopFlashTitle();
      if (onClick) onClick();
    };
    document.body.appendChild(box);
    requestAnimationFrame(function () {
      box.style.opacity = '1';
      box.style.transform = 'translateY(0)';
    });
    setTimeout(function () {
      box.style.opacity = '0';
      box.style.transform = 'translateY(-20px)';
      setTimeout(function () { box.remove(); }, 300);
    }, 6000);
  }

  window.notifyNewMessage = function (title, body, onClick) {
    playBeep();
    vibrate();
    flashTitle();
    showNotification(title, body, onClick);
  };

  // ===== 轮询：检查新消息 =====
  function poll() {
    if (!localStorage.getItem('kuaichat_token')) return;
    // 只在"页面不可见"或"不在当前聊天页"时弹
    var isChatVisible = !$('chatScreen').classList.contains('hidden') || !$('groupChatScreen').classList.contains('hidden');
    authFetch('/api/friends').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return;
      d.friends.forEach(function (f) {
        if (f.unread > 0 && f.last_time && f.last_time > lastMsgId) {
          var isMuted = window.__mutedChats && window.__mutedChats.has(f.username);
          if (!isMuted && document.hidden) {
            window.notifyNewMessage('💬 ' + f.username, f.last_msg || '新消息', function () {
              if (window.openChat) window.openChat(f.username);
            });
          }
          lastMsgId = f.last_time;
        }
      });
    }).catch(function () {});
  }
  setInterval(poll, 8000);
  setTimeout(poll, 3000);

  // ===== 心跳：告诉后端"我还在线" =====
  setInterval(function () {
    if (!localStorage.getItem('kuaichat_token')) return;
    authFetch('/api/heartbeat', { method: 'POST' }).catch(function () {});
  }, 20000);

  // ===== 启动时：查"错过消息" =====
  setTimeout(function () {
    if (!localStorage.getItem('kuaichat_token')) return;
    authFetch('/api/missed_since_last_visit').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok || !d.count) return;
      var items = d.items || [];
      var listHtml = '';
      items.slice(0, 10).forEach(function (it) {
        if (it.type === 'private') {
          listHtml += '<div style="padding:8px 0;border-bottom:1px solid #f0f7fe;cursor:pointer;" data-peer="' + it.from + '">' +
            '<b style="color:#1976d2;">' + it.from + '</b> <span style="color:#90a4ae;font-size:12px;">(' + it.count + ' 条)</span><br>' +
            '<span style="color:#546e7a;font-size:13px;">' + (it.last || '[消息]') + '</span></div>';
        } else {
          listHtml += '<div style="padding:8px 0;border-bottom:1px solid #f0f7fe;">' +
            '<b style="color:#7e57c2;">📢 ' + it.name + '</b> <span style="color:#90a4ae;font-size:12px;">(' + it.count + ' 条)</span></div>';
        }
      });
      var t = $('modalTitle'), m = $('modalMessage');
      var bc = $('modalConfirm'), bx = $('modalCancel'), mi = $('modalIcon');
      if (!t) return;
      t.textContent = '你错过了 ' + d.count + ' 条消息';
      m.innerHTML = '<div style="max-height:300px;overflow-y:auto;font-size:13px;">' + listHtml + '</div>';
      m.style.display = 'block';
      var inp = $('modalInput'); if (inp) inp.classList.add('hidden');
      if (mi) { mi.className = 'modal-icon'; mi.innerHTML = '<i class="fas fa-envelope"></i>'; }
      bc.className = 'modal-btn confirm'; bc.textContent = '知道了'; bc.style.display = 'block';
      bc.onclick = function () { $('modalOverlay').classList.add('hidden'); };
      bx.style.display = 'none';
      $('modalOverlay').classList.remove('hidden');
      // 点私聊条目跳过去
      setTimeout(function () {
        m.querySelectorAll('[data-peer]').forEach(function (el) {
          el.onclick = function () {
            $('modalOverlay').classList.add('hidden');
            if (window.openChat) window.openChat(el.dataset.peer);
          };
        });
      }, 50);
    }).catch(function () {});
  }, 4000);

  // ===== "我"页面加开关 =====
  function injectMe() {
    if ($('nf_notify_cfg')) return true;
    var meView = $('viewMe');
    if (!meView) return false;
    var group = null, gs = meView.querySelectorAll('.setting-group');
    for (var i = 0; i < gs.length; i++) {
      var h3 = gs[i].querySelector('h3');
      if (h3 && h3.textContent.indexOf('新功能') >= 0) { group = gs[i]; break; }
    }
    if (!group) return false;
    if (!$('nf_notify_cfg')) {
      var r = document.createElement('div');
      r.className = 'setting-row';
      r.id = 'nf_notify_cfg';
      r.innerHTML = '<span><i class="fas fa-bell"></i>新消息声音提醒</span><span class="right" id="nf_snd_state">' + (soundEnabled ? '开' : '关') + '</span>';
      r.onclick = function () {
        soundEnabled = !soundEnabled;
        localStorage.setItem('kuaichat_notify_sound', soundEnabled ? 'on' : 'off');
        var st = document.getElementById('nf_snd_state');
        if (st) st.textContent = soundEnabled ? '开' : '关';
        toast(soundEnabled ? '已开启声音提醒' : '已关闭声音提醒');
      };
      group.appendChild(r);
    }
    return true;
  }
  var tries = 0;
  var timer = setInterval(function () { tries++; if (injectMe() || tries > 60) clearInterval(timer); }, 1000);
  injectMe();

  console.log('[nf11] 通知增强已加载');
})();
