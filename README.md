# Dumblexity - simple version of pseudo-Perplexity using Gemini + Streamlit

* Docker: https://hub.docker.com/repository/docker/rapaellk/dumblexity/general
* Github: https://github.com/TaeHunKim/dumblexity

* TODO: Inline citation, multimodal and other grounds (file, ...)

* How to install:

```bash
docker run -d \
  --name my-ai-assistant \
  -p 8501:8501 \
  -e GEMINI_API_KEY="여기에_실제_API_KEY를_입력하세요" \
  -e TAVILY_API_KEY="여기에_실제_API_KEY를_입력하세요" \
  -e YOUTUBE_DATA_API_KEY="여기에_실제_API_KEY를_입력하세요" \
  -v $(pwd)/sessions:/app/sessions \
  --restart unless-stopped \
  dumblexity
```

* docker-compose.yaml (use with `docker-compose up -d`)

```yaml
version: '3.8'
services:
  dumblexity:
    image: rapaellk/dumblexity:latest
    container_name: my-ai-assistant
    ports:
      - "8501:8501"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY} # .env 파일이나 시스템 환경변수에서 가져옴
      - TAVILY_API_KEY=${TAVILY_API_KEY} # .env 파일이나 시스템 환경변수에서 가져옴
      - YOUTUBE_DATA_API_KEY=${YOUTUBE_DATA_API_KEY} # .env 파일이나 시스템 환경변수에서 가져옴
    volumes:
      - ./sessions:/app/sessions
    restart: unless-stopped
```
