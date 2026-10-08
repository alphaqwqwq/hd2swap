"""Check whether the panel draw path runs, and simulate a click on row 1."""
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
-- force the cursor into the panel's first row before the first frame runs:
-- the panel draws below/above the Equipment box (box.y=200, h=44), so aim at
-- the anchor area and let hit-testing decide.
local frame = 0
local fn = loadstring(ADDON_SOURCE, '@addon')
local ok, res = pcall(fn)
out[#out+1] = 'exec=' .. tostring(ok) .. ' ' .. tostring(res)

-- make the mouse report "pressed" on frame 5 and "released" on frame 7
local mouse_down = false
local orig_button = stingray.Mouse.button
stingray.Mouse.button = function() return mouse_down end

for i = 1, 40 do
    frame = i
    mouse_down = (i >= 5 and i < 7)
    local u = rawget(_G, 'update')
    if u then
        local fok, ferr = pcall(u, 0.016)
        if not fok then out[#out+1] = 'frame '..i..' err: '..tostring(ferr); break end
    end
end
out[#out+1] = 'gui text calls = ' .. tostring(calls.text)
out[#out+1] = 'gui rect calls = ' .. tostring(calls.rect)
return table.concat(out, '\n')
'''
L = LuaRuntime(unpack_returned_tuples=True, register_eval=False)
L.execute('ADDON_SOURCE = [==[\n' + src + '\n]==]\nFRAME_COUNT = 40\n')
print(L.eval('(function() ' + head + probe + ' end)()'))
