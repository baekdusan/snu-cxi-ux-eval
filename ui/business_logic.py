"""
비즈니스 로직 함수들
"""
import os
import json
import datetime
from PIL import Image
from typing import List, Dict, Any, Optional
import gradio as gr

from agents.dr_generator_agent import create_dr_generator_agent
from agents.evaluator_agent import create_evaluator_agent
from agents.final_report_agent import FinalReportAgent
from utils import encode_images_to_base64

# 전역 상태 변수들
vector_store_id = None
current_images = None
current_json_data = None
current_agent_name = "Text Legibility"  # 기본값을 드롭다운과 일치시킴
current_base64_images = None
current_json_output = None
current_evaluation_output = None
current_dr_agent = None
current_eval_agent = None
current_step = "initial"
downloaded_files = []
current_mode = "evaluation"
final_report_agent = None
current_api_key = None  # 사용자가 입력한 API 키

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
    
    # API 키 확인
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
    
    # API 키 확인
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
    return f"캐시된 이미지: {cached_images_count}개 ({images_status})\\nBase64 이미지 캐시: {base64_status}\\n{mode_status}"

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
    """평가 결과를 JSON 파일로 다운로드"""
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
        
        actual_file_path = save_result_to_file(evaluation_result, "evaluation", current_agent_name, False, "")
        
        if actual_file_path and actual_file_path not in downloaded_files:
            downloaded_files.append(actual_file_path)
            print(f"새 파일 추가: {actual_file_path}")
        
        return downloaded_files
    except Exception as e:
        print(f"JSON 다운로드 파일 생성 오류: {e}")
        return None

def save_discussion_dialog():
    """Final Report 대화 내용을 파일로 저장"""
    global final_report_agent
    
    if not final_report_agent or not final_report_agent.conversation_history:
        return "❌ 저장할 대화 내용이 없습니다."
    
    try:
        # 출력 디렉터리 생성
        output_dir = "output/final_discussions"
        os.makedirs(output_dir, exist_ok=True)
        
        # 파일명 생성 (타임스탬프 포함)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"final_discussion_{timestamp}.json"
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
        
        # JSON 파일로 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(discussion_data, f, ensure_ascii=False, indent=2)
        
        print(f"대화 내용 저장 완료: {file_path}")
        return f"✅ 대화 내용이 저장되었습니다: {filename}"
        
    except Exception as e:
        print(f"대화 내용 저장 오류: {e}")
        return f"❌ 대화 내용 저장 중 오류 발생: {str(e)}"