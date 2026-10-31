# 走 IPA：不打域名审核，直接装自己手机

> 你的情况：Windows + iPhone，无 Mac，无开发者账号，不上架。
> 结论：**可以，全程约 1-2 小时，0 成本。**

---

## 原理

```
你的 Windows              GitHub 的 macOS 机器          你的 iPhone
─────────────            ────────────────────          ────────────
1. 推代码到 GitHub   →   2. Actions 自动编译      →   3. Sideloadly 签名安装
   （92MB，5 分钟）        （10-15 分钟，免费）          （Windows 上操作，10 分钟）
                          产出未签名 .ipa
```

**关键点**：
- GitHub Actions 对公开仓库**完全免费**，macOS 机器也是免费的
- 编译需要 macOS（Apple 的硬规定），但签名安装可以在 Windows 上做
- 不上架 App Store，就不需要 $99/年的开发者账号

---

## ⚠️ 先说清楚三个限制

| 限制 | 说明 | 应对 |
|------|------|------|
| **7 天失效** | 免费 Apple ID 签名的 App，7 天后打不开 | 每周连电脑重签一次（2 分钟）；或用 AltStore 自动重签 |
| **最多 3 个 App** | 免费账号同时只能装 3 个自签 App | 一般够用 |
| **需要 Windows 装 iTunes** | Sideloadly 靠它识别 iPhone | 微软商店免费装 |

如果 7 天重签觉得麻烦，最后还是建议回到「离线单文件」或「买域名」方案。

---

## 第 1 步：代码推到 GitHub（10 分钟）

### 1.1 在 GitHub 建仓库

1. 打开 https://github.com （现在你的网络能访问了）
2. 注册/登录
3. 右上角 **+** → **New repository**
4. 仓库名：`zhenti-app`
5. **选 Public**（公开仓库的 Actions 免费无限；私有仓库每月只有 2000 分钟）
6. **不要**勾选 "Add a README"
7. 点 **Create repository**

### 1.2 推送代码

在电脑上打开命令行：

```bash
cd "C:\Users\严睿霖\Documents\deepseek-harness\default-workspace\quiz-app"

# 添加 GitHub 远程（把 YOURNAME 换成你的 GitHub 用户名）
git remote add github https://github.com/YOURNAME/zhenti-app.git

# 推送
git push github main
```

推送约 92MB，需要几分钟。

如果提示要输密码，用 **Personal Access Token**（不是账号密码）：
GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic) → Generate new token → 勾选 `repo` → 生成后复制，粘贴到密码位置。

---

## 第 2 步：让 Actions 编译（15 分钟）

### 2.1 触发构建

1. 打开你的仓库页面
2. 点 **Actions** 标签
3. 左侧选 **Build iOS IPA**
4. 右侧点 **Run workflow** → 再点绿色的 **Run workflow**
5. 刷新页面，会看到一次构建正在运行（黄色圆点）

### 2.2 等待

构建过程约 **10-15 分钟**，会依次执行 11 个步骤：

```
✓ Checkout
✓ Setup Node.js
✓ Environment info
✓ Install npm deps
✓ Build www
✓ Capacitor sync
✓ Install CocoaPods deps     ← 这步最慢（3-5 分钟）
✓ Build archive              ← 编译，5-8 分钟
✓ Package IPA
✓ Upload IPA
```

### 2.3 下载 ipa

构建完成后：

1. 点进这次运行记录
2. 页面底部 **Artifacts** 区域
3. 点 **App-unsigned-ipa** 下载
4. 得到一个 zip，解压出 `App-unsigned.ipa`

---

## 第 3 步：签名安装到 iPhone（10 分钟）

### 3.1 准备 Windows 环境

1. **装 iTunes**
   微软商店搜 "iTunes" 安装；或官网下载。
   Sideloadly 需要它提供的驱动来识别 iPhone。

2. **下载 Sideloadly**
   https://sideloadly.io/

3. **iPhone 用数据线连电脑**
   - 用 USB 直连，不要经过 hub
   - iPhone 弹「信任此电脑」→ 点信任

### 3.2 生成 App 专用密码（如果开了双重认证）

苹果账号开了双重认证的话，**不能用登录密码**，必须生成专用密码：

