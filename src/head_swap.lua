-- HD2-Addon: mods/hd2swap/head_swap
--
-- HD2Swap - head-slot armour swapper for HELLDIVERS 2
--
-- Puts an ARMOR item into the HELMET slot through the game's own native
-- setters, so the helmet grants a second armour passive.  This is the
-- "double armour" trick, done out-of-mission on the ship.
--
-- Requires: Bingus Shared Loader v15+ / API 1.  Independent of DiverKit.
--
-- The compatibility scan, screen identity, pointer sampling and GUI handle
-- resolution below are faithful ports of DiverKit's verified implementations
-- (same byte offsets, same validation guards, same material slot setup).

local MODULE = 'mods/hd2swap/head_swap'
local BUILD = 'hd2swap-headswap-v2'

-- ===========================================================================
-- the six head armours worth wearing: their passives still matter in a helmet
-- slot.  ids are stable 32-bit resource hashes, all verified in game.
-- ===========================================================================
local ARMORS = {
    { id = 0x5D0D8002, zh = 'TG-8 神枪手',      note = '坚韧不拔 · 支援武器装填+30%' },
    { id = 0x5F075DC5, zh = 'CPG-48 士兵',      note = '防震内衬 · 爆炸抗性50%/投掷+2' },
    { id = 0xF8B8CF9B, zh = 'BFM-220 铁甲',     note = '钝击创伤缓和 · 防击倒/撞击-30%' },
    { id = 0xF7E6F127, zh = 'O-3 自由之魂',     note = '供氧器 · 步行奔跑与滑铲加速' },
    { id = 0x05E56EE5, zh = 'SR-24 街头侦察兵', note = '蓄势出击 · 装填+30%/弹药+20%' },
    { id = 0xD52BB413, zh = 'CM-21 战壕护理员', note = '急救包 · 治疗剂+2/效果+2秒' },
}

-- ===========================================================================
-- logging (goes to %LOCALAPPDATA%/CowboyBingus/Helldivers2/Logs/HD2Swap.log)
-- ===========================================================================
local Log = (function()
    local M = {}
    local file, closed = nil, false
    local function open()
        if file or closed then return file end
        local loader = rawget(_G, 'CowboyBingusModLoader')
        if loader and type(loader.open_log) == 'function' then
            local ok, f = pcall(function() return loader.open_log('HD2Swap.log') end)
            if ok and f then file = f end
        end
        return file
    end
    function M.write(line)
        local f = open()
        if f then
            local ok = pcall(function() f:write(line .. '\n'); f:flush() end)
            if ok then return end
        end
        -- (marker)nt('[' .. MODULE .. '] ' .. line)
    end
    function M.close()
        if file and not closed then
            pcall(function() file:close() end)
            closed = true
        end
    end
    return M
end)()

Log.write('=== HD2Swap ' .. BUILD .. ' ===')

-- ===========================================================================
-- global addresses.  These are the reference RVAs DiverKit resolves; for the
-- shipped build they are directly usable, and Compat.verify() re-derives the
-- build fingerprint so we refuse to run against an unknown game version.
-- ===========================================================================
local ADDR = {
    manager    = 0x3326E68,
    session    = 0x347CEF0,
    font       = 0x3772268,
    atlas      = 0x3772EE8,
    material   = 0x37C5478,
    gear       = 0x33264F8,
    commit     = 0x1751280,
    helmet_set = 0x875CD0,
    cape_set   = 0x875EC0,
    armor_set  = 0x8760B0,
}

local KNOWN_BUILDS = {
    -- game.dll PE fingerprint : { exe_stamp, exe_size, dll_stamp, dll_size }
    [1790161983] = { 1790149348, 60719104, 1790161983, 74727424 },
}

