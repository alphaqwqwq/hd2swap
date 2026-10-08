# A网 上传：名称与描述（HD2Swap - Head Swap v1.0.0）

> 产物：`D:\SteamLibrary\steamai\HD2Swap\dist\HD2Swap-HeadSwap-v1.0.zip`（21,785 字节）
> 模块名：`mods/hd2swap/head_swap`　Guid：`7c3f1a52-9e04-4b77-8d21-5a6e0c9b4f13`
> 下面第 1/3 节是**中文页**用，第 2/4 节是**英文页**用。粘之前把「【】」里的内容按需替换。

---

## 0. 速查（照这个填）

| 字段 | 建议值 |
|---|---|
| **标题** | `双甲头盔 HD2Swap（Head Swap）— 头盔槽换装甲 · 双被动` |
| 版本 | `1.0.0` |
| 分类 | 玩法 / 装备（Gameplay / Equipment） |
| 前置 | **Bingus Shared Loader v15+ / API 1**（不依赖 DiverKit） |
| 标签 / 关键词 | 双甲、双重护甲、双被动、头盔、头盔槽、护甲、配装、loadout、head swap、double armour、helmet |
| 缩略图 | 用你这次截的**配装界面里 HEAD SWAP 面板**那张（右侧面板 + 一件甲高亮） |
| 附件 | `HD2Swap-HeadSwap-v1.0.zip` |

---

## 1. 标题（中文页）

**主标题（推荐）**

```
双甲头盔 HD2Swap（Head Swap）— 头盔槽换装甲 · 双被动
```

备选：

```
HD2Swap 双甲 — 把任意护甲装进头盔槽
头盔槽换甲 HD2Swap — 双甲 / 双被动叠加
```

## 2. Title (English page)

**Recommended**

```
HD2Swap - Head Swap: armour in the helmet slot (double armour)
```

Alternates:

```
HD2Swap: Double Armour - put any armour in the helmet slot
Head Swap (HD2Swap) - a second armour passive in your helmet
```

---

## 3. 中文描述（直接粘贴）

```
【一句话】在飞船上的配装界面里点一下，就能把一件护甲装进头盔槽 —— 头盔也会给你一份护甲被动，也就是大家说的「双甲」。

【效果】
头盔槽里那件护甲的被动会真正生效，和身上那件叠加。例如：
  · TG-8 神枪手      坚韧不拔   —— 支援武器装填 +30%
  · CPG-48 士兵      防震内衬   —— 爆炸抗性 50% / 投掷 +2
  · BFM-220 铁甲     钝击创伤缓和 —— 防击倒 / 撞击 -30%
  · O-3 自由之魂     供氧器     —— 步行、奔跑与滑铲加速
  · SR-24 街头侦察兵 蓄势出击   —— 装填 +30% / 弹药 +20%
  · CM-21 战壕护理员 急救包     —— 治疗剂 +2 / 效果 +2 秒
（内置就这 6 件「放进头盔槽依然有意义」的甲，列表在源码 ARMORS 表里，想加自己改）

【怎么用】
1. 需要 Bingus Shared Loader v15 或更新（API 1）。本 mod 不依赖 DiverKit。
2. Arsenal 导入本 ZIP → 启用 → Deploy。
3. 进游戏回到飞船，打开【配装 / 装备】界面。
4. 装备按钮右下方会出现 HEAD SWAP 面板，点选一件护甲即可，面板底部会提示结果。
   换完可以直接去打，被动立刻生效。

【实现方式】
走的是游戏自己的原生流程，不是乱写内存：
  ① 写入配装 payload 的头盔槽字段 → ② 调用游戏原生头盔 setter → ③ 走游戏自己的存档 commit → ④ 回读校验
并且带【构建指纹校验】：会核对 game.dll 的时间戳与镜像大小，遇到没验证过的游戏版本会
直接拒绝运行（只在日志里说明原因），不会往未知版本里写内存。游戏更新后等作者适配即可。

【已知限制 · 先说清楚】
· 只在【飞船上的配装界面】生效，任务中不能换（要换就回飞船）。
· 面板文案目前是简体中文。
· 换完【外观】有可能仍显示原来的头盔（被动已经生效）。遇到请反馈。
· 属于内存修改：重启游戏 / 重新 Deploy 就恢复原状，不改存档文件本体。
· 和其它改配装 / 护甲的 mod 可能互相覆盖（同一批字段）。

【报 bug】
请附日志：%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\HD2Swap.log
日志里会写清楚走到哪一步（ready / screen.visible / ui.error / 换甲结果）。

【更新日志】
v1.0.0  首个公开版本。
```

