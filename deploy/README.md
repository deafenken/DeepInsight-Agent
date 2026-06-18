# 生产部署说明

这套配置面向“长期挂服务器、可公网访问”的部署方式，默认使用：

- `systemd` 常驻管理 `uvicorn`
- `nginx` 反向代理公网流量
- 本地 `SQLite + Chroma` 作为数据底座

当前仓库已同时提供两套 `nginx` 配置：

- 有域名场景：`deploy/nginx/deepinsight-agent.conf`
- 纯公网 IP 场景：`deploy/nginx/deepinsight-agent-ip.conf`

## 一、服务器需要准备的内容

代码仓库从 GitHub 拉下来后，还需要补以下本地数据：

- `data/enterprise_analysis.db`
- `data/chroma/`

如果你要在服务器上从零重建数据，还需要补：

- `Final_md/`

可选内容：

- `demo_cache/`
- `DEEPSEEK_API_KEY`

## 二、推荐目录

默认建议部署到：

```text
/root/DeepInsight-Agent
```

目录结构示例：

```text
/root/DeepInsight-Agent
├── .venv/
├── data/
│   ├── enterprise_analysis.db
│   └── chroma/
├── demo_cache/
├── deploy/
├── deepinsight/
├── webapp/
└── requirements.txt
```

## 三、安装依赖

```bash
cd /root/DeepInsight-Agent
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 四、传输数据

推荐从本地同步：

```bash
rsync -avP /Volumes/ORICO/code1/data/enterprise_analysis.db root@server:/root/DeepInsight-Agent/data/
rsync -avP /Volumes/ORICO/code1/data/chroma/ root@server:/root/DeepInsight-Agent/data/chroma/
rsync -avP /Volumes/ORICO/code1/demo_cache/ root@server:/root/DeepInsight-Agent/demo_cache/
```

如果要从零重建：

```bash
python3 -m deepinsight.dataops.db_init
python3 -m deepinsight.dataops.db_expand
python3 -m deepinsight.dataops.data_pipeline --input-dir /root/DeepInsight-Agent/Final_md
python3 -m deepinsight.dataops.macro_import --excel-path /root/DeepInsight-Agent/data/raw_macro/国家统计局_卫生_2022_2024.xlsx
python3 -m deepinsight.dataops.graph_data_pipeline --root-company ST生物
```

## 五、环境变量

复制模板：

```bash
cp deploy/env/webapp.env.example deploy/env/webapp.env
```

按需填写：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL`

如果不填 `DEEPSEEK_API_KEY`，系统会进入本地降级模式。

## 六、systemd

把服务文件复制到系统目录：

```bash
sudo cp deploy/systemd/deepinsight-web.service /etc/systemd/system/deepinsight-web.service
```

如果部署目录不是 `/root/DeepInsight-Agent`，先修改服务文件里的：

- `WorkingDirectory`
- `EnvironmentFile`
- `ExecStart`

然后启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable deepinsight-web
sudo systemctl start deepinsight-web
sudo systemctl status deepinsight-web
```

## 七、nginx

无域名、只用公网 IP 时，推荐直接使用：

```bash
sudo cp deploy/nginx/deepinsight-agent-ip.conf /etc/nginx/sites-available/deepinsight-agent-ip.conf
sudo ln -sf /etc/nginx/sites-available/deepinsight-agent-ip.conf /etc/nginx/sites-enabled/deepinsight-agent-ip.conf
```

如果你后续补了域名，再切回：

```bash
sudo cp deploy/nginx/deepinsight-agent.conf /etc/nginx/sites-available/deepinsight-agent.conf
sudo ln -sf /etc/nginx/sites-available/deepinsight-agent.conf /etc/nginx/sites-enabled/deepinsight-agent.conf
```

检查并重载：

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 八、证书

如果你当前没有域名，就先直接通过公网 IP 走 `HTTP` 访问。

如果以后补域名，再用 `certbot`：

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 九、运维命令

查看日志：

```bash
sudo journalctl -u deepinsight-web -f
```

重启服务：

```bash
sudo systemctl restart deepinsight-web
```

## 十、最小公网部署清单

最少需要：

- 一台 Linux 服务器
- 一个公网 IP
- 已开放 `80/443`
- 仓库代码
- `data/enterprise_analysis.db`
- `data/chroma/`

这样就可以长期挂网页并通过公网 IP 访问。
