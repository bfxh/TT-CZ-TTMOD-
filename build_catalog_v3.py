"""
构建统一资产目录 catalog_v3.json

解决的问题：
  1. 三个游戏各自一套目录名 -> 统一成跨游戏的「类型 kind」+ 游戏内的「阵营/分组 faction」
  2. 旧清单（terra/warrobots/ironsaga manifest）里的真实名称、贴图角色信息合并回来
  3. 补齐几何信息（顶点/面数/包围盒），让详情页有东西可看
  4. 重新做贴图关联（按名字前缀匹配同目录 + 游戏级 _textures_misc），提高缩略图覆盖率

输出字段（每项）:
  id g k f n rn p s t tn v fa x y z tg
  id=序号 g=游戏 k=统一类型 f=阵营/分组 n=文件名 rn=真实资源名(旧清单) p=相对路径
  s=KB t=首选贴图 tn=贴图数 v=顶点 fa=面数 x/y/z=包围盒尺寸 tg=标签
"""
import bisect
import json
import os
import re
import time
from collections import Counter, defaultdict
from multiprocessing import Pool, cpu_count

BASE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.path.join(BASE, 'models')
LEGACY_DIR = os.path.dirname(BASE)
OUT = os.path.join(BASE, 'catalog_v3.json')
GEOM_CACHE = os.path.join(BASE, '_res', 'geom_cache.json')

GAMES = [
    ('tt', '01_泰拉科技', '泰拉科技', 'TerraTech', '#34C759'),
    ('wr', '02_战争机器人', '战争机器人', 'War Robots', '#FF9F0A'),
    ('is', '03_重装上阵', '重装上阵', 'Iron Saga', '#BF5AF2'),
]
GAME_BY_FOLDER = {f: gid for gid, f, *_ in GAMES}

# ---------- 统一类型（跨游戏）----------
KINDS = [
    ('module',   '结构模块', 'M',   '#0A84FF'),
    ('weapon',   '武器炮台', 'W',   '#FF453A'),
    ('mech',     '机体载具', 'R',   '#FF9F0A'),
    ('mobile',   '移动部件', 'D',   '#64D2FF'),
    ('struct',   '建筑场景', 'B',   '#5E5CE6'),
    ('terrain',  '地形矿物', 'T',   '#AC8E68'),
    ('foliage',  '植被',     'F',   '#30D158'),
    ('prop',     '道具装饰', 'P',   '#FF375F'),
    ('drone',    '无人机',   'U',   '#63E6E2'),
    ('vfx',      '特效',     'V',   '#FFD60A'),
    ('ui',       'UI图标',   'I',   '#8E8E93'),
    ('collider', '碰撞体',   'C',   '#636366'),
    ('misc',     '其他',     '?',   '#98989D'),
]
KIND_LABEL = {k: lb for k, lb, *_ in KINDS}

