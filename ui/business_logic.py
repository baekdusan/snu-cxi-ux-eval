"""
비즈니스 로직 함수들
"""
import os
import json
import datetime
import time
import atexit
import tempfile
from PIL import Image
from typing import List, Dict, Any, Optional
import gradio as gr

from agents.dr_generator_agent import create_dr_generator_agent
from agents.evaluator_agent import create_evaluator_agent
from agents.final_report_agent import FinalReportAgent
from utils import encode_images_to_base64

# 🔒 세션 기반 상태 관리 (보안 강화)
session_data = {}  # 세션별 데이터 저장

# 전역 상태 변수들 (세션 무관)
vector_store_id = None

# 기본값들
DEFAULT_AGENT_NAME = "Text Legibility"
DEFAULT_MODE = "evaluation"
DEFAULT_MODEL = "gpt-4o"

def get_session_id():
    """현재 Gradio 세션 ID 가져오기"""
    try:
        import gradio as gr
        # Gradio의 현재 세션 정보를 가져오는 방법이 제한적이므로
        # 임시로 요청 기반 식별자 사용
        import time
        import hashlib
        
        # 현재 시간 기반 세션 식별 (임시 방법)
        # 실제로는 Gradio의 세션 관리 API를 사용해야 함
        current_time = str(time.time())
        session_id = hashlib.md5(current_time.encode()).hexdigest()[:8]
        return f"session_{session_id}"
    except:
        return "default_session"

def init_session_data(session_id=None):
    """세션 데이터 초기화"""
    if session_id is None:
        session_id = get_session_id()
    
    if session_id not in session_data:
        session_data[session_id] = {
            'current_images': None,
            'current_json_data': None,
            'current_agent_name': DEFAULT_AGENT_NAME,
            'current_base64_images': None,
            'current_json_output': None,
            'current_evaluation_output': None,
            'current_dr_agent': None,
            'current_eval_agent': None,
            'current_step': "initial",
            'downloaded_files': [],
            'current_mode': DEFAULT_MODE,
            'final_report_agent': None,
            'current_api_key': None,
            'api_key_timestamp': None,
            'current_model': DEFAULT_MODEL,
            'model_locked': False
        }
    return session_id

# 호환성을 위한 전역 변수들 (기본 세션 사용)
current_images = None
current_json_data = None
current_agent_name = DEFAULT_AGENT_NAME
current_base64_images = None
current_json_output = None
current_evaluation_output = None
current_dr_agent = None
current_eval_agent = None
current_step = "initial"
downloaded_files = []
current_mode = DEFAULT_MODE
final_report_agent = None
current_api_key = None  # 사용자가 입력한 API 키
api_key_timestamp = None  # API key 입력 시간 추적 (보안용)
current_model = DEFAULT_MODEL  # 현재 선택된 모델
model_locked = False  # 모델 변경 잠금 상태

# 🌟 환경 감지: Hugging Face Spaces 여부 확인
def is_hugging_face_space():
    """Hugging Face Spaces 환경인지 확인"""
    return os.getenv("SPACE_ID") is not None or os.getenv("HUGGINGFACE_HUB_CACHE") is not None

IS_HF_SPACE = is_hugging_face_space()
if IS_HF_SPACE:
    print("🌟 Hugging Face Spaces 환경 감지됨 - 클라우드 최적화 모드")
else:
    print("💻 로컬 환경 감지됨 - 로컬 파일 저장 모드")

def set_vector_store_id(vs_id):
    global vector_store_id
    vector_store_id = vs_id

def ensure_vector_store_with_api_key(api_key):
    """벡터스토어가 없으면 API 키로 새로 생성, 있으면 그대로 사용"""
    global vector_store_id
    
    # 이미 벡터스토어가 있으면 그냥 사용
    if vector_store_id:
        print(f"✅ 기존 벡터스토어 사용: {vector_store_id}")
        return vector_store_id
    
    # 벡터스토어가 없으면 API 키로 새로 생성
    try:
        from prompts.prompt_loader import SimplePromptLoader
        from config import get_openai_client
        
        loader = SimplePromptLoader()
        loader.client = get_openai_client(api_key)
        
        vs_id = loader.create_vector_store()
        if vs_id:
            vector_store_id = vs_id
            print(f"✅ 새 벡터스토어 생성 완료: {vs_id}")
            return vs_id
        else:
            print("❌ 벡터스토어 생성 실패")
            return None
    except Exception as e:
        print(f"❌ 벡터스토어 생성 오류: {e}")
        return None



