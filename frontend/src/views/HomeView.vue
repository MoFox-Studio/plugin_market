<script setup lang="ts">
import { computed, watch } from 'vue';
import { useHomeStore } from '@/stores/home';
import { useAuthStore } from '@/stores/auth';
import { useTaxonomyStore } from '@/stores/taxonomy';
import { formatNumber, categoryLabel } from '@/utils/format';
import SpotlightFeature from '@/components/SpotlightFeature.vue';
import RecommendationSection from '@/components/RecommendationSection.vue';
import AsyncSection from '@/components/AsyncSection.vue';
import PageSkeleton from '@/components/PageSkeleton.vue';
import HomePlate from '@/components/HomePlate.vue';
import HomeFinder from '@/components/HomeFinder.vue';
import HomePluginShelf from '@/components/HomePluginShelf.vue';
import ColophonSeal from '@/components/ColophonSeal.vue';
import { drawImpression } from '@/composables/rareImpressions';
import CategoryIndex from '@/components/catalog/CategoryIndex.vue';
import MarketTopicGroups from '@/components/catalog/MarketTopicGroups.vue';
const home = useHomeStore(),
  auth = useAuthStore(),
  taxonomy = useTaxonomyStore();
const latest = computed(() => home.data?.latest?.slice(0, 5) || []);
const featured = computed(() => {
  const curated = home.showcase.filter((x) => x.plugin).map((x) => x.plugin!);
  return curated.length ? curated : home.featuredPlugins;
});
const stats = computed(() => home.data?.stats);
const rarePrint = drawImpression();
const samples = computed(() => [
  ...latest.value,
  ...featured.value,
  ...(home.data?.top_rated || []),
]);
const creators = computed(() => {
  const selected = home.showcase
    .filter((x) => x.author)
    .map((x) => ({
      id: x.author!.author_id,
      name: x.author!.display_name,
      avatar: x.author!.avatar_url,
      caption: x.signature_plugin?.display_name || '社区精选创作者',
      featured: true,
    }));
  const ids = new Set(selected.map((x) => x.id));
  return [
    ...selected,
    ...home.trendingAuthors
      .filter((x) => !ids.has(x.author_id))
      .map((x) => ({
        id: x.author_id,
        name: x.display_name,
        avatar: x.avatar_url,
        caption: x.plugins_count + ' 个作品',
        featured: false,
      })),
  ].slice(0, 4);
});
watch(
  () => auth.viewer?.author_id,
  () => void home.loadHome(),
  { immediate: true },
);
void taxonomy.load();
function date(value: string) {
  return new Date(value).toLocaleDateString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
  });
}
</script>
<template>
  <div class="discovery">
    <header class="gazette-masthead">
      <div class="masthead-line">
        <div class="mast-wing"><b>MOFOX STUDIO</b><small>社区出品</small></div>
        <div class="mast-title" lang="en"><i>The</i> MoFox Gazette</div>
        <div class="mast-wing">
          <b>PLUGIN MARKET</b>
          <small v-if="stats" class="hero-counts"
            >{{
              formatNumber(stats.published_plugins ?? stats.plugins_total ?? 0)
            }}
            款插件</small
          >
          <small v-else>插件与技能</small>
        </div>
      </div>
      <div class="mast-register">
        <span>发现版 <i>◆</i> FRONT PAGE</span>
        <nav aria-label="本版导读">
          <a href="#featured">01 值得一试</a><a href="#for-you">02 猜你喜欢</a>
        </nav>
        <a class="author-jump" href="#publish-guide">创作者指南 ↓</a>
      </div>
    </header>
    <section class="discovery-hero" aria-labelledby="discovery-title">
      <div class="discovery-copy">
        <div class="lead-kicker">
          <span>插件市场</span><i lang="en">Open Possibilities</i>
        </div>
        <h1 id="discovery-title">拓展边界，<br />让灵感运行<b>。</b></h1>
      </div>
      <HomeFinder class="hero-finder" :categories="taxonomy.categories" />
      <HomePlate />
    </section>
    <HomePluginShelf :candidates="samples" />
    <div class="discovery-body">
      <section id="featured" aria-label="值得一试">
        <AsyncSection
          :loading="home.loading && !home.data"
          :error="home.error"
          :empty="!featured.length"
          label="精选内容"
          @retry="home.refresh()"
        >
          <template #loading
            ><PageSkeleton type="detail" :count="1"
          /></template>
          <template #empty
            ><router-link class="text-link" to="/browse"
              >浏览全部插件 ↗</router-link
            ></template
          >
          <SpotlightFeature :items="featured" />
        </AsyncSection>
      </section>
      <RecommendationSection id="for-you" />
      <p v-if="taxonomy.error" class="catalog-caption" role="status">
        {{ taxonomy.error }}
        <button class="text-link" @click="taxonomy.load(true)">重试分类</button>
      </p>
      <CategoryIndex
        v-if="taxonomy.categories.length"
        :categories="taxonomy.categories"
        discovery
      />
      <MarketTopicGroups :tags="taxonomy.tags" discovery />
      <section class="news-section" aria-labelledby="latest-title">
        <header class="section-title">
          <div>
            <span class="eyebrow">03 / LATEST RELEASES</span>
            <h2 id="latest-title">持续生长 <small>最近更新</small></h2>
          </div>
          <router-link class="text-link" to="/browse?sort=updated"
            >全部更新 ↗</router-link
          >
        </header>
        <AsyncSection
          :loading="home.loading && !home.data"
          :error="home.error"
          :empty="!latest.length"
          label="更新记录"
          @retry="home.refresh()"
        >
          <template #loading><PageSkeleton type="rows" :count="4" /></template>
          <div
            class="release-list"
            :class="{ 'release-edition': latest.length > 2 }"
            :style="{ '--news-rows': latest.length - 1 }"
          >
            <router-link
              v-for="(plugin, i) in latest"
              :key="plugin.plugin_id"
              :to="'/plugin/' + encodeURIComponent(plugin.plugin_id)"
              class="release-row"
            >
              <span class="release-number">{{
                String(i + 1).padStart(2, '0')
              }}</span>
              <div>
                <small>{{
                  categoryLabel(plugin.categories?.[0] || 'other')
                }}</small>
                <h3>{{ plugin.display_name }}</h3>
                <p>{{ plugin.summary }}</p>
              </div>
              <span class="release-meta"
                >{{ plugin.latest_version ? 'v' + plugin.latest_version : '' }}
                <time :datetime="plugin.updated_at">{{
                  date(plugin.updated_at)
                }}</time></span
              >
            </router-link>
          </div>
        </AsyncSection>
      </section>
      <section class="creators-section" aria-labelledby="people-title">
        <header class="section-title">
          <div>
            <span class="eyebrow">04 / THE PEOPLE BEHIND</span>
            <h2 id="people-title">由热爱驱动 <small>社区创作者</small></h2>
          </div>
          <small v-if="stats" class="edition-tally"
            >{{ formatNumber(stats.authors_total ?? 0) }} 位创作者 ·
            {{ formatNumber(stats.versions_total ?? 0) }} 个版本</small
          >
        </header>
        <div v-if="creators.length" class="creator-grid">
          <router-link
            v-for="(author, i) in creators"
            :key="author.id"
            :to="'/author/' + encodeURIComponent(author.id)"
            class="creator-card"
          >
            <small
              >{{ author.featured ? 'FEATURED AUTHOR' : 'CONTRIBUTOR' }} / 0{{
                i + 1
              }}</small
            >
            <img
              v-if="author.avatar"
              :src="author.avatar"
              alt=""
              loading="lazy"
            /><span v-else class="person-initial">{{
              author.name.slice(0, 1)
            }}</span>
            <strong>{{ author.name }}</strong
            ><span>{{ author.caption }}</span>
          </router-link>
        </div>
        <p v-else-if="!home.loading" class="catalog-caption">暂无作者资料。</p>
      </section>
      <aside
        id="publish-guide"
        class="publish-guide"
        :class="{ 'has-impression': rarePrint }"
        aria-labelledby="publish-title"
      >
        <div>
          <span class="eyebrow">CREATORS' DESK</span>
          <h2 id="publish-title">把你的插件带到这里。</h2>
          <p>
            在插件项目中使用
            <code>mpdt market publish</code>
            发布，再到创作者工作台管理作品和版本。
          </p>
          <nav aria-label="创作者入口">
            <a
              href="https://docs.mofox.chat/docs/development/plugin_develop/contributing-to-market.html"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="提交插件：打开插件市场投稿文档"
              >提交插件 · 查看文档 ↗</a
            ><a
              href="https://github.com/MoFox-Studio"
              target="_blank"
              rel="noopener noreferrer"
              >开源社区 ↗</a
            >
          </nav>
        </div>
        <ColophonSeal v-if="rarePrint" :print="rarePrint" />
      </aside>
    </div>
  </div>
