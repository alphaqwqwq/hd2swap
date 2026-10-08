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
local fn = loadstring(ADDON_SOURCE, '@addon')
pcall(fn)

-- capture the addon's own ui.error path by intercepting pcall-free draw
local u = rawget(_G, 'update')
for i = 1, 10 do if u then pcall(u, 0.016) end end

out[#out+1] = 'gui text=' .. tostring(calls.text) .. ' rect=' .. tostring(calls.rect) .. ' material=' .. tostring(calls.material)
out[#out+1] = '--- direct reads (mimic gui_handles) ---'
local ffi = require('ffi')
local k = ffi.load('kernel32')
local function rd(a, n)
    local buf = ffi.new('uint8_t[4096]')
    local got = ffi.new('size_t[1]')
    if k.ReadProcessMemory(k.GetCurrentProcess(), ffi.cast('void *', a), buf, n, got) == 0 then return nil end
    return ffi.string(buf, n)
end
local game = 0x7FF000000000
local function hex8(bytes)
    if not bytes then return 'NIL' end
    local o = {}
    for i = #bytes, 1, -1 do o[#o+1] = string.format('%02x', bytes:byte(i)) end
    return table.concat(o)
end
out[#out+1] = 'font  @0x3772268 = ' .. hex8(rd(game + 0x3772268, 8))
out[#out+1] = 'atlas @0x3772EE8 = ' .. hex8(rd(game + 0x3772EE8, 8))
local mb = rd(game + 0x37C478, 8)
out[#out+1] = 'mat   @0x37C478  = ' .. hex8(mb)
local function u32(str, off) local b={str:byte(off+1,off+4)} return b[1]+b[2]*256+b[3]*65536+b[4]*16777216 end
local function u64(str, off) return u32(str,off) + u32(str,off+4)*4294967296 end
if mb then
    local mp = u64(mb, 0)
    out[#out+1] = 'mat ptr = 0x' .. string.format('%X', mp)
    out[#out+1] = 'mat+24  = ' .. hex8(rd(mp + 24, 8))
end
out[#out+1] = '--- addon log ---'
for _, l in ipairs(log_lines) do out[#out+1] = l end
return table.concat(out, '\n')
'''
L = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
L.execute('ADDON_SOURCE = [==[\n' + src + '\n]==]\nFRAME_COUNT = 10\n')
print(L.eval('(function() ' + head + probe + ' end)()'))
