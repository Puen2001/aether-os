# tools/eyecandy/

Terminal polish for an AETHER OS workbench. Every script is self-contained
(stdlib / POSIX only), resolves the repo root from its own location
(override with `PAI_ROOT`), keeps runtime state in `~/.config/personal-ai/`,
and fails open — a missing dependency degrades or skips, never breaks a session.

## The toys

| Toy | What it shows | How to run |
|---|---|---|
| `splash` | VHS-glitch boot splash of the AETHER mark, settles to brass; skips on non-TTY, `NO_SPLASH=1`, or any keypress during the final freeze | `tools/eyecandy/splash` |
| `logo-anim` | random pick of the braille animations per launch (donut/starfield) so a logo pane varies; pin with `EYECANDY_LOGO_ANIM=<name>` | `tools/eyecandy/logo-anim` |
| `art-fit` | downsamples big ASCII art into an 18x8 portrait tile by area-averaged ink density; writes `~/.config/personal-ai/art/<name>.txt` | `pbpaste \| tools/eyecandy/art-fit logo` |
| `chime` | soft completion (`done`) / attention (`attn`) sound cue; macOS `afplay`, silent elsewhere; `NO_CHIME=1` disables | `tools/eyecandy/chime done` |
| `donut` | spinning tunnel of 72 hue-cycled rings in braille sub-pixels, 24-bit color | `tools/eyecandy/donut` |
| `lorenz` | Lorenz strange attractor traced in braille with a fading trail, slow yaw (wants a large pane) | `tools/eyecandy/lorenz` |
| `starfield` | warp-drive starfield, brass-on-charcoal, brightness by nearness | `tools/eyecandy/starfield` |
| `worldmap` | interactive geo console: Natural Earth coastlines + live quakes / news / ISS / disasters / day-night terminator, zoom/pan/inspect, optional Telegram proximity alerts | `tools/eyecandy/worldmap` |

The splash's full VHS effect needs [terminaltexteffects](https://github.com/ChrisBuilds/terminaltexteffects)
(`pipx install terminaltexteffects`); without `tte` it falls back to a clean
brass draw-in. Everything else is stdlib only.

## Wiring

**Splash on session start** — it needs a real TTY, so wire it into your shell rc
or launcher alias, not a Claude Code hook:

```bash
# ~/.zshrc — show once per interactive login shell
[[ -o login && -t 1 ]] && ~/path/to/aether-os/tools/eyecandy/splash
# or per assistant launch:
alias ai='~/path/to/aether-os/tools/eyecandy/splash; claude'
```

**Chime on turn end** — add it ALONGSIDE your existing Stop hooks in
`.claude/settings.json` (keep `dispatch-trace.py` / `vault-sync.sh`; append the
chime entry to the same `hooks` array):

```json
"Stop": [
  { "matcher": "", "hooks": [
    { "type": "command", "command": "system/hooks/dispatch-trace.py", "timeout": 5 },
    { "type": "command", "command": "system/hooks/vault-sync.sh", "timeout": 60 },
    { "type": "command", "command": "tools/eyecandy/chime done", "timeout": 5 }
  ]}
],
"Notification": [
  { "matcher": "", "hooks": [
    { "type": "command", "command": "tools/eyecandy/chime attn", "timeout": 5 }
  ]}
]
```

**Worldmap data** — one-time download of the public-domain coastline file:

```bash
mkdir -p ~/.config/personal-ai
curl -L -o ~/.config/personal-ai/ne_110m_coastline.geojson \
  https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_coastline.geojson
```

## Knobs

| Env var | Effect |
|---|---|
| `NO_SPLASH=1` | skip the splash entirely |
| `SPLASH_NO_SOUND=1` | splash without the optional boot tone (`~/.config/personal-ai/sounds/boot-chord.wav`) |
| `NO_CHIME=1` | mute the chime |
| `EYECANDY_LOGO_ANIM=donut\|starfield\|lorenz` | pin the logo-pane animation |
| `WORLDMAP_HOME="lat,lon"` | home point for distances, arcs, and the `home` region (default 0,0) |
| `WORLDMAP_OFFLINE=1` | worldmap with no network at all |
| `WORLDMAP_ALERTS=1` | opt-in proximity alerts via `tools/telegram-send` (deduped, rate-capped) |
| `PAI_ROOT=/path` | override repo-root resolution for the worldmap script |
