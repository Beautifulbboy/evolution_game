from flask import Flask, render_template, jsonify, request, session
import time
import copy
import random

app = Flask(__name__)
app.secret_key = 'evolution_v4_8_stacking_key'

@app.route('/favicon.ico')
def favicon(): return '', 204

# --- 翻译字典 ---
TRANS = {
    'amino_acid': '氨基酸', 'lipid': '脂质', 'sulfur': '硫磺', 'minerals': '矿物质',
    'ancient_gene': '远古基因',
    'safe_zone': '原生汤浅层', 'thermal_vent': '海底热泉', 'abyss': '深渊海沟',
    'max_hp': '生命上限', 'storage_cap': '仓库容量',
    'heat_res': '耐热性', 'defense': '防御力',
    'gather_speed': '采集/攻击力', 'hp_regen': '生命回复'
}

# --- 变异池 (加入了减益) ---
MUTATION_POOL = [
    # --- 临时增益 ---
    {'id': 't_atk', 'name': '猎手本能', 'type': 'temp', 'duration': 30, 'effect': {'gather_speed': 5.0}, 'desc': '攻击力暴涨', 'color': '#76ff03', 'weight': 20},
    {'id': 't_def', 'name': '甲壳硬化', 'type': 'temp', 'duration': 40, 'effect': {'defense': 3.0}, 'desc': '防御力大幅提升', 'color': '#76ff03', 'weight': 20},
    {'id': 't_reg', 'name': '超速再生', 'type': 'temp', 'duration': 20, 'effect': {'hp_regen': 10.0}, 'desc': '生命极速回复', 'color': '#76ff03', 'weight': 15},
    
    # --- 临时减益 (Debuff) ---
    {'id': 't_weak', 'name': '基因崩溃', 'type': 'temp', 'duration': 30, 'effect': {'defense': -3.0, 'max_hp': -20}, 'desc': '虚弱状态', 'color': '#ff5252', 'weight': 10},
    {'id': 't_slow', 'name': '代谢迟缓', 'type': 'temp', 'duration': 30, 'effect': {'gather_speed': -1.0}, 'desc': '行动变慢', 'color': '#ff5252', 'weight': 10},

    # --- 永久特性 (Perm) ---
    {'id': 'p_cap', 'name': '空间折叠', 'type': 'perm', 'effect': {'storage_cap': 100}, 'desc': '永久容量 +100', 'color': '#00e5ff', 'weight': 10},
    {'id': 'p_atk', 'name': '利爪进化', 'type': 'perm', 'effect': {'gather_speed': 0.5}, 'desc': '永久攻击 +0.5', 'color': '#00e5ff', 'weight': 10},
    {'id': 'p_def', 'name': '石墨烯膜', 'type': 'perm', 'effect': {'defense': 0.3}, 'desc': '永久防御 +0.3', 'color': '#00e5ff', 'weight': 10},
    {'id': 'p_res', 'name': '极端适应', 'type': 'perm', 'effect': {'heat_res': 1.0}, 'desc': '永久耐热 +1.0', 'color': '#00e5ff', 'weight': 10},
    
    # --- 永久减益 (诅咒) ---
    {'id': 'p_curse', 'name': '玻璃大炮', 'type': 'perm', 'effect': {'gather_speed': 2.0, 'max_hp': -50}, 'desc': '攻击大增，血量大减', 'color': '#d500f9', 'weight': 5}
]

