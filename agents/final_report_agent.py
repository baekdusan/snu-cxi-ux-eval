import json
import os
import re
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime
from openai import OpenAI

from config import get_openai_client, DEFAULT_MODEL, VECTOR_INDEXING_WAIT_TIME


class FinalReportAgent:
    """최종 레포트 생성 에이전트 - 모든 평가 결과를 AI가 분석하고 통합 (멀티턴 대화형)"""

    def __init__(self, api_key: Optional[str] = None):
        self.client = get_openai_client(api_key)
        self.model = DEFAULT_MODEL
        self.final_report_cache_file = Path(".final_report_vector_cache.json")
        
        # 멀티턴 대화를 위한 상태 관리
        self.conversation_history: List[Dict[str, Any]] = []
        self.vector_store_id: Optional[str] = None
        self.evaluation_files: List[str] = []
        self.is_initialized: bool = False

    def _calculate_files_hash(self, file_paths: List[str]) -> str:
        """평가 파일들의 해시값 계산 (캐시 키로 사용)"""
        hasher = hashlib.md5()
        
        for file_path in sorted(file_paths):
            if os.path.exists(file_path):
                # 파일명과 수정시간을 해시에 포함
                stat = os.stat(file_path)
                hasher.update(f"{file_path}:{stat.st_mtime}:{stat.st_size}".encode())
            else:
                hasher.update(f"{file_path}:missing".encode())
        
        return hasher.hexdigest()

    def _load_vector_cache(self, files_hash: str) -> Optional[str]:
        """캐시된 벡터스토어 ID 로드"""
        if not self.final_report_cache_file.exists():
            return None
        
        try:
            with open(self.final_report_cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            if cache_data.get('files_hash') == files_hash:
                vector_store_id = cache_data.get('vector_store_id')
                if vector_store_id:
                    print(f"✅ 캐시된 평가 벡터스토어 재사용: {vector_store_id}")
                    return vector_store_id
            
            print("📁 평가 파일이 변경되었습니다. 새 벡터스토어를 생성합니다.")
            return None
            
        except Exception as e:
            print(f"⚠️ 캐시 로드 실패: {e}")
            return None

    def _save_vector_cache(self, files_hash: str, vector_store_id: str) -> None:
        """벡터스토어 ID를 캐시에 저장"""
        try:
            cache_data = {
                'files_hash': files_hash,
                'vector_store_id': vector_store_id,
                'created_at': datetime.datetime.now().isoformat()
            }
            
            with open(self.final_report_cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"💾 평가 벡터스토어 캐시 저장 완료")
            
        except Exception as e:
            print(f"⚠️ 캐시 저장 실패: {e}")

    def initialize_with_files(self, evaluation_files: List[str]) -> str:
        """평가 파일들을 로드하고 멀티턴 대화 준비"""
        if not evaluation_files:
            return "❌ 평가 결과 파일이 없습니다."

        # 파일 존재 확인
        valid_files = [f for f in evaluation_files if os.path.exists(f)]
        if not valid_files:
            return "❌ 읽을 수 있는 평가 결과 파일이 없습니다."

        try:
            self.evaluation_files = valid_files
            
            # 파일 해시 계산 및 캐시 확인
            files_hash = self._calculate_files_hash(valid_files)
            cached_vector_store_id = self._load_vector_cache(files_hash)
            
            if cached_vector_store_id:
                # 캐시된 벡터스토어 사용
                self.vector_store_id = cached_vector_store_id
            else:
                # 새 벡터스토어 생성
                print("=== 평가 결과 벡터스토어 생성 시작 ===")
                
                # 파일 업로드
                uploaded_files = []
                for file_path in valid_files:
                    with open(file_path, "rb") as f:
                        uploaded_file = self.client.files.create(
                            file=f,
                            purpose="assistants"
                        )
                        uploaded_files.append(uploaded_file.id)
                        print(f"파일 업로드 완료: {os.path.basename(file_path)} (ID: {uploaded_file.id})")

                # 벡터스토어 생성 후 파일 추가
                vs = self.client.vector_stores.create(name="Final Report Evaluation Data")
                self.vector_store_id = vs.id
                for file_id in uploaded_files:
                    self.client.vector_stores.files.create(vector_store_id=self.vector_store_id, file_id=file_id)
                print(f"벡터스토어 생성 완료: {self.vector_store_id}")

                # 캐시 저장
                self._save_vector_cache(files_hash, self.vector_store_id)
                
                # 인덱싱 대기
                time.sleep(VECTOR_INDEXING_WAIT_TIME)

            self.is_initialized = True
            file_list = ", ".join([os.path.basename(f) for f in valid_files])
            
            return f"✅ **Final Report Agent 준비 완료!**\n\n📁 **로드된 평가 파일**: {file_list}\n\n💬 **이제 평가 결과에 대해 자유롭게 질문해보세요:**\n- 가장 심각한 문제는 무엇인가요?\n- 우선순위별 개선 사항을 알려주세요\n- 각 에이전트별 주요 발견사항은?\n- 사용자 경험 개선 방향 제시해주세요"

        except Exception as e:
            return f"❌ 초기화 중 오류 발생: {str(e)}"

    def chat(self, user_message: str) -> str:
        """사용자와의 멀티턴 대화 처리"""
        if not self.is_initialized:
            return "❌ 먼저 평가 파일들을 로드해주세요."
        
        if not user_message.strip():
            return "💬 질문을 입력해주세요."

        try:
            # 시스템 프롬프트 (평가 데이터 전문가 역할)
            system_prompt = """당신은 UX/UI 평가 결과 분석 전문가입니다. 
첨부된 평가 파일들에 대해 file_search 도구를 사용하여 정확한 정보를 검색하고, 
사용자의 질문에 대해 구체적이고 실용적인 답변을 제공하세요.

중요한 원칙:
- 반드시 file_search로 검색한 실제 데이터를 기반으로 답변
- 추측이나 일반론이 아닌 구체적인 평가 결과 인용
- 개선 제안 시 우선순위와 구체적인 실행 방안 제시
- 전문적이지만 이해하기 쉬운 언어로 설명"""

            # 입력 메시지 구성
            input_messages: List[Dict[str, Any]] = []
            
            # 시스템 메시지
            input_messages.append({
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt}]
            })
            
            # 기존 대화 히스토리
            input_messages.extend(self.conversation_history)
            
            # 현재 사용자 메시지
            current_message = {
                "role": "user", 
                "content": [{"type": "input_text", "text": user_message}]
            }
            input_messages.append(current_message)

            # Responses API 호출 (file_search 활성화)
            response = self.client.responses.create(
                model=self.model,
                input=input_messages,
                tools=[{
                    "type": "file_search",
                    "vector_store_ids": [self.vector_store_id]
                }]
            )

            ai_response = response.output_text
            
            # 대화 히스토리에 추가
            self.conversation_history.append(current_message)
            self.conversation_history.append({
                "role": "assistant",
                "content": [{"type": "output_text", "text": ai_response}]
            })

            return ai_response

        except Exception as e:
            return f"❌ 응답 생성 중 오류 발생: {str(e)}"

    def reset_conversation(self):
        """대화 히스토리 초기화 (평가 데이터는 유지)"""
        self.conversation_history.clear()
        print("Final Report Agent 대화 히스토리 초기화")

    def clear_all(self):
        """모든 상태 초기화"""
        self.conversation_history.clear()
        self.vector_store_id = None
        self.evaluation_files.clear()
        self.is_initialized = False
        print("Final Report Agent 완전 초기화")

    def generate_final_report_json(self) -> Dict[str, Any]:
        """구조화된 JSON 레포트 생성 (레거시 호환)"""
        if not self.is_initialized:
            return {"error": "Agent not initialized"}
        
        report_request = "모든 평가 결과를 종합하여 다음 JSON 형식으로 최종 보고서를 작성해주세요:\n\n{\n  \"summary\": \"전체 요약\",\n  \"critical_issues\": [\"심각한 문제들\"],\n  \"recommendations\": [\"개선 제안들\"],\n  \"priority_matrix\": \"우선순위별 실행 계획\"\n}\n\nJSON 형식으로만 응답해주세요."
        
        response = self.chat(report_request)
        
        # JSON 추출 시도
        try:
            # JSON 부분만 추출
            start = response.find('{')
            end = response.rfind('}') + 1
            if start != -1 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
            else:
                return {"raw_response": response}
        except json.JSONDecodeError:
            return {"raw_response": response}

    def save_report(self, report: Dict[str, Any], output_dir: str = "output") -> str:
        """최종 레포트를 파일로 저장"""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"final_report_{timestamp}.json"
        file_path = os.path.join(output_dir, filename)

        os.makedirs(output_dir, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        return file_path