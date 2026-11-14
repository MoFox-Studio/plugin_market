<template>
  <div class="catalog-frame"><slot /></div>
</template>
<style scoped>
.catalog-frame {
  width: min(1280px, 100%);
  margin: 0 auto;
  padding: 36px clamp(18px, 3vw, 48px) 72px;
  display: grid;
  gap: 28px;
  min-width: 0;
}
.catalog-frame :deep(.catalog-kicker) {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--blue-600);
  font: 11px/1.4 var(--font-mono);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.catalog-frame :deep(.catalog-kicker)::before {
  content: '';
  width: 18px;
  height: 3px;
  background: var(--blue-500);
}
.catalog-frame :deep(.catalog-heading) {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  border-bottom: 1px solid var(--line);
  padding-bottom: 27px;
}
.catalog-frame :deep(.catalog-heading h1) {
  font: 720 clamp(28px, 3.2vw, 44px) / 1.2 var(--font-sans);
  letter-spacing: -0.045em;
  margin: 14px 0 12px;
  overflow-wrap: anywhere;
}
.catalog-frame :deep(.catalog-heading p) {
  font-size: 14px;
  color: var(--ink-500);
  line-height: 1.75;
  margin: 0;
  max-width: 65ch;
}
.catalog-frame :deep(.catalog-heading .catalog-counter) {
  display: grid;
  gap: 5px;
  flex: none;
  text-align: right;
  font: 11px var(--font-mono);
  color: var(--ink-500);
}
.catalog-frame :deep(.catalog-counter b) {
  font-size: 34px;
  font-weight: 500;
  color: var(--ink-900);
}
.catalog-frame :deep(.catalog-search) {
  display: flex;
  align-items: center;
  gap: 14px;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  padding: 10px 10px 10px 20px;
  border-radius: 3px;
}
.catalog-frame :deep(.catalog-search:focus-within) {
  border-color: var(--blue-500);
  box-shadow: var(--ring);
}
.catalog-frame :deep(.catalog-search input) {
  min-width: 0;
  flex: 1;
  border: 0;
  box-shadow: none;
  outline: 0;
  padding: 8px 0;
  background: transparent;
  font-size: 14px;
}
.catalog-frame :deep(.catalog-search svg) {
  flex: none;
  color: var(--ink-500);
}
.catalog-frame :deep(.catalog-categories) {
  display: flex;
  gap: 4px;
  overflow-x: auto;
  border-bottom: 1px solid var(--line);
  padding-bottom: 12px;
  scrollbar-width: thin;
}
.catalog-frame :deep(.catalog-categories button) {
  padding: 10px 16px;
  white-space: nowrap;
  font-size: 13px;
  border: 1px solid transparent;
  color: var(--ink-500);
}
.catalog-frame :deep(.catalog-categories button:hover) {
  background: var(--surface-hover);
}
.catalog-frame :deep(.catalog-categories button.active) {
  color: var(--blue-700);
  background: var(--blue-100);
  border-color: var(--blue-200);
}
.catalog-frame :deep(.catalog-toolbar) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.catalog-frame :deep(.catalog-controls) {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}
.catalog-frame :deep(.catalog-controls label) {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: 11px;
  color: var(--ink-500);
}
.catalog-frame :deep(.catalog-controls select) {
  max-width: 210px;
  font-size: 12px;
  border: 1px solid var(--line);
  background: var(--surface);
  border-radius: 3px;
  padding: 9px 12px;
}
.catalog-frame :deep(.catalog-segment) {
  display: flex;
  border: 1px solid var(--line);
  background: var(--surface);
}
.catalog-frame :deep(.catalog-segment button) {
  padding: 8px 12px;
  color: var(--ink-500);
  font-size: 12px;
}
.catalog-frame :deep(.catalog-segment .active) {
  color: var(--blue-700);
  background: var(--blue-100);
}
.catalog-frame :deep(.catalog-caption) {
  font: 11px/1.8 var(--font-mono);
  color: var(--ink-500);
  margin: 0;
}
.catalog-frame :deep(.catalog-grid) {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 18px;
}
.catalog-frame :deep(.catalog-grid.list-view) {
  grid-template-columns: 1fr;
}
.catalog-frame :deep(.catalog-pagination) {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}
.catalog-frame :deep(.catalog-pagination .page-number) {
  padding: 8px 12px;
  border: 1px solid var(--line);
  font: 12px var(--font-mono);
}
.catalog-frame :deep(.catalog-pagination .page-number.active) {
  background: var(--blue-700);
  border-color: var(--blue-700);
  color: var(--surface);
}
.catalog-frame :deep(.catalog-breadcrumb) {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  align-items: center;
  color: var(--ink-500);
  font-size: 12px;
  overflow-wrap: anywhere;
}
.catalog-frame :deep(.catalog-breadcrumb a) {
  color: var(--blue-600);
}
.catalog-frame :deep(.catalog-dossier) {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 28px;
  align-items: start;
}
.catalog-frame :deep(.catalog-main) {
  display: grid;
  gap: 24px;
  min-width: 0;
}
.catalog-frame :deep(.catalog-aside) {
  display: grid;
  gap: 20px;
  position: sticky;
  top: calc(var(--topbar-h, 72px) + 24px);
  min-width: 0;
}
.catalog-frame :deep(.catalog-panel) {
  background: var(--surface);
  border: 1px solid var(--line);
  padding: 24px;
  min-width: 0;
  border-radius: 3px;
}
.catalog-frame :deep(.catalog-panel h2),
.catalog-frame :deep(.catalog-panel h3) {
  font: 650 17px/1.5 var(--font-sans);
  margin: 0 0 18px;
}
.catalog-frame :deep(.catalog-panel p) {
  line-height: 1.8;
}
.catalog-frame :deep(.catalog-section-heading) {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.catalog-frame :deep(.catalog-section-heading h2) {
  font: 650 20px/1.4 var(--font-sans);
  margin: 0;
}
.catalog-frame :deep(.catalog-section-heading small) {
  font: 11px var(--font-mono);
  color: var(--ink-500);
}
.catalog-frame :deep(.catalog-tabs) {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid var(--line);
  overflow-x: auto;
}
.catalog-frame :deep(.catalog-tabs button) {
  padding: 14px 0;
  border-bottom: 2px solid transparent;
  color: var(--ink-500);
  white-space: nowrap;
  font-size: 14px;
}
.catalog-frame :deep(.catalog-tabs .active) {
  border-bottom-color: var(--blue-500);
  color: var(--blue-700);
}
.catalog-frame :deep(.catalog-tags) {
  display: flex;
  gap: 7px;
  flex-wrap: wrap;
}
.catalog-frame :deep(.catalog-tags > *) {
  padding: 4px 8px;
  background: var(--surface-soft);
  border: 1px solid var(--line-soft);
  font-size: 11px;
  color: var(--ink-500);
  overflow-wrap: anywhere;
}
.catalog-frame :deep(.catalog-stat-row) {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  margin: 22px 0;
  padding: 18px 0;
  gap: 8px;
}
.catalog-frame :deep(.catalog-stat-row > div) {
  display: grid;
  gap: 6px;
}
.catalog-frame :deep(.catalog-stat-row b) {
  font: 22px var(--font-mono);
}
.catalog-frame :deep(.catalog-stat-row span) {
  font-size: 11px;
  color: var(--ink-500);
}
.catalog-frame :deep(.catalog-facts) {
  display: grid;
  gap: 13px;
  margin: 0;
  font-size: 12px;
}
.catalog-frame :deep(.catalog-facts > div) {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  border-bottom: 1px solid var(--line-soft);
  padding-bottom: 12px;
}
.catalog-frame :deep(.catalog-facts dt) {
  color: var(--ink-500);
  flex: none;
}
.catalog-frame :deep(.catalog-facts dd) {
  margin: 0;
  text-align: right;
  overflow-wrap: anywhere;
}
.catalog-frame :deep(.catalog-muted) {
  color: var(--ink-500);
  font-size: 13px;
}
.catalog-frame :deep(.catalog-empty-note) {
  padding: 20px;
  background: var(--surface-soft);
  color: var(--ink-500);
  font-size: 13px;
  line-height: 1.8;
}
.catalog-frame :deep(.catalog-document) {
  max-width: 68ch;
  font: 400 16px/1.95 var(--font-reading);
  overflow-wrap: anywhere;
  white-space: pre-wrap;
  color: var(--ink-700);
}
.catalog-frame :deep(.markdown-content) {
  max-width: 68ch;
  font: 400 16px/1.9 var(--font-reading);
  overflow-wrap: anywhere;
}
.catalog-frame :deep(.markdown-content img) {
  max-width: 100%;
  height: auto;
}
.catalog-frame :deep(.markdown-content pre) {
  overflow: auto;
  max-width: 100%;
  padding: 18px;
  background: var(--surface-soft);
}
.catalog-frame :deep(.markdown-content table) {
  display: block;
  max-width: 100%;
  overflow: auto;
}
.catalog-frame :deep(.catalog-actions) {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.catalog-frame :deep(.catalog-aside .catalog-actions) {
  display: grid;
}
.catalog-frame :deep(.catalog-icon) {
  display: grid;
  place-items: center;
  width: 72px;
  height: 72px;
  flex: none;
  border: 1px solid var(--blue-200);
  background: var(--blue-100);
  color: var(--blue-700);
  font-size: 32px;
  font-weight: 700;
  overflow: hidden;
  border-radius: 4px;
}
.catalog-frame :deep(.catalog-icon img) {
  height: 100%;
  width: 100%;
  object-fit: cover;
}
.catalog-frame :deep(.catalog-intro) {
  display: flex;
  align-items: center;
  gap: 22px;
}
.catalog-frame :deep(.catalog-intro h1) {
  font: 700 clamp(26px, 3vw, 40px) / 1.25 var(--font-sans);
  margin: 8px 0;
  overflow-wrap: anywhere;
}
.catalog-frame :deep(.catalog-intro-copy) {
  min-width: 0;
}
.catalog-frame :deep(.catalog-summary) {
  font-size: 16px;
  line-height: 1.85;
  color: var(--ink-700);
  margin: 22px 0 0;
}
.catalog-frame :deep(.catalog-version) {
  font: 12px var(--font-mono);
  color: var(--blue-700);
  background: var(--blue-100);
  padding: 5px 8px;
}
.catalog-frame :deep(.catalog-link) {
  color: var(--blue-600);
  text-decoration: underline;
  text-underline-offset: 3px;
}
.catalog-frame :deep(.catalog-stars) {
  display: flex;
  gap: 4px;
  align-items: center;
  flex-wrap: wrap;
}
.catalog-frame :deep(.catalog-stars button) {
  font-size: 26px;
  padding: 4px;
  color: var(--ink-300);
}
.catalog-frame :deep(.catalog-stars button.active) {
  color: var(--warning);
}
.catalog-frame :deep(.catalog-stars button:hover) {
  color: var(--warning-ink);
}
.catalog-frame :deep(.catalog-rating-row) {
  display: grid;
  grid-template-columns: 20px 1fr 24px;
  gap: 9px;
  align-items: center;
  margin: 9px 0;
  font-size: 11px;
  color: var(--ink-500);
}
.catalog-frame :deep(.catalog-rating-track) {
  height: 5px;
  background: var(--line-soft);
}
.catalog-frame :deep(.catalog-rating-track i) {
  display: block;
  height: 100%;
  background: var(--blue-500);
}
@media (max-width: 1100px) {
  .catalog-frame :deep(.catalog-grid) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .catalog-frame :deep(.catalog-dossier) {
    grid-template-columns: minmax(0, 1fr) 260px;
    gap: 20px;
  }
}
@media (max-width: 850px) {
  .catalog-frame :deep(.catalog-dossier) {
    grid-template-columns: 1fr;
  }
  .catalog-frame :deep(.catalog-aside) {
    position: static;
    grid-row: 1;
  }
  .catalog-frame :deep(.catalog-aside .catalog-actions) {
    display: flex;
  }
  .catalog-frame :deep(.catalog-aside .catalog-actions > *) {
    flex: 1;
  }
}
@media (max-width: 620px) {
  .catalog-frame {
    padding: 24px 16px 80px;
    gap: 22px;
  }
  .catalog-frame :deep(.catalog-heading) {
    align-items: flex-start;
  }
  .catalog-frame :deep(.catalog-heading h1) {
    font-size: 29px;
  }
  .catalog-frame :deep(.catalog-grid) {
    grid-template-columns: 1fr;
  }
  .catalog-frame :deep(.catalog-panel) {
    padding: 18px;
  }
  .catalog-frame :deep(.catalog-search) {
    gap: 8px;
    padding-left: 12px;
  }
  .catalog-frame :deep(input),
  .catalog-frame :deep(textarea),
  .catalog-frame :deep(select) {
    font-size: 16px !important;
  }
  .catalog-frame :deep(.catalog-search .btn) {
    padding: 10px;
    font-size: 12px;
    white-space: nowrap;
  }
  .catalog-frame :deep(.catalog-intro) {
    gap: 16px;
  }
  .catalog-frame :deep(.catalog-icon) {
    width: 58px;
    height: 58px;
  }
  .catalog-frame :deep(.catalog-controls select) {
    max-width: 185px;
  }
  .catalog-frame :deep(.catalog-heading .catalog-counter) {
    display: none;
  }
}

.catalog-frame :deep(.catalog-workspace) {
  display: grid;
  grid-template-columns: 190px minmax(0, 1fr);
  gap: 36px;
  align-items: start;
}
.catalog-frame :deep(.catalog-filter-rail) {
  position: sticky;
  top: calc(var(--topbar-h, 64px) + 24px);
  min-width: 0;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
  padding-left: 14px;
  scrollbar-width: thin;
}
.catalog-frame :deep(.catalog-results) {
  display: grid;
  gap: 24px;
  min-width: 0;
}
.catalog-frame :deep(.query-console) {
  background: transparent;
  padding: 0;
  display: grid;
  gap: 18px;
}
.catalog-frame :deep(.query-console__head) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font: 700 20px/1.4 var(--font-editorial, serif);
  color: var(--ink-900);
}
.catalog-frame :deep(.query-console__head small) {
  font: 10px var(--font-sans);
  color: var(--blue-600);
}
.catalog-frame :deep(.query-console .catalog-search) {
  background: var(--surface-soft);
}
.catalog-frame :deep(.query-console .catalog-toolbar) {
  gap: 14px;
}
.catalog-frame :deep(.query-console .catalog-controls) {
  gap: 12px;
}
.catalog-frame :deep(.query-console .catalog-controls label) {
  gap: 8px;
}
.catalog-frame :deep(.query-selection) {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  border-top: 1px dashed var(--line);
  padding-top: 15px;
}
.catalog-frame :deep(.query-selection > span) {
  font-size: 10px;
  color: var(--ink-500);
  margin-right: 4px;
}
.catalog-frame :deep(.query-selection button) {
  display: inline-flex;
  align-items: center;
  gap: 12px;
  max-width: 100%;
  padding: 6px 8px;
  font-size: 10px;
  border: 1px solid var(--blue-200);
  background: var(--blue-50);
  color: var(--blue-700);
  overflow-wrap: anywhere;
}
.catalog-frame :deep(.query-selection b) {
  font-weight: 400;
  font-size: 14px;
}
.catalog-frame :deep(.workspace-result-head) {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  padding: 0 0 16px;
  border-bottom: 1px solid var(--line-strong);
}
.catalog-frame :deep(.edition-index-label) {
  color: var(--blue-700);
  font-size: 11px;
  letter-spacing: .12em;
}
.catalog-frame :deep(.workspace-result-head h2) {
  font: 800 clamp(27px, 3vw, 40px)/1.3 var(--font-editorial, serif);
  margin: 8px 0 0;
}
.catalog-frame :deep(.workspace-result-head h2 small) {
  font: 11px var(--font-mono);
  color: var(--ink-500);
  margin-left: 12px;
}
.catalog-frame :deep(.workspace-guide) {
  margin-top: 26px;
  border-top: 2px solid var(--line);
  padding-top: 18px;
  font-size: 11px;
}
.catalog-frame :deep(.workspace-guide span) {
  color: var(--ink-700);
  font-weight: 600;
}
.catalog-frame :deep(.workspace-guide p) {
  color: var(--ink-500);
  line-height: 1.8;
  margin: 8px 0 14px;
}
.catalog-frame :deep(.workspace-guide a) {
  color: var(--blue-600);
}
.catalog-frame :deep(.workspace-filter-error) {
  font-size: 11px;
  padding: 16px 0;
  line-height: 1.8;
  color: var(--danger-ink);
}
.catalog-frame :deep(.workspace-filter-error button) {
  display: block;
  margin-top: 6px;
}
@media (min-width: 981px) and (max-width: 1300px) {
  .catalog-frame :deep(.catalog-results .catalog-grid:not(.list-view)) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
@media (max-width: 980px) {
  .catalog-frame :deep(.catalog-workspace) {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .catalog-frame :deep(.catalog-filter-rail) {
    position: static;
    max-height: none;
    padding: 0;
    overflow: visible;
  }
  .catalog-frame :deep(.workspace-guide) {
    display: none;
  }
}
@media (max-width: 620px) {
  .catalog-frame :deep(.query-console) {
    padding: 15px;
    gap: 14px;
  }
  .catalog-frame :deep(.workspace-result-head) {
    align-items: start;
  }
  .catalog-frame :deep(.workspace-result-head .catalog-caption) {
    max-width: 110px;
    text-align: right;
  }
}

/* Shared resource dossiers: the document and its acquisition record stay distinct. */
.catalog-frame.dossier-page {
  gap: 24px;
}
.catalog-frame.dossier-page :deep(.dossier-identity) {
  padding: 0;
  background: var(--surface);
  border: 0;
  border-block: 4px double var(--ink-500);
}
.catalog-frame :deep(.dossier-register) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 11px 0;
  border-bottom: 1px solid var(--line-strong);
  color: var(--ink-500);
  font: 11px/1.5 var(--font-sans);
}
.catalog-frame :deep(.dossier-signature) {
  color: var(--blue-700);
  font: italic 400 clamp(20px, 2.4vw, 30px)/1.2 var(--font-script, serif);
}
.catalog-frame :deep(.dossier-register > span:last-child) {
  display: flex;
  align-items: center;
  gap: 10px;
}
.catalog-frame :deep(.dossier-register i) {
  display: block;
  width: 3px;
  height: 3px;
  background: var(--blue-500);
}
.catalog-frame :deep(.dossier-identity__body) {
  padding: clamp(24px, 3.6vw, 46px) 0;
}
.catalog-frame :deep(.dossier-identity__body .catalog-intro h1) {
  margin: 7px 0 11px;
  color: var(--ink-900);
  font: 700 clamp(34px, 4.4vw, 60px)/1.15 var(--font-editorial, serif);
  letter-spacing: -.015em;
}
.catalog-frame :deep(.dossier-identity__body .catalog-icon) {
  width: 86px;
  height: 86px;
  border: 1px solid var(--line);
  background: var(--surface);
  border-radius: 3px;
}
.catalog-frame :deep(.dossier-identity__body .catalog-kicker) {
  font-size: 9px;
  letter-spacing: 0.08em;
}
.catalog-frame :deep(.dossier-identity__body .catalog-kicker)::before {
  width: 10px;
  height: 2px;
}
.catalog-frame :deep(.dossier-identity__body .catalog-summary) {
  max-width: 58ch;
  font: 400 clamp(16px, 1.6vw, 21px)/1.75 var(--font-reading);
}
.catalog-frame :deep(.dossier-identity__foot) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 14px;
  border-top: 1px solid var(--line);
  padding: 12px 0;
  font-size: 11px;
  color: var(--ink-500);
}
.catalog-frame :deep(.dossier-identity__foot .catalog-tags > *) {
  background: none;
  padding: 3px 8px;
  font-size: 10px;
}
.catalog-frame.dossier-page :deep(.catalog-dossier) {
  grid-template-columns: minmax(0, 1fr) 310px;
  gap: 26px;
}
.catalog-frame.dossier-page :deep(.catalog-main) {
  gap: 22px;
  align-content: start;
}
.catalog-frame.dossier-page :deep(.catalog-aside) {
  top: calc(var(--topbar-h, 64px) + 88px);
}
.catalog-frame.dossier-page :deep(.catalog-panel) {
  border-radius: 0;
}
.catalog-frame.dossier-page :deep(.catalog-panel h2) {
  font: 700 clamp(20px, 2vw, 28px)/1.45 var(--font-editorial, serif);
}
.catalog-frame.dossier-page :deep(.catalog-main .catalog-panel) {
  border: 0;
  border-top: 1px solid var(--line-strong);
  padding: clamp(18px, 2.5vw, 34px) clamp(16px, 2.3vw, 30px);
}
.catalog-frame.dossier-page :deep(.catalog-main .catalog-kicker) {
  font: 600 12px/1.5 var(--font-editorial, serif);
  letter-spacing: .12em;
}
.catalog-frame.dossier-page :deep(.catalog-main .catalog-kicker)::before {
  height: 4px;
  border-block: 1px solid currentColor;
  background: transparent;
}
.catalog-frame :deep(.dossier-chapter),
.catalog-frame :deep(.dossier-chapter [id]) {
  scroll-margin-top: calc(var(--topbar-h, 64px) + 88px);
}
.catalog-frame :deep(.document-header) {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin: 22px 0;
  padding-bottom: 18px;
  border-bottom: 3px double var(--line-strong);
}
.catalog-frame :deep(.document-header h2) {
  margin: 0;
}
.catalog-frame :deep(.document-header > span) {
  font: 9px var(--font-mono);
  color: var(--ink-500);
}
.catalog-frame.dossier-page :deep(.acquisition) {
  border-top: 4px double var(--blue-700);
  background: var(--surface);
}
.catalog-frame :deep(.acquisition-label) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  font: 700 17px/1.5 var(--font-editorial, serif);
  color: var(--blue-700);
}
.catalog-frame :deep(.acquisition-label small) {
  font: 10px var(--font-sans);
  color: var(--ink-500);
}
.catalog-frame.dossier-page :deep(.acquisition h2) {
  font: 28px/1.2 var(--font-mono);
  overflow-wrap: anywhere;
}
.catalog-frame.dossier-page :deep(.acquisition .catalog-muted) {
  font-size: 11px;
  margin: 12px 0 22px;
}
.catalog-frame.dossier-page :deep(.catalog-stat-row b) {
  font-size: 20px;
}
.catalog-frame.dossier-page :deep(.catalog-stat-row span) {
  font-size: 10px;
}
.catalog-frame.dossier-page :deep(.release-row),
.catalog-frame.dossier-page :deep(.skill-release) {
  position: relative;
  padding: 22px;
  margin: 18px 0 0;
  border: 1px solid var(--line);
  border-left: 3px solid var(--line-strong);
  background: var(--surface);
}
.catalog-frame.dossier-page :deep(.release-row.is-selected),
.catalog-frame.dossier-page :deep(.skill-release.is-selected) {
  background: var(--blue-50);
  border-left-color: var(--blue-500);
}
.catalog-frame.dossier-page :deep(.release-row.is-withdrawn) {
  background: var(--surface-soft);
}
.catalog-frame.dossier-page :deep(.release-row header),
.catalog-frame.dossier-page :deep(.skill-release header) {
  gap: 10px;
  flex-wrap: wrap;
  justify-content: start;
}
.catalog-frame.dossier-page :deep(.skill-release time) {
  margin-left: auto;
}
.catalog-frame.dossier-page :deep(.release-row .release-selected),
.catalog-frame.dossier-page :deep(.release-selected) {
  background: var(--blue-100);
  color: var(--blue-700);
  padding: 4px 7px;
  font: 9px var(--font-mono);
}
.catalog-frame.dossier-page :deep(.release-row .release-stable) {
  color: var(--ink-500);
}
.catalog-frame.dossier-page :deep(.release-row .catalog-actions),
.catalog-frame.dossier-page :deep(.skill-release .release-bottom) {
  border-top: 1px dashed var(--line);
  padding-top: 16px;
  margin-top: 18px;
}
.catalog-frame.dossier-page :deep(.skill-document) {
  font: 12px/1.95 var(--font-mono);
  padding: 20px;
  background: var(--surface-soft);
  border: 1px solid var(--line-soft);
  tab-size: 2;
}
.catalog-frame :deep(.mobile-acquire) {
  display: none;
}
@media (max-width: 1100px) {
  .catalog-frame.dossier-page :deep(.catalog-dossier) {
    grid-template-columns: minmax(0, 1fr) 270px;
    gap: 20px;
  }
  .catalog-frame :deep(.dossier-identity__body) {
    padding: 26px 0;
  }
}
@media (max-width: 850px) {
  .catalog-frame.dossier-page :deep(.catalog-dossier) {
    grid-template-columns: 1fr;
  }
  .catalog-frame.dossier-page :deep(.catalog-aside) {
    display: contents;
  }
  .catalog-frame.dossier-page :deep(.catalog-main) {
    grid-row: 2;
  }
  .catalog-frame.dossier-page :deep(.acquisition) {
    grid-row: 1;
  }
  .catalog-frame.dossier-page :deep(.community-rating) {
    grid-row: 3;
  }
  .catalog-frame.dossier-page :deep(.acquisition .catalog-facts) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }
  .catalog-frame.dossier-page :deep(.acquisition .catalog-facts > div) {
    display: grid;
    gap: 6px;
    align-content: start;
  }
  .catalog-frame.dossier-page :deep(.acquisition .catalog-facts dd) {
    text-align: left;
  }
}
@media (max-width: 620px) {
  .catalog-frame.dossier-page {
    gap: 18px;
  }
  .catalog-frame :deep(.dossier-register) {
    padding: 8px 0;
    font-size: 10px;
  }
  .catalog-frame :deep(.dossier-register > span:last-child) {
    gap: 6px;
  }
  .catalog-frame :deep(.dossier-identity__body) {
    padding: 22px 0;
  }
  .catalog-frame :deep(.dossier-identity__body .catalog-icon) {
    width: 60px;
    height: 60px;
  }
  .catalog-frame :deep(.dossier-identity__body .catalog-summary) {
    font-size: 15px;
  }
  .catalog-frame :deep(.dossier-identity__foot) {
    padding: 10px 0;
  }
  .catalog-frame :deep(.dossier-identity__foot > span) {
    display: none;
  }
  .catalog-frame.dossier-page :deep(.release-row),
  .catalog-frame.dossier-page :deep(.skill-release) {
    padding: 16px;
  }
  .catalog-frame :deep(.dossier-chapter),
  .catalog-frame :deep(.dossier-chapter [id]) {
    scroll-margin-top: calc(var(--topbar-h, 64px) + 66px);
  }
  .catalog-frame.dossier-page :deep(.acquisition .catalog-facts) {
    grid-template-columns: 1fr;
    gap: 10px;
  }
  .catalog-frame.dossier-page :deep(.acquisition .catalog-facts > div) {
    display: flex;
  }
  .catalog-frame.dossier-page :deep(.acquisition .catalog-facts dd) {
    text-align: right;
  }
  .catalog-frame :deep(.mobile-acquire) {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 29;
    padding: 12px 16px calc(12px + env(safe-area-inset-bottom));
    gap: 14px;
    align-items: center;
    justify-content: space-between;
    background: var(--surface);
    border-top: 1px solid var(--line);
  }
  .catalog-frame :deep(.mobile-acquire > span) {
    min-width: 0;
    font-size: 12px;
    font-weight: 600;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .catalog-frame :deep(.mobile-acquire small) {
    display: block;
    font: 10px var(--font-mono);
    margin-top: 4px;
    color: var(--ink-500);
  }
  .catalog-frame :deep(.mobile-acquire .btn) {
    flex: none;
  }
}

.catalog-frame :deep(.edition-index:not(.list-view)) {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 2px clamp(20px, 3vw, 40px);
}
.catalog-frame :deep(.edition-index.list-view) { gap: 0; }
.catalog-frame.dossier-page :deep(.article-columns .catalog-main .catalog-panel) {
  border: 0;
  padding: 0 0 20px;
  background: transparent;
}
.catalog-frame.dossier-page :deep(.article-columns .catalog-main .catalog-panel h2:first-child) {
  margin-top: 0 !important;
}
.catalog-frame.dossier-page :deep(.article-columns .catalog-aside) {
  border-left: 1px solid var(--line-strong);
  padding-left: clamp(16px, 2vw, 26px);
}
.catalog-frame.dossier-page :deep(.article-columns .catalog-aside .catalog-panel) {
  padding: 14px 0;
  border: 0;
  background: transparent;
}
.catalog-frame.dossier-page :deep(.article-columns .acquisition-label) {
  color: var(--ink-900);
}
@media(min-width: 1181px) {
  .catalog-frame.dossier-page :deep(.article-columns) {
    grid-template-columns: minmax(78px, .16fr) minmax(0, 1fr) minmax(205px, .47fr);
    gap: clamp(20px, 2.1vw, 34px);
  }
  .catalog-frame.dossier-page :deep(.article-columns .catalog-aside) {
    top: calc(var(--topbar-h, 64px) + 18px);
  }
  .catalog-frame.dossier-page :deep(.dossier-chapter),
  .catalog-frame.dossier-page :deep(.dossier-chapter [id]) {
    scroll-margin-top: calc(var(--topbar-h, 64px) + 24px);
  }
}
@media(max-width: 1180px) {
  .catalog-frame.dossier-page :deep(.article-columns > .dossier-navigation) {
    grid-column: 1 / -1;
  }
}
@media(max-width: 850px) {
  .catalog-frame.dossier-page :deep(.article-columns .catalog-main) { grid-row: 2; }
  .catalog-frame.dossier-page :deep(.article-columns .acquisition) { grid-row: 3; }
  .catalog-frame.dossier-page :deep(.article-columns .community-rating) { grid-row: 4; }
  .catalog-frame.dossier-page :deep(.article-columns .catalog-aside .catalog-panel) {
    border-top: 1px solid var(--line-strong);
    padding-block: 18px;
  }
}
@media(max-width: 620px) {
  .catalog-frame :deep(.edition-index:not(.list-view)) { grid-template-columns: 1fr; }
  .catalog-frame :deep(.query-console) { padding: 0; }
}
</style>