# --- 游戏配置 ---
GAME_CONFIG = {
    'boss': {
        'name': '噬菌体霸主', 'max_hp': 3000, 'damage': 20,
        'drop_gene_min': 3, 'drop_gene_max': 6, 'bonus_cap': 1000
    },
    'shop_cost': 5, 
    'zones': {
        'safe_zone': {
            'name': '原生汤浅层', 'desc': '温暖平静。', 'danger_level': '无', 'damage_val': 0, 'mutation_rate': 0,
            'resources': ['amino_acid', 'lipid'], 'color': '#2e7d32'
        },
        'thermal_vent': {
            'name': '海底热泉', 'desc': '高温环境。', 'danger_level': '中危', 'damage_type': 'heat', 'damage_val': 5, 'mutation_rate': 3.0,
            'resources': ['sulfur', 'minerals'], 'color': '#c62828'
        },
        'abyss': {
            'name': '深渊海沟', 'desc': '霸主的巢穴。', 'danger_level': '极危', 'damage_type': 'crush', 'damage_val': 15, 'mutation_rate': 5.0,
            'resources': ['ancient_gene'], 'color': '#311b92'
        }
    },
    'automations': {
        'cilia': {'name': '采集纤毛', 'desc': '自动过滤氨基酸', 'cost': {'amino_acid': 50}, 'cost_scale': 1.4, 'produce': {'amino_acid': 1.0}, 'consume': {}},
        'lipid_synth': {'name': '脂质合成酶', 'desc': '转化氨基酸为脂质', 'cost': {'amino_acid': 100, 'lipid': 20}, 'cost_scale': 1.4, 'produce': {'lipid': 1.0}, 'consume': {'amino_acid': 2.0}},
        'sulfur_pump': {'name': '硫磺泵', 'desc': '消耗生命提取硫磺', 'cost': {'lipid': 200, 'minerals': 50}, 'cost_scale': 1.5, 'produce': {'sulfur': 1.0}, 'consume': {'hp': 0.5}} 
    },
    'recipes': {
        'membrane': {'name': '强化细胞膜', 'base_cost': {'lipid': 10}, 'base_stats': {'max_hp': 30, 'storage_cap': 150}, 'desc': '提升结构强度与容量。'},
        'vacuole': {'name': '巨型液泡', 'base_cost': {'minerals': 20, 'lipid': 20}, 'base_stats': {'storage_cap': 100}, 'desc': '利用矿物撑开内部空间。'},
        'heat_shield': {'name': '复合装甲', 'base_cost': {'lipid': 50, 'minerals': 20}, 'base_stats': {'heat_res': 2, 'defense': 1.5, 'storage_cap': 20}, 'desc': '增加耐热与物理防御。'},
        'flagellum': {'name': '战术鞭毛', 'base_cost': {'amino_acid': 50}, 'base_stats': {'gather_speed': 1.0}, 'desc': '提升采集与攻击伤害。'},
        'mitochondria': {'name': '线粒体引擎', 'base_cost': {'amino_acid': 100, 'sulfur': 20}, 'base_stats': {'hp_regen': 2, 'storage_cap': 50}, 'desc': '提供回复力。'},
        'apex_predator': {'name': '顶级掠食者', 'base_cost': {'ancient_gene': 10, 'amino_acid': 5000}, 'base_stats': {'gather_speed': 10, 'max_hp': 500, 'storage_cap': 2000}, 'desc': '【终极】重写基因，突破生物极限。'}
    }
}

INITIAL_STATE = {
    'stats': {'hp': 100, 'max_hp': 100, 'storage_cap': 200, 'heat_res': 0, 'defense': 0, 'gather_speed': 2, 'hp_regen': 1},
    'inventory': {'amino_acid': 0, 'lipid': 0, 'sulfur': 0, 'minerals': 0, 'ancient_gene': 0},
    'upgrades': {},
    'automations': {'cilia': 0, 'lipid_synth': 0, 'sulfur_pump': 0},
    'perms': [], # 存储结构优化：[{'id':..., 'level':1, ...}]
    'active_buffs': [],
    'mutation_bar': 0.0,
    'current_zone': 'safe_zone',
    'in_combat': False, 'boss_hp': 0, 'flags': {'boss_defeated': False},
    'shop': {'open': False, 'options': []}, 
    'last_update': 0
}

def get_state():
    if 'player' not in session:
        session['player'] = copy.deepcopy(INITIAL_STATE)
        session['player']['last_update'] = time.time()
    p = session['player']
    if 'automations' not in p: p['automations'] = {'cilia': 0, 'lipid_synth': 0, 'sulfur_pump': 0}
    if 'perms' not in p: p['perms'] = []
    if 'shop' not in p: p['shop'] = {'open': False, 'options': []}
    return p

