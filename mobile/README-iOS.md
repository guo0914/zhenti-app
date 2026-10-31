# iOS App 打包指南

> 本目录是 Capacitor 壳应用。它把 `../site` 的网页打包成原生 iOS App。
>
> **重要：编译 iOS App 必须有 macOS + Xcode。Windows 只能生成工程，不能编译。**

---

## 一、这个 App 是什么

采用 **Capacitor**（原 Ionic 团队出品）方案，本质是：

```
你的网页（HTML/CSS/JS）  →  装进一个原生 App 外壳  →  变成 .ipa
```

优点：
- 网页代码完全复用，不用重写
- 题库 92MB 全部内置，**完全离线可用**
- 可访问原生能力（后续可加震动、通知、本地存储等）

---

## 二、日常改代码后如何更新

每次改了 `../site` 里的东西，在这个目录跑：

```bash
npm run sync
```

它做两件事：
1. `prepare-www.js` —— 把 `../site` 复制成 `www/`，并做 App 化改造
2. `cap sync` —— 把 `www/` 同步到 iOS 工程的资源目录

然后重新编译。

---

## 三、打包产物自检

```bash
node scripts/verify-www.js
```

检查 29 项，包括：脚本注入顺序、SW 是否禁用、iOS 安全区样式、
题库分片完整性、包体积等。**全绿才能打包。**

---

## 四、方案 A：有 Mac（推荐，最正规）

### 1. 准备工作

- 一台 macOS 电脑（黑苹果也算）
- 安装 **Xcode**（App Store 免费下载）
- 安装 **CocoaPods**：`sudo gem install cocoapods`

### 2. 打开工程

把整个 `mobile/` 目录拷到 Mac 上，然后：

```bash
cd mobile
npm install
npm run sync
cd ios/App
pod install
```

### 3. 用 Xcode 打开

```bash
open ios/App/App.xcodeproj
```

或双击 `ios/App/App.xcodeproj`。

### 4. 配置签名

在 Xcode 里：

1. 左侧选中 **App** 项目
2. 中间选 **Signing & Capabilities** 标签
3. **Team** 下拉选择你的 Apple ID
   - 没有的话：Xcode → Settings → Accounts → 加 Apple ID（免费的就行）
4. **Bundle Identifier** 改成唯一的，比如 `com.yourname.zhenti`
   - 要和 `capacitor.config.json` 里的 `appId` 一致（或在这里直接改）

### 5. 选择设备并运行

- 想装自己 iPhone：用数据线连电脑，顶部设备选择器选你的 iPhone
- 想上传 App Store：选 **Any iOS Device (arm64)**

### 6. 打包

**装到自己手机上（免费 Apple ID 即可）**：
1. 连上 iPhone
2. 按 `Cmd + R` 运行
3. 首次会提示「不受信任的开发者」，去 iPhone 设置 → 通用 → VPN与设备管理 → 信任你的 Apple ID
4. ⚠️ 免费账号签名的 App **7 天后失效**，需要重新用 Xcode 运行一次

**上传 App Store（需付费账号 $99/年）**：
1. Product → Archive
2. 在 Organizer 里点 **Distribute App**
3. 选 App Store Connect
4. 上传后到 App Store Connect 提交审核

---

## 五、方案 B：没有 Mac —— 云构建（推荐给多数人）

### 选项 1：Codemagic（有免费额度）

1. 注册 https://codemagic.io
2. 关联你的 Git 仓库（代码已在 Gitee：`git@gitee.com:a812183279/quiz-app.git`）
3. 在项目里指定 `mobile/` 为工作目录
4. 添加构建配置：
   ```
   npm install
   npm run sync
   cd ios/App && pod install
   ```
5. Codemagic 会自动用 Mac 机器编译
6. 免费额度：每月 500 分钟构建时间（够用十几次）

**产物**：可以下载未签名的 `.ipa`，或用测试分发（需要设备 UDID 注册）。

### 选项 2：GitHub Actions

在仓库加 `.github/workflows/ios.yml`：

```yaml
name: Build iOS
on: [push, workflow_dispatch]
jobs:
  build:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - name: Build
        working-directory: mobile
        run: |
          npm install
          npm run sync
          cd ios/App && pod install
      - name: Archive
        working-directory: mobile/ios/App
        run: |
          xcodebuild -workspace App.xcworkspace \
            -scheme App \
            -configuration Release \
            -archivePath $PWD/build/App.xcarchive \
            -destination 'generic/platform=iOS' \
            CODE_SIGNING_ALLOWED=NO \
            archive
      - uses: actions/upload-artifact@v4
        with:
          name: ios-build
          path: mobile/ios/App/build/
```