-- ===========================================================================
-- memory api
-- ===========================================================================
local function make_api(ffi, kernel)
    local M = {}
    local own = kernel.GetCurrentProcess()
    -- Fixed-size scratch buffer: `ffi.new('uint8_t[?]', n)` creates a VLA whose
    -- length is not queryable in every LuaJIT build, so keep a plain array of
    -- the maximum size we ever read and use only the first `size` bytes.
    local MAX_READ = 4096
    local scratch = ffi.new('uint8_t[4096]')
    local read_out = ffi.new('size_t[1]')

    function M.read(address, size)
        -- `address` arrives as cdata (ffi.cast('intptr_t', handle)) or a plain
        -- number depending on the caller, so normalise before validating.
        local addr = tonumber(address)
        if not addr or addr < 65536 or size <= 0 or size > MAX_READ then
            return nil
        end
        if kernel.ReadProcessMemory(own, ffi.cast('void *', addr), scratch, size, read_out) == 0 then
            return nil
        end
        if read_out[0] ~= size then return nil end
        return ffi.string(scratch, size)
    end

    function M.write(address, bytes)
        local addr = tonumber(address)
        local n = #bytes
        if not addr or addr < 65536 or n <= 0 or n > MAX_READ then return false end
        ffi.copy(scratch, bytes, n)
        local out = ffi.new('size_t[1]')
        if kernel.WriteProcessMemory(own, ffi.cast('void *', addr), scratch, n, out) == 0 then
            return false
        end
        return out[0] == n
    end
    function M.u32(bytes, offset)
        offset = offset or 0
        if not bytes or #bytes < offset + 4 then return nil end
        local b = { bytes:byte(offset + 1, offset + 4) }
        return b[1] + b[2] * 256 + b[3] * 65536 + b[4] * 16777216
    end
    function M.pointer(bytes, offset)
        local lo = M.u32(bytes, offset or 0)
        local hi = M.u32(bytes, (offset or 0) + 4)
        if not lo or not hi then return nil end
        local v = hi * 4294967296 + lo
        if v == 0 then return nil end
        return v
    end
    function M.u32le(value)
        return string.char(value % 256, math.floor(value / 256) % 256,
            math.floor(value / 65536) % 256, math.floor(value / 16777216) % 256)
    end
    return M
end

-- ===========================================================================
-- Screen identity -- direct port of DiverKit's Screen.identity.
-- Returns (token, box, info) or nil.  box = the native Equipment button rect,
-- which is where our panel anchors.
-- ===========================================================================
local Screen = (function()
    local M = {}

    function M.identity(ctx)
        local api, game = ctx.api, ctx.game
        local manager_bytes = api.read(game + ADDR.manager, 8)
        local session_bytes = api.read(game + ADDR.session, 8)
        local manager, session = api.pointer(manager_bytes), api.pointer(session_bytes)
        if not manager or not session then return nil end

        local bucket = api.read(manager + 0x62A0, 24)
        if not bucket or api.u32(bucket, 0) ~= 1 or api.u32(bucket, 16) ~= 0xE5 then return nil end
        local owner = api.pointer(bucket, 8)
        if not owner then return nil end

        -- set_view at 0x1470d00: 0 = landing map, 1 = stratagem loadout
        local view_bytes = api.read(owner + 8, 4)
        if not view_bytes or api.u32(view_bytes, 0) ~= 1 then return nil end

        -- Equipment selectors retain their parent loadout view during animation
        if api.read(owner + 0x273990, 1) ~= '\0' or api.read(owner + 0x2808, 1) ~= '\0' then return nil end

        local slot_bytes = api.read(owner + 0x27D0, 4)
        local slot = slot_bytes and api.u32(slot_bytes, 0)
        if not slot or slot >= 4 then return nil end

        local peer = api.read(session + 0xB398, 8)
        if not peer or peer == string.rep('\0', 8)
            or api.read(owner + slot * 0x9F0 + 0x9F8, 8) ~= peer then return nil end

        local card
        for i = 0, 3 do
            local candidate = owner + 0x53A78 + i * 0x1EE18
            local payload = api.read(candidate + 0x1EDF0, 8)
            local card_slot = api.read(candidate + 0x1EDFC, 4)
            if payload and api.pointer(payload) == owner + slot * 0x9F0 + 0x10
                and card_slot and api.u32(card_slot, 0) == slot then
                if card then return nil end     -- ambiguous
                card = candidate
            end
        end
        if not card then return nil end

        -- Equipment toggle is card+0x1b820; validator bits must be present
        local widget = api.read(card + 0x1B820, 164)
        if not widget or require('bit').band(api.u32(widget, 0), 0x10) == 0 then return nil end

        local ffi = ctx.ffi
        local function float(offset)
            local v = ffi.new('float[1]')
            ffi.copy(v, widget:sub(offset + 1, offset + 4), 4)
            return tonumber(v[0])
        end

        local opacity, sx, sy = float(84), float(100), float(140)
        if not (opacity >= 0.995 and opacity <= 1.01 and sx >= 0.3 and sx <= 4
            and math.abs(sx - sy) < 0.01) then return nil end

        local box = { x = float(148), y = float(156), w = float(36) * sx, h = float(40) * sy, scale = sx }
        for _, v in pairs(box) do
            if v ~= v or v < 0 or v > 32768 then return nil end
        end
        if box.w < 100 or box.h < 10 then return nil end

        -- re-validate everything we sampled before trusting it
        if api.read(game + ADDR.manager, 8) ~= manager_bytes or api.read(game + ADDR.session, 8) ~= session_bytes
            or api.read(owner + 8, 4) ~= view_bytes
            or api.read(owner + 0x273990, 1) ~= '\0' or api.read(owner + 0x2808, 1) ~= '\0'
            or api.pointer((api.read(card + 0x1EDF0, 8))) ~= owner + slot * 0x9F0 + 0x10
            or api.read(card + 0x1EDFC, 4) ~= slot_bytes
            or api.read(manager + 0x62A0, 24) ~= bucket or api.read(owner + 0x27D0, 4) ~= slot_bytes
            or api.read(session + 0xB398, 8) ~= peer or api.read(owner + slot * 0x9F0 + 0x9F8, 8) ~= peer then
            return nil
        end

        local token = manager_bytes .. session_bytes .. bucket .. slot_bytes .. peer
        return token, box, {
            owner = owner, card = card, slot = slot,
            payload = owner + slot * 0x9F0 + 0x10, session = session,
        }
    end

    return M
end)()