def convert_files_to_images(files_input):
    """Gradio 파일 객체를 PIL Image로 변환"""
    if not files_input:
        return []
    
    images = []
    for i, file_obj in enumerate(files_input):
        try:
            print(f"파일 {i+1} 처리 중: {type(file_obj)}")
            
            # 단순화된 이미지 로드
            if hasattr(file_obj, 'name'):
                print(f"  파일명: {file_obj.name}")
                image = Image.open(file_obj.name)
                print(f"  이미지 정보: 크기={image.size}, 모드={image.mode}")
                images.append(image)
                print(f"  이미지 로드 성공: {file_obj.name}")
            else:
                print(f"  파일 객체 타입: {type(file_obj)}")
                image = Image.open(file_obj)
                print(f"  이미지 정보: 크기={image.size}, 모드={image.mode}")
                images.append(image)
                print(f"  이미지 로드 성공: {type(file_obj)}")
                
        except Exception as e:
            print(f"  이미지 변환 오류: {e}")
            continue
    
    return images

def create_temp_file_for_download(result_data, result_type, agent_name, is_feedback=False, feedback_text=""):
    """🌟 HF Spaces 호환: 임시 파일을 생성하여 다운로드 가능하게 함"""
    try:
        # 파일명 생성
        agent_name_clean = agent_name.replace(' ', '_')
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{result_type}_{agent_name_clean}_{timestamp}.json"
        
        # JSON 데이터 구성
        data = {
            "agent_type": agent_name,
            "timestamp": timestamp,
            "is_feedback": is_feedback,
            "feedback": feedback_text,
            "result": result_data
        }
        
        # 임시 파일 생성 (Gradio가 자동으로 정리함)
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.json', 
            prefix=f"{result_type}_{agent_name_clean}_",
            delete=False,
            encoding='utf-8'
        )
        
        json.dump(data, temp_file, ensure_ascii=False, indent=2)
        temp_file.close()
        
        print(f"🌟 {result_type} 임시 파일 생성: {filename}")
        return temp_file.name
        
    except Exception as e:
        print(f"❌ {result_type} 임시 파일 생성 오류: {e}")
        return None

# 기존 함수는 호환성을 위해 유지 (로컬 개발용)
def save_result_to_file(result_data, result_type, agent_name, is_feedback=False, feedback_text=""):
    """결과를 파일로 저장하는 공통 함수 (로컬 개발용, 호환성 유지)"""
    try:
        # 저장할 디렉터리 결정
        if result_type == "dr_generation":
            output_dir = "output/drgenerator"
        elif result_type == "evaluation":
            output_dir = "output/evaluator"
        else:
            raise ValueError(f"알 수 없는 결과 타입: {result_type}")
        
        # 디렉터리 생성
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        # 파일명 생성
        agent_name_clean = agent_name.replace(' ', '_')
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{result_type}_{agent_name_clean}_{timestamp}.json"
        file_path = os.path.join(output_dir, filename)
        
        # JSON 데이터 구성
        data = {
            "agent_type": agent_name,
            "timestamp": timestamp,
            "is_feedback": is_feedback,
            "feedback": feedback_text,
            "result": result_data
        }
        
        # 파일 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"{result_type} 결과 저장: {file_path}")
        return file_path
        
    except Exception as e:
        print(f"{result_type} 결과 저장 오류: {e}")
        return False

