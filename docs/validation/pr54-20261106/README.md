# PR #54 头像上传验证（2026-11-06）

## 修复了什么

原候选在 try/except 中间插入顶层函数，导致用户模块 SyntaxError、API 无法加载。本轮把函数和限额移到完整配置块之后。双接口超过 10 MiB 返回真实 HTTP 413，修复仅返回 JSON code=413 而 HTTP 仍为 200 的问题；POST 缺少文件时不再访问 None.filename。文件名先统一分隔符、去空字节并取 basename，保存仍使用原有 UUID 文件名。

原 PR 声称原实现可用客户端文件名直接路径穿越，这与实际源码不符：基线已使用 UUID 保存，未复现该路径穿越。此次属于文件名规范化及大小防护，不能描述为修复已证实的任意路径写入。

## 有什么作用

正常图片上传及头像地址更新保持可用；超限图片不会保存到头像目录或更新用户头像。两种上传方法遵循相同大小边界。

## 验证结果

在 kol-stage2 复用已有镜像 `sha256:4d712690199b17ea76030095e97037b2b656bf6fba502c06fe79a0367e195f63`，无网络、只读源码、无凭据和服务连接。当前 base：`512d7dedbf2e21a9e281599f29507ad257fdb36e` 已普通 merge 进入贡献分支；本轮仅头像模块及测试变动。

运行命令（目录为本轮临时副本）：

```sh
sudo -u onticards-preview env DOCKER_HOST=unix:///run/user/1001/docker.sock docker run --rm --network none --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges --mount type=bind,src=/tmp/onti-pr54-cba4d066/user,dst=/work,readonly -w /work --entrypoint python 4d712690199b test_avatar_upload.py
```

- [原候选失败日志](red.log)：原 head `10e2a0d065e0d3e44ad9e64d1da0a3794bb7c5ec`，6 项因 SyntaxError 无法开始（exit 1）。
- [修正语法后的行为失败](behavior-red.log)：证实缺文件异常及两种方法超限 HTTP 200（exit 1）。其中 basename 已修正。
- [最终日志](green.log)：6 项通过（exit 0）；覆盖 POST/PUT 正常、两种路径分隔符及绝对路径、中文名、10 MiB 完整保存、10 MiB+1 拒绝、无文件/空名/无效后缀/不存在用户、不写文件或不提交。
- [测试文件摘要](tested-files.sha256)：与最终源码/测试核对。测试完整解析生产模块，再原样编译头像部分，使用真实 Flask/Flask-RESTful multipart 请求及真实临时磁盘文件；用户查询和提交使用内存替身。

独立上下文终审及最终 head 记录在 PR 正文，未启动 GitHub CI。无 UI 改动。

## 剩余限制

没有导入整个应用或连接真实数据库，也未做浏览器、生产部署和代理层验证。每文件限额在 multipart 解析完成后检查，不能限制请求接收/解析阶段临时磁盘用量、并发或大量重复上传；不能据此声称完整防御上传 DoS。未增加图片内容解码/身份权限/旧头像回收策略。这些为既有边界，不在此次文件名和大小局部审查范围。容器使用 --rm，本轮未创建镜像、持久卷或 Docker 网络；远端临时源码在取证及独审结束后定向清理。
