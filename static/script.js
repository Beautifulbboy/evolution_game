const RES_ORDER = ['amino_acid', 'lipid', 'sulfur', 'minerals', 'ancient_gene'];
const RES_COLORS = {'amino_acid': '#29b6f6', 'lipid': '#ffee58', 'sulfur': '#ff7043', 'minerals': '#bdbdbd', 'ancient_gene': '#d500f9'};

// 初始化资源DOM
const resContainer = document.getElementById('resources-container');
RES_ORDER.forEach(key => {
    const nameStyle = key === 'ancient_gene' ? 'color:#e040fb; font-weight:bold;' : 'color:#ccc;';
    // 注意：TRANS 在 HTML 中被定义为全局变量，所以这里可以直接访问
    resContainer.innerHTML += `
        <div class="res-row" style="margin-bottom:5px;">
            <span style="font-size:12px; ${nameStyle}">${TRANS[key]}</span>
            <div class="bar-box" style="height:16px;">
                <div id="bar-${key}" class="bar-fill" style="background:${RES_COLORS[key]}"></div>
                <div id="txt-${key}" class="bar-text">0 / 100</div>
            </div>
        </div>`;
});

// 启动循环
setInterval(tick, 1000);

// API 交互函数
function tick() { fetch('/tick').then(r=>r.json()).then(render); }
function gather(res) { fetch('/gather/'+res, {method:'POST'}).then(r=>r.json()).then(render); }
function travel(zone) { fetch('/travel/'+zone, {method:'POST'}).then(r=>r.json()).then(render); }
function craft(key) { fetch('/craft/'+key, {method:'POST'}).then(r=>r.json()).then(render); }
function startBattle() { fetch('/battle/start', {method:'POST'}).then(r=>r.json()).then(render); }
function combatAction(act) { fetch('/battle/'+act, {method:'POST'}).then(r=>r.json()).then(render); }

let lastLogMsg = '';

