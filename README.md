# HOI4 Mod 创意工坊上传工具 v2.1

绕过 Paradox 启动器，直接使用 **SteamCMD** 将本地 Mod 上传到 Steam 创意工坊。

## 为什么需要这个工具

P社自带的启动器经常识别不到本地 Mod 文件（尤其是手动创建、非启动器生成的 Mod），导致无法上传。本工具直接调用 Steam 官方的 `steamcmd +workshop_build_item` 接口，与启动器底层用的是同一套 API，不依赖启动器识别 Mod。

## 环境要求

- Windows 10 / 11
- Python 3.8+（自带 tkinter，无需额外依赖；装有 Pillow 时预览图缩略图支持 JPG，没有也能用）
- Steam 账号（需拥有 Hearts of Iron IV）
- 网络能访问 Steam

## 快速开始

```bash
python hoi4_mod_uploader.py
```

1. **左侧「我的 Mod」**：上传过的 Mod 都在历史列表里，单击即载入（自动带上对应的已发布 ID）
2. **左侧「本地 Mod」**：自动扫描 HOI4 的 mod 目录（文档\Paradox Interactive\Hearts of Iron IV\mod），所有带 descriptor 的 Mod 都列出来并标注是否已发布，单击即载入
3. **① Mod 选择**：选目录 → 自动解析名称/版本/标签，自动匹配缩略图（切换 Mod 时预览图和描述会跟着切换），显示 Mod 大小和本机游戏版本核对
4. **② Steam 账号**：输账号密码（首次登录加 Steam Guard 验证码）；可先点「测试登录」验证账号，不上传任何内容
5. **③ 创意工坊信息**：标题、描述、预览图、可见性、更新说明（有历史下拉）
6. **▶ 开始上传**（或 Ctrl+Enter）：底部日志面板实时显示进度，右键状态栏可复制工坊链接

首次上传成功后 PublishedFileID 自动保存；以后更新直接点上传即可。

## 窗口与外观

- 窗口可以**任意拉伸**，默认尺寸按屏幕大小自动放大，关闭时记住大小和位置
- 左下角：「主题」按钮一键切换深色 / 浅色；「A− / A＋」调整界面字号
- 「设置」里还有：尺寸预设（最大到 1920×1080 / 最大化）、记住窗口开关、SteamCMD 管理、上传后自动打开工坊页面等
- 桌面快捷方式：`HOI4 Mod上传工具.lnk`，双击即开（pythonw 无黑窗启动）；图标为 `uploader_icon.ico`，可用 `python make_icon.py` 重新生成

## 登录数据安全

- 配置保存在 `uploader_config.json`，包含：账号名、各 Mod 的已发布 ID、偏好设置
- **密码默认不保存**（只在本次运行中使用）；如需 convenience 可在界面上勾选「记住密码」，会**明文**存到本机配置，风险自担
- 升级到 v2.0 时原始配置已备份为 `uploader_config.backup.json`；每次写入前也会自动留备份，历史记录不会被清掉

## 常见问题

### Q: 提示 "Login Failure: Rate Limit" / 登录失败
A: Steam 对短时间内多次登录有限制。等几分钟再试；可先用「测试登录」确认账号没问题。

### Q: Steam Guard 验证码怎么填？
A: 首次在本工具登录时，Steam 会向邮箱/手机令牌发送验证码，填入「Steam Guard」框一起登录。之后同一台机器通常不再需要。

### Q: 提示 Mod 路径包含中文，可能失败？
A: SteamCMD 对非 ASCII 路径支持差。把 Mod 移到纯英文路径（如 `C:\HOI4Mods\xxx`）再解析上传。SteamCMD 本体和 VDF 必须在纯英文目录（默认 `E:\SteamCMD`）。

### Q: 提示游戏版本不一致？
A: 工具会读取本机 HOI4 的 `launcher-settings.json` 与 Mod 的 `supported_version` 对比大小版本号，不一致时玩家侧可能提示不兼容，建议更新 descriptor。

### Q: 上传成功但工坊页面是私密的？
A: 检查「可见性」设置（公开 / 仅好友 / 私密），或上传后到工坊页面手动改。

### Q: 预览图要求？
A: 建议 1920×1080 PNG/JPG，超过 1MB 会提醒（可能被 Steam 拒收）。解析 Mod 时会自动找 `thumbnail.png` / `preview.png`。

## 技术原理

```
工具生成 VDF 配置文件
        ↓
steamcmd +login <user> <pass> +workshop_build_item upload_workshop.vdf +quit
        ↓
Steam 服务器处理上传，返回 PublishedFileID
        ↓
工具从 VDF 中回读 ID 并保存到配置
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `hoi4_mod_uploader.py` | 主程序（GUI，v2.0） |
| `hoi4_mod_uploader_v1_backup.py` | v1.0 旧版备份 |
| `uploader_config.json` | 配置文件（账号 / 历史 ID / 偏好，自动生成，**不入库**） |
| `uploader_config.example.json` | 配置文件结构示例（给新用户参考） |
| `uploader_config.backup.json` | 升级到 v2.0 时的原始配置备份 |
| `upload_workshop.vdf` | 上传配置（在 E:\SteamCMD 下，自动生成） |
| `logs/` | 每日运行日志（自动生成） |
| `uploader_icon.ico` / `icon_256.png` | 程序图标（窗口、任务栏、快捷方式共用） |
| `make_icon.py` | 图标生成脚本（需要 Pillow，可自行改配色重新生成） |
| `make_cover.py` / `cover_bg.png` / `thumbnail.png` | 封面图制作脚本及素材（与上传无关） |

## 许可证

MIT