def confirm_dr_generation(images_input, selected_agent, user_feedback="", json_input=""):
    """DR 확정 버튼용 함수"""
    global current_images, current_agent_name, current_base64_images, current_json_output, current_dr_agent, current_step
    
    if not images_input:
        return "이미지를 업로드해주세요."
    
    if not selected_agent:
        return "분석할 에이전트를 선택해주세요."
    
    current_agent_name = selected_agent
    print(f"=== {selected_agent} DR 확정 시작 ===")
    
    # JSON 소스 결정
    json_to_use = None
    should_save = False
    
    if current_json_output:
        json_to_use = current_json_output
        should_save = True
        print("=== DR 확정: 기존 캐시된 결과 사용 ===")
    elif json_input and json_input.strip():
        json_to_use = json_input.strip()
        should_save = False
        print("=== DR 확정: textbox 값 사용 (저장 안함) ===")
    else:
        return "❌ DR 생성 결과가 없습니다. 먼저 DR을 생성하거나 JSON을 입력해주세요."
    
    try:
        # JSON 유효성 검사
        json.loads(json_to_use)
        
        # DR Generator 결과를 파일로 저장 (새로 생성된 경우만)
        if should_save:
            result = json.loads(json_to_use)
            is_feedback_generation = bool(user_feedback and user_feedback.strip())
            save_result_to_file(result, "dr_generation", selected_agent, is_feedback_generation, user_feedback)
            print("=== DR 결과 저장 완료 ===")
        else:
            print("=== DR 결과 저장 건너뜀 (textbox 값 사용) ===")
        
        current_step = "generated"
        
        save_status = "저장되었습니다" if should_save else "저장하지 않았습니다 (textbox 값 사용)"
        dr_message = f"=== {selected_agent} DR 확정 완료 ===\\n\\n📋 추출된 JSON:\\n{json_to_use}\\n\\n✅ DR Generator 결과가 {save_status}."
        
        return dr_message, gr.update(interactive=False)
        
    except json.JSONDecodeError as e:
        return f"❌ JSON 형식 오류: {str(e)}"
    except Exception as e:
        return f"❌ DR 확정 중 오류 발생: {str(e)}"

def run_dr_generation(images_input, selected_agent, user_feedback=""):
    """디자인 참조 생성 에이전트 실행"""
    global current_images, current_agent_name, current_base64_images, current_json_output, current_dr_agent, current_step, current_api_key
    
    # 🔒 보안: API key 타임아웃 체크
    if check_api_key_timeout():
        return "🔒 보안: API key가 타임아웃되었습니다. 다시 입력해주세요."
    
    # API 키 확인
    print(f"🐛 [DEBUG] generate_evaluation - current_api_key: {bool(current_api_key)}")
    if current_api_key:
        print(f"🐛 [DEBUG] API 키 앞 10자: {current_api_key[:10]}...")
    if not current_api_key:
        return "❌ OpenAI API 키를 먼저 입력해주세요."
    
    import time
    execution_id = f"dr_gen_{int(time.time() * 1000)}"
    print(f"=== {selected_agent} 디자인 참조 생성 시작 (ID: {execution_id}) ===")
    
    is_feedback_generation = bool(user_feedback and user_feedback.strip())
    
    if not images_input:
        return "이미지를 업로드해주세요."
    
    if not selected_agent:
        return "분석할 에이전트를 선택해주세요."
    
    current_agent_name = selected_agent
    
    # Gradio 파일 객체를 PIL Image로 변환
    images = convert_files_to_images(images_input)
    current_images = images
    
    if not images:
        return "이미지 변환에 실패했습니다."
    
    try:
        # 🤖 DR 생성 시작 시 모델 잠금
        lock_model()
        
        # 에이전트 재사용 또는 생성
        if current_dr_agent is None or current_agent_name != selected_agent:
            try:
                current_dr_agent = create_dr_generator_agent(selected_agent, vector_store_id=vector_store_id, api_key=current_api_key)
                print(f"새로운 디자인 참조 에이전트 생성: {selected_agent}")
            except Exception as e:
                print(f"DR 에이전트 생성 오류: {e}")
                return f"=== {selected_agent} DR 에이전트 생성 실패 ===\\n오류: {str(e)}"
        else:
            print("기존 디자인 참조 에이전트 재사용")
        
        # base64 이미지가 캐시되어 있지 않으면 변환
        if current_base64_images is None:
            current_base64_images = encode_images_to_base64(images)
            if not current_base64_images:
                return f"=== {selected_agent} 오류 ===\\n이미지 인코딩에 실패했습니다."
        else:
            print("캐시된 base64 이미지 재사용")
        
        # 디자인 참조 생성 실행
        result = current_dr_agent.extract_json(current_base64_images, user_feedback)
        
        if isinstance(result, dict):
            json_output = json.dumps(result, ensure_ascii=False, indent=2)
            current_json_output = json_output
            
            if is_feedback_generation:
                current_step = "feedback"
            else:
                current_step = "generated"
            
            return f"=== {selected_agent} 디자인 참조 생성 완료 ===\\n\\n📋 추출된 JSON:\\n{json_output}\\n\\n💬 추가 수정이 필요하면 피드백을 입력하거나 'DR 확정' 버튼을 클릭하세요."
        else:
            return f"=== {selected_agent} 오류 ===\\n{str(result)}"
            
    except Exception as e:
        print(f"에이전트 실행 오류 ({selected_agent}): {e}")
        return f"=== {selected_agent} 오류 ===\\n{str(e)}"

