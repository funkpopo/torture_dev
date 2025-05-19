# Torture Dev

这个工具用于获取GitLab上所有项目在当天（或指定天数内）的提交记录，并将其保存为JSON或TXT文件以供后续LLM分析。同时提供API接口，方便集成到n8n等自动化工作流中。

## 安装

1. 克隆此仓库
2. 安装依赖：
   ```
   pip install -r requirements.txt
   ```

## 命令行模式

基本用法（使用管理员账号权限）：

```bash
python gitlab_commits.py --url https://your-gitlab-instance.com --admin-token YOUR_ADMIN_TOKEN
```

完整参数列表：

```bash
python gitlab_commits.py --url https://your-gitlab-instance.com --admin-token YOUR_ADMIN_TOKEN --output commits.json --days 3 --debug --format json
```

参数说明：
- `--url`: GitLab实例的URL（必填）
- `--admin-token`: GitLab管理员账号的私人访问令牌（必填）
- `--output`: 输出文件的路径（默认：gitlab_commits.txt）
- `--days`: 要获取的过去天数（默认：1，表示今天）
- `--debug`: 开启调试模式，输出详细信息（可选）
- `--format`: 输出格式，可选txt或json（默认：txt）

## API模式

本工具提供了RESTful API接口，方便集成到n8n等自动化工作流中。

### 启动API服务

```bash
python api.py
```

默认监听0.0.0.0:8000，可以通过环境变量自定义：

```bash
# 设置API服务监听地址和端口
export API_HOST=127.0.0.1
export API_PORT=9000
python api.py
```

### API文档

启动服务后，访问 http://localhost:8000/docs 查看自动生成的API文档。

### API接口说明

API提供了两种调用方式：

#### 1. POST方法

```bash
curl -X 'POST' \
  'http://localhost:8000/api/commits' \
  -H 'Content-Type: application/json' \
  -d '{
  "gitlab_url": "https://your-gitlab-instance.com",
  "admin_token": "YOUR_ADMIN_TOKEN",
  "days": 3,
  "debug": false,
  "threads": 0
}'
```

#### 2. GET方法

```bash
curl -X 'GET' \
  'http://localhost:8000/api/commits?gitlab_url=https://your-gitlab-instance.com&days=3' \
  -H 'X-GitLab-Token: YOUR_ADMIN_TOKEN'
```

### n8n集成示例

在n8n中，您可以使用HTTP Request节点来调用API：

1. 添加HTTP Request节点
2. 配置为POST请求
3. URL设置为: `http://your-server:8000/api/commits`
4. Body选择JSON格式，内容为:
```json
{
  "gitlab_url": "https://your-gitlab-instance.com",
  "admin_token": "YOUR_ADMIN_TOKEN",
  "days": 3
}
```
5. 将此节点的输出连接到后续处理节点

## Docker部署

提供了Docker和Docker Compose配置，方便快速部署：

```bash
# 使用Docker Compose部署
docker-compose up -d
```

默认端口为8000，可以通过环境变量或docker-compose.yaml文件修改。

## 获取GitLab管理员访问令牌

1. 使用管理员账号登录到GitLab
2. 点击右上角的用户头像 -> Preferences
3. 在左侧菜单中点击 "Access Tokens"
4. 创建一个新的访问令牌，确保勾选 `api` 和 `read_api` 权限
5. 生成令牌并妥善保存

使用管理员令牌的优势：
- 无需为每个用户生成access token
- 可以访问所有项目和用户数据
- 简化权限管理和维护

## 输出格式

### 文本格式 (--format txt)

输出的TXT文件包含提交信息、作者、时间和修改文件等详细记录。

### JSON格式 (--format json)

输出的JSON文件包含以下结构：

```json
{
  "metadata": {
    "date": "ISO格式的当前时间",
    "gitlab_url": "GitLab URL",
    "days_included": 天数,
    "projects_count": 项目数量,
    "users_count": 用户数量,
    "commits_count": 提交数量
  },
  "commits": [
    { 提交信息列表，包含diff和stats }
  ]
}
```

## 故障排除

如果脚本无法获取项目或提交信息，请尝试以下解决方法：

1. 使用 `--debug` 参数运行脚本，查看详细的错误信息
   ```bash
   python gitlab_commits.py --url https://your-gitlab-instance.com --admin-token YOUR_ADMIN_TOKEN --debug
   ```

2. 确认管理员令牌权限
   - 检查是否授予了 `api` 和 `read_api` 权限
   - 确认令牌未过期
   - 验证令牌是否有足够权限访问所有项目

3. API版本和限制问题
   - 不同GitLab版本的API可能有差异，脚本会尝试多种方法获取数据
   - 某些GitLab实例可能限制API访问频率或范围

4. 网络连接问题
   - 确保能够正常访问GitLab实例
   - 检查是否存在代理或防火墙限制

5. 如果仍然无法获取数据，可以尝试增加 `--days` 参数值，获取更长时间范围的提交
