from flask import Flask, render_template, jsonify, request, session
import time
import copy
import random

app = Flask(__name__)
app.secret_key = 'evolution_v4_1_refactor_key'

# --- 图标 ---
@app.route('/favicon.ico')
def favicon(): return '', 204

# --- 翻译字典 ---
TRANS = {
    'amino_acid': '氨基酸', 'lipid': '脂质', 'sulfur': '硫磺', 'minerals': '矿物质',
    'ancient_gene': '远古基因',
    'safe_zone': '原生汤浅层', 'thermal_vent': '海底热泉', 'abyss': '深渊海沟',
    'max_hp': '生命上限', 'storage_cap': '仓库容量',
    'heat_res': '耐热性', 'defense': '防御力',
    'gather_speed': '攻击/采集力', 'hp_regen': '生命回复'
}

# --- 变异池 ---
MUTATION_POOL = [
    {'id': 'temp_atk', 'name': '猎手本能', 'type': 'temp', 'duration': 30, 'effect': {'gather_speed': 4.0}, 'desc': '攻击力大幅提升', 'color': '#76ff03', 'weight': 25},
    {'id': 'temp_def', 'name': '甲壳硬化', 'type': 'temp', 'duration': 30, 'effect': {'defense': 2.0}, 'desc': '防御力临时提升', 'color': '#76ff03', 'weight': 25},
    {'id': 'temp_weak', 'name': '结构软化', 'type': 'temp', 'duration': 20, 'effect': {'defense': -2.0}, 'desc': '防御力降低', 'color': '#ff5252', 'weight': 20},
    {'id': 'perm_cap', 'name': '空间折叠', 'type': 'perm', 'effect': {'storage_cap': 50}, 'desc': '永久容量 +50', 'color': '#e040fb', 'weight': 5},
    {'id': 'perm_power', 'name': '捕食进化', 'type': 'perm', 'effect': {'gather_speed': 0.2}, 'desc': '永久攻击 +0.2', 'color': '#e040fb', 'weight': 5}
]

# --- 游戏配置 ---
GAME_CONFIG = {
    'boss': {
        'name': '噬菌体霸主',
        'max_hp': 3000,
        'damage': 20,
        'drop_gene_min': 2,
        'drop_gene_max': 5,
        'bonus_cap': 1000
    },
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
            'resources': ['ancient_gene'],
            'color': '#311b92'
        }
    },
    'recipes': {
        'membrane': {'name': '强化细胞膜', 'base_cost': {'lipid': 10}, 'base_stats': {'max_hp': 30, 'storage_cap': 150}, 'desc': '【核心】显著提升物质容量。'},
        'vacuole': {'name': '巨型液泡', 'base_cost': {'minerals': 20, 'lipid': 20}, 'base_stats': {'storage_cap': 100}, 'desc': '利用矿物撑开内部空间。'},
        'heat_shield': {'name': '复合装甲', 'base_cost': {'lipid': 50, 'minerals': 20}, 'base_stats': {'heat_res': 2, 'defense': 1.5, 'storage_cap': 20}, 'desc': '增加耐热与物理防御。'},
        'flagellum': {'name': '战术鞭毛', 'base_cost': {'amino_acid': 50}, 'base_stats': {'gather_speed': 1.0}, 'desc': '提升采集与攻击伤害。'},
        'mitochondria': {'name': '线粒体引擎', 'base_cost': {'amino_acid': 100, 'sulfur': 20}, 'base_stats': {'hp_regen': 2, 'storage_cap': 50}, 'desc': '提供回复力。'},
        'apex_predator': {'name': '顶级掠食者', 'base_cost': {'ancient_gene': 5, 'amino_acid': 2000}, 'base_stats': {'gather_speed': 10, 'max_hp': 500, 'storage_cap': 2000}, 'desc': '【终极】重写基因，突破生物极限。'}
    }
}

