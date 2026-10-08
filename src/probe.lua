-- HD2-Addon: mods/hd2swap/probe

-- Minimal load probe. It does nothing except announce that the module ran,
-- so we can confirm the whole toolchain (archive -> zip -> Arsenal -> loader).

local MODULE = 'mods/hd2swap/probe'
local VERSION = 'v1'

local function log(line)
    local loader = rawget(_G, 'CowboyBingusModLoader')
    if loader and type(loader.open_log) == 'function' then
        local ok, file = pcall(function() return loader.open_log('HD2Swap.log') end)
        if ok and file then
            pcall(function()
                file:write(line .. '\n')
                file:flush()
            end)
            return
        end
    end
    print('[' .. MODULE .. '] ' .. line)
end

log('=== HD2Swap probe ' .. VERSION .. ' ===')
log('module=' .. MODULE)
log('loaded=true')
log('lua_version=' .. tostring(_VERSION))
log('loader_api=' .. tostring(loader_api or (rawget(_G, 'CowboyBingusModLoader') or {}).api))
log('game_session=' .. tostring(rawget(_G, 'GameSession') ~= nil))

return { name = MODULE, status = 'loaded' }
