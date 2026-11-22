<script setup lang="ts">
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  onUpdated,
  ref,
  useAttrs,
  useId,
  useSlots,
  watch,
  type VNode,
} from 'vue';

defineOptions({ inheritAttrs: false });
const props = defineProps<{
  modelValue?: string | number | null;
  value?: string | number | null;
  disabled?: boolean;
  required?: boolean;
  name?: string;
  id?: string;
  placeholder?: string;
}>();
const emit = defineEmits<{
  'update:modelValue': [value: string | number];
  change: [event: Event];
}>();
const attrs = useAttrs(),
  slots = useSlots(),
  uid = useId();
const root = ref<HTMLElement>(),
  trigger = ref<HTMLButtonElement>(),
  native = ref<HTMLSelectElement>();
const popup = ref<HTMLElement>(),
  open = ref(false),
  activeValue = ref<string | number>(),
  invalid = ref(false);
const portal = ref<HTMLElement | string>('body'),
  popupStyle = ref<Record<string, string>>({});
const listId = `market-options-${uid}`;
const fieldLabel = ref('');
type Option = {
  value: string | number;
  label: string;
  disabled: boolean;
  group: string;
};
function textOf(node: unknown): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(textOf).join('');
  if (node && typeof node === 'object' && 'children' in node)
    return textOf((node as VNode).children);
  return '';
}
function readOptions(nodes: VNode[], group = '', disabled = false): Option[] {
  return nodes.flatMap((node) => {
    if (node.type === 'option') {
      const label = String(node.props?.label ?? textOf(node.children)).trim();
      return [
        {
          label,
          value: node.props?.value ?? label,
          disabled:
            disabled ||
            node.props?.disabled === '' ||
            Boolean(node.props?.disabled),
          group,
        },
      ];
    }
    const nextGroup =
      node.type === 'optgroup' ? String(node.props?.label ?? '') : group;
    return Array.isArray(node.children)
      ? readOptions(
          node.children as VNode[],
          nextGroup,
          disabled ||
            node.props?.disabled === '' ||
            Boolean(node.props?.disabled),
        )
      : [];
  });
}
const options = computed(() => readOptions(slots.default?.() || []));
const selectedValue = computed(() =>
  props.modelValue !== undefined ? props.modelValue : props.value,
);
const selected = computed(() =>
  options.value.findIndex(
    (option) => String(option.value) === String(selectedValue.value),
  ),
);
const active = computed({
  get() {
    const index = options.value.findIndex(
      (option) => option.value === activeValue.value && !option.disabled,
    );
    if (index >= 0) return index;
    if (selected.value >= 0 && !options.value[selected.value]?.disabled)
      return selected.value;
    return options.value.findIndex((option) => !option.disabled);
  },
  set(index: number) {
    activeValue.value = options.value[index]?.value;
  },
});
const label = computed(
  () => options.value[selected.value]?.label || props.placeholder || '请选择',
);
const buttonAttrs = computed(() =>
  Object.fromEntries(
    Object.entries(attrs).filter(([key]) => !['class', 'style'].includes(key)),
  ),
);
let search = '',
  searchTimer: ReturnType<typeof setTimeout> | undefined;
let observer: ResizeObserver | undefined;

