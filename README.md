# MES Sample — Web MES + Desktop MES

Tkinter 데스크톱 MES는 [`desktop/`](desktop/)에 보존되어 있고, 저장소 루트에는 Flask 웹 MES가 있습니다. 두 버전은 SQLite 데이터 파일을 각각 사용합니다.

## 프로젝트 구조

```text
app.py                 Flask 앱 및 SQLite 스키마/업무 로직
templates/             Jinja2 화면
static/                Bootstrap 기반 반응형 CSS와 JavaScript
instance/              로컬 웹 DB (Git 제외)
desktop/               기존 Tkinter 앱, 기존 DB, 데스크톱 실행 파일
requirements.txt       Python 패키지
render.yaml            Render Blueprint 배포 설정
run_web.bat            Windows 로컬 웹 실행
```

## 로컬 실행

Python 3.10 이상이 필요합니다.

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app app run --host 127.0.0.1 --port 5000
```

또는 Windows에서 `run_web.bat`을 실행합니다. 브라우저에서 <http://127.0.0.1:5000>을 엽니다. `instance/mes.db`는 기존 `mes.db`의 제품·실적 데이터를 첫 실행 시 복사해 시작합니다. 웹 DB는 `.gitignore` 대상이라 GitHub에 업로드되지 않습니다.

환경별 DB 경로는 `MES_DATABASE`로 지정할 수 있습니다. 테스트는 임시 경로를 사용하고, 운영 환경은 별도 영속 디스크 경로를 사용합니다. 로그인 보호가 필요한 로컬 환경은 `Copy-Item .env.example .env`로 설정 파일을 만든 다음 `SECRET_KEY`, `MES_USERNAME`, `MES_PASSWORD`를 수정하세요. `.env`는 저장소에서 제외됩니다.

Render에는 DB 파일이 자동 전송되지 않습니다. 기존 데스크톱 데이터를 운영 서비스로 옮기려면 `desktop/mes.db` 또는 검토한 로컬 백업을 별도로 보관하고, Render 서비스 디스크로 안전하게 전송해 `/var/data/mes.db`에 배치하세요. Render 문서에 SSH/SCP와 Magic-Wormhole 전송 절차가 있습니다. 데이터 파일을 교체할 때는 서비스 쓰기를 멈추고 별도 백업을 먼저 만드세요.

## 주요 업무 흐름

1. **기준정보**에서 제품을 확인하거나 추가합니다.
2. **생산계획**을 등록합니다.
3. **작업지시**에서 계획과 설비를 선택합니다. 지시번호는 `WO-YYYYMMDD-001` 형식으로 자동 발급됩니다.
4. **생산실적**에서 작업지시와 생산/불량수량을 입력합니다. 양품수량, 달성률, 불량률을 화면에서 계산합니다.
5. **불량관리**에서 실적과 연결된 불량유형·원인·조치를 입력합니다.
6. **설비현황**에서 설비 상태를 관리하고 대시보드 KPI를 확인합니다.

## GitHub 업로드

Git이 설치되어 있고 GitHub 계정에서 새 빈 저장소를 만든 뒤, 프로젝트 폴더에서 실행합니다.

```powershell
git init
git add .
git commit -m "Build web MES application"
git branch -M main
git remote add origin https://github.com/<사용자명>/<저장소명>.git
git push -u origin main
```

`git status`에서 `mes.db`, `desktop/mes.db`, 백업, `.env`, `instance/mes.db`가 추적 대상으로 표시되지 않는지 확인한 뒤 업로드하세요. `desktop/` 안의 Python 앱과 실행 스크립트는 소스 파일이라 저장소에 포함됩니다.

## Render 배포

저장소에는 `render.yaml` Blueprint가 있습니다. GitHub에 push한 다음 Render에서 **New → Blueprint**를 선택하고 저장소를 연결해 설정을 확인한 뒤 생성합니다. Blueprint는 Python 웹 서비스, Gunicorn 시작 명령, 비밀 `SECRET_KEY`, `/var/data/mes.db` 경로의 영속 디스크를 정의합니다. SQLite 파일을 재배포 뒤에도 유지하려면 이 디스크가 필요합니다.

Blueprint 없이 만들 경우 Render에서 **New → Web Service**로 저장소를 연결하고 다음 값을 사용합니다.

| 설정 | 값 |
|---|---|
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120` |
| `MES_DATABASE` 환경변수 | `/var/data/mes.db` |
| Disk mount path | `/var/data` |

`SECRET_KEY`, `MES_USERNAME`, `MES_PASSWORD`는 Render 환경변수로 생성/설정하며 Blueprint는 비밀번호 값을 생성합니다. 서비스 환경변수 화면에서 생성된 로그인 비밀번호를 확인해 운영자에게 안전하게 전달하세요. 로컬은 기본적으로 로그인을 요구하지 않으며, `.env.example` 값처럼 `MES_USERNAME`과 `MES_PASSWORD`를 함께 지정하면 로그인 보호가 활성화됩니다. Render 무료 웹 서비스의 파일시스템은 영구 저장소가 아니므로 SQLite 운영 DB를 보존하려면 persistent disk를 지원하는 유료 웹 서비스 플랜을 선택해야 합니다. SQLite는 단일 인스턴스 데모/소규모 운영에 맞습니다.

## 실제 접속 URL

배포가 성공하면 Render 서비스 상세 화면의 `https://<서비스명>.onrender.com` 주소가 공개 접속 URL입니다. 해당 주소를 방문해 대시보드와 화면을 확인할 수 있습니다. 사용자 도메인을 연결하려면 Render 서비스의 **Settings → Custom Domains**에서 도메인을 추가하고 안내된 DNS 레코드를 도메인 업체에 설정합니다. DNS 확인과 TLS 발급이 완료되면 사용자 도메인으로 접속합니다.