-- ===========================================================================
-- Pointer -- direct port of DiverKit's Pointer (window-relative mouse -> GUI)
-- ===========================================================================
local Pointer = (function()
    local M = {}

    function M.new(ffi, kernel, engine)
        local user = ffi.load('user32')
        local mouse = assert(engine.Mouse, 'Mouse unavailable')
        local left = mouse.button_id('left')
        local point = ffi.new('HD2SwapPoint[1]')
        local rect = ffi.new('HD2SwapRect[1]')
        local pid = ffi.new('uint32_t[1]')
        local point_arg = ffi.cast('void *', point)
        local rect_arg = ffi.cast('void *', rect)
        local pid_arg = ffi.cast('void *', pid)
        local own_pid = kernel.GetCurrentProcessId()
        local self = {}

        function self:reset() self.previous = nil; self.armed = nil end

        function self:focused()
            local window = user.GetForegroundWindow()
            if window == nil then return nil end
            if user.GetWindowThreadProcessId(window, pid_arg) == 0 or pid[0] ~= own_pid then return nil end
            return window
        end

        function self:sample()
            local window = self:focused()
            if not window then return nil end
            if user.GetCursorPos(point_arg) == 0 or user.ScreenToClient(window, point_arg) == 0
                or user.GetClientRect(window, rect_arg) == 0 then return nil end
            local w = rect[0].right - rect[0].left
            local h = rect[0].bottom - rect[0].top
            local x, y = point[0].x, point[0].y
            if w <= 0 or h <= 0 or x < 0 or y < 0 or x >= w or y >= h then return nil end
            local rw, rh = engine.Gui.resolution()
            local value = mouse.button(left)
            return {
                x = x * rw / w, y = (h - y) * rh / h,
                down = value == true or type(value) == 'number' and value > 0,
            }
        end

        function self:step(sample, hit)
            if not sample then self:reset(); return nil end
            local clicked
            if self.previous ~= nil then
                if sample.down and not self.previous then self.armed = hit end
                if not sample.down and self.previous then
                    if hit and hit == self.armed then clicked = hit end
                    self.armed = nil
                end
            end
            self.previous = sample.down
            return clicked
        end

        return self
    end

    return M
end)()

