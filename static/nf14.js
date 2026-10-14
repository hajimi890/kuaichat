(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }
  function toast(m, e) { if (window.showToast) return window.showToast(m, e); alert(m); }

  // ===== 1. 隐藏"我"页面里所有高级分组 =====
  function hideAdvancedGroups() {
    var meView = $('viewMe');
    if (!meView) return;
    meView.querySelectorAll('.setting-group').forEach(function (g) {
      var h3 = g.querySelector('h3');
      if (!h3) return;
      var t = h3.textContent || '';
      if (t.indexOf('新功能') >= 0 || t.indexOf('等级特权') >= 0 || t.indexOf('我的积分') >= 0 || t.indexOf('邀请好友') >= 0) {
        g.style.display = 'none';
      }
    });
  }

  // ===== 2. 往 settingsScreen 里注入"新功能"分组 =====
  function injectSettingsGroups() {
    var ss = $('settingsScreen');
    if (!ss) return false;
    // 找"账号"分组后面 / "退出登录"按钮前，插入
    if ($('nf_settings_advanced')) return true;

    // 找到 settingsScreen 里 scroll 容器
    var scroll = ss.querySelector('div[style*="overflow-y"]') || ss;
    var logout = $('logoutBtn2');

    var wrap = document.createElement('div');
    wrap.id = 'nf_settings_advanced';
    wrap.innerHTML = '' +
      '<div class="setting-group">' +
        '<h3>常用</h3>' +
        '<div class="setting-row" data-fn="openDailyTasks"><span><i class="fas fa-tasks"></i>每日任务</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openAchievements"><span><i class="fas fa-medal"></i>我的成就</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openMyScores"><span><i class="fas fa-trophy"></i>我的游戏成绩</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openSteps"><span><i class="fas fa-shoe-prints"></i>今日步数</span><span class="right">›</span></div>' +
      '</div>' +
      '<div class="setting-group">' +
        '<h3>账号与安全</h3>' +
        '<div class="setting-row" data-fn="openPatternSet"><span><i class="fas fa-th"></i>九宫格密码锁</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openFrameShop"><span><i class="fas fa-hat-cowboy"></i>头像挂件商店</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openFeedback"><span><i class="fas fa-comment-dots"></i>意见反馈</span><span class="right">›</span></div>' +
      '</div>' +
      '<div class="setting-group">' +
        '<h3>社交</h3>' +
        '<div class="setting-row" data-fn="openMyQrcode"><span><i class="fas fa-qrcode"></i>我的二维码</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openScanAdd"><span><i class="fas fa-camera"></i>扫一扫加好友</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openFavorites"><span><i class="fas fa-star"></i>我的收藏</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openMentions"><span><i class="fas fa-at"></i>未读 @</span><span class="right">›</span></div>' +
        '<div class="setting-row" data-fn="openMomentVisibility"><span><i class="fas fa-eye"></i>朋友圈可见范围</span><span class="right">›</span></div>' +
      '</div>' +
      '<div class="setting-group">' +
        '<h3>消息通知</h3>' +
        '<div class="setting-row" id="nf14_sound_row"><span><i class="fas fa-bell"></i>新消息声音提醒</span><span class="right" id="nf14_sound_state">' + (localStorage.getItem('kuaichat_notify_sound') === 'off' ? '关' : '开') + '</span></div>' +
      '</div>';

    // 插入到"退出登录"按钮前
    if (logout && logout.parentNode) {
      logout.parentNode.insertBefore(wrap, logout);
    } else {
      scroll.appendChild(wrap);
    }

    // 绑定功能点击
    wrap.querySelectorAll('[data-fn]').forEach(function (row) {
      row.onclick = function () {
        var fn = window[row.dataset.fn];
        if (typeof fn === 'function') {
          fn();
        } else {
          toast('功能未加载：' + row.dataset.fn, true);
        }
      };
    });

    // 声音开关
    var snd = $('nf14_sound_row');
    if (snd) {
      snd.onclick = function () {
        var on = localStorage.getItem('kuaichat_notify_sound') !== 'off';
        localStorage.setItem('kuaichat_notify_sound', on ? 'off' : 'on');
        var st = $('nf14_sound_state');
        if (st) st.textContent = on ? '关' : '开';
        toast(on ? '已关闭声音提醒' : '已开启声音提醒');
      };
    }

    console.log('[nf14] 设置页注入完成');
    return true;
  }

  // ===== 3. 定时执行 =====
  var tries = 0;
  var timer = setInterval(function () {
    tries++;
    hideAdvancedGroups();
    injectSettingsGroups();
    if (tries > 60) clearInterval(timer);
  }, 1000);

  hideAdvancedGroups();
  injectSettingsGroups();

  // 切 tab 时重跑
  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('.tab-item');
    if (t && t.dataset && t.dataset.tab === 'me') {
      setTimeout(hideAdvancedGroups, 100);
      setTimeout(hideAdvancedGroups, 800);
    }
  }, true);

  console.log('[nf14] 我页面简化已加载');
})();