def extract_json_from_result(result_text):
    """결과 텍스트에서 JSON 부분만 추출"""
    try:
        start_idx = result_text.find('{')
        end_idx = result_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_str = result_text[start_idx:end_idx]
            json.loads(json_str)  # 파싱 테스트
            return json_str
        else:
            return None
    except Exception as e:
        print(f"JSON 추출 오류: {e}")
        return None

def generate_evaluation(images_input, json_input, selected_agent, evaluation_feedback=""):
    """평가 에이전트 실행"""
    global current_images, current_base64_images, current_json_output, current_eval_agent, current_agent_name, current_step, current_evaluation_output, current_api_key
    
    # 🔒 보안: API key 타임아웃 체크
    if check_api_key_timeout():
        return "🔒 보안: API key가 타임아웃되었습니다. 다시 입력해주세요."
    
    # API 키 확인
    print(f"🐛 [DEBUG] generate_evaluation - current_api_key: {bool(current_api_key)}")
    if current_api_key:
        print(f"🐛 [DEBUG] API 키 앞 10자: {current_api_key[:10]}...")
    if not current_api_key:
        return "❌ OpenAI API 키를 먼저 입력해주세요."
    
    is_feedback_evaluation = bool(evaluation_feedback and evaluation_feedback.strip())
    
    print(f"=== 평가 함수 호출 ===")
    print(f"selected_agent: {selected_agent}")
    print(f"current_agent_name: {current_agent_name}")
    print(f"is_feedback_evaluation: {is_feedback_evaluation}")
    
    # 캐시된 JSON 결과 사용
    if current_json_output:
        json_input = current_json_output
        print("캐시된 JSON 결과 사용")
    
    if not images_input:
        return "이미지를 업로드해주세요."
    
    if not json_input or not json_input.strip():
        return "JSON 데이터가 없습니다. 먼저 디자인 참조 생성을 실행해주세요."
    
    # selected_agent가 None이면 캐시된 에이전트 이름 사용
    if not selected_agent or selected_agent.strip() == "":
        if current_agent_name:
            selected_agent = current_agent_name
            print(f"캐시된 에이전트 이름 사용: {selected_agent}")
        else:
            return "분석할 에이전트를 선택해주세요."
    
    current_agent_name = selected_agent
    
    try:
        json_str = extract_json_from_result(json_input)
        if not json_str:
            return "JSON 데이터를 추출할 수 없습니다. 디자인 참조 생성을 다시 실행해주세요."
        
        json_data = json.loads(json_str)
        
        # base64 이미지가 캐시되어 있으면 재사용, 없으면 새로 변환
        if current_base64_images is None:
            images = convert_files_to_images(images_input)
            if not images:
                return "이미지 변환에 실패했습니다."
            
            current_base64_images = encode_images_to_base64(images)
            if not current_base64_images:
                return f"=== {selected_agent} 오류 ===\\n이미지 인코딩에 실패했습니다."
        else:
            print("캐시된 base64 이미지 재사용")
        
        # 평가 에이전트 재사용 또는 생성
        if current_eval_agent is None or current_agent_name != selected_agent:
            try:
                current_eval_agent = create_evaluator_agent(selected_agent, vector_store_id=vector_store_id, api_key=current_api_key)
                print(f"새로운 평가 에이전트 생성: {selected_agent}")
            except Exception as e:
                print(f"Evaluator 에이전트 생성 오류: {e}")
                return f"=== {selected_agent} 평가 에이전트 생성 실패 ===\\n오류: {str(e)}"
        else:
            print("기존 평가 에이전트 재사용")
        
        try:
            result = current_eval_agent.generate_guidelines(current_base64_images, json_data, evaluation_feedback)
            current_evaluation_output = result
            
            if is_feedback_evaluation:
                current_step = "evaluated"
            else:
                current_step = "evaluated"
            
            return f"=== {selected_agent} 평가 생성 완료 ===\\n\\n💡 평가 결과:\\n{result}"
        except Exception as e:
            print(f"평가 에이전트 실행 오류: {e}")
            import traceback
            print(f"상세 오류: {traceback.format_exc()}")
            return f"평가 생성 중 오류가 발생했습니다: {str(e)}"
        
    except json.JSONDecodeError:
        return "JSON 형식이 올바르지 않습니다. 디자인 참조 생성을 다시 실행해주세요."
    except Exception as e:
        print(f"평가 생성 오류 ({selected_agent}): {e}")
        return f"=== {selected_agent} 평가 생성 오류 ===\\n{str(e)}"

