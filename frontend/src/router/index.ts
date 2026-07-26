import { createRouter, createWebHistory } from "vue-router";

import UsersPage from "@/pages/UsersPage.vue";
import UserSessionsPage from "@/pages/UserSessionsPage.vue";
import SessionDetailPage from "@/pages/SessionDetailPage.vue";
import ScenariosPage from "@/pages/ScenariosPage.vue";
import ScenarioDetailPage from "@/pages/ScenarioDetailPage.vue";
import ScenarioEditPage from "@/pages/ScenarioEditPage.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", redirect: "/users" },
    { path: "/users", name: "users", component: UsersPage },
    {
      path: "/users/:userId/sessions",
      name: "user-sessions",
      component: UserSessionsPage,
      props: true,
    },
    {
      path: "/sessions/:sessionId",
      name: "session-detail",
      component: SessionDetailPage,
      props: true,
    },
    { path: "/scenarios", name: "scenarios", component: ScenariosPage },
    { path: "/scenarios/new", name: "scenario-create", component: ScenarioEditPage },
    {
      path: "/scenarios/:scenarioId",
      name: "scenario-detail",
      component: ScenarioDetailPage,
      props: true,
    },
    {
      path: "/scenarios/:scenarioId/edit",
      name: "scenario-edit",
      component: ScenarioEditPage,
      props: true,
    },
    { path: "/:pathMatch(.*)*", redirect: "/users" },
  ],
});

export default router;
