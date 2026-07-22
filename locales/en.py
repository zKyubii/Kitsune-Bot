"""English strings. Keys are `section.name` and must match `it.py`."""

STRINGS = {
    # ── COMMON (reused everywhere) ──────────────────────────────────────────
    "common.enabled": "🟢 Enabled",
    "common.disabled": "🔴 Disabled",
    "common.not_set": "❌ not set",
    "common.none": "*None*",
    "common.back": "Back",
    "common.activate": "Enable",
    "common.deactivate": "Disable",
    "common.state": "Status",
    "common.channel": "📢 Channel",

    # ── DASHBOARD: language ─────────────────────────────────────────────────
    "lang.placeholder": "🌍 Bot language...",
    "lang.field": "🌍 Language",

    # ── COUNTING: chat messages ─────────────────────────────────────────────
    "counting.deleted": "⚠️ {user} has deleted their number: ```{n}```"
                        "The next number is **{next}**.",
    "counting.ruined": "💥 {user} **RUINED IT AT {n}!!** "
                       "Next number is **1**. {reason}\n{record}",
    "counting.reason_double": "You can't count twice in a row.",
    "counting.reason_wrong": "Wrong number: it was **{expected}**.",
    "counting.record_new": "🏆 **New record: {record}!**",
    "counting.record_current": "🏆 Server record: **{record}**",

    # ── COUNTING: dashboard ─────────────────────────────────────────────────
    "counting.title": "🔢 Counting",
    "counting.desc": "Members count in turns in the chosen channel: "
                     "**you can't count twice in a row**.\n"
                     "Messages that aren't numbers are ignored.",
    "counting.channel_placeholder": "🔢 Counting channel...",
    "counting.on_fail": "On mistake",
    "counting.on_fail_reset": "the count restarts from 1",
    "counting.on_fail_delete": "the wrong message gets deleted",
    "counting.btn_reset_on": "On mistake: restart from 1",
    "counting.btn_reset_off": "On mistake: just delete",
    "counting.btn_react_on": "✅ reaction on",
    "counting.btn_react_off": "✅ reaction off",
    "counting.btn_clear": "Reset count",
    "counting.btn_milestones": "Milestones",
    "counting.current": "Current number",
    "counting.current_value": "**{n}** (next: {next})",
    "counting.record": "🏆 Record",
    "counting.react_field": "✅ Reaction",
    "counting.react_on": "on",
    "counting.react_off": "off",
    "counting.milestones": "🏁 Milestones",
    "counting.milestones_none": "none",
    "counting.milestone_entry": "{emoji} at {n}",
    "counting.footer": "If someone deletes their number, the bot announces the next one.",
    "counting.modal_title": "Milestones",
    "counting.modal_label": "Number: emoji (comma separated)",
}
