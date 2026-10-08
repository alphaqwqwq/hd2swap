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
for i = 1, 20 do
    local u = rawget(_G, 'update')
    if u then local ok, err = pcall(u, 0.016)
        if not ok then out[#out+1] = 'frame err: '..tostring(err); break end
    end
end
out[#out+1] = 'gui text=' .. tostring(calls.text) .. ' rect=' .. tostring(calls.rect)
out[#out+1] = '--- addon log ---'
for _, l in ipairs(log_lines) do out[#out+1] = l end
return table.concat(out, '\n')
'''
L = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
L.execute('ADDON_SOURCE = [==[\n' + src + '\n]==]\nFRAME_COUNT = 20\n')
print(L.eval('(function() ' + head + probe + ' end)()'))
