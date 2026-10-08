"""Smoke test that TRACES the addon: wraps api.read/write so every call is
logged with its arguments and result, then runs the real addon and dumps the
trace.  This is how we find the failing call without guessing.
"""

import re
import sys

sys.path.insert(0, r'D:\SteamLibrary\steamai\HD2Swap\test')
from lupa.luajit21 import LuaRuntime

addon = r'D:\SteamLibrary\steamai\HD2Swap\src\head_swap.lua'
H = open(r'D:\SteamLibrary\steamai\HD2Swap\test\smoke_test.py', encoding='utf-8').read()
s = H.index("HARNESS = r'''") + len("HARNESS = r'''")
e = H.index("'''", s)
harness = H[s:e]
src = open(addon, encoding='utf-8').read()

# cap the harness at the "run the addon" marker and append a traced run
head = harness[:harness.index('-- ===========================================================================\n-- 7) run the addon')]

trace = r'''
-- ---------------------------------------------------------------------------
-- traced run: monkey-patch ffi.cast/ffi.new counters and wrap the fake RPM
-- ---------------------------------------------------------------------------
local out = {}
local ffi = require('ffi')

-- expose a probe the addon's make_api will use
local real_rpm = shim.ReadProcessMemory
local rpm_log = {}
shim.ReadProcessMemory = function(proc, addr, buf, size, read)
    local a = tonumber(ffi.cast('uintptr_t', addr))
    local ret = real_rpm(proc, addr, buf, size, read)
    if #rpm_log < 40 then
        rpm_log[#rpm_log+1] = string.format('RPM addr=0x%X size=%d ret=%s got=%s',
            a, size, tostring(ret), tostring(read and read[0]))
    end
    return ret
end

local fn, cerr = loadstring(ADDON_SOURCE, '@addon')
if not fn then out[#out+1] = 'COMPILE ERROR: ' .. tostring(cerr) else
    local ok, res = pcall(fn)
    out[#out+1] = 'exec ok=' .. tostring(ok) .. ' err=' .. tostring(res)
    if ok then
        for i = 1, 5 do
            local u = rawget(_G, 'update')
            if type(u) ~= 'function' then out[#out+1] = 'no update'; break end
            local fok, ferr = pcall(u, 0.016)
            if not fok then out[#out+1] = 'frame error: ' .. tostring(ferr); break end
        end
    end
end
out[#out+1] = '--- rpm log ---'
for _, l in ipairs(rpm_log) do out[#out+1] = l end
return table.concat(out, '\n')
'''

L = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
L.execute('ADDON_SOURCE = [==[\n' + src + '\n]==]\nFRAME_COUNT = 5\n')
print(L.eval('(function() ' + head + trace + ' end)()'))
