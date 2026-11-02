# 行测刷题项目 · 当前状态备忘

> 最后更新：2026-11-02
> 用途：会话上下文压缩后，读此文件即可恢复工作状态

## 一、运行环境

| 项 | 值 |
|----|----|
| 项目目录 | `C:\Users\严睿霖\Documents\deepseek-harness\default-workspace\quiz-app` |
| Python | `C:\Users\严睿霖\AppData\Local\Programs\Python\Python39\python.exe` |
| 服务端口 | 8000（`python server.py --host 0.0.0.0 --port 8000`） |
| 局域网 | `http://192.168.1.21:8000` |
| 公网隧道 | 见 `tunnel-url.txt`（每次重启会变） |
| 一键启动 | `启动服务.cmd` / `停止服务.cmd` |

## 二、代码仓库

| 项 | 值 |
|----|----|
| GitHub | `git@github.com:guo0914/zhenti-app.git`（公开，默认分支 main） |
| Gitee | `git@gitee.com:a812183279/quiz-app.git` |
| 提交数 | 16+（2026-11-01 重建过历史，清除了泄漏的 API Key） |
| 最新构建 | #11 success，提交 `35728aa`，产物 `App-unsigned-ipa` 64.4 MB |

## 三、数据结构（重要）

**两套数据源，不要混淆：**

| 用途 | 文件 | 题量 | 说明 |
|------|------|------|------|
| 分类刷题 | `site/data/zt/<cat>.json` | 4520 | **实际数据源**，按需加载 |
| 分类刷题索引 | `site/data/zhenti.js` | — | 仅 1.1 KB，只有 meta + categories |
| 真题套卷索引 | `site/data/zt-papers.json` | 51 套 | 含 modules / coverage / grade |

- `zhenti.json`（7 MB）**已删除**，从未被引用（死数据）
- `zt-papers.js` 是 `zt-papers.json` 的 JS 包装（`window.__ZT_PAPERS__`）

**分片 cat 键名：** politics / common / verbal / quantity / judge / graph / data / guokao

## 四、关键业务规则

### 套卷顺序
标准顺序：政治 → 常识 → 言语 → 数量 → 判断 → 图形 → 资料
（`fix_all_paper_order.py` 已修复 40 套，42 套全部合规）

### 计时
`examSeconds(poolLen, isWholePaper, kind, region)`：
- 整卷 + `region === '国考'` → 固定 120 分钟
- 整卷 + 省考 → `max(100, 题量×0.9)` 分钟
- 分模块 → `题量×0.9` 分钟

⚠️ 判断整卷必须用 `moduleCat === 'all'`，**不能写 `!moduleCat`**
（`!'all'` 是 false，会导致 135 题算成 2:01:30）

### 材料显示规则
- 资料分析类（增长/比重/平均数/倍数/综合）→ 必保留
- 图形推理 / 类比推理 / 定义判断 → 一律删除
- 其他：题干 ≥ 100 字 → 删除（题干自带文段）
- 题干含「填入文中」→ 保留（横线在材料里）

### 选项图片
- 字段 `optionImgs`，与 `options` 等长数组
- 公式图（路径含「公式图」）按原始尺寸显示，**不能拉伸**
- flex 容器必须加 `align-items:flex-start`，否则公式图被 stretch 糊掉

## 五、AI 批改（申论）

**BYOK 模式**：每个用户自己填 DeepSeek API Key

| 项 | 说明 |
|----|------|
| 前端 | `site/assets/shenlun.js`，Key 存 localStorage `zlfx.shenlun.apikey` |
| 请求头 | `X-User-Api-Key` |
| 后端代理 | `server.py` 的 `/api/ai/chat`，优先用用户 Key |
| 服务器 Key | `ai_key.txt`（已 gitignore，可选，作为兜底） |
| 状态查询 | `/api/ai/status` → `{serverKey, needUserKey}` |

⚠️ **绝不能硬编码 Key 到前端代码**（曾泄漏 `sk-8ed3...` 导致账户被盗用）

## 六、自检工具

```bash
python scripts/audit_all.py          # 7 维数据审计
node scripts/regression-test.js      # 34 项回归测试
python scripts/bump_version.py --ver=vX.Y   # 更新资源版本号
```

**改动前端后必须做：**
1. `bump_version.py --ver=vX.Y`（更新 `?v=` 哈希 + 同步三处版本号）
2. `cd mobile && node scripts/prepare-www.js && npx cap sync ios`
3. 推送到 GitHub → 自动触发 iOS 构建

⚠️ `bump_version.py` 正则要匹配任意查询串（曾因只匹配 `?v=` 导致 `?build=v5` 永不更新）

⚠️ **版本号必须三处同步**（否则自愈机制失效，表现为「改了看不到」）：
| 位置 | 变量 |
|------|------|
| `site/index.html` | `data-app-ver="vX.Y"` |
| `site/index.html` | `var VER = 'vX.Y'` |
| `site/assets/selfheal.js` | `var MY_VERSION = 'vX.Y'` |

曾因前两处写死 `v5.0`、`VER` 却是 `v8.0`，`selfheal.js` 判据恒等 → 「页面版本落后」分支永不触发 → 自愈完全失效。`bump_version.py` 现已自动同步这三处，以及 `sw.js` 的 `CACHE` 名。

## 七、iOS App

| 项 | 说明 |
|----|------|
| 框架 | Capacitor 6，`mobile/` |
| 打包 | GitHub Actions `Build iOS IPA`（macos-14） |
| 触发 | push 到 `site/**` 或 `mobile/**`，或手动 workflow_dispatch |
| 安装 | Sideloadly（Windows 签名），免费账号 7 天有效 |
| 免费额度 | macOS 200 分钟/月，每次构建约 2 分钟但按 10x 计费 |

⚠️ App 是打包快照：
- `site/data/*.json` 数据 → App 会加载新的
- `site/assets/*.js` 代码 → **必须重新构建**

## 八、已知数据缺陷（无法修复）

| 类型 | 数量 | 原因 |
|------|------|------|
| 源数据缺失题 | 7 道 | 源仓库标注「缺失题目正在征集」，已打 `flags:['dataMissing']` |
| 不完整卷 | 6 套 | 网友回忆版缺题，`coverage < 1`，界面已标注「⚠ 仅收录 X%」 |
| 选项全空 | 114 题 | 纯图片选项，四选项均有 `optionImgs`，可正常作答 |

## 九、验证过的功能

- 13 个路由全部正常渲染
- 分类刷题：7 分类、答题、材料折叠、横线（359/449）
- 真题套卷：51 套、7 模块、计时 120 分钟
- 法律专业：2383 题、8 科目
- 题库速查：搜索「悬泉置」命中 4 题
- 申论批改：设置页、Key 测试、用量统计

## 十、待办

- [ ] 用户需在 DeepSeek 后台作废旧 Key `sk-8ed3...` 并充值
- [ ] 下载构建 #11 的 IPA 并用 Sideloadly 安装
- [ ] 桌面备份可清理：`quiz-app-git-full-*.zip`、`quiz-app-dotgit-*`、`zhenti-json-backup-*.zip`
