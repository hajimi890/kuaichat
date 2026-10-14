// =========================================================
// 扫雷
// =========================================================
(function () {
  function toast(m, e) { if (window.showToast) return window.showToast(m, e); alert(m); }

  var ROWS = 9, COLS = 9, MINES = 10;

  window.startMinesweeper = function (container) {
    container.innerHTML = '';
    var board = [], revealed = [], flagged = [];
    var gameOver = false, startTime = 0, timerId = null, revealCount = 0, flagCount = 0;

    var wrap = document.createElement('div');
    wrap.style.cssText = 'width:100%;max-width:380px;padding:12px;';
    wrap.innerHTML =
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;padding:0 6px;">' +
        '<div style="font-size:14px;color:#0d3d6b;">⏱ <b id="msTime" style="color:#42a5f5;">0:00</b></div>' +
        '<div style="font-size:14px;color:#0d3d6b;">💣 <b id="msFlag" style="color:#e53935;">0</b> / ' + MINES + '</div>' +
        '<button id="msReset" style="background:linear-gradient(135deg,#42a5f5,#1e88e5);color:#fff;border:none;border-radius:10px;padding:8px 14px;font-size:12px;font-weight:600;cursor:pointer;font-family:inherit;">重开</button>' +
      '</div>' +
      '<div id="msGrid" style="display:grid;grid-template-columns:repeat(' + COLS + ',1fr);gap:3px;background:#d4e4f7;padding:6px;border-radius:12px;user-select:none;touch-action:manipulation;"></div>';
    container.appendChild(wrap);
    var grid = wrap.querySelector('#msGrid');

    function init() {
      board = []; revealed = []; flagged = [];
      gameOver = false; startTime = Date.now(); revealCount = 0; flagCount = 0;
      for (var r = 0; r < ROWS; r++) {
        board.push([]); revealed.push([]); flagged.push([]);
        for (var c = 0; c < COLS; c++) { board[r].push(0); revealed[r].push(false); flagged[r].push(false); }
      }
      var placed = 0;
      while (placed < MINES) {
        var rr = Math.floor(Math.random() * ROWS), cc = Math.floor(Math.random() * COLS);
        if (board[rr][cc] !== -1) { board[rr][cc] = -1; placed++; }
      }
      for (var r2 = 0; r2 < ROWS; r2++) for (var c2 = 0; c2 < COLS; c2++) {
        if (board[r2][c2] === -1) continue;
        var cnt = 0;
        for (var dr = -1; dr <= 1; dr++) for (var dc = -1; dc <= 1; dc++) {
          var nr = r2 + dr, nc = c2 + dc;
          if (nr >= 0 && nr < ROWS && nc >= 0 && nc < COLS && board[nr][nc] === -1) cnt++;
        }
        board[r2][c2] = cnt;
      }
      grid.innerHTML = '';
      for (var r3 = 0; r3 < ROWS; r3++) for (var c3 = 0; c3 < COLS; c3++) {
        var cell = document.createElement('div');
        cell.className = 'ms-cell';
        cell.dataset.r = r3; cell.dataset.c = c3;
        cell.style.cssText = 'aspect-ratio:1;background:linear-gradient(135deg,#e3f2fd,#bbdefb);border-radius:8px;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;color:#0d3d6b;cursor:pointer;';
        grid.appendChild(cell);
      }
      grid.querySelectorAll('.ms-cell').forEach(function (cell) {
        cell.addEventListener('click', onLeft);
        cell.addEventListener('contextmenu', onRight);
        var pressTimer;
        cell.addEventListener('touchstart', function (e) { pressTimer = setTimeout(function () { onRight(e); }, 500); }, { passive: true });
        cell.addEventListener('touchend', function () { clearTimeout(pressTimer); });
        cell.addEventListener('touchmove', function () { clearTimeout(pressTimer); });
      });
      if (timerId) clearInterval(timerId);
      timerId = setInterval(updateTime, 500);
      updateTime();
    }

    function updateTime() {
      var elapsed = Math.floor((Date.now() - startTime) / 1000);
      var m = Math.floor(elapsed / 60), s = elapsed % 60;
      var tEl = document.getElementById('msTime');
      if (tEl) tEl.textContent = m + ':' + (s < 10 ? '0' + s : s);
    }

    function updateFlag() {
      var fEl = document.getElementById('msFlag');
      if (fEl) fEl.textContent = flagCount;
    }

    function onLeft(e) {
      if (gameOver) return;
      var cell = e.currentTarget;
      var r = parseInt(cell.dataset.r), c = parseInt(cell.dataset.c);
      if (flagged[r][c]) return;
      // 如果已经挖开，做"双击判断"
      if (revealed[r][c]) {
        var num = board[r][c];
        if (num <= 0) return;
        // 数周围旗子
        var flags = 0;
        for (var dr = -1; dr <= 1; dr++) for (var dc = -1; dc <= 1; dc++) {
          if (!dr && !dc) continue;
          var nr = r + dr, nc = c + dc;
          if (nr >= 0 && nr < ROWS && nc >= 0 && nc < COLS && flagged[nr][nc]) flags++;
        }
        // 旗子数等于数字 → 展开其他格
        if (flags === num) {
          for (var dr2 = -1; dr2 <= 1; dr2++) for (var dc2 = -1; dc2 <= 1; dc2++) {
            if (!dr2 && !dc2) continue;
            var nr2 = r + dr2, nc2 = c + dc2;
            if (nr2 >= 0 && nr2 < ROWS && nc2 >= 0 && nc2 < COLS && !revealed[nr2][nc2] && !flagged[nr2][nc2]) {
              reveal(nr2, nc2);
            }
          }
        }
        return;
      }
      reveal(r, c);
    }

    function onRight(e) {
      e.preventDefault();
      if (gameOver) return;
      var cell = e.currentTarget;
      var r = parseInt(cell.dataset.r), c = parseInt(cell.dataset.c);
      if (revealed[r][c]) return;
      flagged[r][c] = !flagged[r][c];
      flagCount += flagged[r][c] ? 1 : -1;
      cell.style.background = flagged[r][c] ? 'linear-gradient(135deg,#ef5350,#e53935)' : 'linear-gradient(135deg,#e3f2fd,#bbdefb)';
      cell.innerHTML = flagged[r][c] ? '<i class="fas fa-flag" style="color:#fff;"></i>' : '';
      updateFlag();
    }

    function reveal(r, c) {
      if (r < 0 || r >= ROWS || c < 0 || c >= COLS) return;
      if (revealed[r][c] || flagged[r][c]) return;
      revealed[r][c] = true;
      revealCount++;
      var cell = grid.querySelector('.ms-cell[data-r="' + r + '"][data-c="' + c + '"]');
      if (!cell) return;
      cell.style.background = '#fff';
      if (board[r][c] === -1) {
        cell.innerHTML = '<i class="fas fa-bomb" style="color:#e53935;"></i>';
        cell.style.background = '#ffebee';
        return lose();
      }
      if (board[r][c] > 0) {
        var colors = ['', '#1976d2', '#388e3c', '#d32f2f', '#7b1fa2', '#f57c00', '#5d4037', '#546e7a', '#000'];
        cell.innerHTML = '<span style="color:' + colors[board[r][c]] + ';">' + board[r][c] + '</span>';
      } else {
        for (var dr = -1; dr <= 1; dr++) for (var dc = -1; dc <= 1; dc++) if (dr || dc) reveal(r + dr, c + dc);
      }
      if (revealCount === ROWS * COLS - MINES) win();
    }

    function lose() {
      gameOver = true;
      clearInterval(timerId);
      grid.querySelectorAll('.ms-cell').forEach(function (cell) {
        var r = parseInt(cell.dataset.r), c = parseInt(cell.dataset.c);
        if (board[r][c] === -1 && !revealed[r][c]) {
          cell.style.background = '#ffcdd2';
          cell.innerHTML = '<i class="fas fa-bomb" style="color:#e53935;"></i>';
        }
      });
      setTimeout(function () { toast('💥 踩到雷了'); }, 200);
    }

    function win() {
      gameOver = true;
      clearInterval(timerId);
      var elapsed = Math.floor((Date.now() - startTime) / 1000);
      if (window.submitGameScore) window.submitGameScore('minesweeper', elapsed, '用时' + elapsed + '秒').catch(function () {});
      setTimeout(function () { toast('🎉 通关！用时 ' + elapsed + ' 秒'); }, 200);
    }

    wrap.querySelector('#msReset').onclick = init;
    init();
  };
  console.log('[minesweeper] 已加载');
})();