-- ===========================================================================
-- native function binding (VirtualQuery-checked, like DiverKit's Apply.bind)
-- ===========================================================================
local Native = (function()
    local M = {}

    function M.bind(ctx)
        local api, ffi, game = ctx.api, ctx.ffi, ctx.game
        -- NOTE: HD2SwapPoint / HD2SwapRect and the kernel32 prototypes are
        -- already declared in prepare_ffi().  Re-declaring an existing typedef
        -- raises "declaration specifier expected near '...'", so only add the
        -- two prototypes that are genuinely new here.
        pcall(ffi.cdef, [[
            size_t VirtualQuery(const void *, void *, size_t);
        ]])
        local out = {}
        local function bind(name, rva, signature)
            local at = game + rva
            local region = ffi.new('uint8_t[48]')
            if ctx.kernel.VirtualQuery(ffi.cast('void *', at), region, 48) ~= 48 then
                return nil, name .. ' unreadable'
            end
            local b = ffi.string(region, 48)
            if api.u32(b, 32) ~= 0x1000 then return nil, name .. ' not committed' end
            local protect = api.u32(b, 36)
            local executable = ({ [0x10] = true, [0x20] = true, [0x40] = true, [0x80] = true })[protect]
            if not executable then return nil, name .. ' not executable' end
            return ffi.cast(signature, at)
        end
        out.commit, ctx.error = bind('commit', ADDR.commit, 'void (*)(void *)')
        if not out.commit then return nil, ctx.error end
        out.helmet, ctx.error = bind('helmet', ADDR.helmet_set, 'void (*)(void *, uint32_t, uint32_t)')
        if not out.helmet then return nil, ctx.error end
        out.armor, ctx.error = bind('armor', ADDR.armor_set, 'void (*)(void *, uint32_t, uint32_t)')
        if not out.armor then return nil, ctx.error end
        return out
    end

    return M
end)()

-- ===========================================================================
-- the actual swap
-- ===========================================================================
local Swap = (function()
    local M = {}
    local HELMET_OFFSET = 0x124

    function M.catalog(ctx)
        local api, game = ctx.api, ctx.game
        local manager = api.pointer(api.read(game + ADDR.gear, 8))
        if not manager then return nil, 'catalog manager unavailable' end
        local array = api.pointer(api.read(manager, 8))
        local count = api.u32(api.read(manager + 8, 4) or '', 0)
        if not array or not count or count < 1 or count > 2048 then return nil, 'catalog bounds rejected' end
        local by_id = {}
        for i = 0, count - 1 do
            local item = api.pointer(api.read(array + i * 8, 8))
            if item then
                local id = api.u32(api.read(item, 4) or '', 0)
                local category = api.u32(api.read(item + 0x28, 4) or '', 0)
                if id and category ~= nil then by_id[id] = category end
            end
        end
        return by_id
    end

    function M.apply(ctx, armor_id)
        local api = ctx.api
        local token, box, info = Screen.identity(ctx)
        if not info then return false, '打开配装界面后再试' end

        local catalog, why = M.catalog(ctx)
        if not catalog then return false, why end
        if catalog[armor_id] == nil then return false, '目录里没有这件装备' end
        if catalog[armor_id] ~= 0 then return false, '这不是护甲（category ' .. tostring(catalog[armor_id]) .. '）' end

        local before = api.u32(api.read(info.payload + HELMET_OFFSET, 4) or '', 0)
        if before == armor_id then return false, '头盔已经是它了' end

        -- 1) write the payload field
        if not api.write(info.payload + HELMET_OFFSET, api.u32le(armor_id)) then
            return false, '内存写入失败'
        end
        if api.u32(api.read(info.payload + HELMET_OFFSET, 4) or '', 0) ~= armor_id then
            return false, '写入未被确认'
        end
        Log.write(string.format('swap.write payload=0x%X offset=0x%X id=0x%08X ok',
            info.payload, HELMET_OFFSET, armor_id))

        -- 2) re-validate the screen, then call the game's own setter
        local token2, box2, info2 = Screen.identity(ctx)
        if not info2 then return false, '界面已变化，已中止' end
        local player = api.u32(api.read(info2.card + 0x1EDF8, 4) or '', 0)
        if not player or player == 0 then return false, '取不到 player id' end
        local setter_ok, setter_err
        if ctx.native_hook then
            -- offline harness provides a stub so we never jump into fake memory
            setter_ok, setter_err = pcall(ctx.native_hook.helmet, ctx.gear_manager, player, armor_id)
        else
            -- void(void* catalog, uint32 player, uint32 id)
            setter_ok, setter_err = pcall(function()
                ctx.native.helmet(ctx.ffi.cast('void *', ctx.gear_manager), player, armor_id)
            end)
        end
        Log.write(string.format('swap.setter player=0x%X ok=%s err=%s',
            player, tostring(setter_ok), tostring(setter_err)))

        -- 3) commit through the game's own save path
        local commit_ok, commit_err
        if ctx.native_hook then
            commit_ok, commit_err = pcall(ctx.native_hook.commit, info2.payload)
        else
            commit_ok, commit_err = pcall(function() ctx.native.commit(info2.payload) end)
        end
        Log.write(string.format('swap.commit ok=%s err=%s', tostring(commit_ok), tostring(commit_err)))

        -- 4) verify what survived
        local after = api.u32(api.read(info.payload + HELMET_OFFSET, 4) or '', 0)
        if after ~= armor_id then
            return false, string.format('被游戏改回了 0x%08X', after)
        end
        return true, string.format('已换上 0x%08X', armor_id)
    end

    return M