## 4. English description (paste area)

```
One click in the ship's loadout screen puts an ARMOR item into your HELMET slot, so the helmet
grants a second armour passive. This is the "double armour" trick.

What it does
  The armour you pick lands in the helmet slot through the game's own native setters, and its
  passive stacks with the armour you are wearing. Six armours are included, chosen because their
  passives still matter in a helmet slot:
    TG-8 Marksman, CPG-48 Soldier, BFM-220 Fortified, O-3 Free Soul,
    SR-24 Street Scout, CM-21 Trench Medic
  (The list lives in the ARMORS table in the source - edit it if you want different ones.)

How to use it
  1. Requires Bingus Shared Loader v15 or newer / API 1. Independent of DiverKit.
  2. Import this ZIP in HD2 Arsenal, enable it, Deploy.
  3. Back on the ship, open the loadout / equipment screen.
  4. A HEAD SWAP panel appears below the equipment button - click a row, the result is printed at
     the bottom of the panel. The passive applies immediately.

How it works
  It uses the game's own path rather than blind memory writes: write the helmet field in the
  loadout payload -> call the game's native helmet setter -> commit through the game's own save
  path -> read back and verify. It also checks a build fingerprint (game.dll timestamp and image
  size) and refuses to run against an unverified game build instead of writing to unknown offsets.

Known limitations (up front)
  - Only works on the ship, in the loadout screen. Not in a mission.
  - The panel text is Simplified Chinese.
  - The character model may still show your original helmet even though the passive is active.
  - Memory-only: restarting the game or re-deploying restores the vanilla helmet; no save files
    are modified.
  - Other mods that write the same loadout fields may override each other.

Bug reports
  Please attach %LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\HD2Swap.log - it records how far it
  got (ready / screen.visible / ui.error / swap result).

Changelog
  v1.0.0  first public release.
```

---

## 5. 可选：让 Arsenal 里显示的名字一致（要不要我做）

Arsenal 列表里显示的 **Name / Description 来自 ZIP 里的 `manifest.json`**，现在是：

```
Name        : HD2Swap - Head Swap - v1.0
Description : Requires Bingus Shared Loader v15 or newer / API 1. Enable both and deploy.
```

两点不一致：① 名字和你上面选的标题不一样；② 描述是 `HD2ArchiveTool\make_mod.py` 里**写死的一句话**，
而 A网页面用的是第 3 节的详细描述。

要一致的话我可以重建一版 ZIP（`HD2Swap\build.py` 支持 `--display`，还支持 `--readme` / `--thumbnail`
把说明文件和缩略图一起打进包）：
- 用新的显示名 + 一句更完整的 Description
- 顺手把 `README.txt` 和你的截图作为缩略图打进去
- 会先跑完 5 道关卡（语法 → 离线冒烟 → 端到端 → 打包 → 校验），失败就不出包

> 顺带一个小不一致：源码里 `BUILD = 'hd2swap-headswap-v2'`，而对外包名是 v1.0。建议对外统一成
> **1.0.0**（或者干脆叫 1.1.0），避免作者/用户对不上版本。

---

## 6. 发布前检查清单

- [ ] 实机确认：配装界面能出面板、点选后**被动真的生效**（你这次测试正好覆盖）
- [ ] 截图：面板 + 高亮行（当缩略图）；最好再来一张「双被动生效」的证据图
- [ ] 附件是 `HD2Swap-HeadSwap-v1.0.zip`（不是 v1 / v2 那两个旧包）
- [ ] 前置写明 **Bingus Shared Loader v15+ / API 1**
- [ ] 描述里保留「已知限制」那 5 条 —— A网 上诚实说明限制比事后被追问划算
