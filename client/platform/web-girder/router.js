import Vue from 'vue';
import Router from 'vue-router';

import girderRest from './plugins/girder';
import Home from './views/Home.vue';
import Jobs from './views/Jobs.vue';
import Login from './views/Login.vue';
import RouterPage from './views/RouterPage.vue';
import Summary from './views/Summary.vue';
import ViewerLoader from './views/ViewerLoader.vue';
import DataShared from './views/DataShared.vue';
import DataBrowser from './views/DataBrowser.vue';

Vue.use(Router);

function beforeEnter(to, from, next) {
  if (!girderRest.user) {
    next('/login');
  } else {
    next();
  }
}

const router = new Router({
  routes: [
    {
      path: '/login',
      name: 'login',
      component: Login,
    },
    {
      path: '/viewer/:id',
      name: 'viewer',
      component: ViewerLoader,
      props: true,
      beforeEnter,
    },
    {
      path: '/',
      component: RouterPage,
      children: [
        {
          path: 'summary',
          name: 'summary',
          component: Summary,
          beforeEnter,
        },
        {
          path: 'jobs',
          name: 'jobs',
          component: Jobs,
          beforeEnter,
        },
        {
          path: '',
          component: Home,
          children: [
            {
              path: 'shared',
              name: 'shared',
              component: DataShared,
            },
            {
              path: ':_modelType?/:_id?',
              name: 'home',
              component: DataBrowser,
              beforeEnter,
            },
          ],
        },
      ],
    },
  ],
});

export default router;