// =========================================================
// 步数（摇一摇）
// =========================================================
(function () {
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

  var STEP_COUNT = 0, pendingDelta = 0, lastStepTime = 0;
  var lastMotion = { x: 0, y: 0, z: 0 };
  var STEP_THRESHOLD = 12, STEP_COOLDOWN = 280;

  window.openSteps = function () {
    authFetch('/api/steps/today').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      STEP_COUNT = d.steps || 0;
      renderSteps();
    });
  };

  function renderSteps() {
    var t = $('modalTitle'), m = $('modalMessage');
    var bc = $('modalConfirm'), bx = $('modalCancel'), mi = $('modalIcon');
    if (!t) return;
    t.textContent = '今日步数';
    m.innerHTML =
      '<div style="text-align:center;padding:10px 0;">' +
        '<div style="font-size:64px;line-height:1;color:#42a5f5;font-weight:800;" id="stepCount">' + STEP_COUNT + '</div>' +
        '<div style="font-size:13px;color:#90a4ae;margin-top:8px;">步</div>' +
        '<div style="font-size:12px;color:#90a4ae;margin-top:12px;line-height:1.7;">摇一摇手机 → 自动 +1 步<br><span style="color:#ff9800;">⚠️ 需授权运动与方向访问</span></div>' +
        '<div style="display:flex;gap:8px;justify-content:center;margin-top:16px;">' +
          '<button type="button" id="stepStartBtn" style="background:linear-gradient(135deg,#42a5f5,#1e88e5);color:#fff;border:none;border-radius:12px;padding:10px 20px;font-weight:600;cursor:pointer;font-family:inherit;">开始计步</button>' +
          '<button type="button" id="stepRankBtn" style="background:#fff3e0;color:#e65100;border:1px solid #ffcc80;border-radius:12px;padding:10px 20px;font-weight:600;cursor:pointer;font-family:inherit;">排行榜</button>' +
        '</div>' +
      '</div>';
    m.style.display = 'block';
    var inp = $('modalInput'); if (inp) inp.classList.add('hidden');
    if (mi) { mi.className = 'modal-icon'; mi.innerHTML = '<i class="fas fa-shoe-prints"></i>'; }
    bc.className = 'modal-btn confirm'; bc.textContent = '关闭'; bc.style.display = 'block';
    bc.onclick = function () { flushPending(); $('modalOverlay').classList.add('hidden'); };
    bx.style.display = 'none';
    $('modalOverlay').classList.remove('hidden');
    setTimeout(function () {
      var sb = $('stepStartBtn'); if (sb) sb.onclick = startMotion;
      var rb = $('stepRankBtn'); if (rb) rb.onclick = openStepRank;
    }, 50);
  }

  function openStepRank() {
    authFetch('/api/steps/rank').then(function (r) { return r.json(); }).then(function (d) {
      if (!d.ok) return toast(d.error, true);
      var html = '<div style="text-align:center;margin-bottom:12px;font-size:13px;color:#546e7a;">我的步数：<b style="color:#42a5f5;">' + d.my_steps + '</b>' + (d.my_rank ? ' · 第 ' + d.my_rank + ' 名' : '') + '</div><div style="max-height:360px;overflow-y:auto;">';
      if (!d.list.length) html += '<div style="text-align:center;color:#90a4ae;padding:30px;">还没有人记录</div>';
      else d.list.forEach(function (it) {
        var medal = it.rank === 1 ? '🥇' : it.rank === 2 ? '🥈' : it.rank === 3 ? '🥉' : ' ' + it.rank + '.';
        var isMe = it.username === (localStorage.getItem('kuaichat_username') || '');
        html += '<div style="display:flex;align-items:center;gap:10px;padding:10px;border-bottom:1px solid #f0f7fe;' + (isMe ? 'background:#e3f2fd;border-radius:8px;' : '') + '">' +
          '<div style="font-size:16px;font-weight:700;color:#ff9800;min-width:36px;">' + medal + '</div>' +
          '<div style="flex:1;font-size:14px;color:#0d3d6b;font-weight:600;">' + it.username + (isMe ? ' (我)' : '') + '</div>' +
          '<div style="font-size:15px;font-weight:700;color:#42a5f5;">' + it.steps + ' 步</div></div>';
      });
      html += '</div>';
      $('modalMessage').innerHTML = html;
      $('modalIcon').innerHTML = '<i class="fas fa-trophy" style="color:#ffc107;"></i>';
      $('modalTitle').textContent = '步数排行榜';
      $('modalConfirm').textContent = '关闭';
      $('modalCancel').style.display = 'none';
    });
  }

  function flushPending() {
    if (pendingDelta <= 0) return;
    var delta = pendingDelta; pendingDelta = 0;
    authFetch('/api/steps/add', { method: 'POST', body: JSON.stringify({ delta: delta }) }).catch(function () {});
  }

  // ===== 计步核心：低通滤波 + 峰值检测 + 频率过滤 =====
  var motionHistory = [];       // 记录最近的加速度幅值
  var lastPeakTime = 0;         // 上次峰值时间
  var lastPeakValue = 0;        // 上次峰值幅值
  var STEP_FREQ_MIN = 0.7;      // 最小步频 Hz（慢走）
  var STEP_FREQ_MAX = 3.5;      // 最大步频 Hz（快跑）
  var PEAK_THRESHOLD = 10.5;    // 峰值阈值（重力单位 ~9.8）
  var FREQ_WINDOW = 3000;       // 用最近 3 秒的数据算频率

  function onMotion(e) {
    var acc = e.accelerationIncludingGravity || e.acceleration;
    if (!acc) return;
    // 1. 计算加速度矢量模长（去掉重力常数 9.8 的影响，用高通的近似）
    var mag = Math.sqrt((acc.x || 0) ** 2 + (acc.y || 0) ** 2 + (acc.z || 0) ** 2);
    // 2. 高通：去掉重力分量（取模长与 9.8 的差值的绝对值）
    var dyn = Math.abs(mag - 9.8);

    var now = Date.now();
    // 3. 记录历史
    motionHistory.push({ t: now, v: dyn });
    // 只保留最近 FREQ_WINDOW 毫秒
    while (motionHistory.length && motionHistory[0].t < now - FREQ_WINDOW) {
      motionHistory.shift();
    }

    // 4. 峰值检测：dyn 超过阈值，且距离上次峰值足够时间
    if (dyn > PEAK_THRESHOLD) {
      // 太近（<200ms）的忽略，避免一次动作算多次
      if (now - lastPeakTime < 200) return;
      // 计算"当前步频"——取最近两次峰值的间隔
      var interval = now - lastPeakTime;
      var freq = interval > 0 ? 1000 / interval : 0;
      // 5. 频率过滤：只有步频在 0.7~3.5 Hz 之间才算一步
      if (lastPeakTime === 0 || (freq >= STEP_FREQ_MIN && freq <= STEP_FREQ_MAX)) {
        lastPeakTime = now;
        STEP_COUNT++;
        pendingDelta++;
        var el = document.getElementById('stepCount');
        if (el) el.textContent = STEP_COUNT;
        if (pendingDelta >= 5) flushPending();
      } else {
        // 频率异常，只更新峰值时间不计数
        lastPeakTime = now;
      }
    }
  }

  function startMotion() {
    if (typeof DeviceMotionEvent === 'undefined') return toast('本机/浏览器不支持运动传感器', true);
    if (typeof DeviceMotionEvent.requestPermission === 'function') {
      DeviceMotionEvent.requestPermission().then(function (state) {
        if (state === 'granted') {
          window.addEventListener('devicemotion', onMotion, { passive: true });
          toast('✅ 计步已开启，摇一摇试试');
        } else toast('未授权', true);
      }).catch(function (err) { toast('授权失败：' + err.message, true); });
    } else {
      window.addEventListener('devicemotion', onMotion, { passive: true });
      toast('✅ 计步已开启，摇一摇试试');
    }
  }

  function injectMe() {
    if (document.getElementById('nf_steps')) return true;
    var meView = document.getElementById('viewMe');
    if (!meView) return false;
    var group = null, gs = meView.querySelectorAll('.setting-group');
    for (var i = 0; i < gs.length; i++) {
      var h3 = gs[i].querySelector('h3');
      if (h3 && h3.textContent.indexOf('新功能') >= 0) { group = gs[i]; break; }
    }
    if (!group) return false;
    var r = document.createElement('div');
    r.className = 'setting-row';
    r.id = 'nf_steps';
    r.innerHTML = '<span><i class="fas fa-shoe-prints"></i>今日步数</span><span class="right">></span>';
    r.onclick = window.openSteps;
    group.appendChild(r);
    return true;
  }
  var tries = 0;
  var timer = setInterval(function () { tries++; if (injectMe() || tries > 60) clearInterval(timer); }, 1000);
  injectMe();
  console.log('[nf8-steps] 步数已加载');
})();
