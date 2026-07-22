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

    # ── MODERATION ──────────────────────────────────────────────────────────
    "mod.self_target": "❌ You can't use this command on yourself.",
    "mod.owner_target": "❌ You can't moderate the server owner.",
    "mod.higher_role": "❌ You can't moderate a user whose role is equal to or above yours.",
    "mod.bot_role_low": "❌ My role is too low: move it above the role of the user you want to moderate.",
    "mod.no_role_perm": "⛔ You don't have a role authorised for this command.",
    "mod.missing_perm": "⛔ You don't have the required permission for this command: `{perms}`",
    "mod.bot_missing_perm": "⚠️ I'm missing the required permission: `{perms}`",
    "mod.generic_error": "❌ An error occurred: {error}",
    "mod.error": "❌ Error: {error}",
    "mod.bad_duration": "❌ Invalid duration format. Examples: `30s`, `10m`, `2h`, `7d`",
    "mod.timeout_max": "❌ The maximum timeout allowed by Discord is **28 days** (`28d`).",
    "mod.bad_id": "❌ Invalid ID.",
    "mod.user_not_found": "❌ User not found.",
    "mod.user_not_banned": "❌ User not found or not banned.",
    "mod.slowmode_need_value": "❌ Pick a preset or enter a custom value in seconds.",
    "mod.slowmode_off": "✅ Slowmode disabled.",
    "mod.slowmode_set": "🐢 Slowmode set to **{value}**.",
    "mod.no_bans": "✅ There are no banned users in this server.",
    "mod.cleared": "🗑️ Deleted **{n}** messages.",
    "mod.warn_self": "❌ You can't warn yourself.",
    "mod.warn_bot": "❌ You can't warn a bot.",
    "mod.no_warns": "✅ **{user}** has no warns.",
    "mod.had_no_warns": "✅ **{user}** had no warns.",
    "mod.warn_removed": "✅ Warn **#{id}** removed.",
    "mod.warn_not_found": "❌ No warn with ID #{id}.",
    "mod.warn_dm_title": "⚠️ You have been warned in {guild}",
    "mod.warns_title": "⚠️ Warns of {user}",
    "mod.auto_kick": "👢 Automatic kick",
    "mod.auto_ban": "🔨 Automatic ban",
    "mod.auto_failed": "⚠️ Automatic action failed (permissions or role too high)",
    "mod.jail_not_configured": "❌ The Jail system isn't configured. "
                               "Go to `/dashboard` → 🛡️ Moderation → 🔒 Jail → **Setup**.",
    "mod.no_jailed": "✅ No user is currently jailed.",
    "mod.only_author": "❌ Only the person who used the command can browse it.",
    "mod.already_jailed": "❌ **{user}** is already jailed.",
    "mod.not_jailed": "❌ **{user}** isn't jailed.",
    # moderation embed
    "mod.embed_reason": "📋 **Reason:**",
    "mod.embed_moderator": "👤 **Moderator:**",
    "mod.embed_duration": "🕐 **Duration:**",
    "mod.embed_purged": "🧹 **Purged:**",
    "mod.embed_purged_value": "last {days} days",
    "mod.embed_proof": "🔗 Proof",
    "mod.embed_attachment": "[Attachment]({url})",

    # ── AVATAR / BANNER ─────────────────────────────────────────────────────
    "avatar.no_banner": "❌ {user} doesn't have a banner.",
    "avatar.no_profile_banner": "❌ {user} doesn't have a profile banner.",

    # ── QUOTE ───────────────────────────────────────────────────────────────
    "quote.only_author": "❌ Only whoever created the quote can edit it.",
    "quote.disabled": "🚫 The Quote feature is disabled on this server.",
    "quote.no_text": "❌ This message has no text to quote.",
    "quote.no_text_short": "❌ That message has no text to quote.",
    "quote.created": "✅ Quote created in {channel}! Customise it with the buttons on the message.",
    "quote.font": "🎨 Select font",
    "quote.background": "Background",
    "quote.bold": "Bold",

    # ── CONFESSION ──────────────────────────────────────────────────────────
    "conf.modal_title": "Anonymous confession",
    "conf.modal_label": "Your confession",
    "conf.placeholder": "Write here... it stays anonymous 🤫",
    "conf.disabled_short": "🚫 Confessions are disabled.",
    "conf.disabled": "🚫 Confessions are disabled on this server.",
    "conf.not_configured": "❌ Confessions aren't configured.",
    "conf.not_configured_admin": "❌ Confessions aren't configured. An admin has to set them up "
                                 "from `/dashboard` → 🔧 Features → Confession.",
    "conf.channel_gone": "❌ The confessions channel no longer exists.",
    "conf.no_perm": "⛔ You don't have the required permission for this command.",
    "conf.published": "✅ Your confession **#{n}** has been published in {channel}!",

    # ── ROLES ───────────────────────────────────────────────────────────────
    "roles.everyone": "❌ You can't assign the @everyone role.",
    "roles.managed": "❌ This role is managed by an integration and can't be assigned manually.",
    "roles.bot_too_low": "❌ My role is too low: move it above the role you want to assign.",
    "roles.higher": "❌ You can't manage a role equal to or above yours.",
    "roles.need_perm": "⛔ You need the **Manage Roles** permission.",
    "roles.already_has": "❌ {user} already has {role}.",
    "roles.doesnt_have": "❌ {user} doesn't have {role}.",
    "roles.added": "✅ {role} added to {user}.",
    "roles.removed": "✅ {role} removed from {user}.",
    "roles.mass_done": "✅ {role} {verb} **{count}** {what}.",

    # ── PARTNERSHIP ─────────────────────────────────────────────────────────
    "partner.channel_gone": "❌ The partnerships channel is no longer configured.",
    "partner.no_write_perm": "❌ I don't have permission to write in the partnerships channel.",
    "partner.send_error": "❌ Error while sending: {error}",
    "partner.published": "✅ Partnership published in {channel}!",
    "partner.disabled": "❌ The **Partnership** feature is disabled on this server.",
    "partner.no_role": "❌ You don't have a role authorised to make partnerships.",

    # ── FUN (ship / marriage) ───────────────────────────────────────────────
    "fun.disabled": "🚫 This feature isn't available on this server right now.",
    "fun.only_target": "❌ Only the person who was asked can accept.",
    "fun.self_marry": "💍 You can't marry yourself! Self-esteem matters, "
                      "but you need someone else 😅",
    "fun.married": "💍 {a} and {b} got married for **24 hours**! 🎉💕",
    "fun.timeout": "⏳ {user} didn't accept in time.",
    "fun.proposal": "{partner}, **{proposer}** wants to marry you! 💍\n",
    "fun.single": "💔 {user} is currently single.",
    "fun.marriage_title": "💍 Marriage",
    "fun.marriage_couple": "Couple",
    "fun.marriage_expires": "Expires",
    # /ship lines, one per row — {a} and {b} are the two users
    "fun.ship_t0": "Ouch, the stars say run 🏃💨 {a} and {b} just no.\n"
                   "Sorry {a}, but {b} isn't for you 💀\n"
                   "Zero sparks between {a} and {b}... better stay friends 🙈\n"
                   "Let's say {a} and {b} have very different tastes 😬",
    "fun.ship_t1": "There's hope for {a} and {b}, keep trying 💪\n"
                   "There's something between {a} and {b}, but it needs work 🤏\n"
                   "With a small miracle, {a} could win {b} over ✨\n"
                   "Not bad {a}... give {b} a chance 🤔",
    "fun.ship_t2": "Halfway there: {a} and {b}, who knows how it ends 💗\n"
                   "You can definitely see some sparks between {a} and {b} 👀\n"
                   "Careful, something might grow between {a} and {b} 🙂\n"
                   "Neither hot nor cold, but {a} and {b} have potential 🔥",
    "fun.ship_t3": "Love is in the air for {a} and {b} 🌸\n"
                   "Great chemistry! {a} and {b} are almost there 💕\n"
                   "Let's be honest, {a} and {b} are cute together 🥰\n"
                   "Heart eyes: {a} and {b} make a lovely couple 💘",
    "fun.ship_t4": "How are you two not married yet, {a} and {b}? 💍\n"
                   "They look made for each other: {a} and {b} 💞\n"
                   "Soulmates, {a} and {b} 🫶\n"
                   "A fairytale couple: {a} and {b} 🏰",
    "fun.ship_t5": "Wedding incoming for {a} and {b}! 💍🔥\n"
                   "The universe brought {a} and {b} together, it's destiny ❤️🌌\n"
                   "Eternal love written in the stars for {a} and {b} ⭐\n"
                   "Inseparable forever: {a} and {b} ♾️",

    # ── LOGS ────────────────────────────────────────────────────────────────
    "logs.timeout_expired": "*Expired automatically*",

    # ── MINIGAMES ───────────────────────────────────────────────────────────
    "mg.disabled": "🚫 Minigames aren't available on this server right now.",
    "mg.coin_heads": "Heads 🪙",
    "mg.coin_tails": "Tails ❌",
    "mg.coin_usage": "❌ Choose **heads** or **tails**. Example: `+moneta heads`",
    "mg.coin_win": "🎉 You got it!",
    "mg.coin_lose": "😅 You got it wrong!",
    "mg.coin_result": "You picked **{choice}**\nThe coin landed on: **{result}**\n{outcome}",
    "mg.8ball_usage": "❌ Ask a question. Example: `+8ball will I get married?`",
    "mg.8ball_title": "🎱 Magic 8-Ball",
    "mg.8ball_question": "❓ Question",
    "mg.8ball_answer": "💬 Answer",
    "mg.8ball_answers": "Yes, absolutely! ✅\nNo, definitely not. ❌\nMaybe... 🤔\n"
                        "The stars say yes. ⭐\nDon't count on it. 🚫\nEverything points to yes. 👍\n"
                        "The outlook isn't good. 😬\nAsk again later. 🔄\n"
                        "It's certain! 💯\nSigns point to no. 👎",
    "mg.rps_usage": "❌ Choose **rock**, **paper** or **scissors**. Example: `+rps rock`",
    "mg.rps_rock": "Rock",
    "mg.rps_paper": "Paper",
    "mg.rps_scissors": "Scissors",
    "mg.rps_title": "Rock, Paper, Scissors",
    "mg.rps_you": "You",
    "mg.rps_bot": "Bot",
    "mg.rps_result": "Result",
    "mg.rps_draw": "Draw! 🤝",
    "mg.rps_win": "You won! 🎉",
    "mg.rps_lose": "You lost! 😅",
    "mg.guess_running": "⚠️ There's already a game running in this channel! Use `+tentativo <number>`.",
    "mg.guess_started": "🎮 I picked a number between **1 and 100**! Use `+tentativo <number>` to guess.",
    "mg.guess_need_number": "❌ Write a number. Example: `+tentativo 50`",
    "mg.guess_no_game": "❌ No game running. Use `+indovina` to start one.",
    "mg.guess_won_one": "🎉 **{user}** guessed it! It was **{number}** in {tries} try!",
    "mg.guess_won_many": "🎉 **{user}** guessed it! It was **{number}** in {tries} tries!",
    "mg.guess_low": "📈 **{number}** is too low! (Try {tries})",
    "mg.guess_high": "📉 **{number}** is too high! (Try {tries})",

    # ── LEVELS ──────────────────────────────────────────────────────────────
    "lvl.disabled": "❌ The levelling system is disabled.",
    "lvl.no_xp": "Nobody has XP yet. 🤷",
    "lvl.leaderboard_title": "🏆 {guild} — Leaderboard",
    "lvl.xp_given": "✅ {verb} **{amount}** XP to {user}.",
    "lvl.xp_given_role": "✅ {verb} **{amount}** XP to **{count}** members with {role}.",
    "lvl.xp_set": "✅ {user} now has **{xp}** XP (level {level}).",
    "lvl.xp_reset": "✅ {user}'s XP reset.",
    "lvl.xp_now": "Now: **{xp}** XP (level {level}).",
    "lvl.verb_given": "Gave",
    "lvl.verb_taken": "Took",

    # ── GREETINGS / BOOST ───────────────────────────────────────────────────
    "greet.not_configured": "❌ The **{type}** message isn't configured. Use `/set {type}`.",
    "greet.embed_gone": "❌ The embed `{name}` no longer exists. Reconfigure with `/set {type}`.",
    "greet.send_error": "❌ Error while sending: {error}",
    "greet.sent": "✅ Message sent in {channel}.",
    "greet.embed_missing": "❌ The embed `{name}` doesn't exist. Create it with `/embed create`.",
    "greet.extra_message": "\nMessage: {msg}",
    "greet.welcome_set": "✅ Welcome set in {channel} using the embed `{name}`.{extra}",
    "greet.boost_set": "✅ Boost message set in {channel} using the embed `{name}`.{extra}",

    # ── COUNTING: chat messages ─────────────────────────────────────────────
    "counting.deleted": "⚠️ {user} has deleted their number: ```{n}```"
                        "The next number is **{next}**.",
    "counting.ruined": "💥 {user} **RUINED IT AT {n}!!**\n"
                       "Next number is **1**.\n"
                       "{reason}\n{record}",
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
