<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  onUpdated,
  reactive,
  ref,
  useAttrs,
  useId,
  watch,
} from 'vue';

defineOptions({ inheritAttrs: false });
const props = withDefaults(
  defineProps<{
    value?: string | null;
    modelValue?: string | null;
    type?: 'date' | 'datetime-local';
    min?: string;
    max?: string;
    name?: string;
    id?: string;
    disabled?: boolean;
    required?: boolean;
    placeholder?: string;
  }>(),
  { type: 'datetime-local' },
);
const emit = defineEmits<{
  'update:modelValue': [value: string];
  input: [event: Event];
  change: [event: Event];
}>();
const attrs = useAttrs(),
  uid = useId();
const root = ref<HTMLElement>(),
  trigger = ref<HTMLButtonElement>(),
  native = ref<HTMLInputElement>(),
  popup = ref<HTMLElement>();
const open = ref(false),
  validationShown = ref(false),
  fieldLabel = ref('');
const portal = ref<HTMLElement | string>('body'),
  popupStyle = ref<Record<string, string>>({});
const draft = reactive({ year: '', month: '', day: '', hour: '', minute: '' });
const viewYear = ref(2026),
  viewMonth = ref(1),
  focusedDate = ref('');
const popupId = `market-date-${uid}`,
  errorId = `${popupId}-error`;
const currentValue = computed(() =>
  String(
    props.modelValue !== undefined
      ? (props.modelValue ?? '')
      : (props.value ?? ''),
  ),
);
const hasTime = computed(() => props.type === 'datetime-local');
const label = computed(() =>
  String(
    attrs['aria-label'] ||
      fieldLabel.value ||
      (hasTime.value ? '选择日期和时间' : '选择日期'),
  ),
);
const buttonAttrs = computed(() =>
  Object.fromEntries(
    Object.entries(attrs).filter(
      ([key]) => !['class', 'style', 'aria-label'].includes(key),
    ),
  ),
);
const weekdays = ['一', '二', '三', '四', '五', '六', '日'];
const pad = (value: number | string, length = 2) =>
  String(value).padStart(length, '0');
