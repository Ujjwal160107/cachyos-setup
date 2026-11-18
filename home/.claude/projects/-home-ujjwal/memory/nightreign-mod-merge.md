---
name: nightreign-mod-merge
description: Merged Nightreign mod (MMV 2.1.8-hf3 + FIA v31_U02 + Everdark 1.83; LM and deflect removed 2026-11-03) built by ~/dev/nr-modmerge/build.py; Everdark build untested in game
metadata:
  node_type: memory
  type: project
  originSessionId: 7d4111d5-b67d-4725-98ab-9e10e93787ac
  modified: 2026-11-02T14:55:08.622Z
---

Output: /mnt/win/Users/ujjwa/Downloads/NR Merged (MMV + FIA + LM)/ with Merged_ServerRedirector.me3 (SR ini shipped exactly as FIA has it; user rejected my shard rename 2026-11-02) and Merged_SeamlessCoop.me3, savefile FIA_SAVE.sl2. The user plays on Windows via me3; friends must use the same folder.

Rebuild: `~/dev/nr-modmerge/venv/bin/python -I ~/dev/nr-modmerge/build.py` (venv has soulstruct, texture2ddecoder). Tools in ~/dev/nr-modmerge/tools: regulation/param/paramdef (Smithbox NR defs + vanilla regs in smithbox-defs), bnd4, dcx (KRAK via krak/ Rust CLI, writes DFLT), fmg, tpf, tae + tae_splice, archive (decrypts game bhd).