end)()

-- ===========================================================================
-- GUI handle resolution -- port of DiverKit's handles()
-- ===========================================================================
local function gui_handles(ctx)
    local api, game = ctx.api, ctx.game
    local function hex8(bytes)
        local out = {}
        for i = #bytes, 1, -1 do out[#out + 1] = string.format('%02x', bytes:byte(i)) end
        return table.concat(out)
    end
    local function hash(address)
        local bytes = api.read(address, 8)
        if not bytes or bytes == string.rep('\0', 8) then return nil end
        return hex8(bytes)
    end
    local font = hash(game + ADDR.font)
    local atlas = hash(game + ADDR.atlas)
            local material_bytes = api.read(game + ADDR.material, 8)
            local material_ptr = material_bytes and api.pointer(material_bytes)
    if not material_ptr then return nil end
    local material = hash(material_ptr + 24)
    if not font or not atlas or not material then return nil end
    return { font = font, atlas = atlas, material = material }
end

-- ===========================================================================
-- panel
-- ===========================================================================
local Panel = (function()
    local M = {}
    local W, ROW, HEAD = 360, 30, 30

    function M.new(engine)
        local self = { regions = {}, hover = nil }
        local App, World, Gui = engine.Application, engine.World, engine.Gui

        function self:clear()
            if self.world and self.gui then
                pcall(function() World.destroy_gui(self.world, self.gui) end)
            end
            self.gui, self.world, self.signature = nil, nil, nil
            self.regions = {}
        end

        function self:hit(x, y)
            for i = #self.regions, 1, -1 do
                local r = self.regions[i]
                if x >= r.x and x < r.x + r.w and y >= r.y and y < r.y + r.h then return r.key end
            end
        end

        function self:height() return HEAD + #ARMORS * ROW + 26 end

        function self:draw(ctx, view)
            local api = ctx.api
            local target
            local main = App.main_world()
            for _, w in ipairs(App.worlds() or {}) do if w ~= main then target = w; break end end
            if not target then self:clear(); return end

            local handles = gui_handles(ctx)
            if not handles then
                if self.handle_error ~= 'unavailable' then
                    self.handle_error = 'unavailable'
                    Log.write('ui.error=font/atlas/material handles unavailable')
                end
                self:clear()
                return
            end

            local box = view.box
            local signature = table.concat({ handles.font, handles.atlas, handles.material,
                string.format('%.1f,%.1f,%.1f,%.1f', box.x, box.y, box.w, box.h),
                tostring(view.selected), tostring(view.hover), tostring(view.notice) }, '|')
            if self.world == target and self.signature == signature then return end

            self:clear()
            self.world = target
            self.gui = assert(World.create_screen_gui(target, 'scale', 1, 1))
            self.signature = signature

            local gui = self.gui
            local ids = engine.IdString64.from_hex
            local font = ids(handles.font)
            local material = ids(handles.material)
            local ink = assert(Gui.material(gui, material))
            local function slot(id) return ids(id .. '00000000') end
            for _, h in ipairs({ '8035c266', '5e8455fe', '309e7783', '82b803a8' }) do
                engine.Material.set_scalar(ink, slot(h), 0)
            end
            engine.Material.set_vector2(ink, slot('e13777ce'), engine.Vector2(1, -1))
            engine.Material.set_vector4(ink, slot('7701209e'), engine.Color(0, 0, 0, 0))
            engine.Material.set_texture(ink, slot('88bac99b'), ids(handles.atlas))

            -- Anchor BELOW the native Equipment button, in the empty area to
            -- the right of the loadout column.  Drawing above the button
            -- overlays the native stratagem/equipment tiles, which makes the
            -- native UI unusable (that is what DiverKit avoids).
            local s = box.scale or (box.w / 420)
            if not (s > 0) then s = 1 end
            local width, height = Gui.resolution()
            local total_h = self:height()

            -- start just under the Equipment button, shifted right into the
            -- free space between the loadout column and the character panel
            local ox = box.x + box.w + 12 * s
            local oy = box.y + box.h + 4 * s

            -- keep it fully on screen
            local panel_w = W * s
            local panel_h = total_h * s
            if ox + panel_w > width - 4 then
                ox = math.max(4, width - panel_w - 4)
            end
            if oy + panel_h > height - 4 then
                oy = math.max(4, height - panel_h - 4)
            end

            local layer = 0
            local gold = engine.Color(255, 213, 0)
            local white = engine.Color(255, 238, 242, 246)
            local muted = engine.Color(255, 153, 171, 184)
            local function rect(x, y, w, h, c, z)
                Gui.rect(gui, engine.Vector3(ox + x * s, oy + y * s, (z or 950) + layer),
                    engine.Vector2(w * s, h * s), c)
            end
            local function outline(x, y, w, h, c, t)
                t = t or 1
                rect(x, y, w, t, c, 952); rect(x, y + h - t, w, t, c, 952)
                rect(x, y, t, h, c, 952); rect(x + w - t, y, t, h, c, 952)
            end
            local function text(value, x, y, size, c, limit)
                Gui.text(gui, value, font, size * s, material,
                    engine.Vector3(ox + x * s, oy + y * s, 953 + layer), c or white)
            end

            self.regions = {}
            local total = self:height()
            rect(0, 0, W, total, engine.Color(200, 8, 14, 20), 0)
            outline(0, 0, W, total, gold, 2)
            text('HEAD SWAP', 8, 10, 15, gold)
            text('Bingus v15+', 176, 11, 12, muted)

            for i, armor in ipairs(ARMORS) do
                local y = HEAD + (i - 1) * ROW
                local selected = (view.selected == i)
                local hovered = (view.hover == i)
                rect(6, y, W - 12, 26, selected and engine.Color(200, 165, 0, 52)
                    or hovered and engine.Color(210, 220, 230, 42)
                    or engine.Color(10, 16, 22, 45), 951)
                outline(6, y, W - 12, 26, selected and gold or engine.Color(200, 212, 220, 145), selected and 2 or 1)
                text(armor.zh, 14, y + 6, 15, selected and gold or white, 96)
                text(armor.note, 112, y + 7, 12, muted)
                self.regions[#self.regions + 1] = {
                    key = i, x = ox + 6 * s, y = oy + y * s, w = (W - 12) * s, h = 26 * s,
                }
            end

            local ny = HEAD + #ARMORS * ROW + 6
            text(view.notice or '', 8, ny, 12, muted)
        end

        return self
    end

    return M
end)()