**注意**：这样产出的是**未签名**的 .ipa，只能：
- 用 **AltStore / SideStore** 侧载到 iPhone（需要每 7 天重签）
- 或用 **Sideloadly**（Windows 上也能用！见方案 C）

### 选项 3：Appflow（Ionic 官方付费服务）

https://ionic.io/appflow —— 付费，但最省事。

---

## 六、方案 C：Windows 上也能装（Sideloadly + 未签名 ipa）

**这条路在纯 Windows 上可行**，步骤：

### 1. 拿到未签名的 .ipa

用方案 B 的云构建产出 `.ipa` 文件。

### 2. 在 Windows 装 Sideloadly

下载：https://sideloadly.io/

### 3. 签名并安装

1. iPhone 用数据线连电脑
2. 打开 Sideloadly，把 `.ipa` 拖进去
3. 填你的 Apple ID（免费即可）
4. 点 **Start**
5. 首次需要在 iPhone 上信任证书：
   设置 → 通用 → VPN与设备管理 → 信任

### 4. 限制

- 免费 Apple ID：**每 7 天需要重新签名一次**
- 最多同时装 3 个自签 App
- 需要 Windows 安装 iTunes（Sideloadly 依赖它识别设备）

---

## 七、方案 D：最简单 —— PWA 添加到主屏幕

如果只是想「手机上有个图标，点开就能用」，**完全不需要打包**：

1. iPhone 用 Safari 打开你的站点
2. 点底部分享按钮
3. 选「添加到主屏幕」
4. 完成 —— 有了图标、全屏运行、可离线

**和原生 App 的差别**：
- ✅ 图标、全屏、离线缓存都有
- ❌ 不能上架 App Store
- ❌ 没有原生能力（通知、震动等）

**这是最省事的方案，5 分钟搞定。**

---

## 八、Store 上架需要什么

如果真要上架 App Store：

| 项目 | 要求 |
|------|------|
| Apple 开发者账号 | $99/年 |
| Mac + Xcode | 必需 |
| App 图标 | 1024×1024 PNG，无透明 |
| 启动图 | 各尺寸适配 |
| 隐私政策 | 必须提供 URL |
| 审核 | 1-7 天，可能被拒多次 |

**特别注意**：Apple 审核指南 4.2 条规定，
「只是把网页包一层」的 App **可能被拒**。需要证明有原生价值。

---

## 九、当前工程状态

已完成的改造：

- ✅ Capacitor 6 工程（iOS + Android 都能生成）
- ✅ 注入 iOS 安全区样式（刘海、底部横条适配）
- ✅ 禁用用户缩放、长按菜单（更像原生）
- ✅ 禁用 Service Worker（App 内不需要，避免更新问题）
- ✅ API 相对路径自动改写成绝对地址
- ✅ 应用内「⚙ 设置页」可配服务器地址
- ✅ 离线模式（不配服务器也能刷题，题库内置）
- ✅ 自检脚本 29 项全绿

未完成（需要 Mac）：

- ⬜ 编译成 .ipa
- ⬜ 应用图标替换（当前用的是网页版图标）
- ⬜ 启动画面定制

---

## 十、遇到问题

### `pod install` 慢或失败

换国内镜像：

```bash
pod repo remove trunk
pod repo add trunk https://cdn.jsdelivr.net/cocoa/Specs.git
```

或用清华镜像：
```bash
cd ~/.cocoapods/repos
git clone https://mirrors.tuna.tsinghua.edu.cn/git/CocoaPods/Specs.git master
```

### Xcode 报签名错误

- 检查 Bundle Identifier 是否唯一
- 确认 Team 已选择
- 免费账号不能使用某些 Capabilities

### App 打开白屏

1. 检查 `www/index.html` 是否有内容
2. 在 Xcode 里打开 Safari 开发者工具（Safari → 开发 → 你的设备）
3. 看 Console 报错

### App 里点不动 / 布局异常

经测试，网页版在个别浏览器（装了扩展的 Edge）会有布局问题。
App 内是干净环境，不受影响。如果 App 内也有问题，
在设置页把「服务器地址」清空，用纯离线模式试试。