# --- 核心更新 1：计算属性时考虑等级 ---
def get_effective_stats(player):
    eff = copy.deepcopy(player['stats'])
    
    # 叠加永久突变 (Base * Level)
    for perm in player['perms']:
        lv = perm.get('level', 1)
        for k, v in perm['effect'].items(): 
            eff[k] = eff.get(k, 0) + (v * lv)
            
    # 叠加临时Buff (临时Buff通常不叠加等级，只叠加时间或共存，这里保持简单共存)
    for buff in player['active_buffs']:
        for k, v in buff['effect'].items(): 
            eff[k] = eff.get(k, 0) + v
            
    if player['flags'].get('boss_defeated'):
        eff['storage_cap'] += GAME_CONFIG['boss']['bonus_cap']
    eff['gather_speed'] = max(0.1, eff['gather_speed'])
    return eff

# --- 核心更新 2：获得永久突变时处理堆叠 ---
def apply_permanent_gene(player, gene_template):
    # 检查是否已拥有
    existing = next((p for p in player['perms'] if p['id'] == gene_template['id']), None)
    
    if existing:
        existing['level'] = existing.get('level', 1) + 1
        return f"基因强化: {gene_template['name']} -> Lv.{existing['level']}"
    else:
        # 新获得，深拷贝并初始化 level
        new_gene = copy.deepcopy(gene_template)
        new_gene['level'] = 1
        player['perms'].append(new_gene)
        return f"获得新基因: {gene_template['name']}"

def trigger_mutation(player):
    total_weight = sum(m['weight'] for m in MUTATION_POOL)
    r = random.uniform(0, total_weight)
    upto = 0
    chosen = MUTATION_POOL[0]
    for m in MUTATION_POOL:
        if upto + m['weight'] >= r:
            chosen = m
            break
        upto += m['weight']
    
    if chosen['type'] == 'perm':
        msg = apply_permanent_gene(player, chosen)
        log_msg = f"🧬 {msg}"
    else:
        new_buff = {
            'name': chosen['name'], 'effect': chosen['effect'],
            'end_time': time.time() + chosen['duration'], 'color': chosen['color']
        }
        player['active_buffs'].append(new_buff)
        log_msg = f"🧬 突变! 获得状态: [{chosen['name']}] ({chosen['duration']}s)"
    return chosen, log_msg

def generate_shop_options():
    options = []
    pool = [m for m in MUTATION_POOL if m['type'] == 'perm'] * 3 + MUTATION_POOL
    for _ in range(3):
        m = random.choice(pool)
        options.append(m)
    return options

def get_next_level_info(player):
    dynamic_recipes = {}
    current_levels = player['upgrades']
    for key, conf in GAME_CONFIG['recipes'].items():
        curr_lv = current_levels.get(key, 0)
        multiplier = 1.5 ** curr_lv
        next_cost = {k: int(v * multiplier) for k, v in conf['base_cost'].items()}
        dynamic_recipes[key] = {
            'name': conf['name'], 'desc': conf['desc'], 'current_level': curr_lv,
            'next_cost': next_cost, 'base_stats': conf['base_stats']
        }
    return dynamic_recipes

def get_auto_info(player):
    info = {}
    for key, conf in GAME_CONFIG['automations'].items():
        lv = player['automations'].get(key, 0)
        scale = conf['cost_scale']
        cost = {k: int(v * (scale ** lv)) for k, v in conf['cost'].items()}
        
        p_str = ", ".join([f"{TRANS.get(k,k)}+{v}" for k,v in conf['produce'].items()])
        c_str = ", ".join([f"{TRANS.get(k,k)}-{v}" for k,v in conf['consume'].items()])
        
        info[key] = {
            'name': conf['name'], 'desc': conf['desc'], 'level': lv,
            'next_cost': cost,
            'produce_str': p_str,
            'consume_str': c_str if c_str else "无"
        }
    return info

@app.route('/')
def index():
    zones_display = {}
    for k, v in GAME_CONFIG['zones'].items():
        res_names = [TRANS[r] for r in v.get('resources', [])]
        zones_display[k] = {'info': v, 'res_str': "、".join(res_names)}
    return render_template('index.html', config=GAME_CONFIG, trans=TRANS, zones=zones_display)

