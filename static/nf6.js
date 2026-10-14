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

  // ===== 九宫格锁 =====
  var PATTERN_POINTS = [];
  var PATTERN_MODE = 'set'; // 'set' 或 'verify'

  function showPatternLock(mode, onSuccess) {
    PATTERN_MODE = mode;
    PATTERN_POINTS = [];
    var overlay = $('patternLockOverlay');
    if (!overlay) {
      overlay = document.createElement('div');
      overlay.id = 'patternLockOverlay';
      overlay.style.cssText = 'position:fixed;inset:0;background:linear-gradient(135deg,#e3f2fd 0%,#bbdefb 50%,#e1f5fe 100%);z-index:2147483600;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:20px;';
      overlay.innerHTML =
        '<div style="width:100%;max-width:340px;background:#fff;border-radius:24px;box-shadow:0 20px 60px rgba(30,136,229,.25);padding:28px 20px 24px;text-align:center;">' +
        '<div style="width:56px;height:56px;border-radius:18px;margin:0 auto 14px;background:linear-gradient(135deg,#42a5f5,#1e88e5);display:flex;align-items:center;justify-content:center;color:#fff;font-size:24px;box-shadow:0 8px 20px rgba(30,136,229,.35);">' +
        '<i class="fas fa-lock"></i></div>' +
        '<div style="color:#0d3d6b;font-size:19px;font-weight:700;margin-bottom:6px;" id="patternTitle">绘制密码</div>' +
        '<div style="color:#90a4ae;font-size:13px;margin-bottom:20px;" id="patternSub">连接至少 4 个点</div>' +
        '<canvas id="patternCanvas" width="300" height="300" style="background:#f5faff;border-radius:20px;border:1.5px solid #e3f2fd;touch-action:none;display:block;margin:0 auto;"></canvas>' +
        '<div style="color:#ef5350;font-size:13px;margin-top:14px;height:20px;font-weight:500;" id="patternError"></div>' +
        '</div>';
      document.body.appendChild(overlay);

      var canvas = overlay.querySelector('#patternCanvas');
      var ctx = canvas.getContext('2d');
      var isDrawing = false;
      var dots = [];
      var dotR = 18;

      for (var i = 0; i < 9; i++) {
        var r = Math.floor(i / 3), c = i % 3;
        dots.push({ x: 50 + c * 100, y: 50 + r * 100, idx: i + 1 });
      }

      function draw() {
        ctx.clearRect(0, 0, 300, 300);
        // 连线
        ctx.strokeStyle = '#42a5f5';
        ctx.lineWidth = 6;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        if (PATTERN_POINTS.length > 0) {
          ctx.beginPath();
          PATTERN_POINTS.forEach(function (idx, i) {
            var d = dots[idx - 1];
            if (i === 0) ctx.moveTo(d.x, d.y);
            else ctx.lineTo(d.x, d.y);
          });
          ctx.stroke();
        }
        // 点
        dots.forEach(function (d) {
          var selected = PATTERN_POINTS.indexOf(d.idx) >= 0;
          ctx.beginPath();
          ctx.arc(d.x, d.y, selected ? dotR + 4 : dotR, 0, Math.PI * 2);
          ctx.fillStyle = selected ? '#42a5f5' : '#d4e4f7';
          ctx.fill();
          if (selected) {
            ctx.beginPath();
            ctx.arc(d.x, d.y, 7, 0, Math.PI * 2);
            ctx.fillStyle = '#fff';
            ctx.fill();
          }
        });
      }
      draw();

      function getPos(e) {
        var rect = canvas.getBoundingClientRect();
        var scaleX = 300 / rect.width;
        var scaleY = 300 / rect.height;
        var t = e.touches ? e.touches[0] : e;
        return { x: (t.clientX - rect.left) * scaleX, y: (t.clientY - rect.top) * scaleY };
      }
      function findNearestDot(pos) {
        for (var i = 0; i < dots.length; i++) {
          var d = dots[i];
          var dist = Math.sqrt((pos.x - d.x) ** 2 + (pos.y - d.y) ** 2);
          if (dist < dotR + 18) return d.idx;
        }
        return -1;
      }
      function onStart(e) {
        e.preventDefault();
        PATTERN_POINTS = [];
        isDrawing = true;
        var idx = findNearestDot(getPos(e));
        if (idx > 0) { PATTERN_POINTS.push(idx); draw(); }
      }
      function onMove(e) {
        if (!isDrawing) return;
        e.preventDefault();
        var idx = findNearestDot(getPos(e));
        if (idx > 0 && PATTERN_POINTS.indexOf(idx) < 0) {
          PATTERN_POINTS.push(idx);
          draw();
        }
      }
      function onEnd(e) {
        if (!isDrawing) return;
        isDrawing = false;
        if (PATTERN_POINTS.length >= 4) {
          handlePatternDone();
        } else if (PATTERN_POINTS.length > 0) {
          overlay.querySelector('#patternError').textContent = '至少连接 4 个点';
          setTimeout(function () {
            PATTERN_POINTS = [];
            draw();
            overlay.querySelector('#patternError').textContent = '';
          }, 900);
        }
      }

      canvas.addEventListener('mousedown', onStart);
      canvas.addEventListener('mousemove', onMove);
      canvas.addEventListener('mouseup', onEnd);
      canvas.addEventListener('touchstart', onStart, { passive: false });
      canvas.addEventListener('touchmove', onMove, { passive: false });
      canvas.addEventListener('touchend', onEnd);

      // 暴露 draw 供外部调用
      window.__patternRedraw = draw;
    }

    // 重置 UI
    overlay.querySelector('#patternTitle').textContent = mode === 'set' ? '绘制密码' : '解锁';
    overlay.querySelector('#patternSub').textContent = mode === 'set' ? '连接至少 4 个点，记住顺序' : '连接你的密码以继续';
    overlay.querySelector('#patternError').textContent = '';
    PATTERN_POINTS = [];
    if (window.__patternRedraw) window.__patternRedraw();
    overlay.style.display = 'flex';

    window.__patternSuccessCb = onSuccess;
  }

  function handlePatternDone() {
    var pattern = PATTERN_POINTS.join('');
    if (PATTERN_MODE === 'set') {
      authFetch('/api/pattern/set', {
        method: 'POST',
        body: JSON.stringify({ pattern: pattern })
      }).then(function(r) { return r.json(); }).then(function(d) {
        if (d.ok) {
          toast('✅ 密码已设置');
          $('patternLockOverlay').style.display = 'none';
          if (window.__patternSuccessCb) window.__patternSuccessCb();
        } else toast(d.error || '失败', true);
      });
    } else {
      authFetch('/api/pattern/verify', {
        method: 'POST',
        body: JSON.stringify({ pattern: pattern })
      }).then(function(r) { return r.json(); }).then(function(d) {
        if (d.ok) {
          $('patternLockOverlay').style.display = 'none';
          if (window.__patternSuccessCb) window.__patternSuccessCb();
        } else {
          $('patternError').textContent = d.error || '密码错误';
          setTimeout(function () {
            PATTERN_POINTS = [];
            $('patternError').textContent = '';
            if (window.__patternRedraw) window.__patternRedraw();
          }, 800);
        }
      });
    }
  }

  window.showPatternLock = showPatternLock;

  // ===== 设置九宫格密码 =====
  window.openPatternSet = function() {
    authFetch('/api/pattern/status').then(function(r) { return r.json(); }).then(function(d) {
      if (d.enabled) {
        if (confirm('你已经开启了密码锁，是否关闭？')) {
          authFetch('/api/pattern/disable', { method: 'POST' }).then(function() {
            toast('已关闭密码锁');
          });
        }
      } else {
        showPatternLock('set', function() {});
      }
    });
  };

  // ===== "我"页面注入 =====
  function injectMe() {
    if ($('nf_pattern')) return true;
    var meView = $('viewMe');
    if (!meView) return false;
    var group = null;
    var gs = meView.querySelectorAll('.setting-group');
    for (var i = 0; i < gs.length; i++) {
      var h3 = gs[i].querySelector('h3');
      if (h3 && h3.textContent.indexOf('新功能') >= 0) { group = gs[i]; break; }
    }
    if (!group) return false;
    if (!$('nf_pattern')) {
      var r = document.createElement('div');
      r.className = 'setting-row';
      r.id = 'nf_pattern';
      r.innerHTML = '<span><i class="fas fa-th"></i>九宫格密码锁</span><span class="right">></span>';
      r.onclick = window.openPatternSet;
      group.appendChild(r);
    }
    return true;
  }
  var tries = 0;
  var timer = setInterval(function() { tries++; if (injectMe() || tries > 60) clearInterval(timer); }, 1000);
  injectMe();

  console.log('[nf6] 九宫格锁已加载');
})();