def get_cache_status():
    """캐시 상태 정보 반환"""
    cached_images_count = len(current_images) if current_images else 0
    base64_status = "있음" if current_base64_images else "없음"
    images_status = "있음" if current_images else "없음"
    mode_status = f"현재 모드: {current_mode}"
    
    # 🔒 보안: API key 상태 표시
    api_status = "없음"
    if current_api_key and api_key_timestamp:
        elapsed_hours = (time.time() - api_key_timestamp) / 3600
        if elapsed_hours < 2:  # 2시간 미만
            api_status = f"있음 ({2 - elapsed_hours:.1f}시간 남음)"
        else:
            api_status = "타임아웃됨"
    
    return f"캐시된 이미지: {cached_images_count}개 ({images_status})\\nBase64 이미지 캐시: {base64_status}\\n{mode_status}\\n🔒 API key: {api_status}"

# 모드 관리 함수들
def get_current_mode():
    """현재 모드 반환"""
    return current_mode

def set_current_mode(mode):
    """현재 모드 설정"""
    global current_mode
    current_mode = mode

# 🤖 모델 관리 함수들
def get_current_model():
    """현재 선택된 모델 반환"""
    return current_model

def set_current_model(model):
    """현재 모델 설정 (잠금되지 않은 경우만)"""
    global current_model, model_locked
    
    if model_locked:
        print(f"⚠️ 모델 변경 잠금됨: 현재 세션에서는 {current_model} 고정")
        return False, f"모델이 {current_model}로 잠금되어 있습니다. 세션을 초기화해야 변경 가능합니다."
    
    current_model = model
    print(f"🤖 모델 변경: {model}")
    return True, f"모델이 {model}로 변경되었습니다."

def lock_model():
    """모델 변경을 잠금 (DR 생성 시작 시 호출)"""
    global model_locked
    model_locked = True
    print(f"🔒 모델 잠금: {current_model} 고정")

def unlock_model():
    """모델 변경 잠금 해제 (초기화 시 호출)"""
    global model_locked
    model_locked = False
    print("🔓 모델 잠금 해제")

def is_model_locked():
    """모델이 잠금 상태인지 확인"""
    return model_locked

def set_api_key(api_key):
    """🔒 보안: API key 설정 (타임스탬프와 함께)"""
    global current_api_key, api_key_timestamp
    current_api_key = api_key
    api_key_timestamp = time.time()
    print(f"🔒 API key 설정됨 (시간: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")

def check_api_key_timeout(timeout_hours=2):
    """🔒 보안: API key 타임아웃 체크 (기본 2시간)"""
    global current_api_key, api_key_timestamp
    
    if not current_api_key or not api_key_timestamp:
        return False
    
    elapsed_hours = (time.time() - api_key_timestamp) / 3600
    if elapsed_hours > timeout_hours:
        print(f"🔒 보안: API key 타임아웃 ({elapsed_hours:.1f}시간 경과) - 자동 정리")
        clear_api_key()
        return True
    return False

