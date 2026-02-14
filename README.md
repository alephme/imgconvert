# ImgConvert

一个最小的桌面图片格式转换工具（GUI）。支持 SVG、JPG、PNG、WebP 四种格式之间转换。

## 运行

1. 安装依赖：

```powershell
pip install -r requirements.txt
```

2. 启动：

```powershell
python -m imgconvert
```

## 说明

- SVG -> JPG/PNG/WebP：使用 Qt 的 SVG 渲染能力将 SVG 渲染为位图后导出。
- JPG/PNG/WebP -> SVG：不做矢量化（复杂），而是把位图以 base64 方式嵌入到 SVG 的 `<image>` 中，仍然是合法的 SVG 文件。