// ===== 启动时检查密码锁 =====
(function() {
  function checkPatternLock() {
    if (!localStorage.getItem('kuaichat_token')) return;
    // 本次会话已解锁
    if (sessionStorage.getItem('pd_unlocked') === '1') return;
    authFetch('/api/pattern/status').then(function(r) { return r.json(); }).then(function(d) {
      if (d.ok && d.enabled) {
        window.showPatternLock('verify', function() {
          sessionStorage.setItem('pd_unlocked', '1');
        });
      }
    }).catch(function() {});
  }
  // 延迟 2 秒（等页面加载好）
  setTimeout(checkPatternLock, 2000);
})();

// ===== PC 端屏幕适应 =====
(function() {
  function applyPC() {
    var isPC = window.innerWidth >= 768;
    var style = document.getElementById('pcAdaptStyle');
    if (!style) {
      style = document.createElement('style');
      style.id = 'pcAdaptStyle';
      document.head.appendChild(style);
    }
    if (isPC) {
      style.textContent = `
        body { padding: 20px !important; }
        .app { max-width: 520px !important; height: 90vh !important; max-height: 900px !important; }
        @media (min-width: 1200px) {
          .app { max-width: 600px !important; }
        }
        .msg-bubble { font-size: 15px !important; }
        .user-item { padding: 12px 16px !important; }
      `;
    } else {
      style.textContent = '';
    }
  }
  applyPC();
  window.addEventListener('resize', applyPC);
  console.log('[nf6-pc] PC 适配已启用');
})();

