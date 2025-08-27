import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
import re

from prompts.prompt_loader import SimplePromptLoader
from config import get_openai_client, DEFAULT_MODEL, MAX_IMAGES_PER_REQUEST, get_current_model


class DRGeneratorAgent:
    """디자인 참조 생성 에이전트 (Responses API + file_search 연동)"""

    def __init__(self, agent_type: str, vector_store_id: Optional[str] = None, api_key: Optional[str] = None):
        self.agent_type = agent_type
        self.vector_store_id = vector_store_id  # file_search용 벡터스토어 ID
        self.client = get_openai_client(api_key)
        
        # 프롬프트 로더 초기화
        self.prompt_loader = SimplePromptLoader()

        # 대화 히스토리 및 JSON 캐시
        self.conversation_history: List[Dict[str, Any]] = []
        self.last_valid_json: Optional[Dict[str, Any]] = None  # 마지막 유효한 JSON 저장

        print(f"DR Generator Agent 초기화 완료: {self.agent_type} (vector_store_id={self.vector_store_id})")

    # ----------------------
    # Public methods
    # ----------------------
    def extract_json(self, base64_images: List[str], user_feedback: str = "") -> Dict[str, Any]:
        """
        이미지에서 JSON 데이터 추출 (Responses API 기반)
        - base64_images: 'data:image/png;base64,AAAA...' 형식의 data URL 리스트 (최대 10장)
        - user_feedback: 후속 턴에서 JSON 업데이트용 피드백(텍스트)
        """
        try:
            # 시스템 프롬프트 로드
            system_prompt = self.prompt_loader.load_prompt("dr_generator", self.agent_type)

            # 입력 메시지 배열
            input_messages: List[Dict[str, Any]] = []

            # 1) 시스템 메시지
            input_messages.append({
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}]
            })

            # 2) 기존 대화 히스토리 재사용
            if self.conversation_history:
                input_messages.extend(self.conversation_history)

            # 3) 현재 사용자 메시지 구성
            if not user_feedback:
                # 첫 호출 - 이미지들과 분석 요청
                max_images = min(len(base64_images), MAX_IMAGES_PER_REQUEST)
                if len(base64_images) > MAX_IMAGES_PER_REQUEST:
                    print(f"경고: 최대 {MAX_IMAGES_PER_REQUEST}개 이미지만 처리 ({len(base64_images)}개 중 {max_images}개)")

                # 유효한 data URL만 필터링
                valid_images = [
                    img for img in base64_images[:max_images]
                    if isinstance(img, str) and img.startswith("data:image/")
                ]
                
                print(f"디버그: 전체 이미지 개수: {len(base64_images)}")
                print(f"디버그: 유효 이미지 개수: {len(valid_images)}")
                if base64_images:
                    print(f"디버그: 첫 번째 이미지 시작: {base64_images[0][:50] if base64_images[0] else 'None'}...")
                
                if not valid_images:
                    raise Exception("유효한 이미지(data URL)가 없습니다. 형식: data:image/png;base64,AAAA...")

                # 사용자 콘텐츠(이미지 + 텍스트)
                user_content: List[Dict[str, Any]] = []
                for img in valid_images:
                    # Responses API는 data URL을 그대로 image_url로 받습니다.
                    user_content.append({
                        "type": "input_image",
                        "image_url": img,
                        # 필요 시 "detail": "high" 가능
                    })

                user_content.append({
                    "type": "input_text",
                    "text": "Analyze the screenshots and return ONLY the JSON in the schema specified by the system prompt. No extra text."
                })

                print(f"이미지 분석 시작: {len(valid_images)}개 이미지")

            else:
                # 피드백 턴 - 텍스트만
                user_content = [{
                    "type": "input_text",
                    "text": f"User feedback: {user_feedback}\n\nPlease update the JSON based on this feedback. Respond with JSON only."
                }]
                print(f"피드백 처리: {user_feedback[:50]}...")

            # 4) 현재 사용자 메시지 추가
            current_message = {"role": "user", "content": user_content}
            input_messages.append(current_message)

            # 5) Responses API 호출 (file_search 활성화 - 벡터스토어가 있을 때만)
            current_model = get_current_model()
            kwargs = dict(model=current_model, input=input_messages)
            if self.vector_store_id:
                kwargs["tools"] = [{"type": "file_search", "vector_store_ids": [self.vector_store_id]}]

            response = self.client.responses.create(**kwargs)
            print(f"🤖 DR Generation - 사용 모델: {current_model}")

            # 6) 텍스트 추출
            response_content = getattr(response, "output_text", None)
            if response_content is None:
                response_content = str(response)

            # 7) 대화 히스토리에 현재 턴 추가 (assistant 응답도 저장)
            self.conversation_history.append(current_message)
            self.conversation_history.append({
                "role": "assistant",
                "content": [{"type": "output_text", "text": response_content}]
            })

            # 8) JSON 파싱
            parsed_result = self._parse_json_response(response_content)

            # 9) 파싱 성공 여부 확인
            if parsed_result.get("status") not in ["json_parse_error", "text_only", "error"]:
                # 유효한 JSON이면 저장하고 반환
                self.last_valid_json = parsed_result
                print(f"새 JSON 생성 성공 ({self.agent_type})")
                return parsed_result
            else:
                # 파싱 실패 → 기존 JSON 유지
                if self.last_valid_json:
                    print(f"JSON 파싱 실패, 기존 JSON 유지 ({self.agent_type})")
                    return self.last_valid_json
                else:
                    # 첫 호출에서 실패한 경우
                    print(f"첫 JSON 생성 실패 ({self.agent_type})")
                    return parsed_result

        except Exception as e:
            print(f"DR Generator 실행 오류: {e}")

            # 기존 유효한 JSON이 있으면 반환, 없으면 에러
            if self.last_valid_json:
                print(f"에러 발생, 기존 JSON 유지 ({self.agent_type})")
                return self.last_valid_json
            else:
                return {
                    "error": str(e),
                    "agent_type": self.agent_type,
                    "status": "error"
                }

    def reset_conversation(self):
        """대화 히스토리 초기화 (기존 JSON 유지)"""
        self.conversation_history.clear()
        print(f"DR Generator 대화 히스토리 초기화 ({self.agent_type})")

    def clear_json_cache(self):
        """저장된 JSON 캐시 완전 초기화"""
        self.last_valid_json = None
        self.reset_conversation()
        print(f"DR Generator JSON 캐시 초기화 ({self.agent_type})")

    # ----------------------
    # Private helpers
    # ----------------------
    def _parse_json_response(self, response_content: str) -> Dict[str, Any]:
        """응답에서 JSON 파싱(견고성 보강)"""
        # 1) 직접 파싱
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            pass

        # 2) 가장 바깥 {} 블록 추출
        start_idx = response_content.find('{')
        end_idx = response_content.rfind('}') + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = response_content[start_idx:end_idx]

            # 2-1) 그대로 파싱
            try:
                return json.loads(json_str)
            except json.JSONDecodeError as e:
                # 2-2) 흔한 오류 보정 시도
                try:
                    # (a) 잘못된 꼬리 콤마 제거
                    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                    json_str = json_str.strip()

                    # (b) 여는/닫는 중괄호 수 불일치 보정
                    if json_str.count('{') > json_str.count('}'):
                        json_str += '}' * (json_str.count('{') - json_str.count('}'))

                    return json.loads(json_str)
                except json.JSONDecodeError:
                    # 2-3) 실패 시 원문 포함하여 반환
                    return {
                        "analysis_type": self.agent_type,
                        "content": response_content,
                        "raw_json": json_str,
                        "json_error": str(e),
                        "status": "json_parse_error"
                    }
        else:
            # 3) JSON 블록이 아예 없을 때
            return {
                "analysis_type": self.agent_type,
                "content": response_content,
                "status": "text_only"
            }


def create_dr_generator_agent(agent_type: str, vector_store_id: Optional[str] = None, api_key: Optional[str] = None) -> DRGeneratorAgent:
    """디자인 참조 생성 에이전트 생성"""
    return DRGeneratorAgent(agent_type, vector_store_id=vector_store_id, api_key=api_key)
