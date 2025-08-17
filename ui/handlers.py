"""
UI 이벤트 핸들러 함수들
"""
import os
import sys
import json
import datetime
from PIL import Image
from typing import List, Dict, Any, Optional

# 상위 디렉토리를 path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.dr_generator_agent import create_dr_generator_agent
from agents.evaluator_agent import create_evaluator_agent  
from agents.final_report_agent import FinalReportAgent
from utils import encode_images_to_base64

# 전역 상태 변수들
vector_store_id = None
current_images = None
current_json_data = None
current_agent_name = None
current_base64_images = None
current_json_output = None
current_evaluation_output = None
current_dr_agent = None
current_eval_agent = None
current_step = "initial"
downloaded_files = []
current_mode = "evaluation"
final_report_agent = None

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

def save_result_to_file(result_data, result_type, agent_name, is_feedback=False, feedback_text=""):
    """결과를 파일로 저장하는 공통 함수"""
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

def get_cache_status():
    """캐시 상태 정보 반환"""
    global current_images, current_base64_images, current_mode
    cached_images_count = len(current_images) if current_images else 0
    base64_status = "있음" if current_base64_images else "없음"
    images_status = "있음" if current_images else "없음"
    mode_status = f"현재 모드: {current_mode}"
    return f"캐시된 이미지: {cached_images_count}개 ({images_status})\\nBase64 이미지 캐시: {base64_status}\\n{mode_status}"

# 상태 설정 함수들
def set_vector_store_id(vs_id):
    global vector_store_id
    vector_store_id = vs_id

def get_vector_store_id():
    return vector_store_id

def get_downloaded_files():
    return downloaded_files

def add_downloaded_file(file_path):
    global downloaded_files
    if file_path and file_path not in downloaded_files:
        downloaded_files.append(file_path)

def get_current_mode():
    return current_mode

def set_current_mode(mode):
    global current_mode
    current_mode = mode

def get_final_report_agent():
    return final_report_agent

def set_final_report_agent(agent):
    global final_report_agent
    final_report_agent = agent