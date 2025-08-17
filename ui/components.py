"""
UI 컴포넌트 관리
"""
import gradio as gr
from PIL import Image
import numpy as np

def create_image_upload_section():
    """이미지 업로드 섹션 생성"""
    with gr.Group():
        # 이미지 업로드 (여러 장 지원)
        images_input = gr.File(
            file_count="multiple",
            file_types=[".jpg", ".jpeg", ".png", ".bmp", ".gif"],
            label="Image",
            height=100,
            show_label=True,
            container=True,
            scale=1,
            min_width=100,
            interactive=True
        )
        
        # 이미지 프리뷰 갤러리
        image_preview = gr.Gallery(
            label="Preview",
            show_label=True,
            elem_id="gallery",
            columns=3,
            rows=2,
            height=245,
            object_fit="contain"
        )
    
    return images_input, image_preview

def create_agent_selector():
    """에이전트 선택 드롭다운 생성"""
    return gr.Dropdown(
        choices=[
            "Text Legibility",
            "Information Architecture", 
            "Icon Representativeness",
            "User Task Suitability"
        ],
        label="Evaluation Module",
            value="Text Legibility",
            container=True,
        interactive=True
    )

def create_control_buttons():
    """제어 버튼들 생성"""
    initial_extract_btn = gr.Button("📋 DR 생성", variant="primary", interactive=True)
    cache_status_btn = gr.Button("캐시 상태 조회", variant="secondary")
    clear_btn = gr.Button("초기화", variant="stop", interactive=True)
    final_report_btn = gr.Button("최종 평가 결과 논의 시작", variant="primary", interactive=False)
    
    return initial_extract_btn, cache_status_btn, clear_btn, final_report_btn

def create_cache_status_display():
    """캐시 상태 표시 컴포넌트 생성"""
    return gr.Textbox(
        label="Cache",
        lines=2,
        interactive=False,
        scale=2
    )

def create_clear_confirm_dialog():
    """초기화 확인 다이얼로그 생성"""
    with gr.Row(visible=False) as clear_confirm_row:
        clear_confirm_text = gr.Textbox(
            value="정말로 모든 데이터를 초기화하시겠습니까?",
            interactive=False,
            label="초기화 확인"
        )
        with gr.Row():
            clear_confirm_btn = gr.Button("✅ 확인", variant="stop")
            clear_cancel_btn = gr.Button("❌ 취소", variant="secondary")
    
    return clear_confirm_row, clear_confirm_text, clear_confirm_btn, clear_cancel_btn

def create_evaluation_mode():
    """평가 모드 UI 생성"""
    with gr.Group(visible=True) as evaluation_mode:
        with gr.Row():
            with gr.Column(scale=1):
                # JSON 추출 결과
                json_output = gr.Textbox(
                    label="Design Representation",
                    lines=25,
                    max_lines=25,
                    interactive=False,
                    placeholder="평가 모듈이 이해한 디자인이 여기에 표시됩니다."
                )
                # 사용자 피드백 입력
                user_feedback = gr.Textbox(
                    label="💬 Feedback",
                    placeholder="DR을 개선하기 위한 피드백을 입력하고 DR을 수정하세요...",
                    lines=3,
                    max_lines=5
                )
                
                with gr.Row():
                    feedback_extract_btn = gr.Button("🔄 DR 업데이트", variant="secondary", interactive=False)
                    confirm_dr_btn = gr.Button("✅ DR 확정", variant="primary", interactive=False)
            
            with gr.Column(scale=1):
                # 가이드라인 결과
                guideline_output = gr.Textbox(
                    label="UX Issue",
                    lines=25,
                    max_lines=25,
                    interactive=False,
                    placeholder="평가 모듈이 도출한 UX 문제가 여기에 표시됩니다."
                )
                # 평가 피드백 입력
                evaluation_feedback = gr.Textbox(
                    label="💬 Feedback",
                    placeholder="UX 문제를 개선하기 위한 피드백을 입력하고 평가를 수정하세요...",
                    lines=3,
                    max_lines=5
                )
                # 평가 관련 버튼
                with gr.Row():
                    evaluation_feedback_btn = gr.Button("🔄 평가 업데이트", variant="secondary", interactive=False)
                    download_btn = gr.Button("📥 UX 문제 다운로드", variant="primary", interactive=False)
    
    return (evaluation_mode, json_output, user_feedback, feedback_extract_btn, 
            confirm_dr_btn, guideline_output, evaluation_feedback, 
            evaluation_feedback_btn, download_btn)

def create_final_report_mode():
    """Final Report 모드 UI 생성"""
    with gr.Group(visible=False) as final_report_mode:
        with gr.Column():
            # 채팅 영역 (챗봇 UI)
            final_report_chat = gr.Chatbot(
                label="💬 Final Summary & Discussion",
                show_share_button=True,
                show_copy_button=True,
                bubble_full_width=False,
                avatar_images=None,
                height=600
            )
            
            # 사용자 입력 및 버튼
            with gr.Row():
                final_report_input = gr.Textbox(
                    label="",
                    placeholder="관심 있는 평가 결과에 대해 자유롭게 질문해보세요... (예: 가장 해결이 시급한 UX 문제는 무엇인가요?)\n- 특정 평가 모듈의 결과\n- 모든 평가 모듈을 종합한 결과",
                    lines=3,
                    scale=5,
                    interactive=False
                )
                final_report_send_btn = gr.Button("📤 전송", variant="primary", scale=1, interactive=False)
            
            # 컨트롤 버튼들
            with gr.Row():
                back_to_evaluation_btn = gr.Button("⬅️ 평가 모드로 돌아가기", variant="secondary", interactive=False)
                save_discussion_btn = gr.Button("💾 대화 내용 저장", variant="primary", interactive=False)
                clear_chat_btn = gr.Button("🗑️ 대화 초기화", variant="stop", interactive=False)
    
    return (final_report_mode, final_report_chat, final_report_input, 
            final_report_send_btn, back_to_evaluation_btn, save_discussion_btn, clear_chat_btn)

def update_image_preview(files):
    """업로드된 이미지들의 프리뷰 업데이트"""
    if not files:
        return []
    
    preview_images = []
    for file_obj in files:
        try:
            # 단순화된 이미지 로드
            if hasattr(file_obj, 'name'):
                image = Image.open(file_obj.name)
            else:
                image = Image.open(file_obj)
            
            # PIL Image를 numpy 배열로 변환 (Gradio Gallery용)
            img_array = np.array(image)
            preview_images.append(img_array)
            print(f"프리뷰 이미지 추가: {image.size}")
            
        except Exception as e:
            print(f"프리뷰 이미지 변환 오류: {e}")
            continue
    
    return preview_images