def clear_api_key():
    """🔒 보안: API key 완전 초기화"""
    global current_api_key, api_key_timestamp, final_report_agent, current_dr_agent, current_eval_agent
    
    print("🔒 보안: API key 및 관련 에이전트 정리 시작...")
    
    # API key 초기화
    current_api_key = None
    api_key_timestamp = None
    
    # 🤖 모델 잠금 해제 (새 세션에서 모델 변경 가능)
    unlock_model()
    
    # API key를 포함한 에이전트들 정리
    if final_report_agent:
        try:
            final_report_agent.clear_all()
        except Exception as e:
            print(f"Final Report Agent 정리 오류: {e}")
        final_report_agent = None
    
    if current_dr_agent:
        try:
            current_dr_agent.clear_json_cache()
        except Exception as e:
            print(f"DR Agent 정리 오류: {e}")
        current_dr_agent = None
    
    if current_eval_agent:
        try:
            current_eval_agent.clear_json_cache()
        except Exception as e:
            print(f"Evaluator Agent 정리 오류: {e}")
        current_eval_agent = None
    
    print("🔒 보안: API key 및 관련 에이전트 정리 완료")

# 🔒 보안: 앱 종료 시 자동 정리
def cleanup_on_exit():
    """앱 종료 시 API key 자동 정리"""
    print("🔒 보안: 앱 종료 - API key 자동 정리")
    clear_api_key()

# 종료 시 정리 함수 등록
atexit.register(cleanup_on_exit)

# Final Report 모드 관련 함수들
def switch_to_final_report_mode():
    """Final Report 모드로 전환"""
    global current_mode, final_report_agent
    
    try:
        if not downloaded_files:
            return (
                "❌ 평가 결과 파일이 없습니다. 먼저 각 에이전트별 평가를 완료하고 결과를 다운로드해주세요.",
                gr.update(visible=False),
                gr.update(visible=True),
                "",
                gr.update(interactive=True),
                gr.update(interactive=True),
                gr.update(interactive=True)
            )
        
        # Final Report Agent 초기화
        if not final_report_agent:
            final_report_agent = FinalReportAgent(api_key=current_api_key)
        
        # 평가 파일들로 Agent 초기화
        initialization_result = final_report_agent.initialize_with_files(downloaded_files)
        current_mode = "final_report"
        
        # 챗봇의 첫 환영 메시지 
        welcome_message = """안녕하세요! 👋

**Final Report Agent**입니다. 평가 결과를 바탕으로 자유롭게 질문해주세요.

📊 **분석 가능한 내용**:
• 가장 심각한 UX 문제점
• 우선순위별 개선 사항  
• 각 평가 모듈별 주요 발견사항
• 구체적인 개선 방향 제시

💬 **어떤 것이 궁금하신가요?**"""

        return (
            initialization_result,
            gr.update(visible=False),
            gr.update(visible=True),
            [(None, welcome_message)],  # AI가 먼저 환영 메시지 전송
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True),
            gr.update(interactive=True)
        )
        
    except Exception as e:
        return (
            f"❌ Final Report 모드 전환 중 오류 발생: {str(e)}",
            gr.update(visible=True),
            gr.update(visible=False),
            "",
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False),
            gr.update(interactive=False)
        )

def switch_to_evaluation_mode():
    """평가 모드로 돌아가기"""
    global current_mode
    current_mode = "evaluation"
    
    return (
        "평가 모드로 돌아왔습니다.",
        gr.update(visible=True),
        gr.update(visible=False),
        [],
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False),
        gr.update(interactive=False)
    )

def send_final_report_message(user_message, current_chat_history=None):
    """Final Report Agent와 대화"""
    global final_report_agent
    
    if current_chat_history is None:
        current_chat_history = []
    
    if not final_report_agent:
        current_chat_history.append((user_message, "❌ Final Report Agent가 초기화되지 않았습니다."))
        return current_chat_history, ""
    
    if not user_message.strip():
        return current_chat_history, ""
    
    try:
        ai_response = final_report_agent.chat(user_message)
        current_chat_history.append((user_message, ai_response))
        return current_chat_history, ""
        
    except Exception as e:
        error_msg = f"❌ 응답 생성 중 오류: {str(e)}"
        current_chat_history.append((user_message, error_msg))
        return current_chat_history, ""

def clear_final_report_chat():
    """Final Report 대화 초기화"""
    global final_report_agent
    if final_report_agent:
        final_report_agent.reset_conversation()
    return [], "Final Report 대화가 초기화되었습니다."

