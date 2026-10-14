(function () {
  function $(id) { return document.getElementById(id); }

  var GAMES = {
    'game2048Btn':   { id: '2048',        name: '2048',       icon: 'fa-th',            desc: '合并数字',   color: 'linear-gradient(135deg,#f6a623,#e68a00)' },
    'gameSnakeBtn':  { id: 'snake',       name: '贪吃蛇',     icon: 'fa-staff-snake',   desc: '经典玩法',   color: 'linear-gradient(135deg,#66bb6a,#388e3c)' },
    'gameMemoryBtn': { id: 'memory',      name: '翻牌记忆',   icon: 'fa-clone',         desc: '找出配对',   color: 'linear-gradient(135deg,#42a5f5,#1e88e5)' },
    'gameRpsBtn':    { id: 'minesweeper', name: '扫雷',       icon: 'fa-bomb',          desc: '挖出所有雷', color: 'linear-gradient(135deg,#ab47bc,#7b1fa2)' },
    'gameGomokuBtn': { id: 'gomoku',      name: '五子棋',     icon: 'fa-circle',        desc: '人机对战',   color: 'linear-gradient(135deg,#5c6bc0,#3949ab)' }
  };

  function beautify() {
    var vg = $('viewGames');
    if (!vg) return false;
    if (vg.dataset.nf7v2 === '1') return true;

    var found = 0;
    Object.keys(GAMES).forEach(function (btnId) {
      var card = $(btnId);
      if (!card) return;
      found++;
      var g = GAMES[btnId];

      if (card.dataset.nf7wrapped === '1') return;
      card.dataset.nf7wrapped = '1';

      var wrapper = document.createElement('div');
      wrapper.style.cssText = 'border-radius:20px;overflow:hidden;box-shadow:0 10px 24px rgba(30,136,229,.18);background:#fff;';
      card.parentNode.insertBefore(wrapper, card);
      wrapper.appendChild(card);

      card.style.cssText = 'background:' + g.color + ';padding:22px 12px 18px;color:#fff;text-align:center;cursor:pointer;position:relative;border-radius:0;box-shadow:none;border:none;';
      card.innerHTML =
        '<div style="width:56px;height:56px;margin:0 auto 12px;border-radius:18px;background:rgba(255,255,255,.25);display:flex;align-items:center;justify-content:center;box-shadow:0 4px 12px rgba(0,0,0,.15);">' +
          '<i class="fas ' + g.icon + '" style="font-size:26px;color:#fff;"></i>' +
        '</div>' +
        '<div style="font-size:16px;font-weight:700;letter-spacing:.3px;">' + g.name + '</div>' +
        '<div style="font-size:11px;opacity:.85;margin-top:4px;">' + g.desc + '</div>';

      // 如果是扫雷，替换掉旧 onclick
      if (g.id === 'minesweeper') {
        card.onclick = function () {
          if (typeof window.startMinesweeper === 'function') {
            var gs = document.getElementById('gameScreen');
            var gc = document.getElementById('gameBody');
            var gt = document.getElementById('gameTitle');
            var main = document.getElementById('mainScreen');
            if (!gs || !gc) return alert('游戏容器不存在');
            if (main) main.classList.add('hidden');
            gs.classList.remove('hidden');
            if (gt) gt.textContent = '扫雷';
            gc.innerHTML = '';
            gc.style.cssText = 'flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;overflow:auto;background:#f5faff;padding:16px;';
            window.startMinesweeper(gc);
          } else {
            alert('扫雷模块未加载，请刷新页面');
          }
        };
      }

      var rankBtn = document.createElement('button');
      rankBtn.type = 'button';
      rankBtn.style.cssText = 'width:100%;background:#fff;color:#1976d2;border:none;border-top:1px solid #f0f7fe;padding:11px;font-size:13px;font-weight:600;cursor:pointer;font-family:inherit;display:flex;align-items:center;justify-content:center;gap:6px;';
      rankBtn.innerHTML = '<i class="fas fa-trophy" style="color:#ff9800;"></i>排行榜';
      rankBtn.onclick = function (e) {
        e.stopPropagation();
        if (window.openGameRank) window.openGameRank(g.id, g.name);
        else alert('排行榜未加载');
      };
      wrapper.appendChild(rankBtn);
    });

    if (found === 5) {
      vg.dataset.nf7v2 = '1';
      console.log('[nf7] 5 卡片美化完成');
    }
    return found === 5;
  }

  var tries = 0;
  var timer = setInterval(function () {
    tries++;
    if (beautify() || tries > 60) clearInterval(timer);
  }, 800);
  beautify();

  document.addEventListener('click', function (e) {
    var t = e.target.closest && e.target.closest('.tab-item');
    if (t && t.dataset && t.dataset.tab === 'games') {
      setTimeout(beautify, 100);
      setTimeout(beautify, 800);
    }
  }, true);
})();