</template>
<style scoped>
.discovery {
  width: min(100%, 1600px);
  margin-inline: auto;
  padding: 0 clamp(20px, 4vw, 56px) 54px;
}
.masthead-line {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 16px;
  padding: clamp(12px, 0.7vw, 15px) 0;
  border-bottom: 4px double var(--ink-700);
}
.mast-title {
  text-align: center;
  color: var(--ink-900);
  font: 800 clamp(46px, 6vw, 100px) / 1.05 var(--font-editorial);
  letter-spacing: -0.056em;
  white-space: nowrap;
}
.mast-title i {
  font: 400 0.65em/1 var(--font-script);
  color: var(--blue-700);
  letter-spacing: normal;
}
.mast-wing {
  width: max-content;
  text-align: center;
  border-block: 1px solid var(--line-strong);
  padding: 6px 0;
  color: var(--ink-700);
}
.mast-wing:last-child {
  justify-self: end;
}
.mast-wing b,
.mast-wing small {
  display: block;
  font-size: 11px;
  letter-spacing: 0.1em;
}
.mast-wing b {
  font-family: var(--font-reading);
  font-weight: 800;
}
.mast-wing small {
  margin-top: 4px;
  color: var(--ink-500);
}
.mast-register {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 12px;
  min-height: 37px;
  border-bottom: 1px solid var(--ink-500);
  color: var(--ink-700);
}
.mast-register {
  font: 11px/1.4 var(--font-mono);
  letter-spacing: 0.04em;
}
.mast-register i {
  margin-inline: 4px;
  font-style: normal;
  color: var(--blue-700);
}
.mast-register nav {
  display: flex;
  align-items: center;
  gap: 18px;
  color: var(--blue-700);
  font-weight: 650;
}
.mast-register a {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
}
.mast-register a:hover {
  text-decoration: underline;
  text-underline-offset: 4px;
}
.mast-register > a {
  justify-self: end;
}
.discovery-hero {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
  grid-template-areas: 'copy art' 'finder art';
  align-items: center;
  column-gap: clamp(16px, 3vw, 54px);
  padding-top: clamp(23px, 2.1vw, 40px);
}
.discovery-copy {
  grid-area: copy;
  align-self: end;
}
.lead-kicker {
  display: flex;
  gap: 12px;
  align-items: center;
  color: var(--blue-700);
}
.lead-kicker span {
  color: var(--blue-700);
  font: 700 12px/1.3 var(--font-sans);
  letter-spacing: 0.15em;
}
.lead-kicker i {
  padding-left: 12px;
  border-left: 1px solid var(--line-strong);
  font: 400 clamp(20px, 1.6vw, 25px) / 1 var(--font-script);
}
.discovery-copy h1 {
  margin: clamp(18px, 1.35vw, 26px) 0 14px;
  color: var(--ink-900);
  font: 800 clamp(43px, 4.25vw, 74px) / 1.13 var(--font-editorial);
  letter-spacing: -0.055em;
}
.discovery-copy h1 b {
  color: var(--blue-700);
}

