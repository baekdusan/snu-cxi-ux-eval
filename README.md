---
title: Samsung UX Evaluation
emoji: 📱
colorFrom: blue
colorTo: purple
sdk: gradio
sdk_version: 3.50.2
app_file: app.py
pinned: false
---


# Samsung MX UI Analytics System

Samsung MX UI에 대한 UX/UI 분석을 위한 AI 기반 분석 시스템입니다. 스크린샷을 업로드하여 4가지 전문 에이전트(Visibility, Information Architecture, Icon Representativeness, User Task Suitability)로 분석하고, 최종 레포트를 생성할 수 있습니다.

## 🎯 **새로운 간단한 구조**

### **1단계: 디자인 참조 생성 에이전트 (DR Generator Agent)**
- 스크린샷 → JSON 파일 생성
- 멀티턴 대화로 JSON 개선
- 최종 JSON 파일 저장

### **2단계: 평가 에이전트 (Evaluator Agent)**
- 스크린샷 + JSON 파일 → 평가 결과 생성
- 각 에이전트별 전문 분석

## 📁 **프로젝트 구조**

```
snu-cxi-ux-eval/
├── app.py                          # 메인 Gradio 애플리케이션
├── config.py                       # 설정 관리 (API 키, 모델 설정)
├── utils.py                        # 유틸리티 함수들 (이미지 인코딩, 캐시 관리)
├── requirements.txt                 # Python 의존성
├── README.md                       # 프로젝트 설명
├── agents/                         # AI 에이전트 모듈
│   ├── __init__.py                 # 에이전트 패키지 초기화
│   ├── dr_generator_agent.py       # 디자인 참조 생성 에이전트
│   ├── evaluator_agent.py          # 평가 에이전트
│   └── final_report_agent.py       # 최종 보고서 생성 및 대화 에이전트
├── ui/                             # UI 컴포넌트 및 비즈니스 로직
│   ├── __init__.py
│   ├── components.py               # Gradio UI 컴포넌트 정의
│   ├── business_logic.py           # 비즈니스 로직 및 상태 관리
│   └── handlers.py                 # 이벤트 핸들러
├── prompts/                        # 프롬프트 관리
│   ├── prompt_loader.py            # 프롬프트 로더 및 벡터 스토어 관리
│   └── Agent*_*.md                 # 4개 에이전트별 DR 생성 및 평가 프롬프트 (총 8개)
├── references/                     # 참조 문서 및 가이드라인
│   └── Agent*_*.md                 # 각 에이전트별 휴리스틱 및 용어 정의 문서들
└── output/                         # 분석 결과 저장소
    ├── drgenerator/                # DR 생성 결과 (JSON)
    ├── evaluator/                  # 평가 결과 (JSON)
    └── final_discussions/          # 최종 토론 내용 (JSON)
```

## 🚀 **사용 방법**

### **1. 환경 설정**
```bash
# 의존성 설치
pip install -r requirements.txt

# OpenAI API 키 설정
export OPENAI_API_KEY="your-api-key-here"
```

### **2. 애플리케이션 실행**
```bash
python app.py
```

### **3. 웹 인터페이스 사용**
1. **스크린샷 업로드**: 분석할 UI 스크린샷을 업로드
2. **에이전트 선택**: 분석할 에이전트 유형 선택
   - Visibility (가시성)
   - Information Architecture (정보 구조)
   - Icon Representativeness (아이콘 대표성)
   - User Task Suitability (사용자 작업 적합성)
3. **디자인 참조 생성**: 📋 버튼 클릭으로 JSON 추출
4. **피드백 입력** (선택사항): JSON 개선을 위한 피드백 입력
5. **평가 생성**: 💡 버튼 클릭으로 최종 평가 결과 생성
6. **대화형 분석**: 평가 결과를 바탕으로 AI와 대화하며 개선 방안 제시
7. **대화 내용 저장**: 분석 토론 내용을 JSON 파일로 다운로드

## 🔧 **기술 스택**

- **Python 3.8+**: 메인 프로그래밍 언어
- **Gradio 3.50.2**: 웹 UI 프레임워크  
- **OpenAI API (순정)**: Responses API, Vector Stores, File API
- **GPT-4o**: 멀티모달 AI 모델
- **PIL (Pillow)**: 이미지 처리
- **JSON**: 구조화된 데이터 포맷

## 💡 **주요 기능**

### **디자인 참조 생성 에이전트**
- 스크린샷에서 구조화된 JSON 데이터 추출
- 멀티턴 대화를 통한 JSON 개선
- 4가지 전문 영역별 분석

### **평가 에이전트**
- JSON 데이터와 스크린샷을 바탕으로 평가
- 구체적인 개선 방안 제시
- 우선순위별 가이드라인 생성

### **대화형 분석 에이전트**
- 평가 결과를 종합하여 자연어 대화 지원
- 사용자 질문에 맞춤형 개선 방안 제시
- 우선순위별 문제점 및 해결책 논의
- 대화 내용 JSON 형태로 저장 및 다운로드

### **이미지 캐싱 시스템**
- Base64 이미지 캐싱으로 성능 최적화
- 중복 변환 방지
- 메모리 효율성 향상

## 🎨 **UI 구성**

- **이미지 업로드**: 다중 이미지 지원
- **실시간 프리뷰**: 업로드된 이미지 갤러리
- **에이전트 선택**: 드롭다운 메뉴
- **단계별 진행**: 디자인 참조 → 평가
- **캐시 상태**: 시스템 상태 모니터링

## 🔄 **워크플로우**

1. **이미지 업로드** → 프리뷰 확인
2. **에이전트 선택** → 분석 영역 결정
3. **디자인 참조 생성** → JSON 데이터 추출
4. **피드백 입력** (선택) → JSON 개선
5. **평가 생성** → 최종 가이드라인 생성
6. **대화형 분석** → AI와 토론하며 맞춤형 개선 방안 도출

## 📊 **분석 영역**

### **Visibility (가시성)**
- 텍스트 가독성
- 버튼 및 인터랙션 요소 가시성
- 정보 계층 구조
- 색상 사용 및 공간 활용

### **Information Architecture (정보 구조)**
- 네비게이션 구조
- 메뉴 계층 구조
- 콘텐츠 조직화
- 사용자 경로 및 정보 검색성

### **Icon Representativeness (아이콘 대표성)**
- 아이콘 의미 전달력
- 아이콘 일관성
- 아이콘 가시성 및 스타일
- 문화적 적절성

### **User Task Suitability (사용자 작업 적합성)**
- 작업 완료성 및 효율성
- 작업 직관성 및 접근성
- 작업 일관성
- 다중 화면 연속성

## 🛠️ **개발 정보**

- **Python 버전**: 3.8+
- **Gradio 버전**: 3.50.2
- **OpenAI API**: 순정 API, GPT-4o 모델, Responses API 사용
- **이미지 형식**: PNG, JPG, JPEG, BMP, GIF 지원
- **데이터 형식**: JSON 구조화된 출력

## 📝 **라이선스**

이 프로젝트는 Samsung MX 팀을 위한 내부 도구입니다. 