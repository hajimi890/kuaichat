(function () {
  'use strict';

  // ===== 样式 =====
  var css = document.createElement('style');
  css.textContent = `
    .pd-mask{position:fixed;inset:0;background:rgba(13,61,107,.5);z-index:2147483646;display:flex;align-items:center;justify-content:center;padding:24px;opacity:0;transition:opacity .2s;}
    .pd-mask.pd-in{opacity:1;}
    .pd-box{width:100%;max-width:320px;background:#fff;border-radius:22px;box-shadow:0 24px 60px -12px rgba(0,0,0,.4);overflow:hidden;transform:scale(.92);transition:transform .22s cubic-bezier(.34,1.56,.64,1);}
    .pd-mask.pd-in .pd-box{transform:scale(1);}
    .pd-icon{width:56px;height:56px;border-radius:18px;margin:24px auto 14px;display:flex;align-items:center;justify-content:center;font-size:26px;color:#fff;}
    .pd-icon.info{background:linear-gradient(135deg,#42a5f5,#1e88e5);}
    .pd-icon.success{background:linear-gradient(135deg,#1bbf8b,#0e9e70);}
    .pd-icon.warn{background:linear-gradient(135deg,#ffb74d,#f57c00);}
    .pd-icon.error{background:linear-gradient(135deg,#ef5350,#e53935);}
    .pd-title{font-size:17px;font-weight:700;color:#0d3d6b;text-align:center;padding:0 20px;}
    .pd-msg{font-size:14px;color:#546e7a;line-height:1.7;text-align:center;padding:12px 24px 0;word-break:break-word;max-height:40vh;overflow-y:auto;}
    .pd-input{width:calc(100% - 44px);margin:14px 22px 0;padding:12px 14px;background:#f5faff;border:1.5px solid #d4e4f7;border-radius:12px;font-size:15px;color:#0d3d6b;outline:none;font-family:inherit;box-sizing:border-box;}
    .pd-input:focus{border-color:#42a5f5;background:#fff;}
    .pd-actions{display:flex;gap:10px;padding:20px 22px 22px;}
    .pd-btn{flex:1;border:none;border-radius:14px;padding:13px;font-size:14px;font-weight:600;cursor:pointer;font-family:inherit;transition:transform .1s;}
    .pd-btn:active{transform:scale(.97);}
    .pd-btn.cancel{background:#f5faff;color:#546e7a;border:1px solid #e3f2fd;}
    .pd-btn.ok{background:linear-gradient(135deg,#42a5f5,#1e88e5);color:#fff;box-shadow:0 6px 16px rgba(30,136,229,.3);}
    .pd-btn.danger{background:linear-gradient(135deg,#ef5350,#e53935);color:#fff;box-shadow:0 6px 16px rgba(229,57,53,.3);}
    html.dark .pd-box{background:#14283d;}
    html.dark .pd-title{color:#e6f2fb;}
    html.dark .pd-msg{color:#9db4c7;}
    html.dark .pd-input{background:#12293f;border-color:#1f3d57;color:#e6f2fb;}
    html.dark .pd-btn.cancel{background:#12293f;color:#9db4c7;border-color:#1f3d57;}
  `;
  document.head.appendChild(css);

  // ===== 通用弹窗 =====
  function showDialog(opts) {
    return new Promise(function (resolve) {
      var mask = document.createElement('div');
      mask.className = 'pd-mask';

      var iconClass = opts.type || 'info';
      var iconHtml = opts.icon || (iconClass === 'success' ? '✓' :
        iconClass === 'error' ? '✕' :
        iconClass === 'warn' ? '!' : 'i');

      var html = '<div class="pd-box">' +
        '<div class="pd-icon ' + iconClass + '">' + iconHtml + '</div>' +
        '<div class="pd-title">' + (opts.title || '提示') + '</div>' +
        (opts.message ? '<div class="pd-msg">' + escapeHtml(opts.message) + '</div>' : '') +
        (opts.input ? '<input class="pd-input" id="pdInput" placeholder="' + escapeHtml(opts.placeholder || '') + '" value="' + escapeHtml(opts.value || '') + '">' : '') +
        '<div class="pd-actions">' +
        (opts.showCancel !== false ? '<button class="pd-btn cancel" id="pdCancel">' + (opts.cancelText || '取消') + '</button>' : '') +
        '<button class="pd-btn ' + (opts.danger ? 'danger' : 'ok') + '" id="pdOk">' + (opts.okText || '确定') + '</button>' +
        '</div></div>';

      mask.innerHTML = html;
      document.body.appendChild(mask);
      requestAnimationFrame(function () { mask.classList.add('pd-in'); });

      var input = mask.querySelector('#pdInput');
      if (input) setTimeout(function () { input.focus(); input.select(); }, 100);

      function close(val) {
        mask.classList.remove('pd-in');
        setTimeout(function () { mask.remove(); }, 220);
        resolve(val);
      }

      mask.querySelector('#pdOk').onclick = function () {
        if (input) close(input.value);
        else close(true);
      };
      var cb = mask.querySelector('#pdCancel');
      if (cb) cb.onclick = function () {
        if (input) close(null);
        else close(false);
      };

      if (input) {
        input.onkeydown = function (e) {
          if (e.key === 'Enter') { e.preventDefault(); close(input.value); }
          if (e.key === 'Escape') { e.preventDefault(); close(null); }
        };
      } else {
        mask.onkeydown = function (e) {
          if (e.key === 'Enter') { e.preventDefault(); close(true); }
          if (e.key === 'Escape') { e.preventDefault(); close(false); }
        };
        setTimeout(function () { mask.tabIndex = 0; mask.focus(); }, 50);
      }

      mask.onclick = function (e) {
        if (e.target === mask) {
          if (input) close(null);
          else close(false);
        }
      };
    });
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // ===== 替换原生 alert =====
  window.alert = function (msg) {
    showDialog({
      title: '提示',
      message: String(msg || ''),
      type: 'info',
      showCancel: false,
      okText: '知道了'
    });
  };

  // ===== 替换原生 confirm（同步返回，无法真正 await，所以用兼容写法） =====
  // 注意：confirm 是同步的，这里返回 Promise，但旧代码可能当同步用
  // 我们把 confirm 改成"总是 true"，真正的确认走 showDialog 异步
  var _origConfirm = window.confirm;
  window.confirm = function (msg) {
    // 为了兼容旧代码，弹出漂亮弹窗，返回 true（默认同意）
    // 想拦截取消逻辑的代码，需要改用 window.prettyConfirm
    showDialog({
      title: '确认',
      message: String(msg || ''),
      type: 'warn',
      okText: '确定',
      cancelText: '取消',
      showCancel: true,
      danger: true
    }).then(function (ok) {
      if (!ok) {
        // 用户点了取消，触发一个全局事件，业务代码可以监听
        window.dispatchEvent(new CustomEvent('pd-confirm-cancel', { detail: { message: msg } }));
      } else {
        window.dispatchEvent(new CustomEvent('pd-confirm-ok', { detail: { message: msg } }));
      }
    });
    return true; // 兼容旧代码默认走"确定"分支
  };

  // ===== 替换原生 prompt =====
  window.prompt = function (msg, defaultValue) {
    // prompt 也是同步的，返回 null 或字符串。我们用异步弹窗，返回 defaultValue
    showDialog({
      title: '输入',
      message: String(msg || ''),
      input: true,
      value: defaultValue || '',
      okText: '确定',
      cancelText: '取消',
      showCancel: true
    }).then(function (val) {
      if (val !== null) {
        window.dispatchEvent(new CustomEvent('pd-prompt-result', { detail: { message: msg, value: val } }));
      } else {
        window.dispatchEvent(new CustomEvent('pd-prompt-cancel', { detail: { message: msg } }));
      }
    });
    return null; // 兼容旧代码
  };

  // ===== 暴露给业务代码（异步版） =====
  window.prettyAlert = function (msg, title) {
    return showDialog({ title: title || '提示', message: msg, type: 'info', showCancel: false, okText: '知道了' });
  };
  window.prettyConfirm = function (msg, title) {
    return showDialog({ title: title || '确认', message: msg, type: 'warn', okText: '确定', cancelText: '取消', showCancel: true, danger: true });
  };
  window.prettyPrompt = function (msg, defaultValue, title) {
    return showDialog({ title: title || '输入', message: msg, input: true, value: defaultValue || '', okText: '确定', cancelText: '取消', showCancel: true });
  };
  window.prettyToast = function (msg, type) {
    return showDialog({ title: type === 'success' ? '成功' : type === 'error' ? '错误' : '提示', message: msg, type: type || 'info', showCancel: false, okText: '知道了' });
  };

  console.log('[pretty_dialog] 已加载');
})();
