"""Offline smoke-test harness for HD2Swap Lua addons.

Runs an addon inside a real LuaJIT (Lua 5.1 + FFI, same as the game) against a
FAKE game process, so pure logic errors surface here instead of in game:
  * nil indexing / typos / scoping / FFI misuse
  * wrong payload offsets, missing commit, rejected writes
  * whether the GUI draw path actually runs

Everything is serialised to a string before returning to Python: handing Lua
tables across the lupa bridge trips on metatable lookups.

Usage:
    python smoke_test.py <addon.lua> [--frames N] [--verbose]
"""

import argparse
import sys

from lupa.luajit21 import LuaRuntime

HARNESS = r'''
-- ===========================================================================
-- 1) synthetic process image we can read and write
-- ===========================================================================
local BASE = 0x7FF000000000
local HEAP = {}
local function put(addr, bytes) HEAP[addr] = bytes end
local function get(addr, size)
    local out = {}
    for i = 1, size do out[i] = '\0' end
    for a, chunk in pairs(HEAP) do
        for i = 0, #chunk - 1 do
            local off = a + i - addr
            if off >= 0 and off < size then out[off + 1] = chunk:sub(i + 1, i + 1) end
        end
    end
    return table.concat(out)
end
local function put_u32(addr, v)
    put(addr, string.char(v % 256, math.floor(v / 256) % 256,
                          math.floor(v / 65536) % 256, math.floor(v / 16777216) % 256))
end
local function put_u64(addr, v)
    put_u32(addr, v % 4294967296)
    put_u32(addr + 4, math.floor(v / 4294967296))
end
local function get_u32(addr)
    local s = get(addr, 4)
    return s:byte(1) + s:byte(2) * 256 + s:byte(3) * 65536 + s:byte(4) * 16777216
end
local function put_f32(addr, v)
    local ffi = require('ffi')
    put(addr, ffi.string(ffi.new('float[1]', v), 4))
end

-- ===========================================================================
-- 2) FFI shim: a fake kernel32 backed by HEAP
-- ===========================================================================
local ffi = require('ffi')
local shim = {}
shim.GetModuleHandleA = function(name)
    if name == 'game.dll' then return BASE end
    if name == 'helldivers2.exe' then return BASE - 0x1000000 end
    return nil
end
shim.GetCurrentProcess = function() return 0x1 end
shim.GetCurrentProcessId = function() return 1234 end
shim.GetTickCount64 = function() return 123456 end
shim.ReadProcessMemory = function(_, addr, buf, size, read)
    local a = tonumber(ffi.cast('uintptr_t', addr))
    if a < 65536 then return 0 end
    local s = get(a, size)
    ffi.copy(buf, s, size)
    if read ~= nil then read[0] = size end
    return 1
end
shim.WriteProcessMemory = function(_, addr, buf, size, written)
    local a = tonumber(ffi.cast('uintptr_t', addr))
    if a < 65536 then return 0 end
    put(a, ffi.string(buf, size))
    if written ~= nil then written[0] = size end
    return 1
end
shim.VirtualQuery = function(_, buf, size)
    if size >= 48 then
        local s = string.rep('\0', 48)
        s = s:sub(1, 32) .. string.char(0x00, 0x10, 0x00, 0x00)
            .. string.char(0x20, 0x00, 0x00, 0x00) .. s:sub(41)
        ffi.copy(buf, s, 48)
    end
    return 48
end
shim.GetForegroundWindow = function() return 0x1 end
shim.GetWindowThreadProcessId = function(win, pid)
    local ffi2 = require('ffi')
    if pid ~= nil then ffi2.cast('uint32_t *', pid)[0] = 1234 end
    return 1
end
shim.GetCursorPos = function() return 0 end
shim.ScreenToClient = function() return 0 end
shim.GetClientRect = function() return 0 end

-- user32 entry points the Pointer module needs
shim.GetCursorPos = function(ptr) 
    -- leave the point at (10,10) so hit-testing has something real
    local ffi2 = require('ffi')
    local p = ffi2.cast('HD2SwapPoint *', ptr)
    p[0].x, p[0].y = 10, 10
    return 1
end
shim.ScreenToClient = function(win, ptr) return 1 end
shim.GetClientRect = function(win, ptr)
    local ffi2 = require('ffi')
    local r = ffi2.cast('HD2SwapRect *', ptr)
    r[0].left, r[0].top, r[0].right, r[0].bottom = 0, 0, 1920, 1080
    return 1
end
local kernel_proxy = setmetatable({}, {
    __index = function(_, k)
        local v = shim[k]
        if v == nil then error('kernel32 shim missing: ' .. tostring(k), 2) end
        return v
    end,
})
shim.load = function() return kernel_proxy end

-- what the addon's require('ffi') must return: a proxy whose .load() works
-- and whose .cdef is a no-op
local ffi_proxy = setmetatable({}, {
    __index = function(_, k)
        local real = ffi[k]
        if real ~= nil then return real end
        if k == 'load' then return function() return kernel_proxy end end
        if k == 'cdef' then return function() end end
        return function() return nil end
    end,
})

-- ===========================================================================
-- 2b) make require('ffi') return a proxy whose .load() gives the fake kernel
--     (the addon calls ffi.load('kernel32') itself, so we must intercept it)
-- ===========================================================================
local real_require = require
local cached_ffi = nil
require = function(name)
    if name == 'ffi' then
        if cached_ffi then return cached_ffi end
        local real = real_require('ffi')
        cached_ffi = setmetatable({}, {
            __index = function(_, k)
                if k == 'load' then return function() return kernel_proxy end end
                return real[k]
            end,
        })
        return cached_ffi
    end
    return real_require(name)
end

-- ===========================================================================
-- 3) recording spies
-- ===========================================================================
local calls = { text = 0, rect = 0, material = 0, commit = 0, setter = 0 }
local log_lines = {}


-- offline stub for the native setter/commit: we must never jump into fake
-- memory, so the harness installs Lua stubs the addon will prefer.
_G.__HD2SWAP_NATIVE_HOOK = {
    helmet = function(catalog, player, id)
        calls.setter = calls.setter + 1
        calls.last_setter = string.format('helmet(catalog=0x%X, player=0x%X, id=0x%08X)',
            tonumber(catalog) or 0, player, id)
    end,
    commit = function(payload)
        calls.commit = calls.commit + 1
        calls.last_commit = string.format('commit(payload=0x%X)', payload)
    end,
    armor = function() calls.setter = calls.setter + 1 end,
}

-- ===========================================================================
-- 4) seed the fake game
-- ===========================================================================
local ARMOR_ID  = 0x5D0D8002   -- row 1 of the addon list (TG-8)
local HELMET_ID = 0x58716E11
local CAT_PTR   = BASE + 0x33264F8
local MGR_PTR   = BASE + 0x3326E68
local SESSION_PTR = BASE + 0x347CEF0
local MANAGER   = BASE + 0x30000
local SESSION   = BASE + 0x31000
local OWNER     = BASE + 0x40000
local ARRAY     = BASE + 0x20000

put_u64(CAT_PTR, MANAGER)
put_u64(MGR_PTR, MANAGER)
put_u64(SESSION_PTR, SESSION)
put_u64(MANAGER, ARRAY)              -- [0] = gear catalog array ptr
-- NOTE: this collides with the owner bucket layout; the addon uses the same
-- pointer for both, exactly like DiverKit does, so keep the layouts separate.
put_u64(MANAGER, ARRAY)
put_u32(MANAGER + 8, 9)              -- catalog count

local ids  = { ARMOR_ID, HELMET_ID, 0xBD961A7C, 0x05E56EE5,
               0x5D0D8002, 0x5F075DC5, 0xF8B8CF9B, 0xF7E6F127, 0xD52BB413 }
-- categories: 0=armour 1=helmet 2=cape
local cats = { 0, 1, 2, 0, 0, 0, 0, 0, 0 }
for i = 0, 8 do
    local item = BASE + 0x50000 + i * 0x100
    put_u64(ARRAY + i * 8, item)
    put_u32(item, ids[i + 1])
    put_u32(item + 0x28, cats[i + 1])
end

put_u64(SESSION + 0xB398, 0x1122334455667788)

-- ===========================================================================
-- 5) fake loader + engine
-- ===========================================================================
CowboyBingusModLoader = {
    api = 1,
    log_directory = 'X:/fake/Logs',
    open_log = function()
        return {
            write = function(_, s) log_lines[#log_lines + 1] = tostring(s) end,
            flush = function() end,
            close = function() end,
        }
    end,
}

stingray = {
    Gui = {
        resolution = function() return 1920, 1080 end,
        rect = function() calls.rect = calls.rect + 1 end,
        text = function() calls.text = calls.text + 1 end,
        material = function() calls.material = calls.material + 1; return {} end,
        text_extents = function() return nil, nil end,
    },
    World = {
        create_screen_gui = function() return {} end,
        destroy_gui = function() end,
    },
    Application = {
        main_world = function() return 'MAIN' end,
        worlds = function() return { 'MAIN', 'HUD' } end,
        can_get = function() return true end,
    },
    Mouse = {
        button_id = function() return 1 end,
        button = function() return false end,
    },
    IdString64 = { from_hex = function(h) return h end },
    Material = {
        set_scalar = function() end, set_vector2 = function() end,
        set_vector4 = function() end, set_texture = function() end,
    },
    Vector2 = function(x, y) return { x = x, y = y } end,
    Vector3 = function(x, y, z) return { x = x, y = y, z = z } end,
    Vector4 = function(x, y, z, w) return { x = x, y = y, z = z, w = w } end,
    Color = function(a, r, g, b) return { a = a, r = r, g = g, b = b } end,
}

-- payload: OWNER + slot*0x9F0 + 0x10
local PAYLOAD = OWNER + 0x10
-- owner bucket in the manager: count=1, type=0xE5, owner ptr
put(OWNER + 8, string.char(1, 0, 0, 0))           -- view = 1 (loadout screen)
put(OWNER + 0x273990, '\0\0\0\0')
put(OWNER + 0x2808, '\0\0\0\0')
put_u32(OWNER + 0x27D0, 0)                        -- slot 0
put_u64(OWNER + 0x9F8, 0x1122334455667788)        -- peer match
put_u32(PAYLOAD + 0x124, HELMET_ID)               -- current helmet

local CARD = OWNER + 0x53A78
put_u64(CARD + 0x1EDF0, PAYLOAD)
put_u32(CARD + 0x1EDFC, 0)
put_u32(CARD + 0x1EDF8, 0xABCD)

local WIDGET = CARD + 0x1B820
put_u32(WIDGET, 0x10)
put_f32(WIDGET + 84, 1.0)
put_f32(WIDGET + 100, 1.0)
put_f32(WIDGET + 140, 1.0)
put_f32(WIDGET + 148, 100.0)
put_f32(WIDGET + 156, 200.0)
put_f32(WIDGET + 36, 420.0)
put_f32(WIDGET + 40, 44.0)

-- manager as owner-bucket holder (DiverKit reads manager+0x62A0)
local BUCKET = MANAGER + 0x62A0
put_u32(BUCKET, 1)
put_u32(BUCKET + 16, 0xE5)
put_u64(BUCKET + 8, OWNER)


-- GUI handle globals the panel resolves (font / atlas / material)
local FONT_G   = BASE + 0x3772268
local ATLAS_G  = BASE + 0x3772EE8
local MAT_G    = BASE + 0x37C5478
local MAT_OBJ  = BASE + 0x60000
put_u64(FONT_G,  0x1122334455667788)
put_u64(ATLAS_G, 0x99AABBCCDDEEFF00)
put_u64(MAT_G, MAT_OBJ)
put_u64(MAT_OBJ + 24, 0x0F1E2D3C4B5A6978)

-- ===========================================================================
-- 6) PE header so the build gate passes
-- ===========================================================================
do
    local pe = 0x80
    local head = string.rep('\0', 88)
    head = 'PE\0\0' .. head:sub(5)
    head = head:sub(1, 4) .. string.char(0x64, 0x86)                  -- Machine x64
        .. string.char(0x02, 0x00) .. head:sub(9, 22)
        .. string.char(0x0B, 0x02) .. head:sub(25)                    -- Magic PE32+
    local stamp, size = 1790161983, 74727424
    head = head:sub(1, 8)
        .. string.char(stamp % 256, math.floor(stamp / 256) % 256,
                       math.floor(stamp / 65536) % 256, math.floor(stamp / 16777216) % 256)
        .. head:sub(13)
    head = head:sub(1, 80)
        .. string.char(size % 256, math.floor(size / 256) % 256,
                       math.floor(size / 65536) % 256, math.floor(size / 16777216) % 256)
        .. head:sub(85)
    put(BASE, 'MZ' .. string.rep('\0', 58) .. string.char(pe, 0, 0, 0))
    put(BASE + pe, head)
end

-- ===========================================================================
-- 7) run the addon
-- ===========================================================================
local R = { ok = false }
local ok, err = pcall(function()
    local fn, cerr = loadstring(ADDON_SOURCE, '@addon')
    if not fn then R.stage, R.error = 'compile', tostring(cerr); return end
    local ok2, res = pcall(fn)
    if not ok2 then R.stage, R.error = 'execute', tostring(res); return end
    R.result = res
    R.ok = true
end)
if not ok then R.stage, R.error = 'harness', tostring(err) end

if R.ok then
    for i = 1, FRAME_COUNT do
        local update = rawget(_G, 'update')
        if type(update) ~= 'function' then
            R.frame_error = 'update hook not installed'
            break
        end
        local fok, ferr = pcall(update, 0.016)
        if not fok then
            R.frame_error = 'frame ' .. i .. ': ' .. tostring(ferr)
            break
        end
    end
    local shutdown = rawget(_G, 'shutdown')
    if type(shutdown) == 'function' then pcall(shutdown) end
    R.helmet_after = get_u32(PAYLOAD + 0x124)
    R.expect = ARMOR_ID
end

-- ===========================================================================
-- 8) serialise to a string (never hand Lua tables to the bridge)
-- ===========================================================================
local out = {}
out[#out + 1] = 'ok=' .. tostring(R.ok)
out[#out + 1] = 'stage=' .. tostring(R.stage or '')
out[#out + 1] = 'error=' .. tostring(R.error or '')
out[#out + 1] = 'frame_error=' .. tostring(R.frame_error or '')
out[#out + 1] = 'helmet_after=' .. tostring(R.helmet_after or -1)
out[#out + 1] = 'expect=' .. tostring(R.expect or -1)
out[#out + 1] = 'gui_text=' .. tostring(calls.text)
out[#out + 1] = 'gui_rect=' .. tostring(calls.rect)
out[#out + 1] = 'nametype=' .. type(R.result)
if type(R.result) == 'table' then
    out[#out + 1] = 'name=' .. tostring(R.result.name)
    out[#out + 1] = 'status=' .. tostring(R.result.status)
end
out[#out + 1] = 'LOG_BEGIN'
for i, line in ipairs(log_lines) do out[#out + 1] = line end
out[#out + 1] = 'LOG_END'
return table.concat(out, '\n')
'''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('addon')
    ap.add_argument('--frames', type=int, default=400)
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args()

    src = open(a.addon, encoding='utf-8').read()
    L = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
    L.execute('ADDON_SOURCE = [==[\n' + src + '\n]==]\nFRAME_COUNT = %d\n' % a.frames)

    try:
        text = L.eval('(function() ' + HARNESS + ' end)()')
    except Exception as e:
        print('!!! harness threw:', type(e).__name__, e)
        return 2

    print('=== run ===')
    in_log = False
    log = []
    fields = {}
    for line in str(text).splitlines():
        if line == 'LOG_BEGIN':
            in_log = True
            continue
        if line == 'LOG_END':
            in_log = False
            continue
        if in_log:
            log.append(line)
        else:
            k, _, v = line.partition('=')
            fields[k] = v

    bad = False
    if fields.get('ok') != 'true':
        bad = True
        print('  FAILED stage:', fields.get('stage'))
        print('  error:', fields.get('error'))
    if fields.get('frame_error'):
        bad = True
        print('  FRAME ERROR:', fields['frame_error'])
    if fields.get('status') != 'scheduled':
        bad = True
        print('  addon did not report scheduled:', fields.get('status'))

    print('  module     :', fields.get('name'), fields.get('status'))
    print('  gui calls  : text=%s rect=%s' % (fields.get('gui_text'), fields.get('gui_rect')))
    try:
        ha, ex = int(fields.get('helmet_after')), int(fields.get('expect'))
        print('  helmet slot: 0x%08X (want 0x%08X) -> %s'
              % (ha, ex, 'SWAPPED' if ha == ex else 'NOT swapped'))
    except Exception:
        pass

    print('  log (%d lines):' % len(log))
    for line in (log if a.verbose else log[:40]):
        print('   |', line)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
