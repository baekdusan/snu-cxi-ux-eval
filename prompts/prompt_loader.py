import re
import json
import hashlib
from pathlib import Path
from typing import Optional, Dict
from openai import OpenAI

from config import get_openai_client

# 파일 읽기 라이브러리들
try:
    import docx  # python-docx 라이브러리
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import markdown  # markdown 라이브러리
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

class SimplePromptLoader:
    """간단한 프롬프트 로더 - Python 파일 기반 프롬프트 관리"""
    
    def __init__(self):
        self.prompts_dir = Path("prompts/")
        self.refs_dir = Path("references/")  # 루트 레벨 references 폴더
        self.cache_file = Path(".vector_store_cache.json")  # 벡터스토어 캐시 파일
        
        # OpenAI 클라이언트 초기화 (환경변수가 있을 때만 시도)
        try:
            self.client = get_openai_client()
        except ValueError:
            self.client = None
            print("경고: OPENAI_API_KEY가 설정되지 않았습니다. 벡터스토어 기능을 사용할 수 없습니다.")
        
        # 에이전트별 참조 문서 매핑 (벡터스토어용)
        self.reference_mapping = {
            "Text Legibility": ["Agent1_Text_heuristics.md"],
            "Information Architecture": ["Agent2_Terms_and_definitions.md", "Agent2_IA_heuristics.md"],
            "Icon Representativeness": ["Agent3_Icon_heuristics.md"],
            "User Task Suitability": ["Agent4_Terms_and_definitions.md", "Agent4_heuristics.md"]
        }
        
        # 벡터스토어 관련 속성
        self.vector_store = None
        self.file_to_vector_store_mapping = {}  # 파일명 -> 벡터스토어 ID 매핑
        self._vector_store_initialized = False  # 초기화 상태 추적
        
        # 캐시 로드
        self._load_cache()
    
    def _calculate_files_hash(self) -> str:
        """참조 파일들의 해시값 계산 (파일 변경 감지용)"""
        hasher = hashlib.md5()
        
        # 모든 참조 파일 수집 (중복 제거)
        all_files = set()
        for agent_files in self.reference_mapping.values():
            for filename in agent_files:
                all_files.add(filename)
        
        # 파일들을 정렬된 순서로 해시에 추가
        for filename in sorted(all_files):
            file_path = self.refs_dir / filename
            if file_path.exists():
                # 파일명과 수정시간을 해시에 포함
                hasher.update(f"{filename}:{file_path.stat().st_mtime}".encode())
            else:
                hasher.update(f"{filename}:missing".encode())
        
        return hasher.hexdigest()
    
    def _load_cache(self) -> None:
        """캐시 파일에서 벡터스토어 정보 로드"""
        if not self.cache_file.exists():
            return
        
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            
            # 파일 해시 검증
            current_hash = self._calculate_files_hash()
            cached_hash = cache_data.get('files_hash', '')
            
            if current_hash == cached_hash:
                # 파일이 변경되지 않았으면 캐시된 벡터스토어 정보 사용
                self.vector_store_id = cache_data.get('vector_store_id')
                self.file_to_vector_store_mapping = cache_data.get('file_mapping', {})
                if self.vector_store_id:
                    self._vector_store_initialized = True
                    print(f"✅ 캐시된 벡터스토어 재사용: {self.vector_store_id}")
                    return
            
            print("📁 참조 파일이 변경되었거나 캐시가 유효하지 않습니다. 새로 생성합니다.")
            
        except Exception as e:
            print(f"⚠️ 캐시 로드 실패: {e}")
    
    def _save_cache(self) -> None:
        """벡터스토어 정보를 캐시 파일에 저장"""
        try:
            cache_data = {
                'vector_store_id': getattr(self, 'vector_store_id', None),
                'files_hash': self._calculate_files_hash(),
                'file_mapping': self.file_to_vector_store_mapping
            }
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            print(f"💾 벡터스토어 캐시 저장 완료")
            
        except Exception as e:
            print(f"⚠️ 캐시 저장 실패: {e}")
    
    def load_prompt(self, agent_type: str, agent_name: str) -> str:
        """에이전트 타입과 이름으로 프롬프트 로드 (모든 에이전트 Markdown 사용)"""
        try:
            # 모든 에이전트가 Markdown 파일 사용
            agent_num = self._get_agent_number(agent_name)
            if agent_type == "dr_generator":
                md_file = f"Agent{agent_num}_DR_prompt.md"
            elif agent_type == "evaluator":
                md_file = f"Agent{agent_num}_E_prompt.md"
            else:
                raise ValueError(f"알 수 없는 에이전트 타입: {agent_type}")
            
            prompt_text = self._read_markdown_prompt(md_file)
            
            # 프롬프트 원본 그대로 반환 (file_search가 벡터스토어에서 관련 내용 자동 검색)
            return prompt_text
            
        except Exception as e:
            print(f"프롬프트 로드 오류: {e}")
            return f"프롬프트 로드 실패: {str(e)}"
    
    def _get_agent_number(self, agent_name: str) -> str:
        """에이전트 이름을 숫자로 매핑"""
        mapping = {
            "Text Legibility": "1",
            "Information Architecture": "2",
            "Icon Representativeness": "3", 
            "User Task Suitability": "4"
        }
        if agent_name not in mapping:
            raise ValueError(f"알 수 없는 에이전트: {agent_name}")
        return mapping[agent_name]
    
    def _read_markdown_prompt(self, filename: str) -> str:
        """Markdown 프롬프트 파일 읽기"""
        file_path = self.prompts_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없음: {filename}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            raise Exception(f"파일 읽기 오류 ({filename}): {str(e)}")
    
    
    def _read_docx_file(self, file_path: Path) -> str:
        """DOCX 파일 읽기"""
        if not DOCX_AVAILABLE:
            return f"[python-docx 라이브러리가 설치되지 않음: {file_path.name}]"
        
        try:
            doc = docx.Document(file_path)
            text = []
            for paragraph in doc.paragraphs:
                text.append(paragraph.text)
            return '\n'.join(text)
        except Exception as e:
            return f"[DOCX 파일 읽기 오류: {file_path.name}, {str(e)}]"
    
    def _read_markdown_file(self, file_path: Path) -> str:
        """Markdown 파일 읽기 (HTML로 변환 후 텍스트 추출)"""
        if not MARKDOWN_AVAILABLE:
            return f"[markdown 라이브러리가 설치되지 않음: {file_path.name}]"
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # Markdown을 HTML로 변환
            html = markdown.markdown(md_content)
            
            # HTML 태그 제거하고 텍스트만 추출
            import re
            text = re.sub(r'<[^>]+>', '', html)
            return text
        except Exception as e:
            return f"[Markdown 파일 읽기 오류: {file_path.name}, {str(e)}]"
    
    
    def create_vector_store(self) -> str:
        """참조 파일들을 벡터스토어에 업로드하고 벡터스토어 ID 반환"""
        if not self.client:
            print("오류: OpenAI 클라이언트가 초기화되지 않았습니다.")
            return None
            
        try:
            # 캐시된 벡터스토어가 있으면 재사용
            if self._vector_store_initialized and hasattr(self, 'vector_store_id'):
                print(f"✅ 캐시된 벡터스토어 재사용: {self.vector_store_id}")
                return self.vector_store_id
            
            print("=== 벡터스토어 생성 및 파일 업로드 시작 ===")
            
            # 새 벡터스토어 생성
            self.vector_store = self.client.vector_stores.create(
                name="UX Guidelines Reference Documents"
            )
            self.vector_store_id = self.vector_store.id
            print(f"벡터스토어 생성 완료: {self.vector_store_id}")
            
            # 모든 참조 파일 수집 (중복 제거)
            all_files = set()
            for agent_files in self.reference_mapping.values():
                for filename in agent_files:
                    all_files.add(filename)
            
            print(f"업로드할 파일 목록: {list(all_files)}")
            
            # 파일들을 벡터스토어에 업로드
            uploaded_count = 0
            for filename in all_files:
                file_path = self.refs_dir / filename
                if file_path.exists():
                    try:
                        print(f"파일 업로드 중: {filename}")
                        with open(file_path, 'rb') as f:
                            # OpenAI에 파일 업로드
                            uploaded_file = self.client.files.create(
                                file=f,
                                purpose='assistants'
                            )
                            
                            # 벡터스토어에 파일 추가
                            self.client.vector_stores.files.create(
                                vector_store_id=self.vector_store_id,
                                file_id=uploaded_file.id
                            )
                            
                            # 매핑 테이블에 추가
                            self.file_to_vector_store_mapping[filename] = uploaded_file.id
                            print(f"✅ 업로드 완료: {filename} -> {uploaded_file.id}")
                            uploaded_count += 1
                            
                    except Exception as e:
                        print(f"❌ 파일 업로드 실패: {filename}, 오류: {e}")
                else:
                    print(f"⚠️  파일을 찾을 수 없음: {file_path}")
            
            # 초기화 완료 표시 및 캐시 저장
            self._vector_store_initialized = True
            self._save_cache()
            print(f"=== 벡터스토어 초기화 완료: {uploaded_count}개 파일 업로드 ===")
            
            return self.vector_store_id
            
        except Exception as e:
            print(f"❌ 벡터스토어 생성 실패: {e}")
            return None
    
    def get_vector_store_id(self) -> Optional[str]:
        """벡터스토어 ID 반환 (없으면 생성)"""
        if self._vector_store_initialized and hasattr(self, 'vector_store_id'):
            return self.vector_store_id
        return self.create_vector_store()
    
    def get_file_mapping(self) -> Dict[str, str]:
        """파일명 -> 벡터스토어 파일 ID 매핑 반환"""
        return self.file_to_vector_store_mapping.copy()
    
    def is_file_uploaded(self, filename: str) -> bool:
        """특정 파일이 벡터스토어에 업로드되었는지 확인"""
        return filename in self.file_to_vector_store_mapping
    
    def initialize_vector_store_if_needed(self) -> bool:
        """필요시 벡터스토어 초기화 (최초 한번만)"""
        if not self._vector_store_initialized:
            vector_store_id = self.create_vector_store()
            return vector_store_id is not None
        return True
    
    # 레거시 메서드 - 현재 사용되지 않음
    # def get_available_prompts(self, agent_type: str) -> list:
    #     """사용 가능한 프롬프트 목록 반환 (레거시)"""
    #     pass 