(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  function toast(m, e) { if (window.showToast) return window.showToast(m, e); alert(m); }
  function authFetch(url, opts) {
    opts = opts || {};
    var h = opts.headers || {};
    var t = localStorage.getItem('kuaichat_token') || '';
    if (t) h['Authorization'] = 'Bearer ' + t;
    if (opts.body && typeof opts.body === 'string' && !h['Content-Type']) h['Content-Type'] = 'application/json';
    opts.headers = h;
    return fetch(url, opts);
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - base64String.length % 4) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var raw = atob(base64);
    var arr = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
    return arr;
  }

  async function enablePush() {
    if (!('serviceWorker' in navigator)) return toast('浏览器不支持 Service Worker', true);
    if (!('PushManager' in window)) return toast('浏览器不支持推送', true);

    // 1. 注册 SW
    var reg;
    try {
      reg = await navigator.serviceWorker.register('/static/sw.js', { scope: '/' });
    } catch (e) {
      return toast('SW 注册失败：' + e.message, true);
    }

    // 2. 请求通知权限
    var perm = await Notification.requestPermission();
    if (perm !== 'granted') return toast('你拒绝了通知权限', true);

    // 3. 拿公钥
    var pk = await authFetch('/api/push/public_key').then(function (r) { return r.json(); });
    if (!pk.ok || !pk.publicKey) return toast('服务器没配公钥', true);

    // 4. 订阅
    var existing = await reg.pushManager.getSubscription();
    var sub = existing;
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(pk.publicKey)
      });
    }

    // 5. 发给后端
    await authFetch('/api/push/subscribe', {
      method: 'POST',
      body: JSON.stringify({ subscription: sub.toJSON() })
    });

    toast('✅ 推送已开启');
  }

  async function disablePush() {
    if (!('serviceWorker' in navigator)) return;
    var reg = await navigator.serviceWorker.getRegistration('/static/sw.js');
    if (!reg) return toast('未注册');
    var sub = await reg.pushManager.getSubscription();
    if (sub) {
      await authFetch('/api/push/unsubscribe', {
        method: 'POST',
        body: JSON.stringify({ endpoint: sub.endpoint })
      });
      await sub.unsubscribe();
    }
    toast('已关闭推送');
  }

  async function testPush() {
    var r = await authFetch('/api/push/test', { method: 'POST' });
    var d = await r.json();
    if (d.ok) toast('✅ 测试推送已发送（sent=' + d.sent + '）');
    else toast(d.error || '失败', true);
  }

  async function isSubscribed() {
    if (!('serviceWorker' in navigator)) return false;
    var reg = await navigator.serviceWorker.getRegistration('/static/sw.js');
    if (!reg) return false;
    var sub = await reg.pushManager.getSubscription();
    return !!sub;
  }

  window.openPushSettings = async function () {
    var enabled = await isSubscribed();
    var t = $('modalTitle'), m = $('modalMessage');
    var bc = $('modalConfirm'), bx = $('modalCancel'), mi = $('modalIcon');
    if (!t) return;
    t.textContent = '消息推送';
    m.innerHTML =
      '<div style="font-size:13px;color:#546e7a;line-height:1.9;padding:8px 4px;">' +
        '<div>开启后，App 关掉/切后台时，新消息会以系统通知形式弹出。</div>' +
        '<div style="margin-top:12px;padding:10px;background:#f5faff;border-radius:10px;">' +
          '<div style="font-size:12px;color:#90a4ae;">当前状态</div>' +
          '<div style="font-size:15px;font-weight:700;color:' + (enabled ? '#1bbf8b' : '#90a4ae') + ';margin-top:4px;">' + (enabled ? '✅ 已开启' : '⭕ 未开启') + '</div>' +
        '</div>' +
      '</div>';
    m.style.display = 'block';
    var inp = $('modalInput'); if (inp) inp.classList.add('hidden');
    if (mi) { mi.className = 'modal-icon'; mi.innerHTML = '<i class="fas fa-bell"></i>'; }
    bc.className = 'modal-btn confirm';
    bc.textContent = enabled ? '关闭推送' : '开启推送';
    bc.style.display = 'block';
    bx.textContent = '测试一下';
    bx.style.display = 'block';
    $('modalOverlay').classList.remove('hidden');

    bc.onclick = async function () {
      if (enabled) await disablePush();
      else await enablePush();
      $('modalOverlay').classList.add('hidden');
    };
    bx.onclick = async function () {
      await testPush();
    };
  };

  // "我"页面注入"消息推送"
  function injectMe() {
    if ($('nf_push')) return true;
    var meView = $('viewMe');
    if (!meView) return false;
    var group = null, gs = meView.querySelectorAll('.setting-group');
    for (var i = 0; i < gs.length; i++) {
      var h3 = gs[i].querySelector('h3');
      if (h3 && h3.textContent.indexOf('新功能') >= 0) { group = gs[i]; break; }
    }
    if (!group) return false;
    if (!$('nf_push')) {
      var r = document.createElement('div');
      r.className = 'setting-row';
      r.id = 'nf_push';
      r.innerHTML = '<span><i class="fas fa-bell"></i>消息推送</span><span class="right">></span>';
      r.onclick = window.openPushSettings;
      group.appendChild(r);
    }
    return true;
  }
  var tries = 0;
  var timer = setInterval(function () { tries++; if (injectMe() || tries > 60) clearInterval(timer); }, 1000);
  injectMe();

  // 启动时：如果已经开过，重新绑定（SW 会自动续订）
  navigator.serviceWorker && navigator.serviceWorker.register('/static/sw.js', { scope: '/' }).then(function () {
    console.log('[nf9] SW 已注册');
  }).catch(function (e) { console.log('[nf9] SW err', e); });

  console.log('[nf9] 推送模块已加载');
})();
