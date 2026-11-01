# ojousama：Claude 大小姐的感知插件

Claude 大小姐是一个住在 Claude 桌面应用窗口上的 Q 版小挂件。这个插件是她的"感知"：

- 监听 Claude 的工作状态：思考中、调用工具、等你确认、一轮完成、空闲
- 读取 Pro / Max 订阅的 5 小时、7 天额度和本次会话花费
- 把这些写到项目文件夹的 `state/sessions/<会话 id>.json`
- 会话开始时运行 `overlay/launch.cmd` 叫醒桌面上的大小姐（`overlay/ojousama.py`）

大小姐自己负责画出来、贴着 Claude 窗口、拖动吸附、按状态换表情，Claude 关掉时她也会离开。

## 文件夹结构

```
claude-ojousama/
├── mod/        这个插件
├── overlay/    桌面上的大小姐（Python + PySide6）
├── art/cut/    九张透明背景的表情
└── state/      插件和大小姐之间传递状态的地方
```

## 长期安装

在 `~/.claude/settings.json` 的 `env` 里加上：

```json
"CLAUDE_CODE_PLUGIN_DIRS": "D:\\你放项目的地方\\claude-ojousama\\mod"
```

之后新开的 Claude Code 会话都会自动加载它。
