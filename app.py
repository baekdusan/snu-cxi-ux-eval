"""
Samsung MX UI Analytics System - 메인 애플리케이션
"""
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="gradio")

import os
import gradio as gr
from prompts.prompt_loader import SimplePromptLoader
from config import validate_api_key, AVAILABLE_MODELS

# UI 모듈 임포트
from ui.components import (
    create_image_upload_section, create_agent_selector, create_control_buttons,
    create_cache_status_display, create_clear_confirm_dialog,
    create_evaluation_mode, create_final_report_mode, update_image_preview
)
from ui.business_logic import (
    set_vector_store_id, run_dr_generation, confirm_dr_generation, 
    generate_evaluation, get_cache_status, switch_to_final_report_mode,
    switch_to_evaluation_mode, send_final_report_message, clear_final_report_chat,
    download_evaluation_json, save_discussion_dialog, ensure_vector_store_with_api_key
)

# 벡터 스토어 초기화 (캐시에서 직접 로드)
import json
from pathlib import Path

try:
    cache_file = Path(".vector_store_cache.json")
    if cache_file.exists():
        with open(cache_file, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
            vector_store_id = cache_data.get('vector_store_id')
            if vector_store_id:
                set_vector_store_id(vector_store_id)
                print(f"[INIT] 캐시에서 vector_store_id 로드: {vector_store_id}")
            else:
                print("[INIT] 캐시에 vector_store_id 없음")
                vector_store_id = None
    else:
        print("[INIT] 벡터스토어 캐시 파일 없음")
        vector_store_id = None
except Exception as e:
    print(f"[INIT] vector store cache load failed: {e}")
    vector_store_id = None

# 버튼 상태 관리 함수들
def get_button_states():
    """현재 단계에 따른 버튼 상태 반환"""
    from ui.business_logic import current_step, is_model_locked, get_current_model
    
    # 🤖 모델 잠금 상태 반영
    model_locked = is_model_locked()
    current_model = get_current_model()
    
    # 모델 드롭다운 라벨 동적 변경
    if model_locked:
        model_label = f"🤖 {current_model} 🔒"
    else:
        model_label = "🤖 모델 선택"
    
    base_states = {
        "model_dropdown": not model_locked,
        "model_label": model_label
    }
    
    if current_step == "initial":
        return {
            **base_states,
            "agent_dropdown": True, "initial_extract_btn": True,
            "feedback_extract_btn": False, "confirm_dr_btn": False,
            "guideline_btn": False, "evaluation_feedback_btn": False,
            "download_btn": False
        }
    elif current_step in ["generated", "feedback"]:
        return {
            **base_states,
            "agent_dropdown": False, "initial_extract_btn": False,
            "feedback_extract_btn": True, "confirm_dr_btn": True,
            "guideline_btn": False, "evaluation_feedback_btn": False,
            "download_btn": False
        }
    elif current_step == "evaluated":
        return {
            **base_states,
            "agent_dropdown": False, "initial_extract_btn": False,
            "feedback_extract_btn": False, "confirm_dr_btn": False,
            "guideline_btn": True, "evaluation_feedback_btn": True,
            "download_btn": True
        }
    else:
        return {
            **base_states,
            "agent_dropdown": True, "initial_extract_btn": True,
            "feedback_extract_btn": False, "confirm_dr_btn": False,
            "guideline_btn": False, "evaluation_feedback_btn": False,
            "download_btn": False
        }

def update_button_states():
    """버튼 상태 업데이트"""
    states = get_button_states()
    return (
        gr.update(interactive=states["agent_dropdown"]), 
        gr.update(interactive=states["initial_extract_btn"]),
        gr.update(interactive=states["feedback_extract_btn"]),
        gr.update(interactive=states["confirm_dr_btn"]),
        gr.update(interactive=states["guideline_btn"]),
        gr.update(interactive=states["evaluation_feedback_btn"]),
        gr.update(interactive=states["download_btn"]),
        gr.update(interactive=states["model_dropdown"], label=states["model_label"])  # 🤖 모델 드롭다운 상태 + 라벨
    )

def check_json_and_update_confirm_btn(json_input):
    """JSON textbox 값에 따라 DR 확정 버튼 상태 업데이트"""
    has_json = json_input and json_input.strip() != ""
    return gr.update(interactive=has_json)

def show_clear_confirm():
    return gr.update(visible=True)

def hide_clear_confirm():
    return gr.update(visible=False)

def clear_conversation():
    """대화 기록 초기화"""
    from ui.business_logic import (
        current_dr_agent, current_eval_agent, current_images, current_json_data,
        current_base64_images, current_json_output, current_evaluation_output,
        current_step
    )
    
    # 에이전트 정리
    if current_dr_agent:
        try:
            current_dr_agent.clear_json_cache()
        except Exception as e:
            print(f"DR 에이전트 완전 정리 오류: {e}")
            
    if current_eval_agent:
        try:
            current_eval_agent.clear_json_cache()
        except Exception as e:
            print(f"Evaluator 에이전트 완전 정리 오류: {e}")
    
    # 전역 변수들 초기화
    import ui.business_logic as bl
    bl.current_images = None
    bl.current_json_data = None
    bl.current_base64_images = None
    bl.current_json_output = None
    bl.current_evaluation_output = None
    bl.current_dr_agent = None
    bl.current_eval_agent = None
    bl.current_step = "initial"
    
    # 🔒 보안: API key 완전 초기화 (Hugging Face 등 공유 환경에서 중요)
    bl.clear_api_key()
    
    print("=== 모든 캐시 및 API key 완전 초기화 (보안) ===")
    return "", [], "", "", "", gr.update(visible=False), gr.update(interactive=True)

def on_agent_change(selected_agent):
    """에이전트 변경 시 필요한 초기화"""
    import ui.business_logic as bl
    
    # 에이전트가 실제로 변경된 경우만 초기화
    if bl.current_agent_name != selected_agent:
        print(f"=== 에이전트 변경: {bl.current_agent_name} → {selected_agent} ===")
        
        # 기존 에이전트 완전 정리
        if bl.current_dr_agent:
            try:
                bl.current_dr_agent.reset_conversation()
                del bl.current_dr_agent
            except Exception as e:
                print(f"DR 에이전트 리소스 정리 오류: {e}")
                
        if bl.current_eval_agent:
            try:
                bl.current_eval_agent.reset_conversation()
                del bl.current_eval_agent
            except Exception as e:
                print(f"Evaluator 에이전트 리소스 정리 오류: {e}")
        
        # 상태 변수 완전 초기화
        bl.current_agent_name = selected_agent
        bl.current_json_output = None
        bl.current_evaluation_output = None
        bl.current_dr_agent = None
        bl.current_eval_agent = None
        bl.current_step = "initial"
        bl.current_json_data = None  # JSON 데이터도 초기화
        
        print(f"=== 에이전트 변경 완료: {selected_agent} (이미지 캐시 유지) ===")
    else:
        print(f"=== 동일한 에이전트 선택됨: {selected_agent} ===")
    
    return gr.update(value=""), gr.update(value="")

def after_download_reset():
    print("=== 다운로드 완료 - agent_dropdown 활성화 ===")
    return gr.update(interactive=True)

def check_final_report_btn():
    from ui.business_logic import downloaded_files
    has_files = len(downloaded_files) > 0
    return gr.update(interactive=has_files)

def validate_and_update_api_key(api_key):
    """API 키 유효성 검증 및 상태 업데이트"""
    import ui.business_logic as bl
    
    if not api_key.strip():
        # 🔒 보안: 빈 키 입력 시 기존 API 키 완전 정리
        bl.clear_api_key()
        return gr.update(interactive=False)
    
    is_valid, message = validate_api_key(api_key.strip())
    
    if is_valid:
        # 🔒 보안: API 키를 안전하게 저장 (타임스탬프와 함께)
        bl.set_api_key(api_key.strip())
        
        # 벡터스토어 확인 및 필요시 생성
        vs_id = ensure_vector_store_with_api_key(api_key.strip())
        if vs_id:
            print(f"✅ API 키 유효 (벡터스토어: {vs_id[:20]}...)")
        else:
            print("✅ API 키 유효 (벡터스토어 생성 실패)")
        
        return gr.update(interactive=True)
    else:
        # 🔒 보안: 잘못된 키 입력 시 기존 API 키 완전 정리
        print(f"❌ API 키 검증 실패: {message}")
        bl.clear_api_key()
        return gr.update(interactive=False)

def get_system_status():
    """📊 종합 시스템 상태 반환 (API + 캐시 + 모드)"""
    from ui.business_logic import current_images, current_base64_images, current_mode, current_api_key, api_key_timestamp, is_model_locked, get_current_model
    import time
    import datetime
    
    # API 키 상태 체크 (조용한 확인)
    if current_api_key:
        print(f"✅ API 키 활성: {current_api_key[:10]}... ({datetime.datetime.fromtimestamp(api_key_timestamp).strftime('%H:%M:%S')})")
    else:
        print("⚠️ API 키 미설정")
    
    # 이미지 캐시 상태
    cached_images_count = len(current_images) if current_images else 0
    base64_status = "있음" if current_base64_images else "없음"
    images_status = "있음" if current_images else "없음"
    
    # API 키 상태
    if current_api_key and api_key_timestamp:
        elapsed_hours = (time.time() - api_key_timestamp) / 3600
        if elapsed_hours < 2:  # 2시간 미만
            api_status = f"✅ 인증됨 ({2 - elapsed_hours:.1f}시간 남음)"
        else:
            api_status = "⏰ 타임아웃됨"
    else:
        api_status = "❌ 미인증"
    
    # 모델 상태
    current_model = get_current_model()
    if is_model_locked():
        model_status = f"🔒 {current_model} (잠금됨)"
    else:
        model_status = f"🤖 {current_model}"
    
    # 현재 모드
    mode_status = f"📍 {current_mode} 모드"
    
    status_text = f"🔑 API: {api_status}\n{model_status}\n{mode_status}\n📁 이미지 캐시: {cached_images_count}개 ({images_status}), Base64: {base64_status}"
    
    return status_text

def update_model_selection(selected_model):
    """🤖 모델 선택 업데이트"""
    import ui.business_logic as bl
    
    success, message = bl.set_current_model(selected_model)
    
    if success:
        print(f"🤖 {message}")
        return gr.update()  # 변경 없음 (성공 시)
    else:
        print(f"⚠️ {message}")
        # 잠금된 경우 이전 모델로 되돌리기
        current = bl.get_current_model()
        return gr.update(value=current)

# 🔒 보안: Hugging Face Spaces에서 앱 시작 시 모든 상태 초기화
print("🔒 보안: 앱 시작 - 모든 상태 초기화")
import ui.business_logic as bl
bl.clear_api_key()

# Gradio 인터페이스 정의  
demo = gr.Blocks(theme=gr.themes.Soft(), title="[SNU x CXI] Mobile App UX Evaluation System")

with demo:
    # 🎨 헤더 섹션 (타이틀 + API 설정 + 모델 선택)
    with gr.Row():
        with gr.Column(scale=4):
            gr.Markdown("# [SNU x CXI] Mobile App UX Evaluation System")
            gr.Markdown("스크린샷을 업로드하고 평가 모듈을 선택하세요!")
        with gr.Column(scale=1):
            # 🔑 API 설정 섹션 (헤더에 배치)
            api_key_input = gr.Textbox(
                label="OpenAI API Key", 
                type="password",
                placeholder="sk-...",
            )

        with gr.Column(scale=1):
            model_dropdown = gr.Dropdown(
                choices=AVAILABLE_MODELS,
                value="gpt-4o",
                label="🤖 모델 선택",
                interactive=True
            )

    with gr.Row():
        with gr.Column(scale=1):
            # 📊 종합 시스템 모니터링 (맨 위 배치)
            system_status = gr.Textbox(
                label="📊 시스템 상태",
                value="시스템 초기화 중...",
                interactive=False,
                lines=4
            )
            
            # 시스템 제어 버튼들
            with gr.Row():
                cache_status_btn = gr.Button("상태 새로고침", variant="secondary")
                clear_btn = gr.Button("초기화", variant="stop", interactive=True)
            
            # 초기화 확인 다이얼로그
            clear_confirm_row, clear_confirm_text, clear_confirm_btn, clear_cancel_btn = create_clear_confirm_dialog()            
            
            # 이미지 업로드 및 에이전트 선택
            images_input, image_preview = create_image_upload_section()
            agent_dropdown = create_agent_selector()
            
            # DR 생성 버튼
            initial_extract_btn = gr.Button("📋 DR 생성", variant="primary", interactive=False)
            


        # 메인 작업 영역
        with gr.Column(scale=4):
            # 평가 모드
            evaluation_components = create_evaluation_mode()
            (evaluation_mode, json_output, user_feedback, feedback_extract_btn, 
             confirm_dr_btn, guideline_output, evaluation_feedback, 
             evaluation_feedback_btn, download_btn) = evaluation_components

            # Final Report 모드
            final_report_components = create_final_report_mode()
            (final_report_mode, final_report_chat, final_report_input, 
             final_report_send_btn, back_to_evaluation_btn, save_discussion_btn, clear_chat_btn) = final_report_components
            
            # 최종 논의 시작 버튼 (모든 평가 완료 후)
            final_report_btn = gr.Button("🚀 최종 평가 결과 논의 시작", variant="primary", interactive=False, size="lg")

    # 이벤트 연결
    # API 키 검증 (시스템 상태 및 버튼 상태 업데이트)
    api_key_input.change(
        fn=validate_and_update_api_key,
        inputs=[api_key_input],
        outputs=[initial_extract_btn]
    ).then(
        fn=update_button_states,
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, clear_btn, model_dropdown]
    ).then(
        fn=get_system_status,
        outputs=[system_status]
    )
    
    # 🤖 모델 선택 (잠금 시 이전 값으로 되돌림)
    model_dropdown.change(
        fn=update_model_selection,
        inputs=[model_dropdown],
        outputs=[model_dropdown]
    )
    
    # 이미지 업로드
    images_input.change(
        fn=update_image_preview,
        inputs=[images_input],
        outputs=[image_preview]
    )
    
    # DR 생성
    initial_extract_btn.click(
        fn=run_dr_generation,
        inputs=[images_input, agent_dropdown],
        outputs=[json_output]
    ).then(
        fn=update_button_states,
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, model_dropdown]
    )
    
    # DR 피드백 반영
    feedback_extract_btn.click(
        fn=run_dr_generation,
        inputs=[images_input, agent_dropdown, user_feedback],
        outputs=[json_output]
    ).then(
        fn=lambda: "",
        outputs=[user_feedback]
    ).then(
        fn=update_button_states,
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, model_dropdown]
    )
    
    # DR 확정 및 평가 생성
    confirm_dr_btn.click(
        fn=confirm_dr_generation,
        inputs=[images_input, agent_dropdown, user_feedback, json_output],
        outputs=[json_output, json_output]
    ).then(
        fn=generate_evaluation,
        inputs=[images_input, json_output, agent_dropdown],
        outputs=[guideline_output]
    ).then(
        fn=update_button_states,
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, model_dropdown]
    )
    
    # 평가 피드백 반영
    evaluation_feedback_btn.click(
        fn=generate_evaluation,
        inputs=[images_input, json_output, agent_dropdown, evaluation_feedback],
        outputs=[guideline_output]
    ).then(
        fn=lambda: "",
        outputs=[evaluation_feedback]
    ).then(
        fn=update_button_states,
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, model_dropdown]
    )
    
    # 다운로드
    download_btn.click(
        fn=download_evaluation_json,
        outputs=[gr.File(label="평가 모듈별 UX 문제 다운로드", file_count="multiple")]
    ).then(
        fn=after_download_reset,
        outputs=[agent_dropdown]
    ).then(
        fn=check_final_report_btn,
        outputs=[final_report_btn]
    )
    
    # 에이전트 변경
    agent_dropdown.change(
        fn=on_agent_change,
        inputs=[agent_dropdown],
        outputs=[json_output, guideline_output]
    ).then(
        fn=update_button_states,
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, model_dropdown]
    )
    
    # JSON 변경 시 DR 확정 버튼 업데이트
    json_output.change(
        fn=check_json_and_update_confirm_btn,
        inputs=[json_output],
        outputs=[confirm_dr_btn]
    )
    
    # 초기화 관련
    clear_btn.click(fn=show_clear_confirm, outputs=[clear_confirm_row])
    clear_confirm_btn.click(
        fn=clear_conversation,
        outputs=[json_output, image_preview, user_feedback, guideline_output, evaluation_feedback, clear_confirm_row, json_output]
    ).then(
        fn=update_button_states,
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, clear_btn, model_dropdown]
    ).then(
        fn=get_system_status,
        outputs=[system_status]
    )
    clear_cancel_btn.click(fn=hide_clear_confirm, outputs=[clear_confirm_row])
    
    # 📊 시스템 상태 새로고침
    cache_status_btn.click(fn=get_system_status, outputs=[system_status])
    
    # Final Report 모드 전환
    final_report_btn.click(
        fn=switch_to_final_report_mode,
        outputs=[system_status, evaluation_mode, final_report_mode, final_report_chat, final_report_input, final_report_send_btn, back_to_evaluation_btn, save_discussion_btn]
    )
    
    # Final Report 메시지 전송
    final_report_send_btn.click(
        fn=send_final_report_message,
        inputs=[final_report_input, final_report_chat],
        outputs=[final_report_chat, final_report_input]
    )
    final_report_input.submit(
        fn=send_final_report_message,
        inputs=[final_report_input, final_report_chat],
        outputs=[final_report_chat, final_report_input]
    )
    
    # 🌟 대화 내용 저장 (HF Spaces 호환)
    save_discussion_btn.click(
        fn=save_discussion_dialog,
        outputs=[system_status, gr.File(label="Final Report 대화 내용 다운로드")]
    )
    
    # 평가 모드로 돌아가기
    back_to_evaluation_btn.click(
        fn=switch_to_evaluation_mode,
        outputs=[system_status, evaluation_mode, final_report_mode, final_report_chat, final_report_input, final_report_send_btn, back_to_evaluation_btn, save_discussion_btn]
    )
    
    # 대화 초기화
    clear_chat_btn.click(
        fn=clear_final_report_chat,
        outputs=[final_report_chat, system_status]
    )
    
    # 초기 상태 설정
    demo.load(fn=get_system_status, outputs=[system_status])
    demo.load(
        fn=update_button_states,
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, clear_btn, model_dropdown]
    )
    
    # 🔒 보안: 브라우저 새로고침 시 API 키 정리 (F5 보안 문제 해결)
    # 주의: 너무 자주 호출되지 않도록 조건부 정리
    demo.load(
        fn=lambda: bl.clear_api_key() if bl.current_api_key else None,
        outputs=[]
    )

    
    # 드롭다운 기본값과 current_agent_name 동기화
    demo.load(
        fn=lambda: "Text Legibility",  # 드롭다운 기본값 명시적 설정
        outputs=[agent_dropdown]
    )

# 애플리케이션 실행
if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",  # 허깅페이스 스페이스용
        server_port=7860,
        share=False,  # 허깅페이스에서는 share=False
        debug=False,
        show_error=True,
        quiet=True,
        max_threads=4
    )