# --- 逻辑 ---
def common_tick_logic(p, dt):
    eff = get_effective_stats(p)
    log = None
    z = GAME_CONFIG['zones'][p['current_zone']]
    
    # 自动化
    for key, conf in GAME_CONFIG['automations'].items():
        count = p['automations'].get(key, 0)
        if count > 0:
            can_produce = True
            for res, amount in conf['consume'].items():
                req = amount * count * dt
                if res == 'hp': 
                    if p['stats']['hp'] < req + 5: can_produce = False
                else:
                    if p['inventory'].get(res, 0) < req: can_produce = False
            if can_produce:
                for res, amount in conf['consume'].items():
                    req = amount * count * dt
                    if res == 'hp': p['stats']['hp'] -= req
                    else: p['inventory'][res] -= req
                for res, amount in conf['produce'].items():
                    gain = amount * count * dt
                    if p['inventory'].get(res, 0) < eff['storage_cap']:
                        p['inventory'][res] = min(eff['storage_cap'], p['inventory'].get(res, 0) + gain)

    # 战斗/环境
    if p['in_combat']:
        boss_dmg = max(1, GAME_CONFIG['boss']['damage'] - eff['defense']) * dt
        p['stats']['hp'] -= boss_dmg
    elif z['damage_val'] > 0:
        dmg_type = z.get('damage_type')
        res = eff['heat_res'] if dmg_type == 'heat' else 0
        dmg = max(0, z['damage_val'] - eff['defense'] - res) * dt
        if dmg > 0: p['stats']['hp'] -= dmg

    if z['mutation_rate'] > 0: p['mutation_bar'] += z['mutation_rate'] * dt
    if p['mutation_bar'] >= 100:
        p['mutation_bar'] = 0
        _, txt = trigger_mutation(p)
        log = {'msg': txt, 'type': 'mut'}

    now = time.time()
    active_list = []
    for b in p['active_buffs']:
        if b['end_time'] > now:
            b['remaining'] = b['end_time'] - now 
            active_list.append(b)
    p['active_buffs'] = active_list

    reg = eff['hp_regen'] * dt
    if p['stats']['hp'] < eff['max_hp']: p['stats']['hp'] += reg
    
    if p['stats']['hp'] <= 0:
        p['stats']['hp'] = 10
        p['in_combat'] = False
        p['current_zone'] = 'safe_zone'
        p['active_buffs'] = []
        p['mutation_bar'] = 0
        p['shop']['open'] = False
        log = {'msg': "核心崩溃！紧急重构。", 'type': 'dmg'}

    p['stats']['hp'] = min(eff['max_hp'], p['stats']['hp'])
    return log, eff

def make_resp(p, log=None):
    return jsonify({
        'player': p, 
        'eff_stats': get_effective_stats(p), 
        'log': log, 
        'recipes': get_next_level_info(p),
        'auto_info': get_auto_info(p)
    })

# --- API ---
@app.route('/tick')
def tick():
    p = get_state()
    dt = time.time() - p['last_update']
    p['last_update'] = time.time()
    log, _ = common_tick_logic(p, dt)
    session.modified = True
    return make_resp(p, log)

@app.route('/gather/<res>', methods=['POST'])
def gather(res):
    p = get_state()
    log, eff = common_tick_logic(p, 0.1) 
    p['mutation_bar'] += 2.0
    if p['inventory'][res] >= eff['storage_cap']:
         return make_resp(p, {'msg': "仓库已满", 'type': 'sys'})
    actual = min(eff['gather_speed'], eff['storage_cap'] - p['inventory'][res])
    p['inventory'][res] += actual
    if not log: log = {'msg': f"吸取: +{actual:.1f} {TRANS.get(res,res)}", 'type': 'get'}
    session.modified = True
    return make_resp(p, log)

@app.route('/travel/<zone>', methods=['POST'])
def travel(zone):
    p = get_state()
    if p['in_combat']: return make_resp(p, {'msg': "战斗中无法跃迁！", 'type': 'dmg'})
    p['current_zone'] = zone
    p['last_update'] = time.time()
    session.modified = True
    return make_resp(p, {'msg': f"跃迁至: {GAME_CONFIG['zones'][zone]['name']}", 'type': 'sys'})

