# 안전보건 뉴스룸

산업안전·산업보건 국내 뉴스를 평일 8시~18시 매시간 자동으로 모아 보여주는 웹페이지입니다.
Claude 없이 GitHub의 무료 기능만으로 돌아가며, 링크만 있으면 누구나 로그인 없이 볼 수 있습니다.

## 구성

| 파일 | 하는 일 |
|---|---|
| `collect.py` | 뉴스 검색 → 조건에 맞는 기사만 골라 분류 → 같은 사건 기사 묶기 → `data/news.json` 저장 |
| `config.json` | 검색어, 분류 키워드, 제외 단어 (여기만 고치면 수집 기준이 바뀜) |
| `index.html` | 화면. `data/news.json`을 읽어 보여주고 10분마다 새로 확인 |
| `.github/workflows/collect.yml` | 평일 8~18시 매시간 `collect.py`를 실행하는 자동 예약 |
| `data/news.json` | 수집된 기사 (최근 90일 보관). 처음에는 9월 29일 기사 13건이 들어 있음 |

## 설치 (처음 한 번, 약 20분)

### 1. 네이버 뉴스 검색 키 발급 (선택)

**건너뛰어도 됩니다.** 키가 없으면 구글 뉴스 RSS로 자동 수집되므로 바로 2단계로 가셔도 시스템은 돌아갑니다.
네이버 키를 쓰면 기사 요약문이 함께 오고 국내 언론 범위가 넓어집니다. 나중에 추가해도 됩니다.

네이버 개발자센터의 검색 API는 2026년 7월 31일부터 신규 발급이 끝나고 **NAVER API HUB**(네이버 클라우드 플랫폼)로 옮겨졌습니다.
그래서 개발자센터의 '사용 API' 목록에는 더 이상 '검색'이 나오지 않습니다.

