<template>
  <div id="app-shell">
    <header class="app-bar">
      <div class="brand">
        <span class="logo">🧬</span>
        <span class="app-title">AssetsLab</span>
        <span class="app-sub">数据驱动角色素材管线</span>
      </div>
      <nav class="app-nav">
        <router-link to="/species">
          <span class="nav-icon">🦴</span> 物种
        </router-link>
        <router-link to="/presets">
          <span class="nav-icon">🏷</span> 预设
        </router-link>
      </nav>
      <div class="nav-right">
        <span class="status-dot"></span>
        <span class="status-text">本地服务</span>
      </div>
    </header>
    <main><router-view /></main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif; background: #f0f2f5; color: #303133; }
.app-bar { display: flex; align-items: center; gap: 24px; padding: 0 24px; height: 56px; background: #fff; border-bottom: 1px solid #e4e7ed; box-shadow: 0 1px 3px rgba(0,0,0,.04); position: sticky; top: 0; z-index: 100; }
.brand { display: flex; align-items: baseline; gap: 8px; }
.logo { font-size: 1.3rem; }
.app-title { font-weight: 700; font-size: 1.15rem; letter-spacing: .2px; }
.app-sub { font-size: .75rem; color: #999; }
.app-nav { display: flex; gap: 4px; flex: 1; }
.app-nav a { display: flex; align-items: center; gap: 6px; padding: 7px 16px; border-radius: 8px; text-decoration: none; color: #666; font-size: .92rem; transition: all .15s; }
.app-nav a:hover { background: #f5f7fa; color: #409eff; }
.app-nav a.router-link-active { background: #ecf5ff; color: #409eff; font-weight: 600; }
.nav-icon { font-size: 1rem; }
.nav-right { display: flex; align-items: center; gap: 6px; font-size: .75rem; color: #999; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #67c23a; box-shadow: 0 0 0 3px rgba(103,194,58,.2); }
main { max-width: 1280px; margin: 0 auto; padding: 20px 24px 40px; }
</style>
