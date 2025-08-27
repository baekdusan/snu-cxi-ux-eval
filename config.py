"""
설정 관리 모듈
"""
import os
from openai import OpenAI

# 기타 설정들
DEFAULT_MODEL = "gpt-4o"
MAX_IMAGES_PER_REQUEST = 10
VECTOR_INDEXING_WAIT_TIME = 3  # 초

def get_openai_client(api_key=None):
    """
    OpenAI 클라이언트 생성
    
    Args:
        api_key (str, optional): 사용자가 입력한 API 키. 없으면 환경변수에서 가져옴
    
    Returns:
        OpenAI: OpenAI 클라이언트 객체
        
    Raises:
        ValueError: API 키가 제공되지 않은 경우
    """
    if api_key:
        return OpenAI(api_key=api_key)
    
    # 환경변수에서 API 키 확인 (로컬 개발용)
    env_api_key = os.getenv("OPENAI_API_KEY")
    if env_api_key:
        return OpenAI(api_key=env_api_key)
    
    raise ValueError("OpenAI API 키가 필요합니다. API 키를 입력해주세요.")

def get_current_model():
    """현재 선택된 모델 반환 (business_logic에서 가져옴)"""
    try:
        from ui.business_logic import get_current_model
        return get_current_model()
    except ImportError:
        return DEFAULT_MODEL

# 사용 가능한 모델 목록
AVAILABLE_MODELS = [
    "gpt-4o",
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano"
]

def validate_api_key(api_key):
    """
    API 키 유효성 검증
    
    Args:
        api_key (str): 검증할 API 키
        
    Returns:
        tuple: (is_valid, error_message)
    """
    if not api_key:
        return False, "API 키를 입력해주세요."
    
    if not api_key.startswith("sk-"):
        return False, "유효하지 않은 API 키 형식입니다. 'sk-'로 시작해야 합니다."
    
    try:
        client = OpenAI(api_key=api_key)
        # 간단한 API 호출로 키 유효성 확인
        client.models.list()
        return True, "API 키가 유효합니다."
    except Exception as e:
        return False, f"API 키 검증 실패: {str(e)}"