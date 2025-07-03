import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
      meta: { requiresAuth: true }
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue')
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue')
    },
    {
      path: '/leanmessage-test',
      name: 'leanmessage-test',
      component: () => import('../views/LeanMessageTest.vue'),
      meta: { requiresAuth: false }
    },
    {
      path: '/system-chat-test',
      name: 'system-chat-test',
      component: () => import('../views/SystemChatTest.vue'),
      meta: { requiresAuth: false }
    }
  ]
})

// Router guards
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  const isLoggedIn = !!authStore.token;

  if (to.meta.requiresAuth && !isLoggedIn) {
    next({ name: 'login' });
  } else if ((to.name === 'login' || to.name === 'register') && isLoggedIn) {
    next({ name: 'home' });
  } else {
    next();
  }
});

export default router 