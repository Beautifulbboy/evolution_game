const RES_ORDER = ['amino_acid', 'lipid', 'sulfur', 'minerals', 'ancient_gene'];
const RES_COLORS = {'amino_acid': '#29b6f6', 'lipid': '#ffee58', 'sulfur': '#ff7043', 'minerals': '#bdbdbd', 'ancient_gene': '#d500f9'};

const resContainer = document.getElementById('resources-container');
RES_ORDER.forEach(key => {
    const nameStyle = key === 'ancient_gene' ? 'color:#e040fb; font-weight:bold;' : 'color:#ccc;';
    resContainer.innerHTML += `
        <div class="res-row" style="margin-bottom:5px;">
            <span style="font-size:12px; ${nameStyle}">${TRANS[key]}</span>
            <div class="bar-box" style="height:16px;">
                <div id="bar-${key}" class="bar-fill" style="background:${RES_COLORS[key]}"></div>
                <div id="txt-${key}" class="bar-text">0 / 100</div>
            </div>
        </div>`;
});

// Tab 切换逻辑
function switchTab(tabName, btn) {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
    document.getElementById('tab-' + tabName).classList.add('active');
    btn.classList.add('active');
}

setInterval(tick, 1000);
function tick() { fetch('/tick').then(r=>r.json()).then(render); }
function gather(res) { fetch('/gather/'+res, {method:'POST'}).then(r=>r.json()).then(render); }
function travel(zone) { fetch('/travel/'+zone, {method:'POST'}).then(r=>r.json()).then(render); }
function craft(key) { fetch('/craft/'+key, {method:'POST'}).then(r=>r.json()).then(render); }
function buyAuto(key) { fetch('/buy_auto/'+key, {method:'POST'}).then(r=>r.json()).then(render); }
function startBattle() { fetch('/battle/start', {method:'POST'}).then(r=>r.json()).then(render); }
function combatAction(act) { fetch('/battle/'+act, {method:'POST'}).then(r=>r.json()).then(render); }
function openShop() { fetch('/shop/open', {method:'POST'}).then(r=>r.json()).then(render); }
function selectShop(idx) { fetch('/shop/select/'+idx, {method:'POST'}).then(r=>r.json()).then(render); }

let lastLogMsg = '';