def download_evaluation_json():
    """🌟 HF Spaces 호환: 평가 결과를 JSON 파일로 다운로드"""
    global current_evaluation_output, current_agent_name, downloaded_files
    
    if not current_evaluation_output:
        return None
    
    try:
        evaluation_result = current_evaluation_output
        try:
            if current_evaluation_output.startswith('{') and current_evaluation_output.endswith('}'):
                parsed_result = json.loads(current_evaluation_output)
                evaluation_result = parsed_result
        except:
            pass
        
        if IS_HF_SPACE:
            # 🌟 HF Spaces: 임시 파일 생성으로 즉시 다운로드 가능
            temp_file_path = create_temp_file_for_download(evaluation_result, "evaluation", current_agent_name, False, "")
            
            if temp_file_path:
                # 다운로드 이력에 추가 (Final Report용)
                if temp_file_path not in downloaded_files:
                    downloaded_files.append(temp_file_path)
                    print(f"🌟 새 평가 파일 준비 (HF Spaces): {current_agent_name}")
                
                return temp_file_path
            else:
                return None
        else:
            # 💻 로컬: 기존 방식 + 임시 파일 생성
            saved_file_path = save_result_to_file(evaluation_result, "evaluation", current_agent_name, False, "")
            temp_file_path = create_temp_file_for_download(evaluation_result, "evaluation", current_agent_name, False, "")
            
            if temp_file_path:
                # 다운로드 이력에 추가 (Final Report용 - 로컬 파일 경로 사용)
                if saved_file_path and saved_file_path not in downloaded_files:
                    downloaded_files.append(saved_file_path)
                    print(f"💻 새 평가 파일 준비 (로컬): {current_agent_name}")
                
                return temp_file_path
            else:
                return None
            
    except Exception as e:
        print(f"❌ JSON 다운로드 파일 생성 오류: {e}")
        return None

def save_discussion_dialog():
    """🌟 HF Spaces 호환: Final Report 대화 내용을 파일로 다운로드"""
    global final_report_agent
    
    if not final_report_agent or not final_report_agent.conversation_history:
        return "❌ 저장할 대화 내용이 없습니다.", None
    
    try:
        # 파일명 생성 (타임스탬프 포함)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"final_discussion_{timestamp}.json"
        
        # 💻 로컬 환경에서는 디렉터리에도 저장
        if not IS_HF_SPACE:
            output_dir = "output/final_discussions"
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, filename)
        
        # 대화 내용 구조화
        discussion_data = {
            "timestamp": timestamp,
            "total_turns": len(final_report_agent.conversation_history) // 2,  # user-assistant 쌍으로 계산
            "evaluation_files": final_report_agent.evaluation_files,
            "conversation_history": []
        }
        
        # 대화 히스토리 변환 (Responses API 형식 → 읽기 쉬운 형식)
        for i, message in enumerate(final_report_agent.conversation_history):
            if message["role"] == "user":
                content = message["content"][0]["text"] if message["content"] else ""
                discussion_data["conversation_history"].append({
                    "turn": i // 2 + 1,
                    "role": "user", 
                    "content": content
                })
            elif message["role"] == "assistant":
                content = message["content"][0]["text"] if message["content"] else ""
                discussion_data["conversation_history"].append({
                    "turn": i // 2 + 1,
                    "role": "assistant",
                    "content": content
                })
        
        # 💻 로컬 환경에서는 파일도 저장
        if not IS_HF_SPACE:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(discussion_data, f, ensure_ascii=False, indent=2)
            print(f"💻 로컬 대화 파일 저장: {file_path}")
        
        # 🌟 임시 파일 생성으로 즉시 다운로드 가능
        temp_file = tempfile.NamedTemporaryFile(
            mode='w', 
            suffix='.json', 
            prefix=f"final_discussion_{timestamp}_",
            delete=False,
            encoding='utf-8'
        )
        
        json.dump(discussion_data, temp_file, ensure_ascii=False, indent=2)
        temp_file.close()
        
        env_msg = "HF Spaces" if IS_HF_SPACE else "로컬"
        print(f"🌟 대화 내용 파일 준비 ({env_msg}): {filename}")
        return f"✅ 대화 내용이 준비되었습니다: {filename}", temp_file.name
        
    except Exception as e:
        print(f"❌ 대화 내용 파일 생성 오류: {e}")
        return f"❌ 대화 내용 저장 실패: {str(e)}", None