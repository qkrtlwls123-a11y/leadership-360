# NAS 환경 설치 및 실행 가이드

## 1) Python 패키지 설치

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install gspread pymysql flask
```

## 2) MariaDB 준비

1. MariaDB에 데이터베이스 생성
   ```sql
   CREATE DATABASE survey_db DEFAULT CHARACTER SET utf8mb4;
   ```
2. `schema.sql` 실행
   ```bash
   mysql -u root -p survey_db < schema.sql
   ```

## 3) 서비스 계정 인증 파일 준비

* Google Cloud에서 Service Account 생성 후 `service_account.json`을 프로젝트 루트에 저장합니다.
* 해당 서비스 계정에 Google Sheet 공유 권한을 부여해야 합니다.

## 4) 환경 변수 설정

```bash
export DB_HOST=127.0.0.1
export DB_PORT=3306
export DB_USER=root
export DB_PASSWORD=비밀번호
export DB_NAME=survey_db
export GOOGLE_SERVICE_ACCOUNT=service_account.json
export FORMS_CONFIG_PATH=forms_config.json
```

## 5) 동기화 스크립트 실행

```bash
python sync_survey.py
```

## 6) 웹 어드민 실행

```bash
python app.py
```

브라우저에서 `http://<NAS_IP>:5000` 접속 후 **동기화 실행** 버튼을 클릭합니다.
