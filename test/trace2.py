"""Trace the addon's own api.read by wrapping the object the addon builds.

We let the addon call make_api itself, then intercept by monkey-patching the
FFI proxy's `string` and `cast` so every api.read is visible.
"""
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

-- wrap the requirable ffi so we can see what the addon receives
local real = require
local seen = {}
package.loaded['ffi'] = setmetatable({}, {
    __index = function(_, k)
        if seen[k] == nil then seen[k] = 0 end
        seen[k] = seen[k] + 1
        if k == 'new' then
            return function(...)
                local a = {...}
                if type(a[1]) == 'string' and a[1]:find('uint8_t') then
                    out[#out+1] = 'ffi.new(' .. tostring(a[1]) .. ', ' .. tostring(a[2]) .. ')'
                end
                return ffi.new(...)
            end
        end
        return ffi[k]
    end,
})

-- ALSO wrap the kernel the addon will load
local RPM = shim.ReadProcessMemory
shim.ReadProcessMemory = function(proc, addr, buf, size, read)
    local a = tonumber(ffi.cast('uintptr_t', addr))
    local r = RPM(proc, addr, buf, size, read)
    out[#out+1] = string.format('RPM(0x%X, %d) -> %s', a, size, tostring(r))
    return r
end

local fn = loadstring(ADDON_SOURCE, '@addon')
local ok, res = pcall(fn)
out[#out+1] = 'exec=' .. tostring(ok) .. ' ' .. tostring(res)
if ok then
    for i = 1, 3 do
        local u = rawget(_G, 'update')
        if u then pcall(u, 0.016) end
    end
end
out[#out+1] = '--- ffi field access counts ---'
for k, v in pairs(seen) do out[#out+1] = '  ' .. k .. ' = ' .. v end
return table.concat(out, '\n')
'''
L = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
L.execute('ADDON_SOURCE = [==[\n' + src + '\n]==]\nFRAME_COUNT = 3\n')
print(L.eval('(function() ' + head + probe + ' end)()'))