INITIAL_STATE = {
    'stats': {'hp': 100, 'max_hp': 100, 'storage_cap': 200, 'heat_res': 0, 'defense': 0, 'gather_speed': 2, 'hp_regen': 1},
    'inventory': {'amino_acid': 0, 'lipid': 0, 'sulfur': 0, 'minerals': 0, 'ancient_gene': 0},
    'upgrades': {}, 
    'mutation_bar': 0.0,
    'active_buffs': [],
    'current_zone': 'safe_zone',
    'in_combat': False, 'boss_hp': 0, 'flags': {'boss_defeated': False},
    'last_update': 0
}

def get_state():
    if 'player' not in session:
        session['player'] = copy.deepcopy(INITIAL_STATE)
        session['player']['last_update'] = time.time()
    p = session['player']
    if 'flags' not in p: p['flags'] = {'boss_defeated': False}
    return p

def get_effective_stats(player):
    eff = copy.deepcopy(player['stats'])
    for buff in player['active_buffs']:
        for stat, val in buff['effect'].items(): eff[stat] = eff.get(stat, 0) + val
    if player['flags'].get('boss_defeated'): eff['storage_cap'] += GAME_CONFIG['boss']['bonus_cap']
    eff['gather_speed'] = max(0.1, eff['gather_speed'])
    return eff

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
        for k, v in chosen['effect'].items(): player['stats'][k] = player['stats'].get(k, 0) + v
        log_msg = f"🧬 突变! 获得永久特性: [{chosen['name']}]"
    else:
        new_buff = {
            'name': chosen['name'], 'effect': chosen['effect'],
            'end_time': time.time() + chosen['duration'], 'color': chosen['color']
        }
        player['active_buffs'].append(new_buff)
        log_msg = f"🧬 突变! 获得状态: [{chosen['name']}] ({chosen['duration']}s)"
    return chosen, log_msg

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

@app.route('/')
def index():
    # 预处理数据传给前端模板
    zones_display = {}
    for k, v in GAME_CONFIG['zones'].items():
        res_names = [TRANS[r] for r in v.get('resources', [])]
        zones_display[k] = {'info': v, 'res_str': "、".join(res_names)}
    
    # 渲染 templates/index.html
    return render_template('index.html', config=GAME_CONFIG, trans=TRANS, zones=zones_display)

# --- 核心逻辑 ---
def common_tick_logic(p, dt):
    log = None
    eff = get_effective_stats(p)
    z = GAME_CONFIG['zones'][p['current_zone']]
    
    if not p['in_combat'] and z['damage_val'] > 0:
        dmg_type = z.get('damage_type')
        res = eff['heat_res'] if dmg_type == 'heat' else 0
        dmg = max(0, z['damage_val'] - eff['defense'] - res) * dt
        if dmg > 0:
            p['stats']['hp'] -= dmg
            log = {'msg': f"环境侵蚀: -{dmg:.1f} HP", 'type': 'dmg'}
            
    if p['in_combat']:
        boss_dmg = max(1, GAME_CONFIG['boss']['damage'] - eff['defense']) * dt
        p['stats']['hp'] -= boss_dmg

    if z['mutation_rate'] > 0: p['mutation_bar'] += z['mutation_rate'] * dt
    if p['mutation_bar'] >= 100:
        p['mutation_bar'] = 0
        _, log_text = trigger_mutation(p)
        log = {'msg': log_text, 'type': 'mut'}

    # 4. Buff时间管理
    now = time.time()
    # 过滤掉过期的
    active_list = []
    for b in p['active_buffs']:
        if b['end_time'] > now:
            # 【修复点】在这里实时计算 remaining 发给前端
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
        log = {'msg': "核心机体崩溃！紧急重构于安全区。", 'type': 'dmg'}

    p['stats']['hp'] = min(eff['max_hp'], p['stats']['hp'])
    return log, eff

# --- API 路由 ---
@app.route('/tick')
def tick():
    p = get_state()
    dt = time.time() - p['last_update']
    p['last_update'] = time.time()
    log, eff = common_tick_logic(p, dt)
    session.modified = True
    return jsonify({'player': p, 'eff_stats': eff, 'log': log, 'recipes': get_next_level_info(p)})