function render(data) {
    const p = data.player;
    const eff = data.eff_stats;
    const recipes = data.recipes;
    const autoInfo = data.auto_info;
    
    // 1. 状态
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

    // 2. 环境模式
    const normalEnv = document.getElementById('current-env');
    const combatUi = document.getElementById('combat-interface');
    const mainUi = document.getElementById('main-interface');
    
    if (p.in_combat) {
        normalEnv.style.display = 'none';
        mainUi.style.display = 'none';
        combatUi.style.display = 'flex';
        const bossPct = (p.boss_hp / BOSS_CONFIG.max_hp) * 100;
        document.getElementById('boss-bar').style.width = bossPct + '%';
        document.getElementById('boss-text').innerText = `${Math.floor(p.boss_hp)} / ${BOSS_CONFIG.max_hp}`;
    } else {
        normalEnv.style.display = 'flex';
        mainUi.style.display = 'flex';
        combatUi.style.display = 'none';
        
        const zConf = ZONE_CONFIG[p.current_zone].info;
        normalEnv.style.background = zConf.color;
        document.getElementById('env-title').innerText = zConf.name;
        document.getElementById('env-desc').innerText = zConf.desc + (zConf.damage_val > 0 ? ` [⚠️ 伤害: -${zConf.damage_val}/s]` : "");

        const gatherArea = document.getElementById('gather-area');
        const combatArea = document.getElementById('combat-area');
        const zoneCont = document.getElementById('zone-container');
        
        if (p.current_zone === 'abyss') {
            if (p.flags.boss_defeated) {
                gatherArea.style.display = 'block';
                combatArea.style.display = 'block';
            } else {
                gatherArea.style.display = 'none';
                combatArea.style.display = 'block';
            }
        } else {
            gatherArea.style.display = 'block';
            combatArea.style.display = 'none';
        }
        
        if(gatherArea.style.display !== 'none') {
            gatherArea.innerHTML = '';
            zConf.resources.forEach(r => {
                gatherArea.innerHTML += `<button class="gather-btn" onclick="gather('${r}')">采集 ${TRANS[r]}</button>`;
            });
        }
        
        zoneCont.innerHTML = '';
        for(const [k, z] of Object.entries(ZONE_CONFIG)) {
            zoneCont.innerHTML += `<button class="travel-btn" onclick="travel('${k}')"><b>${z.info.name}</b><br><small style="color:#90a4ae">${z.res_str}</small></button>`;
        }
    }

    // 3. Buff 渲染
    const buffArea = document.getElementById('buff-area');
    buffArea.innerHTML = p.active_buffs.length ? '' : '<span style="color:#555; font-size:11px;">状态稳定</span>';
    p.active_buffs.forEach(b => {
        let tooltip = '';
        for(const [k, v] of Object.entries(b.effect)) {
            let sign = v > 0 ? '+' : '';
            tooltip += `${TRANS[k]||k} ${sign}${v} `;
        }
        buffArea.innerHTML += `<span class="buff-tag" style="background:${b.color}" data-tooltip="${tooltip.trim()}">${b.name} (${Math.ceil(b.remaining)}s)</span>`;
    });

    // 4. 永久基因
    const permArea = document.getElementById('perm-area');
    if (p.perms.length > 0) {
        permArea.innerHTML = '';
        p.perms.forEach(b => {
            let tooltip = '';
            for(const [k, v] of Object.entries(b.effect)) {
                let sign = v > 0 ? '+' : '';
                tooltip += `${TRANS[k]||k} ${sign}${v} `;
            }
            permArea.innerHTML += `<span class="buff-tag" style="background:#222; border:1px solid ${b.color}; color:${b.color};" data-tooltip="${tooltip.trim()}">${b.name}</span>`;
        });
    } else {
        permArea.innerHTML = '<span style="color:#666; font-size:12px;">(暂无)</span>';
    }

    // 5. 资源
    RES_ORDER.forEach(key => {
        const val = p.inventory[key];
        const cap = eff.storage_cap;
        document.getElementById('txt-'+key).innerText = `${Math.floor(val)} / ${cap}`;
        document.getElementById('bar-'+key).style.width = Math.min(100, (val/cap)*100) + '%';
    });

    // --- 6. 标签页内容 ---
    
    // Tab 1: 进化
    const craftGrid = document.getElementById('craft-grid');
    craftGrid.innerHTML = '';
    for(const [k, r] of Object.entries(recipes)) {
         let costStr = '';
         for(const [ck, cv] of Object.entries(r.next_cost)) costStr += `${TRANS[ck]} x${cv} `;
         let statStr = '';
         for(const [sk, sv] of Object.entries(r.base_stats)) statStr += `${TRANS[sk]||sk} +${sv} `;
         
         const cardStyle = k === 'apex_predator' ? 'border: 1px solid #e040fb; box-shadow: 0 0 5px #e040fb;' : '';
         
         craftGrid.innerHTML += `
         <div class="craft-card" style="${cardStyle}">
            <div>
                <div style="font-weight:bold; color:#81c784; font-size:13px;">${r.name} <span style="font-size:10px; color:#aaa;">Lv.${r.current_level}</span></div>
                <div style="color:#aaa; font-size:11px; margin:5px 0;">${r.desc}</div>
            </div>
            <div>
                <div style="background:#111; padding:5px; border-radius:4px; margin-bottom:5px; font-size:11px; color:#bdbdbd;">
                    <div>需: ${costStr}</div>
                    <div style="color:#66bb6a; margin-top:2px;">益: ${statStr}</div>
                </div>
                <button class="craft-btn" onclick="craft('${k}')">进化</button>
            </div>
         </div>`;
    }

    // Tab 2: 自动化 (这里做了修改，显示需求)
    const autoList = document.getElementById('auto-list');
    autoList.innerHTML = '';
    for(const [k, info] of Object.entries(autoInfo)) {
        // 构建可见的成本字符串
        let displayCostStr = '';
        for(const [r,v] of Object.entries(info.next_cost)) {
            displayCostStr += `${TRANS[r] || r}: ${v}  `;
        }

        let detail = `产: ${info.produce_str} | 耗: ${info.consume_str}`;
        
        autoList.innerHTML += `
        <div class="auto-row">
            <div style="flex:1;">
                <div style="font-size:12px; font-weight:bold; color:#ffb74d;">${info.name} <span style="font-size:10px; color:#666;">Lv.${info.level}</span></div>
                <div style="font-size:10px; color:#aaa;">${detail}</div>
                <div style="font-size:10px; color:#ffcc80; margin-top:2px;">需: ${displayCostStr}</div>
            </div>
            <button class="auto-btn" onclick="buyAuto('${k}')">升级</button>
        </div>`;
    }

    // Tab 3: 商店
    if (p.shop.open) {
        document.getElementById('shop-init').style.display = 'none';
        document.getElementById('shop-options').style.display = 'block';
        const cardsDiv = document.getElementById('shop-cards');
        cardsDiv.innerHTML = '';
        p.shop.options.forEach((opt, idx) => {
            let tip = '';
            for(const [k, v] of Object.entries(opt.effect)) tip += `${TRANS[k]||k} +${v}\n`;
            
            cardsDiv.innerHTML += `
            <div class="shop-card" onclick="selectShop(${idx})">
                <div style="font-size:14px; font-weight:bold; color:${opt.color};">${opt.name}</div>
                <div style="font-size:11px; color:#ccc; margin:10px 0;">${opt.desc}</div>
                <div style="font-size:10px; color:#aaa; white-space:pre;">${tip}</div>
            </div>`;
        });
    } else {
        document.getElementById('shop-init').style.display = 'block';
        document.getElementById('shop-options').style.display = 'none';
    }

    // 7. 日志
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