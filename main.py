import base64
from typing import Optional

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


MAX_IMAGE_SIZE = 10 * 1024 * 1024


@register(
    "astrbot_plugin_img_ocr",
    "zhist",
    "图片OCR识别插件，支持多种OCR服务商",
    "1.0.0"
)
class ImageOCRPlugin(Star):
    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        timeout = aiohttp.ClientTimeout(total=120, connect=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
        logger.info("[OCR] 图片OCR识别插件初始化完成")

    async def terminate(self):
        if self.session and not self.session.closed:
            await self.session.close()
        logger.info("[OCR] 图片OCR识别插件已卸载")

    async def _get_image_bytes(self, image_url: str) -> Optional[bytes]:
        if image_url.startswith(("http://", "https://")):
            try:
                async with self.session.get(image_url) as resp:
                    if resp.status == 200:
                        image_bytes = await resp.read()
                        if len(image_bytes) > MAX_IMAGE_SIZE:
                            logger.error(f"[OCR] 图片过大: {len(image_bytes)} bytes")
                            return None
                        return image_bytes
                    else:
                        logger.error(f"[OCR] 下载图片失败，状态码: {resp.status}")
                        return None
            except Exception as e:
                logger.error(f"[OCR] 下载图片失败: {e}")
                return None
        else:
            try:
                with open(image_url, "rb") as f:
                    image_bytes = f.read()
                if len(image_bytes) > MAX_IMAGE_SIZE:
                    logger.error(f"[OCR] 图片过大: {len(image_bytes)} bytes")
                    return None
                return image_bytes
            except Exception as e:
                logger.error(f"[OCR] 读取本地图片失败: {e}")
                return None

    async def _ocr_ocrspace(self, image_bytes: bytes) -> str:
        use_free = self.config.get("ocrspace_use_free", True)
        if use_free:
            api_key = "helloworld"
        else:
            api_key = self.config.get("ocrspace_apikey", "") or "helloworld"
        
        image_base64 = base64.b64encode(image_bytes).decode()
        
        data = {
            "base64Image": f"data:image/png;base64,{image_base64}",
            "language": self._get_ocrspace_language(),
            "isOverlayRequired": "false",
            "apikey": api_key,
        }
        
        try:
            async with self.session.post(
                "https://api.ocr.space/parse/image",
                data=data
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("OCRExitCode") == 1:
                        parsed = result.get("ParsedResults", [])
                        if parsed:
                            return parsed[0].get("ParsedText", "")
                    err_msg = result.get("ErrorMessage", "未知错误")
                    return f"OCR识别失败: {err_msg}"
                return f"API请求失败，状态码: {resp.status}"
        except Exception as e:
            return f"OCR请求异常: {e}"

    def _get_ocrspace_language(self) -> str:
        lang_map = {"chs": "chs", "eng": "eng", "jpn": "jpn", "kor": "kor"}
        return lang_map.get(self.config.get("language", "chs"), "chs")

    async def _ocr_baidu(self, image_bytes: bytes) -> str:
        api_key = self.config.get("baidu_apikey", "")
        secret_key = self.config.get("baidu_secretkey", "")
        
        if not api_key or not secret_key:
            return "百度OCR未配置API Key和Secret Key"
        
        try:
            async with self.session.post(
                f"https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={api_key}&client_secret={secret_key}"
            ) as resp:
                if resp.status != 200:
                    return f"获取百度Token失败，状态码: {resp.status}"
                token_data = await resp.json()
                access_token = token_data.get("access_token")
                if not access_token:
                    return "获取百度Token失败"
                
                image_base64 = base64.b64encode(image_bytes).decode()
                lang_map = {"chs": "CHN_ENG", "eng": "ENG", "jpn": "JAP", "kor": "KOR"}
                language_type = lang_map.get(self.config.get("language", "chs"), "CHN_ENG")
                
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                async with self.session.post(
                    f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={access_token}",
                    data={"image": image_base64, "language_type": language_type},
                    headers=headers
                ) as ocr_resp:
                    if ocr_resp.status == 200:
                        result = await ocr_resp.json()
                        words_list = result.get("words_result", [])
                        if words_list:
                            texts = [item.get("words", "") for item in words_list]
                            return "\n".join(texts)
                        return "未识别到文字"
                    return f"百度OCR请求失败，状态码: {ocr_resp.status}"
        except Exception as e:
            return f"百度OCR请求异常: {e}"

    async def _ocr_tencent(self, image_bytes: bytes) -> str:
        secret_id = self.config.get("tencent_secretid", "")
        secret_key = self.config.get("tencent_secretkey", "")
        
        if not secret_id or not secret_key:
            return "腾讯云OCR未配置SecretId和SecretKey"
        
        try:
            import hmac
            import hashlib
            import time
            from datetime import datetime
            
            image_base64 = base64.b64encode(image_bytes).decode()
            host = "ocr.tencentcloudapi.com"
            endpoint = "ocr.tencentcloudapi.com"
            service = "ocr"
            action = "GeneralAccurateOCR"
            version = "2018-11-19"
            region = "ap-beijing"
            
            payload = '{"ImageBase64":"' + image_base64 + '"}'
            
            now = int(time.time())
            date = datetime.utcfromtimestamp(now).strftime("%Y-%m-%d")
            
            def sha256_hex(s):
                return hashlib.sha256(s.encode("utf-8")).hexdigest()
            
            http_request_method = "POST"
            canonical_uri = "/"
            canonical_querystring = ""
            ct = "application/json"
            canonical_headers = f"content-type:{ct}\nhost:{host}\n"
            signed_headers = "content-type;host"
            hashed_request_payload = sha256_hex(payload)
            canonical_request = f"{http_request_method}\n{canonical_uri}\n{canonical_querystring}\n{canonical_headers}\n{signed_headers}\n{hashed_request_payload}"
            
            algorithm = "TC3-HMAC-SHA256"
            credential_scope = f"{date}/{service}/tc3_request"
            hashed_canonical_request = sha256_hex(canonical_request)
            string_to_sign = f"{algorithm}\n{now}\n{credential_scope}\n{hashed_canonical_request}"
            
            def hmac_sha256(key, msg):
                return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()
            
            secret_date = hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
            secret_service = hmac_sha256(secret_date, service)
            secret_signing = hmac_sha256(secret_service, "tc3_request")
            signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
            
            authorization = f"{algorithm} Credential={secret_id}/{credential_scope}, SignedHeaders={signed_headers}, Signature={signature}"
            
            headers = {
                "Authorization": authorization,
                "Content-Type": ct,
                "Host": host,
                "X-TC-Action": action,
                "X-TC-Timestamp": str(now),
                "X-TC-Version": version,
                "X-TC-Region": region,
            }
            
            async with self.session.post(
                f"https://{endpoint}",
                headers=headers,
                data=payload
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    text_detections = result.get("Response", {}).get("TextDetections", [])
                    if text_detections:
                        texts = [item.get("DetectedText", "") for item in text_detections]
                        return "\n".join(texts)
                    return "未识别到文字"
                return f"腾讯云OCR请求失败，状态码: {resp.status}"
        except Exception as e:
            return f"腾讯云OCR请求异常: {e}"

    async def _do_ocr(self, image_bytes: bytes, provider: str = None) -> str:
        provider = provider or self.config.get("default_provider", "ocrspace")
        
        providers = {
            "ocrspace": self._ocr_ocrspace,
            "baidu": self._ocr_baidu,
            "tencent": self._ocr_tencent,
        }
        
        ocr_func = providers.get(provider)
        if not ocr_func:
            return f"不支持的OCR服务商: {provider}"
        
        return await ocr_func(image_bytes)

    @filter.llm_tool(name="ocr_image")
    async def ocr_image(self, event: AstrMessageEvent, image_url: str, provider: str = None) -> str:
        """识别图片中的文字内容。

        Args:
            image_url(string): 图片地址（支持本地路径和网络URL）
            provider(string): OCR服务商，可选值：ocrspace、baidu、tencent。不填使用默认配置
        """
        image_bytes = await self._get_image_bytes(image_url)
        if not image_bytes:
            return "无法获取图片内容"
        
        result = await self._do_ocr(image_bytes, provider)
        return result if result else "未识别到文字"