.hero-finder {
  grid-area: finder;
  width: 100%;
  margin-top: 4px;
  align-self: start;
}
.discovery-hero :deep(.home-plate) {
  grid-area: art;
}
.edition-tally {
  color: var(--ink-500);
  font: 12px/1.5 var(--font-sans);
}
.discovery-body {
  padding-top: clamp(28px, 2.4vw, 46px);
}
.discovery-body > section,
#publish-guide {
  scroll-margin-top: 78px;
}
#for-you,
.news-section,
.creators-section {
  margin-top: clamp(36px, 4.6vw, 74px);
}
.section-title {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 12px;
  margin-bottom: 20px;
  padding-top: 16px;
  border-top: 3px double var(--ink-500);
}
.section-title h2,
.publish-guide h2 {
  margin: 10px 0 0;
  font: 800 clamp(26px, 3.3vw, 52px) / 1.18 var(--font-editorial);
}
.section-title h2 small {
  display: inline-block;
  margin-left: 10px;
  color: var(--ink-500);
  font: 13px/1.6 var(--font-sans);
}
.text-link {
  color: var(--blue-700);
  font-weight: 600;
  font-size: 13px;
}
.release-row {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: baseline;
  gap: 14px;
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
}
.release-number,
.release-meta,
.creator-card small {
  font: 11px/1.6 var(--font-mono);
  color: var(--ink-500);
}
.release-row small {
  color: var(--blue-700);
}
.release-row h3 {
  margin: 2px 0;
  font: 700 17px/1.4 var(--font-reading);
}
.release-row p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--ink-700);
}
.release-meta time {
  display: block;
}
.release-edition {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  column-gap: clamp(18px, 3.2vw, 54px);
}
.release-edition .release-row:first-child {
  grid-row: span var(--news-rows);
  align-content: start;
  padding: 18px 22px;
  background: var(--surface-soft);
  border-top: 2px solid var(--ink-700);
}
.release-edition .release-row:first-child h3 {
  margin: 16px 0;
  font: 800 clamp(24px, 2.5vw, 40px) / 1.25 var(--font-editorial);
}
.creator-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}
.creator-card {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  padding: 18px;
  border: 1px solid var(--line);
  background: var(--surface);
}
.creator-card img,
.person-initial {
  width: 42px;
  height: 42px;
  object-fit: cover;
  border-radius: 50%;
}
.person-initial {
  display: grid;
  place-items: center;
  background: var(--surface-soft);
}
.creator-card strong {
  font: 700 18px/1.35 var(--font-reading);
}
.creator-card > span:last-child {
  color: var(--ink-500);
  font-size: 12px;
}
.publish-guide {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-items: center;
  gap: 22px;
  margin-top: 48px;
  border-block: 3px double var(--ink-500);
  padding: 24px 0;
}
.publish-guide h2 {
  font-size: clamp(24px, 2.4vw, 36px);
}
@media (min-width: 701px) {
  .publish-guide.has-impression { grid-template-columns: minmax(0, 1fr) minmax(180px, 240px); }
}
.publish-guide p {
  margin: 9px 0 0;
  color: var(--ink-700);
  line-height: 1.8;
}
.publish-guide nav {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 22px;
  margin-top: 16px;
  color: var(--blue-700);
  font-weight: 600;
}
@media (max-width: 700px) {
  .discovery {
    padding: 0 18px 34px;
  }
  .masthead-line {
    display: block;
    padding: 17px 0 10px;
  }
  .mast-wing {
    display: none;
  }
  .mast-title {
    font-size: clamp(31px, 9.3vw, 55px);
  }
  .mast-register {
    grid-template-columns: 1fr auto;
    gap: 6px;
    font-size: 10px;
  }
  .mast-register > span {
    display: none;
  }
  .mast-register nav {
    grid-column: 2;
    grid-row: 1;
    gap: 10px;
  }
  .mast-register > a {
    grid-column: 1;
    grid-row: 1;
    justify-self: start;
  }
  .discovery-hero {
    grid-template-columns: minmax(0, 1fr) clamp(65px, 23vw, 110px);
    column-gap: 8px;
    padding-top: 20px;
  }
  .discovery-copy {
    display: contents;
  }
  .lead-kicker {
    grid-column: 1/-1;
    grid-row: 1;
  }
  .discovery-copy h1 {
    grid-column: 1;
    grid-row: 2;
    align-self: center;
    margin: 10px 0;
    font-size: clamp(32px, 8.5vw, 51px);
  }
  .discovery-hero :deep(.home-plate) {
    grid-column: 2;
    grid-row: 2;
  }
  .hero-finder {
    grid-column: 1/-1;
    grid-row: 3;
    margin-top: 8px;
  }
  .edition-tally {
    font-size: 10px;
  }
  .release-edition {
    grid-template-columns: 1fr;
  }
  .release-edition .release-row:first-child {
    grid-row: auto;
  }
  .creator-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
  }
  .creator-card {
    padding: 12px;
  }
  .publish-guide {
    grid-template-columns: 1fr;
  }
  .publish-guide nav {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
  }
}
</style>