User decisions: Server Redirector + Seamless both shipped; Limitless Merchant wins every merchant (MMV's expanded shop unreachable); reuse FIA save.

**Why:** MMV's mod page says Seamless is unsupported; both MMV and FIA recommend Server Redirector.
**How to apply:** on a mod update, swap the source paths in work/paths.py and rerun build.py; check the CONFLICT lines in work/build.log. Merged files are written unlinked so the original hard-linked mod files never change.

Sekiro deflect add-on (sekiro_deflect.py, built in): katana guard adds SpEffect 7799000/7799001 cloned from Executor's 707000 (stateInfo 606 = engine 'Deflecting'), hooks in c0000.hks guard start/guard damage/guard break, reuses FIA VFX 71831/71841 and R1 trigger 71821.

A true 11th Nightfarer is blocked: the save has exactly 10 hero loadout slots and heroType 11 already means 'All' (universal vessels). User chose deflect-only, no Wolf port, on 2026-11-02.

Gotcha (fixed 2026-11-02): the game's own zstd decoder rejects regulation.bin frames with window >64 KB ('Frame requires too much memory for decoding'); first build black-screened. regulation.py now writes windowLog 16, no frame flags, DCX attr 0x0f; tests/test_regulation_format.py guards it.

Debug tools (debug_tools.py, built in): DEBUG_<profile>.bat runs me3 with ME3_FILE_LOG_LEVEL=trace and collects console, me3 log, WER crash dumps (debug/Enable_Crash_Dumps.reg) and build_log.txt into logs/<date>_<profile>/ in the merged folder. Ask the user for that folder on failure.

Saves (Steam ID 76561199820097485 = cdc7da6e... inside files): Seamless writes NR0000.co2 regardless of me3 savefile; Server Redirector with CL_USE_ALT_SAVE reads <savefile>.CL_SAVE. On 2026-11-02 the user's real save (NR0000.co2, 114 relics) was copied over a fresh FIA_SAVE.CL_SAVE; full backup in ~/dev/nr-modmerge/save-backup-2026-11-02/. FIA_SAVE.sl2/NR0000.sl2 (183 relics) carry a different Steam ID. The two launchers keep separate saves.

Deflect v2 (2026-11-02, user said v1 felt slow/late/tight): guard interrupts actions like Executor's stance (ExecGuardOnCancelTiming), window 0.25s from press, pre-guard frontal hits deflected in ExecDamage, success clears spam marker. Katana guard only exists two-handed in NR. Enemy AtkParam_Npc atkSa_JustGuard x4 (engine deflect stance damage; also buffs Executor) so 1 deflect staggers normal enemies, 2-3 stun bosses (stance 100-155).

Online: the game folder has OnlineFix (dlllist.txt loads OnlineFix64.dll, FakeAppId 480). Server Redirector loads fine but login fails, so the game falls back offline. I declined to work around it; the fix is a genuine Steam install.

Guard pose: SEKIRO_GUARD_POSE in sekiro_deflect.py makes katana deflect use GUARD_STYLE_DEMONSWORD (Executor stance, right tilt). Unverified that non-Executor heroes have those animations; flip to False if the guard looks broken.

Shareable zip: Downloads/NR Merged (MMV + FIA + LM).zip (4.46 GB, 7z store, excludes logs). Re-zip after any rebuild.

2026-11-03: user had Limitless Merchant and the Sekiro deflect removed from the build (sekiro_deflect.py kept but no longer called; MMV's own merchant talk restored). Everdark Boss Overhaul Pack 1.83 (#293) IS merged (user reversed course 2026-11-03), via merge_evd.py: MMV bullets 7500303-306 -> 7590303-306; Everdark SpEffect 46083 -> 46983 (+ Heolstor 758000_battle.lua); MMV keeps 46038, its c5300 boss, its c5140.hks (Everdark's doesn't compile) and text 338481; Everdark's name lists win (vanilla + 60 entries). The game archive is patch 1.03.3 while the mods target 1.03.5, so event/TAE 'vanilla' comparisons include patch drift. #273 not merged.

2026-11-03: second build, separate folder `Downloads/NR Merged (MMV + VINS + Everdark)/` via `build_vins.py` + `merge_vins.py` (build.py helpers reused through build.configure). User chose: FIA out, ELDEN VINS 1.5.2 (#287, extracted to Downloads/ELDEN VINS NIGHTREIGN-287-1-5-2/) is the combat base, MMV weapons whose moves only MMV's c0000 behaviour graph registers are pulled from loot (96 weapons, 55 skills; weight 0). Same launchers/saves as before (FIA_SAVE / NR0000.co2), plus ELDEN VINS's NightreignFPSFOV.dll. Ownership: player files/params -> ELDEN VINS; shared forget909 boss ports -> MMV (newer, clean NR fields; VINS converter left junk like spEffectTextId_1=120554); Everdark -> 1.83 except m60_42_36_50. Table groups (loot/spell tables) now merge per entry in merge_regulation. Skill type T animations live in a{T+600}.tae. Untested in game; no zip made (12 GB free on /mnt/win).

2026-11-04: user said the MMV+VINS+Everdark build broke their character's moves. Rebuilt as `Downloads/NR Merged (VINS + MMV bosses)/` (build_vins.py + merge_vins.py, rewritten): base regulation is ELDEN VINS's own (1.03.4), so every player-side param is byte-identical to VINS; MMV contributes only boss/castle/spawn params (MMV_PARAMS allowlist), files minus c0000/parts/dll/merchant talk; no invaders (SmallbaseInvationNpcParam + their CharaInit rows), no Everdark 1.83, no FIA. Clashing IDs renumbered (VINS 46033-46083 -> +900 incl. c7580 TAE events 66/67, m18 emevds, 758000 lua; MMV 9000000-3 -> 9050000-3 incl. c9997.hks + c1700 TAE). Source moves: MMV now read from /mnt/win/.Trash-1000/files/ (user trashed it; emptying the Linux trash breaks rebuilds), FIA folder deleted so launcher DLLs live in ~/dev/nr-modmerge/launchers/, VINS folder renamed to 'ELDEN VINS NIGHTREIGN-287-1-5-2-1769916199'. Old broken MMV+VINS+Everdark folder and 14.5 GB zip still in Downloads. Recycle-bin saves (Oct 25) backed up to save-backup-2026-11-02/recycle-bin-saves-2026-10-25/.
