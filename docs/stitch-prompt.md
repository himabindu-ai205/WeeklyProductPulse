# Google Stitch prompt — Weekly Review Pulse

Paste the block below into [Stitch](https://stitch.withgoogle.com/). Choose **Web**. After the first screen, use the follow-ups at the bottom one at a time.

**Do not generate a Fee context / legal / SEBI / AMFI / exit-load section.** That block is removed from this product.

---

## Prompt (copy everything in this block)

```
Zoom out — product
Internal web dashboard: “Weekly Review Pulse” for Groww (Play Store, package com.nextbillion.groww). Audience: Product, Growth, Support, Leadership. They open it once a week and must understand themes, verbatim quotes, and three actions in under two minutes. Not a marketing site. Not a consumer fintech app. Desktop-first (1440px), with a usable 390px mobile layout.

Zoom in — screen
Screen 1: Weekly pulse (default / happy path). Goal: scan-first briefing. The first screenful must be KPIs + themes, not a large editorial hero.

Visual system
Warm paper editorial, not SaaS purple. Background #F7F4EE. Surfaces #FDFBF7. Text #1A1715 / secondary #4A453F / tertiary #8C857C. Accent terracotta #C96442. Success #3D8C5C. Error #C0392B. Hairline borders rgba(90,75,60,0.08). Cards 16px radius, pill buttons 980px radius. Typography: DM Sans for UI chrome and stats; Lora italic for the page title only (small). No emoji in headings or badges. No heavy gradients. No dark mode. No sidebar. Max content width 900px, centered. Sticky top nav with backdrop blur.

Layout hierarchy (top to bottom)
1. Sticky nav: Groww wordmark (simple green “G” monogram 28px) + “Groww” + muted “Product Pulse”. Right: signed-in chip “himabindu.avalur@gmail.com” (this tool is internal; email send is not public).
2. Compact title row (NOT a tall hero): small uppercase eyebrow “Customer voice · Play Store”. Title in Lora italic ~32px: “Weekly Review Pulse”. One line of supporting text: “Rolling 12-week corpus, distilled to this week’s themes, quotes, and actions.”
3. Toolbar: label “Period” + select showing “Aug 27 – Sep 2, 2026” (options also include Aug 20–26). Ghost button “Refresh”. Do not reset the selected week on refresh.
4. Freshness + viewing bar (pill): “Viewing Aug 27 – Sep 2, 2026” + green “Report ready” if the week is current. If the selected week is older than the current ISO week, show an amber badge “N weeks behind” instead of green ready. Never show infrastructure copy (no “cold API”, no “Gmail MCP”, no Render).
5. KPI strip — four equal cards in a row (stack 2×2 on mobile):
   - 3.0★  Average rating this week
   - 46    Reviews this week
   - 46    Corpus (12 weeks)
   - ↑     Top theme trend: Trading & orders rising
6. Three theme cards in a vertical stack. Each card is a first-class object, not a markdown dump. Left terracotta 3px accent. Ranked 1–3 in a filled terracotta circle. Title, stats row (review count, avg stars, trend ↑ rising / → steady / ↓ falling), 2-sentence summary, one verbatim quote with star rating + date, and a single linked action title. Sample content (use exactly; keep typos in quotes — they are verbatim):
   Card 1 — Trading & orders · 20 reviews · 3.0★ · ↑ rising
   Summary: Users like buying stocks in the UI, but flag high brokerage, a laggy option chain, and thinner intraday margin vs rivals.
   Quote (2★, 1 Sep): “Best user interface ,but high brokerage charges . I recommend kotak neo to everyone under age 30”
   Action: Reduce brokerage fees for young investors
   Card 2 — Payments & UPI · 3 reviews · 2.3★ · ↑ rising
   Summary: Critical UPI errors send the wrong amount and erode trust; a few users mention helpful auto-debit.
   Quote (1★, 2 Sep): “SENDING WRONG PAYMENT AMOUNT TO BHIM! Fix this or else change your Product Managers!!”
   Action: Fix UPI payment amount validation
   Card 3 — Withdrawals & payouts · 2 reviews · 1.0★ · ↑ rising
   Summary: Unexplained holds and missing funds; severe dissatisfaction.
   Quote (1★, 2 Sep): “worest and froud app, it holds some amount without explaining the reson on withdraw time.”
   Action: Increase transparency on withdrawal processing
7. Actions section heading “What to do next” (no emoji). Three checklist rows, not an essay. Each row: number, bold title, one-line detail, theme tag, optional owner placeholder “Unassigned”.
   1. Reduce brokerage fees for young investors — Adjust fees for users under 30 and align margin with competitors. Tag: Trading
   2. Fix UPI payment amount validation — Strict amount checks so transfers cannot send the wrong value. Tag: Payments
   3. Increase transparency on withdrawal processing — Live status and a clear reason for every hold. Tag: Withdrawals
8. Share panel (internal only): heading “Share”. Lead: “Copy a link, download the note, or draft email to your alias.” Controls: “Copy link” (secondary) showing URL pattern https://pulse.groww.internal/?week=2026-W36; “Download .md” (ghost); email field prefilled with himabindu.avalur@gmail.com; primary button “Create email draft” (not “Send report” — this product drafts, it does not blast). Helper text under the button: “Creates a Gmail draft. Nothing is sent until you send it.” Confirm which week is attached: “Draft for week ending 2 Sep 2026”.
9. Footer: “Weekly Review Pulse · Groww Customer Voice · week ending 2 Sep 2026”. Tiny muted line: “46 reviews analyzed”. No model names, no “Powered by groq”.

Hard exclusions — do not draw these at all
- No “Fee context”, “facts only”, exit load, SEBI, AMFI, mutual fund legal boilerplate, official-sources list, or any regulatory appendix.
- No emoji in titles (no 📊 📈 🔍 💡).
- No themes named “Great App” or “Great Ui”.
- No large centered marketing hero that pushes KPIs below the fold.
- No public unauthenticated “Send report to any address” spam form.
- No loading skeleton as the default state of this screen (this screen is the loaded report).

States to design as additional screens (same visual system)
Screen 2 — Empty: period select disabled; document icon; title “No reports yet”; body “Reports generate every Sunday evening. The first pulse will appear here.” Share disabled.
Screen 3 — Stale week: same as Screen 1 but period is “Mar 23 – 29, 2026” and the badge is amber “23 weeks behind”. KPI numbers may stay filled. No fee section.
Screen 4 — Draft created modal: centered dialog, success check, title “Draft created”, body “Week ending 2 Sep 2026 · Gmail draft for himabindu.avalur@gmail.com”. Primary “Done”. Focus on Done. Click-outside and Escape close. No “Email sent” wording.
Screen 5 — Mobile 390px of Screen 1: nav compresses; KPIs 2×2; theme cards full width; share buttons stack; period select full width.

Accessibility
Skip link “Skip to report”. Visible labels on Period and email. Contrast on terracotta-on-cream meets WCAG AA. Focus rings use terracotta glow. Reduced motion: no shimmer or pop.

Output
High-fidelity web UI mockups for all five screens. Desktop 1440 for 1–4, mobile 390 for 5. Production-ready spacing and real copy, not lorem. Suitable to hand to an engineer.
```

---

## Follow-ups (one change per prompt)

1. Make the KPI cards tighter: 12px labels, 28px values, less padding. Keep four in a row on desktop.
2. On each theme card, put the quote in a left-bordered italic block and the action as a text button “Open action →” that visually points at the matching checklist row.
3. Add a week-over-week delta under Average rating: “−0.2 vs prior week” in the error color if down, success color if up.
4. Disable “Create email draft” until the viewer is signed in; show a lock + “Sign in to draft email” instead of the form.
5. Confirm there is still no Fee context, legal appendix, emoji headings, or “Email sent” success copy.