@app.route('/gather/<res>', methods=['POST'])
def gather(res):
    p = get_state()
    log, eff = common_tick_logic(p, 0.1) 
    p['mutation_bar'] += 2.0 
    
    if p['inventory'][res] >= eff['storage_cap']:
         return jsonify({'player': p, 'eff_stats': eff, 'log': {'msg': "仓库已满", 'type': 'sys'}, 'recipes': get_next_level_info(p)})

    actual = min(eff['gather_speed'], eff['storage_cap'] - p['inventory'][res])
    p['inventory'][res] += actual
    
    if not log: log = {'msg': f"吸取: +{actual:.1f} {TRANS.get(res,res)}", 'type': 'get'}
    session.modified = True
    return jsonify({'player': p, 'eff_stats': eff, 'log': log, 'recipes': get_next_level_info(p)})

@app.route('/travel/<zone>', methods=['POST'])
def travel(zone):
    p = get_state()
    if p['in_combat']: return jsonify({'player': p, 'eff_stats': get_effective_stats(p), 'log': {'msg': "战斗中无法跃迁！", 'type': 'dmg'}, 'recipes': get_next_level_info(p)})
    p['current_zone'] = zone
    p['last_update'] = time.time()
    session.modified = True
    return jsonify({'player': p, 'eff_stats': get_effective_stats(p), 'log': {'msg': f"跃迁至: {GAME_CONFIG['zones'][zone]['name']}", 'type': 'sys'}, 'recipes': get_next_level_info(p)})

@app.route('/craft/<item>', methods=['POST'])
def craft(item):
    p = get_state()
    dynamic_recipes = get_next_level_info(p)
    target = dynamic_recipes.get(item)
    if not target: return jsonify({})
    
    cost = target['next_cost']
    for k, v in cost.items():
        if p['inventory'].get(k, 0) < v: return jsonify({'player': p, 'eff_stats': get_effective_stats(p), 'log': {'msg': "资源不足", 'type': 'sys'}, 'recipes': dynamic_recipes})
    
    for k, v in cost.items(): p['inventory'][k] -= v
    for k, v in target['base_stats'].items(): p['stats'][k] = p['stats'].get(k, 0) + v
    p['upgrades'][item] = p['upgrades'].get(item, 0) + 1
    if 'max_hp' in target['base_stats']: p['stats']['hp'] += target['base_stats']['max_hp']

    session.modified = True
    return jsonify({'player': p, 'eff_stats': get_effective_stats(p), 'log': {'msg': f"进化: {target['name']} -> Lv.{p['upgrades'][item]}", 'type': 'get'}, 'recipes': get_next_level_info(p)})

@app.route('/battle/start', methods=['POST'])
def battle_start():
    p = get_state()
    if p['current_zone'] != 'abyss': return jsonify({})
    p['in_combat'] = True
    p['boss_hp'] = GAME_CONFIG['boss']['max_hp']
    session.modified = True
    return jsonify({'player': p, 'eff_stats': get_effective_stats(p), 'log': {'msg': "⚠️ 噬菌体霸主已苏醒！", 'type': 'combat'}, 'recipes': get_next_level_info(p)})

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
        log_msg = {'msg': f"🏆 胜利! 获得{gene_amt}远古基因，并永久解锁容量+1000", 'type': 'combat'}
    
    session.modified = True
    return jsonify({'player': p, 'eff_stats': eff, 'log': log_msg, 'recipes': get_next_level_info(p)})

@app.route('/battle/escape', methods=['POST'])
def battle_escape():
    p = get_state()
    p['in_combat'] = False
    p['current_zone'] = 'safe_zone'
    session.modified = True
    return jsonify({'player': p, 'eff_stats': get_effective_stats(p), 'log': {'msg': "💨 紧急撤离成功。", 'type': 'sys'}, 'recipes': get_next_level_info(p)})

if __name__ == '__main__':
    app.run(debug=True)