-- ===========================================================================
-- runtime
--
-- Pattern taken from the mods that actually work (P2PPing, GalacticMenuHotkey,
-- AutoReloadRounds): do NOT gate on any global.  Hook `update`, then try to
-- initialise on every frame.  Early failures are expected and merely logged
-- (throttled); the tick simply keeps trying until the game is ready.
-- ===========================================================================
local state = { notice = '打开配装界面后点选护甲' }

local function start(g)
    local ffi, kernel, engine = g.ffi, g.kernel, g.engine
    local game = g.game
    if not game or game == 0 then return nil, 'game.dll not found' end

    local api = g.api
    -- build gate: only run against the game build whose offsets we verified
    local dos = api.read(game, 64)
    Log.write(string.format('probe game=0x%X dos=%s type=%s',
        tonumber(game) or -1, tostring(dos ~= nil), type(dos)))
    if not dos or dos:sub(1, 2) ~= 'MZ' then return nil, 'module unreadable' end
    local pe = api.u32(dos, 60)
    local head = api.read(game + pe, 88)
    if not head or head:sub(1, 4) ~= 'PE\0\0' then return nil, 'bad PE header' end
    local dll_stamp = api.u32(head, 8)
    local dll_size = api.u32(head, 80)
    local known = KNOWN_BUILDS[dll_stamp]
    Log.write(string.format('compat.game_dll_stamp=%d size=%d', dll_stamp, dll_size))
    if not known or known[4] ~= dll_size then
        return nil, 'unsupported game build'
    end

    local ctx = { ffi = ffi, kernel = kernel, engine = engine, api = api, game = game }
    local native, why = Native.bind(ctx)
    if not native then return nil, why end
    ctx.native = native
    if _G.__HD2SWAP_NATIVE_HOOK then ctx.native_hook = _G.__HD2SWAP_NATIVE_HOOK end
    -- The native setters take the *resolved catalog pointer*, not the address
    -- of the global (DiverKit passes plan.catalog = pointer(game+0x33264f8)).
    local gear_global = api.read(game + ADDR.gear, 8)
    ctx.gear_manager = gear_global and api.pointer(gear_global) or nil
    Log.write('gear.catalog=0x' .. string.format('%X', ctx.gear_manager or 0))
    if not ctx.gear_manager then return nil, 'gear catalog pointer unavailable' end

    local pointer = Pointer.new(ffi, kernel, engine)
    local panel = Panel.new(engine)
    local screen_token
    -- exported for offline tests only; harmless in game
    _G.__HD2SWAP_DEBUG = { pointer = pointer, panel = panel, ctx = ctx }

    ctx.ready = true
    Log.write('ready=true')
    local tick_count = 0

    -- debug hook: expose the panel's live hit regions so an offline test can
    -- click precisely instead of guessing coordinates
    local debug_regions = {}
    ctx.debug_regions = debug_regions

    return function()
        tick_count = tick_count + 1
        debug_regions.regions = panel.regions
        debug_regions.token = screen_token
        if tick_count == 1 or tick_count % 100 == 0 then
            Log.write('tick=' .. tick_count)
        end
        local current_token, box, info = Screen.identity(ctx)
        if current_token ~= screen_token then
            screen_token = current_token
            pointer:reset()
            panel:clear()
            Log.write('screen.visible=' .. tostring(current_token ~= nil))
        end
        if not current_token then return end
        local input = pointer:sample()
        if not input then
            pointer:reset()
            return
        end

        local hit = panel:hit(input.x, input.y)
        panel.hover = hit
        local clicked = pointer:step(input, hit)
        if clicked and ARMORS[clicked] then
            local armor = ARMORS[clicked]
            -- NOTE: Swap.apply returns (ok, message) — pcall yields
            -- (ok, returned1, returned2), so capture all three.
            local pcall_ok, apply_ok, apply_msg = pcall(Swap.apply, ctx, armor.id)
            local text
            if not pcall_ok then
                text = tostring(apply_ok)                 -- the thrown error
            else
                text = apply_ok and tostring(apply_msg) or tostring(apply_msg)
            end
            state.notice = tostring(text or '?'):gsub('^.-:%d+: ', '')
            state.selected = clicked
            Log.write(string.format('apply %s 0x%08X ok=%s -> %s',
                armor.zh, armor.id, tostring(apply_ok), state.notice))
            -- do NOT clear the panel here: clearing rebuilds it every frame and
            -- was re-arming the click state machine.  Just force a redraw.
            panel.signature = nil
        end

        local ok, why2 = pcall(function()
            panel:draw(ctx, {
                box = box,
                selected = state.selected or 1,
                hover = panel.hover,
                notice = state.notice,
            })
        end)
        if not ok then
            local text = tostring(why2):gsub('^.-:%d+: ', '')
            if ctx.ui_error ~= text then
                ctx.ui_error = text
                Log.write('ui.error=' .. text)
            end
        elseif tick_count <= 2 or tick_count % 300 == 0 then
            Log.write(string.format('draw box=%.0f,%.0f,%.0f,%.0f text=%d rect=%d',
                box.x, box.y, box.w, box.h, 0, 0))
        end
    end