function position() {
  if (!open.value || !trigger.value) return;
  const rect = trigger.value.getBoundingClientRect();
  const viewport = window.visualViewport;
  const width = viewport?.width || window.innerWidth;
  const height = viewport?.height || window.innerHeight;
  const leftEdge = viewport?.offsetLeft || 0,
    topEdge = viewport?.offsetTop || 0;
  const menuWidth = Math.min(Math.max(rect.width, 232), width - 24);
  const below = topEdge + height - rect.bottom - 12,
    above = rect.top - topEdge - 12;
  const flip = below < 180 && above > below;
  const maxHeight = Math.min(320, Math.max(96, (flip ? above : below) - 6));
  popupStyle.value = {
    left: `${Math.min(Math.max(leftEdge + 12, rect.left), leftEdge + width - menuWidth - 12)}px`,
    width: `${menuWidth}px`,
    maxHeight: `${maxHeight}px`,
    top: flip ? 'auto' : `${rect.bottom + 6}px`,
    bottom: flip ? `${window.innerHeight - rect.top + 6}px` : 'auto',
  };
}
function ensureActiveVisible() {
  nextTick(() =>
    popup.value
      ?.querySelector<HTMLElement>(`[data-index="${active.value}"]`)
      ?.scrollIntoView?.({ block: 'nearest' }),
  );
}
function show() {
  if (props.disabled || !options.value.length) return;
  portal.value =
    trigger.value?.closest<HTMLDialogElement>('dialog[open]') || document.body;
  active.value =
    selected.value >= 0 && !options.value[selected.value]?.disabled
      ? selected.value
      : options.value.findIndex((option) => !option.disabled);
  open.value = true;
  nextTick(() => {
    position();
    ensureActiveVisible();
  });
}
function close() {
  open.value = false;
  search = '';
  clearTimeout(searchTimer);
}
function move(direction: number) {
  if (!open.value) {
    show();
    return;
  }
  const count = options.value.length;
  for (let i = 1; i <= count; i++) {
    const next = (active.value + direction * i + count) % count;
    if (!options.value[next]?.disabled) {
      active.value = next;
      ensureActiveVisible();
      return;
    }
  }
}
function onChange(event: Event) {
  const value = (event.target as HTMLSelectElement).value;
  invalid.value = Boolean(props.required && !value);
  emit(
    'update:modelValue',
    options.value.find((option) => String(option.value) === value)?.value ??
      value,
  );
  emit('change', event);
}
function onInvalid() {
  invalid.value = true;
  trigger.value?.focus({ preventScroll: true });
  show();
}
function choose(index: number) {
  const option = options.value[index];
  if (!option || option.disabled || props.disabled) return;
  if (native.value && index !== selected.value) {
    native.value.value = String(option.value);
    native.value.dispatchEvent(new Event('change', { bubbles: true }));
  }
  close();
  trigger.value?.focus({ preventScroll: true });
}
function keydown(event: KeyboardEvent) {
  if (props.disabled) return;
  if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    event.preventDefault();
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp')
      move(event.key === 'ArrowDown' ? 1 : -1);
    else {
      if (!open.value) show();
      const indices = options.value
        .map((_, i) => i)
        .filter((i) => !options.value[i].disabled);
      active.value =
        (event.key === 'Home' ? indices[0] : indices[indices.length - 1]) ?? -1;
      ensureActiveVisible();
    }
  } else if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault();
    if (open.value) choose(active.value);
    else show();
  } else if (event.key === 'Escape' && open.value) {
    event.preventDefault();
    event.stopPropagation();
    close();
  } else if (event.key === 'Tab') close();
  else if (
    event.key.length === 1 &&
    !event.ctrlKey &&
    !event.metaKey &&
    !event.altKey
  ) {
    if (!open.value) show();
    search += event.key.toLocaleLowerCase();
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => {
      search = '';
    }, 700);
    const index = options.value.findIndex(
      (option) =>
        !option.disabled && option.label.toLocaleLowerCase().startsWith(search),
    );
    if (index >= 0) {
      active.value = index;
      ensureActiveVisible();
    }
  }
}
function outside(event: Event) {
  const target = event.target as Node | null;
  if (!root.value?.contains(target) && !popup.value?.contains(target)) close();
}
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
function scroll(event: Event) {
  if (!popup.value?.contains(event.target as Node)) position();
}
watch(
  () => props.disabled,
  (disabled) => {
    if (disabled) close();
  },
);
watch(selectedValue, (value) => {
  if (open.value) active.value = selected.value;
  if (value !== '' && value !== undefined && value !== null)
    invalid.value = false;
});
onMounted(() => {
  syncLabel();
  document.addEventListener('pointerdown', outside);
  document.addEventListener('focusin', outside);
  window.addEventListener('resize', position);
  window.addEventListener('scroll', scroll, true);
  window.visualViewport?.addEventListener('resize', position);
  if (typeof ResizeObserver !== 'undefined' && trigger.value) {
    observer = new ResizeObserver(position);
    observer.observe(trigger.value);
  }
});
onUpdated(syncLabel);
onBeforeUnmount(() => {
  close();
  observer?.disconnect();
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
    class="market-select"
    :class="[attrs.class, { 'is-open': open, 'is-disabled': disabled }]"
    :style="attrs.style as any"
  >
    <select
      ref="native"
      class="market-select-native"
      :name="name"
      :value="selectedValue"
      tabindex="-1"
      hidden
      aria-hidden="true"
      :disabled="disabled"
      :required="required"
      @change="onChange"
      @invalid.prevent="onInvalid"
    >
      <slot />
    </select>
    <button
      :id="id"
      ref="trigger"
      v-bind="buttonAttrs"
      class="market-select-trigger"
      type="button"
      role="combobox"
      :aria-label="String(attrs['aria-label'] || fieldLabel || label)"
      aria-haspopup="listbox"
      :aria-expanded="open"
      :aria-controls="listId"
      :aria-activedescendant="
        open && active >= 0 ? `${listId}-${active}` : undefined
      "
      :aria-required="required || undefined"
      :aria-invalid="invalid || (attrs['aria-invalid'] ? 'true' : undefined)"
      :aria-describedby="
        [attrs['aria-describedby'], invalid ? `${listId}-error` : '']
          .filter(Boolean)
          .join(' ') || undefined
      "
      :disabled="disabled"
      @click="open ? close() : show()"
      @keydown="keydown"
    >
      <span class="market-select-value">{{ label }}</span
      ><span class="market-select-chevron" aria-hidden="true">⌄</span>
    </button>
    <span
      v-if="invalid"
      :id="`${listId}-error`"
      class="market-select-error"
      role="alert"
      >请选择一个有效选项。</span
    >
    <Teleport :to="portal">
      <Transition name="market-popup">
        <div
          v-if="open"
          :id="listId"
          ref="popup"
          role="listbox"
          class="market-select-popup"
          :style="popupStyle"
          :aria-label="String(attrs['aria-label'] || '选择选项')"
          @pointerdown.prevent
        >
          <div class="market-select-caption" aria-hidden="true">
            <span>MOFOX / SELECT</span
            ><span>{{ options.length.toString().padStart(2, '0') }}</span>
          </div>
          <template
            v-for="(option, index) in options"
            :key="`${option.value}-${index}`"
          >
            <div
              v-if="option.group && option.group !== options[index - 1]?.group"
              class="market-select-group"
            >
              {{ option.group }}
            </div>
            <div
              :id="`${listId}-${index}`"
              role="option"
              :data-index="index"
              :aria-selected="index === selected"
              :aria-disabled="option.disabled || undefined"
              class="market-select-option"
              :class="{
                'is-active': index === active,
                'is-selected': index === selected,
                'is-disabled': option.disabled,
              }"
              @pointermove="!option.disabled && (active = index)"
              @click.stop="choose(index)"
            >
              <span class="market-select-index" aria-hidden="true">{{
                String(index + 1).padStart(2, '0')
              }}</span
              ><span>{{ option.label }}</span
              ><span class="market-select-check" aria-hidden="true">{{
                index === selected ? '✓' : ''
              }}</span>
            </div>
          </template>
        </div>
      </Transition>
    </Teleport>
  </span>
</template>

<style>
.market-select {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  vertical-align: middle;
  min-width: 140px;
  max-width: 100%;
  border: 0;
  padding: 0;
  background: none;
}
.market-select-native {
  position: absolute !important;
  width: 1px !important;
  height: 1px !important;
  min-width: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  opacity: 0;
  pointer-events: none;
  overflow: hidden;
  clip-path: inset(50%);
}
.market-select-trigger {
  display: flex;
  align-items: center;
  gap: 20px;
  justify-content: space-between;
  width: 100%;
  min-height: 40px;
  padding: 10px 12px;
  color: var(--ink-900);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 2px;
  font: 13px/1.4 var(--font-sans);
  text-align: left;
  cursor: pointer;
  transition:
    border-color 140ms,
    background 140ms;
}
.market-select-trigger:hover,
.market-select.is-open .market-select-trigger {
  border-color: var(--blue-500);
  background: var(--surface-soft);
}
.market-select-trigger:focus-visible {
  outline: 2px solid var(--blue-500);
  outline-offset: 3px;
}
.market-select.is-disabled {
  opacity: 0.5;
}
.market-select.is-disabled .market-select-trigger {
  cursor: not-allowed;
}
.market-select-trigger[aria-invalid='true'] {
  border-color: var(--danger-ink);
}
.market-select-error {
  margin-top: 5px;
  font: 12px/1.4 var(--font-sans);
  color: var(--danger-ink);
}
.market-select-value {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.market-select-chevron {
  color: var(--blue-600);
  font: 18px/1 var(--font-mono);
  transition: transform 180ms;
}
.market-select.is-open .market-select-chevron {
  transform: rotate(180deg);
}
.market-select-popup {
  position: fixed;
  z-index: 1600;
  overflow: auto;
  overscroll-behavior: contain;
  padding: 6px;
  border: 1px solid var(--blue-300);
  border-top: 2px solid var(--blue-500);
  background: var(--surface);
  color: var(--ink-900);
  box-shadow: 0 14px 40px color-mix(in srgb, var(--ink-900) 14%, transparent);
  border-radius: 2px;
  scrollbar-width: thin;
  scrollbar-color: var(--blue-300) transparent;
}
.market-select-caption {
  display: flex;
  justify-content: space-between;
  padding: 7px 8px 10px;
  font: 9px/1.4 var(--font-mono);
  letter-spacing: 0.12em;
  color: var(--ink-500);
  border-bottom: 1px solid var(--line-soft);
  margin-bottom: 4px;
}
.market-select-option {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr) 16px;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 8px;
  border-left: 2px solid transparent;
  font: 13px/1.5 var(--font-sans);
  cursor: pointer;
  overflow-wrap: anywhere;
}
.market-select-option.is-active {
  background: var(--surface-soft);
  border-left-color: var(--blue-500);
}
.market-select-option.is-selected {
  color: var(--blue-700);
  font-weight: 600;
}
.market-select-option.is-disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.market-select-index {
  color: var(--ink-500);
  font: 9px var(--font-mono);
}
.market-select-check {
  color: var(--blue-600);
}
.market-select-group {
  padding: 12px 8px 4px;
  font: 10px var(--font-mono);
  color: var(--ink-500);
}
.market-popup-enter-active,
.market-popup-leave-active {
  transition:
    opacity 140ms ease,
    transform 140ms ease;
}
.market-popup-enter-from,
.market-popup-leave-to {
  opacity: 0;
  transform: translateY(-5px);
}
@media (max-width: 760px) {
  .market-select-trigger {
    min-height: 44px;
    font-size: 16px;
  }
  .market-select-option {
    min-height: 44px;
    font-size: 15px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .market-popup-enter-active,
  .market-popup-leave-active,
  .market-select-chevron,
  .market-select-trigger {
    transition: none;
  }
}
</style>