function dateString(year: number, month: number, day: number) {
  return `${pad(year, 4)}-${pad(month)}-${pad(day)}`;
}
function monthDays(year: number, month: number) {
  return month === 2
    ? year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0)
      ? 29
      : 28
    : [4, 6, 9, 11].includes(month)
      ? 30
      : 31;
}
function mondayIndex(year: number, month: number, day = 1) {
  // UTC is only used for Gregorian weekday arithmetic, never to parse/format a
  // selected value. Wall-clock fields remain exactly as entered by the user.
  const date = new Date(0);
  date.setUTCFullYear(year, month - 1, day);
  return (date.getUTCDay() + 6) % 7;
}
function readValue(value: string) {
  return /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?$/.exec(value);
}
function todayParts() {
  const now = new Date();
  return [
    String(now.getFullYear()),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
  ];
}
function setDraft(parts: string[]) {
  [draft.year, draft.month, draft.day, draft.hour, draft.minute] = parts;
  syncView();
  focusedDate.value = dateString(
    viewYear.value,
    viewMonth.value,
    Math.min(
      Number(draft.day) || 1,
      monthDays(viewYear.value, viewMonth.value),
    ),
  );
}
function syncView() {
  const year = Number(draft.year),
    month = Number(draft.month);
  if (/^\d{4}$/.test(draft.year) && year >= 1 && year <= 9999)
    viewYear.value = year;
  if (/^\d{1,2}$/.test(draft.month) && month >= 1 && month <= 12)
    viewMonth.value = month;
}
function validate(fields: typeof draft): string {
  const values = hasTime.value
    ? Object.values(fields)
    : [fields.year, fields.month, fields.day];
  if (values.every((value) => !value))
    return props.required ? '请选择日期。' : '';
  if (
    !/^\d{4}$/.test(fields.year) ||
    !/^\d{1,2}$/.test(fields.month) ||
    !/^\d{1,2}$/.test(fields.day)
  )
    return '请填写完整的年、月、日。';
  const year = Number(fields.year),
    month = Number(fields.month),
    day = Number(fields.day);
  if (
    year < 1 ||
    year > 9999 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > monthDays(year, month)
  )
    return '日期无效，请检查月份与天数。';
  if (
    hasTime.value &&
    (!/^\d{1,2}$/.test(fields.hour) ||
      !/^\d{1,2}$/.test(fields.minute) ||
      Number(fields.hour) > 23 ||
      Number(fields.minute) > 59)
  )
    return '时间无效，请填写 00–23 时、00–59 分。';
  const value = serialize(fields);
  if (props.min && value < props.min)
    return `不能早于 ${props.min.replace('T', ' ')}。`;
  if (props.max && value > props.max)
    return `不能晚于 ${props.max.replace('T', ' ')}。`;
  return '';
}
function serialize(fields: typeof draft) {
  if (!fields.year && !fields.month && !fields.day) return '';
  const date = dateString(
    Number(fields.year),
    Number(fields.month),
    Number(fields.day),
  );
  return hasTime.value
    ? `${date}T${pad(Number(fields.hour))}:${pad(Number(fields.minute))}`
    : date;
}
const draftError = computed(() => validate(draft));
const weeks = computed(() => {
  const blank = mondayIndex(viewYear.value, viewMonth.value);
  const total = monthDays(viewYear.value, viewMonth.value);
  const cells = Array.from(
    { length: Math.ceil((blank + total) / 7) * 7 },
    (_, index) =>
      index < blank || index >= blank + total ? null : index - blank + 1,
  );
  return Array.from({ length: cells.length / 7 }, (_, index) =>
    cells.slice(index * 7, index * 7 + 7),
  );
});
function disabledDay(day: number) {
  const value = dateString(viewYear.value, viewMonth.value, day);
  return !!(
    (props.min && value < props.min.slice(0, 10)) ||
    (props.max && value > props.max.slice(0, 10))
  );
}
function selectedDay(day: number) {
  return (
    Number(draft.year) === viewYear.value &&
    Number(draft.month) === viewMonth.value &&
    Number(draft.day) === day
  );
}
function pickDay(day: number) {
  if (disabledDay(day)) return;
  draft.year = pad(viewYear.value, 4);
  draft.month = pad(viewMonth.value);
  draft.day = pad(day);
  if (!draft.hour) draft.hour = '00';
  if (!draft.minute) draft.minute = '00';
  focusedDate.value = dateString(viewYear.value, viewMonth.value, day);
  validationShown.value = false;
}
function moveMonth(delta: number) {
  const next = viewYear.value * 12 + viewMonth.value - 1 + delta;
  const year = Math.floor(next / 12),
    month = (next % 12) + 1;
  if (year < 1 || year > 9999) return;
  viewYear.value = year;
  viewMonth.value = month;
  focusedDate.value = dateString(year, month, 1);
}
function focusDay() {
  void nextTick(() =>
    popup.value
      ?.querySelector<HTMLButtonElement>(`[data-date="${focusedDate.value}"]`)
      ?.focus(),
  );
}
function calendarKey(event: KeyboardEvent, day: number) {
  const moves: Record<string, number> = {
    ArrowLeft: -1,
    ArrowRight: 1,
    ArrowUp: -7,
    ArrowDown: 7,
    Home: -mondayIndex(viewYear.value, viewMonth.value, day),
    End: 6 - mondayIndex(viewYear.value, viewMonth.value, day),
  };
  if (event.key === 'PageUp' || event.key === 'PageDown') {
    event.preventDefault();
    moveMonth(event.key === 'PageUp' ? -1 : 1);
    focusDay();
    return;
  }
  if (!(event.key in moves)) return;
  event.preventDefault();
  let year = viewYear.value,
    month = viewMonth.value,
    next = day + moves[event.key];
  if (next < 1) {
    month--;
    if (month < 1) {
      month = 12;
      year--;
    }
    if (year < 1) return;
    next += monthDays(year, month);
  }
  if (next > monthDays(year, month)) {
    next -= monthDays(year, month);
    month++;
    if (month > 12) {
      month = 1;
      year++;
    }
    if (year > 9999) return;
  }
  const nextDate = dateString(year, month, next);
  if (
    (props.min && nextDate < props.min.slice(0, 10)) ||
    (props.max && nextDate > props.max.slice(0, 10))
  )
    return;
  viewYear.value = year;
  viewMonth.value = month;
  focusedDate.value = dateString(year, month, next);
  focusDay();
}
function position() {
  if (!open.value || !trigger.value) return;
  const rect = trigger.value.getBoundingClientRect(),
    viewport = window.visualViewport;
  const width = viewport?.width || window.innerWidth,
    height = viewport?.height || window.innerHeight;
  const left = viewport?.offsetLeft || 0,
    top = viewport?.offsetTop || 0;
  const menuWidth = Math.max(0, Math.min(352, width - 24));
  const desiredHeight =
    popup.value?.scrollHeight || (hasTime.value ? 540 : 480);
  const below = top + height - rect.bottom - 12,
    above = rect.top - top - 12;
  const flip = below < Math.min(desiredHeight, 300) && above > below;
  const available = Math.max(below, above);
  const menuHeight = Math.min(
    desiredHeight,
    Math.max(100, available - 6),
    Math.max(0, height - 24),
  );
  const proposedTop = flip ? rect.top - menuHeight - 6 : rect.bottom + 6;
  popupStyle.value = {
    left: `${Math.min(Math.max(left + 12, rect.left), left + width - menuWidth - 12)}px`,
    top: `${Math.max(top + 12, Math.min(proposedTop, top + height - menuHeight - 12))}px`,
    width: `${menuWidth}px`,
    maxHeight: `${menuHeight}px`,
  };
}
function show() {
  if (props.disabled) return;
  const parts = readValue(currentValue.value);
  setDraft(
    parts
      ? [parts[1], parts[2], parts[3], parts[4] || '00', parts[5] || '00']
      : todayParts(),
  );
  validationShown.value = false;
  portal.value =
    trigger.value?.closest<HTMLDialogElement>('dialog[open]') || document.body;
  open.value = true;
  void nextTick(() => {
    position();
    focusDay();
    if (popup.value && !popup.value.contains(document.activeElement))
      popup.value
        .querySelector<HTMLInputElement>('[data-part="year"]')
        ?.focus();
  });
}
function close(returnFocus = true) {
  open.value = false;
  if (returnFocus) trigger.value?.focus({ preventScroll: true });
}
function nativeInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value);
  emit('input', event);
}
function commit(value: string) {
  if (props.disabled) return;
  if (native.value && value !== currentValue.value) {
    native.value.value = value;
    native.value.dispatchEvent(new Event('input', { bubbles: true }));
    native.value.dispatchEvent(new Event('change', { bubbles: true }));
  }
  close();
}
function apply() {
  validationShown.value = true;
  if (!draftError.value) commit(serialize(draft));
}
function clear() {
  if (!props.required) commit('');
}
function today() {
  setDraft(todayParts());
  validationShown.value = false;
  focusDay();
}
function outside(event: Event) {
  const target = event.target as Node;
  if (!root.value?.contains(target) && !popup.value?.contains(target))
    close(false);
}
function popupKey(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault();
    event.stopPropagation();
    close();
    return;
  }
  if (event.key === 'Enter' && event.target instanceof HTMLInputElement) {
    event.preventDefault();
    apply();
    return;
  }
  if (event.key !== 'Tab') return;
  const fields = Array.from(
    popup.value?.querySelectorAll<HTMLElement>(
      'button:not(:disabled), input:not(:disabled)',
    ) || [],
  ).filter((node) => node.tabIndex >= 0);
  const first = fields[0],
    last = fields[fields.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last?.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first?.focus();
  }
}
function updateNativeValidity() {
  if (!native.value) return;
  const parts = readValue(currentValue.value);
  native.value.setCustomValidity(
    currentValue.value && !parts
      ? '日期格式无效。'
      : parts
        ? validate({
            year: parts[1],
            month: parts[2],
            day: parts[3],
            hour: parts[4] || '',
            minute: parts[5] || '',
          })
        : '',
  );
}
let resizeObserver: ResizeObserver | undefined;
function scroll(event: Event) {
  if (!popup.value?.contains(event.target as Node)) position();
}
watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) close(false);
  },
);
watch(
  [currentValue, () => props.min, () => props.max, () => props.type],
  () => {
    updateNativeValidity();
    if (open.value) close(false);
  },
);
function syncLabel() {
  const parent = root.value?.closest('label');
  if (!parent) return;
  function words(node: Node): string {
    if (
      node === root.value ||
      (node instanceof HTMLElement &&
        node.matches('small, [aria-hidden="true"]'))
    )
      return '';
    if (node.nodeType === Node.TEXT_NODE) return node.textContent || '';
    return Array.from(node.childNodes).map(words).join(' ');
  }
  fieldLabel.value = words(parent).replace(/\s+/g, ' ').trim();
}
onUpdated(syncLabel);
onMounted(() => {
  syncLabel();
  updateNativeValidity();
  document.addEventListener('pointerdown', outside);
  document.addEventListener('focusin', outside);
  window.addEventListener('resize', position);
  window.addEventListener('scroll', scroll, true);
  window.visualViewport?.addEventListener('resize', position);
  if (typeof ResizeObserver !== 'undefined' && trigger.value) {
    resizeObserver = new ResizeObserver(position);
    resizeObserver.observe(trigger.value);
  }
});
onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  document.removeEventListener('pointerdown', outside);
  document.removeEventListener('focusin', outside);
  window.removeEventListener('resize', position);
  window.removeEventListener('scroll', scroll, true);
  window.visualViewport?.removeEventListener('resize', position);
});
</script>

