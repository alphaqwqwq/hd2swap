"""End-to-end offline test: run the addon, read the real panel hit regions,
click a row, and verify the helmet slot actually changed through the game API."""
import sys
sys.path.insert(0, r'D:\SteamLibrary\steamai\HD2Swap\test')
from lupa.luajit21 import LuaRuntime

addon = r'D:\SteamLibrary\steamai\HD2Swap\src\head_swap.lua'
H = open(r'D:\SteamLibrary\steamai\HD2Swap\test\smoke_test.py', encoding='utf-8').read()
s = H.index("HARNESS = r'''") + len("HARNESS = r'''")
e = H.index("'''", s)
head = H[s:e]
head = head[:head.index('-- ===========================================================================\n-- 7) run the addon')]
src = open(addon, encoding='utf-8').read()

probe = r'''
local out = {}
local ffi = require('ffi')
local k = ffi.load('kernel32')

local function helmet()
    local buf = ffi.new('uint8_t[4096]')
    local got = ffi.new('size_t[1]')
    k.ReadProcessMemory(k.GetCurrentProcess(), ffi.cast('void *', PAYLOAD + 0x124), buf, 4, got)
    local b = ffi.string(buf, 4)
    return b:byte(1) + b:byte(2)*256 + b:byte(3)*65536 + b:byte(4)*16777216
end
local function armor_body()
    local buf = ffi.new('uint8_t[4096]')
    local got = ffi.new('size_t[1]')
    k.ReadProcessMemory(k.GetCurrentProcess(), ffi.cast('void *', PAYLOAD + 0x12C), buf, 4, got)
    local b = ffi.string(buf, 4)
    return b:byte(1) + b:byte(2)*256 + b:byte(3)*65536 + b:byte(4)*16777216
end

local up = function() local u = rawget(_G,'update'); if u then return pcall(u, 0.016) end end
local fn = loadstring(ADDON_SOURCE, '@addon')
pcall(fn)
up()   -- first tick: identify + draw

local D = rawget(_G, '__HD2SWAP_DEBUG')
out[#out+1] = 'debug table: ' .. tostring(D ~= nil)
if not D then return table.concat(out, '\n') end
local regions = D.panel.regions or {}
out[#out+1] = '#regions = ' .. tostring(#regions)
for i, r in ipairs(regions) do
    out[#out+1] = string.format('  row %s: x=%.0f y=%.0f w=%.0f h=%.0f',
        tostring(r.key), r.x, r.y, r.w, r.h)
end

out[#out+1] = string.format('before: helmet=0x%08X body=0x%08X', helmet(), armor_body())

-- click the centre of row `idx` using the REAL region rectangles
local function click_row(idx)
    local r = regions[idx]
    if not r then return false end
    local cx, cy = r.x + r.w / 2, r.y + r.h / 2
    -- the Pointer converts client pixels -> GUI space as
    --   x = px * rw / w ; y = (h - py) * rh / h
    -- with rw=1920 rh=1080 and client 1920x1080 this is x = px, y = 1080 - py
    local px, py = cx, 1080 - cy
    shim.GetCursorPos = function(ptr)
        local p = ffi.cast('HD2SwapPoint *', ptr)
        p[0].x, p[0].y = px, py
        return 1
    end
    stingray.Mouse.button = function() return false end; up()
    stingray.Mouse.button = function() return true end;  up()
    stingray.Mouse.button = function() return false end; up()
    return true
end

local ok = click_row(1)
out[#out+1] = 'clicked row 1: ' .. tostring(ok)
out[#out+1] = string.format('after : helmet=0x%08X body=0x%08X', helmet(), armor_body())
out[#out+1] = '--- addon log ---'
for _, l in ipairs(log_lines) do out[#out+1] = l end
return table.concat(out, '\n')
'''
L = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
L.execute('ADDON_SOURCE = [==[\n' + src + '\n]==]\nFRAME_COUNT = 3\n')
print(L.eval('(function() ' + head + probe + ' end)()'))
