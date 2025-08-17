import base64
import io
from typing import List, Union
from PIL import Image
import hashlib

# 이미지 캐시 (메모리 기반)
_image_cache = {}

def encode_image_to_base64(image: Image.Image) -> str:
    """이미지를 base64로 인코딩 (캐시 적용)"""
    if image is None:
        print("encode_image_to_base64: 이미지가 None입니다")
        return None
    
    try:
        # 이미지 해시 생성 (캐시 키)
        image_bytes = io.BytesIO()
        image.save(image_bytes, format="PNG")
        image_hash = hashlib.md5(image_bytes.getvalue()).hexdigest()
        
        # 캐시에 있으면 반환
        if image_hash in _image_cache:
            print(f"encode_image_to_base64: 캐시에서 이미지 반환 (해시: {image_hash[:8]}...)")
            return _image_cache[image_hash]
        
        # 없으면 인코딩하고 캐시에 저장
        base64_image = base64.b64encode(image_bytes.getvalue()).decode('utf-8')
        result = f"data:image/png;base64,{base64_image}"
        _image_cache[image_hash] = result
        
        print(f"encode_image_to_base64: 새 이미지 인코딩 완료 (해시: {image_hash[:8]}..., 길이: {len(result)})")
        return result
    except Exception as e:
        print(f"이미지 인코딩 오류: {e}")
        return None

def encode_images_to_base64(images: Union[Image.Image, List[Image.Image]]) -> Union[str, List[str]]:
    """단일 이미지 또는 이미지 리스트를 base64로 인코딩"""
    if images is None:
        return None
    
    try:
        if isinstance(images, Image.Image):
            return encode_image_to_base64(images)
        elif isinstance(images, list):
            encoded_images = []
            for img in images:
                if img is not None and hasattr(img, 'save'):  # PIL Image인지 확인
                    encoded = encode_image_to_base64(img)
                    if encoded:
                        encoded_images.append(encoded)
            return encoded_images
        else:
            raise ValueError("images must be PIL.Image or list of PIL.Image")
    except Exception as e:
        print(f"이미지 인코딩 오류: {e}")
        return None

def clear_image_cache():
    """이미지 캐시 초기화"""
    global _image_cache
    _image_cache.clear()

def get_cache_info():
    """캐시 정보 반환"""
    return {
        "cached_images": len(_image_cache),
        "cache_keys": list(_image_cache.keys())
    } 