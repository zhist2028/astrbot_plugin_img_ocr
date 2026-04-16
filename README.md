# astrbot_plugin_img_ocr

AstrBot 图片OCR识别插件，为AI提供图片文字识别能力。

## 功能

- 暴露 `ocr_image` 函数给AI调用
- 支持本地图片和网络图片URL
- 支持多种OCR服务商

## 支持的OCR服务商

| 服务商 | 免费额度 | 需注册 | 特点 |
|--------|---------|--------|------|
| OCRSpace(推荐) | 25,000次/月 | 否 | 支持中文，无需注册 |
| 百度OCR | 50,000次/天 | 是 | 中文识别精度高 |
| 腾讯云OCR | 1,000次/月 | 是 | 精度高 |

## 配置

在AstrBot管理面板中配置：

1. **default_provider**: 默认OCR服务商
2. **language**: 识别语言（中文/英文/日语/韩语）
3. **ocrspace_use_free**: 是否使用OCRSpace免费额度（开启则无需注册和填写Key）
4. **ocrspace_apikey**: OCRSpace API Key（使用免费额度时无需填写）
5. **baidu_apikey/baidu_secretkey**: 百度OCR配置（需注册）
6. **tencent_secretid/tencent_secretkey**: 腾讯云OCR配置（需注册）

## 使用

AI会自动调用 `ocr_image` 函数识别图片中的文字。

函数参数：
- `image_url`: 图片地址（本地路径或网络URL）
- `provider`: OCR服务商（可选，不填使用默认配置）

## 许可证

AGPL-3.0