<template>
  <span
    ref="root"
    class="market-datetime"
    :class="[attrs.class, { 'is-open': open }]"
    :style="attrs.style as any"
  >
    <button
      :id="id"
      ref="trigger"
      v-bind="buttonAttrs"
      type="button"
      class="market-datetime-trigger"
      :aria-label="label"
      aria-haspopup="dialog"
      :aria-controls="popupId"
      :aria-expanded="open"
      :disabled="disabled"
      @click="open ? close() : show()"
      @keydown.esc="open && popupKey($event)"
      @keydown.down.prevent="show()"
    >
      <span :class="{ 'is-placeholder': !currentValue }">{{
        currentValue
          ? currentValue.replace('T', ' ')
          : placeholder || (hasTime ? '选择日期和时间' : '选择日期')
      }}</span
      ><svg
        viewBox="0 0 24 24"
        width="18"
        height="18"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        aria-hidden="true"
      >
        <rect x="3" y="5" width="18" height="16" rx="1" />
        <path d="M7 2v6m10-6v6M3 11h18m-12 4h3m3 0h3m-9 3h3" />
      </svg>
    </button>
    <input
      ref="native"
      class="market-datetime-native"
      type="text"
      hidden
      :value="currentValue"
      :name="name"
      :required="required"
      :disabled="disabled"
      tabindex="-1"
      aria-hidden="true"
      @input="nativeInput"
      @change="emit('change', $event)"
      @invalid.prevent="show()"
    />
    <Teleport :to="portal">
      <section
        v-if="open"
        :id="popupId"
        ref="popup"
        class="market-datetime-popup"
        role="dialog"
        :aria-label="label"
        :style="popupStyle"
        @keydown="popupKey"
        @click.stop
      >
        <header>
          <span>MOFOX / LOCAL TIME</span
          ><button
            type="button"
            class="market-date-close"
            aria-label="取消选择"
            @click="close()"
          >
            ×
          </button>
        </header>
        <div class="market-date-month">
          <button
            type="button"
            aria-label="上个月"
            :disabled="viewYear === 1 && viewMonth === 1"
            @click="moveMonth(-1)"
          >
            ←</button
          ><strong aria-live="polite"
            >{{ viewYear }} 年 {{ viewMonth }} 月</strong
          ><button
            type="button"
            aria-label="下个月"
            :disabled="viewYear === 9999 && viewMonth === 12"
            @click="moveMonth(1)"
          >
            →
          </button>
        </div>
        <table class="market-date-calendar" aria-label="选择日期">
          <thead>
            <tr>
              <th v-for="day in weekdays" :key="day" scope="col">{{ day }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(week, index) in weeks" :key="index">
              <td v-for="(day, column) in week" :key="column">
                <button
                  v-if="day"
                  type="button"
                  :data-date="dateString(viewYear, viewMonth, day)"
                  :aria-label="dateString(viewYear, viewMonth, day)"
                  :aria-pressed="selectedDay(day)"
                  :tabindex="
                    dateString(viewYear, viewMonth, day) === focusedDate
                      ? 0
                      : -1
                  "
                  :disabled="disabledDay(day)"
                  @click="pickDay(day)"
                  @keydown="calendarKey($event, day)"
                >
                  {{ day }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="market-date-fields">
          <label
            >年<input
              v-model="draft.year"
              data-part="year"
              aria-label="年"
              inputmode="numeric"
              maxlength="4"
              autocomplete="off"
              @input="syncView" /></label
          ><label
            >月<input
              v-model="draft.month"
              data-part="month"
              aria-label="月"
              inputmode="numeric"
              maxlength="2"
              autocomplete="off"
              @input="syncView" /></label
          ><label
            >日<input
              v-model="draft.day"
              data-part="day"
              aria-label="日"
              inputmode="numeric"
              maxlength="2"
              autocomplete="off" /></label
          ><template v-if="hasTime"
            ><label
              >时<input
                v-model="draft.hour"
                data-part="hour"
                aria-label="小时"
                inputmode="numeric"
                maxlength="2"
                autocomplete="off" /></label
            ><label
              >分<input
                v-model="draft.minute"
                data-part="minute"
                aria-label="分钟"
                inputmode="numeric"
                maxlength="2"
                autocomplete="off" /></label
          ></template>
        </div>
        <p class="market-date-hint">
          {{
            hasTime
              ? '按本地时间填写，不进行时区转换。'
              : '选择日期后应用筛选。'
          }}
        </p>
        <p
          v-if="validationShown && draftError"
          :id="errorId"
          class="market-date-error"
          role="alert"
        >
          {{ draftError }}
        </p>
        <footer>
          <button type="button" class="market-date-text" @click="today">
            今天</button
          ><button
            type="button"
            class="market-date-text"
            :disabled="required"
            @click="clear"
          >
            清除</button
          ><span /><button
            type="button"
            class="market-date-cancel"
            @click="close()"
          >
            取消</button
          ><button type="button" class="market-date-apply" @click="apply">
            应用
          </button>
        </footer>
      </section>
    </Teleport>
  </span>
</template>

<style>
.market-datetime {
  display: inline-flex;
  position: relative;
  min-width: 170px;
  max-width: 100%;
  padding: 0 !important;
  border: 0 !important;
  background: none !important;
  vertical-align: middle;
}
.market-datetime-trigger {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 40px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--surface);
  color: var(--ink-900);
  font: 13px/1.4 var(--font-sans);
  text-align: left;
}
.market-datetime-trigger > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.market-datetime-trigger svg {
  flex: none;
  color: var(--blue-600);
}
.market-datetime-trigger .is-placeholder {
  color: var(--ink-500);
}
.market-datetime-trigger:hover,
.market-datetime.is-open .market-datetime-trigger {
  border-color: var(--blue-500);
}
.market-datetime-trigger:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: 3px;
}
.market-datetime-trigger:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.market-datetime-native {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  min-width: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  opacity: 0;
  clip-path: inset(50%);
  pointer-events: none;
}
.market-datetime-popup {
  position: fixed;
  z-index: 1601;
  box-sizing: border-box;
  overflow: auto;
  overscroll-behavior: contain;
  padding: 16px;
  border: 1px solid var(--line-strong);
  border-top: 2px solid var(--blue-500);
  border-radius: 2px;
  background: var(--surface);
  color: var(--ink-900);
  box-shadow: var(--shadow-2);
  font: 13px/1.5 var(--font-sans);
}
.market-datetime-popup header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 10px;
  margin-bottom: 12px;
}
.market-datetime-popup header > span {
  color: var(--ink-500);
  font: 9px var(--font-mono);
  letter-spacing: 0.12em;
}
.market-date-close {
  width: 28px;
  height: 28px;
  font-size: 22px;
  color: var(--ink-500);
}
.market-date-month {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.market-date-month strong {
  font-size: 14px;
}
.market-date-month button {
  width: 32px;
  height: 32px;
  border: 1px solid var(--line);
  color: var(--blue-700);
}
.market-date-calendar {
  width: 100%;
  table-layout: fixed;
  border-collapse: collapse;
  margin: 0 0 14px;
}
.market-date-calendar th {
  padding: 7px 0;
  font-size: 11px;
  font-weight: 400;
  color: var(--ink-500);
}
.market-date-calendar td {
  padding: 2px;
  text-align: center;
  height: 36px;
}
.market-date-calendar button {
  width: 100%;
  height: 32px;
  border: 1px solid transparent;
  font: 12px var(--font-mono);
}
.market-date-calendar button:hover {
  background: var(--surface-soft);
  border-color: var(--blue-500);
}
.market-date-calendar button[aria-pressed='true'] {
  color: var(--blue-700);
  background: var(--blue-50);
  border-color: var(--blue-500);
}
.market-date-calendar button:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
.market-date-fields {
  display: flex;
  gap: 8px;
}
.market-date-fields label {
  display: grid;
  gap: 5px;
  flex: 1;
  min-width: 0;
  font-size: 10px;
  color: var(--ink-500);
}
.market-date-fields label:first-child {
  flex: 1.6;
}
.market-date-fields input {
  width: 100%;
  box-sizing: border-box;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 2px;
  background: var(--surface-soft);
  color: var(--ink-900);
  padding: 8px 5px;
  text-align: center;
  font: 13px var(--font-mono);
}
.market-datetime-popup button:focus-visible,
.market-date-fields input:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: 2px;
}
.market-date-hint {
  font-size: 10px;
  color: var(--ink-500);
  margin: 10px 0 14px;
}
.market-date-error {
  color: var(--danger-ink);
  font-size: 12px;
  margin: 10px 0;
}
.market-datetime-popup footer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}
.market-datetime-popup footer > span {
  flex: 1;
}
.market-date-text {
  font-size: 11px;
  color: var(--blue-700);
}
.market-date-text:disabled {
  opacity: 0.35;
}
.market-date-cancel,
.market-date-apply {
  padding: 8px 12px;
  border: 1px solid var(--line);
  font-size: 12px;
}
.market-date-apply {
  color: var(--ink-on-blue);
  background: var(--blue-700);
  border-color: var(--blue-700);
}
@media (max-width: 760px) {
  .market-datetime-trigger,
  .market-date-fields input {
    font-size: 16px;
  }
  .market-datetime-trigger {
    min-height: 44px;
  }
  .market-date-calendar button {
    height: 36px;
  }
  .market-date-calendar td {
    height: 40px;
  }
  .market-datetime-popup {
    padding: 14px;
  }
}
</style>