end

-- ===========================================================================
-- hooks -- installed immediately; initialisation is retried every frame
-- ===========================================================================
local previous_update, previous_shutdown = rawget(_G, 'update'), rawget(_G, 'shutdown')
local ticker, started, stopped = nil, false, false
local attempts, last_reason = 0, nil
local ffi_ready = false
local kernel, engine, ffi_lib

local function prepare_ffi()
    if ffi_ready then return kernel ~= nil end
    local ok, ffi = pcall(require, 'ffi')
    if not ok or not ffi then return false end
    ffi_lib = ffi
    pcall(ffi.cdef, [[
        void *GetModuleHandleA(const char *name);
        void *GetCurrentProcess(void);
        uint32_t GetCurrentProcessId(void);
        typedef struct { int32_t x, y; } HD2SwapPoint;
        typedef struct { int32_t left, top, right, bottom; } HD2SwapRect;
        int ReadProcessMemory(void *, const void *, void *, size_t, size_t *);
        int WriteProcessMemory(void *, void *, const void *, size_t, size_t *);
        size_t VirtualQuery(const void *, void *, size_t);
        void *GetForegroundWindow(void);
        uint32_t GetWindowThreadProcessId(void *, void *);
        int GetCursorPos(void *);
        int ScreenToClient(void *, void *);
        int GetClientRect(void *, void *);
    ]])
    local ok2, k = pcall(ffi.load, 'kernel32')
    if not ok2 or not k then return false end
    kernel = k
    ffi_ready = true
    Log.write('ffi.ready=true')
    return true
