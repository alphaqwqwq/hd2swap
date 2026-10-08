"""Diagnose Screen.identity against the fake game: report which guard fails."""
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
local function u32(str, off)
    local b = { str:byte(off+1, off+4) }
    return b[1] + b[2]*256 + b[3]*65536 + b[4]*16777216
end
local function read(a, n)
    local buf = ffi.new('uint8_t[4096]')
    local got = ffi.new('size_t[1]')
    if k.ReadProcessMemory(k.GetCurrentProcess(), ffi.cast('void *', a), buf, n, got) == 0 then return nil end
    local str = ffi.string(buf, n)
    local want = k.ReadProcessMemory and 0
    return str
end

local game = 0x7FF000000000
local function rd(a, n) 
    local buf = ffi.new('uint8_t[4096]')
    local got = ffi.new('size_t[1]')
    local ret = k.ReadProcessMemory(k.GetCurrentProcess(), ffi.cast('void *', a), buf, n, got)
    if ret == 0 then return nil end
    return ffi.string(buf, n)
end

out[#out+1] = '--- Screen.identity guard walk ---'
local manager_b = rd(game + 0x3326E68, 8)
local session_b = rd(game + 0x347CEF0, 8)
out[#out+1] = 'manager_b=' .. tostring(manager_b and #manager_b)
local function ptr(b) 
    if not b or #b < 8 then return nil end
    local lo = u32(b,0); local hi = u32(b,4)
    local v = hi*4294967296 + lo
    if v == 0 then return nil end
    return v
end
local manager = ptr(manager_b); local session = ptr(session_b)
if not manager or not session then
    out[#out+1] = 'ABORT: manager=' .. tostring(manager) .. ' session=' .. tostring(session)
    return table.concat(out, '\n')
end
out[#out+1] = 'manager=0x' .. tostring(manager and string.format('%X',manager))
out[#out+1] = 'session=0x' .. tostring(session and string.format('%X',session))

local bucket = rd(manager + 0x62A0, 24)
out[#out+1] = 'bucket count=' .. tostring(bucket and u32(bucket,0))
out[#out+1] = 'bucket type =' .. tostring(bucket and u32(bucket,16))
local owner = ptr(bucket)
out[#out+1] = 'owner=0x' .. tostring(owner and string.format('%X',owner))
local view = rd(owner+8,4)
out[#out+1] = 'view=' .. tostring(view and u32(view,0))
out[#out+1] = 'owner+0x273990 byte=' .. tostring(rd(owner+0x273990,1))
out[#out+1] = 'owner+0x2808 byte  =' .. tostring(rd(owner+0x2808,1))
local sb = rd(owner+0x27D0,4)
out[#out+1] = 'slot=' .. tostring(sb and u32(sb,0))
local peer = rd(session+0xB398,8)
out[#out+1] = 'peer=' .. tostring(peer and #peer)
out[#out+1] = 'peer_match=' .. tostring(rd(owner+0*0x9F0+0x9F8,8) == peer)
return table.concat(out, '\n')
'''
L = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
L.execute('ADDON_SOURCE = [==[\n' + src + '\n]==]\nFRAME_COUNT = 3\n')
print(L.eval('(function() ' + head + probe + ' end)()'))
