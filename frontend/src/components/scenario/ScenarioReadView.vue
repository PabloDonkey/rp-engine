<script setup lang="ts">
import { computed } from "vue";

import MetadataList from "@/components/scenario/MetadataList.vue";
import type { ScenarioDefinition } from "@/api/scenarioSchema";

/**
 * A scenario as a page, one card per part.
 *
 * The order is not a style choice. `ConversationBuilder` assembles the prompt as
 * description, then initial context, then world, then character, then rules, so the page
 * reads in the order the model reads it. Access and metadata sit at the bottom, because
 * they never reach the prompt. The story graph is last: it is inert data no scenario uses.
 */
const props = defineProps<{ scenario: ScenarioDefinition }>();

const characterEntries = computed(() => Object.entries(props.scenario.characters));
const beatEntries = computed(() => Object.entries(props.scenario.story_graph?.beats ?? {}));

const VISIBILITY_MEANING: Record<string, string> = {
  PUBLIC: "Listed in /scenarios and playable by anyone.",
  UNLISTED: "Hidden from /scenarios, but playable by anyone who knows the id.",
  RESTRICTED: "Listed and playable only in the group chats named below.",
};
</script>

<template>
  <div class="grid gap-6">
    <section>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Description
      </h2>
      <div class="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
        <p v-if="scenario.description" class="whitespace-pre-wrap">{{ scenario.description }}</p>
        <p v-else class="text-neutral-500">No description.</p>
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Opening scene
      </h2>
      <div class="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
        <p class="mb-2 text-xs text-neutral-500">
          <!-- v-pre: these are literal placeholders, not Vue interpolations. -->
          The first thing the player reads. <code v-pre>{{ user }}</code
          >, <code v-pre>{{ char }}</code> and <code v-pre>{{ world }}</code> are replaced when
          the prompt is built.
        </p>
        <p v-if="scenario.initial_context" class="whitespace-pre-wrap">
          {{ scenario.initial_context }}
        </p>
        <p v-else class="text-neutral-500">No opening scene.</p>
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">World</h2>
      <div class="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
        <p v-if="!scenario.world" class="text-neutral-500">
          No world. The prompt carries no world section.
        </p>
        <div v-else class="grid gap-3">
          <div>
            <div class="font-medium">{{ scenario.world.name }}</div>
            <div class="text-xs text-neutral-500">{{ scenario.world.id }}</div>
          </div>
          <p v-if="scenario.world.description" class="whitespace-pre-wrap">
            {{ scenario.world.description }}
          </p>
          <div>
            <div class="mb-1 text-xs uppercase tracking-wide text-neutral-500">World rules</div>
            <ol
              v-if="scenario.world.rules.length"
              class="list-decimal pl-5 marker:text-neutral-500"
            >
              <li v-for="(rule, index) in scenario.world.rules" :key="index">{{ rule }}</li>
            </ol>
            <p v-else class="text-neutral-500">None.</p>
          </div>
          <div>
            <div class="mb-1 text-xs uppercase tracking-wide text-neutral-500">World metadata</div>
            <MetadataList :metadata="scenario.world.metadata" />
          </div>
        </div>
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Characters
      </h2>
      <p v-if="characterEntries.length === 0" class="text-sm text-neutral-500">
        No characters. This is a freeform scenario.
      </p>
      <div v-else class="grid gap-2">
        <div
          v-for="[role, character] in characterEntries"
          :key="role"
          class="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10"
        >
          <div class="mb-2 flex flex-wrap items-baseline gap-2">
            <span
              class="rounded-full border border-black/10 px-2 py-0.5 text-xs dark:border-white/10"
              >{{ role }}</span
            >
            <span class="font-medium">{{ character.name }}</span>
            <span class="text-xs text-neutral-500">{{ character.id }}</span>
          </div>
          <div class="grid gap-2">
            <div v-if="character.description">
              <div class="text-xs uppercase tracking-wide text-neutral-500">Description</div>
              <p class="whitespace-pre-wrap">{{ character.description }}</p>
            </div>
            <div v-if="character.personality">
              <div class="text-xs uppercase tracking-wide text-neutral-500">Personality</div>
              <p class="whitespace-pre-wrap">{{ character.personality }}</p>
            </div>
            <div v-if="character.greeting">
              <div class="text-xs uppercase tracking-wide text-neutral-500">Greeting</div>
              <p class="whitespace-pre-wrap">{{ character.greeting }}</p>
            </div>
            <div>
              <div class="mb-1 text-xs uppercase tracking-wide text-neutral-500">Metadata</div>
              <MetadataList :metadata="character.metadata" />
            </div>
          </div>
        </div>
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">Rules</h2>
      <div class="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
        <p class="mb-2 text-xs text-neutral-500">The prompt lists these in this order.</p>
        <ol v-if="scenario.rules.length" class="list-decimal pl-5 marker:text-neutral-500">
          <li v-for="(rule, index) in scenario.rules" :key="index">{{ rule }}</li>
        </ol>
        <p v-else class="text-neutral-500">No rules.</p>
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">Access</h2>
      <div class="grid gap-2 rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
        <div>
          <span class="font-medium">{{ scenario.visibility }}</span>
          <span class="ml-2 text-xs text-neutral-500">
            {{ VISIBILITY_MEANING[scenario.visibility] }}
          </span>
        </div>
        <div v-if="scenario.visibility === 'RESTRICTED'">
          <div class="mb-1 text-xs uppercase tracking-wide text-neutral-500">
            Allowed group chat ids
          </div>
          <ul v-if="scenario.allowed_group_chat_ids.length" class="flex flex-wrap gap-1">
            <li
              v-for="chatId in scenario.allowed_group_chat_ids"
              :key="chatId"
              class="rounded-full border border-black/10 px-2 py-0.5 text-xs dark:border-white/10"
            >
              {{ chatId }}
            </li>
          </ul>
          <p v-else class="text-neutral-500">
            None, so nobody can play it. Add a chat id, or change the visibility.
          </p>
        </div>
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">Metadata</h2>
      <div class="rounded-lg border border-black/10 p-3 dark:border-white/10">
        <p class="mb-2 text-xs text-neutral-500">Never reaches the prompt. For your own notes.</p>
        <MetadataList :metadata="scenario.metadata" />
      </div>
    </section>

    <section>
      <h2 class="mb-2 text-sm font-semibold uppercase tracking-wide text-neutral-500">
        Story graph
      </h2>
      <div class="rounded-lg border border-black/10 p-3 text-sm dark:border-white/10">
        <p v-if="!scenario.story_graph" class="text-neutral-500">No story graph.</p>
        <div v-else class="grid gap-2">
          <p class="text-xs text-neutral-500">
            Inert data. Nothing in the engine walks these beats yet.
          </p>
          <div>
            <span class="text-xs uppercase tracking-wide text-neutral-500">Entry beat</span>
            <span class="ml-2">{{ scenario.story_graph.entry_beat_id ?? "none" }}</span>
          </div>
          <ul class="grid gap-1">
            <li v-for="[beatId, beat] in beatEntries" :key="beatId">
              <span class="font-medium">{{ beatId }}</span>
              <span class="ml-2 text-neutral-500">{{ beat.description }}</span>
            </li>
          </ul>
        </div>
      </div>
    </section>
  </div>
</template>