// ===== 网页内消息弹窗 =====
(function() {
  var lastMsgId = 0;
  var lastGroupMsgId = 0;
  var pollTimer = null;

  function showInPageNotification(title, body, onClick) {
    var box = document.createElement('div');
    box.style.cssText = 'position:fixed;top:20px;right:20px;max-width:320px;background:#fff;border-radius:16px;box-shadow:0 12px 36px rgba(0,0,0,.18);padding:14px 18px;z-index:2147483400;cursor:pointer;opacity:0;transform:translateX(30px);transition:all .3s;';
    box.innerHTML = '<div style="font-size:14px;font-weight:700;color:#0d3d6b;margin-bottom:4px;">' + title + '</div>' +
      '<div style="font-size:13px;color:#546e7a;line-height:1.5;word-break:break-word;">' + body + '</div>';
    box.onclick = function() {
      box.style.opacity = '0';
      box.style.transform = 'translateX(30px)';
      setTimeout(function() { box.remove(); }, 300);
      if (onClick) onClick();
    };
    document.body.appendChild(box);
    requestAnimationFrame(function() {
      box.style.opacity = '1';
      box.style.transform = 'translateX(0)';
    });
    setTimeout(function() {
      box.style.opacity = '0';
      box.style.transform = 'translateX(30px)';
      setTimeout(function() { box.remove(); }, 300);
    }, 5000);
  }
  window.showInPageNotification = showInPageNotification;

  function poll() {
    if (!localStorage.getItem('kuaichat_token')) return;
    // 私聊未读
    authFetch('/api/friends').then(function(r) { return r.json(); }).then(function(d) {
      if (!d.ok) return;
      d.friends.forEach(function(f) {
        if (f.unread > 0 && f.last_time && f.last_time > lastMsgId) {
          var isMuted = window.__mutedChats && window.__mutedChats.has(f.username);
          if (!isMuted && document.hidden) {
            showInPageNotification('💬 ' + f.username, f.last_msg || '新消息', function() {
              if (window.openChat) window.openChat(f.username);
            });
          }
          lastMsgId = f.last_time;
        }
      });
    }).catch(function() {});
  }
  // 每 15 秒检查一次
  pollTimer = setInterval(poll, 15000);
  console.log('[nf6-notify] 消息弹窗已启用');
})();
