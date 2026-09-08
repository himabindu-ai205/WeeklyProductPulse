(function () {
  "use strict";

  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const TREND = {
    rising: { arrow: "↑", label: "rising", cls: "text-primary" },
    falling: { arrow: "↓", label: "falling", cls: "text-error" },
    steady: { arrow: "→", label: "steady", cls: "text-secondary" },
  };

  const state = {
    pulse: null,
    meta: { product_name: "Groww", email_subject: "Weekly Review Pulse — Groww — {week_ending}" },
    error: null,
  };

  function $(id) {
    return document.getElementById(id);
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function parseDate(iso) {
    const [y, m, d] = iso.split("-").map(Number);
    return new Date(y, m - 1, d);
  }

  function toIsoWeekString(date) {
    const target = new Date(date.valueOf());
    const dayNr = (date.getDay() + 6) % 7;
    target.setDate(target.getDate() - dayNr + 3);
    const firstThursday = target.valueOf();
    target.setMonth(0, 1);
    if (target.getDay() !== 4) {
      target.setMonth(0, 1 + ((4 - target.getDay() + 7) % 7));
    }
    const week = 1 + Math.round((firstThursday - target.valueOf()) / 604800000);
    return `${target.getFullYear()}-W${String(week).padStart(2, "0")}`;
  }

  function compareIsoWeek(a, b) {
    const ma = a.match(/^(\d{4})-W(\d{2})$/);
    const mb = b.match(/^(\d{4})-W(\d{2})$/);
    if (!ma || !mb) return 0;
    const ya = Number(ma[1]);
    const yb = Number(mb[1]);
    if (ya !== yb) return ya - yb;
    return Number(ma[2]) - Number(mb[2]);
  }

  function formatRange(fromIso, toIso) {
    const from = parseDate(fromIso);
    const to = parseDate(toIso);
    const sM = MONTHS[from.getMonth()];
    const eM = MONTHS[to.getMonth()];
    const sD = from.getDate();
    const eD = to.getDate();
    const sY = from.getFullYear();
    const eY = to.getFullYear();
    if (sY !== eY) return `${sM} ${sD}, ${sY} – ${eM} ${eD}, ${eY}`;
    if (sM !== eM) return `${sM} ${sD} – ${eM} ${eD}, ${sY}`;
    return `${sM} ${sD} – ${eD}, ${sY}`;
  }

  function formatShort(iso) {
    const d = parseDate(iso);
    return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
  }

  function windowFrom(pulse) {
    const w = pulse.reporting_window || {};
    return { from: w.from_ || w.from, to: w.to };
  }

  function corpusWeeks(pulse) {
    const c = pulse.corpus_window || {};
    const from = c.from_ || c.from;
    if (!from || !c.to) return 12;
    const days = (parseDate(c.to) - parseDate(from)) / 86400000;
    return Math.max(1, Math.round(days / 7));
  }

  function weeksBehind(pulse) {
    const ending = pulse.week_ending;
    if (!ending) return 0;
    const pulseWeek = toIsoWeekString(parseDate(ending));
    const nowWeek = toIsoWeekString(new Date());
    const diff = compareIsoWeek(nowWeek, pulseWeek);
    return Math.max(0, diff);
  }

  function themeTag(theme) {
    const id = (theme.id || "").toLowerCase();
    const map = {
      trading: "Trading",
      payments: "Payments",
      withdrawals: "Withdrawals",
      kyc: "KYC",
      onboarding: "Onboarding",
    };
    if (map[id]) return map[id];
    return (theme.label || id || "Theme").split(/[&/]/)[0].trim();
  }

  function quoteFor(pulse, themeId) {
    return (pulse.quotes || []).find((q) => q.theme_id === themeId) || null;
  }

  function actionFor(pulse, themeId) {
    return (pulse.actions || []).find((a) => a.theme_id === themeId) || null;
  }

  function stars(n) {
    if (n == null || Number.isNaN(Number(n))) return "n/a";
    return Number(n).toFixed(1);
  }

  function shareUrl(pulse) {
    const iso = toIsoWeekString(parseDate(pulse.week_ending));
    return `${window.location.origin}/?week=${encodeURIComponent(iso)}`;
  }

  function renderEmpty() {
    return `
      <div class="max-w-container-max-width mx-auto px-space-md lg:px-space-lg py-space-xl">
        <section class="flex flex-col gap-space-md mb-space-xl">
          <div class="flex items-center gap-space-2xs mb-1">
            <span class="font-label-sm text-label-sm text-primary tracking-widest uppercase">Customer voice</span>
            <span class="text-tertiary font-label-sm text-label-sm">·</span>
            <span class="font-label-sm text-label-sm text-tertiary tracking-widest uppercase">Play Store</span>
          </div>
          <h1 class="font-display-title text-display-title italic text-on-surface tracking-tight">Weekly Review Pulse</h1>
          <p class="font-body-md text-body-md text-on-surface-variant max-w-xl">Rolling 12-week corpus, distilled to this week’s themes, quotes, and actions.</p>
        </section>
        <section class="w-full bg-surface-container-lowest rounded-xl p-space-xl md:p-space-2xl shadow-sm text-center flex flex-col items-center" id="report">
          <div class="w-20 h-20 rounded-full bg-surface-container flex items-center justify-center mb-space-lg">
            <span class="material-symbols-outlined text-tertiary text-[36px]">description</span>
          </div>
          <h2 class="font-headline-md text-headline-md font-bold text-on-surface mb-space-2xs">No reports yet</h2>
          <p class="font-body-md text-body-md text-secondary leading-relaxed mb-space-lg max-w-md">Reports generate every Sunday evening. The first pulse will appear here.</p>
          <div class="inline-flex items-center gap-space-xs px-space-md py-1.5 rounded-full bg-surface-container text-on-secondary-container">
            <span class="w-2 h-2 rounded-full bg-primary"></span>
            <span class="font-label-sm text-label-sm font-semibold tracking-wide uppercase">Run python -m src then refresh</span>
          </div>
        </section>
      </div>`;
  }

  function renderError(message) {
    return `
      <div class="max-w-container-max-width mx-auto px-space-md lg:px-space-lg py-space-xl" id="report">
        <h1 class="font-display-title text-display-title italic mb-space-md">Weekly Review Pulse</h1>
        <div class="bg-surface-container-lowest rounded-xl p-space-xl text-center">
          <span class="material-symbols-outlined text-error text-[40px]">error</span>
          <h2 class="font-headline-md font-bold mt-space-sm">Unable to load report</h2>
          <p class="font-body-md text-secondary mt-space-xs">${escapeHtml(message)}</p>
        </div>
      </div>`;
  }

  function renderThemeCard(pulse, theme, index) {
    const trend = TREND[theme.trend] || TREND.steady;
    const quote = quoteFor(pulse, theme.id);
    const action = actionFor(pulse, theme.id);
    const low = theme.avg_rating_week != null && theme.avg_rating_week < 2.5;
    const ratingCls = low ? "text-error" : "text-on-surface";
    const quoteBadge = quote && quote.rating === 1
      ? "bg-error-container text-on-error-container"
      : "bg-surface-container-highest text-secondary";
    const actionHref = action ? `#action-${index + 1}` : "#actions";

    return `
      <article class="bg-surface-container-lowest p-5 rounded-xl shadow-sm relative overflow-hidden pl-6">
        <div class="absolute left-0 top-0 bottom-0 w-[3px] bg-primary"></div>
        <div class="flex flex-wrap items-center justify-between gap-space-xs mb-space-xs">
          <div class="flex items-center gap-space-sm">
            <div class="w-6 h-6 rounded-full bg-primary text-on-primary font-headline-sm text-xs flex items-center justify-center font-bold shrink-0">${index + 1}</div>
            <h2 class="font-headline-md text-headline-md font-bold text-on-surface">${escapeHtml(theme.label)}</h2>
          </div>
          <div class="flex items-center gap-space-xs font-label-sm text-label-sm text-secondary bg-surface-container-low px-space-sm py-1 rounded-full">
            <span>${escapeHtml(String(theme.count_week))} reviews</span>
            <span class="text-tertiary-fixed-dim">·</span>
            <span class="${ratingCls} font-semibold">${escapeHtml(stars(theme.avg_rating_week))}★</span>
            <span class="text-tertiary-fixed-dim">·</span>
            <span class="${trend.cls} font-semibold">${trend.arrow} ${trend.label}</span>
          </div>
        </div>
        <p class="font-body-md text-body-md text-on-surface-variant mb-space-md">${escapeHtml(theme.summary)}</p>
        ${quote ? `
        <div class="bg-surface-container-low p-space-md rounded-lg mb-space-md border-l-2 border-primary">
          <div class="flex items-center justify-between mb-space-2xs">
            <div class="inline-flex items-center gap-1 ${quoteBadge} px-space-xs py-0.5 rounded font-label-sm text-label-sm font-semibold">
              <span>${quote.rating != null ? escapeHtml(String(quote.rating)) + "★" : "Quote"}</span>
            </div>
            <span class="font-label-sm text-label-sm text-tertiary font-medium">${escapeHtml(formatShort(quote.date))}</span>
          </div>
          <blockquote class="font-body-md text-body-md text-on-surface italic leading-relaxed">“${escapeHtml(quote.text)}”</blockquote>
        </div>` : ""}
        ${action ? `
        <div class="flex items-center justify-between pt-space-xs">
          <a class="inline-flex items-center gap-1.5 font-label-md text-label-md text-primary font-semibold hover:underline" href="${actionHref}">
            <span>Open action →</span>
          </a>
          <span class="font-label-sm text-label-sm text-tertiary">${escapeHtml(themeTag(theme))}</span>
        </div>` : ""}
      </article>`;
  }

  function renderActionRow(pulse, action, index) {
    const theme = (pulse.top_themes || []).find((t) => t.id === action.theme_id) || { label: action.theme_id, id: action.theme_id };
    return `
      <div class="flex flex-col sm:flex-row sm:items-center justify-between p-space-sm rounded-lg bg-surface-container-low/50 hover:bg-surface-container-low transition-colors gap-space-sm" id="action-${index + 1}">
        <div class="flex items-start gap-space-sm min-w-0">
          <label class="relative flex items-center pt-0.5 cursor-pointer">
            <input class="action-checkbox w-4 h-4 rounded text-primary accent-primary" type="checkbox" data-action-id="${escapeHtml(action.theme_id + "-" + index)}" aria-label="Mark done: ${escapeHtml(action.title)}">
          </label>
          <div class="flex flex-col min-w-0">
            <span class="action-title font-headline-sm text-headline-sm font-semibold text-on-surface">${index + 1}. ${escapeHtml(action.title)}</span>
            <span class="font-body-sm text-body-sm text-secondary">${escapeHtml(action.detail)}</span>
          </div>
        </div>
        <div class="flex items-center gap-space-xs shrink-0 self-end sm:self-center pl-7 sm:pl-0">
          <span class="px-space-xs py-0.5 rounded-full font-label-sm text-label-sm font-semibold bg-surface-container-highest text-on-surface-variant">${escapeHtml(themeTag(theme))}</span>
          <span class="px-space-xs py-0.5 rounded-full font-label-sm text-label-sm font-semibold text-tertiary bg-surface-container">Unassigned</span>
        </div>
      </div>`;
  }

  function renderBriefing(pulse) {
    const win = windowFrom(pulse);
    const range = formatRange(win.from, win.to);
    const iso = toIsoWeekString(parseDate(pulse.week_ending));
    const behind = weeksBehind(pulse);
    const top = (pulse.top_themes || [])[0];
    const topTrend = top ? (TREND[top.trend] || TREND.steady) : TREND.steady;
    const weeks = corpusWeeks(pulse);
    const readyBadge = behind === 0
      ? `<div class="inline-flex items-center gap-1.5 px-space-sm py-1 rounded-full bg-surface-container text-[#3D8C5C]">
           <span class="w-2 h-2 rounded-full bg-[#3D8C5C]"></span>
           <span class="font-label-sm text-label-sm font-semibold uppercase tracking-wide">Report ready</span>
         </div>`
      : `<span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary-fixed text-on-primary-fixed-variant font-label-sm text-label-sm font-semibold tracking-wider uppercase">
           <span class="material-symbols-outlined text-[13px]">history</span>
           ${behind} week${behind === 1 ? "" : "s"} behind
         </span>`;

    const staleBanner = behind >= 1
      ? `<div class="flex items-center gap-space-sm px-space-md py-2.5 rounded-xl bg-primary-fixed/40 text-on-surface-variant mb-space-lg">
           <span class="material-symbols-outlined text-primary text-[20px] flex-shrink-0">info</span>
           <p class="font-body-sm text-body-sm leading-tight text-on-surface">
             <strong class="font-semibold text-primary">Archive view</strong> — this pulse is ${behind} week${behind === 1 ? "" : "s"} behind the current ISO week.
           </p>
         </div>`
      : "";

    return `
      <div class="max-w-container-max-width mx-auto px-space-md lg:px-space-lg py-space-xl">
        <section class="flex flex-col gap-space-xs pb-space-md">
          <div class="flex items-center gap-space-xs">
            <span class="font-label-sm text-label-sm text-tertiary uppercase tracking-widest font-bold">Customer Voice · Play Store</span>
          </div>
          <div class="flex flex-col sm:flex-row sm:items-baseline justify-between gap-space-xs">
            <h1 class="font-display-title text-display-title italic text-on-surface font-normal">Weekly Review Pulse</h1>
            <span class="font-label-sm text-label-sm text-secondary uppercase tracking-wider bg-surface-container-low px-space-xs py-0.5 rounded-full">${escapeHtml(iso.replace("-", " · "))}</span>
          </div>
          <p class="font-body-md text-body-md text-secondary">Rolling 12-week corpus, distilled to this week’s themes, quotes, and actions.</p>
        </section>

        <section class="flex flex-wrap items-center justify-between gap-space-sm py-space-sm mb-space-lg bg-surface-container-lowest/60 rounded-xl px-space-md">
          <div class="flex items-center gap-space-xs flex-wrap">
            <label class="font-label-md text-label-md text-tertiary font-semibold uppercase tracking-wider" for="period-select">Period</label>
            <div class="relative inline-flex items-center">
              <select id="period-select" class="appearance-none bg-surface-container-low text-on-surface font-headline-sm text-body-md font-semibold py-1.5 pl-3 pr-8 rounded-full focus:outline-none focus:ring-2 focus:ring-primary/20 cursor-pointer" aria-label="Select report week">
                <option selected value="${escapeHtml(iso)}">${escapeHtml(range)}</option>
              </select>
              <span class="material-symbols-outlined absolute right-2 text-tertiary pointer-events-none text-base">expand_more</span>
            </div>
            <button type="button" id="refresh-btn" class="ml-space-2xs inline-flex items-center gap-1 px-space-sm py-1.5 rounded-full font-label-md text-label-md text-secondary hover:text-on-surface hover:bg-surface-container-high">
              <span class="material-symbols-outlined text-sm text-tertiary" id="refresh-icon">refresh</span>
              <span>Refresh</span>
            </button>
          </div>
          <div class="flex items-center gap-space-xs">
            <span class="font-body-sm text-body-sm text-secondary hidden sm:inline">Viewing ${escapeHtml(range)}</span>
            ${readyBadge}
          </div>
        </section>

        ${staleBanner}

        <section class="grid grid-cols-2 lg:grid-cols-4 gap-space-md mb-space-2xl" aria-label="Key metrics">
          <div class="bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col justify-between">
            <span class="font-label-sm text-label-sm uppercase tracking-wider text-tertiary font-semibold">Average rating this week</span>
            <div class="flex items-baseline gap-space-2xs mt-space-sm">
              <span class="font-metric-xl text-metric-xl text-on-surface font-bold">${escapeHtml(stars(pulse.avg_rating_week))}</span>
              <span class="text-primary text-xl font-headline-md">★</span>
            </div>
          </div>
          <div class="bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col justify-between">
            <span class="font-label-sm text-label-sm uppercase tracking-wider text-tertiary font-semibold">Reviews this week</span>
            <div class="mt-space-sm"><span class="font-metric-xl text-metric-xl text-on-surface font-bold">${escapeHtml(String(pulse.review_count_week))}</span></div>
          </div>
          <div class="bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col justify-between">
            <span class="font-label-sm text-label-sm uppercase tracking-wider text-tertiary font-semibold">Corpus (${weeks} weeks)</span>
            <div class="mt-space-sm"><span class="font-metric-xl text-metric-xl text-on-surface font-bold">${escapeHtml(String(pulse.review_count_corpus))}</span></div>
          </div>
          <div class="bg-surface-container-lowest p-space-md rounded-xl shadow-sm flex flex-col justify-between">
            <span class="font-label-sm text-label-sm uppercase tracking-wider text-tertiary font-semibold">Top theme trend</span>
            <div class="flex items-center gap-1 mt-space-sm ${topTrend.cls}">
              <span class="font-headline-md text-headline-md font-bold">${topTrend.arrow}</span>
              <span class="font-headline-md text-headline-md font-bold truncate">${top ? escapeHtml(top.label.split("&")[0].trim()) : "—"}</span>
            </div>
            <span class="font-body-sm text-body-sm text-secondary truncate mt-space-xs">${top ? escapeHtml(top.label + " " + topTrend.label) : ""}</span>
          </div>
        </section>

        <div class="flex items-center justify-between mb-space-md">
          <div class="flex items-center gap-space-xs">
            <span class="font-headline-md text-headline-md text-on-surface font-semibold">Emerging friction themes</span>
            <span class="px-space-xs py-0.5 rounded bg-surface-container-high text-secondary font-label-sm text-label-sm font-semibold">${(pulse.top_themes || []).length} active</span>
          </div>
        </div>

        <section class="flex flex-col gap-space-md mb-space-2xl" id="report">
          ${(pulse.top_themes || []).map((t, i) => renderThemeCard(pulse, t, i)).join("")}
        </section>

        <section class="mb-space-2xl bg-surface-container-lowest p-space-lg rounded-xl shadow-sm" id="actions">
          <div class="flex items-center justify-between pb-space-sm mb-space-md">
            <div>
              <h2 class="font-headline-lg text-headline-lg font-bold text-on-surface">What to do next</h2>
              <p class="font-body-sm text-body-sm text-secondary">Priority follow-ups from this week’s reviews.</p>
            </div>
            <span class="font-label-sm text-label-sm uppercase tracking-wider text-tertiary font-semibold hidden sm:inline">${(pulse.actions || []).length} recommendations</span>
          </div>
          <div class="flex flex-col gap-space-sm">
            ${(pulse.actions || []).map((a, i) => renderActionRow(pulse, a, i)).join("")}
          </div>
        </section>

        <section class="bg-surface-container-lowest p-space-lg rounded-xl shadow-sm mb-space-xl">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-space-xs mb-space-md">
            <div>
              <div class="flex items-center gap-space-xs">
                <h2 class="font-headline-md text-headline-md font-bold text-on-surface">Share</h2>
                <span class="font-label-sm text-label-sm font-semibold text-secondary uppercase bg-surface-container px-space-xs py-0.5 rounded">Internal only</span>
              </div>
              <p class="font-body-sm text-body-sm text-secondary mt-0.5">Copy a link, download the note, or draft email to your alias.</p>
            </div>
            <div class="flex items-center gap-space-xs">
              <button type="button" id="copy-link-btn" class="inline-flex items-center gap-1.5 px-space-sm py-1.5 rounded-full bg-surface-container-low hover:bg-surface-container-high text-on-surface font-label-md text-label-md font-semibold">
                <span class="material-symbols-outlined text-sm text-secondary">link</span>
                <span id="copy-btn-text">Copy link</span>
              </button>
              <button type="button" id="download-md-btn" class="inline-flex items-center gap-1.5 px-space-sm py-1.5 rounded-full bg-surface-container-low hover:bg-surface-container-high text-on-surface font-label-md text-label-md font-semibold">
                <span class="material-symbols-outlined text-sm text-secondary">download</span>
                <span>Download .md</span>
              </button>
            </div>
          </div>
          <div class="bg-surface-container-low p-space-md rounded-lg flex flex-col gap-space-sm">
            <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-space-xs">
              <div class="relative flex-1">
                <span class="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-tertiary text-base">mail</span>
                <label class="sr-only" for="email-target">Recipient email</label>
                <input id="email-target" class="w-full bg-surface-container-lowest text-on-surface font-body-md text-body-md pl-9 pr-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary/20 placeholder:text-tertiary" type="email" value="" placeholder="name@company.com" autocomplete="email" required>
              </div>
              <button type="button" id="draft-email-btn" class="inline-flex items-center justify-center gap-2 px-space-lg py-2 rounded-full bg-primary hover:bg-primary-container text-on-primary font-headline-sm text-label-md font-semibold active:scale-[0.98]">
                <span class="material-symbols-outlined text-base">outgoing_mail</span>
                <span>Create email draft</span>
              </button>
            </div>
            <div class="flex items-center justify-between text-tertiary font-body-sm text-body-sm">
              <span>Creates a mail draft. Nothing is sent until you send it.</span>
              <span class="font-label-sm text-label-sm hidden sm:inline">Draft for week ending ${escapeHtml(formatShort(pulse.week_ending))}</span>
            </div>
          </div>
        </section>
      </div>`;
  }

  function bindBriefing(pulse) {
    const refreshBtn = $("refresh-btn");
    const refreshIcon = $("refresh-icon");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", async () => {
        refreshIcon?.classList.add("animate-spin");
        await load(true);
        refreshIcon?.classList.remove("animate-spin");
      });
    }

    document.querySelectorAll(".action-checkbox").forEach((cb) => {
      const key = `pulse-action:${cb.getAttribute("data-action-id")}`;
      cb.checked = sessionStorage.getItem(key) === "1";
      toggleDone(cb);
      cb.addEventListener("change", () => {
        sessionStorage.setItem(key, cb.checked ? "1" : "0");
        toggleDone(cb);
      });
    });

    const copyBtn = $("copy-link-btn");
    const copyText = $("copy-btn-text");
    if (copyBtn) {
      copyBtn.addEventListener("click", async () => {
        const url = shareUrl(pulse);
        try {
          await navigator.clipboard.writeText(url);
        } catch {
          /* ignore */
        }
        if (copyText) {
          copyText.textContent = "Copied!";
          setTimeout(() => {
            copyText.textContent = "Copy link";
          }, 2000);
        }
      });
    }

    const downloadBtn = $("download-md-btn");
    if (downloadBtn) {
      downloadBtn.addEventListener("click", async () => {
        const res = await fetch("/api/pulse.md", { cache: "no-store" });
        if (!res.ok) return;
        const text = await res.text();
        const iso = toIsoWeekString(parseDate(pulse.week_ending));
        const blob = new Blob([text], { type: "text/markdown" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `Groww_Pulse_${iso}.md`;
        a.click();
        URL.revokeObjectURL(url);
      });
    }

    const draftBtn = $("draft-email-btn");
    const emailInput = $("email-target");
    if (draftBtn) {
      draftBtn.addEventListener("click", () => {
        const to = (emailInput?.value || "").trim();
        if (!to || !to.includes("@")) {
          emailInput?.focus();
          emailInput?.setCustomValidity("Enter a recipient email address.");
          emailInput?.reportValidity();
          return;
        }
        emailInput?.setCustomValidity("");
        const ending = formatShort(pulse.week_ending);
        const subject = (state.meta.email_subject || "Weekly Review Pulse — Groww — {week_ending}")
          .replace("{week_ending}", pulse.week_ending);
        const themes = (pulse.top_themes || []).map((t) => t.label).join(", ");
        const body =
          `Weekly Review Pulse — ${pulse.product_name} — week ending ${pulse.week_ending}\n` +
          `Avg rating: ${stars(pulse.avg_rating_week)}★ · ${pulse.review_count_week} reviews\n` +
          `Top themes: ${themes}\n\n` +
          `${shareUrl(pulse)}\n`;
        window.location.href = `mailto:${encodeURIComponent(to)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
        openModal(`Week ending ${ending} · mail draft for ${to}`);
      });
    }
  }

  function toggleDone(cb) {
    const el = cb.closest("[id^='action-']")?.querySelector(".action-title");
    if (!el) return;
    el.classList.toggle("is-done", cb.checked);
    el.classList.toggle("text-on-surface", !cb.checked);
  }

  function openModal(detail) {
    const overlay = $("draft-modal");
    const desc = $("modal-description");
    if (desc) desc.textContent = detail;
    overlay?.classList.remove("hidden");
    $("btn-done")?.focus();
  }

  function closeModal() {
    $("draft-modal")?.classList.add("hidden");
  }

  function paint() {
    const app = $("app");
    const footerLine = $("footer-line");
    const footerMeta = $("footer-meta");

    if (state.error && !state.pulse) {
      app.innerHTML = renderError(state.error);
      return;
    }
    if (!state.pulse) {
      app.innerHTML = renderEmpty();
      if (footerLine) footerLine.textContent = "Weekly Review Pulse · Groww Customer Voice";
      if (footerMeta) footerMeta.textContent = "";
      return;
    }

    const pulse = state.pulse;
    app.innerHTML = renderBriefing(pulse);
    bindBriefing(pulse);
    if (footerLine) {
      footerLine.textContent = `Weekly Review Pulse · Groww Customer Voice · week ending ${formatShort(pulse.week_ending)}`;
    }
    if (footerMeta) footerMeta.textContent = `${pulse.review_count_week} reviews analyzed`;
  }

  async function load(bust) {
    const q = bust ? `?_=${Date.now()}` : "";
    try {
      const [pulseRes, metaRes] = await Promise.all([
        fetch(`/api/pulse${q}`, { cache: "no-store" }),
        fetch(`/api/meta${q}`, { cache: "no-store" }),
      ]);
      if (metaRes.ok) state.meta = await metaRes.json();
      if (pulseRes.status === 404) {
        state.pulse = null;
        state.error = null;
      } else if (!pulseRes.ok) {
        const err = await pulseRes.json().catch(() => ({}));
        state.pulse = null;
        state.error = err.detail || pulseRes.statusText;
      } else {
        state.pulse = await pulseRes.json();
        state.error = null;
      }
    } catch (e) {
      state.pulse = null;
      state.error = e instanceof Error ? e.message : String(e);
    }
    paint();
  }

  $("btn-done")?.addEventListener("click", closeModal);
  $("btn-close-x")?.addEventListener("click", closeModal);
  $("draft-modal")?.addEventListener("click", (e) => {
    if (e.target === $("draft-modal")) closeModal();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });

  load(false);
})();
