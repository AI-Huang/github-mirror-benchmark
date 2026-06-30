# github-mirror-benchmark

面向国内网络环境的 GitHub 镜像测速工具，用于快速比较多个 GitHub 镜像的下载响应和阶段性下载耗时。

English documentation: [docs/README_EN.md](docs/README_EN.md)

## 功能

- 内置多个常见 GitHub 镜像源，并带有实时进度显示
- 测量首字节时间、1 KB、1000 KiB、10 MiB 阶段下载时间
- 可选显示吞吐速度，便于比较不同镜像的实际下载表现
- 支持临时指定 benchmark 文件路径、额外镜像和只测试指定镜像
- 使用 [Rich](https://github.com/Textualize/rich) 输出清晰的终端表格

## 安装

需要 Python >= 3.11 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone <repo-url>
cd github-mirror-benchmark
uv sync
```

## 使用

```bash
# 使用默认配置运行测速
uv run python main.py run

# 使用一个假的示例路径覆盖本次测速文件
uv run python main.py run --file /example-owner/example-repo/releases/download/v0.0.0/example.bin

# 不显示吞吐速度，只看阶段下载时间
uv run python main.py run --no-speed-mbps

# 只测试指定镜像
uv run python main.py run --only "github.com (official)" --only "ghproxy.com"

# 临时添加自定义镜像
uv run python main.py run --mirror "my-mirror=https://my.proxy.example.com/https://github.com"

# 调整请求超时和单镜像最长下载时长，单位都是毫秒
uv run python main.py run --timeout 10000 --endurance 30000

# 查看内置镜像列表
uv run python main.py list
```

## 配置 benchmark 文件

默认 benchmark 文件路径从 `.env` 里的 `BENCH_FILE_PATH` 读取。本仓库不会提交 `.env`，请按自己的网络环境和目标文件在本地配置。

```env
BENCH_FILE_PATH=/example-owner/example-repo/releases/download/v0.0.0/example.bin
```

代码和文档中的路径使用 fake example path；实际可访问的测试文件请只放在本地 `.env` 或命令行参数里。

## 内置镜像

| 名称 | 基础 URL |
| --- | --- |
| github.com (official) | <https://github.com> |
| gh-proxy.com | <https://gh-proxy.com> |
| ghfast.top | <https://ghfast.top> |
| ghproxy.net | <https://ghproxy.net> |
| moeyy.cn | <https://gh.moeyy.cn> |
| github.akams.cn | <https://github.akams.cn> |
| kkgithub.com | <https://kkgithub.com> |
| bgithub.xyz | <https://bgithub.xyz> |
| dgithub.xyz | <https://dgithub.xyz> |
| githubfast.com | <https://githubfast.com> |
| hub.nuaa.cf | <https://hub.nuaa.cf> |

## 选项

| 选项 | 默认值 | 说明 |
| --- | --- | --- |
| `--file` | `.env` 中的 `BENCH_FILE_PATH` | 相对 GitHub 根路径的 benchmark 文件路径 |
| `--timeout` | `10000` | 单个镜像请求超时时间，单位毫秒 |
| `--endurance` | `30000` | 单个镜像最长下载时长，单位毫秒 |
| `--mirror NAME=URL` | - | 添加额外镜像，可重复传入 |
| `--only NAME` | - | 只测试指定名称的内置镜像，可重复传入 |
| `--no-speed-mbps` | - | 隐藏吞吐速度列，并跳过 MB/s 计算 |
