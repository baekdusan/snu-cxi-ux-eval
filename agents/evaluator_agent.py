import json
from typing import List, Dict, Any, Optional
from openai import OpenAI
import re

from prompts.prompt_loader import SimplePromptLoader
from config import get_openai_client, DEFAULT_MODEL


class EvaluatorAgent:
    """평가 에이전트 (Responses API + file_search 연동)"""

    def __init__(self, agent_type: str, vector_store_id: Optional[str] = None, api_key: Optional[str] = None):
        self.agent_type = agent_type
        self.vector_store_id = vector_store_id  # file_search용 벡터스토어 ID
        self.client = get_openai_client(api_key)
        
        # 프롬프트 로더 초기화
        self.prompt_loader = SimplePromptLoader()

        # 대화 히스토리 및 JSON 캐시
        self.conversation_history: List[Dict[str, Any]] = []
        self.last_valid_json: Optional[Dict[str, Any]] = None  # 마지막 유효한 JSON 저장

        print(f"Evaluator Agent 초기화 완료: {self.agent_type} (vector_store_id={self.vector_store_id})")

    def generate_guidelines(self, base64_images: List[str], json_data: Dict[str, Any], user_feedback: str = "") -> str:
        """평가 가이드라인 생성 (Responses API 기반, JSON 출력)"""
        try:
            # 시스템 프롬프트 로드
            system_prompt = self.prompt_loader.load_prompt("evaluator", self.agent_type)

            # 입력 메시지 구성 시작
            input_messages: List[Dict[str, Any]] = []

            # 1) 시스템 메시지 (Responses API: input_text)
            input_messages.append({
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}]
            })

            # 2) 기존 대화 히스토리 포함
            if self.conversation_history:
                input_messages.extend(self.conversation_history)

            # 3) 이번 턴 user 컨텐츠 구성
            if not user_feedback:
                # 첫 호출 - JSON 데이터 + 이미지들
                json_str = json.dumps(json_data, ensure_ascii=False, separators=(',', ':'))

                user_content: List[Dict[str, Any]] = []
                # (a) JSON 텍스트 먼저
                user_content.append({
                    "type": "input_text",
                    "text": f"JSON Data:\n{json_str}\n\nPlease generate/return the evaluation strictly in JSON format only."
                })

                # (b) 이미지 (최대 9장: 텍스트 1 + 이미지 9 = 총 10 파트 안전)
                max_images = min(len(base64_images), 9)
                if len(base64_images) > 9:
                    print(f"경고: 최대 9개 이미지만 처리 ({len(base64_images)}개 중 {max_images}개)")

                valid_images = [
                    img for img in base64_images[:max_images]
                    if img and isinstance(img, str) and img.startswith("data:image/")
                ]

                for img in valid_images:
                    # data URL을 그대로 image_url에 전달 (Responses API 규격)
                    user_content.append({
                        "type": "input_image",
                        "image_url": img
                        # 필요 시 "detail": "high" 추가 가능
                    })

                print(f"평가 시작: JSON 데이터 + {len(valid_images)}개 이미지")

            else:
                # 피드백 턴 - 텍스트만 (영문화)
                user_content = [{
                    "type": "input_text",
                    "text": f"User feedback: {user_feedback}\n\nPlease update the evaluation JSON strictly in the same JSON schema only, with no additional explanations."
                }]
                print(f"피드백 처리: {user_feedback[:50]}...")

            # 4) 현재 user 메시지 push
            current_message = {"role": "user", "content": user_content}
            input_messages.append(current_message)

            # 5) Responses API 호출 (file_search 활성화 - 벡터스토어가 있을 때만)
            kwargs = dict(model=DEFAULT_MODEL, input=input_messages)
            if self.vector_store_id:
                kwargs["tools"] = [{"type": "file_search", "vector_store_ids": [self.vector_store_id]}]

            response = self.client.responses.create(**kwargs)

            # 6) 응답 텍스트 추출
            response_content = getattr(response, "output_text", None)
            if response_content is None:
                response_content = str(response)

            # 7) 히스토리에 user/assistant 저장 (assistant는 output_text 타입)
            self.conversation_history.append(current_message)
            self.conversation_history.append({
                "role": "assistant",
                "content": [{"type": "output_text", "text": response_content}]
            })

            # 8) JSON 파싱
            parsed_result = self._parse_json_response(response_content)

            # 9) 성공/실패 처리
            if parsed_result.get("status") not in ["json_parse_error", "text_only", "error"]:
                self.last_valid_json = parsed_result
                json_output = json.dumps(parsed_result, ensure_ascii=False, indent=2)
                print(f"새 평가 JSON 생성 성공 ({self.agent_type})")
                return json_output
            else:
                # 파싱 실패 → 원인 분석 후 기존 캐시 유지 반환
                failure_reason = parsed_result.get("status", "unknown")
                print(f"JSON 파싱 실패 원인: {failure_reason} ({self.agent_type})")
                if failure_reason == "json_parse_error":
                    print(f"JSON 오류 상세: {parsed_result.get('json_error', 'N/A')}")
                    print(f"원본 응답 길이: {len(response_content)} 문자")
                    print(f"원본 응답 일부: {response_content[:200]}...")
                elif failure_reason == "text_only":
                    print(f"AI가 텍스트로만 응답 (JSON 없음)")
                    print(f"응답 내용: {response_content[:200]}...")
                
                if self.last_valid_json:
                    print(f"기존 캐시된 JSON 유지 ({self.agent_type})")
                    return json.dumps(self.last_valid_json, ensure_ascii=False, indent=2)
                else:
                    print(f"첫 평가 JSON 생성 실패 - 재시도 권장 ({self.agent_type})")
                    return f"❌ {self.agent_type} 평가 생성에 실패했습니다. (원인: {failure_reason}) 재시도해보세요."

        except Exception as e:
            print(f"Evaluator 실행 오류: {e}")
            import traceback
            print(f"상세 오류: {traceback.format_exc()}")
            if self.last_valid_json:
                print(f"에러 발생, 기존 JSON 유지 ({self.agent_type})")
                return json.dumps(self.last_valid_json, ensure_ascii=False, indent=2)
            else:
                return f"❌ {self.agent_type} 평가 생성 중 오류가 발생했습니다: {str(e)}"

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
                    # (a) 잘못된 꼬리 콤마 제거: ", }" / ", ]" → "}" / "]"
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

    # ----------------------
    # Utilities
    # ----------------------
    def reset_conversation(self):
        """대화 히스토리 초기화 (기존 JSON 유지)"""
        self.conversation_history.clear()
        print(f"Evaluator 대화 히스토리 초기화 ({self.agent_type})")

    def clear_json_cache(self):
        """저장된 JSON 캐시 완전 초기화"""
        self.last_valid_json = None
        self.reset_conversation()
        print(f"Evaluator JSON 캐시 초기화 ({self.agent_type})")


def create_evaluator_agent(agent_type: str, vector_store_id: Optional[str] = None, api_key: Optional[str] = None) -> EvaluatorAgent:
    """평가 에이전트 생성"""
    return EvaluatorAgent(agent_type, vector_store_id=vector_store_id, api_key=api_key)