# 关键词规则（按优先级），作用于 文件名(小写) 再作用于 目录名(小写)
KIND_RULES = [
    ('collider', ['collider', 'collision', 'col_', '_col', 'colmesh']),
    ('ui',       ['reticule', 'crosshair', 'hud_', '_hud', 'icon', 'minimap']),
    ('vfx',      ['_fx', 'fx_', 'particle', 'vfx', 'glow', 'flare', 'smoke',
                  'explosion', 'trail', 'spark', 'beam_fx', 'muzzleflash']),
    ('foliage',  ['tree', 'plant', 'bush', 'log_', 'grass', 'fern', 'cactus',
                  'leaf', 'branch', 'trunk', 'shrub', 'vine', 'flower']),
    ('terrain',  ['rock', 'ore', 'crystal', 'gem', 'stone', 'cliff', 'terrain',
                  'ground', 'pebble', 'boulder', 'mine_', 'resource', 'chunk',
                  'dirt', 'sand_', 'ice_', 'lava', 'water_']),
    ('weapon',   ['weapon', 'gun', 'cannon', 'laser', 'launcher', 'missile',
                  'rocket', 'plasma', 'phaser', 'blaster', 'mortar', 'minigun',
                  'flak', 'railgun', 'torpedo', 'tesla', 'coil', 'howitzer',
                  'autocannon', 'bolter', 'spear', 'scatter', 'pulser', 'disruptor',
                  'carbine', 'shotgun', 'sniper', 'cyclone', 'avalanche', 'emitter']),
    ('mobile',   ['wheel', 'tyre', 'tire', 'track', 'bogie', 'thruster',
                  'propellor', 'propeller', 'rotor', 'fan_', 'wing', 'hover',
                  'jet_', 'suspension', 'axle', 'hub_', 'skid', 'screw_', 'pedrail']),
    ('drone',    ['drone', 'uav', 'quadcopter']),
    ('mech',     ['cab', 'cockpit', 'chassis', 'hull', 'titan', 'robot', 'mech']),
    ('prop',     ['crate', 'barrel', 'decor', 'sign_', 'flag', 'antenna', 'lamp',
                  'fence', 'door', 'panel', 'console', 'pillar', 'statue', 'cargo',
                  'progressbar', 'led_', 'screen', 'display', 'button', 'dial',
                  'gauge', 'speaker', '喇叭', 'monitor', 'beacon']),
    ('struct',   ['building', 'house', 'tower', 'wall', 'bridge', 'platform',
                  'scene', 'level', 'city', 'ruin', 'bunker', 'hangar', 'gate',
                  'ramp', 'stair', 'floor', 'road', 'roof', 'window', 'container',
                  'factory', 'base_', 'structure', 'blockhouse']),
    ('module',   ['block', 'plate', 'armor', 'armour', 'frame', 'strut', 'bracket',
                  'mount', 'battery', 'generator', 'shield', 'radar', 'sensor',
                  'drill', 'scoop', 'grabber', 'hammer', 'module', 'core', 'tank',
                  'pod', 'seat', 'booster', 'pack', 'cabin', 'gyro', 'reactor',
                  'silencer', 'barrel', 'magazine', 'cargo']),
]

# ---------- 阵营 / 分组 ----------
TT_FACTION = [
    ('GSO', 'GSO 基础'), ('GC', 'GeoCorp'), ('BF', 'BetterFuture'),
    ('VEN', 'Venture'), ('HE', 'Hawkeye'), ('SJ', 'SpaceJunkers'),
    ('RR', 'Reticule'), ('EXP', 'Experimental'), ('SPE', 'Special'),
]
TT_FOLDER_FACTION = {
    'GSO_GeoCorp_Basic_Other': 'GSO 基础', 'GC_GeoCorp_Other': 'GeoCorp',
    'BF_BetterFuture_Other': 'BetterFuture', 'VEN_Venture_Other': 'Venture',
    'HE_Hawkeye_Other': 'Hawkeye', 'SJ_SpaceJunkers_Other': 'SpaceJunkers',
    'RR_Reticule_Other': 'Reticule', 'EXP_Experimental_Other': 'Experimental',
    'SPE_Special_Other': 'Special',
}
IS_FACTION = {
    '方块零件': '方块', '场景部件': '场景', '关卡元素': '关卡',
    '特效配件': '特效', '通用资源': '通用', '道具物品': '道具',
}

# 目录 -> 统一类型（硬映射，优先于关键词）
FOLDER_KIND = {
    # TerraTech
    'Weapons': 'weapon', '武器': 'weapon',
    'Wheels_Tracks': 'mobile', '轮子': 'mobile', '移动': 'mobile',
    'Flight': 'mobile',
    'Rocks_Ores': 'terrain', '矿物': 'terrain', '资源': 'terrain',
    'Trees_Plants': 'foliage',
    'Colliders': 'collider',
    'UI_FX': 'vfx',
    'Sky': 'struct', 'Environment': 'struct',
    '驾驶舱': 'mech',
    '道具': 'prop', 'Decor': 'prop',
    'Blocks': 'module', '方块': 'module', '基础': 'module',
    'Tools_Equipment': 'module',
    # War Robots
    '机器人主体': 'mech', '无人机': 'drone',
    # Iron Saga
    '方块零件': 'module', '场景部件': 'struct', '关卡元素': 'struct',
    '特效配件': 'vfx', '通用资源': 'misc', '道具物品': 'prop',
}

