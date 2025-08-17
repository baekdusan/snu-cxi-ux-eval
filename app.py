"""
Samsung MX UI Analytics System - 메인 애플리케이션
"""
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="gradio")

import os
import gradio as gr
from prompts.prompt_loader import SimplePromptLoader
from config import validate_api_key

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
    download_evaluation_json, save_discussion_dialog
)

# 벡터 스토어 초기화
try:
    _loader = SimplePromptLoader()
    vector_store_id = _loader.get_vector_store_id()
    set_vector_store_id(vector_store_id)
    print(f"[INIT] vector_store_id = {vector_store_id}")
except Exception as e:
    print(f"[INIT] vector store init failed: {e}")
    vector_store_id = None

# 버튼 상태 관리 함수들
def get_button_states():
    """현재 단계에 따른 버튼 상태 반환"""
    from ui.business_logic import current_step
    
    if current_step == "initial":
        return {
            "agent_dropdown": True, "initial_extract_btn": True,
            "feedback_extract_btn": False, "confirm_dr_btn": False,
            "guideline_btn": False, "evaluation_feedback_btn": False,
            "download_btn": False
        }
    elif current_step in ["generated", "feedback"]:
        return {
            "agent_dropdown": False, "initial_extract_btn": False,
            "feedback_extract_btn": True, "confirm_dr_btn": True,
            "guideline_btn": False, "evaluation_feedback_btn": False,
            "download_btn": False
        }
    elif current_step == "evaluated":
        return {
            "agent_dropdown": False, "initial_extract_btn": False,
            "feedback_extract_btn": False, "confirm_dr_btn": False,
            "guideline_btn": True, "evaluation_feedback_btn": True,
            "download_btn": True
        }
    else:
        return {
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
        gr.update(interactive=states["download_btn"])
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
    
    print("=== 모든 캐시 완전 초기화 ===")
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
    if not api_key.strip():
        return gr.update(value="⚠️ API 키를 입력해주세요"), gr.update(interactive=False)
    
    is_valid, message = validate_api_key(api_key.strip())
    
    if is_valid:
        # UI business logic에 API 키 저장
        import ui.business_logic as bl
        bl.current_api_key = api_key.strip()
        return gr.update(value=f"✅ {message}"), gr.update(interactive=True)
    else:
        return gr.update(value=f"❌ {message}"), gr.update(interactive=False)

# Gradio 인터페이스 정의
demo = gr.Blocks(theme=gr.themes.Soft(), title="[SNU x CXI] Mobile App UX Evaluation System")

with demo:
    gr.Markdown("# [SNU x CXI] Mobile App UX Evaluation System")
    gr.Markdown("스크린샷을 업로드하고 평가 모듈을 선택하세요!")

    with gr.Row():
        with gr.Column(scale=1):
            # API 키 입력 섹션
            # gr.Markdown("### 🔑 OpenAI API 키 입력")
            api_key_input = gr.Textbox(
                label="OpenAI API Key", 
                type="password",
                placeholder="sk-...",
            )
            api_key_status = gr.Textbox(
                label="상태",
                value="⚠️ API 키를 입력해주세요",
                interactive=False
            )
            
            # 이미지 업로드 및 에이전트 선택
            images_input, image_preview = create_image_upload_section()
            agent_dropdown = create_agent_selector()
            
            # DR 생성 버튼
            initial_extract_btn = gr.Button("📋 DR 생성", variant="primary", interactive=False)
            
            # 캐시 상태 표시 박스
            cache_status = create_cache_status_display()
            
            # 나머지 제어 버튼들 
            with gr.Row():
                cache_status_btn = gr.Button("캐시 상태 조회", variant="secondary")
                clear_btn = gr.Button("초기화", variant="stop", interactive=True)
            
            # 초기화 확인 다이얼로그
            clear_confirm_row, clear_confirm_text, clear_confirm_btn, clear_cancel_btn = create_clear_confirm_dialog()

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
    # API 키 검증
    api_key_input.change(
        fn=validate_and_update_api_key,
        inputs=[api_key_input],
        outputs=[api_key_status, initial_extract_btn]
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
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn]
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
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn]
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
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn]
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
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn]
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
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn]
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
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn, clear_btn]
    )
    clear_cancel_btn.click(fn=hide_clear_confirm, outputs=[clear_confirm_row])
    
    # 캐시 상태 조회
    cache_status_btn.click(fn=get_cache_status, outputs=[cache_status])
    
    # Final Report 모드 전환
    final_report_btn.click(
        fn=switch_to_final_report_mode,
        outputs=[cache_status, evaluation_mode, final_report_mode, final_report_chat, final_report_input, final_report_send_btn, back_to_evaluation_btn, save_discussion_btn]
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
    
    # 대화 내용 저장
    save_discussion_btn.click(
        fn=save_discussion_dialog,
        outputs=[cache_status]
    )
    
    # 평가 모드로 돌아가기
    back_to_evaluation_btn.click(
        fn=switch_to_evaluation_mode,
        outputs=[cache_status, evaluation_mode, final_report_mode, final_report_chat, final_report_input, final_report_send_btn, back_to_evaluation_btn, save_discussion_btn]
    )
    
    # 대화 초기화
    clear_chat_btn.click(
        fn=clear_final_report_chat,
        outputs=[final_report_chat, cache_status]
    )
    
    # 초기 상태 설정
    demo.load(fn=get_cache_status, outputs=[cache_status])
    demo.load(
        fn=lambda: (
            gr.update(interactive=True), gr.update(interactive=True), 
            gr.update(interactive=False), gr.update(interactive=False),
            gr.update(interactive=False), gr.update(interactive=False)
        ),
        outputs=[agent_dropdown, initial_extract_btn, feedback_extract_btn, confirm_dr_btn, evaluation_feedback_btn, download_btn]
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