function render(data) {
    const p = data.player;
    const eff = data.eff_stats;
    const recipes = data.recipes;
    
    // 1. 机体状态
    document.getElementById('hp-bar').style.width = (eff.hp / eff.max_hp * 100) + '%';
    document.getElementById('hp-text').innerText = `${Math.floor(eff.hp)} / ${eff.max_hp}`;
    document.getElementById('dna-bar').style.width = p.mutation_bar + '%';
    document.getElementById('dna-text').innerText = `DNA: ${Math.floor(p.mutation_bar)}%`;
    
    document.getElementById('s-def').innerText = eff.defense.toFixed(1);
    document.getElementById('s-heat').innerText = eff.heat_res.toFixed(1);
    document.getElementById('s-spd').innerText = eff.gather_speed.toFixed(1);
    document.getElementById('s-reg').innerText = eff.hp_regen.toFixed(1);
    document.getElementById('cap-display').innerText = `Cap: ${eff.storage_cap}`;
    document.getElementById('atk-dmg').innerText = (eff.gather_speed * 5).toFixed(1);

    // 2. 模式切换
    const normalEnv = document.getElementById('current-env');
    const combatUi = document.getElementById('combat-interface');
    const evolUi = document.getElementById('evolution-interface');
    const gatherArea = document.getElementById('gather-area');
    const combatBtnArea = document.getElementById('combat-area');

    if (p.in_combat) {
        normalEnv.style.display = 'none';
        evolUi.style.display = 'none';
        combatUi.style.display = 'flex';
        
        const bossPct = (p.boss_hp / BOSS_CONFIG.max_hp) * 100;
        document.getElementById('boss-bar').style.width = bossPct + '%';
        document.getElementById('boss-text').innerText = `${Math.floor(p.boss_hp)} / ${BOSS_CONFIG.max_hp}`;
    } else {
        normalEnv.style.display = 'flex';
        evolUi.style.display = 'flex';
        combatUi.style.display = 'none';
        
        const zConf = ZONE_CONFIG[p.current_zone].info;
        normalEnv.style.background = zConf.color;
        document.getElementById('env-title').innerText = zConf.name;
        
        let dText = zConf.desc;
        if(zConf.damage_val > 0) dText += ` [⚠️ 伤害: -${zConf.damage_val}/s]`;
        if(zConf.mutation_rate > 0) dText += ` [☢️ 辐射: +${zConf.mutation_rate}%/s]`;
        document.getElementById('env-desc').innerText = dText;

        // 深渊特殊逻辑
        if (p.current_zone === 'abyss') {
            if (p.flags.boss_defeated) {
                gatherArea.style.display = 'block';
                combatBtnArea.style.display = 'block';
                gatherArea.innerHTML = '';
                zConf.resources.forEach(r => {
                    gatherArea.innerHTML += `<button class="gather-btn" onclick="gather('${r}')">采集 ${TRANS[r]}</button>`;
                });
            } else {
                gatherArea.style.display = 'none';
                combatBtnArea.style.display = 'block';
            }
        } else {
            gatherArea.style.display = 'block';
            combatBtnArea.style.display = 'none';
            gatherArea.innerHTML = '';
            zConf.resources.forEach(r => {
                gatherArea.innerHTML += `<button class="gather-btn" onclick="gather('${r}')">采集 ${TRANS[r]}</button>`;
            });
        }
    }
    
    if (p.flags.boss_defeated) {
        const desc = document.getElementById('zone-desc-abyss');
        if(desc) desc.innerText = "BOSS: 已击败 (可采集: 远古基因)";
    }

    // 3. Buff
    const buffArea = document.getElementById('buff-area');
    buffArea.innerHTML = p.active_buffs.length ? '' : '<span style="color:#555; font-size:11px;">状态稳定</span>';
    p.active_buffs.forEach(b => {
        let tooltip = '';
        for(const [k, v] of Object.entries(b.effect)) {
            const sign = v > 0 ? '+' : '';
            // 这里使用单斜杠 \n
            tooltip += `${TRANS[k]||k} ${sign}${v}`;
        }
        // data-tooltip 这里加上 .trim() 去掉最后一个换行符
        buffArea.innerHTML += `<span class="buff-tag" style="background:${b.color}" data-tooltip="${tooltip.trim()}">${b.name} (${Math.ceil(b.remaining)}s)</span>`;
    });

    // 4. 资源
    RES_ORDER.forEach(key => {
        const val = p.inventory[key];
        const cap = eff.storage_cap;
        document.getElementById('txt-'+key).innerText = `${Math.floor(val)} / ${cap}`;
        document.getElementById('bar-'+key).style.width = Math.min(100, (val/cap)*100) + '%';
    });

    // 5. 进化序列
    const grid = document.getElementById('craft-grid');
    grid.innerHTML = '';
    for (const [key, r] of Object.entries(recipes)) {
        let costStr = '';
        for (const [k, v] of Object.entries(r.next_cost)) costStr += `${TRANS[k]} x${v} `;
        let statStr = '';
        for (const [k, v] of Object.entries(r.base_stats)) statStr += `${TRANS[k]||k} +${v} `;
        const cardStyle = key === 'apex_predator' ? 'border: 1px solid #e040fb; box-shadow: 0 0 5px #e040fb;' : '';

        grid.innerHTML += `
        <div class="craft-card" style="${cardStyle}">
            <div>
                <div style="display:flex; justify-content:space-between; color:#81c784; font-weight:bold; font-size:13px;">
                    <span>${r.name}</span><span style="background:#333; padding:1px 4px; font-size:11px; color:#ffd54f;">Lv.${r.current_level}</span>
                </div>
                <div style="color:#aaa; font-size:11px; margin:5px 0;">${r.desc}</div>
            </div>
            <div>
                <div style="background:#111; padding:5px; border-radius:4px; margin-bottom:5px; font-size:11px; color:#bdbdbd;">
                    <div>需: ${costStr}</div>
                    <div style="color:#66bb6a; margin-top:2px;">益: ${statStr}</div>
                </div>
                <button class="craft-btn" onclick="craft('${key}')">进化升级</button>
            </div>
        </div>`;
    }

    // 6. 日志
    if (data.log && data.log.msg !== lastLogMsg) {
        const logBox = document.getElementById('game-log');
        const time = new Date().toLocaleTimeString().split(' ')[0];
        let cls = 'log-sys';
        if (data.log.type === 'dmg') cls = 'log-dmg';
        if (data.log.type === 'get') cls = 'log-get';
        if (data.log.type === 'mut') cls = 'log-mut';
        if (data.log.type === 'combat') cls = 'log-combat';
        logBox.innerHTML = `<div class="log-line"><span style="color:#555">[${time}]</span> <span class="${cls}" style="${cls==='log-mut'?'color:#e040fb':''}">${data.log.msg}</span></div>` + logBox.innerHTML;
        lastLogMsg = data.log.msg;
    }
}