@app.route('/craft/<item>', methods=['POST'])
def craft(item):
    p = get_state()
    rec = get_next_level_info(p).get(item)
    if not rec: return make_resp(p)
    for k, v in rec['next_cost'].items():
        if p['inventory'].get(k, 0) < v: return make_resp(p, {'msg': "资源不足", 'type': 'sys'})
    for k, v in rec['next_cost'].items(): p['inventory'][k] -= v
    for k, v in rec['base_stats'].items(): p['stats'][k] = p['stats'].get(k, 0) + v
    p['upgrades'][item] = p['upgrades'].get(item, 0) + 1
    if 'max_hp' in rec['base_stats']: p['stats']['hp'] += rec['base_stats']['max_hp']
    session.modified = True
    return make_resp(p, {'msg': f"进化: {rec['name']}", 'type': 'get'})

@app.route('/buy_auto/<item>', methods=['POST'])
def buy_auto(item):
    p = get_state()
    info = get_auto_info(p).get(item)
    if not info: return make_resp(p)
    for k, v in info['next_cost'].items():
        if p['inventory'].get(k, 0) < v: return make_resp(p, {'msg': "资源不足", 'type': 'sys'})
    for k, v in info['next_cost'].items(): p['inventory'][k] -= v
    p['automations'][item] = p['automations'].get(item, 0) + 1
    session.modified = True
    return make_resp(p, {'msg': f"升级成功: {info['name']}", 'type': 'get'})

@app.route('/battle/start', methods=['POST'])
def battle_start():
    p = get_state()
    if p['current_zone'] != 'abyss': return make_resp(p)
    p['in_combat'] = True
    p['boss_hp'] = GAME_CONFIG['boss']['max_hp']
    session.modified = True
    return make_resp(p, {'msg': "⚠️ 噬菌体霸主已苏醒！", 'type': 'combat'})

@app.route('/battle/attack', methods=['POST'])
def battle_attack():
    p = get_state()
    if not p['in_combat']: return jsonify({})
    log, eff = common_tick_logic(p, 0.1) 
    dmg = eff['gather_speed'] * 5
    p['boss_hp'] -= dmg
    log_msg = {'msg': f"攻击: 对霸主造成 {dmg:.1f} 伤害", 'type': 'get'}
    if p['boss_hp'] <= 0:
        p['in_combat'] = False
        p['boss_hp'] = 0
        p['flags']['boss_defeated'] = True
        gene_amt = random.randint(GAME_CONFIG['boss']['drop_gene_min'], GAME_CONFIG['boss']['drop_gene_max'])
        p['inventory']['ancient_gene'] += gene_amt
        log_msg = {'msg': f"🏆 胜利! 获得{gene_amt}远古基因，容量+1000", 'type': 'combat'}
    session.modified = True
    return make_resp(p, log_msg)

@app.route('/battle/escape', methods=['POST'])
def battle_escape():
    p = get_state()
    p['in_combat'] = False
    p['current_zone'] = 'safe_zone'
    session.modified = True
    return make_resp(p, {'msg': "💨 紧急撤离成功。", 'type': 'sys'})

@app.route('/shop/open', methods=['POST'])
def shop_open():
    p = get_state()
    cost = GAME_CONFIG['shop_cost']
    if p['inventory'].get('ancient_gene', 0) < cost:
        return make_resp(p, {'msg': f'需要 {cost} 远古基因', 'type': 'sys'})
    p['inventory']['ancient_gene'] -= cost
    p['shop']['open'] = True
    p['shop']['options'] = generate_shop_options()
    session.modified = True
    return make_resp(p, {'msg': '基因编辑器已启动', 'type': 'sys'})

@app.route('/shop/select/<int:idx>', methods=['POST'])
def shop_select(idx):
    p = get_state()
    if not p['shop']['open'] or idx < 0 or idx >= len(p['shop']['options']): return make_resp(p)
    chosen = p['shop']['options'][idx]
    
    if chosen['type'] == 'perm':
        # 核心更新 3：使用新逻辑处理永久基因堆叠
        msg = apply_permanent_gene(p, chosen)
    else:
        chosen['end_time'] = time.time() + chosen['duration']
        p['active_buffs'].append(chosen)
        msg = f"应用临时状态: {chosen['name']}"
        
    p['shop']['open'] = False
    p['shop']['options'] = []
    session.modified = True
    return make_resp(p, {'msg': msg, 'type': 'mut'})

if __name__ == '__main__':
    app.run(debug=True)