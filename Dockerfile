# 베이스 이미지 (가볍고 안정적인 버전 사용)
FROM python:3.12-slim

# 작업 디렉토리 설정
WORKDIR /app

# 필수 패키지 설치를 위한 시스템 업데이트 (필요한 경우만)
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# 소스 코드 복사
COPY dumblexity.py .

# 세션 저장용 디렉토리 생성
RUN mkdir -p /app/sessions

# Streamlit 기본 포트 노출
EXPOSE 8501

# 헬스체크 (선택 사항, 운영 환경에서 유용)
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# 실행 명령어
ENTRYPOINT ["streamlit", "run", "dumblexity.py", "--server.port=8501", "--server.address=0.0.0.0"]