1. 浏览器打开 https://appleid.apple.com
2. 登录
3. 找到 **安全** → **App 专用密码**
4. 点「生成密码」→ 随便填个名字（如 "Sideloadly"）
5. 复制生成的密码（形如 `abcd-efgh-ijkl-mnop`）

### 3.3 签名安装

1. 打开 **Sideloadly**
2. 把 `App-unsigned.ipa` **拖进窗口**（或点左上角 IPA 图标选择文件）
3. **Apple ID** 框填你的 Apple ID 邮箱
4. **Password** 填上一步生成的**专用密码**
5. 点 **Start**
6. 等待，会依次显示：
   ```
   Signing...
   Installing...
   Done.
   ```

### 3.4 iPhone 上信任证书（第一次必须做）

1. iPhone → **设置** → **通用** → **VPN与设备管理**
2. 找到「开发者 App」下面你的 Apple ID（邮箱地址）
3. 点进去 → **信任「你的邮箱」**
4. 弹窗确认 → **信任**

### 3.5 完成

回到桌面，图标「行测刷题」已经出现。点开即用。

---

## 第 4 步：App 内配置（可选）

打开 App 后：

**只离线刷题**：什么都不用配。题库 19MB 全在 App 里，直接能刷。

**想同步进度到电脑**：
1. 点右上角 **⚙ 齿轮**
2. 填服务器地址：
   - 同一 WiFi：`http://192.168.x.x:8000`（电脑上 `ipconfig` 查）
   - 任意网络：电脑上跑 `穿透.cmd` 拿到 `https://xxx.trycloudflare.com`
3. 点 **测试连接** → 显示「连接成功」→ **保存**

---

## 7 天失效怎么办

到期后 App 会提示「无法验证 App」。重新签名即可：

1. iPhone 连电脑
2. 打开 Sideloadly
3. 把**同一个 ipa** 拖进去
4. 点 Start

**2 分钟搞定，不用重新编译。**

### 三个长期方案

| 方案 | 成本 | 说明 |
|------|------|------|
| 每周重签 | 免费 | 连电脑点一次 |
| AltStore 自动重签 | 免费 | 需家里有台常开的电脑跑 AltServer，后台自动重签 |
| 付费开发者账号 | $99/年 | 签名 1 年有效，也可上架 |
| 回退到离线单文件 | 免费 | 无失效问题，但没有桌面图标和全屏 |

---

## 常见问题

### Actions 构建失败

点进失败的运行记录，看哪一步标红。常见原因：

| 失败步骤 | 原因 | 解决 |
|---------|------|------|
| Install CocoaPods deps | 网络慢导致 pod 超时 | 已加 `pod install` 不带 `--repo-update` 的优化，通常能过 |
| Build archive | Bundle ID 冲突 | 已在配置里改成 `com.yanruilin.zhenti` |
| Package IPA | 找不到 .app | 检查编译日志，通常是上一步失败 |

**把失败的日志截图发我**，我帮你改配置。

### 推送代码报错 `remote: Support for password authentication was removed`

GitHub 不再支持密码推送，要用 **Personal Access Token**。
生成方法见第 1.2 节。

### Sideloadly 报 `Could not connect to device`

1. 确认 iTunes 装了
2. 换 USB 口（优先主板后面的）
3. iPhone 上「信任此电脑」
4. 关掉其他占用设备的程序（iTunes、爱思助手）

### Sideloadly 报 `Invalid Apple ID or password`

开了双重认证的话要用**专用密码**，不是登录密码。见 3.2。

### 装完打开是白屏

1. 等 3-5 秒（首次加载题库）
2. 如果一直白屏，在 App 里下拉刷新
3. 或检查 Xcode 日志（需要 Mac，或者把 ipa 重新装一次）

### 免费账号提示 `Unable to install`

- 免费账号同时只能装 3 个自签 App，先删掉其他的
- 或换一个新的 Apple ID 试

---

## 检查清单

开始之前确认：

- [ ] GitHub 账号能登录
- [ ] 命令行 `git` 可用
- [ ] Windows 已装 iTunes
- [ ] Sideloadly 已下载
- [ ] iPhone 数据线能连（USB 直连）
- [ ] 知道自己的 Apple ID 密码（或已生成专用密码）

全部就绪后，按上面 4 个步骤走，1-2 小时能装好。
