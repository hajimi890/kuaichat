(function () {
  'use strict';
  function $(id) { return document.getElementById(id); }

  // ========== 拦截 "+" 按钮 ==========
  document.addEventListener('click', function (e) {
    var target = e.target.closest && e.target.closest('#uploadBtn, #groupUploadBtn');
    if (!target) return;
    var inPrivate = !$('chatScreen').classList.contains('hidden');
    var inGroup = !$('groupChatScreen').classList.contains('hidden');
    if (!inPrivate && !inGroup) return;
    e.stopImmediatePropagation();
    e.preventDefault();
    if (typeof window.showPopup !== 'function') return;

    if (target.id === 'groupUploadBtn') {
      window.showPopup([
        { key: 'image', label: '发送图片', icon: 'fa-image' },
        { key: 'video', label: '发送视频', icon: 'fa-video' },
        { key: 'file', label: '发送文件', icon: 'fa-paperclip' },
        { key: 'redpacket', label: '发红包', icon: 'fa-envelope-open-text' },
        { key: 'music', label: '发送音乐', icon: 'fa-music' },
        { key: 'vote', label: '发起群投票', icon: 'fa-poll' },
        { key: 'files', label: '群文件', icon: 'fa-folder-open' },
        { key: 'select', label: '多选消息', icon: 'fa-check-square' },
        { key: 'pinned', label: '查看置顶消息', icon: 'fa-thumbtack' }
      ], function (k) {
        if (k === 'vote' && window.openCreateVote) window.openCreateVote();
        else if (k === 'files' && window.openGroupFiles) window.openGroupFiles();
        else if (k === 'select' && window.toggleSelectMode) window.toggleSelectMode();
        else if (k === 'pinned' && window.openPinnedMessages) window.openPinnedMessages();
        else if (k === 'redpacket' && window.openSendPacket) window.openSendPacket();
        else if (k === 'music' && window.pickMusic) window.pickMusic('group');
        else if (typeof pickMedia === 'function') pickMedia(k, 'group');
      });
    } else {
      window.showPopup([
        { key: 'image', label: '发送图片', icon: 'fa-image' },
        { key: 'video', label: '发送视频', icon: 'fa-video' },
        { key: 'file', label: '发送文件', icon: 'fa-paperclip' },
        { key: 'gift', label: '送礼物', icon: 'fa-gift' },
        { key: 'redpacket', label: '发红包', icon: 'fa-envelope-open-text' },
        { key: 'share', label: '分享纯文本', icon: 'fa-share-alt' },
        { key: 'music', label: '发送音乐', icon: 'fa-music' },
        { key: 'location', label: '共享位置', icon: 'fa-map-marker-alt' },
        { key: 'select', label: '多选消息', icon: 'fa-check-square' },
        { key: 'pinned', label: '查看置顶消息', icon: 'fa-thumbtack' },
        { key: 'unread', label: '跳到未读', icon: 'fa-arrow-down' }
      ], function (k) {
        if (k === 'location' && window.shareLocation) window.shareLocation();
        else if (k === 'select' && window.toggleSelectMode) window.toggleSelectMode();
        else if (k === 'pinned' && window.openPinnedMessages) window.openPinnedMessages();
        else if (k === 'unread' && window.jumpToUnread) window.jumpToUnread();
        else if (k === 'redpacket' && window.openSendPacket) window.openSendPacket();
        else if (k === 'gift' && window.openGiftPicker) window.openGiftPicker();
        else if (k === 'share' && window.openSharePicker) window.openSharePicker();
        else if (k === 'music' && window.pickMusic) window.pickMusic('private');
        else if (typeof pickMedia === 'function') pickMedia(k, 'private');
      });
    }
  }, true);

  // ========== 长按消息菜单 ==========
  document.addEventListener('contextmenu', function (e) {
    var row = e.target.closest && e.target.closest('.msg-row');
    if (!row) return;
    var mid = row.dataset.mid; if (!mid) return;
    e.preventDefault();
    if (typeof window.showPopup !== 'function') return;
    window.showPopup([
      { key: 'copy', label: '复制', icon: 'fa-copy' },
      { key: 'favorite', label: '收藏', icon: 'fa-star' },
      { key: 'pin', label: '置顶', icon: 'fa-thumbtack' },
      { key: 'forward', label: '转发', icon: 'fa-share' },
      { key: 'select', label: '多选', icon: 'fa-check-square' }
    ], function (k) {
      var b = row.querySelector('.msg-bubble');
      var text = b ? (b.innerText || '') : '';
      if (k === 'copy') { try { navigator.clipboard.writeText(text); if (window.showToast) window.showToast('已复制'); } catch (_) {} }
      else if (k === 'favorite' && window.favoriteMessage) window.favoriteMessage(mid);
      else if (k === 'pin' && window.pinMessage) window.pinMessage(mid);
      else if (k === 'forward' && window.forwardMessage) window.forwardMessage(mid);
      else if (k === 'select' && window.toggleSelectMode) window.toggleSelectMode();
    });
  }, true);

  var pressTimer = null;
  document.addEventListener('touchstart', function (e) {
    var row = e.target.closest && e.target.closest('.msg-row');
    if (!row || !row.dataset.mid) return;
    pressTimer = setTimeout(function () {
      var ev = new MouseEvent('contextmenu', { bubbles: true, cancelable: true });
      row.dispatchEvent(ev);
    }, 600);
  }, { passive: true });
  document.addEventListener('touchend', function () { if (pressTimer) clearTimeout(pressTimer); });
  document.addEventListener('touchmove', function () { if (pressTimer) clearTimeout(pressTimer); });

  // ========== 我页面注入新功能分组 ==========
  function injectMeButtons() {
    if ($('nf_qrcode')) return true;
    var meView = $('viewMe'); if (!meView) return false;
    var wrap = document.createElement('div');
    wrap.className = 'setting-group';
    wrap.innerHTML = '<h3>新功能</h3>' +
      '<div class="setting-row" id="nf_qrcode"><span><i class="fas fa-qrcode"></i>我的二维码</span><span class="right">></span></div>' +
      '<div class="setting-row" id="nf_scan"><span><i class="fas fa-camera"></i>扫一扫加好友</span><span class="right">></span></div>' +
      '<div class="setting-row" id="nf_fav"><span><i class="fas fa-star"></i>我的收藏</span><span class="right">></span></div>' +
      '<div class="setting-row" id="nf_mentions"><span><i class="fas fa-at"></i>未读 @</span><span class="right">></span></div>' +
      '<div class="setting-row" id="nf_vis"><span><i class="fas fa-eye"></i>朋友圈可见范围</span><span class="right">></span></div>';
    var anchor = $('editProfileBtn') || $('settingsBtn') || $('openShopBtn') || $('petEntryBtn');
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(wrap, anchor);
    else meView.appendChild(wrap);
    $('nf_qrcode').onclick = window.openMyQrcode || function () { alert('未加载'); };
    $('nf_scan').onclick = window.openScanAdd || function () { alert('未加载'); };
    $('nf_fav').onclick = window.openFavorites || function () { alert('未加载'); };
    $('nf_mentions').onclick = window.openMentions || function () { alert('未加载'); };
    $('nf_vis').onclick = window.openMomentVisibility || function () { alert('未加载'); };
    return true;
  }

  var tries = 0;
  var timer = setInterval(function () {
    tries++;
    if (injectMeButtons() || tries > 60) clearInterval(timer);
  }, 1000);
  injectMeButtons();

  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('.tab-item');
    if (t && t.dataset && t.dataset.tab === 'me') {
      setTimeout(injectMeButtons, 100); setTimeout(injectMeButtons, 500); setTimeout(injectMeButtons, 1500);
    }
  }, true);

  if (window.refreshOnlineStatus) setInterval(window.refreshOnlineStatus, 5000);

  console.log('[nf4] 已加载');
})();