end

local function try_start()
    if started then return end
    attempts = attempts + 1

    if not prepare_ffi() then
        if last_reason ~= 'ffi' then
            last_reason = 'ffi'
            Log.write('startup.waiting=ffi not ready attempt=' .. attempts)
        end
        return
    end

    engine = rawget(_G, 'stingray')
    if not engine then
        if last_reason ~= 'stingray' then
            last_reason = 'stingray'
            Log.write('startup.waiting=stingray missing attempt=' .. attempts)
        end
        return
    end

    local handle = kernel.GetModuleHandleA('game.dll')
    local game = handle and ffi_lib.cast('intptr_t', handle)
    if not game or game == 0 then
        if last_reason ~= 'game.dll' then
            last_reason = 'game.dll'
            Log.write('startup.waiting=game.dll handle attempt=' .. attempts)
        end
        return
    end

    local ok, result, why = pcall(start, {
        ffi = ffi_lib, kernel = kernel, engine = engine,
        api = make_api(ffi_lib, kernel), game = game,
    })
    if not ok then
        -- a hard error: log once and stop trying
        Log.write('startup.failed=' .. tostring(result))
        started = true
        return
    end
    if not result then
        -- not ready yet: remember why (throttled) and retry next frame
        if why ~= last_reason then
            last_reason = why
            Log.write('startup.waiting=' .. tostring(why) .. ' attempt=' .. attempts)
        end
        return
    end

    ticker = result
    started = true
    Log.write('scheduled=true')
end

update = function(...)
    local result = previous_update and previous_update(...) or nil
    if not stopped then
        if not started then
            local ok, why = pcall(try_start)
            if not ok then
                Log.write('startup.error=' .. tostring(why))
                stopped = true
            end
        end
        if ticker then
            local ok, why = pcall(ticker)
            if not ok then
                local text = tostring(why):gsub('^.-:%d+: ', '')
                if last_reason ~= 'tick:' .. text then
                    last_reason = 'tick:' .. text
                    Log.write('runtime.error=' .. text)
                end
            end
        end
    end
    return result
end

shutdown = function(...)
    stopped = true
    Log.write('finish_reason=shutdown')
    Log.close()
    if previous_shutdown then return previous_shutdown(...) end
end

-- exposed for the offline smoke test (harmless in game)
return { name = MODULE, status = 'scheduled', debug = _G.__HD2SWAP_DEBUG }
