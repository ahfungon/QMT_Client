# 部署文档

## 系统要求

### 硬件要求
- CPU: 双核及以上
- 内存: 4GB及以上
- 硬盘: 50GB可用空间

### 软件要求
- 操作系统: Windows 10/11 或 Linux
- Python 3.10+
- Git

## 环境准备

### Python环境
1. 下载并安装Python 3.10或更高版本
2. 确保pip已更新到最新版本
```bash
python -m pip install --upgrade pip
```

## 部署步骤

### 1. 获取代码
```bash
git clone [项目地址]
cd QMT_Client
```

### 2. 创建虚拟环境
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate
```

### 3. 安装依赖
```bash
pip install -r requirements.txt
```

### 4. 配置文件
1. 复制配置文件模板
```bash
cp config/app.example.yml config/app.yml
```

2. 修改应用配置 (config/app.yml)
```yaml
development:
  log_level: DEBUG
  api_base_url: http://localhost:5000/api/v1
  check_interval: 60  # 策略检查间隔（秒）

production:
  log_level: INFO
  api_base_url: http://your-api-server/api/v1
  check_interval: 60
```

### 5. 启动应用
```bash
# 开发环境
python run.py

# 生产环境
python run.py --env production
```

## 日志管理
- 日志文件位置: `logs/`
- 日志级别在 `config/app.yml` 中配置
- 日志文件按日期自动轮转

## 监控和维护

### 健康检查
- 定期检查日志文件
- 检查策略执行情况
- 监控系统资源使用情况

### 配置文件备份
- 定期备份 `config/` 目录
- 保存多个版本的配置文件

### 系统更新
1. 拉取最新代码
```bash
git pull origin main
```

2. 更新依赖
```bash
pip install -r requirements.txt
```

## 故障排除

### 常见问题
1. API调用失败
- 检查API服务器状态
- 验证API配置信息
- 查看错误日志

2. 策略执行异常
- 检查策略配置
- 验证账户余额
- 查看执行日志

### 日志查看
```bash
# 查看最新日志
tail -f logs/app.log

# 查看错误日志
grep ERROR logs/app.log
```

## 安全建议
1. 定期更新系统和依赖包
2. 使用强密码并定期更换
3. 启用防火墙
4. 定期备份数据

## 联系支持
- 技术支持邮箱: [待定]
- 问题反馈: [项目Issues地址] 