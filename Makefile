# ==========================================
# Configuration
# ==========================================
# [필수] 본인의 Docker Hub 사용자명으로 변경하세요.
DOCKER_USER ?= rapaellk
# 이미지 이름
IMAGE_NAME ?= dumblexity
# 버전 태그 (릴리스할 때마다 변경)
VERSION ?= 0.0.9

# 전체 이미지 이름 조합 (예: rapaellk/dumblexity)
FULL_IMAGE_NAME := $(DOCKER_USER)/$(IMAGE_NAME)

# 로컬 테스트용 컨테이너 이름
CONTAINER_NAME := $(IMAGE_NAME)-dev

# ==========================================
# Targets
# ==========================================
.PHONY: help build tag push release run stop clean

help: ## 사용 가능한 명령어 목록을 표시합니다.
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

run:
	streamlit run ./dumblexity.py

build: ## 로컬에서 Docker 이미지를 빌드합니다.
	@echo "🐳 Building docker image: $(IMAGE_NAME)..."
	docker build -t $(IMAGE_NAME) .

tag: build ## 빌드된 이미지에 Docker Hub용 태그(버전 + latest)를 붙입니다.
	@echo "🏷️ Tagging image as $(FULL_IMAGE_NAME):$(VERSION) and latest..."
	docker tag $(IMAGE_NAME) $(FULL_IMAGE_NAME):$(VERSION)
	docker tag $(IMAGE_NAME) $(FULL_IMAGE_NAME):latest

push: tag ## 태그된 이미지를 Docker Hub에 푸시합니다. (로그인 필요)
	@echo "🚀 Pushing image to Docker Hub..."
	docker push $(FULL_IMAGE_NAME):$(VERSION)
	docker push $(FULL_IMAGE_NAME):latest
	@echo "✅ Push complete! Available at https://hub.docker.com/r/$(DOCKER_USER)/$(IMAGE_NAME)"

release: push ## [원스톱] 빌드 -> 태그 -> 푸시 과정을 한 번에 수행합니다.
	@echo "🎉 Release $(VERSION) completed successfully!"

docker-run: stop ## 로컬에서 컨테이너를 실행합니다. (GOOGLE_API_KEY 환경변수 필요)
	@echo "▶️ Running container locally..."
	@mkdir -p $(PWD)/sessions
	docker run -d --name $(CONTAINER_NAME) \
		-p 8501:8501 \
		-e GOOGLE_API_KEY=${GOOGLE_API_KEY} \
		-v $(PWD)/sessions:/app/sessions \
		$(IMAGE_NAME)
	@echo "🔗 App is running at http://localhost:8501"

stop: ## 로컬에서 실행 중인 컨테이너를 중지하고 삭제합니다.
	@echo "🛑 Stopping container..."
	@docker rm -f $(CONTAINER_NAME) 2>/dev/null || true

clean: stop ## 로컬에 생성된 이미지와 컨테이너를 정리합니다.
	@echo "🧹 Cleaning up local images..."
	docker rmi $(IMAGE_NAME) $(FULL_IMAGE_NAME):$(VERSION) $(FULL_IMAGE_NAME):latest 2>/dev/null || true