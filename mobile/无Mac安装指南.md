# 没有 Mac 怎么装到 iPhone 上

> 你手上的环境：Windows + iPhone。没有 Mac，没有苹果开发者账号。
>
> 下面这条路**完全可行**，我第一次做大概 2 小时，熟练后 20 分钟。

---

## 全流程一览

```
Windows 电脑              云端 Mac               iPhone
─────────────            ─────────────           ────────────
1. 推代码到 GitHub   →   2. 自动编译 ipa    →   3. Sideloadly 签名安装
                          (Codemagic 或           （Windows 上操作）
                           GitHub Actions）
```

关键点：**编译必须在 macOS 上做**（Apple 的硬性规定），
但「签名安装」这一步可以在 Windows 上完成。

---

## 第 0 步：准备（约 20 分钟，一次性）

### 0.1 注册云端构建账号（选一个）

**选项 A：Codemagic**（推荐，界面最友好，有免费额度）

1. 打开 https://codemagic.io
2. 用 GitHub / Google 账号注册
3. 免费额度：每月 **500 分钟** macOS 构建（一次构建约 10-15 分钟，够用 30 次）

**选项 B：GitHub Actions**（完全免费，但需要公开仓库或用额度）

1. 需要 GitHub 账号
2. 公开仓库 → 免费无限
3. 私有仓库 → 每月 2000 分钟（macOS 消耗 ×10，实际 200 分钟）

### 0.2 代码放到 GitHub

你的代码现在在 Gitee。两种做法：

**做法一（推荐）：Gitee 镜像到 GitHub**

1. 在 GitHub 新建空仓库（如 `zhenti-ios`）
2. 在命令行操作：

```bash
cd "C:\Users\严睿霖\Documents\deepseek-harness\default-workspace\quiz-app"

# 添加 GitHub 远程
git remote add github https://github.com/你的用户名/zhenti-ios.git

# 推上去（会包含 mobile/ 目录）
git push github main
```

**做法二：直接 clone Gitee 再推到 GitHub**

```bash
cd D:\
git clone --bare https://gitee.com/a812183279/quiz-app.git quiz-app.git
cd quiz-app.git
git push --mirror https://github.com/你的用户名/zhenti-ios.git
```

### 0.3 iPhone 上装 Sideloadly 需要的组件

1. Windows 上装 **iTunes**（微软商店或官网下载）
   - Sideloadly 靠 iTunes 的驱动识别 iPhone
2. 下载 **Sideloadly**：https://sideloadly.io/
3. iPhone 用数据线连电脑，「信任此电脑」

---

## 第 1 步：云端编译（约 15 分钟）

### 用 Codemagic 的话

1. 登录 Codemagic
2. **Add application** → 选 GitHub → 选你的 `zhenti-ios` 仓库
3. 项目配置它会自动读取 `mobile/codemagic.yaml`
4. 点 **Start new build**，选 `ios-unsigned` 这个 workflow
5. 等 10-15 分钟
6. 构建完成后，在 **Artifacts** 里下载 `App-unsigned.ipa`

### 用 GitHub Actions 的话

1. 代码推到 GitHub 后，进仓库 → **Actions** 标签
2. 左边选 **Build iOS (Unsigned)**
3. 右边点 **Run workflow** → **Run workflow**
4. 等 10-15 分钟
5. 完成后点进这次运行 → 底部 **Artifacts** → 下载 `ios-unsigned-ipa.zip`
6. 解压得到 `App-unsigned.ipa`

---

## 第 2 步：签名安装（约 10 分钟）

1. **iPhone 连电脑**（用数据线，USB 直连不要用 hub）

2. 打开 **Sideloadly**

3. **把 ipa 拖进 Sideloadly 窗口**（或用左侧 IPA 图标选择文件）

4. 在 **Apple ID** 框里填你的 Apple ID
   - 免费账号就行，不需要开发者账号
   - ⚠️ 如果开了双重认证，需要在 https://appleid.apple.com 生成一个**专用密码**填进去（不是你的登录密码）

5. 点 **Start**

6. 等待，会看到进度：
   ```
   Signing... → Installing... → Done
   ```