1. [네이버 클라우드 플랫폼](https://www.ncloud.com)에 가입하고 콘솔에 로그인
2. 서비스 목록에서 **NAVER API HUB**를 찾아 애플리케이션을 새로 만들고, 사용할 API로 **뉴스 검색**을 선택
3. 발급된 **Client ID**와 **Client Secret**을 메모 (네이버 클라우드의 계정 Access Key와는 다른 것입니다)

2026년 9월 현재 무료로 제공되며, 이 시스템은 하루 약 260회를 호출합니다.
예전에 개발자센터에서 받아 둔 키가 있다면 3단계에서 `NAVER_API` 이름으로 값 `legacy`를 하나 더 등록하면 그 키를 쓸 수 있습니다(2027년 6월 30일까지).

### 2. GitHub 저장소 만들기

1. [github.com](https://github.com) 가입(회사 계정 권장) → 오른쪽 위 **+ → New repository**
2. 이름: `safety-newsroom`, **Public** 선택 → **Create repository**
3. 새 저장소 화면에서 **uploading an existing file** 클릭 → 이 폴더의 파일을 모두 끌어다 놓고 **Commit changes**
   - `.github` 폴더는 숨김 폴더라 끌어다 놓기에서 빠질 수 있습니다. 빠졌다면 **Add file → Create new file**에서
     이름을 `.github/workflows/collect.yml`로 입력하고 내용을 붙여 넣으세요.

### 3. API 키 등록 (1단계를 건너뛰었다면 이 단계도 건너뜀)

저장소의 **Settings → Secrets and variables → Actions → New repository secret**에서 두 개를 추가합니다.

- `NAVER_CLIENT_ID` : 1단계의 Client ID
- `NAVER_CLIENT_SECRET` : 1단계의 Client Secret

키가 틀렸거나 네이버 쪽에 문제가 있으면 수집기가 자동으로 구글 뉴스로 바꿔 수집하고, Actions 로그에 그 사실을 남깁니다.

### 4. 자동 수집 권한 켜기

**Settings → Actions → General → Workflow permissions**에서 **Read and write permissions** 선택 → Save.

### 5. 웹페이지 공개

**Settings → Pages → Build and deployment**에서 Source: **Deploy from a branch**, Branch: **main / (root)** → Save.
1~2분 뒤 `https://<GitHub아이디>.github.io/safety-newsroom/` 주소가 생깁니다. 이 주소를 팀원에게 공유하면 됩니다.

### 6. 첫 수집 테스트

**Actions 탭 → 뉴스 수집 → Run workflow**를 누르고 1~2분 기다립니다. 초록 체크가 뜨면 페이지를 새로고침해 새 기사를 확인하세요.
이후로는 평일 8시~18시 매시간(7분경) 자동으로 실행됩니다.

## 운영 팁

- **엉뚱한 기사가 섞일 때**: `config.json`의 `exclude_if_any`에 단어를 추가합니다.
- **놓치는 기사가 있을 때**: 해당 분류의 `queries`에 검색어를 추가합니다. 검색어 하나당 매시간 한 번 검색합니다.
- **분류가 어긋날 때**: 각 분류의 `keywords`를 조정합니다. 제목에 들어간 단어는 2점, 요약문에 들어간 단어는 1점, 그 분류 검색어로 찾은 기사는 2점을 더해 점수가 가장 높은 분류로 갑니다.
- **많이 보도된 이슈**: 제목이 비슷한 기사를 한 건으로 묶고, 가장 많은 언론이 다룬 순서로 최대 5건을 보여줍니다. AI 요약은 아닙니다.
- GitHub 예약 실행은 서버 사정으로 몇 분에서 수십 분 늦을 수 있습니다.
- 수집 이력이 매시간 커밋으로 남습니다. 문제가 생기면 Actions 탭에서 실패한 실행의 로그를 확인하세요.

## 공개 범위

무료 GitHub Pages 주소는 **인터넷에 공개**됩니다. 뉴스 링크 모음이라 민감한 내용은 없지만, 팀 메모 같은 내부 정보는 넣지 마세요.
사내에서만 보이게 하려면 아래 사내 서버 방식을 쓰거나, GitHub Enterprise의 비공개 Pages를 사용해야 합니다.

## 사내 서버에서 돌리기 (GitHub를 쓸 수 없을 때)

파이썬 3.9 이상이 있는 리눅스 서버면 됩니다. 추가 패키지는 필요 없습니다.

```bash
# 1) 폴더를 서버에 복사 (예: /opt/safety-newsroom)
# 2) 수집 테스트
cd /opt/safety-newsroom
NAVER_CLIENT_ID=발급ID NAVER_CLIENT_SECRET=발급Secret python3 collect.py

# 3) 예약 등록: crontab -e 에 아래 줄 추가 (평일 8~18시 매시간 7분)
#    서버 시간대가 이미 한국 시간(KST)이면 CRON_TZ 줄은 빼도 됩니다.
#    CRON_TZ를 지원하지 않는 cron이라면 서버 시간대를 KST로 맞춰 주세요.
CRON_TZ=Asia/Seoul
7 8-18 * * 1-5 cd /opt/safety-newsroom && NAVER_CLIENT_ID=발급ID NAVER_CLIENT_SECRET=발급Secret python3 collect.py >> collect.log 2>&1
```

화면은 이 폴더를 웹 서버(nginx, IIS, 사내 포털의 정적 파일 경로 등)로 서비스하면 됩니다.
간단히 확인만 하려면 `python3 -m http.server 8080`을 실행한 뒤 `http://서버주소:8080`으로 접속하세요.
(`index.html`을 파일로 바로 열면 브라우저 보안 때문에 기사가 안 보입니다. 반드시 웹 서버를 거쳐야 합니다.)

Windows 서버라면 작업 스케줄러에 같은 명령(`python collect.py`)을 평일 8~18시 1시간 간격으로 등록하면 됩니다.
