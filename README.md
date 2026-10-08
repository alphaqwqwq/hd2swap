# HD2Swap — Head Swap（双甲头盔）

把一件**护甲**装进**头盔槽**，头盔就会额外给你一份护甲被动 —— 也就是大家说的**「双甲」**。
只作用于飞船上的配装界面，走游戏自己的原生 setter + commit，不直接改存档文件。

> Requires **Bingus Shared Loader v15+ / API 1**. Independent of DiverKit.

---

## 效果

头盔槽里那件护甲的被动会真正生效，和身上那件叠加。内置 6 件「放进头盔槽依然有意义」的甲：

| 护甲 | 被动 |
|---|---|
| TG-8 神枪手 | 坚韧不拔 · 支援武器装填 +30% |
| CPG-48 士兵 | 防震内衬 · 爆炸抗性 50% / 投掷 +2 |
| BFM-220 铁甲 | 钝击创伤缓和 · 防击倒 / 撞击 -30% |
| O-3 自由之魂 | 供氧器 · 步行、奔跑与滑铲加速 |
| SR-24 街头侦察兵 | 蓄势出击 · 装填 +30% / 弹药 +20% |
| CM-21 战壕护理员 | 急救包 · 治疗剂 +2 / 效果 +2 秒 |

列表在 `src/head_swap.lua` 的 `ARMORS` 表里，想换自己改。

## 安装 / 使用

1. 需要 **Bingus Shared Loader v15 或更新（API 1）**。本 mod 不依赖 DiverKit。
2. 用 **HD2 Arsenal** 导入 `dist/HD2Swap-HeadSwap-v2.zip` → 启用 → **Deploy**。
3. 进游戏回到飞船，打开**配装 / 装备**界面。
4. 装备按钮附近会出现 **HEAD SWAP** 面板，点选一件护甲即可，面板底部提示结果。换完可直接去打，被动立刻生效。

## 已知限制

- 只在**飞船上的配装界面**生效，任务中不能换。
- 面板文案目前是简体中文。
- 换完**外观**有可能仍显示原来的头盔（被动已经生效）。
- 属于内存修改：重启游戏 / 重新 Deploy 就恢复原状，**不改存档文件本体**。
- 和其它改配装 / 护甲的 mod 可能互相覆盖（同一批字段）。
- 带**构建指纹校验**：会核对 `game.dll` 时间戳与镜像大小，遇到没验证过的游戏版本会**拒绝运行**（只在日志里说明原因）。游戏更新后等作者适配。

## 报告 Bug（请务必附日志）

在 [Issues](https://github.com/alphaqwqwq/hd2swap/issues) 里新建一条，并尽量附上：

1. **日志文件**（整个发上来）：
   `%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\HD2Swap.log`
2. **复现步骤**：点了面板里哪一件、第几步、是**闪退**还是**报错**、发生在什么时候。
3. 还装了哪些其它改配装 / 护甲 / 头盔的 mod。
4. 游戏版本 / 最近是否更新过。

日志里最关键的行：

```
ready=true / scheduled=true        # 是否成功启动
screen.visible=true                # 配装界面是否被识别
swap.write payload=... id=...      # 写入头盔槽字段
swap.setter player=... ok=...      # 调用游戏原生 setter
swap.commit ok=...                 # 走游戏原生 commit
apply <甲> 0x... ok=... -> ...      # 一次完整换甲的结果
ui.error=... / runtime.error=...   # 出错信息
```

> 崩溃前**最后一行**决定往哪查：停在 `swap.setter` 之前 → 崩在原生 setter；停在 `swap.commit` 之前 → 崩在 commit。

## 目录结构

```
src/head_swap.lua     mod 本体（Lua）
src/probe.lua         最小加载探针（只写日志，验证工具链）
test/                离线测试：smoke（假游戏）+ e2e（点击→换甲）+ 若干诊断脚本
build.py             一键构建：语法 → 冒烟 → 端到端 → 打包 → 校验（失败即停）
dist/                已构建的 ZIP
STATUS.md            实现状态与已知风险（内部笔记）
A网上传-名称与描述.md  上传用文案
```

## 从源码构建（开发）

```powershell
& "D:\py\python.exe" build.py
```

`build.py` 会依次跑 5 道关卡并在第一处失败时停止（语法 → 离线冒烟 → 端到端 → 打包 → 校验）。

> 注意：打包依赖同工作区里的 `HD2ArchiveTool`（`make_mod.py` / `bingus_build.py`），
> 测试脚本里也写死了本机绝对路径，所以**当前仓库里的构建脚本只在本机工作区可直接跑**。
> 移植到别的机器需要一起带上 `HD2ArchiveTool` 并改路径。

---

## English

HD2Swap puts an **armour** item into your **helmet slot**, so the helmet grants a second armour
passive (the "double armour" trick). Ship loadout screen only; it goes through the game's own
native setters and commit path rather than editing save files.

- Requires **Bingus Shared Loader v15+ / API 1**. Independent of DiverKit.
- Install: import `dist/HD2Swap-HeadSwap-v2.zip` in HD2 Arsenal, enable, Deploy, then open the
  loadout screen on the ship and click a row in the **HEAD SWAP** panel.
- Memory-only: restarting the game or re-deploying restores the vanilla helmet.
- Refuses to run against an unverified game build (checks the `game.dll` fingerprint).

**Bug reports:** open an issue and attach
`%LOCALAPPDATA%\CowboyBingus\Helldivers2\Logs\HD2Swap.log` plus the exact repro steps, your other
loadout/armour mods, and your game version.