TEX_EXT = ('.png', '.jpg', '.jpeg', '.bmp', '.tga')


# ============================================================
# 旧清单合并
# ============================================================
def load_legacy():
    """返回 {game: {key: {rn, cat, tex:[(role, basename)]}}}
    key: tt/wr = obj 文件名主干(小写); is = 清单 id，如 block_000009
    """
    out: dict[str, dict] = {'tt': {}, 'wr': {}, 'is': {}}
    specs = [
        ('tt', 'terra_manifest.json'),
        ('wr', 'warrobots_manifest.json'),
        ('is', 'ironsaga_manifest.json'),
    ]
    for gid, fn in specs:
        fp = os.path.join(LEGACY_DIR, fn)
        if not os.path.exists(fp):
            print('  [warn] 缺少旧清单: %s' % fn)
            continue
        try:
            with open(fp, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:  # noqa: BLE001 单个 OBJ 解析失败不应中断整批扫描，失败项计入统计
            print('  [warn] 读取 %s 失败: %s' % (fn, e))
            continue
        models = data.get('models', data) if isinstance(data, dict) else data
        for m in models:
            obj = m.get('obj', '')
            stem = os.path.splitext(os.path.basename(obj))[0]
            if not stem:
                continue
            if gid == 'is':
                key = m.get('id') or ''
                if not key:
                    num = re.sub(r'\D', '', stem)
                    if not num:
                        continue
                    key = '%s_%s' % (m.get('category', 'block'), num.zfill(6))
            else:
                key = stem.lower()
            if key in out[gid]:
                continue
            raw = m.get('textures', [])
            tex = []
            if isinstance(raw, list):
                for t in raw:
                    if isinstance(t, dict):
                        tex.append((t.get('role', 'diffuse'), os.path.basename(t.get('path', ''))))
                    elif isinstance(t, str):
                        tex.append(('diffuse', os.path.basename(t)))
            out[gid][key] = {
                'rn': m.get('name', ''),
                'cat': m.get('category', ''),
                'tex': tex,
            }
        print('  旧清单 %-24s %d 条' % (fn, len(out[gid])))
    return out


# 重装上阵：目录 -> 旧清单分类前缀
IS_FOLDER_CAT = {
    '方块零件': 'block', '场景部件': 'scene', '关卡元素': 'levelsets',
    '特效配件': 'sfx', '通用资源': 'common', '道具物品': 'item',
}


# ============================================================
# 几何信息（多进程）
# ============================================================
def _geom_one(args):
    rel, abs_path = args
    try:
        if os.path.getsize(abs_path) > 80 * 1024 * 1024:
            return rel, (0, 0, 0, 0, 0)
        verts = faces = 0
        minx = miny = minz = 1e9
        maxx = maxy = maxz = -1e9
        with open(abs_path, encoding='utf-8', errors='ignore') as f:
            for line in f:
                if line.startswith('v '):
                    verts += 1
                    p = line[2:].split()
                    if len(p) >= 3:
                        try:
                            x, y, z = float(p[0]), float(p[1]), float(p[2])
                        except ValueError:
                            continue
                        if x < minx: minx = x
                        if x > maxx: maxx = x
                        if y < miny: miny = y
                        if y > maxy: maxy = y
                        if z < minz: minz = z
                        if z > maxz: maxz = z
                elif line.startswith('f '):
                    faces += 1
        if minx > maxx:
            minx = miny = minz = maxx = maxy = maxz = 0
        return rel, (verts, faces,
                     round(maxx - minx, 3), round(maxy - miny, 3), round(maxz - minz, 3))
    except Exception:  # noqa: BLE001 读盘失败按缺省值继续，缺文件不该让整批目录构建失败
        return rel, (0, 0, 0, 0, 0)


def build_geom(files, force=False):
    """files: [(rel, abs)] -> {rel: (v, f, x, y, z)}"""
    cache = {}
    if os.path.exists(GEOM_CACHE) and not force:
        try:
            with open(GEOM_CACHE, encoding='utf-8') as f:
                cache = json.load(f)
        except Exception:  # noqa: BLE001 写盘失败只记账不上抛，构建结束后统一汇总
            cache = {}
    todo = [(r, a) for r, a in files if r not in cache]
    print('  几何解析: %d 个（缓存命中 %d）' % (len(todo), len(files) - len(todo)))
    if todo:
        t0 = time.time()
        nproc = min(cpu_count(), 12)
        with Pool(processes=nproc) as pool:
            for i, (rel, g) in enumerate(pool.imap_unordered(_geom_one, todo, chunksize=64)):
                cache[rel] = g
                if (i + 1) % 5000 == 0:
                    print('    %d/%d  %.0fs' % (i + 1, len(todo), time.time() - t0))
        os.makedirs(os.path.dirname(GEOM_CACHE), exist_ok=True)
        with open(GEOM_CACHE, 'w', encoding='utf-8') as f:
            json.dump(cache, f)
        print('  几何解析完成 %.0fs' % (time.time() - t0))
    return cache


# ============================================================
# 分类
# ============================================================
def kind_of(gid, stem, folder):
    k = FOLDER_KIND.get(folder)
    if k:
        # 目录命中后，仍允许文件名里的强特征覆盖（避免 Weapons 目录里混碰撞体）
        low = stem.lower()
        for kk, words in KIND_RULES[:3]:  # collider / ui / vfx
            for w in words:
                if w in low:
                    return kk
        return k
    low_n = stem.lower()
    low_f = folder.lower()
    for kk, words in KIND_RULES:
        for w in words:
            if w in low_n:
                return kk
    for kk, words in KIND_RULES:
        for w in words:
            if w in low_f:
                return kk
    # 游戏级兜底：泰拉科技除环境/资源类目录外，其余基本都是可拼装的方块模块
    if gid == 'tt':
        return 'module' if faction_of(gid, stem, folder) != '通用' else 'misc'
    if gid == 'wr':
        return 'weapon' if folder.startswith('equipment_') else 'mech'
    return 'misc'


def faction_of(gid, stem, folder):
    if gid == 'tt':
        if folder in TT_FOLDER_FACTION:
            return TT_FOLDER_FACTION[folder]
        up = stem.upper()
        for pre, label in TT_FACTION:
            if up.startswith(pre + '_'):
                return label
        return '通用'
    if gid == 'wr':
        if folder.startswith('equipment_'):
            return '武器装备'
        if folder == '机器人主体':
            return '机甲主体'
        if folder == '_textures_misc':
            return '未分组'
        return '场景'
    if gid == 'is':
        return IS_FACTION.get(folder, '未分组')
    return '通用'


def stem_key(stem):
    """用于贴图前缀匹配的归一化 key"""
    s = stem.lower()
    s = re.sub(r'_lod\d+$', '', s)
    s = re.sub(r'_\d{2,6}$', '', s)
    return re.sub(r'\.mesh$', '', s)


class PrefixIndex:
    """按名字前缀查贴图的索引（有序 key + 二分）"""

    def __init__(self, mapping):
        self.map = mapping
        self.keys = sorted(mapping.keys())

    def find(self, c):
        if not c or len(c) < 4:
            return []
        i = bisect.bisect_left(self.keys, c)
        if i < len(self.keys) and self.keys[i].startswith(c):
            return self.map[self.keys[i]]
        if i > 0:
            k = self.keys[i - 1]
            if len(k) >= 4 and c.startswith(k):
                return self.map[k]
        return []


def prefix_hits(key, pidx):
    """逐个丢弃尾部 token 做前缀匹配"""
    if not pidx:
        return []
    parts = key.split('_')
    while parts:
        c = '_'.join(parts)
        r = pidx.find(c)
        if r:
            return r
        parts.pop()
    return []


# ============================================================
# 主流程
# ============================================================
def main():
    t0 = time.time()
    print('扫描 %s' % MODELS)
    legacy = load_legacy()

    files = []          # (rel, abs, gid, folder, stem)
    tex_by_dir = defaultdict(list)   # dir -> [(stem, rel)]
    tex_by_game = defaultdict(list)  # gid -> [(stem, rel)]
    png_byname: dict = defaultdict(dict)   # gid -> {basename_lower: rel}

    for gid, folder, *_ in GAMES:
        gdir = os.path.join(MODELS, folder)
        if not os.path.isdir(gdir):
            print('  [warn] 缺少目录 %s' % folder)
            continue
        for root, _dirs, fns in os.walk(gdir):
            sub = os.path.relpath(root, gdir).replace('\\', '/')
            sub = '' if sub == '.' else sub
            for fn in fns:
                low = fn.lower()
                if low.endswith('.obj'):
                    rel = 'models/%s/%s' % (folder, (sub + '/' + fn) if sub else fn)
                    files.append((rel, os.path.join(root, fn), gid, sub or '(根目录)', os.path.splitext(fn)[0]))
                elif low.endswith(TEX_EXT):
                    rel = 'models/%s/%s' % (folder, (sub + '/' + fn) if sub else fn)
                    st = os.path.splitext(fn)[0]
                    tex_by_dir[root].append((st, rel))
                    tex_by_game[gid].append((st, rel))
                    png_byname[gid].setdefault(fn.lower(), rel)

    print('  模型 %d 个，贴图 %d 张' % (len(files), sum(len(v) for v in tex_by_game.values())))

    # 贴图索引：目录内 stem -> rel，以及游戏内 stem -> rel
    dir_pidx = {}
    for d, lst in tex_by_dir.items():
        m = defaultdict(list)
        for st, rel in lst:
            m[st.lower()].append(rel)
        dir_pidx[d] = PrefixIndex(m)
    game_pidx = {}
    for g, lst in tex_by_game.items():
        m = defaultdict(list)
        for st, rel in lst:
            m[st.lower()].append(rel)
        game_pidx[g] = PrefixIndex(m)

    geom = build_geom([(r, a) for r, a, *_ in files])

    items = []
    for idx, (rel, abs_p, gid, sub, stem) in enumerate(files):
        try:
            size = os.path.getsize(abs_p)
        except OSError:
            size = 0
        key = stem_key(stem)
        d = os.path.dirname(abs_p)

        # --- 旧清单 key ---
        lg = {}
        if gid == 'is':
            num = re.sub(r'\D', '', stem)
            if num:
                cat = IS_FOLDER_CAT.get(sub)
                cands = ['%s_%s' % (cat, num.zfill(6))] if cat else \
                        ['%s_%s' % (c, num.zfill(6)) for c in IS_FOLDER_CAT.values()]
                for kk in cands:
                    if kk in legacy['is']:
                        lg = legacy['is'][kk]
                        break
        else:
            low = stem.lower()
            for kk in (low, re.sub(r'_lod\d+$', '', low), re.sub(r'\.mesh$', '', low)):
                if kk in legacy[gid]:
                    lg = legacy[gid][kk]
                    break

        # --- 贴图关联：1) 旧清单精确映射（带角色）2) 名字前缀启发式 ---
        texts, roles, tq = [], [], 0
        gidx = png_byname.get(gid, {})
        for role, bn in lg.get('tex', []):
            rt = gidx.get(bn.lower())
            if rt and rt not in texts:
                texts.append(rt)
                roles.append(role)
        if texts:
            tq = 1
        elif not (gid == 'is' and stem.isdigit()):
            texts = list(prefix_hits(key, dir_pidx.get(d)))
            if texts:
                tq = 2
            else:
                texts = list(prefix_hits(key, game_pidx.get(gid)))
                if texts:
                    tq = 2
        texts = sorted(set(texts))[:6]
        roles = sorted(set(roles))

        v, fa, bx, by, bz = geom.get(rel, (0, 0, 0, 0, 0))

        kind = kind_of(gid, stem, sub)
        # 旧清单里的分类可作为兜底（重装上阵的旧目录信息更可信）
        if kind == 'misc' and gid == 'is' and lg.get('cat'):
            _c = lg['cat']
            kind = {'block': 'module', 'scene': 'struct', 'levelsets': 'struct',
                    'sfx': 'vfx', 'item': 'prop', 'common': 'misc'}.get(_c, 'misc')

        tags = []
        if texts:
            tags.append('tex')
        if v == 0 and fa == 0:
            tags.append('empty')
        if re.search(r'_lod\d+', stem, re.IGNORECASE):
            tags.append('lod')
        if kind == 'collider' or stem.lower().startswith('col_'):
            tags.append('col')
        if fa >= 20000:
            tags.append('hi')
        elif 0 < fa <= 200:
            tags.append('low')
        if size >= 5 * 1024 * 1024:
            tags.append('big')

        items.append({
            'id': idx, 'g': gid, 'k': kind, 'f': faction_of(gid, stem, sub),
            'c': sub, 'n': stem, 'rn': lg.get('rn', ''), 'p': rel,
            's': round(size / 1024, 1), 't': texts[0] if texts else '',
            'tn': len(texts), 'tl': texts, 'tr': roles, 'tq': tq,
            'v': v, 'fa': fa,
            'x': bx, 'y': by, 'z': bz, 'tg': tags,
        })

    # ---------- 重复标记：同游戏 + 同文件名主干，按路径保留第一个 ----------
    seen: dict = {}
    dup_count = 0
    for it in sorted(items, key=lambda i: (i['g'], i['p'])):
        key = (it['g'], it['n'].lower())
        if key in seen:
            it['tg'].append('dup')
            it['dup'] = seen[key]
            dup_count += 1
        else:
            seen[key] = it['id']

    # ---------- 统计 ----------
    def counter(field):
        c = Counter(i[field] for i in items)
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))

    kinds_count = counter('k')
    games = []
    for gid, folder, cn, en, color in GAMES:
        # 注意：别复用上面的 sub（那是字符串的"子目录名"）——同名不同型是隐患
        grp = [x for x in items if x['g'] == gid]
        ck = Counter(x['k'] for x in grp)
        cf = Counter(x['f'] for x in grp)
        cd = Counter(x['c'] for x in grp)
        games.append({
            'id': gid, 'folder': folder, 'name': cn, 'en': en, 'color': color,
            'count': len(grp),
            'uniq': sum(1 for x in grp if 'dup' not in x['tg']),
            'tex': sum(1 for x in grp if x['tn']),
            'mb': round(sum(x['s'] for x in grp) / 1024),
            'faces': sum(x['fa'] for x in grp),
            'kinds': dict(sorted(ck.items(), key=lambda kv: -kv[1])),
            'factions': dict(sorted(cf.items(), key=lambda kv: -kv[1])),
            'folders': dict(sorted(cd.items(), key=lambda kv: -kv[1])),
        })

    data = {
        'v': 3,
        'generated': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total': len(items),
        'games': games,
        'kinds': [{'id': k, 'label': lb, 'icon': ic, 'color': co, 'count': kinds_count.get(k, 0)}
                  for k, lb, ic, co in KINDS],
        'kindLabel': KIND_LABEL,
        'factions': {g['id']: g['factions'] for g in games},
        'folders': {g['id']: g['folders'] for g in games},
        'items': items,
    }

    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

    print('\n完成: %s' % OUT)
    print('  模型 %d（唯一 %d / 重复副本 %d），贴图命中 %d，总大小 %.1f GB' % (
        len(items), len(items) - dup_count, dup_count,
        sum(1 for i in items if i['tn']),
        sum(i['s'] for i in items) / 1024 / 1024))
    print('  类型分布:')
    for k, lb, *_ in KINDS:
        print('    %-10s %-6s %d' % (k, lb, kinds_count.get(k, 0)))
    print('  耗时 %.0fs' % (time.time() - t0))


if __name__ == '__main__':
    main()
