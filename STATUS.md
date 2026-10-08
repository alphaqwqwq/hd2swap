# HD2Swap Head Swap v1 —— 状态与已知风险

**模块名**：`mods/hd2swap/head_swap`
**产物**：`D:\SteamLibrary\steamai\HD2Swap\dist\HD2Swap-HeadSwap-v1.zip`
**语法**：通过 luaparser 检查 ✅
**容器**：字节级正确（哈希 = `0x14E5E3AAB8215ADD`，与自算一致）✅

## 已确定可靠的部分（有实证）

| 部分 | 依据 |
|---|---|
| 容器打包 | 逐字节复刻过 DiverKit 的 patch_0 |
| 资源名哈希 | 已验证 3/3 |
| 探测模块能加载并写日志 | 已在游戏里跑通（`mods/hd2swap/probe: loaded`） |
| 装备目录读取 | DiverKit 逻辑：`*(game+0x33264f8)` → array/count，id@+0，category@+0x28 |
| 头盔槽字段 | `payload+0x124`（armor `+0x12c`，cape `+0x128`） |
| 原生 setter RVA | helmet `0x875CD0`，commit `0x1751280` |
| 6 件头部甲的 ID | 全部实测得到并交叉验证 |

## ⚠️ 未经验证、很可能出错的部分（我明确标出来）

1. **帧回调挂载方式**
   我假设 `_G.update` / `_G.shutdown` 是可覆盖的全局（照抄 DiverKit 的写法）。
   但 DiverKit 是在 **`require` 之后**改的，我们是**立刻执行**——若 `update` 尚不存在，
   我们的赋值可能不是游戏真正调用的那个。**需要确认**。

2. **UI 文字绘制**
   DiverKit 用 `handles()` 从内存里取 font / atlas / material 三个 **UUID 字符串**
   （`api.read(game+0x3772268, 8)` 后按字节逆序转 hex）。我照抄了公式，但
   **`gsub` 逆序 + `IdString64.from_hex` 的细节未经实机验证**，面板可能画不出字。

3. **锚点（Equipment 按钮矩形）**
   我按 `card+0x1B820` 读 164 字节，取前 4 个 float 当 x/y/w/h。
   DiverKit 的 `Screen.identity` 里有专门的 float 解析并做了合理性校验，
   我**没抄全**——坐标很可能是错的，面板可能画到屏幕外。

4. **identity 里的 peer 校验被我删了**
   DiverKit 会比对 `session+0xb398`（本地 peer）与 `owner+slot*0x9f0+0x9f8`，
   并检查 `ready_guard`。我省略了这些守卫，**可能误判到别人的卡片**。

5. **鼠标点击**
   我用 `engine.Mouse.button_id('left')` + `GetCursorPos/ScreenToClient`，
   坐标换算照抄 DiverKit，但**同 #3 一样依赖锚点正确**。

6. **未处理"正牌头盔"字段**
   存档里 `0xBE` 位置还留着真头盔 ID，游戏可能在加载时用它重建外观，
   导致双甲"看起来没生效"（尽管被动已生效）。DiverKit 走的是原生 commit，
   我们走的是**裸写 + 原生 setter + commit**，行为可能不同。

## 结论

**v1 是"骨架完整、内脏未验证"的版本**。正确做法不是继续盲写，而是：

1. 先装上去，看 `HD2Swap.log` 里 **能走到哪一步**
   （`scheduled` → `screen.visible=true` → `ui.drawn` → `ui.error=...`）
2. 按日志逐项修：锚点 → 文字句柄 → 回调挂载
3. 每修一项只改一处，避免同时引入多个未知

## 下一步（等你的日志）

把 ZIP 导入 Arsenal → 和 Bingus Shared Loader 一起启用 → Deploy → 进游戏到飞船 →
打开配装界面 → 退出。然后我读 `HD2Swap.log` 决定往哪修。