7. **iPhone 上信任证书**（第一次必须做）：
   - 设置 → 通用 → VPN与设备管理
   - 找到「开发者 App」下面你的 Apple ID
   - 点进去 → **信任**

8. 回到桌面，App 图标已经出现，点开即用

---

## 第 3 步：App 内配置（1 分钟）

打开 App 后：

**如果只想离线刷题**：什么都不用配，直接进「分类刷题」就能用。
题库 19MB 全在 App 里。

**如果要同步进度到电脑（可选）**：
1. 点右上角 **⚙ 齿轮**
2. 填服务器地址：
   - 电脑和手机同一 WiFi：`http://192.168.x.x:8000`
     （在电脑命令行运行 `ipconfig`，看「IPv4 地址」）
   - 任意网络：先在电脑上双击 `穿透.cmd`，会得到一个
     `https://xxx.trycloudflare.com` 地址，填这个
3. 点 **测试连接** → 显示「连接成功」→ 点 **保存**

---

## 关于「7 天失效」

免费 Apple ID 签名的 App **7 天后会打不开**（提示「无法验证 App」）。
这不是 bug，是苹果对免费账号的限制。

**三个应对办法**：

| 办法 | 成本 | 说明 |
|------|------|------|
| **每周重新签名** | 免费 | 连电脑用 Sideloadly 再点一次 Start，2 分钟 |
| **付费开发者账号** | $99/年 | 签名有效期 1 年，不用管 |
| **AltStore 自动重签** | 免费 | 需家里有台常开的电脑跑 AltServer，自动后台重签 |
| **改用 PWA** | 免费 | 完全没有失效问题（见下） |

---

## 备选：PWA（如果觉得上面太麻烦）

如果「7 天重签一次」让你觉得麻烦，其实有个**零成本方案**：

1. iPhone 用 **Safari** 打开你的站点
2. 点底部分享按钮
3. 选 **添加到主屏幕**
4. 完成

效果：
- ✅ 桌面有图标
- ✅ 点开全屏运行（没有地址栏）
- ✅ 能离线使用
- ✅ **永不失效**
- ❌ 不能上架 App Store
- ❌ 没有原生能力（推送通知等）

**日常自用的话，这个方案其实就够。**

---

## 遇到问题

### 云构建失败，报 `pod install` 错误

可能是 CocoaPods 仓库太慢。在 `codemagic.yaml` 的 pod install 步骤前加：

```yaml
- name: 换 CocoaPods 镜像
  script: |
    pod repo remove trunk || true
    pod repo add trunk https://cdn.jsdelivr.net/cocoa/Specs.git
```

### 报 `No signing certificate` 错误

说明用了 `ios-signed` 那个 workflow。**没有开发者账号就用 `ios-unsigned`**。

### Sideloadly 报 `Could not connect to device`

1. 确认 iTunes 装了
2. 换个 USB 口（优先用主板后面的口）
3. iPhone 上「信任此电脑」
4. 关掉其他占用设备的程序（iTunes、爱思助手等）

### Sideloadly 报 `Invalid Apple ID or password`

开了双重认证的话，**不能用登录密码**，要去
https://appleid.apple.com → 安全 → App 专用密码 → 生成一个，用那个。

### App 打开白屏

1. 等 3-5 秒（第一次加载题库需要时间）
2. 如果一直白屏：Xcode 里看日志（需要 Mac）；或者
   在 App 里下拉刷新试试
3. 检查 `mobile/www/index.html` 是否有内容

### App 里布局还是乱

网页版在你那台装了扩展的 Edge 上有布局问题，但 **App 内是干净环境**，
不会有这个问题。如果 App 内也有，在 ⚙ 里把地址清空（切纯离线）试试。

---

## 检查清单

打包前确认：

- [ ] `cd mobile && node scripts/verify-www.js` 全绿
- [ ] 代码已推到 GitHub
- [ ] Codemagic / GitHub Actions 账号已注册
- [ ] Windows 已装 iTunes + Sideloadly
- [ ] iPhone 数据线可连

做完这些就可以开始了。
